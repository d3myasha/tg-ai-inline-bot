import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import Settings
from bot.handlers.access import is_user_allowed
from bot.services.dembel import DembelService

logger = logging.getLogger(__name__)

router = Router(name="dembel_cmd")


@router.message(Command("dembel"))
async def cmd_dembel(
    message: Message,
    settings: Settings,
    dembel_service: DembelService,
) -> None:
    if message.from_user is None:
        return
    if not is_user_allowed(settings, message.from_user.id):
        await message.answer("У вас нет доступа.")
        return

    if not settings.dembel_enabled:
        await message.answer(
            "📅 Дембель выключен. Включи через /settings → Дембель."
        )
        return

    remaining = dembel_service.days_remaining
    if remaining <= 0:
        await message.answer(
            f"🎉 Дембель уже наступил! Все {dembel_service.days_remaining} дней прошли."
        )
        return

    await message.answer(
        f"📅 Запускаю… Осталось {remaining} дн."
    )
    await dembel_service.trigger_now()
