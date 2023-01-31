class EndpointError(Exception):
    """Ошибка: эндпойнт не корректен."""

    pass


class ResponseFormatError(Exception):
    """Ошибка: формат response не json."""

    pass
