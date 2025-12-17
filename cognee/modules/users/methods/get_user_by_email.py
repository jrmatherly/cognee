from sqlalchemy import select
from sqlalchemy.orm import selectinload

from cognee.infrastructure.databases.relational import get_relational_engine

from ..models import User


async def get_user_by_email(user_email: str):
    """Get a user by email with eager-loaded relationships.

    Eager loading conventions for this module:
    - Use `selectinload` for one-to-many/many-to-many relationships (users -> roles, tenants)
      This avoids Cartesian product issues with multiple collections.
    - Use `joinedload` for many-to-one relationships (e.g., user -> single tenant lookup)
    """
    db_engine = get_relational_engine()

    async with db_engine.get_async_session() as session:
        user = (
            await session.execute(
                select(User)
                .options(selectinload(User.roles), selectinload(User.tenants))
                .where(User.email == user_email)
            )
        ).scalar()

        return user
