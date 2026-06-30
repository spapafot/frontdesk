import asyncio
from collections.abc import AsyncGenerator

from app.core.db import SessionLocal
from app.repositories.business_repository import BusinessRepository
from app.services import speech_service
from app.services.chat_service import run_turn
from app.utils.text import SentenceChunker

# OpenAI's transcription endpoint accepts up to 25 MB per request.
MAX_AUDIO_BYTES = 25 * 1024 * 1024


def filename_for(mime: str | None) -> str:
    """Pick a filename/extension the STT API recognizes from the recorder mime."""
    mime = (mime or "").lower()
    if "mp4" in mime or "m4a" in mime:
        return "audio.mp4"
    if "ogg" in mime:
        return "audio.ogg"
    if "wav" in mime:
        return "audio.wav"
    if "mp3" in mime or "mpeg" in mime:
        return "audio.mp3"
    return "audio.webm"


async def _tts_voice(business_id: int | None) -> str | None:
    async with SessionLocal() as session:
        repo = BusinessRepository(session)
        business = (
            await repo.get(business_id) if business_id else await repo.get_or_create_default()
        )
        await session.commit()
        return business.tts_voice if business else None


async def process_utterance(
    audio: bytes,
    mime: str | None,
    conversation_id: int | None,
    business_id: int | None = None,
) -> AsyncGenerator[dict | bytes, None]:
    """Handle one spoken utterance end to end.

    Yields outbound messages for the voice socket: dicts are sent as JSON,
    ``bytes`` are sent as binary MP3 frames (one per sentence, in order).

    Sentences are synthesized concurrently (each in its own task) while token
    streaming continues, so audio for the next sentence is already being made
    while the current one plays - but frames are still yielded strictly in order.
    """
    transcript = await speech_service.transcribe(audio, filename_for(mime))
    yield {"type": "transcript", "text": transcript}
    if not transcript:
        yield {"type": "done", "conversation_id": conversation_id}
        return

    voice = await _tts_voice(business_id)
    out_queue: asyncio.Queue = asyncio.Queue()

    async def produce() -> None:
        chunker = SentenceChunker()

        def synth(sentence: str) -> None:
            task = asyncio.create_task(speech_service.synthesize(sentence, voice))
            out_queue.put_nowait(("audio", task))

        try:
            async for event in run_turn(transcript, conversation_id, business_id, voice=True):
                etype = event.get("type")
                if etype == "token":
                    out_queue.put_nowait(("json", event))
                    for sentence in chunker.push(event.get("content", "")):
                        synth(sentence)
                elif etype == "done":
                    rest = chunker.flush()
                    if rest:
                        synth(rest)
                    out_queue.put_nowait(("json", event))
                elif etype in ("conversation", "error"):
                    out_queue.put_nowait(("json", event))
        finally:
            out_queue.put_nowait(None)

    producer = asyncio.create_task(produce())
    try:
        while True:
            item = await out_queue.get()
            if item is None:
                break
            kind, payload = item
            if kind == "json":
                yield payload
            else:
                try:
                    yield await payload  # synthesized MP3 bytes
                except Exception:  # noqa: BLE001 - skip a failed sentence, keep going
                    continue
    finally:
        producer.cancel()
