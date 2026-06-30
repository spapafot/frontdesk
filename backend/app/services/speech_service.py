from functools import lru_cache

from openai import AsyncOpenAI

from app.core.config import settings


@lru_cache
def get_openai_client() -> AsyncOpenAI:
    """Dedicated client for the real OpenAI API (speech), not DeepSeek."""
    return AsyncOpenAI(api_key=settings.openai_api_key)


async def transcribe(data: bytes, filename: str, language: str | None = None) -> str:
    """Transcribe an audio clip to text via OpenAI STT (auto-detects language)."""
    client = get_openai_client()
    kwargs: dict = {
        "model": settings.openai_stt_model,
        "file": (filename, data),
    }
    if language:
        kwargs["language"] = language
    result = await client.audio.transcriptions.create(**kwargs)
    return (result.text or "").strip()


async def synthesize(text: str, voice: str | None = None) -> bytes:
    """Synthesize speech (MP3 bytes) from text via OpenAI TTS."""
    client = get_openai_client()
    response = await client.audio.speech.create(
        model=settings.openai_tts_model,
        voice=voice or settings.openai_tts_voice,
        input=text,
        response_format="mp3",
    )
    return await response.aread()
