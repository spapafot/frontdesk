"""Production authentication.

Two independent gates, both no-ops when their config is empty so local
development keeps working unchanged:

1. ``EdgeSecretMiddleware`` - verifies a shared secret that the Cloudflare
   Worker injects on every request. This proves the request came through the
   edge proxy and blocks anyone hitting the raw Lambda Function URL directly.
   It runs on *all* routes (public and admin) except CORS preflight and health.

2. ``require_admin`` - a FastAPI dependency that verifies a Supabase-issued
   JWT. Applied only to admin routers (knowledge, settings, conversations,
   analytics); public chat/widget routes never use it. Two signing schemes
   are supported and auto-selected from the token's ``alg`` header:
     * HS256  -> verified with the legacy shared ``supabase_jwt_secret``.
     * ES256/RS256 -> verified against the project's public JWKS (fetched from
       ``supabase_jwks_url`` and cached). This is the path for Supabase
       projects that have migrated to asymmetric signing keys.
"""

from __future__ import annotations

import asyncio
import hmac
import time

import httpx
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
        if (
            secret
            and request.method != "OPTIONS"
            and request.url.path not in _EDGE_EXEMPT_PATHS
        ):
            provided = request.headers.get(settings.edge_secret_header, "")
            # Constant-time compare to avoid leaking the secret via timing.
            if not hmac.compare_digest(provided, secret):
                return JSONResponse(
                    {"detail": "Forbidden API Access."},
                    status_code=status.HTTP_403_FORBIDDEN,
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


# In-process JWKS cache. Supabase signing keys rotate rarely, so we fetch the
# key set once and reuse it for ``supabase_jwks_cache_seconds``. The lock keeps
# a burst of concurrent requests from all fetching on a cold/expired cache.
_jwks_cache: dict[str, object] = {"set": None, "fetched_at": 0.0}
_jwks_lock = asyncio.Lock()


async def _fetch_jwks_set() -> jwt.PyJWKSet:
    """Fetch and parse the project's public JWKS. Split out for testability."""
    async with httpx.AsyncClient(timeout=5.0) as http:
        resp = await http.get(settings.supabase_jwks_url)
        resp.raise_for_status()
        return jwt.PyJWKSet.from_dict(resp.json())


async def _get_signing_key(token: str) -> jwt.PyJWK:
    """Return the public JWK that signed ``token``, fetching/caching the JWKS."""
    kid = jwt.get_unverified_header(token).get("kid")
    if not kid:
        raise jwt.InvalidTokenError("token has no 'kid' header")

    now = time.monotonic()
    cached = _jwks_cache["set"]
    fresh = cached is not None and (
        now - float(_jwks_cache["fetched_at"]) < settings.supabase_jwks_cache_seconds
    )

    def _find(jwk_set: jwt.PyJWKSet) -> jwt.PyJWK | None:
        return next((k for k in jwk_set.keys if k.key_id == kid), None)

    if fresh:
        key = _find(cached)  # type: ignore[arg-type]
        if key is not None:
            return key

    # Cache is cold, expired, or missing this kid (likely a key rotation) -> refetch.
    async with _jwks_lock:
        # Another coroutine may have refreshed while we waited for the lock.
        cached = _jwks_cache["set"]
        if cached is not None and (
            time.monotonic() - float(_jwks_cache["fetched_at"])
            < settings.supabase_jwks_cache_seconds
        ):
            key = _find(cached)  # type: ignore[arg-type]
            if key is not None:
                return key

        jwk_set = await _fetch_jwks_set()

        _jwks_cache["set"] = jwk_set
        _jwks_cache["fetched_at"] = time.monotonic()

        key = _find(jwk_set)
        if key is None:
            raise jwt.InvalidTokenError(f"no signing key matches kid {kid!r}")
        return key


async def _decode(token: str) -> dict:
    """Verify ``token`` and return its claims, picking the scheme from ``alg``."""
    alg = jwt.get_unverified_header(token).get("alg", "")
    common = {
        "audience": settings.supabase_jwt_audience,
        "options": {"verify_aud": True},
    }

    if alg == "HS256":
        if not settings.supabase_jwt_secret:
            raise jwt.InvalidTokenError("HS256 token but no shared secret configured")
        return jwt.decode(
            token, settings.supabase_jwt_secret, algorithms=["HS256"], **common
        )

    # Asymmetric (ES256/RS256): verify against the project's public JWKS.
    if not settings.supabase_jwks_url:
        raise jwt.InvalidTokenError(
            f"{alg or 'asymmetric'} token but SUPABASE_URL is not configured"
        )
    signing_key = await _get_signing_key(token)
    return jwt.decode(token, signing_key.key, algorithms=["ES256", "RS256"], **common)


async def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AdminUser:
    """Validate the Supabase access token on an admin request.

    Every environment (local, dev, and production) must present a valid
    Supabase JWT; there is no bypass. The signing config
    (``SUPABASE_JWT_SECRET`` or ``SUPABASE_URL``) must therefore be set for
    admin routes to be reachable.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = await _decode(credentials.credentials)
    except (jwt.PyJWTError, httpx.HTTPError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if not claims.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AdminUser(
        subject=claims.get("sub", ""),
        email=claims.get("email"),
        claims=claims,
    )
