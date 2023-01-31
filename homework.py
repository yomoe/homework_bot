import logging
import os
import sys
import time
from http import HTTPStatus
from os import getenv

import requests
import telegram
from requests import RequestException
from telegram.error import BadRequest, NetworkError, TimedOut, Unauthorized

from exceptions import APIErrors, TelegaCustomError

PRACTICUM_TOKEN = getenv('YAP_TOKEN')
TELEGRAM_TOKEN = getenv('TG_TOKEN')
TELEGRAM_CHAT_ID = getenv('TG_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def check_tokens() -> bool:
    """Проверяет наличие токенов."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot: telegram.Bot, message: str) -> None:
    """Отправляет сообщение в телеграм."""
    try:
        logging.debug(f'Пытаемся отправить сообщение: {message}')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug(f'Сообщение отправлено: {message}')
    except BadRequest:
        raise BadRequest('Неверный запрос к API телеграма')
    except TimedOut:
        raise TimedOut()
    except NetworkError:
        raise NetworkError('Ошибка сети при обращение к API телеграма')
    except Unauthorized:
        logging.critical('Проверьте токен телеграма и права бота')
        raise Unauthorized('Неверный токен телеграма или права бота')
    except telegram.TelegramError as error:
        logging.error(f'Ошибка телеграма {error}')
        raise TelegaCustomError(f'Ошибка телеграма {error}')


def get_api_answer(timestamp: int = 0) -> dict:
    """Запрашивает у API Яндекс.Практикум статус домашней работы."""
    try:
        logging.debug(f'Пытаемся получить ответ API: {timestamp}')
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        logging.debug(f'Ответ API: {homework_statuses.text}')

        if homework_statuses.status_code != HTTPStatus.OK:
            raise RequestException(
                f'Неверный ответ API: {homework_statuses.text}')

    except ConnectionError:
        raise ConnectionError('Сбой при запросе к эндпоинту')
    except APIErrors:
        raise APIErrors('Ошибка при запросе к API')
    except Exception as error:
        raise Exception(f'Ошибка при запросе к API: {error}')

    try:
        return homework_statuses.json()
    except ValueError as error:
        raise ValueError(f'Не удалось декодировать ответ API: {error}')


def check_response(response: dict) -> dict:
    """Проверяет полученный ответ на корректность."""
    logging.debug(f'Проверяем ответ {response} на корректность')
    if not isinstance(response, dict) or not isinstance(
            response.get('homeworks'), list):
        raise TypeError('Неверный формат ответа API')
    if not response.get('homeworks'):
        raise TypeError('Нет новых домашних работ')
    logging.debug('Есть домашние работы')
    return response.get('homeworks')[0]


def parse_status(homework: dict) -> str:
    """Парсит ответ API и возвращает сообщение для телеграма."""
    logging.debug(f'Парсим ответ API: {homework}')
    homework_name = homework.get('homework_name')
    if not homework_name:
        raise KeyError('Не указано название домашней работы')
    hw_status = homework.get('status')
    logging.debug(f'Получен статус "{hw_status}" для работы {homework_name}')
    if hw_status not in HOMEWORK_VERDICTS:
        raise ValueError('Неизвестный статус домашней работы')
    verdict = HOMEWORK_VERDICTS[hw_status]
    logging.debug(
        f'Изменился статус проверки работы "{homework_name}": {verdict}'
    )
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main() -> None:
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
            print(last_hw)
            if last_hw:
                send_message(bot, parse_status(last_hw))
            logging.info('Скрипт ожидает следующей проверки')
            time.sleep(RETRY_PERIOD)
        except Exception as error:
            if str(error) == 'Нет новых домашних работ':
                logging.info(error)
            else:
                logging.error(f'Сбой в работе программы: {error}')
        finally:
            logging.info('Скрипт ожидает следующей проверки')
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
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
    main()
