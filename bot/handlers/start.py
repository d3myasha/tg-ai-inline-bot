from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет!\n"
        "• Напиши сюда текст — отвечу в чате.\n"
        "• В любом чате: @имя_бота и вопрос — inline (/setinline в BotFather).\n"
        "• /model — выбрать модель (иначе из .env: OPENAI_MODEL)."
    )