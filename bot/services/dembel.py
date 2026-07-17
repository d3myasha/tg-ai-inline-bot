import asyncio
import json
import logging
import random
import time
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from bot.config import Settings

logger = logging.getLogger(__name__)

DEMBEL_QUOTES = [
    "🇷🇺 Дембель — это не просто слово, это состояние души.",
    "🇷🇺 Кто не служил, тот не поймёт, что такое дембель.",
    "🇷🇺 Дембель — это когда ты уже не солдат, но ещё не гражданский.",
    "🇷🇺 Солдат спит — служба идёт. Дембель спит — дембель идёт.",
    "🇷🇺 Дембель неизбежен, как налоги.",
    "🇷🇺 У дембеля выходных не бывает — бывает только дембель.",
    "🇷🇺 100 дней до приказа — ещё не дембель, но уже и не солдат.",
    "🇷🇺 Дембель — это праздник, который всегда с тобой.",
    "🇷🇺 Три года — не три дня, а дембель — один.",
    "🇷🇺 Чем ближе дембель, тем громче оркестр.",
    "🇷🇺 Дембель — это момент, когда ты понимаешь, что Родина тебя больше не ищет.",
    "🇷🇺 Дембельские 100 дней считает каждый солдат. А мы считаем каждый день!",
    "🇷🇺 Дембель — это финишная прямая. Добежать бы…",
    "🇷🇺 Чемодан — на выход! Дембель — на вход!",
    "🇷🇺 Отслужил — и спи спокойно. Дембель всё расставил по местам.",
    "🇷🇺 Дембельский аккорд — последняя песня солдата.",
    "🇷🇺 Дембель — это когда дембельнулся и забыл, как по стойке смирно стоять.",
    "🇷🇺 У каждого солдата есть мечта. И имя ей — Дембель.",
    "🇷🇺 ДМБ — это не фильм, это жизнь после армии.",
    "🇷🇺 С каждым днём всё ближе к дому, с каждым днём всё дальше от казармы.",
]

_STATE_FILE = "/data/dembel_state.json"


class DembelState:
    def __init__(self, path: str = _STATE_FILE) -> None:
        self._path = Path(path)
        self.current_days: int = 0
        self.last_updated: float = 0.0  # Unix timestamp

    def load(self) -> None:
        if not self._path.exists():
            logger.info("No dembel state file, starting fresh")
            self.current_days = 0
            self.last_updated = 0.0
            return
        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
            self.current_days = int(data.get("current_days", 0))
            last = data.get("last_updated", 0)
            self.last_updated = float(last) if last else 0.0
        except (OSError, json.JSONDecodeError, ValueError):
            logger.exception("Failed to load dembel state")
            self.current_days = 0
            self.last_updated = 0.0

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        content = json.dumps(
            {"current_days": self.current_days, "last_updated": self.last_updated},
            ensure_ascii=False,
        )
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(self._path)

    def should_update(self, min_interval: float) -> bool:
        """Return True if min_interval seconds passed since last update and days > 0."""
        return (
            self.current_days > 0
            and (time.time() - self.last_updated) >= min_interval
        )

    def apply_update(self) -> int | None:
        """Decrement and save. Returns new count or None if already at zero."""
        if self.current_days <= 0:
            return None
        old = self.current_days
        self.current_days -= 1
        self.last_updated = time.time()
        self.save()
        logger.info("Dembel: %d → %d", old, self.current_days)
        return self.current_days

    @property
    def title_text(self) -> str:
        return f"{self.current_days}ДДД"


class DembelService:
    def __init__(self, bot: Bot, settings: Settings) -> None:
        self._bot = bot
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
            self._state.last_updated = 0.0  # force first update
            self._state.save()
            logger.info("Dembel initialised at %d days", self._state.current_days)

        # Check on startup
        await self._check_and_update()

        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "Dembel service started, %d days remaining, interval=%ds",
            self._state.current_days,
            self._settings.dembel_check_interval_seconds,
        )

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._settings.dembel_check_interval_seconds)
                await self._check_and_update()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Dembel loop error")

    async def _check_and_update(self) -> None:
        interval = self._settings.dembel_check_interval_seconds
        if not self._state.should_update(interval):
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
        except TelegramBadRequest as e:
            logger.warning(
                "Failed to set custom title %s: %s. "
                "Make sure the bot is admin in the group and the user is an admin.",
                title,
                e,
            )

    async def _send_quote(self) -> None:
        quote = random.choice(DEMBEL_QUOTES)
        days_left = self._state.current_days
        sign = "🎉 Дембель!" if days_left == 0 else f"📆 Осталось {days_left} дн."
        text = f"{sign}\n\n{quote}"
        try:
            await self._bot.send_message(
                chat_id=self._settings.dembel_chat_id,
                text=text,
            )
            logger.info("Dembel quote sent to chat %s", self._settings.dembel_chat_id)
        except TelegramBadRequest as e:
            logger.warning("Failed to send dembel quote: %s", e)
