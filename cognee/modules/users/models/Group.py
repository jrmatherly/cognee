"""Group model for OIDC group-based access control.

Groups are Principals, enabling group-based dataset sharing via the
existing ACL system. Groups can be synchronized from OIDC providers
(e.g., Keycloak, Microsoft EntraID) via the external_id field.
"""

from sqlalchemy.orm import relationship, Mapped
from sqlalchemy import Column, String, ForeignKey, UUID, UniqueConstraint, Index
from .Principal import Principal
from .UserGroup import UserGroup


class Group(Principal):
    """Group principal for OIDC-based access control.

    Groups extend the Principal hierarchy, allowing them to be used
    in ACL entries alongside Users, Roles, and Tenants. This enables
    three levels of dataset sharing:
    - Individual: Share with specific users
    - Group: Share with OIDC groups (e.g., EntraID security groups)
    - Global: Share with all users in a tenant

    Attributes:
        name: Display name of the group
        external_id: OIDC provider's group identifier (for sync)
        tenant_id: Tenant this group belongs to
        description: Optional description of the group's purpose
    """

    __tablename__ = "groups"

    id = Column(UUID, ForeignKey("principals.id", ondelete="CASCADE"), primary_key=True)

    name = Column(String(255), nullable=False, index=True)
    external_id = Column(String(512), nullable=True)  # Index defined in __table_args__
    description = Column(String(1024), nullable=True)

    # Foreign key to Tenant (groups are scoped to tenants)
    tenant_id = Column(UUID, ForeignKey("tenants.id"), nullable=False)

    # Relationship to Tenant
    tenant = relationship("Tenant", back_populates="groups", foreign_keys=[tenant_id])

    # Many-to-Many relationship with Users
    users: Mapped[list["User"]] = relationship(  # noqa: F821
        "User",
        secondary=UserGroup.__tablename__,
        back_populates="groups",
    )

    # ACL Relationship (inherited from Principal via polymorphism)
    acls = relationship("ACL", back_populates="principal", cascade="all, delete")

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_groups_tenant_name"),
        UniqueConstraint("tenant_id", "external_id", name="uq_groups_tenant_external_id"),
        Index("ix_groups_external_id", "external_id"),
        Index("ix_groups_tenant_id", "tenant_id"),
    )

    __mapper_args__ = {
        "polymorphic_identity": "group",
    }

    def __repr__(self) -> str:
        return f"<Group(name={self.name}, tenant_id={self.tenant_id})>"
