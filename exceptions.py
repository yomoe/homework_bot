class APIErrors(Exception):
    """Ошибка при работе API."""
    pass


class TelegaCustomError(Exception):
    """Ошибка при работе с телеграмом."""
    pass
