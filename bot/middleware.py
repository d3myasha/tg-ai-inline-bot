from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from openai import AsyncOpenAI

from bot.config import Settings
from bot.services.user_models import UserModelStore


class InjectDependenciesMiddleware(BaseMiddleware):
    def __init__(
        self,
        settings: Settings,
        openai_client: AsyncOpenAI,
        user_model_store: UserModelStore,
    ) -> None:
        self._settings = settings
        self._openai_client = openai_client
        self._user_model_store = user_model_store

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["settings"] = self._settings
        data["openai_client"] = self._openai_client
        data["user_model_store"] = self._user_model_store
        return await handler(event, data)