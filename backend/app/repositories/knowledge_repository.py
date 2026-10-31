from datetime import datetime

from sqlalchemy import delete, func, literal_column, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.models.profile import AssistantProfile


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

    async def get_by_source_url(
        self, profile_id: int, source_url: str
    ) -> KnowledgeDocument | None:
        """Return an existing link document for this URL, for dedup on add."""
        stmt = select(KnowledgeDocument).where(
            KnowledgeDocument.profile_id == profile_id,
            KnowledgeDocument.source_url == source_url,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def count_chunks_for_owner(self, owner_user_id: str) -> int:
        """Total knowledge chunks across all of an account's sites.

        Chunks (≈ one pgvector row each) are the plan's knowledge unit, enforced
        account-wide. ``knowledge_chunks`` carries ``profile_id`` directly, so a
        single join to ``assistant_profiles`` resolves ownership.
        """
        result = await self.session.execute(
            select(func.count(KnowledgeChunk.id))
            .join(AssistantProfile, AssistantProfile.id == KnowledgeChunk.profile_id)
            .where(AssistantProfile.owner_user_id == owner_user_id)
        )
        return int(result.scalar_one())

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
    ) -> list[tuple[KnowledgeChunk, str, float]]:
        """Return active chunks ranked by OR-based PostgreSQL full-text search.

        This complements vector search for names, identifiers, and transliterated
        words, which semantic embeddings can otherwise rank inconsistently.
        """
        clean_terms = list(dict.fromkeys(term.lower() for term in terms if term))
        if not clean_terms:
            return []

        # Terms come from the service's Unicode word tokenizer, so joining them
        # with OR produces a safe to_tsquery expression rather than user-authored
        # query syntax. `simple` keeps names, identifiers, and Greek words intact.
        config = literal_column("'simple'")
        query = func.to_tsquery(config, " | ".join(clean_terms))
        content_vector = func.to_tsvector(config, KnowledgeChunk.content)
        title_vector = func.to_tsvector(config, KnowledgeDocument.title)
        content_rank = func.ts_rank_cd(content_vector, query)
        # A title match is unusually strong evidence for a short document chunk.
        rank = (content_rank + 2.0 * func.ts_rank_cd(title_vector, query)).label(
            "text_rank"
        )
        stmt = (
            select(KnowledgeChunk, KnowledgeDocument.title, rank)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(
                KnowledgeChunk.profile_id == profile_id,
                KnowledgeDocument.is_active.is_(True),
                KnowledgeDocument.processing_status == "ready",
                or_(content_vector.op("@@")(query), title_vector.op("@@")(query)),
            )
            .order_by(rank.desc(), KnowledgeChunk.id)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [(row[0], row[1], float(row[2])) for row in result.all()]
