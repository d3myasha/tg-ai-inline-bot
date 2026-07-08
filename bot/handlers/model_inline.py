"""Inline model picker: @bot model / пустой запрос → список моделей."""

from aiogram.types import InlineQueryResultArticle, InputTextMessageContent

from bot.config import Settings
from bot.services.model_catalog import ModelCatalogService
from bot.services.user_models import UserModelStore

INLINE_RESULT_CLEAR_DEFAULT = "mclr:default"


def is_model_picker_query(query: str) -> bool:
    q = query.strip().lower()
    if not q:
        return True
    return q in ("model", "модель", "models", "модели")


async def build_model_picker_results(
    catalog: list[str],
    catalog_service: ModelCatalogService,
    settings: Settings,
    user_model_store: UserModelStore,
    user_id: int,
) -> list[InlineQueryResultArticle]:
    current = await user_model_store.get_model(user_id)
    results: list[InlineQueryResultArticle] = []

    for name in catalog_service.models_for_inline(catalog):
        mark = " ✓" if name == current else ""
        results.append(
            InlineQueryResultArticle(
                id=catalog_service.inline_result_id(name),
                title=f"{name}{mark}"[:64],
                description="Выбрать для чата и inline",
                input_message_content=InputTextMessageContent(
                    message_text=f"Модель: {name}",
                ),
            )
        )

    default_mark = " ✓" if current == settings.openai_model else ""
    results.append(
        InlineQueryResultArticle(
            id=INLINE_RESULT_CLEAR_DEFAULT,
            title=f"По умолчанию ({settings.openai_model}){default_mark}"[:64],
            description="OPENAI_MODEL из .env",
            input_message_content=InputTextMessageContent(
                message_text=f"Модель по умолчанию: {settings.openai_model}",
            ),
        )
    )
    return results


async def apply_chosen_inline_model(
    result_id: str,
    settings: Settings,
    catalog_service: ModelCatalogService,
    user_model_store: UserModelStore,
    user_id: int,
) -> str | None:
    if result_id == INLINE_RESULT_CLEAR_DEFAULT:
        await user_model_store.clear_model(user_id)
        return settings.openai_model

    chosen = catalog_service.model_from_inline_result_id(result_id)
    if not chosen:
        return None

    await user_model_store.set_model(user_id, chosen)
    return chosen