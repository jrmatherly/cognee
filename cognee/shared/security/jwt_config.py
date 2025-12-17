"""JWT secret configuration with fail-fast validation.

This module provides secure JWT secret handling that:
- Fails fast if secret is not configured
- Validates minimum secret length
- Detects common weak/default secrets
- Provides generation instructions for operators
"""

import os
from functools import lru_cache
from typing import Optional

from cognee.shared.logging_utils import get_logger

logger = get_logger("jwt_config")

# Minimum secure secret length (32 characters = 256 bits)
MIN_SECRET_LENGTH = 32

# Common weak secrets to detect and reject
WEAK_SECRETS = frozenset({
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
})


class JWTSecretError(RuntimeError):
    """Raised when JWT secret configuration is invalid."""

    pass


def validate_jwt_secret(secret: Optional[str], env_var_name: str = "FASTAPI_USERS_JWT_SECRET") -> str:
    """Validate a JWT secret meets security requirements.

    Args:
        secret: The secret value to validate
        env_var_name: Environment variable name for error messages

    Returns:
        The validated secret string

    Raises:
        JWTSecretError: If secret is missing, too short, or weak
    """
    if not secret:
        raise JWTSecretError(
            f"{env_var_name} environment variable is required. "
            f'Generate a secure secret with: python -c "import secrets; print(secrets.token_urlsafe(64))"'
        )

    if len(secret) < MIN_SECRET_LENGTH:
        raise JWTSecretError(
            f"{env_var_name} must be at least {MIN_SECRET_LENGTH} characters. "
            f"Current length: {len(secret)}. "
            f'Generate a secure secret with: python -c "import secrets; print(secrets.token_urlsafe(64))"'
        )

    # Check for known weak secrets (case-insensitive)
    if secret.lower() in WEAK_SECRETS:
        raise JWTSecretError(
            f"{env_var_name} contains a known weak/default value. "
            f'Generate a secure secret with: python -c "import secrets; print(secrets.token_urlsafe(64))"'
        )

    return secret


@lru_cache
def get_jwt_secret() -> str:
    """Get validated JWT secret from environment.

    This function is cached to avoid repeated validation.

    Returns:
        Validated JWT secret string

    Raises:
        JWTSecretError: If secret is not properly configured
    """
    secret = os.getenv("FASTAPI_USERS_JWT_SECRET")
    return validate_jwt_secret(secret)


@lru_cache
def get_reset_password_token_secret() -> str:
    """Get validated reset password token secret."""
    secret = os.getenv("FASTAPI_USERS_RESET_PASSWORD_TOKEN_SECRET")
    return validate_jwt_secret(secret, "FASTAPI_USERS_RESET_PASSWORD_TOKEN_SECRET")


@lru_cache
def get_verification_token_secret() -> str:
    """Get validated verification token secret."""
    secret = os.getenv("FASTAPI_USERS_VERIFICATION_TOKEN_SECRET")
    return validate_jwt_secret(secret, "FASTAPI_USERS_VERIFICATION_TOKEN_SECRET")
