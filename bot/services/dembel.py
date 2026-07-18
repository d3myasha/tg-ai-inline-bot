import asyncio
import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from openai import AsyncOpenAI

from bot.config import Settings
from bot.services.llm import complete_chat

logger = logging.getLogger(__name__)

_STATE_FILE = "/data/dembel_state.json"
_CHECK_INTERVAL = 3600  # check every hour, decrement once per day


class DembelState:
    def __init__(self, path: str = _STATE_FILE) -> None:
        self._path = Path(path)
        self.current_days: int = 0
        self.last_updated: str = ""  # YYYY-MM-DD

    def load(self) -> None:
        if not self._path.exists():
            logger.info("No dembel state file, starting fresh")
            self.current_days = 0
            self.last_updated = ""
            return
        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
            self.current_days = int(data.get("current_days", 0))
            self.last_updated = str(data.get("last_updated", ""))
        except (OSError, json.JSONDecodeError, ValueError):
            logger.exception("Failed to load dembel state")
            self.current_days = 0
            self.last_updated = ""

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        content = json.dumps(
            {"current_days": self.current_days, "last_updated": self.last_updated},
            ensure_ascii=False,
        )
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(self._path)

    def should_update(self) -> bool:
        """Return True if a new calendar day has started and days > 0."""
        if self.current_days <= 0:
            return False
        today = date.today().isoformat()
        return self.last_updated != today

    def apply_update(self) -> int | None:
        """Decrement and save. Returns new count or None if already at zero."""
        if self.current_days <= 0:
            return None
        old = self.current_days
        self.current_days -= 1
        self.last_updated = date.today().isoformat()
        self.save()
        logger.info("Dembel: %d → %d", old, self.current_days)
        return self.current_days

    @property
    def title_text(self) -> str:
        return f"{self.current_days}ДДД"


class DembelService:
    def __init__(
        self, bot: Bot, openai_client: AsyncOpenAI, settings: Settings,
    ) -> None:
        self._bot = bot
        self._openai_client = openai_client
        self._settings = settings
        self._state = DembelState()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if not self._settings.dembel_enabled:
            logger.info("Dembel service disabled")
            return
        self._state.load()
        if self._state.current_days == 0 and self._settings.dembel_days > 0:
            self._state.current_days = self._settings.dembel_days
            self._state.last_updated = ""  # force first update
            self._state.save()
            logger.info("Dembel initialised at %d days", self._state.current_days)

        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "Dembel service started, %d days remaining, check every %ds",
            self._state.current_days,
            _CHECK_INTERVAL,
        )

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def restart(self) -> None:
        """Stop the current loop (if running) and start a fresh one."""
        await self.stop()
        await self.start()

    async def trigger_now(self) -> None:
        """Force decrement, update title and send quote immediately."""
        if not self._settings.dembel_enabled or self._state.current_days <= 0:
            return
        self._state.apply_update()
        await self._apply_title()
        await self._send_quote()

    def set_days(self, days: int) -> None:
        """Reset the countdown to a specific number of days."""
        self._state.current_days = max(0, days)
        self._state.last_updated = ""
        self._state.save()
        logger.info("Dembel days reset to %d", self._state.current_days)

    @property
    def days_remaining(self) -> int:
        return self._state.current_days

    async def _run_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(_CHECK_INTERVAL)
                await self._check_and_update()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Dembel loop error")

    async def _check_and_update(self) -> None:
        if not self._state.should_update():
            return
        new_count = self._state.apply_update()
        if new_count is None:
            logger.info("Dembel already at 0, nothing to do")
            return

        await self._apply_title()
        await self._send_quote()

    async def _apply_title(self) -> None:
        title = self._state.title_text
        logger.info(
            "Setting custom title for user %s in chat %s: %s",
            self._settings.dembel_user_id,
            self._settings.dembel_chat_id,
            title,
        )
        try:
            await self._bot.set_chat_administrator_custom_title(
                chat_id=self._settings.dembel_chat_id,
                user_id=self._settings.dembel_user_id,
                custom_title=title,
            )
            logger.info("Custom title updated to %s", title)
        except Exception as e:
            logger.warning(
                "Failed to set custom title %s: %s. "
                "Make sure the bot is admin in the group and the user is an admin.",
                title,
                e,
            )

    async def _send_quote(self) -> None:
        days_left = self._state.current_days
        sign = "🎉 Дембель!" if days_left == 0 else f"📆 Осталось {days_left} дн."
        try:
            quote = await complete_chat(
                self._openai_client,
                self._settings,
                (
                    "Напиши короткую вдохновляющую цитату про дембель из армии. "
                    "Одним абзацем, максимум 2 предложения. "
                    "На русском, в стиле армейского юмора."
                ),
                model=self._settings.openai_model,
            )
        except Exception:
            logger.exception("Failed to generate dembel quote via LLM")
            quote = "🇷🇺 Дембель — это состояние души!"
        text = f"{sign}\n\n{quote}"
        try:
            await self._bot.send_message(
                chat_id=self._settings.dembel_chat_id,
                text=text,
            )
            logger.info("Dembel quote sent to chat %s", self._settings.dembel_chat_id)
        except Exception as e:
            logger.warning("Failed to send dembel quote: %s", e)
