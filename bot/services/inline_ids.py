import hashlib

DEFERRED_PREFIX = "def:"


def deferred_result_id(user_id: int, query: str) -> str:
    digest = hashlib.sha256(f"{user_id}:{query}".encode()).hexdigest()[:24]
    return f"{DEFERRED_PREFIX}{digest}"