class EndpointError(Exception):
    """Ошибка: эндпойнт не корректен."""

    pass


class ResponseFormatError(Exception):
    """Ошибка: формат response не json."""

    pass


class EmptyListException(Exception):
    """Исключение - статус работы не изменился."""

    pass


class InvalidResponseExc(Exception):
    """Исключение - status_code API != 200."""

    pass
