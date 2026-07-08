import logging

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.filters import Command
from aiogram.types import Message
from openai import AsyncOpenAI

from bot.config import Settings
from bot.handlers.access import is_user_allowed
from bot.services.llm import complete_chat, truncate_for_telegram
from bot.services.user_models import UserModelStore

logger = logging.getLogger(__name__)

router = Router(name="chat")


@router.message(F.text, ~Command())
async def handle_text_message(
    message: Message,
    settings: Settings,
    openai_client: AsyncOpenAI,
    user_model_store: UserModelStore,
) -> None:
    if message.from_user is None:
        return

    text = (message.text or "").strip()
    if not text:
        return

    if not is_user_allowed(settings, message.from_user.id):
        await message.answer("У вас нет доступа к этому боту.")
        return

    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    model = await user_model_store.get_model(message.from_user.id)

    try:
        answer_text = await complete_chat(
            openai_client, settings, text, model=model
        )
    except Exception:
        logger.exception("LLM request failed")
        await message.answer(
            "Не удалось получить ответ от API. Проверь OPENAI_API_KEY, "
            "OPENAI_BASE_URL и OPENAI_MODEL в .env"
        )
        return

    await message.answer(truncate_for_telegram(answer_text))