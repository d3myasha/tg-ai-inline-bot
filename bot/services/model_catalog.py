import hashlib
import logging
import time

from openai import AsyncOpenAI

from bot.config import Settings

logger = logging.getLogger(__name__)

INLINE_MODEL_ID_PREFIX = "mset:"
INLINE_MODEL_HASH_PREFIX = "mset:h:"
INLINE_MAX_RESULTS = 49


class ModelCatalogService:
    def __init__(self, ttl_seconds: int = 300) -> None:
        self._ttl = ttl_seconds
        self._cached: list[str] | None = None
        self._cached_at: float = 0.0
        self._hash_to_model: dict[str, str] = {}

    def _env_filter(self, settings: Settings) -> set[str] | None:
        raw = settings.available_models.strip()
        if not raw:
            return None
        return {part.strip() for part in raw.split(",") if part.strip()}

    async def fetch_catalog(
        self,
        client: AsyncOpenAI,
        settings: Settings,
        *,
        force_refresh: bool = False,
    ) -> list[str]:
        now = time.monotonic()
        if (
            not force_refresh
            and self._cached is not None
            and now - self._cached_at < self._ttl
        ):
            return self._cached

        try:
            ids = []
            async for item in client.models.list():
                mid = getattr(item, "id", None)
                if mid:
                    ids.append(mid)
        except Exception:
            logger.exception("Failed to fetch models from provider /models")
            ids = []

        env_only = self._env_filter(settings)
        if env_only is not None and not ids:
            ids = sorted(env_only)
        elif env_only is not None:
            ids = [m for m in ids if m in env_only]

        if not ids:
            ids = [settings.openai_model]
        else:
            ids = sorted(set(ids))
            if settings.openai_model not in ids:
                ids.insert(0, settings.openai_model)

        self._cached = ids
        self._cached_at = now
        self._rebuild_hash_map(ids)
        return ids

    def _rebuild_hash_map(self, models: list[str]) -> None:
        self._hash_to_model = {}
        for name in models:
            rid = self.inline_result_id(name)
            if rid.startswith(INLINE_MODEL_HASH_PREFIX):
                key = rid.removeprefix(INLINE_MODEL_HASH_PREFIX)
                self._hash_to_model[key] = name

    def inline_result_id(self, model: str) -> str:
        direct = f"{INLINE_MODEL_ID_PREFIX}{model}"
        if len(direct.encode("utf-8")) <= 64:
            return direct
        digest = hashlib.sha256(model.encode("utf-8")).hexdigest()[:16]
        return f"{INLINE_MODEL_HASH_PREFIX}{digest}"

    def model_from_inline_result_id(self, result_id: str) -> str | None:
        if result_id.startswith(INLINE_MODEL_HASH_PREFIX):
            return self._hash_to_model.get(
                result_id.removeprefix(INLINE_MODEL_HASH_PREFIX)
            )
        if result_id.startswith(INLINE_MODEL_ID_PREFIX):
            return result_id.removeprefix(INLINE_MODEL_ID_PREFIX)
        return None

    def models_for_inline(self, catalog: list[str]) -> list[str]:
        return catalog[:INLINE_MAX_RESULTS]


def create_model_catalog_service(settings: Settings) -> ModelCatalogService:
    return ModelCatalogService(ttl_seconds=settings.models_cache_ttl_seconds)