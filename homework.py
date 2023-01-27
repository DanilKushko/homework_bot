import logging
import os
import sys
import time
from pathlib import Path

import requests
import telegram
from dotenv import load_dotenv

from mistakes import (EmptyListException, EndpointError, GlobalsError,
                      InvalidApiExc, InvalidResponseExc, ResponseFormatError)

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
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
    for key in (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, ENDPOINT):
        if key is None:
            logging.error('Отсутствует глобальная переменная')
            return False
        if not key:
            logging.error('Пустая глобальная переменная')
            return False
    return True


def send_message(bot, message):
    """Отправляет сообщение пользователю в Телегу."""
    try:
        logger.debug(f'Попытка обращения к чату ={TELEGRAM_CHAT_ID}=')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as error:
        logger.error(f'Не удалось отправить сообщение "{message}"'
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
        raise telegram.TelegramError(
            '{error}, {url}, {headers}, {params}'.format(
                error=error,
                **all_params,
            )
        )
    response_status = response.status_code
    if response_status != 200:
        raise EndpointError(
            '{response_status}, {url}, {headers}, {params}'.format(
                response_status=response_status,
                **all_params,
            )
        )
    try:
        return response.json()
    except Exception as error:
        raise ResponseFormatError(
            f'Формат не json {error}'.format(error)
        )


def check_response(response):
    """Проверка ответа API и возврат списка работ."""
    if not isinstance(response, dict):
        raise TypeError('not dict после .json() в ответе API')
    if 'homeworks' and 'current_date' not in response:
        raise InvalidApiExc('Некорректный ответ API')
    if not isinstance(response.get('homeworks'), list):
        raise TypeError('not list в ответе API по ключу homeworks')
    if not response.get('homeworks'):
        raise EmptyListException('Новых статусов нет')
    try:
        return response.get('homeworks')[0]
    except Exception as error:
        raise InvalidResponseExc(f'Из ответа не получен список работ: {error}')


def parse_status(homework):
    """Возвращает текст сообщения от ревьюера."""
    if not homework:
        raise InvalidApiExc('Словарь homeworks пуст')
    if 'homework_name' not in homework:
        raise KeyError('Ключ homework_name отсутствует')
    if 'status' not in homework:
        raise KeyError('Ключ status отсутствует')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(
            f'Статус работы: "{homework_status}"'.format(
                homework_status
            )
        )
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    if not check_tokens():
        logger.critical('Недоступны переменные окружения!')
        raise GlobalsError('Ошибка глобальной переменной. Смотрите логи.')
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            send_message(bot, message)
            logging.info(homework)
            current_timestamp = response.get('current_date')
        except IndexError:
            message = 'Статус работы не изменился'
            send_message(bot, message)
            logging.info(message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)
        logging.info(f'Сообщение {message} отправлено'.format(message))


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s, %(message)s, %(lineno)d, %(name)s',
        filemode='w',
        filename=f'{Path(__file__).stem}.log',
        level=logging.CRITICAL,
    )
    main()
