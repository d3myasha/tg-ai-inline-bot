import asyncio
import json
import logging
from pathlib import Path

from bot.config import Settings

logger = logging.getLogger(__name__)


class UserModelStore:
    def __init__(self, path: Path, default_model: str) -> None:
        self._path = path
        self._default_model = default_model
        self._cache: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def _load(self) -> None:
        if not self._path.exists():
            self._cache = {}
            return
        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, dict):
                self._cache = {str(k): str(v) for k, v in data.items()}
            else:
                self._cache = {}
        except (OSError, json.JSONDecodeError):
            logger.exception("Failed to load user models from %s", self._path)
            self._cache = {}

    async def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self._cache, ensure_ascii=False, indent=0),
            encoding="utf-8",
        )
        tmp.replace(self._path)

    async def ensure_loaded(self) -> None:
        async with self._lock:
            if self._path.exists():
                await self._load()

    async def get_model(self, user_id: int) -> str:
        key = str(user_id)
        async with self._lock:
            if self._path.exists():
                await self._load()
            return self._cache.get(key, self._default_model)

    async def set_model(self, user_id: int, model: str) -> None:
        key = str(user_id)
        async with self._lock:
            if self._path.exists():
                await self._load()
            self._cache[key] = model
            await self._save()

    async def clear_model(self, user_id: int) -> None:
        key = str(user_id)
        async with self._lock:
            if self._path.exists():
                await self._load()
            self._cache.pop(key, None)
            await self._save()


def create_user_model_store(settings: Settings) -> UserModelStore:
    return UserModelStore(
        path=Path(settings.user_models_path),
        default_model=settings.openai_model,
    )