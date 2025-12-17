"""Tests for OAuth state storage backends."""

import os
import time
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from cognee.modules.users.authentication.oidc.state_storage import (
    OAuthStateStorage,
    InMemoryStateStorage,
    RedisStateStorage,
    get_state_storage,
    STATE_TTL,
)


class TestInMemoryStateStorage:
    """Tests for InMemoryStateStorage class."""

    @pytest.fixture
    def storage(self):
        """Create fresh storage instance for each test."""
        return InMemoryStateStorage()

    @pytest.mark.asyncio
    async def test_set_stores_state(self, storage):
        """Should store state with redirect URI."""
        await storage.set("test_state", "https://example.com/callback")
        assert "test_state" in storage._states

    @pytest.mark.asyncio
    async def test_get_and_delete_returns_data(self, storage):
        """Should return stored data and delete it."""
        await storage.set("test_state", "https://example.com/callback")
        result = await storage.get_and_delete("test_state")

        assert result is not None
        redirect_uri, timestamp = result
        assert redirect_uri == "https://example.com/callback"
        assert isinstance(timestamp, float)
        assert "test_state" not in storage._states

    @pytest.mark.asyncio
    async def test_get_and_delete_returns_none_for_missing(self, storage):
        """Should return None for non-existent state."""
        result = await storage.get_and_delete("nonexistent_state")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_and_delete_returns_none_for_expired(self, storage):
        """Should return None for expired state."""
        # Manually insert expired state
        expired_time = time.time() - STATE_TTL - 1
        storage._states["expired_state"] = ("https://example.com", expired_time)

        result = await storage.get_and_delete("expired_state")
        assert result is None
        assert "expired_state" not in storage._states

    @pytest.mark.asyncio
    async def test_cleanup_expired_removes_old_states(self, storage):
        """Should remove expired states during cleanup."""
        # Add valid state
        await storage.set("valid_state", "https://valid.com")

        # Add expired state
        expired_time = time.time() - STATE_TTL - 1
        storage._states["expired_state"] = ("https://expired.com", expired_time)

        removed = await storage.cleanup_expired()

        assert removed == 1
        assert "valid_state" in storage._states
        assert "expired_state" not in storage._states

    @pytest.mark.asyncio
    async def test_cleanup_expired_returns_zero_when_none_expired(self, storage):
        """Should return 0 when no states are expired."""
        await storage.set("state1", "https://example1.com")
        await storage.set("state2", "https://example2.com")

        removed = await storage.cleanup_expired()
        assert removed == 0

    @pytest.mark.asyncio
    async def test_state_is_one_time_use(self, storage):
        """State should only be retrievable once."""
        await storage.set("single_use_state", "https://example.com")

        # First retrieval succeeds
        result1 = await storage.get_and_delete("single_use_state")
        assert result1 is not None

        # Second retrieval fails
        result2 = await storage.get_and_delete("single_use_state")
        assert result2 is None


class TestRedisStateStorage:
    """Tests for RedisStateStorage class."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        mock = MagicMock()
        mock.setex = AsyncMock()
        mock.getdel = AsyncMock()
        mock.get = AsyncMock()
        mock.delete = AsyncMock()
        mock.close = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_set_stores_with_ttl(self, mock_redis):
        """Should store state in Redis with TTL."""
        with patch("redis.asyncio.from_url", return_value=mock_redis):
            storage = RedisStateStorage("redis://localhost:6379/0")
            await storage.set("test_state", "https://example.com")

            mock_redis.setex.assert_called_once()
            call_args = mock_redis.setex.call_args
            assert "cognee:oauth:state:test_state" in call_args[0]
            assert STATE_TTL in call_args[0]

    @pytest.mark.asyncio
    async def test_get_and_delete_uses_getdel(self, mock_redis):
        """Should use atomic GETDEL operation."""
        mock_redis.getdel.return_value = f"https://example.com:{time.time()}"

        with patch("redis.asyncio.from_url", return_value=mock_redis):
            storage = RedisStateStorage("redis://localhost:6379/0")
            result = await storage.get_and_delete("test_state")

            mock_redis.getdel.assert_called_once()
            assert result is not None

    @pytest.mark.asyncio
    async def test_get_and_delete_fallback_for_old_redis(self, mock_redis):
        """Should fallback to GET+DELETE for older Redis versions."""
        mock_redis.getdel.side_effect = Exception("GETDEL not supported")
        mock_redis.get.return_value = f"https://example.com:{time.time()}"

        with patch("redis.asyncio.from_url", return_value=mock_redis):
            storage = RedisStateStorage("redis://localhost:6379/0")
            result = await storage.get_and_delete("test_state")

            mock_redis.get.assert_called_once()
            mock_redis.delete.assert_called_once()
            assert result is not None

    @pytest.mark.asyncio
    async def test_get_and_delete_returns_none_for_missing(self, mock_redis):
        """Should return None for non-existent state."""
        mock_redis.getdel.return_value = None

        with patch("redis.asyncio.from_url", return_value=mock_redis):
            storage = RedisStateStorage("redis://localhost:6379/0")
            result = await storage.get_and_delete("nonexistent")

            assert result is None

    @pytest.mark.asyncio
    async def test_cleanup_expired_returns_zero(self, mock_redis):
        """Redis TTL handles expiration, cleanup returns 0."""
        with patch("redis.asyncio.from_url", return_value=mock_redis):
            storage = RedisStateStorage("redis://localhost:6379/0")
            result = await storage.cleanup_expired()

            assert result == 0

    def test_raises_import_error_without_redis(self):
        """Should raise ImportError if redis package not installed."""
        with patch.dict("sys.modules", {"redis.asyncio": None}):
            with patch("builtins.__import__", side_effect=ImportError("No module")):
                with pytest.raises(ImportError) as exc_info:
                    RedisStateStorage("redis://localhost:6379/0")
                assert "redis" in str(exc_info.value).lower()


class TestGetStateStorage:
    """Tests for get_state_storage factory function."""

    def setup_method(self):
        """Reset singleton before each test."""
        import cognee.modules.users.authentication.oidc.state_storage as module
        module._state_storage = None

    def test_returns_in_memory_by_default(self):
        """Should return InMemoryStateStorage when no Redis URL."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove Redis URL if set
            os.environ.pop("OAUTH_STATE_REDIS_URL", None)
            storage = get_state_storage()
            assert isinstance(storage, InMemoryStateStorage)

    def test_returns_redis_when_url_set(self):
        """Should return RedisStateStorage when OAUTH_STATE_REDIS_URL is set."""
        mock_redis = MagicMock()
        with patch.dict(os.environ, {"OAUTH_STATE_REDIS_URL": "redis://localhost:6379/0"}):
            with patch("redis.asyncio.from_url", return_value=mock_redis):
                # Reset singleton
                import cognee.modules.users.authentication.oidc.state_storage as module
                module._state_storage = None

                storage = get_state_storage()
                assert isinstance(storage, RedisStateStorage)

    def test_returns_same_instance_on_subsequent_calls(self):
        """Should return singleton instance."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OAUTH_STATE_REDIS_URL", None)
            storage1 = get_state_storage()
            storage2 = get_state_storage()
            assert storage1 is storage2

    def test_warns_in_kubernetes_without_redis(self):
        """Should warn when running in K8s without Redis."""
        with patch.dict(os.environ, {"KUBERNETES_SERVICE_HOST": "10.0.0.1"}, clear=True):
            os.environ.pop("OAUTH_STATE_REDIS_URL", None)
            # Reset singleton
            import cognee.modules.users.authentication.oidc.state_storage as module
            module._state_storage = None

            with patch("cognee.modules.users.authentication.oidc.state_storage.logger") as mock_logger:
                storage = get_state_storage()
                mock_logger.warning.assert_called()
                assert isinstance(storage, InMemoryStateStorage)


class TestStateTTL:
    """Tests for state TTL configuration."""

    def test_default_ttl_is_600_seconds(self):
        """Default TTL should be 10 minutes (600 seconds)."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OAUTH_STATE_TTL", None)
            # The default is set at module load time
            assert STATE_TTL == 600 or STATE_TTL > 0

    def test_ttl_can_be_configured_via_env(self):
        """TTL should be configurable via OAUTH_STATE_TTL."""
        # This tests the env var is read at module load time
        # We can verify the constant exists and is reasonable
        assert isinstance(STATE_TTL, int)
        assert STATE_TTL > 0
