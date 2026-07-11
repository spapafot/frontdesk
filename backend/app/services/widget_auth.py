from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException

from app.core.config import settings

AUDIENCE = "widget-chat"


def create_widget_token(profile_id: int, installation_id: int, public_key: str) -> str:
    if not settings.widget_session_secret:
        raise HTTPException(status_code=503, detail="Widget session signing is not configured.")
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(profile_id),
            "installation_id": installation_id,
            "key": public_key,
            "aud": AUDIENCE,
            "iat": now,
            "exp": now + timedelta(seconds=settings.widget_session_ttl_seconds),
        },
        settings.widget_session_secret,
        algorithm="HS256",
    )


def decode_widget_token(token: str) -> tuple[int, int, str]:
    if not settings.widget_session_secret:
        raise HTTPException(status_code=503, detail="Widget session signing is not configured.")
    try:
        claims = jwt.decode(
            token,
            settings.widget_session_secret,
            algorithms=["HS256"],
            audience=AUDIENCE,
        )
        return int(claims["sub"]), int(claims["installation_id"]), str(claims["key"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired widget session.") from exc
