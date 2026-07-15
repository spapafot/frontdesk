from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_session
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.widget_repository import WidgetRepository
from app.schemas.conversation import WidgetRatingRequest
from app.services.live_auth import conversation_token_matches
from app.services.widget_auth import create_widget_token, decode_widget_token

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
    live_human_escalation_enabled: bool = False


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
        live_human_escalation_enabled=(
            settings.live_human_escalation_enabled
            and profile.live_human_escalation_enabled
        ),
    )


@router.post("/rating", status_code=204)
async def rate_conversation(
    body: WidgetRatingRequest,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Let a widget visitor rate their own conversation.

    Authorized exactly like ``/chat/stream`` and ``/live/visitor/socket-ticket``:
    the widget token proves the installation and the conversation token proves
    the visitor owns this conversation. Not gated by the live-escalation flag -
    a plain AI conversation can be rated too.
    """
    profile_id, installation_id, public_key = decode_widget_token(body.widget_token)
    installation = await WidgetRepository(session).get_for_profile(profile_id)
    if (
        installation is None
        or installation.id != installation_id
        or installation.public_key != public_key
        or not installation.is_enabled
    ):
        raise HTTPException(status_code=401, detail="Widget installation is unavailable.")
    conversation = await ConversationRepository(session).get(body.conversation_id)
    if conversation is None or conversation.profile_id != profile_id:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    conversation_token_matches(
        body.conversation_token,
        profile_id=profile_id,
        conversation_id=conversation.id,
        stored_hash=conversation.visitor_session_id_hash,
    )
    await ConversationRepository(session).set_rating(conversation, body.rating)
    await session.commit()
    return Response(status_code=204)
