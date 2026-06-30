"""Re-embed all stored knowledge chunks with the currently configured model.

Run after changing EMBEDDING_MODEL (the stored vectors must be regenerated with
the same model the query side uses). Usage inside the backend container:

    python reindex_embeddings.py
"""
import asyncio

from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.knowledge import KnowledgeChunk
from app.services.embeddings import embed_passage_sync


async def main() -> None:
    print(
        f"Re-indexing embeddings with: {settings.embedding_model} "
        f"(dim={settings.embedding_dim})"
    )
    async with SessionLocal() as session:
        chunks = list((await session.execute(select(KnowledgeChunk))).scalars().all())
        total = len(chunks)
        print(f"Found {total} chunk(s) to re-embed.")
        for i, chunk in enumerate(chunks, start=1):
            chunk.embedding = embed_passage_sync(chunk.content)
            if i % 20 == 0 or i == total:
                await session.commit()
                print(f"  re-embedded {i}/{total}")
        await session.commit()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
