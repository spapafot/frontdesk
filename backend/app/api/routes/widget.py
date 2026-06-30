from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.repositories.business_repository import BusinessRepository

router = APIRouter(prefix="/widget", tags=["widget"])


class WidgetConfig(BaseModel):
    assistant_name: str
    business_name: str


@router.get("/config", response_model=WidgetConfig)
async def widget_config(
    key: str = Query(..., min_length=1),
    session: AsyncSession = Depends(get_session),
) -> WidgetConfig:
    """Public, non-secret config for the embedded widget, keyed by site key."""
    business = await BusinessRepository(session).get_by_public_key(key)
    if business is None:
        raise HTTPException(status_code=404, detail="Unknown site key.")
    return WidgetConfig(
        assistant_name=business.assistant_name,
        business_name=business.name,
    )
