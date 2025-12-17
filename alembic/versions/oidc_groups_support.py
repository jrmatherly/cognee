"""Add OIDC groups support

Revision ID: oidc_groups_001
Revises: c946955da633
Create Date: 2025-12-16

This migration adds:
- groups table: OIDC groups as principals for group-based ACLs
- user_groups table: Many-to-many relationship between users and groups

Groups inherit from the principals table (polymorphic identity: 'group'),
enabling group-based dataset sharing via the existing ACL system.
"""

from typing import Sequence, Union
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import ProgrammingError


# revision identifiers, used by Alembic.
revision: str = "oidc_groups_001"
down_revision: Union[str, None] = "46a6ce2bd2b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _safe_create_index(index_name: str, table_name: str, columns: list) -> None:
    """Create an index, ignoring 'already exists' errors for concurrent execution.

    This handles the race condition where multiple pods check if an index exists,
    both see it doesn't, and both try to create it simultaneously.
    """
    try:
        op.create_index(index_name, table_name, columns)
    except ProgrammingError as e:
        if "already exists" in str(e).lower():
            # Index was created by another concurrent process, that's fine
            pass
        else:
            raise


def _safe_create_table(table_name: str, *columns, **kwargs) -> None:
    """Create a table, ignoring 'already exists' errors for concurrent execution."""
    try:
        op.create_table(table_name, *columns, **kwargs)
    except ProgrammingError as e:
        if "already exists" in str(e).lower():
            # Table was created by another concurrent process, that's fine
            pass
        else:
            raise


def upgrade() -> None:
    conn = op.get_bind()

    def get_table_names():
        """Get fresh table names from inspector."""
        return sa.inspect(conn).get_table_names()

    def get_index_names(table_name: str) -> set:
        """Get fresh index names for a table, handling case where table doesn't exist."""
        insp = sa.inspect(conn)
        if table_name not in insp.get_table_names():
            return set()
        return {idx["name"] for idx in insp.get_indexes(table_name) if idx.get("name")}

    # Create groups table (inherits from principals via polymorphic identity)
    # Note: Table and indexes may already exist if created by Base.metadata.create_all()
    # in entrypoint.sh before migrations run. We check for existence to be idempotent.
    if "groups" not in get_table_names():
        _safe_create_table(
            "groups",
            sa.Column(
                "id",
                sa.UUID,
                sa.ForeignKey("principals.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("name", sa.String(255), nullable=False, index=True),
            sa.Column("external_id", sa.String(512), nullable=True, index=True),
            sa.Column("description", sa.String(1024), nullable=True),
            sa.Column(
                "tenant_id",
                sa.UUID,
                sa.ForeignKey("tenants.id"),
                nullable=False,
            ),
            # Unique constraints
            sa.UniqueConstraint("tenant_id", "name", name="uq_groups_tenant_name"),
            sa.UniqueConstraint("tenant_id", "external_id", name="uq_groups_tenant_external_id"),
        )

    # Create indexes only if they don't exist (may be created by SQLAlchemy model)
    # Refresh inspector to get current state after potential table creation
    # Note: We use _safe_create_index to handle race conditions where the check
    # passes but another process creates the index before we do.
    existing_indexes = get_index_names("groups")

    if "ix_groups_external_id" not in existing_indexes:
        _safe_create_index("ix_groups_external_id", "groups", ["external_id"])
    if "ix_groups_tenant_id" not in existing_indexes:
        _safe_create_index("ix_groups_tenant_id", "groups", ["tenant_id"])

    # Create user_groups association table
    if "user_groups" not in get_table_names():
        _safe_create_table(
            "user_groups",
            sa.Column(
                "user_id",
                sa.UUID,
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "group_id",
                sa.UUID,
                sa.ForeignKey("groups.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                default=lambda: datetime.now(timezone.utc),
            ),
        )

    # Create indexes only if they don't exist (may be created by SQLAlchemy model)
    # Refresh inspector to get current state after potential table creation
    existing_user_groups_indexes = get_index_names("user_groups")

    if "ix_user_groups_user_id" not in existing_user_groups_indexes:
        _safe_create_index("ix_user_groups_user_id", "user_groups", ["user_id"])
    if "ix_user_groups_group_id" not in existing_user_groups_indexes:
        _safe_create_index("ix_user_groups_group_id", "user_groups", ["group_id"])


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    # Drop user_groups table and indexes
    if "user_groups" in insp.get_table_names():
        existing_ug_indexes = {idx["name"] for idx in insp.get_indexes("user_groups")}
        if "ix_user_groups_group_id" in existing_ug_indexes:
            op.drop_index("ix_user_groups_group_id", table_name="user_groups")
        if "ix_user_groups_user_id" in existing_ug_indexes:
            op.drop_index("ix_user_groups_user_id", table_name="user_groups")
        op.drop_table("user_groups")

    # Drop groups table and indexes
    if "groups" in insp.get_table_names():
        existing_groups_indexes = {idx["name"] for idx in insp.get_indexes("groups")}
        if "ix_groups_tenant_id" in existing_groups_indexes:
            op.drop_index("ix_groups_tenant_id", table_name="groups")
        if "ix_groups_external_id" in existing_groups_indexes:
            op.drop_index("ix_groups_external_id", table_name="groups")
        op.drop_table("groups")
