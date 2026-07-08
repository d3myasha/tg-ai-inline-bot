import hashlib
import logging
import time
import uuid

from aiogram import Bot, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    ChosenInlineResult,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from openai import AsyncOpenAI

from bot.config import Settings
from bot.handlers.access import is_user_allowed
from bot.handlers.model_inline import (
    apply_chosen_inline_model,
    build_model_picker_results,
    is_model_picker_query,
)
from bot.services.inline_deferred import schedule_deferred_inline
from bot.services.inline_pending import InlineAiJob, InlinePendingStore
from bot.services.model_catalog import ModelCatalogService
from bot.services.telegram_format import plain_preview
from bot.services.telegram_send import llm_text_for_inline
from bot.services.user_models import UserModelStore

logger = logging.getLogger(__name__)

router = Router(name="inline")

DEFERRED_PREFIX = "def:"


def _deferred_id(user_id: int, query: str) -> str:
    digest = hashlib.sha256(f"{user_id}:{query}".encode()).hexdigest()[:24]
    return f"{DEFERRED_PREFIX}{digest}"


@router.chosen_inline_result()
async def on_chosen_inline_result(
    chosen: ChosenInlineResult,
    bot: Bot,
    settings: Settings,
    openai_client: AsyncOpenAI,
    model_catalog_service: ModelCatalogService,
    user_model_store: UserModelStore,
    inline_pending_store: InlinePendingStore,
) -> None:
    user = chosen.from_user
    if user is None or not is_user_allowed(settings, user.id):
        return

    result_id = chosen.result_id

    if result_id.startswith(DEFERRED_PREFIX):
        if not chosen.inline_message_id:
            logger.warning("No inline_message_id for deferred %s", result_id)
            return
        job = await inline_pending_store.pop(result_id)
        if job is None:
            return
        schedule_deferred_inline(
            bot, chosen.inline_message_id, job, settings, openai_client,
        )
        return

    applied = await apply_chosen_inline_model(
        result_id, settings, model_catalog_service, user_model_store, user.id,
    )
    if applied is not None:
        logger.info("User %s selected model via inline: %s", user.id, applied)


@router.inline_query()
async def handle_inline_query(
    inline_query: InlineQuery,
    settings: Settings,
    openai_client: AsyncOpenAI,
    user_model_store: UserModelStore,
    model_catalog_service: ModelCatalogService,
    inline_pending_store: InlinePendingStore,
) -> None:
    query = (inline_query.query or "").strip()
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

    if not query:
        current = await user_model_store.get_model(user.id)
        await inline_query.answer(
            results=[
                InlineQueryResultArticle(
                    id="hint:model",
                    title=f"Модель: {current}"[:64],
                    description="Введите @бот вопрос. Смена: @бот model",
                    input_message_content=InputTextMessageContent(
                        message_text=(
                            f"Текущая модель: {current}. "
                            "Выбор сохраняется для всех чатов. "
                            "Сменить: @бот model"
                        ),
                    ),
                ),
            ],
            cache_time=5,
            is_personal=True,
        )
        return

    if is_model_picker_query(query):
        catalog = await model_catalog_service.fetch_catalog(
            openai_client, settings
        )
        results = await build_model_picker_results(
            catalog, model_catalog_service, settings, user_model_store, user.id,
        )
        await inline_query.answer(
            results=results,
            cache_time=10,
            is_personal=True,
            switch_pm_text="Чат с ботом",
            switch_pm_parameter="start",
        )
        return

    model = await user_model_store.get_model(user.id)

    result_id = _deferred_id(user.id, query)
    await inline_pending_store.put(
        result_id,
        InlineAiJob(query=query, model=model, user_id=user.id, created_at=time.monotonic()),
    )

    placeholder, p_mode = llm_text_for_inline(
        "⏳ Генерирую ответ…", user_query=query,
    )
    title = query if len(query) <= 64 else query[:61] + "..."

    results = [
        InlineQueryResultArticle(
            id=result_id,
            title=title,
            description="Нажми — ответ появится в чате",
            input_message_content=InputTextMessageContent(
                message_text=placeholder, parse_mode=p_mode,
            ),
        )
    ]

    try:
        await inline_query.answer(results=results, cache_time=0, is_personal=True)
    except TelegramBadRequest as exc:
        await inline_pending_store.pop(result_id)
        if "query is too old" in str(exc).lower():
            logger.warning("Inline query expired (deferred): %r", query[:80])
            return
        raise