import json
import logging
from pathlib import Path
from typing import Any

from bot.config import Settings

logger = logging.getLogger(__name__)

_RUNTIME_FILE = "/data/runtime_settings.json"

# Defaults used when file doesn't exist yet
_DEFAULTS: dict[str, Any] = {
    "openai_api_key": "",
    "openai_base_url": "https://api.openai.com/v1",
    "openai_model": "gpt-4o-mini",
    "available_models": "",
    "models_cache_ttl_seconds": 300,
    "assistant_system_prompt": (
        "You are a helpful assistant. Answer in the user's language. "
        "Use Telegram-friendly Markdown: **bold**, lists with -, "
        "`inline code`, fenced ```code blocks```. Avoid complex HTML."
    ),
    "allowed_telegram_user_ids": "",
    "dembel_enabled": False,
    "dembel_user_id": 0,
    "dembel_chat_id": 0,
    "dembel_days": 0,
    "dembel_check_interval_seconds": 3600,
}


class RuntimeSettingsStore:
    """Persistent runtime settings — overrides .env values."""

    def __init__(self, path: str = _RUNTIME_FILE) -> None:
        self._path = Path(path)
        self._data: dict[str, Any] = dict(_DEFAULTS)

    def load(self) -> None:
        if not self._path.exists():
            logger.info("No runtime settings file, using defaults")
            self._data = dict(_DEFAULTS)
            self.save()
            return
        try:
            raw = self._path.read_text(encoding="utf-8")
            loaded = json.loads(raw)
            if isinstance(loaded, dict):
                # Merge over defaults so new fields get populated
                merged = dict(_DEFAULTS)
                merged.update(loaded)
                self._data = merged
            else:
                self._data = dict(_DEFAULTS)
        except (OSError, json.JSONDecodeError):
            logger.exception("Failed to load runtime settings")
            self._data = dict(_DEFAULTS)

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self._path)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    @property
    def data(self) -> dict[str, Any]:
        return dict(self._data)

    def apply_to_settings(self, settings: Settings) -> None:
        """Overwrite Settings fields with runtime values where non-empty."""
        for key, value in self._data.items():
            if not hasattr(settings, key):
                continue
            # Skip empty strings / zero values (user hasn't configured them)
            if isinstance(value, str) and not value:
                continue
            if isinstance(value, (int, float)) and value == 0 and not key.startswith("dembel"):
                continue
            setattr(settings, key, value)
        logger.info("Runtime settings applied to Settings object")

    def override_from_settings(self, settings: Settings) -> None:
        """Copy non-default Settings fields into runtime store."""
        for key in _DEFAULTS:
            val = getattr(settings, key, None)
            if val is not None:
                self._data[key] = val
        self.save()
