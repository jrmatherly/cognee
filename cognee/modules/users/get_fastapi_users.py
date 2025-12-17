import uuid
from functools import lru_cache
from fastapi_users import FastAPIUsers

from .authentication.get_api_auth_backend import get_api_auth_backend
from .authentication.get_client_auth_backend import get_client_auth_backend
from .authentication.oidc.oidc_config import get_oidc_config
from .authentication.oidc.oidc_auth_backend import get_oidc_auth_backend

from .get_user_manager import get_user_manager
from .models.User import User


@lru_cache
def get_fastapi_users():
    """Create FastAPI Users instance with all configured auth backends.

    This factory creates the FastAPIUsers instance with:
    - API bearer token backend (for API clients)
    - Client cookie backend (for web browsers)
    - OIDC backend (if enabled via OIDC_ENABLED=true)
    """
    api_auth_backend = get_api_auth_backend()
    client_auth_backend = get_client_auth_backend()

    backends = [api_auth_backend, client_auth_backend]

    # Add OIDC backend if enabled
    oidc_config = get_oidc_config()
    if oidc_config.oidc_enabled:
        oidc_backend = get_oidc_auth_backend()
        if oidc_backend:
            backends.append(oidc_backend)

    fastapi_users = FastAPIUsers[User, uuid.UUID](
        get_user_manager, backends
    )

    return fastapi_users
