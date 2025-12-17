"""OIDC authentication backend for FastAPI-Users.

This module provides the authentication backend that integrates
OIDC/Keycloak authentication with FastAPI-Users. It reuses the
existing JWT strategy for token management after OIDC authentication.
"""

from functools import lru_cache
from typing import Optional

from fastapi_users.authentication import AuthenticationBackend
from fastapi_users.authentication.transport import BearerTransport

from cognee.modules.users.authentication.default.default_jwt_strategy import (
    DefaultJWTStrategy,
)
from cognee.shared.logging_utils import get_logger
from cognee.shared.security import get_jwt_secret
from .oidc_config import get_oidc_config

logger = get_logger("oidc_auth_backend")


class OIDCBearerTransport(BearerTransport):
    """Bearer transport for OIDC tokens.

    This transport handles Bearer token authentication for users
    who authenticated via OIDC. After OIDC login, users receive
    a JWT that can be used for subsequent API requests.
    """

    def __init__(self):
        super().__init__(tokenUrl="api/v1/auth/oidc/token")

    @property
    def name(self) -> str:
        return "oidc_bearer"


@lru_cache
def get_oidc_auth_backend() -> Optional[AuthenticationBackend]:
    """Create OIDC authentication backend.

    Returns configured backend if OIDC is enabled, None otherwise.
    The backend uses Bearer transport with JWT strategy, allowing
    tokens issued after OIDC login to be used for API authentication.

    Returns:
        AuthenticationBackend or None if OIDC is disabled
    """
    config = get_oidc_config()

    if not config.oidc_enabled:
        logger.debug("OIDC authentication is disabled")
        return None

    transport = OIDCBearerTransport()

    def get_jwt_strategy() -> DefaultJWTStrategy:
        secret = get_jwt_secret()
        return DefaultJWTStrategy(secret, lifetime_seconds=3600)

    backend = AuthenticationBackend(
        name="oidc",
        transport=transport,
        get_strategy=get_jwt_strategy,
    )

    logger.info("OIDC authentication backend configured")
    return backend
