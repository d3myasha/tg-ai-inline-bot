import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from openai import AsyncOpenAI

from bot.config import Settings
from bot.handlers.access import is_user_allowed
from bot.services.model_catalog import ModelCatalogService
from bot.services.user_models import UserModelStore

logger = logging.getLogger(__name__)

router = Router(name="model_select")

CALLBACK_PREFIX = "model:"
CALLBACK_DEFAULT = "model:default"
CALLBACK_REFRESH = "model:refresh"
PAGE_SIZE = 12


def _keyboard(
    catalog: list[str],
    current: str,
    settings: Settings,
    page: int = 0,
) -> InlineKeyboardMarkup:
    start = page * PAGE_SIZE
    chunk = catalog[start : start + PAGE_SIZE]
    rows: list[list[InlineKeyboardButton]] = []

    for index, name in enumerate(chunk, start=start):
        mark = " ✓" if name == current else ""
        label = f"{name}{mark}"
        if len(label) > 60:
            label = label[:57] + "..."
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"{CALLBACK_PREFIX}{index}",
                )
            ]
        )

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(text="◀️", callback_data=f"modelpage:{page - 1}")
        )
    if start + PAGE_SIZE < len(catalog):
        nav.append(
            InlineKeyboardButton(text="▶️", callback_data=f"modelpage:{page + 1}")
        )
    if nav:
        rows.append(nav)

    rows.append(
        [
            InlineKeyboardButton(text="🔄 Обновить список", callback_data=CALLBACK_REFRESH),
            InlineKeyboardButton(
                text=f"Дефолт ({settings.openai_model})",
                callback_data=CALLBACK_DEFAULT,
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _status_text(
    current: str,
    settings: Settings,
    catalog: list[str],
    page: int,
) -> str:
    total_pages = max(1, (len(catalog) + PAGE_SIZE - 1) // PAGE_SIZE)
    return (
        f"Текущая модель: <b>{current}</b>\n"
        f"Список с провайдера <code>/v1/models</code> ({len(catalog)} шт.), "
        f"стр. {page + 1}/{total_pages}\n"
        f"Без выбора: <b>{settings.openai_model}</b> из .env"
    )


@router.message(Command("model"))
async def cmd_model(
    message: Message,
    settings: Settings,
    openai_client: AsyncOpenAI,
    user_model_store: UserModelStore,
    model_catalog_service: ModelCatalogService,
) -> None:
    if message.from_user is None:
        return
    if not is_user_allowed(settings, message.from_user.id):
        await message.answer("У вас нет доступа к этому боту.")
        return

    await message.bot.send_chat_action(message.chat.id, "typing")
    catalog = await model_catalog_service.fetch_catalog(openai_client, settings)
    current = await user_model_store.get_model(message.from_user.id)
    await message.answer(
        _status_text(current, settings, catalog, 0),
        reply_markup=_keyboard(catalog, current, settings, 0),
    )


@router.callback_query(F.data.startswith("modelpage:"))
async def on_model_page(
    callback: CallbackQuery,
    settings: Settings,
    openai_client: AsyncOpenAI,
    user_model_store: UserModelStore,
    model_catalog_service: ModelCatalogService,
) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return

    try:
        page = int((callback.data or "").removeprefix("modelpage:"))
    except ValueError:
        await callback.answer()
        return

    catalog = await model_catalog_service.fetch_catalog(openai_client, settings)
    current = await user_model_store.get_model(callback.from_user.id)
    await callback.message.edit_text(
        _status_text(current, settings, catalog, page),
        reply_markup=_keyboard(catalog, current, settings, page),
    )
    await callback.answer()


@router.callback_query(F.data == CALLBACK_REFRESH)
async def on_model_refresh(
    callback: CallbackQuery,
    settings: Settings,
    openai_client: AsyncOpenAI,
    user_model_store: UserModelStore,
    model_catalog_service: ModelCatalogService,
) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return

    catalog = await model_catalog_service.fetch_catalog(
        openai_client, settings, force_refresh=True
    )
    current = await user_model_store.get_model(callback.from_user.id)
    await callback.message.edit_text(
        _status_text(current, settings, catalog, 0),
        reply_markup=_keyboard(catalog, current, settings, 0),
    )
    await callback.answer("Список обновлён")


@router.callback_query(F.data.regexp(r"^model:\d+$"))
async def on_model_pick(
    callback: CallbackQuery,
    settings: Settings,
    openai_client: AsyncOpenAI,
    user_model_store: UserModelStore,
    model_catalog_service: ModelCatalogService,
) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return
    if not is_user_allowed(settings, callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    data = callback.data or ""
    catalog = await model_catalog_service.fetch_catalog(openai_client, settings)

    if data == CALLBACK_DEFAULT:
        await user_model_store.clear_model(callback.from_user.id)
        chosen = settings.openai_model
        page = 0
    else:
        try:
            index = int(data.removeprefix(CALLBACK_PREFIX))
            chosen = catalog[index]
            page = index // PAGE_SIZE
        except (ValueError, IndexError):
            await callback.answer("Неверная кнопка", show_alert=True)
            return
        await user_model_store.set_model(callback.from_user.id, chosen)

    await callback.message.edit_text(
        _status_text(chosen, settings, catalog, page),
        reply_markup=_keyboard(catalog, chosen, settings, page),
    )
    await callback.answer(f"Выбрано: {chosen}")