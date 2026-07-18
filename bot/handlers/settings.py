import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from openai import AsyncOpenAI

from bot.config import Settings
from bot.handlers.access import is_user_allowed
from bot.services.dembel import DembelService
from bot.services.runtime_settings import RuntimeSettingsStore

logger = logging.getLogger(__name__)

router = Router(name="settings")

# ── state: who is editing what ────────────────────────────────────
_awaiting: dict[int, str] = {}

# ── helpers ────────────────────────────────────────────────────────

_SETTING_LABELS: dict[str, str] = {
    "openai_api_key": "🔑 API Key",
    "openai_base_url": "🌐 Base URL",
    "openai_model": "🧠 Модель",
    "assistant_system_prompt": "📝 System Prompt",
    "available_models": "📋 Доступные модели",
    "models_cache_ttl_seconds": "⏳ Кэш моделей (сек)",
    "dembel_enabled": "📅 Дембель",
    "dembel_user_id": "👤 Дембель: user_id",
    "dembel_chat_id": "💬 Дембель: chat_id",
    "dembel_days": "📆 Дембель: дней",
    "dembel_check_interval_seconds": "⏱ Дембель: интервал (с)",
    "allowed_telegram_user_ids": "👥 Разрешённые ID",
}

_CATEGORIES: dict[str, tuple[str, ...]] = {
    "ai": ("openai_api_key", "openai_base_url", "openai_model", "assistant_system_prompt", "available_models"),
    "access": ("allowed_telegram_user_ids",),
    "dembel": ("dembel_enabled", "dembel_user_id", "dembel_chat_id", "dembel_days", "dembel_check_interval_seconds"),
}

_CATEGORY_LABELS = {
    "ai": "🧠 Модель и API",
    "access": "👥 Доступ",
    "dembel": "📅 Дембель",
}


def _mask(value: str, max_show: int = 8) -> str:
    if not value:
        return "—"
    if len(value) <= max_show + 4:
        return value[:max_show] + "…"
    return value[:max_show // 2] + "…" + value[-(max_show // 2):]


def _fmt_val(store: RuntimeSettingsStore, key: str) -> str:
    val = store.get(key)
    if key == "openai_api_key":
        return _mask(str(val), 8)
    if isinstance(val, bool):
        return "✅ Вкл" if val else "❌ Выкл"
    if val is None or val == "" or val == 0:
        return "—"
    return str(val)


def _main_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for cat_key, (cat_label) in _CATEGORY_LABELS.items():
        rows.append([
            InlineKeyboardButton(text=cat_label, callback_data=f"setcat:{cat_key}"),
        ])
    rows.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="set:close")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _category_keyboard(cat_key: str) -> InlineKeyboardMarkup:
    rows = []
    keys = _CATEGORIES[cat_key]
    for k in keys:
        label = _SETTING_LABELS.get(k, k)
        rows.append([
            InlineKeyboardButton(text=label, callback_data=f"setval:{k}"),
        ])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="set:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── commands ──────────────────────────────────────────────────────

@router.message(Command("settings"))
async def cmd_settings(
    message: Message,
    settings: Settings,
    runtime_settings: RuntimeSettingsStore,
) -> None:
    if message.from_user is None:
        return
    if not is_user_allowed(settings, message.from_user.id):
        await message.answer("У вас нет доступа.")
        return
    _awaiting.pop(message.from_user.id, None)
    await message.answer(
        "⚙️ <b>Настройки</b>\n\n"
        "Выбери категорию:",
        reply_markup=_main_keyboard(),
    )


# ── callbacks ─────────────────────────────────────────────────────

@router.callback_query(F.data == "set:close")
async def on_close(callback: CallbackQuery) -> None:
    if callback.message:
        await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data == "set:main")
async def on_main_menu(callback: CallbackQuery) -> None:
    if callback.from_user:
        _awaiting.pop(callback.from_user.id, None)
    if callback.message:
        await callback.message.edit_text(
            "⚙️ <b>Настройки</b>\n\nВыбери категорию:",
            reply_markup=_main_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("setcat:"))
async def on_category(
    callback: CallbackQuery,
    runtime_settings: RuntimeSettingsStore,
) -> None:
    if callback.from_user:
        _awaiting.pop(callback.from_user.id, None)
    cat = (callback.data or "").removeprefix("setcat:")
    if cat not in _CATEGORIES:
        await callback.answer("Неизвестная категория")
        return

    lines = [f"<b>{_CATEGORY_LABELS[cat]}</b>\n"]
    for k in _CATEGORIES[cat]:
        label = _SETTING_LABELS.get(k, k)
        val = _fmt_val(runtime_settings, k)
        lines.append(f"• {label}: <code>{val}</code>")

    if callback.message:
        await callback.message.edit_text(
            "\n".join(lines) + "\n\nНажми на параметр, чтобы изменить:",
            reply_markup=_category_keyboard(cat),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("setval:"))
async def on_setting_pick(
    callback: CallbackQuery,
    settings: Settings,
    runtime_settings: RuntimeSettingsStore,
    dembel_service: DembelService,
) -> None:
    user = callback.from_user
    if user is None:
        await callback.answer()
        return
    key = (callback.data or "").removeprefix("setval:")
    label = _SETTING_LABELS.get(key, key)

    if key == "dembel_enabled":
        # Toggle
        current = runtime_settings.get(key, False)
        new_val = not current
        runtime_settings.set(key, new_val)
        settings.apply_overlay(runtime_settings.data)
        status = "включён" if new_val else "выключен"
        if new_val:
            await dembel_service.restart()
        else:
            await dembel_service.stop()
        await callback.answer(f"Дембель {status}")
        # Refresh the category view
        cat = _find_category(key)
        if cat and callback.message:
            lines = [f"<b>{_CATEGORY_LABELS[cat]}</b>\n"]
            for k in _CATEGORIES[cat]:
                lbl = _SETTING_LABELS.get(k, k)
                val = _fmt_val(runtime_settings, k)
                lines.append(f"• {lbl}: <code>{val}</code>")
            await callback.message.edit_text(
                "\n".join(lines) + "\n\nНажми на параметр, чтобы изменить:",
                reply_markup=_category_keyboard(cat),
            )
        return

    _awaiting[user.id] = key
    hint = _input_hint(key)
    await callback.message.edit_text(
        f"{label}\n\n{hint}\n\n"
        f"Текущее значение: <code>{_fmt_val(runtime_settings, key)}</code>\n\n"
        f"<i>Напиши новое значение в чат (или /cancel для отмены).</i>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="◀️ Отмена", callback_data="set:main"),
            ]],
        ),
    )
    await callback.answer()


def _find_category(key: str) -> str | None:
    for cat, keys in _CATEGORIES.items():
        if key in keys:
            return cat
    return None


def _input_hint(key: str) -> str:
    hints = {
        "openai_api_key": "Введите новый API-ключ (начинается с sk-…):",
        "openai_base_url": "Введите новый Base URL (например https://api.openai.com/v1):",
        "openai_model": "Введите название модели (например gpt-4o-mini):",
        "assistant_system_prompt": "Введите новый системный промпт:",
        "available_models": "Введите список моделей через запятую (пусто = все):",
        "models_cache_ttl_seconds": "Введите TTL кэша в секундах (например 300):",
        "dembel_user_id": "Введите Telegram user_id для дембель-счётчика:",
        "dembel_chat_id": "Введите chat_id группы для дембель-счётчика:",
        "dembel_days": "Введите начальное количество дней (например 347):",
        "dembel_check_interval_seconds": "Введите интервал проверки в секундах (60 = минута, 3600 = час):",
        "allowed_telegram_user_ids": "Введите ID пользователей через запятую (пусто = все):",
    }
    return hints.get(key, "Введите новое значение:")


# ── text input catcher ────────────────────────────────────────────

@router.message(F.text, ~F.text.startswith("/"))
async def catch_setting_value(
    message: Message,
    settings: Settings,
    runtime_settings: RuntimeSettingsStore,
    openai_client: AsyncOpenAI,
    dembel_service: DembelService,
) -> None:
    user = message.from_user
    if user is None:
        return
    key = _awaiting.pop(user.id, None)
    if key is None:
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Значение не может быть пустым. Попробуй ещё раз или /cancel.")
        _awaiting[user.id] = key
        return

    # Validate and convert
    if key in ("models_cache_ttl_seconds", "dembel_user_id", "dembel_chat_id", "dembel_days", "dembel_check_interval_seconds"):
        try:
            val = int(text)
        except ValueError:
            await message.answer("Ошибка: нужно ввести число. Попробуй ещё раз.")
            _awaiting[user.id] = key
            return
    else:
        val = text

    runtime_settings.set(key, val)
    settings.apply_overlay(runtime_settings.data)

    # If API key or base URL changed, update the live client
    if key in ("openai_api_key", "openai_base_url"):
        if key == "openai_api_key":
            openai_client.api_key = val
        elif key == "openai_base_url":
            openai_client.base_url = val
        logger.info("Runtime: %s updated on live client", key)

    # If a dembel setting changed (toggle handled in on_setting_pick), restart service
    if key.startswith("dembel") and key != "dembel_enabled":
        if settings.dembel_enabled:
            await dembel_service.restart()
        logger.info("Runtime: dembel setting %s updated, dembel_enabled=%s", key, settings.dembel_enabled)

    await message.answer(f"✅ <b>{_SETTING_LABELS.get(key, key)}</b> обновлено!\n\n"
                         f"Новое значение: <code>{_fmt_val(runtime_settings, key)}</code>")

    logger.info("Runtime setting %s updated by user %s", key, user.id)
