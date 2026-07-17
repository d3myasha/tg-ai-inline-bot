from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет!\n"
        "• В личном чате просто напиши текст — отвечу.\n"
        "• В группе используй <code>/ai вопрос</code> или "
        "<code>/ask вопрос</code>.\n"
        "• Inline: @имя_бота вопрос; @имя_бота model — выбор модели.\n"
        "• /model — меню моделей.\n"
        "• /settings — все настройки (API, модель, дембель).\n"
        "• /start — это сообщение."
    )