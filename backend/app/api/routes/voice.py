import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.services import voice_service

router = APIRouter(tags=["voice"])


@router.websocket("/voice/ws")
async def voice_ws(ws: WebSocket) -> None:
    """Bidirectional voice channel.

    Client -> server: JSON control frames (config/audio_end/cancel) and binary
    audio chunks buffered until ``audio_end``. Server -> client: JSON events
    (transcript/token/done/error) and binary MP3 audio frames.

    Each utterance is processed in a background task so the receive loop keeps
    running and a ``cancel`` (barge-in) can interrupt an in-flight reply.
    """
    await ws.accept()

    if not settings.openai_api_key:
        await ws.send_json(
            {"type": "error", "message": "Speech features require OPENAI_API_KEY."}
        )
        await ws.close()
        return

    state = {"conversation_id": None}
    mime: str | None = None
    chunks: list[bytes] = []
    total = 0
    current: asyncio.Task | None = None

    async def run_turn_task(audio: bytes, audio_mime: str | None, conv: int | None) -> None:
        try:
            async for out in voice_service.process_utterance(audio, audio_mime, conv):
                if isinstance(out, (bytes, bytearray)):
                    await ws.send_bytes(out)
                else:
                    if out.get("type") == "conversation":
                        state["conversation_id"] = out["conversation_id"]
                    await ws.send_json(out)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - report to client
            await ws.send_json({"type": "error", "message": f"Voice error: {exc}"})

    def cancel_current() -> None:
        if current is not None and not current.done():
            current.cancel()

    try:
        while True:
            message = await ws.receive()
            if message["type"] == "websocket.disconnect":
                break

            text = message.get("text")
            if text is not None:
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    continue
                kind = data.get("type")

                if kind == "config":
                    if data.get("conversation_id") is not None:
                        state["conversation_id"] = data["conversation_id"]
                    mime = data.get("mime") or mime

                elif kind == "cancel":
                    cancel_current()
                    chunks = []
                    total = 0

                elif kind == "audio_end":
                    audio = b"".join(chunks)
                    chunks = []
                    total = 0
                    if not audio:
                        continue
                    cancel_current()
                    current = asyncio.create_task(
                        run_turn_task(audio, mime, state["conversation_id"])
                    )
                continue

            chunk = message.get("bytes")
            if chunk is not None:
                total += len(chunk)
                if total > voice_service.MAX_AUDIO_BYTES:
                    chunks = []
                    total = 0
                    await ws.send_json(
                        {"type": "error", "message": "Audio too long; please try a shorter clip."}
                    )
                    continue
                chunks.append(chunk)
    except WebSocketDisconnect:
        pass
    finally:
        cancel_current()
