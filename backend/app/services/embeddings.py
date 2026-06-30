from functools import lru_cache

from starlette.concurrency import run_in_threadpool

from app.core.config import settings


@lru_cache
def _get_model():
    # Imported lazily so the (heavy) model only loads when first needed.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embedding_model)


def _encode(text: str) -> list[float]:
    model = _get_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def embed_passage_sync(text: str) -> list[float]:
    """Embed a document/passage. Retrieval models (e.g. e5) expect a prefix."""
    return _encode(f"{settings.embedding_passage_prefix}{text}")


def embed_query_sync(text: str) -> list[float]:
    """Embed a search query. Retrieval models (e.g. e5) expect a prefix."""
    return _encode(f"{settings.embedding_query_prefix}{text}")


async def embed_query(text: str) -> list[float]:
    return await run_in_threadpool(embed_query_sync, text)


async def embed_passage(text: str) -> list[float]:
    return await run_in_threadpool(embed_passage_sync, text)
