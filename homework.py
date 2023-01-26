import logging
import os
import sys
import time
from http import HTTPStatus
from os import getenv

import requests
import telegram
from requests import RequestException

PRACTICUM_TOKEN = getenv('YAP_TOKEN')
TELEGRAM_TOKEN = getenv('TG_TOKEN')
TELEGRAM_CHAT_ID = 132016857

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

logging.basicConfig(
    level=logging.INFO,
    format=(
        u'%(filename)s:%(lineno)d #%(levelname)-8s '
        u'[%(asctime)s] - %(name)s - %(message)s'
    ),
    handlers=[
        logging.StreamHandler(stream=sys.stdout),
        logging.FileHandler(f'{BASE_DIR}/bot.log', mode='w')
    ]
)


def check_tokens():
    """Проверяет наличие токенов."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN])


def send_message(bot, message):
    """Отправляет сообщение в телеграм."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug(f'Сообщение отправлено: {message}')
    except Exception:
        logging.error('Ошибка отправки сообщения')
        raise Exception('Ошибка отправки сообщения')


def get_api_answer(timestamp):
    """Запрашивает у API Яндекс.Практикум статус домашней работы."""
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        logging.debug(f'Ответ API: {homework_statuses.text}')

        if homework_statuses.status_code != HTTPStatus.OK:
            logging.error(f'Неверный ответ API: {homework_statuses.text}')
            raise RequestException(
                f'Неверный ответ API: {homework_statuses.text}')

    except Exception as error:
        logging.error(f'Ошибка при запросе к API: {error}')
        raise Exception(f'Ошибка при запросе к API: {error}')
    except ConnectionError:
        logging.error('Сбой при запросе к эндпоинту')
        raise ConnectionError('Сбой при запросе к эндпоинту')

    try:
        return homework_statuses.json()
    except ValueError as error:
        logging.error(f'Не удалось декодировать ответ API: {error}')
        raise ValueError(f'Не удалось декодировать ответ API: {error}')


def check_response(response):
    """Проверяет полученный ответ на корректность."""
    if not isinstance(response, dict) or not isinstance(
            response.get('homeworks'), list):
        logging.error('Неверный формат ответа API')
        raise TypeError('Неверный формат ответа API')
    if not response.get('homeworks'):
        logging.debug('Нет новых домашних работ')
        raise TypeError('Нет новых домашних работ')
    logging.debug('Есть домашние работы')
    return response.get('homeworks')[0]


def parse_status(homework):
    """Парсит ответ API и возвращает сообщение для телеграма."""
    homework_name = homework.get('homework_name')
    if not homework_name:
        logging.error('Не указано название домашней работы')
        raise KeyError('Не указано название домашней работы')
    hw_status = homework.get('status')
    logging.info(f'Получен статус "{hw_status}" для работы ')
    if hw_status not in HOMEWORK_VERDICTS:
        logging.error('Неизвестный статус домашней работы')
        raise ValueError('Неизвестный статус домашней работы')
    verdict = HOMEWORK_VERDICTS[hw_status]
    logging.debug(
        f'Изменился статус проверки работы "{homework_name}": {verdict}'
    )
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    logging.info('Программа стартует')
    if not check_tokens():
        logging.critical('Не указаны токены')
        sys.exit('Не указаны токены')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            if 'current_date' in response:
                timestamp = response['current_date']
            last_hw = check_response(response)
            if last_hw:
                send_message(bot, parse_status(last_hw))
            logging.info('Скрипт ожидает следующей проверки')
            time.sleep(RETRY_PERIOD)
        except Exception as error:
            logging.error(f'Сбой в работе программы: {error}')
        finally:
            logging.info('Скрипт ожидает следующей проверки')
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
