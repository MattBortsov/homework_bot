import logging
import os
import requests
import time

from dotenv import load_dotenv
from telebot import TeleBot, types


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

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)


def check_tokens():
    """Проверяет наличие всех необходимых переменных окружения."""
    tokens = {
        'practicum': PRACTICUM_TOKEN,
        'telegram': TELEGRAM_TOKEN,
        'chat_id': TELEGRAM_CHAT_ID
    }
    missing_tokens = [name for name, token in tokens.items() if not token]

    if missing_tokens:
        logging.critical(
            f'Отсутствуют обязательные переменные окружения:'
            f'{", ".join(missing_tokens)}'
        )
        return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Бот отправил сообщение: {message}')
    except Exception as error:
        logging.error(f'Ошибка при отправке сообщения: {error}')


def get_api_answer(timestamp):
    """Делает запрос к API сервиса Практикум Домашка."""
    timestamp = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=timestamp)
        if response.status_code != 200:
            error_message = (
                f'Эндпоинт {ENDPOINT} недоступен.'
                f'Код ответа API: {response.status_code}'
            )
            logging.error(error_message)
            raise Exception(error_message)
        return response.json()
    except requests.exceptions.RequestException as error:
        error_message = f'Ошибка при запросе к API: {error}'
        logging.error(error_message)
        raise Exception(error_message)


def check_response(response):
    """Проверяет корректность ответа API."""
    if not isinstance(response, dict):
        raise TypeError('Ответ от API должен быть словарём.')
    if 'homeworks' not in response or 'current_date' not in response:
        raise KeyError('В ответе API отсутствуют ожидаемые ключи.')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('По ключу "homeworks" должен быть список.')
    return homeworks


def parse_status(homework):
    """Извлекает статус работы из информации о домашней работе."""
    if 'homework_name' not in homework:
        raise KeyError('В ответе API отсутствует ключ "homework_name".')
    if 'status' not in homework:
        raise KeyError('В ответе API отсутствует ключ "status".')
    homework_name = homework['homework_name']
    homework_status = homework['status']

    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Недокументированный статус: {homework_status}')

    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""

    if not check_tokens():
        return

    # Создаем объект класса бота
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time() - 60 * 86400)

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
            else:
                # Логируем отсутствие изменений статуса
                logging.debug('Нет новых статусов для проверки.')
            timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
