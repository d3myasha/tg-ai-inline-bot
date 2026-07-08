from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.config import Settings
from bot.handlers.access import is_user_allowed
from bot.services.user_models import UserModelStore

router = Router(name="model_select")

CALLBACK_PREFIX = "model:"
CALLBACK_DEFAULT = "model:default"


def _keyboard(settings: Settings, current: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for index, name in enumerate(settings.model_catalog()):
        mark = " ✓" if name == current else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{name}{mark}",
                    callback_data=f"{CALLBACK_PREFIX}{index}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=f"По умолчанию ({settings.openai_model})",
                callback_data=CALLBACK_DEFAULT,
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("model"))
async def cmd_model(
    message: Message,
    settings: Settings,
    user_model_store: UserModelStore,
) -> None:
    if message.from_user is None:
        return
    if not is_user_allowed(settings, message.from_user.id):
        await message.answer("У вас нет доступа к этому боту.")
        return

    current = await user_model_store.get_model(message.from_user.id)
    await message.answer(
        f"Текущая модель: <b>{current}</b>\n"
        f"Если не выбирать — используется <b>{settings.openai_model}</b> из .env.\n"
        "Нажми кнопку:",
        reply_markup=_keyboard(settings, current),
    )


@router.callback_query(F.data.startswith(CALLBACK_PREFIX))
async def on_model_pick(
    callback: CallbackQuery,
    settings: Settings,
    user_model_store: UserModelStore,
) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return
    if not is_user_allowed(settings, callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    catalog = settings.model_catalog()
    data = callback.data or ""

    if data == CALLBACK_DEFAULT:
        await user_model_store.clear_model(callback.from_user.id)
        chosen = settings.openai_model
    else:
        try:
            index = int(data.removeprefix(CALLBACK_PREFIX))
            chosen = catalog[index]
        except (ValueError, IndexError):
            await callback.answer("Неверная кнопка", show_alert=True)
            return
        await user_model_store.set_model(callback.from_user.id, chosen)

    await callback.message.edit_text(
        f"Модель: <b>{chosen}</b>\n"
        f"Дефолт из .env: <b>{settings.openai_model}</b>",
        reply_markup=_keyboard(settings, chosen),
    )
    await callback.answer(f"Выбрано: {chosen}")