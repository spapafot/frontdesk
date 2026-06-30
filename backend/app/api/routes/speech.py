from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services import speech_service

router = APIRouter(prefix="/speech", tags=["speech"])


class TranscriptionOut(BaseModel):
    text: str


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    voice: str | None = None


def _require_key() -> None:
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=503, detail="Speech features require OPENAI_API_KEY."
        )


@router.post("/transcribe", response_model=TranscriptionOut)
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str | None = Form(default=None),
) -> TranscriptionOut:
    _require_key()
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty audio upload.")
    try:
        text = await speech_service.transcribe(
            data, file.filename or "audio.webm", language
        )
    except Exception as exc:  # noqa: BLE001 - surface provider errors to the client
        raise HTTPException(status_code=502, detail=f"Transcription failed: {exc}")
    return TranscriptionOut(text=text)


@router.post("/tts")
async def text_to_speech(body: TTSRequest) -> StreamingResponse:
    _require_key()
    try:
        audio = await speech_service.synthesize(body.text, body.voice)
    except Exception as exc:  # noqa: BLE001 - surface provider errors to the client
        raise HTTPException(status_code=502, detail=f"Speech synthesis failed: {exc}")
    return StreamingResponse(iter([audio]), media_type="audio/mpeg")
