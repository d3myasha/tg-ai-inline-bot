from aiogram import Router

from bot.handlers.inline import router as inline_router
from bot.handlers.start import router as start_router


def setup_routers() -> Router:
    root = Router()
    root.include_router(start_router)
    root.include_router(inline_router)
    return root