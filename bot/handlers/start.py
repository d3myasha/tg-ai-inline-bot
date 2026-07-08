from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет!\n"
        "• Напиши сюда текст — отвечу в чате.\n"
        "• Inline: @имя_бота вопрос — ответ ИИ; @имя_бота model — выбор модели (сохраняется везде).\n"
        "• /model — то же меню в чате. Дефолт: OPENAI_MODEL в .env.\n"
        "• BotFather: /setinline и включи inline feedback для выбора модели."
    )