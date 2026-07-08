import logging
import uuid

from aiogram import Router
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
from bot.services.llm import complete_chat, truncate_for_telegram
from bot.services.model_catalog import ModelCatalogService
from bot.services.user_models import UserModelStore

logger = logging.getLogger(__name__)

router = Router(name="inline")


@router.chosen_inline_result()
async def on_chosen_inline_result(
    chosen: ChosenInlineResult,
    settings: Settings,
    model_catalog_service: ModelCatalogService,
    user_model_store: UserModelStore,
) -> None:
    user = chosen.from_user
    if user is None or not is_user_allowed(settings, user.id):
        return

    applied = await apply_chosen_inline_model(
        chosen.result_id,
        settings,
        model_catalog_service,
        user_model_store,
        user.id,
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

    if is_model_picker_query(query):
        catalog = await model_catalog_service.fetch_catalog(
            openai_client, settings
        )
        results = await build_model_picker_results(
            catalog,
            model_catalog_service,
            settings,
            user_model_store,
            user.id,
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

    try:
        answer_text = await complete_chat(
            openai_client, settings, query, model=model
        )
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