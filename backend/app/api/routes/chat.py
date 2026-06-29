from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest
from app.services.chat_service import stream_chat

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    generator = stream_chat(
        message=request.message,
        conversation_id=request.conversation_id,
        business_id=request.business_id,
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
