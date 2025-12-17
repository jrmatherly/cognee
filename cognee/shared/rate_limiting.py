"""Rate limiting utilities for cognee.

Provides rate limiters for:
- LLM API calls (existing)
- Embedding API calls (existing)
- Authentication endpoints (new)
- General API endpoints (new)
"""

import os
from aiolimiter import AsyncLimiter
from contextlib import nullcontext

from cognee.infrastructure.llm.config import get_llm_config
from cognee.shared.logging_utils import get_logger

logger = get_logger("rate_limiting")

llm_config = get_llm_config()

# Existing LLM rate limiters
llm_rate_limiter = AsyncLimiter(
    llm_config.llm_rate_limit_requests, llm_config.embedding_rate_limit_interval
)
embedding_rate_limiter = AsyncLimiter(
    llm_config.embedding_rate_limit_requests, llm_config.embedding_rate_limit_interval
)

# Authentication rate limiters (stricter limits)
# 5 login attempts per 5 minutes per client
AUTH_LOGIN_REQUESTS = int(os.getenv("AUTH_RATE_LIMIT_LOGIN_REQUESTS", "5"))
AUTH_LOGIN_WINDOW = int(os.getenv("AUTH_RATE_LIMIT_LOGIN_WINDOW", "300"))

# 10 OAuth authorize requests per minute
AUTH_OAUTH_REQUESTS = int(os.getenv("AUTH_RATE_LIMIT_OAUTH_REQUESTS", "10"))
AUTH_OAUTH_WINDOW = int(os.getenv("AUTH_RATE_LIMIT_OAUTH_WINDOW", "60"))

# 5 OAuth callbacks per minute (should match authorize)
AUTH_CALLBACK_REQUESTS = int(os.getenv("AUTH_RATE_LIMIT_CALLBACK_REQUESTS", "5"))
AUTH_CALLBACK_WINDOW = int(os.getenv("AUTH_RATE_LIMIT_CALLBACK_WINDOW", "60"))

# Rate limiting enabled flag
AUTH_RATE_LIMIT_ENABLED = os.getenv("AUTH_RATE_LIMIT_ENABLED", "true").lower() == "true"

# Create rate limiters
_auth_login_limiter = AsyncLimiter(AUTH_LOGIN_REQUESTS, AUTH_LOGIN_WINDOW)
_auth_oauth_limiter = AsyncLimiter(AUTH_OAUTH_REQUESTS, AUTH_OAUTH_WINDOW)
_auth_callback_limiter = AsyncLimiter(AUTH_CALLBACK_REQUESTS, AUTH_CALLBACK_WINDOW)


def llm_rate_limiter_context_manager():
    """Existing LLM rate limiter."""
    global llm_rate_limiter
    if llm_config.llm_rate_limit_enabled:
        return llm_rate_limiter
    else:
        # Return a no-op context manager if rate limiting is disabled
        return nullcontext()


def embedding_rate_limiter_context_manager():
    """Existing embedding rate limiter."""
    global embedding_rate_limiter
    if llm_config.embedding_rate_limit_enabled:
        return embedding_rate_limiter
    else:
        # Return a no-op context manager if rate limiting is disabled
        return nullcontext()


def auth_login_rate_limiter():
    """Rate limiter for login/authentication endpoints.

    Default: 5 requests per 5 minutes.
    Configure via AUTH_RATE_LIMIT_LOGIN_REQUESTS and AUTH_RATE_LIMIT_LOGIN_WINDOW.
    """
    if AUTH_RATE_LIMIT_ENABLED:
        return _auth_login_limiter
    return nullcontext()


def auth_oauth_rate_limiter():
    """Rate limiter for OAuth authorize endpoint.

    Default: 10 requests per minute.
    Configure via AUTH_RATE_LIMIT_OAUTH_REQUESTS and AUTH_RATE_LIMIT_OAUTH_WINDOW.
    """
    if AUTH_RATE_LIMIT_ENABLED:
        return _auth_oauth_limiter
    return nullcontext()


def auth_callback_rate_limiter():
    """Rate limiter for OAuth callback endpoint.

    Default: 5 requests per minute.
    Configure via AUTH_RATE_LIMIT_CALLBACK_REQUESTS and AUTH_RATE_LIMIT_CALLBACK_WINDOW.
    """
    if AUTH_RATE_LIMIT_ENABLED:
        return _auth_callback_limiter
    return nullcontext()
