import asyncio
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class InlineAiJob:
    query: str
    model: str
    user_id: int
    created_at: float


class InlinePendingStore:
    """Maps inline result_id → LLM job until user picks a result."""

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

    async def pop(self, result_id: str) -> InlineAiJob | None:
        async with self._lock:
            self._purge_expired()
            return self._jobs.pop(result_id, None)