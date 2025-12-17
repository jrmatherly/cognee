"""OIDC authentication router for Keycloak/EntraID integration.

This module provides the OAuth endpoints for OIDC authentication:
- /authorize: Initiate OAuth flow (redirect to Keycloak)
- /callback: Handle OAuth callback and issue JWT
- /me: Get current user info (includes groups)

The router integrates with FastAPI-Users for token management.
"""

import os
import secrets
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from cognee.modules.users.get_fastapi_users import get_fastapi_users
from cognee.modules.users.models import User
from cognee.modules.users.methods import get_authenticated_user
from cognee.modules.users.authentication.oidc.oidc_config import get_oidc_config
from cognee.modules.users.authentication.oidc.keycloak_oauth import get_keycloak_oauth_client
from cognee.shared.logging_utils import get_logger
from cognee.shared.security import get_jwt_secret
from cognee.shared.rate_limiting import auth_oauth_rate_limiter, auth_callback_rate_limiter
from cognee.modules.users.authentication.oidc.state_storage import get_state_storage, STATE_TTL

logger = get_logger("oidc_router")


class OIDCTokenResponse(BaseModel):
    """Response model for OIDC token endpoint."""

    access_token: str
    token_type: str = "bearer"
    expires_in: Optional[int] = 3600


class OIDCUserResponse(BaseModel):
    """Response model for OIDC user info endpoint."""

    email: str
    groups: list[str] = []
    roles: list[str] = []
    tenant: Optional[str] = None


def get_oidc_router() -> APIRouter:
    """Create OIDC OAuth router.

    Returns:
        APIRouter with OIDC endpoints, or empty router if OIDC is disabled
    """
    router = APIRouter(tags=["oidc"])
    config = get_oidc_config()

    if not config.oidc_enabled:
        logger.debug("OIDC disabled, returning empty router")

        @router.get("/status")
        async def oidc_status():
            return {"enabled": False, "message": "OIDC authentication is not configured"}

        return router

    @router.get("/status")
    async def oidc_status():
        """Check OIDC configuration status."""
        return {
            "enabled": True,
            "provider": config.oidc_provider_name,
            "login_url": "/api/v1/auth/oidc/authorize",
        }

    @router.get("/authorize")
    async def oidc_authorize(
        request: Request,
        redirect_uri: Optional[str] = Query(
            None, description="URL to redirect after login"
        ),
    ):
        """Initiate OIDC authorization flow.

        Redirects the user to the Keycloak login page. After successful
        authentication, Keycloak will redirect back to the callback endpoint.

        Args:
            redirect_uri: Optional URL to redirect after successful login

        Returns:
            RedirectResponse to Keycloak authorization endpoint
        """
        # Apply rate limiting to prevent abuse
        async with auth_oauth_rate_limiter():
            try:
                # Get state storage (Redis or in-memory)
                state_storage = get_state_storage()

                # Clean up expired states periodically
                await state_storage.cleanup_expired()

                oauth_client = get_keycloak_oauth_client()

                # Generate state for CSRF protection
                state = secrets.token_urlsafe(32)
                await state_storage.set(state, redirect_uri or config.oidc_redirect_uri)

                # Get authorization URL
                callback_url = config.oidc_redirect_uri
                auth_url = await oauth_client.get_authorization_url(
                    redirect_uri=callback_url,
                    state=state,
                    scope=config.get_scopes_list(),
                )

                logger.info(f"Redirecting to OIDC provider: {auth_url[:80]}...")
                return RedirectResponse(auth_url)

            except Exception as e:
                logger.error(f"OIDC authorize failed: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to initiate OIDC login: {str(e)}",
                )

    @router.get("/callback")
    async def oidc_callback(
        request: Request,
        code: str = Query(..., description="Authorization code from OIDC provider"),
        state: str = Query(..., description="State parameter for CSRF protection"),
        error: Optional[str] = Query(None, description="Error from OIDC provider"),
        error_description: Optional[str] = Query(None, description="Error description"),
    ):
        """Handle OIDC callback after successful authentication.

        This endpoint:
        1. Validates the state parameter
        2. Exchanges the authorization code for tokens
        3. Fetches user info and groups from Keycloak
        4. Creates or updates the user (JIT provisioning)
        5. Issues a Cognee JWT token

        Args:
            code: Authorization code from Keycloak
            state: CSRF state parameter
            error: Error code if authentication failed
            error_description: Error description if authentication failed

        Returns:
            OIDCTokenResponse with access token
        """
        # Apply rate limiting to prevent abuse
        async with auth_callback_rate_limiter():
            # Check for errors from OIDC provider
            if error:
                logger.error(f"OIDC error: {error} - {error_description}")
                raise HTTPException(
                    status_code=400,
                    detail=f"OIDC authentication failed: {error_description or error}",
                )

            # Get state storage and validate state
            state_storage = get_state_storage()
            state_data = await state_storage.get_and_delete(state)

            if state_data is None:
                logger.error("Invalid or expired OAuth state parameter")
                raise HTTPException(
                    status_code=400,
                    detail="Invalid or expired state parameter. Please try logging in again.",
                )

            original_redirect, state_timestamp = state_data

            try:
                oauth_client = get_keycloak_oauth_client()

                # Exchange code for access token
                callback_url = config.oidc_redirect_uri
                token = await oauth_client.get_access_token(code, callback_url)

                # Store token and fetch user info
                oauth_client.set_last_token(token)
                access_token = token.get("access_token")

                if not access_token:
                    raise HTTPException(status_code=400, detail="No access token received")

                # Get user info and groups
                account_id, account_email = await oauth_client.get_id_email(access_token)
                oidc_groups = oauth_client.get_groups_from_claims()
                oidc_claims = oauth_client.get_last_claims()

                # Store claims in request state for UserManager
                request.state.oidc_claims = oidc_claims

                # Import here to avoid circular imports
                from cognee.modules.users.authentication.oidc.oidc_user_manager import (
                    OIDCUserManager,
                )
                from cognee.modules.users.get_user_db import get_user_db_context
                from cognee.infrastructure.databases.relational import get_relational_engine

                db_engine = get_relational_engine()
                async with db_engine.get_async_session() as session:
                    async with get_user_db_context(session) as user_db:
                        user_manager = OIDCUserManager(user_db)

                        # Handle OAuth callback (JIT provisioning + group sync)
                        user = await user_manager.oauth_callback(
                            oauth_name=config.oidc_provider_name,
                            access_token=access_token,
                            account_id=account_id,
                            account_email=account_email,
                            request=request,
                            associate_by_email=True,
                            is_verified_by_default=True,
                        )

                # Generate Cognee JWT token
                from cognee.modules.users.authentication.default.default_jwt_strategy import (
                    DefaultJWTStrategy,
                )

                jwt_secret = get_jwt_secret()
                jwt_strategy = DefaultJWTStrategy(jwt_secret, lifetime_seconds=3600)
                cognee_token = await jwt_strategy.write_token(user)

                logger.info(f"OIDC login successful for {account_email}")

                # If we have an original redirect, redirect there with token in fragment
                # Using fragment (#) instead of query (?) prevents token from being:
                # - Logged by web servers
                # - Visible in browser history
                # - Sent in Referer headers
                if original_redirect and original_redirect != config.oidc_redirect_uri:
                    redirect_url = f"{original_redirect}#token={cognee_token}"
                    return RedirectResponse(redirect_url, status_code=302)

                return OIDCTokenResponse(
                    access_token=cognee_token,
                    token_type="bearer",
                    expires_in=3600,
                )

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"OIDC callback failed: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"OIDC authentication failed: {str(e)}",
                )

    @router.get("/me", response_model=OIDCUserResponse)
    async def oidc_me(user: User = Depends(get_authenticated_user)):
        """Get current user info including OIDC groups and roles.

        Returns:
            User info with groups, roles, and tenant
        """
        # Safely access tenant name
        tenant_name = None
        if user.tenants and len(user.tenants) > 0:
            tenant_name = user.tenants[0].name

        return OIDCUserResponse(
            email=user.email,
            groups=[g.name for g in user.groups] if user.groups else [],
            roles=[r.name for r in user.roles] if user.roles else [],
            tenant=tenant_name,
        )

    @router.post("/logout")
    async def oidc_logout(user: User = Depends(get_authenticated_user)):
        """Logout the current user.

        Note: This invalidates the Cognee JWT but does not log out
        from Keycloak. For full SSO logout, redirect to Keycloak's
        logout endpoint.

        Returns:
            Logout confirmation message
        """
        logger.info(f"User {user.email} logged out")
        return {"message": "Logged out successfully"}

    return router
