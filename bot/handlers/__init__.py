from aiogram import Router

from bot.handlers.ask import router as ask_router
from bot.handlers.chat import router as chat_router
from bot.handlers.dembel_cmd import router as dembel_cmd_router
from bot.handlers.inline import router as inline_router
from bot.handlers.inline_model_capture import router as inline_model_capture_router
from bot.handlers.inline_placeholder import router as inline_placeholder_router
from bot.handlers.inline_noop import router as inline_noop_router
from bot.handlers.model_select import router as model_select_router
from bot.handlers.settings import router as settings_router
from bot.handlers.start import router as start_router


def setup_routers() -> Router:
    root = Router()
    root.include_router(ask_router)
    root.include_router(dembel_cmd_router)
    root.include_router(settings_router)
    root.include_router(start_router)
    root.include_router(inline_noop_router)
    root.include_router(model_select_router)
    root.include_router(inline_model_capture_router)
    root.include_router(inline_placeholder_router)
    root.include_router(chat_router)
    root.include_router(inline_router)
    return root