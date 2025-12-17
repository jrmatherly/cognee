"""UserGroup association table for many-to-many User-Group relationship."""

from datetime import datetime, timezone
from sqlalchemy import Column, ForeignKey, DateTime, UUID, Index
from cognee.infrastructure.databases.relational import Base


class UserGroup(Base):
    """Association table linking Users to Groups.

    This enables users to be members of multiple groups, and groups
    to contain multiple users. Used for group-based dataset sharing
    and OIDC group synchronization.
    """

    __tablename__ = "user_groups"

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    group_id = Column(UUID, ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True)

    __table_args__ = (
        Index("ix_user_groups_user_id", "user_id"),
        Index("ix_user_groups_group_id", "group_id"),
    )
