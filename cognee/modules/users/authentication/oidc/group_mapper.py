"""Group-to-role mapping for OIDC authentication.

This module provides functionality to:
- Map OIDC groups (from Keycloak/EntraID) to Cognee roles
- Synchronize user group memberships from OIDC claims
- Sync user role assignments based on group mappings
"""

from typing import Dict, List, Optional, Set
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cognee.modules.users.models import User, Role, Tenant, Group, UserGroup
from cognee.shared.logging_utils import get_logger
from .oidc_config import get_oidc_config

logger = get_logger("group_mapper")


class GroupMapper:
    """Maps OIDC groups to Cognee roles and syncs user memberships.

    The mapper supports two modes controlled by config:
    - additive: Only adds roles from current OIDC groups (default)
    - sync: Removes roles not present in current OIDC groups

    Example group mapping configuration:
        {
            "IT-Admins": ["admin", "editor"],
            "Data-Scientists": ["editor", "reader"],
            "Viewers": ["reader"]
        }
    """

    def __init__(self, session: AsyncSession, tenant: Tenant):
        """Initialize the group mapper.

        Args:
            session: Database session for queries
            tenant: Tenant context for role/group operations
        """
        self.session = session
        self.tenant = tenant
        self.config = get_oidc_config()
        self._group_mappings: Optional[Dict[str, List[str]]] = None

    @property
    def group_mappings(self) -> Dict[str, List[str]]:
        """Lazy-load group mappings from config."""
        if self._group_mappings is None:
            self._group_mappings = self.config.load_group_mappings()
        return self._group_mappings

    async def sync_user_groups_and_roles(
        self,
        user: User,
        oidc_groups: List[str],
    ) -> tuple[List[Group], List[Role]]:
        """Synchronize user's groups and roles from OIDC claims.

        Args:
            user: User to update
            oidc_groups: List of group names from OIDC token

        Returns:
            Tuple of (assigned_groups, assigned_roles)
        """
        # Sync groups
        assigned_groups = await self._sync_user_groups(user, oidc_groups)

        # Map groups to roles and sync
        assigned_roles = await self._sync_user_roles(user, oidc_groups)

        return assigned_groups, assigned_roles

    async def _sync_user_groups(
        self,
        user: User,
        oidc_groups: List[str],
    ) -> List[Group]:
        """Sync user's group memberships from OIDC claims.

        Creates groups that don't exist and updates user's memberships.

        Args:
            user: User to update
            oidc_groups: List of group names from OIDC

        Returns:
            List of groups user is now a member of
        """
        assigned_groups = []

        for group_name in oidc_groups:
            # Get or create group
            group = await self._get_or_create_group(group_name)
            assigned_groups.append(group)

            # Check if user is already in group
            if group not in user.groups:
                user.groups.append(group)
                logger.info(f"Added user {user.email} to group {group_name}")

        # Optionally remove from groups not in OIDC claims
        if self.config.oidc_role_sync_mode == "sync":
            groups_to_remove = [
                g for g in user.groups if g.name not in oidc_groups
            ]
            for group in groups_to_remove:
                user.groups.remove(group)
                logger.info(f"Removed user {user.email} from group {group.name}")

        return assigned_groups

    async def _sync_user_roles(
        self,
        user: User,
        oidc_groups: List[str],
    ) -> List[Role]:
        """Sync user's roles based on group-to-role mappings.

        Args:
            user: User to update
            oidc_groups: List of group names from OIDC

        Returns:
            List of roles user is assigned to
        """
        # Map groups to role names
        target_role_names = self._map_groups_to_role_names(oidc_groups)

        # Apply default role if no mappings matched
        if not target_role_names:
            target_role_names = {self.config.oidc_default_role}

        assigned_roles = []

        for role_name in target_role_names:
            role = await self._get_or_create_role(role_name)
            assigned_roles.append(role)

            # Add role if not already assigned
            if role not in user.roles:
                user.roles.append(role)
                logger.info(f"Assigned role {role_name} to user {user.email}")

        # Optionally remove roles not mapped from current groups
        if self.config.oidc_remove_unmatched_roles:
            roles_to_remove = [
                r for r in user.roles if r.name not in target_role_names
            ]
            for role in roles_to_remove:
                user.roles.remove(role)
                logger.info(f"Removed role {role.name} from user {user.email}")

        return assigned_roles

    def _map_groups_to_role_names(self, oidc_groups: List[str]) -> Set[str]:
        """Map OIDC groups to Cognee role names.

        Args:
            oidc_groups: List of OIDC group names

        Returns:
            Set of Cognee role names to assign
        """
        role_names = set()

        for group in oidc_groups:
            if group in self.group_mappings:
                role_names.update(self.group_mappings[group])

        return role_names

    async def _get_or_create_group(self, group_name: str) -> Group:
        """Get existing group or create new one.

        Uses savepoints to handle race conditions without invalidating
        the outer transaction.

        Args:
            group_name: Name of the group

        Returns:
            Group model instance
        """
        from sqlalchemy.exc import IntegrityError

        # Try to find existing group in tenant
        stmt = select(Group).where(
            Group.tenant_id == self.tenant.id,
            Group.name == group_name,
        )
        result = await self.session.execute(stmt)
        group = result.scalar_one_or_none()

        if group is not None:
            return group

        # Create new group using savepoint for race condition safety
        try:
            # begin_nested() creates a SAVEPOINT
            async with self.session.begin_nested():
                from cognee.modules.users.models.Principal import Principal

                # Create principal entry first
                principal = Principal(type="group")
                self.session.add(principal)
                await self.session.flush()

                # Create group
                group = Group(
                    id=principal.id,
                    name=group_name,
                    external_id=group_name,  # Use name as external_id for OIDC groups
                    tenant_id=self.tenant.id,
                )
                self.session.add(group)
                # Savepoint is committed when context exits successfully

            logger.info(f"Created OIDC group: {group_name}")
            return group

        except IntegrityError:
            # Savepoint rolled back automatically, outer transaction intact
            # Another process created the group concurrently, fetch it
            result = await self.session.execute(stmt)
            group = result.scalar_one_or_none()

            if group is None:
                raise RuntimeError(f"Failed to create or retrieve group: {group_name}")

            logger.debug(f"Group {group_name} created by concurrent process")
            return group

    async def _get_or_create_role(self, role_name: str) -> Role:
        """Get existing role or create new one.

        Uses savepoints to handle race conditions without invalidating
        the outer transaction.

        Args:
            role_name: Name of the role

        Returns:
            Role model instance
        """
        from sqlalchemy.exc import IntegrityError

        # Try to find existing role in tenant
        stmt = select(Role).where(
            Role.tenant_id == self.tenant.id,
            Role.name == role_name,
        )
        result = await self.session.execute(stmt)
        role = result.scalar_one_or_none()

        if role is not None:
            return role

        # Create new role using savepoint for race condition safety
        try:
            async with self.session.begin_nested():
                from cognee.modules.users.models.Principal import Principal

                # Create principal entry first
                principal = Principal(type="role")
                self.session.add(principal)
                await self.session.flush()

                # Create role
                role = Role(
                    id=principal.id,
                    name=role_name,
                    tenant_id=self.tenant.id,
                )
                self.session.add(role)

            logger.info(f"Created role: {role_name}")
            return role

        except IntegrityError:
            # Savepoint rolled back automatically, outer transaction intact
            result = await self.session.execute(stmt)
            role = result.scalar_one_or_none()

            if role is None:
                raise RuntimeError(f"Failed to create or retrieve role: {role_name}")

            logger.debug(f"Role {role_name} created by concurrent process")
            return role


async def get_user_effective_groups(
    session: AsyncSession,
    user_id: UUID,
) -> List[Group]:
    """Get all groups a user belongs to.

    Args:
        session: Database session
        user_id: User's UUID

    Returns:
        List of Group models the user is a member of
    """
    stmt = select(User).where(User.id == user_id).options(selectinload(User.groups))
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        return []

    return list(user.groups)
