from datetime import datetime

from sqlalchemy import and_, delete, func, or_, select
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

    async def delete_chunks(self, document_id: int) -> None:
        await self.session.execute(
            delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id)
        )

    async def set_processing_status(
        self,
        document: KnowledgeDocument,
        status: str,
        *,
        error: str | None = None,
        processed_at: datetime | None = None,
    ) -> None:
        document.processing_status = status
        document.processing_error = error
        document.processed_at = processed_at
        await self.session.flush()

    async def get_document(
        self, profile_id: int, document_id: int
    ) -> KnowledgeDocument | None:
        document = await self.session.get(KnowledgeDocument, document_id)
        if document is None or document.profile_id != profile_id:
            return None
        return document

    async def list_documents(self, profile_id: int) -> list[tuple[KnowledgeDocument, int]]:
        """Return (document, chunk_count) tuples for the business, newest first."""
        chunk_count = func.count(KnowledgeChunk.id)
        stmt = (
            select(KnowledgeDocument, chunk_count)
            .outerjoin(KnowledgeChunk, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(KnowledgeDocument.profile_id == profile_id)
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
        self, profile_id: int, embedding: list[float], limit: int = 4
    ) -> list[tuple[KnowledgeChunk, str, float]]:
        """Return (chunk, document_title, distance) ordered by cosine distance."""
        distance = KnowledgeChunk.embedding.cosine_distance(embedding)
        stmt = (
            select(KnowledgeChunk, KnowledgeDocument.title, distance.label("distance"))
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(
                KnowledgeChunk.profile_id == profile_id,
                KnowledgeDocument.is_active.is_(True),
                KnowledgeDocument.processing_status == "ready",
            )
            .order_by(distance)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [(row[0], row[1], float(row[2])) for row in result.all()]

    async def search_text(
        self, profile_id: int, terms: list[str], limit: int = 4
    ) -> list[tuple[KnowledgeChunk, str]]:
        """Return active chunks containing any exact query term.

        This complements vector search for names, identifiers, and transliterated
        words, which semantic embeddings can otherwise rank inconsistently.
        """
        escaped_terms = [
            term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            for term in terms
            if term
        ]
        patterns = [f"%{term}%" for term in escaped_terms]
        if not patterns:
            return []

        matches = []
        for pattern in patterns:
            matches.append(
                or_(
                    KnowledgeChunk.content.ilike(pattern, escape="\\"),
                    KnowledgeDocument.title.ilike(pattern, escape="\\"),
                )
            )
        stmt = (
            select(KnowledgeChunk, KnowledgeDocument.title)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(
                KnowledgeChunk.profile_id == profile_id,
                KnowledgeDocument.is_active.is_(True),
                KnowledgeDocument.processing_status == "ready",
                and_(*matches),
            )
            .order_by(KnowledgeChunk.id)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]
