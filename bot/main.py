import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import get_settings
from bot.handlers import setup_routers
from bot.middleware import InjectDependenciesMiddleware
from bot.services.llm import create_openai_client
from bot.services.user_models import create_user_model_store


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    settings = get_settings()
    openai_client = create_openai_client(settings)
    user_model_store = create_user_model_store(settings)

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.update.middleware(
        InjectDependenciesMiddleware(
            settings=settings,
            openai_client=openai_client,
            user_model_store=user_model_store,
        ),
    )
    dp.include_router(setup_routers())

    log = logging.getLogger(__name__)
    log.info("Starting long polling (webhook disabled)")

    try:
        await dp.start_polling(bot)
    finally:
        await openai_client.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())