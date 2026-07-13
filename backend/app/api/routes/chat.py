from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin
from app.core.db import get_session
from app.repositories.profile_repository import ProfileRepository
from app.repositories.widget_repository import WidgetRepository
from app.schemas.chat import ChatRequest
from app.services.chat_service import stream_chat
from app.services.widget_auth import decode_widget_token

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
        if not await WidgetRepository(session).reserve_message(installation, _period()):
            await session.rollback()
            raise HTTPException(status_code=429, detail="Monthly widget message quota exceeded.")
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
            profile = await repo.get_owned(body.site_id, user.id)
            if profile is None:
                raise HTTPException(status_code=404, detail="Site not found.")
        else:
            profile = await repo.get_or_create_default(user.id, user.email)
        await session.commit()
        profile_id = profile.id

    return StreamingResponse(
        stream_chat(
            message=body.message,
            profile_id=profile_id,
            conversation_id=body.conversation_id,
            include_sources=not is_widget,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
