import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class InlineAiJob:
    query: str
    model: str
    user_id: int
    created_at: float
    answer: str | None = None
    error: str | None = None
    inline_message_id: str | None = None
    chat_id: int | None = None
    message_id: int | None = None
    _deliver_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)


class InlinePendingStore:
    """Maps inline result_id → in-flight or completed LLM job."""

    def __init__(self, ttl_seconds: int = 600) -> None:
        self._ttl = ttl_seconds
        self._jobs: dict[str, InlineAiJob] = {}
        self._lock = asyncio.Lock()

    def _purge_expired(self) -> None:
        now = time.monotonic()
        expired = [
            rid
            for rid, job in self._jobs.items()
            if now - job.created_at > self._ttl
        ]
        for rid in expired:
            self._jobs.pop(rid, None)

    async def put(self, result_id: str, job: InlineAiJob) -> None:
        async with self._lock:
            self._purge_expired()
            self._jobs[result_id] = job

    async def get(self, result_id: str) -> InlineAiJob | None:
        async with self._lock:
            self._purge_expired()
            return self._jobs.get(result_id)

    async def pop(self, result_id: str) -> InlineAiJob | None:
        async with self._lock:
            self._purge_expired()
            return self._jobs.pop(result_id, None)