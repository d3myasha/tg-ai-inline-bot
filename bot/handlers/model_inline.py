"""Inline model picker: @bot model / пустой запрос → список моделей."""

from aiogram.types import InlineQueryResultArticle, InputTextMessageContent

from bot.config import Settings
from bot.services.user_models import UserModelStore

INLINE_RESULT_SET_PREFIX = "mset:"
INLINE_RESULT_CLEAR_DEFAULT = "mclr:default"


def is_model_picker_query(query: str) -> bool:
    q = query.strip().lower()
    if not q:
        return True
    return q in ("model", "модель", "models", "модели")


async def build_model_picker_results(
    settings: Settings,
    user_model_store: UserModelStore,
    user_id: int,
) -> list[InlineQueryResultArticle]:
    current = await user_model_store.get_model(user_id)
    catalog = settings.model_catalog()
    results: list[InlineQueryResultArticle] = []

    for index, name in enumerate(catalog):
        mark = " ✓" if name == current else ""
        results.append(
            InlineQueryResultArticle(
                id=f"{INLINE_RESULT_SET_PREFIX}{index}",
                title=f"{name}{mark}",
                description="Выбрать эту модель для чата и inline",
                input_message_content=InputTextMessageContent(
                    message_text=f"Модель: {name}",
                ),
            )
        )

    default_mark = " ✓" if current == settings.openai_model else ""
    results.append(
        InlineQueryResultArticle(
            id=INLINE_RESULT_CLEAR_DEFAULT,
            title=f"По умолчанию ({settings.openai_model}){default_mark}",
            description="Сбросить выбор, использовать OPENAI_MODEL из .env",
            input_message_content=InputTextMessageContent(
                message_text=f"Модель по умолчанию: {settings.openai_model}",
            ),
        )
    )
    return results


async def apply_chosen_inline_model(
    result_id: str,
    settings: Settings,
    user_model_store: UserModelStore,
    user_id: int,
) -> str | None:
    """Returns chosen model name if applied."""
    if result_id == INLINE_RESULT_CLEAR_DEFAULT:
        await user_model_store.clear_model(user_id)
        return settings.openai_model

    if not result_id.startswith(INLINE_RESULT_SET_PREFIX):
        return None

    try:
        index = int(result_id.removeprefix(INLINE_RESULT_SET_PREFIX))
        chosen = settings.model_catalog()[index]
    except (ValueError, IndexError):
        return None

    await user_model_store.set_model(user_id, chosen)
    return chosen