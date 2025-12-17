"""OIDC/Keycloak authentication module for Cognee.

This module provides OpenID Connect (OIDC) authentication support with:
- Keycloak integration (federated with Microsoft EntraID, Google, GitHub)
- Just-In-Time (JIT) user provisioning
- Group-to-role mapping from OIDC claims
- Dataset sharing via group principals

Configuration via environment variables (see oidc_config.py).
"""

from .oidc_config import get_oidc_config, OIDCConfig
from .oidc_auth_backend import get_oidc_auth_backend

__all__ = [
    "get_oidc_config",
    "OIDCConfig",
    "get_oidc_auth_backend",
]
