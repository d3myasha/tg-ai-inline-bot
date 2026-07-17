import logging

from aiogram import Router
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from openai import AsyncOpenAI

from bot.config import Settings
from bot.handlers.access import is_user_allowed
from bot.services.llm import complete_chat
from bot.services.telegram_send import reply_llm_text
from bot.services.user_models import UserModelStore

logger = logging.getLogger(__name__)

router = Router(name="ask")


@router.message(Command("ai", "ask"))
async def cmd_ai(
    message: Message,
    command: CommandObject,
    settings: Settings,
    openai_client: AsyncOpenAI,
    user_model_store: UserModelStore,
) -> None:
    if message.from_user is None:
        return

    if not is_user_allowed(settings, message.from_user.id):
        await message.answer("У вас нет доступа к этому боту.")
        return

    query = (command.args or "").strip()
    if not query:
        await message.answer(
            "Напиши вопрос после команды.\n\n"
            "Примеры:\n"
            "<code>/ai какой смысл жизни?</code>\n"
            "<code>/ask краткая история Рима</code>"
        )
        return

    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    model = await user_model_store.get_model(message.from_user.id)
    logger.info(
        "AI command user=%s chat=%s model=%s text=%r",
        message.from_user.id,
        message.chat.id,
        model,
        query[:120],
    )

    try:
        answer_text = await complete_chat(
            openai_client, settings, query, model=model,
        )
    except Exception:
        logger.exception("LLM request failed")
        await message.answer(
            "Не удалось получить ответ от API. Проверь OPENAI_API_KEY, "
            "OPENAI_BASE_URL и OPENAI_MODEL в .env",
        )
        return

    await reply_llm_text(message, answer_text, user_query=query)
