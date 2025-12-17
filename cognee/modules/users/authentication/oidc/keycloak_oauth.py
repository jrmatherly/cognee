"""Keycloak OAuth client with group claim extraction.

This module provides a custom OAuth client for Keycloak that:
- Uses OIDC discovery to configure endpoints automatically
- Extracts group claims from the ID token/userinfo
- Works with Keycloak federated with Microsoft EntraID
"""

from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

import httpx
from httpx_oauth.clients.openid import OpenID
from httpx_oauth.oauth2 import OAuth2Token

from cognee.shared.logging_utils import get_logger
from .oidc_config import get_oidc_config

logger = get_logger("keycloak_oauth")


class KeycloakOAuth(OpenID):
    """Keycloak-specific OAuth client with group claim extraction.

    This client extends httpx-oauth's OpenID client to:
    - Store full userinfo claims for group extraction
    - Handle Keycloak-specific token response formats
    - Support OIDC discovery via .well-known endpoint
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        openid_configuration_endpoint: str,
        name: str = "keycloak",
        base_scopes: Optional[List[str]] = None,
    ):
        """Initialize Keycloak OAuth client.

        Args:
            client_id: OAuth client ID from Keycloak
            client_secret: OAuth client secret from Keycloak
            openid_configuration_endpoint: URL to .well-known/openid-configuration
            name: OAuth provider name for routing
            base_scopes: Default scopes to request
        """
        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            openid_configuration_endpoint=openid_configuration_endpoint,
            name=name,
            base_scopes=base_scopes or ["openid", "profile", "email"],
        )
        self._last_claims: Dict[str, Any] = {}
        self._last_token: Optional[OAuth2Token] = None

    async def get_id_email(self, token: str) -> Tuple[str, str]:
        """Get user ID and email from OAuth token.

        This method fetches the userinfo and stores all claims
        for later group extraction.

        Args:
            token: Access token from OAuth flow

        Returns:
            Tuple of (subject_id, email)

        Raises:
            httpx.HTTPStatusError: If userinfo request fails
            ValueError: If required claims are missing
        """
        config = get_oidc_config()

        async with httpx.AsyncClient(verify=config.oidc_verify_ssl) as client:
            response = await client.get(
                self.userinfo_endpoint,
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            userinfo = response.json()

        # Store full claims for group extraction
        self._last_claims = userinfo

        # Extract required fields
        account_id = userinfo.get("sub")
        account_email = userinfo.get(config.oidc_email_claim, userinfo.get("email"))

        if not account_id:
            raise ValueError("Missing 'sub' claim in OIDC userinfo")
        if not account_email:
            raise ValueError(f"Missing email claim in OIDC userinfo")

        logger.debug(f"OIDC userinfo retrieved for: {account_email}")
        return str(account_id), str(account_email)

    def get_last_claims(self) -> Dict[str, Any]:
        """Get the last retrieved userinfo claims.

        Returns:
            Dict of all claims from the most recent userinfo request
        """
        return self._last_claims.copy()

    def get_groups_from_claims(self) -> List[str]:
        """Extract group memberships from stored claims.

        Returns:
            List of group names/IDs from the OIDC claims
        """
        config = get_oidc_config()
        groups = self._last_claims.get(config.oidc_group_claim, [])

        # Handle string or list formats
        if isinstance(groups, str):
            groups = [groups]
        elif not isinstance(groups, list):
            logger.warning(f"Unexpected groups claim type: {type(groups)}")
            groups = []

        return groups

    def set_last_token(self, token: OAuth2Token) -> None:
        """Store the last OAuth token for reference.

        Args:
            token: OAuth2Token from the authorization flow
        """
        self._last_token = token

    def get_last_token(self) -> Optional[OAuth2Token]:
        """Get the last OAuth token.

        Returns:
            The most recent OAuth2Token, or None
        """
        return self._last_token


@lru_cache
def get_keycloak_oauth_client() -> KeycloakOAuth:
    """Factory function for Keycloak OAuth client.

    Returns:
        Configured KeycloakOAuth client

    Raises:
        ValueError: If OIDC is not enabled or configured
    """
    config = get_oidc_config()

    if not config.oidc_enabled:
        raise ValueError("OIDC authentication is not enabled")

    if not config.oidc_server_metadata_url:
        raise ValueError("OIDC_SERVER_METADATA_URL is required")

    return KeycloakOAuth(
        client_id=config.oidc_client_id,
        client_secret=config.oidc_client_secret,
        openid_configuration_endpoint=config.oidc_server_metadata_url,
        name=config.oidc_provider_name,
        base_scopes=config.get_scopes_list(),
    )
