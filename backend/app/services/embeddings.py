from functools import lru_cache

from openai import AsyncOpenAI, OpenAI

from app.core.config import settings

# OpenAI embeddings (text-embedding-3-*) need no query/passage prefixes, so
# passage and query embedding are the same call. Kept as separate function names
# for compatibility with existing call sites.


@lru_cache
def _sync_client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)


@lru_cache
def _async_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.openai_api_key)


def _embed_sync(text: str) -> list[float]:
    response = _sync_client().embeddings.create(
        model=settings.openai_embedding_model, input=text
    )
    return response.data[0].embedding


async def _embed_async(text: str) -> list[float]:
    response = await _async_client().embeddings.create(
        model=settings.openai_embedding_model, input=text
    )
    return response.data[0].embedding


def embed_passage_sync(text: str) -> list[float]:
    """Embed a document/passage (synchronous; used by ingestion and scripts)."""
    return _embed_sync(text)


def embed_query_sync(text: str) -> list[float]:
    """Embed a search query (synchronous)."""
    return _embed_sync(text)


async def embed_query(text: str) -> list[float]:
    return await _embed_async(text)


async def embed_passage(text: str) -> list[float]:
    return await _embed_async(text)
