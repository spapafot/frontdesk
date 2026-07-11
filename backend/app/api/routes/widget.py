from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.repositories.profile_repository import ProfileRepository
from app.repositories.widget_repository import WidgetRepository
from app.services.widget_auth import create_widget_token

router = APIRouter(prefix="/widget", tags=["widget"])


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
    session: AsyncSession = Depends(get_session),
) -> WidgetSession:
    origin = request.headers.get("origin")
    installation = await WidgetRepository(session).get_by_key(key)
    if (
        origin is None
        or installation is None
        or not installation.is_enabled
        or installation.allowed_origin != origin
    ):
        raise HTTPException(status_code=403, detail="Widget is not authorized for this origin.")
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
