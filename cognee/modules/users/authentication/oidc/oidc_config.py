"""OIDC/Keycloak configuration module.

This module provides configuration for OIDC authentication including:
- Keycloak server connection settings
- Group-to-role mapping configuration
- JIT provisioning settings

Configuration is loaded from environment variables prefixed with OIDC_.
"""

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cognee.shared.logging_utils import get_logger

logger = get_logger("oidc_config")


class OIDCConfig(BaseSettings):
    """OIDC authentication configuration.

    All settings can be configured via environment variables with OIDC_ prefix.

    Example:
        OIDC_ENABLED=true
        OIDC_CLIENT_ID=cognee
        OIDC_CLIENT_SECRET=<secret>
        OIDC_SERVER_METADATA_URL=https://keycloak.example.com/realms/cognee/.well-known/openid-configuration
    """

    # Core OIDC Settings
    oidc_enabled: bool = False
    oidc_provider_name: str = "keycloak"
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_server_metadata_url: str = ""

    # OAuth URLs (computed from metadata if not provided)
    oidc_authorization_endpoint: Optional[str] = None
    oidc_token_endpoint: Optional[str] = None
    oidc_userinfo_endpoint: Optional[str] = None
    oidc_jwks_uri: Optional[str] = None

    # Scopes and claims
    oidc_scopes: str = "openid profile email"
    oidc_group_claim: str = "groups"
    oidc_email_claim: str = "email"
    oidc_name_claim: str = "name"

    # Callback configuration
    oidc_redirect_uri: str = ""
    oidc_base_url: str = "http://localhost:8000"

    # Group-to-Role Mapping
    oidc_group_mapping_file: str = ""
    oidc_group_mapping_json: str = "{}"
    oidc_default_role: str = "viewer"

    # JIT Provisioning Settings
    oidc_auto_provision_users: bool = True
    oidc_auto_assign_tenant: str = ""
    oidc_create_user_tenant: bool = True
    oidc_tenant_from_email_domain: bool = True

    # Role Sync Settings
    oidc_role_sync_mode: str = "additive"
    oidc_remove_unmatched_roles: bool = False

    # SSL/TLS Settings
    oidc_verify_ssl: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )

    @model_validator(mode="after")
    def compute_redirect_uri(self) -> "OIDCConfig":
        """Compute redirect URI if not provided."""
        if not self.oidc_redirect_uri and self.oidc_base_url:
            self.oidc_redirect_uri = (
                f"{self.oidc_base_url.rstrip('/')}/api/v1/auth/oidc/callback"
            )
        return self

    @model_validator(mode="after")
    def validate_enabled_config(self) -> "OIDCConfig":
        """Validate required fields when OIDC is enabled.

        Raises:
            ValueError: If OIDC is enabled but required fields are missing
        """
        if self.oidc_enabled:
            errors = []

            if not self.oidc_client_id:
                errors.append("OIDC_CLIENT_ID is required when OIDC is enabled")

            if not self.oidc_client_secret:
                errors.append("OIDC_CLIENT_SECRET is required when OIDC is enabled")

            if not self.oidc_server_metadata_url:
                errors.append("OIDC_SERVER_METADATA_URL is required when OIDC is enabled")

            if errors:
                raise ValueError(
                    "OIDC configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
                )

        return self

    def load_group_mappings(self) -> Dict[str, List[str]]:
        """Load group-to-role mappings from file or JSON string.

        Returns:
            Dict mapping OIDC group names to lists of Cognee role names.
            Example: {"IT-Admins": ["admin"], "Data-Scientists": ["editor", "reader"]}
        """
        mappings = {}

        # Try loading from file first
        if self.oidc_group_mapping_file:
            file_path = Path(self.oidc_group_mapping_file)
            if file_path.exists():
                try:
                    with open(file_path, "r") as f:
                        mappings = json.load(f)
                    logger.info(f"Loaded group mappings from {file_path}")
                except (json.JSONDecodeError, IOError) as e:
                    logger.error(f"Failed to load group mappings from file: {e}")
            else:
                logger.warning(f"Group mapping file not found: {file_path}")

        # Fall back to JSON string from env var
        if not mappings and self.oidc_group_mapping_json:
            try:
                mappings = json.loads(self.oidc_group_mapping_json)
                logger.info("Loaded group mappings from OIDC_GROUP_MAPPING_JSON")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse OIDC_GROUP_MAPPING_JSON: {e}")

        # Remove any comment entries (keys starting with _)
        mappings = {k: v for k, v in mappings.items() if not k.startswith("_")}

        return mappings

    def get_scopes_list(self) -> List[str]:
        """Parse scopes string into list."""
        return [s.strip() for s in self.oidc_scopes.split() if s.strip()]


@lru_cache
def get_oidc_config() -> OIDCConfig:
    """Factory function for OIDC configuration (singleton)."""
    return OIDCConfig()
