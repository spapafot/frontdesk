from functools import lru_cache

from starlette.concurrency import run_in_threadpool

from app.core.config import settings


@lru_cache
def _get_model():
    # Imported lazily so the (heavy) model only loads when first needed.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embedding_model)


def embed_sync(text: str) -> list[float]:
    model = _get_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


async def embed(text: str) -> list[float]:
    return await run_in_threadpool(embed_sync, text)
