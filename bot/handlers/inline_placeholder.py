import logging
import re

from aiogram import F, Router
from aiogram.types import Message

from bot.config import Settings
from bot.handlers.access import is_user_allowed
from bot.handlers.inline import deferred_result_id
from bot.services.inline_deferred import attach_inline_target_and_deliver
from bot.services.inline_pending import InlinePendingStore

logger = logging.getLogger(__name__)

router = Router(name="inline_placeholder")

_PLACEHOLDER_MARKERS = ("Генерирую ответ", "⏳")
_QUESTION_PLAIN = re.compile(r"^\*\*Вопрос:\*\*\s*(.+?)(?:\n\n|\Z)", re.DOTALL)
_QUESTION_HTML = re.compile(r"<b>Вопрос:</b>\s*(.+?)(?:\n\n|\Z)", re.DOTALL | re.IGNORECASE)


def _extract_query(text: str) -> str | None:
    text = text.strip()
    for pattern in (_QUESTION_HTML, _QUESTION_PLAIN):
        m = pattern.search(text)
        if m:
            return m.group(1).strip()
    return None


@router.message(F.text.contains("Генерирую ответ"))
async def bind_placeholder_message(
    message: Message,
    settings: Settings,
    inline_pending_store: InlinePendingStore,
) -> None:
    """When inline feedback is off, user still sends the placeholder as a normal message."""
    if message.from_user is None or message.text is None:
        return
    if not is_user_allowed(settings, message.from_user.id):
        return

    text = message.text
    if not any(marker in text for marker in _PLACEHOLDER_MARKERS):
        return

    query = _extract_query(text)
    if not query:
        return

    result_id = deferred_result_id(message.from_user.id, query)
    job = await inline_pending_store.get(result_id)
    if job is None:
        return

    logger.info(
        "Inline placeholder message user=%s chat=%s msg=%s",
        message.from_user.id,
        message.chat.id,
        message.message_id,
    )
    await attach_inline_target_and_deliver(
        message.bot,
        result_id,
        job,
        chat_id=message.chat.id,
        message_id=message.message_id,
    )