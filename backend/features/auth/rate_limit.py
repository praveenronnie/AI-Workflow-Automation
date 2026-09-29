"""Login rate limiting backed by Redis (shared across workers/replicas).

Falls back to the previous per-process in-memory window when Redis is
unreachable, so dev environments without Redis still boot.
"""

import logging
import time

from backend.ai.storage.cache import RedisCache

logger = logging.getLogger(__name__)

LOGIN_LIMIT = 10  # max attempts per window
LOGIN_WINDOW = 300  # seconds

_fallback_attempts: dict = {}
_cache: RedisCache | None = None


def _get_cache() -> RedisCache | None:
    global _cache
    if _cache is None:
        try:
            _cache = RedisCache()
        except Exception:  # noqa: BLE001
            _cache = None
    return _cache


def check_login_allowed(ip: str) -> bool:
    """Record an attempt and return False when the IP exceeded the limit."""
    now = time.time()
    cache = _get_cache()
    key = f"ratelimit:login:{ip}"
    if cache is not None and cache.client is not None:
        try:
            client = cache.client
            count = client.incr(key)
            if count == 1:
                client.expire(key, LOGIN_WINDOW)
            return count <= LOGIN_LIMIT
        except Exception as exc:  # noqa: BLE001 — fall through to memory
            logger.warning("Redis rate limit unavailable, using memory: %s", exc)

    recent = [t for t in _fallback_attempts.get(ip, []) if now - t < LOGIN_WINDOW]
    allowed = len(recent) < LOGIN_LIMIT
    if allowed:
        recent.append(now)
    _fallback_attempts[ip] = recent
    return allowed
