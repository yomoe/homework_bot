import logging
import sys
import time
from datetime import datetime
from http import HTTPStatus
from os import getenv
from pytz import timezone

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

LOCAL_TIMEZONE = 'Asia/Bangkok'

logging.basicConfig(
    level=logging.INFO,
    format=(
        u'%(filename)s:%(lineno)d #%(levelname)-8s '
        u'[%(asctime)s] - %(name)s - %(message)s'
    ),
    filename='bot.log',
    filemode='w'
)
console = logging.StreamHandler(sys.stdout)


def check_tokens():
    """Проверяет наличие токенов."""
    if not PRACTICUM_TOKEN or not TELEGRAM_TOKEN:
        logging.critical('Не указаны токены')
        raise ValueError('Не указаны токены')
    logging.info('Токены указаны')
    return True


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
    """Проверяет ответ API на наличие домашних работ."""
    if not isinstance(response, dict) or not isinstance(
            response.get('homeworks'), list):
        logging.error('Неверный формат ответа API')
        raise TypeError('Неверный формат ответа API')
    if not response.get('homeworks'):
        logging.debug('Нет новых домашних работ')
        raise KeyError('Нет новых домашних работ')
    logging.debug('Есть домашние работы')
    return True


def parse_status(homework):
    """Парсит ответ API и возвращает сообщение для телеграма."""
    if not homework.get('homework_name'):
        logging.error('Не указано название домашней работы')
        raise ValueError('Не указано название домашней работы')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        logging.error('Неизвестный статус домашней работы')
        raise ValueError('Неизвестный статус домашней работы')
    verdict = HOMEWORK_VERDICTS[homework_status]
    logging.debug(f'Статус проверки работы "{homework_name}": {verdict}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    logging.info('Программа стартует')
    if check_tokens():

        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        timestamp = int(time.time())
        timestamp_for_requests = int(datetime(2022, 10, 18).timestamp())

        while True:
            try:
                homeworks = get_api_answer(timestamp_for_requests)
                if check_response(homeworks):
                    # Получаем время последнего обновления домашней работы
                    hw_date_upd = int(
                        datetime.strptime(
                            homeworks.get('homeworks')[0].get('date_updated'),
                            '%Y-%m-%dT%H:%M:%S%z'
                        ).astimezone(timezone(LOCAL_TIMEZONE)).timestamp())
                    if timestamp < hw_date_upd:
                        timestamp = int(time.time())
                        message = parse_status(homeworks.get('homeworks')[0])
                        send_message(bot, message)
                logging.info('Скрипт ожидает следующей проверки')
                time.sleep(RETRY_PERIOD)
            except Exception as error:
                message = f'Сбой в работе программы: {error}'
                logging.error(message)
            finally:
                time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
