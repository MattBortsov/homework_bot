import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot
from telebot.apihelper import ApiException


load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM')
TELEGRAM_TOKEN = os.getenv('TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет наличие всех необходимых переменных окружения."""
    tokens = {
        'practicum': PRACTICUM_TOKEN,
        'telegram': TELEGRAM_TOKEN,
        'chat_id': TELEGRAM_CHAT_ID
    }
    missing_tokens = [name for name, token in tokens.items() if not token]

    if missing_tokens:
        error_message = (
            'Отсутствуют обязательные переменные окружения: '
            f'{", ".join(missing_tokens)}'
        )
        logging.critical(error_message)
        raise OSError(error_message)


def send_message(bot, message):
    """Отправляет сообщение в Telegram."""
    logging.debug(f'Начало отправки сообщения: {message}')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Бот отправил сообщение: {message}')
    except (ApiException, requests.RequestException) as error:
        logging.error(f'Ошибка при отправке сообщения: {error}')


def get_api_answer(timestamp):
    """Делает запрос к API сервиса Практикум Домашка."""
    timestamp = {'from_date': timestamp}
    logging.debug(f'Начало запроса к API: {ENDPOINT}, параметры: {timestamp}')
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=timestamp)
    except requests.exceptions.RequestException as error:
        raise ConnectionError(
            f'Ошибка при запросе к API {ENDPOINT} '
            f'с параметрами {timestamp}: {error}'
        )

    if response.status_code != HTTPStatus.OK:
        raise ValueError(
            f'Эндпоинт {ENDPOINT} недоступен. '
            f'Код ответа API: {response.status_code} ({response.reason})'
        )
    return response.json()


def check_response(response):
    """Проверяет корректность ответа API."""
    logging.debug('Начало проверки ответа от API.')

    if not isinstance(response, dict):
        raise TypeError(
            'Ответ от API должен быть словарём. '
            f'Получен тип: {type(response).__name__}.'
        )

    if 'homeworks' not in response:
        raise KeyError('В ответе API отсутствуют ожидаемый ключ - homeworks.')
    homeworks = response['homeworks']

    if not isinstance(homeworks, list):
        raise TypeError(
            'По ключу "homeworks" должен быть список. '
            f'Получен тип: {type(homeworks).__name__}.'
        )

    logging.debug('Проверка ответа от API завершена успешно.')
    return homeworks


def parse_status(homework):
    """Извлекает статус работы из информации о домашней работе."""
    logging.debug('Начало извлечения статуса работы.')
    if 'homework_name' not in homework:
        raise KeyError('В ответе API отсутствует ключ "homework_name".')
    if 'status' not in homework:
        raise KeyError('В ответе API отсутствует ключ "status".')
    homework_name = homework['homework_name']
    homework_status = homework['status']

    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Недокументированный статус: {homework_status}')

    verdict = HOMEWORK_VERDICTS[homework_status]
    logging.debug('Извлечение статуса работы завершена успешно.')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    last_error_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
                last_error_message = ''
            else:
                logging.debug('Нет новых статусов для проверки.')
            timestamp = response.get('current_date', int(time.time()))
        except Exception as error:
            error_message = f'Сбой в работе программы: {error}'
            logging.error(error_message)
            if error_message != last_error_message:
                send_message(bot, error_message)
                last_error_message = error_message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)s %(funcName)s %(message)s ',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    main()
