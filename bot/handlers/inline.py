import hashlib
import logging
import time
import uuid

from aiogram import Bot, Router
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
from bot.services.inline_deferred import (
    attach_inline_target_and_deliver,
    schedule_inline_llm,
)
from bot.services.inline_pending import InlineAiJob, InlinePendingStore
from bot.services.model_catalog import ModelCatalogService
from bot.services.telegram_send import llm_text_for_inline
from bot.services.user_models import UserModelStore

logger = logging.getLogger(__name__)

router = Router(name="inline")

DEFERRED_PREFIX = "def:"


def deferred_result_id(user_id: int, query: str) -> str:
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
        job = await inline_pending_store.get(result_id)
        if job is None:
            logger.warning("No pending job for %s", result_id)
            return
        if chosen.inline_message_id:
            await attach_inline_target_and_deliver(
                bot,
                result_id,
                job,
                inline_message_id=chosen.inline_message_id,
            )
        else:
            logger.info(
                "chosen_inline_result without inline_message_id for %s "
                "(waiting for placeholder message in chat)",
                result_id,
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
    bot: Bot,
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

    result_id = deferred_result_id(user.id, query)

    if await inline_pending_store.get(result_id) is not None:
        logger.debug("Duplicate inline_query for %s, LLM already running", result_id)
        existing_job = await inline_pending_store.get(result_id)
        if existing_job is not None:
            existing_job.created_at = time.monotonic()
        placeholder, p_mode = llm_text_for_inline(
            "⏳ Генерирую ответ…", user_query=query,
        )
        title = query if len(query) <= 64 else query[:61] + "..."
        try:
            await inline_query.answer(
                results=[InlineQueryResultArticle(
                    id=result_id,
                    title=title,
                    description="Нажми — ответ появится в чате",
                    input_message_content=InputTextMessageContent(
                        message_text=placeholder, parse_mode=p_mode,
                    ),
                )],
                cache_time=0,
                is_personal=True,
            )
        except TelegramBadRequest as exc:
            if "query is too old" in str(exc).lower():
                return
            raise
        return

    job = InlineAiJob(
        query=query,
        model=model,
        user_id=user.id,
        created_at=time.monotonic(),
    )
    await inline_pending_store.put(result_id, job)

    schedule_inline_llm(
        bot,
        result_id,
        job,
        settings,
        openai_client,
        inline_pending_store,
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