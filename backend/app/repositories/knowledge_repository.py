from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeChunk, KnowledgeDocument


class KnowledgeRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_document(self, **kwargs) -> KnowledgeDocument:
        document = KnowledgeDocument(**kwargs)
        self.session.add(document)
        await self.session.flush()
        return document

    async def add_chunk(self, **kwargs) -> KnowledgeChunk:
        chunk = KnowledgeChunk(**kwargs)
        self.session.add(chunk)
        await self.session.flush()
        return chunk

    async def get_document(
        self, business_id: int, document_id: int
    ) -> KnowledgeDocument | None:
        document = await self.session.get(KnowledgeDocument, document_id)
        if document is None or document.business_id != business_id:
            return None
        return document

    async def list_documents(self, business_id: int) -> list[tuple[KnowledgeDocument, int]]:
        """Return (document, chunk_count) tuples for the business, newest first."""
        chunk_count = func.count(KnowledgeChunk.id)
        stmt = (
            select(KnowledgeDocument, chunk_count)
            .outerjoin(KnowledgeChunk, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(KnowledgeDocument.business_id == business_id)
            .group_by(KnowledgeDocument.id)
            .order_by(KnowledgeDocument.id.desc())
        )
        result = await self.session.execute(stmt)
        return [(row[0], int(row[1])) for row in result.all()]

    async def list_chunks(self, document_id: int) -> list[KnowledgeChunk]:
        stmt = (
            select(KnowledgeChunk)
            .where(KnowledgeChunk.document_id == document_id)
            .order_by(KnowledgeChunk.id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def set_active(self, document: KnowledgeDocument, is_active: bool) -> None:
        document.is_active = is_active
        await self.session.flush()

    async def delete_document(self, document: KnowledgeDocument) -> None:
        await self.session.execute(
            delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id)
        )
        await self.session.delete(document)
        await self.session.flush()

    async def search(
        self, business_id: int, embedding: list[float], limit: int = 4
    ) -> list[tuple[KnowledgeChunk, str, float]]:
        """Return (chunk, document_title, distance) ordered by cosine distance."""
        distance = KnowledgeChunk.embedding.cosine_distance(embedding)
        stmt = (
            select(KnowledgeChunk, KnowledgeDocument.title, distance.label("distance"))
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(
                KnowledgeChunk.business_id == business_id,
                KnowledgeDocument.is_active.is_(True),
            )
            .order_by(distance)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [(row[0], row[1], float(row[2])) for row in result.all()]
