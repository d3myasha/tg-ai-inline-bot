import logging
import re

from aiogram import F, Router
from aiogram.types import Message

from bot.config import Settings
from bot.handlers.access import is_user_allowed
from bot.services.user_models import UserModelStore

logger = logging.getLogger(__name__)

router = Router(name="inline_model_capture")

_MODEL_MSG = re.compile(r"^Модель:\s*(.+)$", re.IGNORECASE)
_DEFAULT_MSG = re.compile(r"^Модель по умолчанию:\s*(.+)$", re.IGNORECASE)


@router.message(F.text.startswith("Модель"))
async def save_model_from_inline_message(
    message: Message,
    settings: Settings,
    user_model_store: UserModelStore,
) -> None:
    """Persist model when user sends inline picker result (works without feedback)."""
    if message.from_user is None:
        return
    if not is_user_allowed(settings, message.from_user.id):
        return

    text = (message.text or "").strip()
    if not text:
        return

    if m := _DEFAULT_MSG.match(text):
        await user_model_store.clear_model(message.from_user.id)
        logger.info(
            "User %s reset model via inline message to default %s",
            message.from_user.id,
            settings.openai_model,
        )
        return

    if m := _MODEL_MSG.match(text):
        name = m.group(1).strip()
        if name:
            await user_model_store.set_model(message.from_user.id, name)
            logger.info(
                "User %s set model via inline message: %s",
                message.from_user.id,
                name,
            )