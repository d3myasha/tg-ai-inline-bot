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
    llm_task: asyncio.Task[None] | None = field(default=None, repr=False)
    deliver_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)


class InlinePendingStore:
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
            job = self._jobs.pop(rid, None)
            if job and job.llm_task and not job.llm_task.done():
                job.llm_task.cancel()

    async def put(self, result_id: str, job: InlineAiJob) -> InlineAiJob | None:
        async with self._lock:
            self._purge_expired()
            old = self._jobs.get(result_id)
            self._jobs[result_id] = job
            return old

    async def get(self, result_id: str) -> InlineAiJob | None:
        async with self._lock:
            self._purge_expired()
            return self._jobs.get(result_id)

    async def pop(self, result_id: str) -> InlineAiJob | None:
        async with self._lock:
            self._purge_expired()
            return self._jobs.pop(result_id, None)