from bot.config import Settings


def is_user_allowed(settings: Settings, user_id: int) -> bool:
    allowed = settings.allowed_user_id_set()
    if allowed is None:
        return True
    return user_id in allowed