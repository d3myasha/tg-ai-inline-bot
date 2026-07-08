from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет!\n"
        "• Напиши сюда текст — отвечу в чате.\n"
        "• Inline: @имя_бота вопрос; @имя_бота model — выбор модели.\n"
        "• /model — меню моделей. Выбор **только для вашего Telegram user_id** "
        "(личка, группы, inline — одна модель на аккаунт, не на чат).\n"
        "• Дефолт без выбора: OPENAI_MODEL в .env.\n"
        "• BotFather: /setinline и **inline feedback** (иначе inline-ответ не обновится в чате)."
    )