from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

DEFERRED_CALLBACK_PREFIX = "idef:"


def deferred_placeholder_keyboard(result_id: str) -> InlineKeyboardMarkup:
    token = result_id.removeprefix("def:")
    data = f"{DEFERRED_CALLBACK_PREFIX}{token}"[:64]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⏳ Ответ обновится здесь",
                    callback_data=data,
                )
            ]
        ]
    )