import logging
import re

from aiogram import F, Router
from aiogram.types import Message

from bot.config import Settings
from bot.handlers.access import is_user_allowed
from bot.services.inline_deferred import attach_inline_target_and_deliver
from bot.services.inline_ids import deferred_result_id
from bot.services.inline_pending import InlinePendingStore

logger = logging.getLogger(__name__)

router = Router(name="inline_placeholder")

_PLACEHOLDER_MARKERS = ("Генерирую ответ", "⏳")
_QUESTION_PLAIN = re.compile(
    r"(?:\*\*Вопрос:\*\*|<b>Вопрос:</b>|Вопрос:)\s*(.+?)(?:\n\n|\Z)",
    re.DOTALL | re.IGNORECASE,
)


def _extract_query(text: str) -> str | None:
    text = text.strip()
    m = _QUESTION_PLAIN.search(text)
    if m:
        query = m.group(1).strip()
        if query:
            return query

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) >= 2 and "Генерирую" in lines[-1]:
        first = lines[0]
        if first.lower().startswith("вопрос:"):
            return first.split(":", 1)[1].strip() or None
        return first
    return None


@router.message(F.text.contains("Генерирую ответ"))
async def bind_placeholder_message(
    message: Message,
    settings: Settings,
    inline_pending_store: InlinePendingStore,
) -> None:
    if message.from_user is None or message.text is None:
        return
    if not is_user_allowed(settings, message.from_user.id):
        return

    text = message.text
    if not any(marker in text for marker in _PLACEHOLDER_MARKERS):
        return

    query = _extract_query(text)
    if not query:
        logger.info(
            "placeholder message but query not parsed user=%s text=%r",
            message.from_user.id,
            text[:200],
        )
        return

    result_id = deferred_result_id(message.from_user.id, query)
    job = await inline_pending_store.get(result_id)
    if job is None:
        logger.info(
            "placeholder message no job user=%s result=%s query=%r",
            message.from_user.id,
            result_id,
            query[:80],
        )
        return

    logger.info(
        "Inline placeholder message user=%s chat=%s msg=%s result=%s",
        message.from_user.id,
        message.chat.id,
        message.message_id,
        result_id,
    )
    await attach_inline_target_and_deliver(
        message.bot,
        result_id,
        job,
        inline_pending_store,
        chat_id=message.chat.id,
        message_id=message.message_id,
    )