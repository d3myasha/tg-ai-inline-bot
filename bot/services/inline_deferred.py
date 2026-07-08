import asyncio
import logging

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from openai import AsyncOpenAI

from bot.config import Settings
from bot.services.answer_format import build_llm_reply_markdown
from bot.services.inline_pending import InlineAiJob, InlinePendingStore
from bot.services.llm import complete_chat
from bot.services.telegram_format import format_llm_plain_fallback
from bot.services.telegram_send import llm_text_for_inline

logger = logging.getLogger(__name__)


async def _edit_target(
    bot: Bot,
    job: InlineAiJob,
    text: str,
    parse_mode: ParseMode | None,
) -> bool:
    kwargs: dict = {"text": text}
    if parse_mode is not None:
        kwargs["parse_mode"] = parse_mode

    if job.inline_message_id:
        kwargs["inline_message_id"] = job.inline_message_id
    elif job.chat_id is not None and job.message_id is not None:
        kwargs["chat_id"] = job.chat_id
        kwargs["message_id"] = job.message_id
    else:
        logger.warning(
            "inline deliver skipped: no target user=%s query=%r",
            job.user_id,
            job.query[:80],
        )
        return False

    try:
        await bot.edit_message_text(**kwargs)
        logger.info(
            "inline deliver ok user=%s inline_id=%s chat=%s msg=%s",
            job.user_id,
            job.inline_message_id,
            job.chat_id,
            job.message_id,
        )
        return True
    except TelegramBadRequest as exc:
        logger.warning("edit_message_text failed: %s", exc)
        if parse_mode is not None:
            try:
                kwargs["text"] = format_llm_plain_fallback(
                    build_llm_reply_markdown(job.query, job.answer or job.error or "")
                )
                kwargs["parse_mode"] = ParseMode.NONE
                await bot.edit_message_text(**kwargs)
                logger.info("inline deliver ok (plain fallback) user=%s", job.user_id)
                return True
            except TelegramBadRequest as exc2:
                logger.warning("plain edit also failed: %s", exc2)
        return False


async def try_deliver_inline_job(bot: Bot, job: InlineAiJob) -> bool:
    async with job._deliver_lock:
        if job.answer is None and job.error is None:
            return False
        body = job.answer if job.answer is not None else job.error or ""
        text, parse_mode = llm_text_for_inline(body, user_query=job.query)
        return await _edit_target(bot, job, text, parse_mode)


async def run_inline_llm(
    bot: Bot,
    result_id: str,
    job: InlineAiJob,
    settings: Settings,
    openai_client: AsyncOpenAI,
    inline_pending_store: InlinePendingStore,
) -> None:
    logger.info(
        "LLM inline start user=%s model=%s query=%r",
        job.user_id,
        job.model,
        job.query[:120],
    )
    try:
        job.answer = await complete_chat(
            openai_client,
            settings,
            job.query,
            model=job.model,
        )
        logger.info(
            "LLM inline done user=%s query=%r len=%s",
            job.user_id,
            job.query[:80],
            len(job.answer or ""),
        )
    except asyncio.CancelledError:
        logger.info("LLM inline cancelled user=%s query=%r", job.user_id, job.query[:80])
        raise
    except Exception:
        logger.exception("Deferred inline LLM failed")
        job.error = "Не удалось получить ответ от API."

    stored = await inline_pending_store.get(result_id)
    if stored is not job:
        return

    if await try_deliver_inline_job(bot, job):
        await inline_pending_store.pop(result_id)


def schedule_inline_llm(
    bot: Bot,
    result_id: str,
    job: InlineAiJob,
    settings: Settings,
    openai_client: AsyncOpenAI,
    inline_pending_store: InlinePendingStore,
) -> None:
    if job.llm_task and not job.llm_task.done():
        job.llm_task.cancel()
    job.llm_task = asyncio.create_task(
        run_inline_llm(
            bot,
            result_id,
            job,
            settings,
            openai_client,
            inline_pending_store,
        )
    )


async def attach_inline_target_and_deliver(
    bot: Bot,
    result_id: str,
    job: InlineAiJob,
    inline_pending_store: InlinePendingStore,
    *,
    inline_message_id: str | None = None,
    chat_id: int | None = None,
    message_id: int | None = None,
) -> None:
    if inline_message_id:
        job.inline_message_id = inline_message_id
    if chat_id is not None:
        job.chat_id = chat_id
    if message_id is not None:
        job.message_id = message_id
    if await try_deliver_inline_job(bot, job):
        await inline_pending_store.pop(result_id)