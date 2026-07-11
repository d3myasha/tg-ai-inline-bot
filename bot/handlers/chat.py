import logging

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.types import Message
from openai import AsyncOpenAI

from bot.config import Settings
from bot.handlers.access import is_user_allowed
from bot.services.llm import complete_chat
from bot.services.telegram_send import reply_llm_text
from bot.services.user_models import UserModelStore

logger = logging.getLogger(__name__)

router = Router(name="chat")


@router.message(F.text, ~F.text.startswith("/"))
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
    logger.info(
        "LLM chat start user=%s model=%s text=%r",
        message.from_user.id,
        model,
        text[:120],
    )

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

    await reply_llm_text(message, answer_text, user_query=text)