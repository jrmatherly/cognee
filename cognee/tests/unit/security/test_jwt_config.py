"""Tests for JWT configuration security."""

import os
import pytest
from unittest.mock import patch

from cognee.shared.security.jwt_config import (
    validate_jwt_secret,
    get_jwt_secret,
    get_reset_password_token_secret,
    get_verification_token_secret,
    JWTSecretError,
    MIN_SECRET_LENGTH,
)


class TestValidateJwtSecret:
    """Tests for validate_jwt_secret function."""

    def test_valid_secret_passes(self):
        """Valid secrets should be returned unchanged."""
        valid_secret = "a" * 64
        result = validate_jwt_secret(valid_secret)
        assert result == valid_secret

    def test_minimum_length_secret_passes(self):
        """Secret at exactly MIN_SECRET_LENGTH should pass."""
        valid_secret = "a" * MIN_SECRET_LENGTH
        result = validate_jwt_secret(valid_secret)
        assert result == valid_secret

    def test_none_secret_raises(self):
        """None secret should raise JWTSecretError."""
        with pytest.raises(JWTSecretError) as exc_info:
            validate_jwt_secret(None)
        assert "required" in str(exc_info.value).lower()
        assert "FASTAPI_USERS_JWT_SECRET" in str(exc_info.value)

    def test_empty_secret_raises(self):
        """Empty secret should raise JWTSecretError."""
        with pytest.raises(JWTSecretError) as exc_info:
            validate_jwt_secret("")
        assert "required" in str(exc_info.value).lower()

    def test_short_secret_raises(self):
        """Secret shorter than MIN_SECRET_LENGTH should raise."""
        short_secret = "a" * (MIN_SECRET_LENGTH - 1)
        with pytest.raises(JWTSecretError) as exc_info:
            validate_jwt_secret(short_secret)
        assert str(MIN_SECRET_LENGTH) in str(exc_info.value)

    def test_weak_secret_super_secret_raises(self):
        """'super_secret' should be rejected."""
        with pytest.raises(JWTSecretError) as exc_info:
            validate_jwt_secret("super_secret")
        assert "weak" in str(exc_info.value).lower()

    def test_weak_secret_case_insensitive(self):
        """Weak secret check should be case-insensitive."""
        with pytest.raises(JWTSecretError):
            validate_jwt_secret("SUPER_SECRET")

    def test_weak_secrets_list(self):
        """All known weak secrets should be rejected."""
        weak_secrets = [
            "super_secret",
            "secret",
            "changeme",
            "password",
            "jwt_secret",
            "your_secret_here",
            "change_me",
            "development_secret",
            "test_secret",
            "12345678",
        ]
        for weak in weak_secrets:
            with pytest.raises(JWTSecretError):
                validate_jwt_secret(weak)

    def test_custom_env_var_name_in_error(self):
        """Custom env var name should appear in error message."""
        with pytest.raises(JWTSecretError) as exc_info:
            validate_jwt_secret(None, "MY_CUSTOM_SECRET")
        assert "MY_CUSTOM_SECRET" in str(exc_info.value)

    def test_error_includes_generation_command(self):
        """Error messages should include secret generation command."""
        with pytest.raises(JWTSecretError) as exc_info:
            validate_jwt_secret(None)
        assert "secrets.token_urlsafe" in str(exc_info.value)


class TestGetJwtSecret:
    """Tests for get_jwt_secret function."""

    def test_returns_valid_env_secret(self):
        """Should return secret from environment."""
        valid_secret = "a" * 64
        with patch.dict(os.environ, {"FASTAPI_USERS_JWT_SECRET": valid_secret}, clear=False):
            # Clear cache to force re-evaluation
            get_jwt_secret.cache_clear()
            result = get_jwt_secret()
            assert result == valid_secret

    def test_raises_when_env_not_set(self):
        """Should raise when environment variable not set."""
        env_copy = os.environ.copy()
        env_copy.pop("FASTAPI_USERS_JWT_SECRET", None)
        with patch.dict(os.environ, env_copy, clear=True):
            get_jwt_secret.cache_clear()
            with pytest.raises(JWTSecretError):
                get_jwt_secret()

    def test_caches_result(self):
        """Should cache the validation result."""
        valid_secret = "b" * 64
        with patch.dict(os.environ, {"FASTAPI_USERS_JWT_SECRET": valid_secret}, clear=False):
            get_jwt_secret.cache_clear()
            result1 = get_jwt_secret()
            result2 = get_jwt_secret()
            assert result1 is result2


class TestGetResetPasswordTokenSecret:
    """Tests for get_reset_password_token_secret function."""

    def test_returns_valid_secret(self):
        """Should return secret from environment."""
        valid_secret = "c" * 64
        with patch.dict(
            os.environ,
            {"FASTAPI_USERS_RESET_PASSWORD_TOKEN_SECRET": valid_secret},
            clear=False,
        ):
            get_reset_password_token_secret.cache_clear()
            result = get_reset_password_token_secret()
            assert result == valid_secret

    def test_raises_when_not_set(self):
        """Should raise when environment variable not set."""
        env_copy = os.environ.copy()
        env_copy.pop("FASTAPI_USERS_RESET_PASSWORD_TOKEN_SECRET", None)
        with patch.dict(os.environ, env_copy, clear=True):
            get_reset_password_token_secret.cache_clear()
            with pytest.raises(JWTSecretError) as exc_info:
                get_reset_password_token_secret()
            assert "RESET_PASSWORD" in str(exc_info.value)


class TestGetVerificationTokenSecret:
    """Tests for get_verification_token_secret function."""

    def test_returns_valid_secret(self):
        """Should return secret from environment."""
        valid_secret = "d" * 64
        with patch.dict(
            os.environ,
            {"FASTAPI_USERS_VERIFICATION_TOKEN_SECRET": valid_secret},
            clear=False,
        ):
            get_verification_token_secret.cache_clear()
            result = get_verification_token_secret()
            assert result == valid_secret

    def test_raises_when_not_set(self):
        """Should raise when environment variable not set."""
        env_copy = os.environ.copy()
        env_copy.pop("FASTAPI_USERS_VERIFICATION_TOKEN_SECRET", None)
        with patch.dict(os.environ, env_copy, clear=True):
            get_verification_token_secret.cache_clear()
            with pytest.raises(JWTSecretError) as exc_info:
                get_verification_token_secret()
            assert "VERIFICATION" in str(exc_info.value)
