from aiogram import F, Router
from aiogram.types import CallbackQuery

router = Router(name="inline_noop")


@router.callback_query(F.data == "def:noop")
async def deferred_placeholder_button(callback: CallbackQuery) -> None:
    await callback.answer()