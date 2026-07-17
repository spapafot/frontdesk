from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin
from app.core.db import get_session
from app.repositories.profile_repository import ProfileRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.widget_repository import WidgetRepository
from app.schemas.chat import ChatRequest
from app.services import billing
from app.services.chat_service import stream_chat
from app.services.widget_auth import decode_widget_token
from app.services.live_auth import (
    conversation_token_matches,
    new_visitor_session_id,
)

router = APIRouter(prefix="/chat", tags=["chat"])


def _period() -> date:
    now = datetime.now(timezone.utc)
    return date(now.year, now.month, 1)


@router.post("/stream")
async def chat_stream(
    body: ChatRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    is_widget = bool(body.widget_token)
    visitor_session_id = None
    installation_id = None
    if body.widget_token:
        profile_id, installation_id, public_key = decode_widget_token(body.widget_token)
        installation = await WidgetRepository(session).get_for_profile(profile_id)
        if (
            installation is None
            or installation.id != installation_id
            or installation.public_key != public_key
            or not installation.is_enabled
        ):
            raise HTTPException(status_code=401, detail="Widget installation is unavailable.")
        # Quota is enforced account-wide (pooled across all the owner's sites)
        # against the owner's plan; the per-site counter below is display-only.
        profile = await ProfileRepository(session).get(profile_id)
        if profile is None:
            raise HTTPException(status_code=401, detail="Widget installation is unavailable.")
        subscription_repo = SubscriptionRepository(session)
        subscription = await subscription_repo.get_or_create_trial(profile.owner_user_id)
        base_limit = billing.limits_for(subscription).messages
        if base_limit is not None and not await subscription_repo.reserve_account_message(
            profile.owner_user_id, _period(), base_limit
        ):
            await session.rollback()
            raise HTTPException(status_code=429, detail="Monthly message quota exceeded.")
        await WidgetRepository(session).increment_usage(installation, _period())
        if body.conversation_id is not None:
            conversation = await ConversationRepository(session).get(body.conversation_id)
            if conversation is None or conversation.profile_id != profile_id:
                raise HTTPException(status_code=404, detail="Conversation not found.")
            if not body.conversation_token:
                raise HTTPException(status_code=401, detail="Conversation session is required.")
            conversation_token_matches(
                body.conversation_token,
                profile_id=profile_id,
                conversation_id=conversation.id,
                stored_hash=conversation.visitor_session_id_hash,
            )
        else:
            visitor_session_id = new_visitor_session_id()
        await session.commit()
    else:
        authorization = request.headers.get("authorization", "")
        credentials = None
        if authorization.lower().startswith("bearer "):
            credentials = HTTPAuthorizationCredentials(
                scheme="Bearer", credentials=authorization[7:]
            )
        user = await require_admin(credentials)
        repo = ProfileRepository(session)
        if body.site_id is not None:
            result = await repo.get_accessible(body.site_id, user.id, user.email)
            if result is None:
                raise HTTPException(status_code=404, detail="Site not found.")
            profile = result[0]
        else:
            profile, _ = await repo.resolve_default_access(user.id, user.email)
        await session.commit()
        profile_id = profile.id

        # An admin/operator must never continue a website visitor's conversation
        # through this endpoint: doing so would append messages as if the visitor
        # sent them and poison the stored transcript. Visitor conversations are
        # read-only from the dashboard; live handoff goes through the live socket
        # instead. The admin's own test chats have no visitor session, so they
        # are unaffected.
        if body.conversation_id is not None:
            conversation = await ConversationRepository(session).get(
                body.conversation_id
            )
            if (
                conversation is not None
                and conversation.profile_id == profile_id
                and conversation.visitor_session_id_hash is not None
            ):
                raise HTTPException(
                    status_code=403,
                    detail="Visitor conversations are read-only from the dashboard.",
                )

    return StreamingResponse(
        stream_chat(
            message=body.message,
            profile_id=profile_id,
            conversation_id=body.conversation_id,
            include_sources=not is_widget,
            installation_id=installation_id,
            visitor_session_id=visitor_session_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
