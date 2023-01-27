class APIErrors(Exception):
    """Ошибка при работе API."""
    pass


class CustomError(Exception):
    """Ошибка при работе с телеграмом."""
    pass
