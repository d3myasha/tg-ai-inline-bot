import logging
import uuid

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from openai import AsyncOpenAI

from bot.config import Settings
from bot.handlers.access import is_user_allowed
from bot.services.llm import complete_chat, truncate_for_telegram

logger = logging.getLogger(__name__)

router = Router(name="inline")


@router.inline_query()
async def handle_inline_query(
    inline_query: InlineQuery,
    settings: Settings,
    openai_client: AsyncOpenAI,
) -> None:
    query = (inline_query.query or "").strip()
    if not query:
        await inline_query.answer(
            results=[],
            switch_pm_text="Открыть бота",
            switch_pm_parameter="start",
            cache_time=1,
            is_personal=True,
        )
        return

    user = inline_query.from_user
    if user is None or not is_user_allowed(settings, user.id):
        await inline_query.answer(
            results=[
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title="Доступ запрещён",
                    description="Ваш user id не в ALLOWED_TELEGRAM_USER_IDS",
                    input_message_content=InputTextMessageContent(
                        message_text="У вас нет доступа к этому боту.",
                    ),
                )
            ],
            cache_time=1,
            is_personal=True,
        )
        return

    try:
        answer_text = await complete_chat(openai_client, settings, query)
    except Exception:
        logger.exception("LLM request failed for inline query")
        answer_text = (
            "Не удалось получить ответ от API. Проверь ключ, base URL и модель."
        )

    answer_text = truncate_for_telegram(answer_text)
    title = query if len(query) <= 64 else query[:61] + "..."
    description = (
        answer_text[:256] if len(answer_text) <= 256 else answer_text[:253] + "..."
    )

    try:
        await inline_query.answer(
            results=[
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title=title,
                    description=description,
                    input_message_content=InputTextMessageContent(
                        message_text=answer_text,
                    ),
                )
            ],
            cache_time=0,
            is_personal=True,
        )
    except TelegramBadRequest as exc:
        if "query is too old" in str(exc).lower():
            logger.warning(
                "Inline query expired before answer (LLM too slow): query=%r",
                query[:80],
            )
            return
        raise