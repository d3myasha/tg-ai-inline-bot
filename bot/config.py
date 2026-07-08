from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str = Field(validation_alias="TELEGRAM_BOT_TOKEN")
    openai_api_key: str = Field(validation_alias="OPENAI_API_KEY")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias="OPENAI_BASE_URL",
    )
    openai_model: str = Field(default="gpt-4o-mini", validation_alias="OPENAI_MODEL")
    assistant_system_prompt: str = Field(
        default="You are a helpful assistant. Answer concisely in the user's language.",
        validation_alias="ASSISTANT_SYSTEM_PROMPT",
    )
    allowed_telegram_user_ids: str = Field(
        default="",
        validation_alias="ALLOWED_TELEGRAM_USER_IDS",
    )

    def allowed_user_id_set(self) -> set[int] | None:
        raw = self.allowed_telegram_user_ids.strip()
        if not raw:
            return None
        ids: set[int] = set()
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            ids.add(int(part))
        return ids


@lru_cache
def get_settings() -> Settings:
    return Settings()