from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_session
from app.repositories.profile_repository import ProfileRepository
from app.repositories.widget_repository import WidgetRepository
from app.services.widget_auth import create_widget_token

router = APIRouter(prefix="/widget", tags=["widget"])


def _canonical_host(origin: str) -> str:
    """Origin with a leading ``www.`` stripped from its host.

    Lets the apex domain and its ``www`` subdomain authorize interchangeably -
    they are the same site - so an admin only has to register one of them.
    """
    scheme, sep, host = origin.partition("://")
    if not sep:
        return origin
    if host.startswith("www."):
        host = host[4:]
    return f"{scheme}://{host}"


def _origin_allowed(allowed_origin: str | None, origin: str) -> bool:
    if not allowed_origin:
        return False
    if allowed_origin == origin:
        return True
    return _canonical_host(allowed_origin) == _canonical_host(origin)


class WidgetSession(BaseModel):
    token: str
    installation_id: int
    origin: str
    assistant_name: str
    business_name: str


@router.post("/session", response_model=WidgetSession)
async def create_session(
    request: Request,
    response: Response,
    key: str = Form(..., min_length=1),
    turnstile_token: str = Form(default="", max_length=2048),
    session: AsyncSession = Depends(get_session),
) -> WidgetSession:
    # The token itself is consumed by the Cloudflare Worker. FastAPI trusts
    # only the internal marker injected after successful Siteverify validation.
    _ = turnstile_token
    if settings.turnstile_required:
        if not settings.edge_shared_secret:
            raise HTTPException(
                status_code=503,
                detail="Widget verification enforcement is misconfigured.",
            )
        if request.headers.get(settings.turnstile_verified_header) != "1":
            raise HTTPException(
                status_code=403, detail="Widget verification is required."
            )
    origin = request.headers.get("origin")
    installation = await WidgetRepository(session).get_by_key(key)
    if (
        origin is None
        or installation is None
        or not installation.is_enabled
        or not _origin_allowed(installation.allowed_origin, origin)
    ):
        raise HTTPException(
            status_code=403, detail="Widget is not authorized for this origin."
        )
    profile = await ProfileRepository(session).get(installation.profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Assistant profile not found.")
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Vary"] = "Origin"
    return WidgetSession(
        token=create_widget_token(profile.id, installation.id, installation.public_key),
        installation_id=installation.id,
        origin=origin,
        assistant_name=profile.assistant_name,
        business_name=profile.name,
    )
