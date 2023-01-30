import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from telegram import TelegramError

from exceptions import (EndpointError, InvalidResponseExc, ResponseFormatError)

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s - %(lineno)d - %(name)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    errors = []
    keys = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']
    for key in keys:
        globals()[key]
        if not key:
            errors.append(key)
    if len(errors):
        logging.error('Cписок с отстутсвующими переменными не пуст "{key}".')
        sys.exit()
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))
# я не смог убрать return
# просто иначе pytest не проходит, видимо ему нужно,
# чтобы переменные возвращались, подсмотрел такую штуку
# как all() по идее она теперь возвращает значение True
# если все элементы в итерируемом объекте - истинны


def send_message(bot, message):
    """Отправляет сообщение пользователю в Телегу."""
    try:
        logger.debug(f'Попытка обращения к чату ={TELEGRAM_CHAT_ID}=')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except TelegramError as error:
        logger.exception(f'Не удалось отправить сообщение "{message}"'
                         f'по причине ошибки "{error}"', exc_info=True)
    else:
        logger.info(
            f'В Telegram успешно отправлено сообщение "{message}"'
        )


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    all_params = dict(url=ENDPOINT, headers=HEADERS, params=params)
    try:
        response = requests.get(**all_params)
    except requests.exceptions.RequestException as error:
        raise ConnectionError(
            '{error}, {url}, {params}'.format(
                error=error,
                **all_params,
            )
        )
    response_status = response.status_code
    if response_status != HTTPStatus.OK:
        raise EndpointError(
            '{response_status}, {url}, {params}'.format(
                response_status=response_status,
                **all_params,
            )
        )
    try:
        return response.json()
    except TypeError as error:
        raise ResponseFormatError(
            f'Формат декаодирования не json {error}'.format(error)
        )


def check_response(response):
    """Проверка ответа API и возврат списка работ."""
    logger.info('Начало проверки ответа API')
    if not isinstance(response, dict):
        raise TypeError('not dict после .json() в ответе API')
    if 'homeworks' not in response:
        raise KeyError('Некорректный ответ API')
    if 'current_date' not in response:
        raise TypeError('Некорректный ответ API')
    if not isinstance(response.get('homeworks'), list):
        raise TypeError('not list в ответе API по ключу homeworks')
    try:
        return response.get('homeworks')
    except Exception as error:
        raise InvalidResponseExc(f'Из ответа не получен список работ: {error}')


def parse_status(homework):
    """Возвращает текст сообщения от ревьюера."""
    if 'homework_name' not in homework:
        raise KeyError('Ключ homework_name отсутствует')
    if 'status' not in homework:
        raise KeyError('Ключ status отсутствует')
    homework_name = homework['homework_name']
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(
            f'Статус работы: "{homework_status}"'
        )
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Недоступны переменные окружения!')
        raise SystemExit('Ошибка глобальной переменной. Смотрите логи.')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    current_report = {
        'messages': ''
    }
    prev_report = {
        'messages': ''
    }
    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = (
                response.get('current_date', current_timestamp)
            )
            homeworks = check_response(response)
            if homeworks:
                homework = homeworks[0]
                current_report['name'] = homework.get('homework_name')
                status = parse_status(homework)
                current_report['messages'] = status
            else:
                current_report['messages'] = 'ДЗ отсутствует.'
                status = 'Новых статусов нет!'
            if current_report != prev_report:
                send_message(bot=bot, message=status)
                prev_report = current_report.copy()
            else:
                logger.debug('Новые статусы отсутствуют')

        except Exception as error:
            error_text = f'Произошла ошибка: {error}.'
            logger.error(error, exc_info=True)
            current_report['messages'] = error_text
            if current_report != prev_report:
                send_message(bot=bot, message=error_text)
                prev_report = current_report.copy()

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':

    main()
