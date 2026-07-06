from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest
from app.services.chat_service import stream_chat

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    # This endpoint is PUBLIC (website visitors), so we never trust a
    # ``business_id`` from the body - that would let a caller target another
    # tenant. Tenant identity comes only from the widget's ``site_key``; the
    # admin app sends neither and falls back to the single default business.
    generator = stream_chat(
        message=request.message,
        conversation_id=request.conversation_id,
        business_id=None,
        site_key=request.site_key,
        voice=request.voice,
    )
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
