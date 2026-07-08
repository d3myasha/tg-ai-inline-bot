from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from openai import AsyncOpenAI

from bot.config import Settings
from bot.services.inline_pending import InlinePendingStore
from bot.services.model_catalog import ModelCatalogService
from bot.services.user_models import UserModelStore


class InjectDependenciesMiddleware(BaseMiddleware):
    def __init__(
        self,
        settings: Settings,
        openai_client: AsyncOpenAI,
        user_model_store: UserModelStore,
        model_catalog_service: ModelCatalogService,
        inline_pending_store: InlinePendingStore,
    ) -> None:
        self._settings = settings
        self._openai_client = openai_client
        self._user_model_store = user_model_store
        self._model_catalog_service = model_catalog_service
        self._inline_pending_store = inline_pending_store

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["settings"] = self._settings
        data["openai_client"] = self._openai_client
        data["user_model_store"] = self._user_model_store
        data["model_catalog_service"] = self._model_catalog_service
        data["inline_pending_store"] = self._inline_pending_store
        return await handler(event, data)