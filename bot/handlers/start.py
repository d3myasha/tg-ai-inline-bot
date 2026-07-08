from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет! В любом чате набери @имя_бота и свой вопрос — ответ придёт inline.\n"
        "В BotFather должен быть включён inline: /setinline."
    )