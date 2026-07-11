"""Rebuild chunks for every stored document from its saved text.

Re-chunks (applying the current junk-chunk filter) and re-embeds with the
configured model. Use after changing the chunker, the filter, or the embedding
model. Runs from the document's stored `content`, so no re-upload is needed.

Usage inside the backend container:

    python reingest_documents.py
"""
import asyncio

from sqlalchemy import delete, select

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.embeddings import embed_passage_sync
from app.services.ingestion_service import chunk_text


async def main() -> None:
    print(
        f"Re-ingesting documents with: {settings.openai_embedding_model} "
        f"(dim={settings.embedding_dim})"
    )
    async with SessionLocal() as session:
        repo = KnowledgeRepository(session)
        documents = list(
            (await session.execute(select(KnowledgeDocument))).scalars().all()
        )
        print(f"Found {len(documents)} document(s).")
        for document in documents:
            await session.execute(
                delete(KnowledgeChunk).where(
                    KnowledgeChunk.document_id == document.id
                )
            )
            chunks = chunk_text(document.content)
            for chunk in chunks:
                await repo.add_chunk(
                    profile_id=document.profile_id,
                    document_id=document.id,
                    content=chunk,
                    embedding=embed_passage_sync(chunk),
                    meta={"title": document.title},
                )
            await session.commit()
            print(f"  {document.title}: {len(chunks)} chunk(s)")
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
