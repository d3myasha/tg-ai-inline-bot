import asyncio
import logging

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest

from bot.config import Settings
from bot.services.answer_format import build_llm_reply_markdown
from bot.services.inline_pending import InlineAiJob
from bot.services.llm import complete_chat
from bot.services.telegram_format import format_llm_markdown_for_telegram, format_llm_plain_fallback
from bot.services.telegram_send import llm_text_for_inline
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


async def run_deferred_inline_answer(
    bot: Bot,
    inline_message_id: str,
    job: InlineAiJob,
    settings: Settings,
    openai_client: AsyncOpenAI,
) -> None:
    try:
        answer = await complete_chat(
            openai_client,
            settings,
            job.query,
            model=job.model,
        )
    except Exception:
        logger.exception("Deferred inline LLM failed")
        answer = "Не удалось получить ответ от API."

    text, parse_mode = llm_text_for_inline(answer, user_query=job.query)
    try:
        await bot.edit_message_text(
            text=text,
            inline_message_id=inline_message_id,
            parse_mode=parse_mode or ParseMode.HTML,
        )
    except TelegramBadRequest as exc:
        logger.warning("editMessageText failed for inline %s: %s", inline_message_id, exc)
        # Fallback without parse mode
        combined = build_llm_reply_markdown(job.query, answer)
        try:
            await bot.edit_message_text(
                text=format_llm_plain_fallback(combined),
                inline_message_id=inline_message_id,
                parse_mode=ParseMode.NONE,
            )
        except TelegramBadRequest:
            logger.warning("Plain edit also failed for inline %s", inline_message_id)


def schedule_deferred_inline(
    bot: Bot,
    inline_message_id: str,
    job: InlineAiJob,
    settings: Settings,
    openai_client: AsyncOpenAI,
) -> None:
    asyncio.create_task(
        run_deferred_inline_answer(
            bot,
            inline_message_id,
            job,
            settings,
            openai_client,
        )
    )