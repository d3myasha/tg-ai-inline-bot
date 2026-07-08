from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет!\n"
        "• Напиши сюда текст — отвечу в чате.\n"
        "• В любом чате: @имя_бота и вопрос — ответ inline (нужен /setinline в BotFather)."
    )