"""Redis cache for intents, embeddings, and queries."""

import json
import logging
from typing import Any, Dict, List, Optional

import redis

from inspection_ai.core.config import get_settings

logger = logging.getLogger(__name__)


class RedisCache:
    """Redis-backed fast cache for section intents and derived artifacts.

    Degrades gracefully: with no reachable Redis, ``client`` is ``None`` and
    every operation is a no-op so callers never need to branch.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.client: Optional[redis.Redis] = None
        try:
            self.client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
            self.client.ping()
        except Exception as exc:
            logger.warning("Redis unavailable, caching disabled: %s", exc)
            self.client = None

    @staticmethod
    def _intent_key(
        section_id: str,
        field_count: int,
        report_id: Optional[str],
        form_type: Optional[str],
    ) -> str:
        return (
            f"intent:{form_type or 'default'}:"
            f"{report_id or 'global'}:{section_id}:{field_count}"
        )

    def get_intent(
        self,
        section_id: str,
        field_count: int,
        report_id: Optional[str] = None,
        form_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if self.client is None:
            return None
        try:
            raw = self.client.get(
                self._intent_key(section_id, field_count, report_id, form_type)
            )
            return json.loads(raw) if raw else None
        except Exception as exc:
            logger.warning("Redis get_intent failed: %s", exc)
            return None

    def set_intent(
        self,
        section_id: str,
        field_count: int,
        intent: Dict[str, Any],
        ttl: int = 3600,
        report_id: Optional[str] = None,
        form_type: Optional[str] = None,
    ) -> bool:
        if self.client is None:
            return False
        try:
            self.client.set(
                self._intent_key(section_id, field_count, report_id, form_type),
                json.dumps(intent),
                ex=ttl,
            )
            return True
        except Exception as exc:
            logger.warning("Redis set_intent failed: %s", exc)
            return False

    def get_json(self, key: str) -> Optional[Any]:
        if self.client is None:
            return None
        try:
            raw = self.client.get(key)
            return json.loads(raw) if raw else None
        except Exception as exc:
            logger.warning("Redis get_json failed: %s", exc)
            return None

    def set_json(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        if self.client is None:
            return False
        try:
            payload = json.dumps(value)
            if ttl:
                self.client.set(key, payload, ex=ttl)
            else:
                self.client.set(key, payload)
            return True
        except Exception as exc:
            logger.warning("Redis set_json failed: %s", exc)
            return False

    def delete_pattern(self, pattern: str) -> int:
        if self.client is None:
            return 0
        try:
            keys: List[str] = list(self.client.scan_iter(match=pattern))
            if keys:
                self.client.delete(*keys)
            return len(keys)
        except Exception as exc:
            logger.warning("Redis delete_pattern failed: %s", exc)
            return 0