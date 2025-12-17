"""OIDC-extended UserManager for JIT provisioning and group sync.

This module provides an extended UserManager that handles:
- Just-In-Time (JIT) user provisioning on first OIDC login
- Automatic tenant assignment for new users
- Group membership synchronization from OIDC claims
- Role assignment based on group-to-role mappings
"""

from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import Request
from sqlalchemy import select, insert
from sqlalchemy.exc import IntegrityError

from cognee.modules.users.get_user_manager import UserManager
from cognee.modules.users.models import User, Tenant, UserTenant
from cognee.modules.users.models.User import UserCreate
from cognee.infrastructure.databases.relational import get_relational_engine
from cognee.shared.logging_utils import get_logger
from .oidc_config import get_oidc_config
from .group_mapper import GroupMapper

logger = get_logger("oidc_user_manager")


class OIDCUserManager(UserManager):
    """Extended UserManager with OIDC JIT provisioning and group sync.

    This manager extends the base UserManager to handle OIDC-specific
    authentication flows including:
    - Creating users on first OAuth login
    - Assigning users to tenants based on configuration
    - Synchronizing group memberships from OIDC claims
    - Mapping OIDC groups to Cognee roles
    """

    async def oauth_callback(
        self,
        oauth_name: str,
        access_token: str,
        account_id: str,
        account_email: str,
        expires_at: Optional[int] = None,
        refresh_token: Optional[str] = None,
        request: Optional[Request] = None,
        *,
        associate_by_email: bool = False,
        is_verified_by_default: bool = True,
    ) -> User:
        """Handle OAuth callback with OIDC-specific JIT provisioning.

        This method is called by FastAPI-Users after successful OAuth login.
        It handles user provisioning, tenant assignment, and group sync.

        Args:
            oauth_name: Name of the OAuth provider
            access_token: OAuth access token
            account_id: User's ID from the OAuth provider
            account_email: User's email from the OAuth provider
            expires_at: Token expiration timestamp
            refresh_token: OAuth refresh token
            request: FastAPI request object
            associate_by_email: Whether to associate by email
            is_verified_by_default: Whether new users are verified

        Returns:
            User object (new or existing)
        """
        config = get_oidc_config()

        # Check if this is an OIDC provider we handle specially
        if not config.oidc_enabled or oauth_name != config.oidc_provider_name:
            # Fall back to default behavior for non-OIDC providers
            return await super().oauth_callback(
                oauth_name,
                access_token,
                account_id,
                account_email,
                expires_at,
                refresh_token,
                request,
                associate_by_email=associate_by_email,
                is_verified_by_default=is_verified_by_default,
            )

        # Extract OIDC claims from request state
        oidc_claims = self._extract_oidc_claims(request)
        oidc_groups = oidc_claims.get(config.oidc_group_claim, [])

        logger.info(f"OIDC callback for {account_email} with {len(oidc_groups)} groups")

        # Get or create user
        user = await self._get_or_provision_user(
            account_email=account_email,
            account_id=account_id,
            oidc_claims=oidc_claims,
            is_verified=is_verified_by_default,
        )

        # Get or create tenant and sync groups/roles
        await self._sync_user_tenant_and_groups(user, oidc_groups)

        logger.info(f"OIDC login successful for {account_email}")
        return user

    async def _get_or_provision_user(
        self,
        account_email: str,
        account_id: str,
        oidc_claims: Dict[str, Any],
        is_verified: bool = True,
    ) -> User:
        """Get existing user or provision new one from OIDC claims.

        Args:
            account_email: User's email address
            account_id: OIDC subject ID
            oidc_claims: Full OIDC claims dictionary
            is_verified: Whether user should be marked as verified

        Returns:
            User model instance
        """
        config = get_oidc_config()

        # Try to find existing user by email
        from fastapi_users.exceptions import UserNotExists

        try:
            user = await self.get_by_email(account_email)
            logger.debug(f"Found existing user: {account_email}")
            return user
        except UserNotExists:
            pass  # User doesn't exist, will provision below

        if not config.oidc_auto_provision_users:
            raise Exception(f"User {account_email} not found and auto-provisioning is disabled")

        # Create new user
        logger.info(f"JIT provisioning new user: {account_email}")

        user_create = UserCreate(
            email=account_email,
            password=str(uuid4()),  # Random password (won't be used for OIDC users)
            is_verified=is_verified,
            is_active=True,
            is_superuser=False,
        )

        user = await self.create(user_create)
        logger.info(f"Created user {account_email} with ID {user.id}")

        return user

    async def _sync_user_tenant_and_groups(
        self,
        user: User,
        oidc_groups: List[str],
    ) -> None:
        """Sync user's tenant assignment and group memberships.

        Args:
            user: User to update
            oidc_groups: List of group names from OIDC claims
        """
        db_engine = get_relational_engine()

        async with db_engine.get_async_session() as session:
            # Get or create tenant for user
            tenant = await self._get_or_create_user_tenant(session, user)

            # Sync groups and roles
            if oidc_groups:
                mapper = GroupMapper(session, tenant)
                assigned_groups, assigned_roles = await mapper.sync_user_groups_and_roles(
                    user, oidc_groups
                )
                logger.info(
                    f"Synced {len(assigned_groups)} groups and "
                    f"{len(assigned_roles)} roles for {user.email}"
                )

            await session.commit()

    async def _get_or_create_user_tenant(
        self,
        session,
        user: User,
    ) -> Tenant:
        """Get existing tenant or create new one for user.

        Tenant assignment strategy (in order of precedence):
        1. Use existing tenant if user already has one
        2. Use configured default tenant (OIDC_AUTO_ASSIGN_TENANT)
        3. Create tenant from email domain (OIDC_TENANT_FROM_EMAIL_DOMAIN)
        4. Create user-specific tenant

        Args:
            session: Database session
            user: User model

        Returns:
            Tenant model instance
        """
        config = get_oidc_config()

        # Check if user already has a tenant
        if user.tenant_id:
            stmt = select(Tenant).where(Tenant.id == user.tenant_id)
            result = await session.execute(stmt)
            tenant = result.scalar_one_or_none()
            if tenant:
                return tenant

        # Determine tenant name based on config
        if config.oidc_auto_assign_tenant:
            tenant_name = config.oidc_auto_assign_tenant
        elif config.oidc_tenant_from_email_domain and "@" in user.email:
            domain = user.email.split("@")[1]
            tenant_name = f"org-{domain}"
        else:
            tenant_name = f"user-{user.id}"

        # Try to find existing tenant by name
        stmt = select(Tenant).where(Tenant.name == tenant_name)
        result = await session.execute(stmt)
        tenant = result.scalar_one_or_none()

        if tenant is None:
            # Create new tenant
            from cognee.modules.users.models.Principal import Principal

            # Create principal entry first
            principal = Principal(type="tenant")
            session.add(principal)
            await session.flush()

            tenant = Tenant(
                id=principal.id,
                name=tenant_name,
                owner_id=user.id,
            )
            session.add(tenant)
            await session.flush()
            logger.info(f"Created tenant: {tenant_name}")

        # Update user's active tenant
        user.tenant_id = tenant.id
        session.add(user)
        await session.flush()

        # Add user to tenant association if not already a member
        try:
            stmt = insert(UserTenant).values(user_id=user.id, tenant_id=tenant.id)
            await session.execute(stmt)
            logger.debug(f"Added user {user.email} to tenant {tenant_name}")
        except IntegrityError:
            # User already in tenant, which is fine
            await session.rollback()
            logger.debug(f"User {user.email} already in tenant {tenant_name}")

        return tenant

    def _extract_oidc_claims(self, request: Optional[Request]) -> Dict[str, Any]:
        """Extract OIDC claims from request state.

        Claims are stored in request.state by the OAuth client
        during the callback flow.

        Args:
            request: FastAPI request object

        Returns:
            Dictionary of OIDC claims, or empty dict if not available
        """
        if not request:
            return {}

        # Try to get claims from request state
        if hasattr(request.state, "oidc_claims"):
            return request.state.oidc_claims

        # Try to get from OAuth client (fallback)
        if hasattr(request.state, "oauth_client"):
            oauth_client = request.state.oauth_client
            if hasattr(oauth_client, "get_last_claims"):
                return oauth_client.get_last_claims()

        return {}
