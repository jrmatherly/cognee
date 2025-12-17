from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm

from cognee.modules.users.get_fastapi_users import get_fastapi_users
from cognee.modules.users.models import User
from cognee.modules.users.methods import get_authenticated_user
from cognee.modules.users.authentication.get_client_auth_backend import get_client_auth_backend
from cognee.shared.rate_limiting import auth_login_rate_limiter
from cognee.shared.logging_utils import get_logger

logger = get_logger("auth_router")


def get_auth_router():
    """Create authentication router with rate limiting.

    Returns FastAPI Users auth router with additional security:
    - Rate-limited login endpoint (default: 5 attempts per 5 minutes)
    - Protected /me endpoint for user info
    """
    auth_backend = get_client_auth_backend()
    fastapi_users = get_fastapi_users()

    # Create a new router that wraps the FastAPI Users router
    auth_router = APIRouter()

    # Get the original login strategy for token generation
    strategy = auth_backend.get_strategy()

    @auth_router.post("/login")
    async def rate_limited_login(
        request: Request,
        credentials: OAuth2PasswordRequestForm = Depends(),
    ):
        """Login endpoint with rate limiting.

        Rate limit: 5 attempts per 5 minutes (configurable via env vars).

        Args:
            credentials: Username (email) and password

        Returns:
            Access token on successful authentication

        Raises:
            HTTPException: On invalid credentials or rate limit exceeded
        """
        async with auth_login_rate_limiter():
            # Import here to avoid circular imports
            from cognee.modules.users.get_user_manager import get_user_manager
            from cognee.modules.users.get_user_db import get_user_db_context
            from cognee.infrastructure.databases.relational import get_relational_engine

            db_engine = get_relational_engine()
            async with db_engine.get_async_session() as session:
                async with get_user_db_context(session) as user_db:
                    user_manager = get_user_manager(user_db)

                    # Authenticate user
                    user = await user_manager.authenticate(credentials)

                    if user is None:
                        logger.warning(f"Failed login attempt for: {credentials.username}")
                        raise HTTPException(
                            status_code=400,
                            detail="LOGIN_BAD_CREDENTIALS",
                        )

                    if not user.is_active:
                        logger.warning(f"Login attempt for inactive user: {credentials.username}")
                        raise HTTPException(
                            status_code=400,
                            detail="LOGIN_USER_NOT_VERIFIED",
                        )

                    # Generate token
                    token = await strategy.write_token(user)

                    logger.info(f"Successful login for: {credentials.username}")

                    return {
                        "access_token": token,
                        "token_type": "bearer",
                    }

    @auth_router.post("/logout")
    async def logout(user: User = Depends(get_authenticated_user)):
        """Logout endpoint.

        Note: For stateless JWT, this is a no-op on the server side.
        The client should discard the token.
        """
        logger.info(f"User logged out: {user.email}")
        return {"message": "Logged out successfully"}

    @auth_router.get("/me")
    async def get_me(user: User = Depends(get_authenticated_user)):
        """Get current authenticated user info."""
        return {
            "email": user.email,
        }

    return auth_router
