from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import HTTPException

from app.core.config import settings

CONVERSATION_AUDIENCE = "live-conversation"
SOCKET_AUDIENCE = "live-socket"


def new_visitor_session_id() -> str:
    return secrets.token_urlsafe(32)


def visitor_session_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _secret() -> str:
    if not settings.widget_session_secret:
        raise HTTPException(status_code=503, detail="Live-session signing is not configured.")
    return settings.widget_session_secret


def create_conversation_token(
    profile_id: int,
    installation_id: int,
    conversation_id: int,
    visitor_session_id: str,
) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": visitor_session_id,
            "profile_id": profile_id,
            "installation_id": installation_id,
            "conversation_id": conversation_id,
            "aud": CONVERSATION_AUDIENCE,
            "iat": now,
            "exp": now + timedelta(seconds=settings.live_conversation_token_ttl_seconds),
        },
        _secret(),
        algorithm="HS256",
    )


def decode_conversation_token(token: str) -> dict[str, Any]:
    try:
        claims = jwt.decode(
            token,
            _secret(),
            algorithms=["HS256"],
            audience=CONVERSATION_AUDIENCE,
        )
        for key in ("sub", "profile_id", "installation_id", "conversation_id"):
            if key not in claims:
                raise KeyError(key)
        return claims
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired conversation session.") from exc


def conversation_token_matches(token: str, *, profile_id: int, conversation_id: int, stored_hash: str | None) -> dict[str, Any]:
    claims = decode_conversation_token(token)
    valid = (
        int(claims["profile_id"]) == profile_id
        and int(claims["conversation_id"]) == conversation_id
        and stored_hash is not None
        and hmac.compare_digest(visitor_session_hash(str(claims["sub"])), stored_hash)
    )
    if not valid:
        raise HTTPException(status_code=401, detail="Conversation session does not match.")
    return claims


def create_socket_ticket(claims: dict[str, Any]) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            **claims,
            "aud": SOCKET_AUDIENCE,
            "jti": secrets.token_urlsafe(16),
            "iat": now,
            "exp": now + timedelta(seconds=settings.live_socket_ticket_ttl_seconds),
        },
        _secret(),
        algorithm="HS256",
    )


def decode_socket_ticket(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            _secret(),
            algorithms=["HS256"],
            audience=SOCKET_AUDIENCE,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired socket ticket.") from exc
