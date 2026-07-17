from functools import lru_cache
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Only in .env ────────────────────────────────────────────
    telegram_bot_token: str = Field(validation_alias="TELEGRAM_BOT_TOKEN")
    dev_telegram_id: int = Field(validation_alias="DEV_TELEGRAM_ID")

    # ── Runtime-overridable (defaults, see runtime_settings.json) ──
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias="OPENAI_BASE_URL",
    )
    openai_model: str = Field(default="gpt-4o-mini", validation_alias="OPENAI_MODEL")
    available_models: str = Field(
        default="",
        validation_alias="AVAILABLE_MODELS",
    )
    models_cache_ttl_seconds: int = Field(
        default=300,
        validation_alias="MODELS_CACHE_TTL_SECONDS",
    )
    user_models_path: str = Field(
        default="/data/user_models.json",
        validation_alias="USER_MODELS_PATH",
    )
    assistant_system_prompt: str = Field(
        default=(
            "You are a helpful assistant. Answer in the user's language. "
            "Use Telegram-friendly Markdown: **bold**, lists with -, "
            "`inline code`, fenced ```code blocks```. Avoid complex HTML."
        ),
        validation_alias="ASSISTANT_SYSTEM_PROMPT",
    )
    allowed_telegram_user_ids: str = Field(
        default="",
        validation_alias="ALLOWED_TELEGRAM_USER_IDS",
    )
    dembel_enabled: bool = Field(default=False, validation_alias="DEMBEL_ENABLED")
    dembel_user_id: int = Field(default=0, validation_alias="DEMBEL_USER_ID")
    dembel_chat_id: int = Field(default=0, validation_alias="DEMBEL_CHAT_ID")
    dembel_days: int = Field(default=0, validation_alias="DEMBEL_DAYS")
    dembel_check_interval_seconds: int = Field(
        default=3600, validation_alias="DEMBEL_CHECK_INTERVAL_SECONDS",
    )

    def apply_overlay(self, data: dict[str, Any]) -> None:
        """Overwrite fields from a runtime settings dict."""
        for key, value in data.items():
            if not hasattr(self, key):
                continue
            if isinstance(value, str) and not value:
                continue
            if isinstance(value, (int, float)) and value == 0 and not key.startswith("dembel"):
                continue
            setattr(self, key, value)

    def allowed_user_id_set(self) -> set[int] | None:
        """Combine dev_telegram_id + allowed_telegram_user_ids."""
        ids: set[int] = set()
        if self.dev_telegram_id:
            ids.add(self.dev_telegram_id)
        raw = self.allowed_telegram_user_ids.strip()
        if raw:
            for part in raw.split(","):
                part = part.strip()
                if part:
                    try:
                        ids.add(int(part))
                    except ValueError:
                        continue
        return ids if ids else None


@lru_cache
def get_settings() -> Settings:
    return Settings()
