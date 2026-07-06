"""Production authentication.

Two independent gates, both no-ops when their config is empty so local
development keeps working unchanged:

1. ``EdgeSecretMiddleware`` - verifies a shared secret that the Cloudflare
   Worker injects on every request. This proves the request came through the
   edge proxy and blocks anyone hitting the raw Lambda Function URL directly.
   It runs on *all* routes (public and admin) except CORS preflight and health.

2. ``require_admin`` - a FastAPI dependency that verifies a Supabase-issued
   JWT (HS256). Applied only to admin routers (knowledge, settings,
   conversations, analytics); public chat/widget routes never use it.
"""

from __future__ import annotations

import hmac

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings

# Paths that must stay reachable without the edge secret: CORS preflight has no
# custom headers, and health checks are called by the platform, not the Worker.
_EDGE_EXEMPT_PATHS = {"/health", "/", "/docs", "/openapi.json"}


class EdgeSecretMiddleware(BaseHTTPMiddleware):
    """Reject requests that did not come through the edge proxy."""

    async def dispatch(self, request: Request, call_next):
        secret = settings.edge_shared_secret
        if secret and request.method != "OPTIONS" and request.url.path not in _EDGE_EXEMPT_PATHS:
            provided = request.headers.get(settings.edge_secret_header, "")
            # Constant-time compare to avoid leaking the secret via timing.
            if not hmac.compare_digest(provided, secret):
                return JSONResponse(
                    {"detail": "Forbidden."}, status_code=status.HTTP_403_FORBIDDEN
                )
        return await call_next(request)


# auto_error=False so we can return a clean 401 (and skip entirely when admin
# auth is disabled for local dev).
_bearer = HTTPBearer(auto_error=False)


class AdminUser:
    """The authenticated admin, derived from the Supabase JWT claims."""

    def __init__(self, subject: str, email: str | None, claims: dict):
        self.id = subject
        self.email = email
        self.claims = claims


async def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AdminUser:
    """Validate the Supabase access token on an admin request.

    When ``SUPABASE_JWT_SECRET`` is unset (local dev), auth is disabled and a
    synthetic dev user is returned so the admin UI works without a login.
    """
    if not settings.admin_auth_enabled:
        return AdminUser(subject="dev", email="dev@localhost", claims={})

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience=settings.supabase_jwt_audience,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return AdminUser(
        subject=claims.get("sub", ""),
        email=claims.get("email"),
        claims=claims,
    )
