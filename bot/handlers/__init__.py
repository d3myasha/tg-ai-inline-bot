from aiogram import Router

from bot.handlers.chat import router as chat_router
from bot.handlers.start import router as start_router


def setup_routers() -> Router:
    root = Router()
    root.include_router(start_router)
    root.include_router(chat_router)
    return root