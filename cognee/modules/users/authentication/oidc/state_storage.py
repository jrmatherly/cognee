"""OAuth state storage backends.

Provides pluggable state storage for OAuth flows:
- InMemoryStateStorage: Single-instance deployments (default)
- RedisStateStorage: Multi-instance Kubernetes deployments

Configure via OAUTH_STATE_REDIS_URL environment variable.
"""

import os
import time
from abc import ABC, abstractmethod
from typing import Optional, Tuple
from functools import lru_cache

from cognee.shared.logging_utils import get_logger

logger = get_logger("oauth_state_storage")

# State TTL in seconds (default: 10 minutes)
STATE_TTL = int(os.getenv("OAUTH_STATE_TTL", "600"))


class OAuthStateStorage(ABC):
    """Abstract base class for OAuth state storage."""

    @abstractmethod
    async def set(self, state: str, redirect_uri: str) -> None:
        """Store OAuth state with redirect URI.

        Args:
            state: Cryptographically secure state token
            redirect_uri: URL to redirect after authentication
        """
        pass

    @abstractmethod
    async def get_and_delete(self, state: str) -> Optional[Tuple[str, float]]:
        """Retrieve and delete OAuth state (atomic operation).

        Args:
            state: State token to retrieve

        Returns:
            Tuple of (redirect_uri, timestamp) or None if not found/expired
        """
        pass

    @abstractmethod
    async def cleanup_expired(self) -> int:
        """Remove expired state entries.

        Returns:
            Number of entries removed
        """
        pass


class InMemoryStateStorage(OAuthStateStorage):
    """In-memory state storage for single-instance deployments.

    WARNING: Do not use in multi-pod Kubernetes deployments.
    Set OAUTH_STATE_REDIS_URL for distributed deployments.
    """

    def __init__(self):
        self._states: dict[str, Tuple[str, float]] = {}
        logger.info("Using in-memory OAuth state storage (single-instance only)")

    async def set(self, state: str, redirect_uri: str) -> None:
        """Store state in memory with current timestamp."""
        self._states[state] = (redirect_uri, time.time())

    async def get_and_delete(self, state: str) -> Optional[Tuple[str, float]]:
        """Pop state from memory if exists and not expired."""
        if state not in self._states:
            return None

        redirect_uri, timestamp = self._states.pop(state)

        # Check if expired
        if time.time() - timestamp > STATE_TTL:
            logger.debug(f"OAuth state expired: {state[:8]}...")
            return None

        return redirect_uri, timestamp

    async def cleanup_expired(self) -> int:
        """Remove expired entries from memory."""
        current_time = time.time()
        expired = [
            s for s, (_, ts) in self._states.items()
            if current_time - ts > STATE_TTL
        ]
        for state in expired:
            del self._states[state]

        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired OAuth states")
        return len(expired)


class RedisStateStorage(OAuthStateStorage):
    """Redis-backed state storage for multi-instance deployments.

    Requires: pip install redis[hiredis]
    Configure via OAUTH_STATE_REDIS_URL environment variable.
    """

    def __init__(self, redis_url: str):
        try:
            import redis.asyncio as redis_async
        except ImportError:
            raise ImportError(
                "Redis support requires 'redis' package. "
                "Install with: pip install redis[hiredis]"
            )

        self._redis = redis_async.from_url(
            redis_url,
            decode_responses=True,
            socket_timeout=5.0,
            socket_connect_timeout=5.0,
        )
        self._key_prefix = "cognee:oauth:state:"
        logger.info(f"Using Redis OAuth state storage: {redis_url[:20]}...")

    def _key(self, state: str) -> str:
        """Generate Redis key for state."""
        return f"{self._key_prefix}{state}"

    async def set(self, state: str, redirect_uri: str) -> None:
        """Store state in Redis with TTL."""
        key = self._key(state)
        value = f"{redirect_uri}:{time.time()}"
        await self._redis.setex(key, STATE_TTL, value)

    async def get_and_delete(self, state: str) -> Optional[Tuple[str, float]]:
        """Atomically get and delete state from Redis."""
        key = self._key(state)

        # Use GETDEL for atomic operation (Redis 6.2+)
        try:
            value = await self._redis.getdel(key)
        except Exception:
            # Fallback for older Redis versions
            value = await self._redis.get(key)
            if value:
                await self._redis.delete(key)

        if not value:
            return None

        # Parse stored value
        try:
            redirect_uri, timestamp_str = value.rsplit(":", 1)
            return redirect_uri, float(timestamp_str)
        except ValueError:
            logger.warning(f"Invalid OAuth state format: {key}")
            return None

    async def cleanup_expired(self) -> int:
        """Redis TTL handles expiration automatically."""
        return 0

    async def close(self):
        """Close Redis connection."""
        await self._redis.close()


# Singleton instance
_state_storage: Optional[OAuthStateStorage] = None


def get_state_storage() -> OAuthStateStorage:
    """Factory function to get appropriate state storage backend.

    Uses Redis if OAUTH_STATE_REDIS_URL is set, otherwise in-memory.

    Returns:
        Configured OAuthStateStorage instance
    """
    global _state_storage

    if _state_storage is not None:
        return _state_storage

    redis_url = os.getenv("OAUTH_STATE_REDIS_URL")

    if redis_url:
        _state_storage = RedisStateStorage(redis_url)
    else:
        # Warn if running in Kubernetes without Redis
        k8s_indicators = [
            os.getenv("KUBERNETES_SERVICE_HOST"),
            os.getenv("KUBERNETES_PORT"),
        ]
        if any(k8s_indicators):
            logger.warning(
                "Running in Kubernetes without Redis state storage. "
                "OAuth authentication may fail across pods. "
                "Set OAUTH_STATE_REDIS_URL for production deployments."
            )

        _state_storage = InMemoryStateStorage()

    return _state_storage
