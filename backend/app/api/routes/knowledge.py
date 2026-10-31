import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminUser, require_admin
from app.core.db import get_session
from app.api.dependencies import get_selected_site
from app.models.profile import AssistantProfile
from app.repositories.knowledge_repository import KnowledgeRepository
from app.schemas.knowledge import (
    ChunkOut,
    DocumentOut,
    FaqRequest,
    LinkRequest,
    ToggleRequest,
)
from app.services import aws_ingestion, billing, jina_reader
from app.services.ingestion_service import (
    SUPPORTED_EXTENSIONS,
    ExtractionError,
    ingest_text_document,
    reingest_text_document,
)
from app.services.jina_reader import JinaReaderError

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

# Link sources are fetched to markdown and stored as a .txt object so the Lambda
# reuses the existing text extractor; the filename drives extractor selection.
LINK_STORAGE_FILENAME = "page.txt"

FAQ_TYPE = "faq"


def _to_out(document, chunk_count: int) -> DocumentOut:
    return DocumentOut(
        id=document.id,
        title=document.title,
        type=document.type,
        source_url=document.source_url,
        content=document.content if document.type == FAQ_TYPE else None,
        is_active=document.is_active,
        processing_status=document.processing_status,
        chunk_count=chunk_count,
        created_at=document.created_at,
        processed_at=document.processed_at,
    )


def _faq_text(question: str, answer: str) -> str:
    # Question and answer in one text so retrieval matches on either.
    return f"{question}\n\n{answer}"


async def _enforce_knowledge_limit(
    session, user: AdminUser, profile: AssistantProfile
) -> None:
    """402 when the account's plan knowledge allowance is reached.

    Knowledge is metered in chunks (≈ pgvector rows) pooled **account-wide**
    across all the owner's sites, covering files, scanned pages, and FAQs alike.
    Entitlements resolve by the site's owning account, so a team member adding to
    an owner's site is bound by the owner's plan; super-admins are unlimited.

    Ingestion is asynchronous, so we gate on the *current* chunk total before
    accepting a new source; the 10 MB/file cap bounds any single overshoot.
    """
    owner_user_id = profile.owner_user_id
    entitlements = await billing.resolve_entitlements(session, user, owner_user_id)
    if entitlements.knowledge_chunks is None:
        return
    used = await KnowledgeRepository(session).count_chunks_for_owner(owner_user_id)
    if used >= entitlements.knowledge_chunks:
        raise HTTPException(
            status_code=402,
            detail=(
                "Your plan's knowledge limit has been reached. "
                "Upgrade to add more documents, pages, and FAQs."
            ),
        )


def _link_storage_key(profile_id: int) -> str:
    return f"profiles/{profile_id}/{uuid.uuid4().hex}/{LINK_STORAGE_FILENAME}"


async def _fetch_link(url: str, *, no_cache: bool) -> tuple[str, bytes]:
    """Fetch a URL via Jina Reader and return ``(title, utf-8 bytes)``.

    Raises HTTPException(502) on a fetch failure and 413 if the page is too big.
    """
    try:
        title, content = await jina_reader.fetch_url(url, no_cache=no_cache)
    except JinaReaderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    data = content.encode("utf-8")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413, detail="The page is too large to ingest (over 10 MB)."
        )
    return title, data


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_selected_site),
) -> list[DocumentOut]:
    rows = await KnowledgeRepository(session).list_documents(profile.id)
    return [_to_out(doc, count) for doc, count in rows]


@router.post("/documents", response_model=DocumentOut, status_code=202)
async def upload_document(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_selected_site),
    user: AdminUser = Depends(require_admin),
) -> DocumentOut:
    await _enforce_knowledge_limit(session, user, profile)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 10 MB limit.")

    filename = file.filename or "untitled"
    extension = os.path.splitext(filename)[1].lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported file type: {extension or 'unknown'}. Supported types: "
                f"{', '.join(sorted(SUPPORTED_EXTENSIONS))}."
            ),
        )
    if not aws_ingestion.is_configured():
        raise HTTPException(
            status_code=503, detail="Document ingestion is not configured."
        )

    storage_key = f"profiles/{profile.id}/{uuid.uuid4().hex}/{filename}"
    try:
        await aws_ingestion.upload_source(storage_key, data, file.content_type)
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail="Could not store the document for processing."
        ) from exc

    repo = KnowledgeRepository(session)
    try:
        document = await repo.create_document(
            profile_id=profile.id,
            title=filename,
            type=extension.lstrip("."),
            content="",
            is_active=False,
            processing_status="queued",
            storage_key=storage_key,
        )
        await session.commit()
        await aws_ingestion.enqueue(
            {
                "document_id": document.id,
                "profile_id": profile.id,
                "filename": filename,
                "storage_key": storage_key,
            }
        )
    except Exception as exc:
        await session.rollback()
        if "document" in locals():
            persisted = await repo.get_document(profile.id, document.id)
            if persisted is not None:
                persisted.processing_status = "failed"
                persisted.processing_error = "The ingestion job could not be queued."
                await session.commit()
        try:
            await aws_ingestion.delete_source(storage_key)
        except Exception:
            pass
        raise HTTPException(
            status_code=503, detail="Could not queue the document for processing."
        ) from exc

    return _to_out(document, 0)


@router.post("/links", response_model=DocumentOut, status_code=202)
async def add_link(
    body: LinkRequest,
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_selected_site),
    user: AdminUser = Depends(require_admin),
) -> DocumentOut:
    await _enforce_knowledge_limit(session, user, profile)
    url = str(body.url)
    if not aws_ingestion.is_configured():
        raise HTTPException(
            status_code=503, detail="Document ingestion is not configured."
        )

    repo = KnowledgeRepository(session)
    if await repo.get_by_source_url(profile.id, url) is not None:
        raise HTTPException(
            status_code=409,
            detail="This page is already in the knowledge base. Use Rescan to refresh it.",
        )

    title, data = await _fetch_link(url, no_cache=False)

    storage_key = _link_storage_key(profile.id)
    try:
        await aws_ingestion.upload_source(storage_key, data, "text/plain; charset=utf-8")
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail="Could not store the page for processing."
        ) from exc

    try:
        document = await repo.create_document(
            profile_id=profile.id,
            title=title[:255],
            type="url",
            source_url=url,
            content="",
            is_active=False,
            processing_status="queued",
            storage_key=storage_key,
        )
        await session.commit()
        await aws_ingestion.enqueue(
            {
                "document_id": document.id,
                "profile_id": profile.id,
                "filename": LINK_STORAGE_FILENAME,
                "storage_key": storage_key,
            }
        )
    except Exception as exc:
        await session.rollback()
        if "document" in locals():
            persisted = await repo.get_document(profile.id, document.id)
            if persisted is not None:
                persisted.processing_status = "failed"
                persisted.processing_error = "The ingestion job could not be queued."
                await session.commit()
        try:
            await aws_ingestion.delete_source(storage_key)
        except Exception:
            pass
        raise HTTPException(
            status_code=503, detail="Could not queue the page for processing."
        ) from exc

    return _to_out(document, 0)


@router.post("/faqs", response_model=DocumentOut, status_code=201)
async def add_faq(
    body: FaqRequest,
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_selected_site),
    user: AdminUser = Depends(require_admin),
) -> DocumentOut:
    """Store a question/answer pair and index it synchronously.

    No S3/SQS involved - the entry is ready and active when the request
    returns, so FAQs work even when the async ingestion stack is unconfigured.
    """
    await _enforce_knowledge_limit(session, user, profile)
    try:
        document, chunk_count = await ingest_text_document(
            session,
            profile.id,
            title=body.question,
            text=_faq_text(body.question, body.answer),
            doc_type=FAQ_TYPE,
            content=body.answer,
        )
        await session.commit()
    except ExtractionError as exc:
        await session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        await session.rollback()
        raise HTTPException(
            status_code=502,
            detail="Could not index the FAQ entry. Please try again.",
        ) from exc
    return _to_out(document, chunk_count)


@router.put("/faqs/{document_id}", response_model=DocumentOut)
async def update_faq(
    document_id: int,
    body: FaqRequest,
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_selected_site),
) -> DocumentOut:
    repo = KnowledgeRepository(session)
    document = await repo.get_document(profile.id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if document.type != FAQ_TYPE:
        raise HTTPException(status_code=409, detail="Only FAQ entries can be edited.")
    try:
        chunk_count = await reingest_text_document(
            session,
            document,
            title=body.question,
            text=_faq_text(body.question, body.answer),
            content=body.answer,
        )
        await session.commit()
    except ExtractionError as exc:
        await session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        await session.rollback()
        raise HTTPException(
            status_code=502,
            detail="Could not index the FAQ entry. Please try again.",
        ) from exc
    return _to_out(document, chunk_count)


@router.post("/documents/{document_id}/rescan", response_model=DocumentOut, status_code=202)
async def rescan_document(
    document_id: int,
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_selected_site),
) -> DocumentOut:
    repo = KnowledgeRepository(session)
    document = await repo.get_document(profile.id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if document.type != "url" or not document.source_url:
        raise HTTPException(
            status_code=409, detail="Only web page links can be rescanned."
        )
    if not aws_ingestion.is_configured():
        raise HTTPException(
            status_code=503, detail="Document ingestion is not configured."
        )

    # Force a live fetch so a stale cached copy is never re-ingested.
    title, data = await _fetch_link(document.source_url, no_cache=True)

    storage_key = _link_storage_key(profile.id)
    try:
        await aws_ingestion.upload_source(storage_key, data, "text/plain; charset=utf-8")
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail="Could not store the page for processing."
        ) from exc

    try:
        # Re-queue: flipping status off "ready" defeats the Lambda's idempotency
        # skip, and the fresh storage_key matches the message it will receive.
        document.title = title[:255]
        document.storage_key = storage_key
        document.processing_status = "queued"
        document.processing_error = None
        await session.commit()
        await aws_ingestion.enqueue(
            {
                "document_id": document.id,
                "profile_id": profile.id,
                "filename": LINK_STORAGE_FILENAME,
                "storage_key": storage_key,
                # Keep the entry's current enable/disable state across the refresh.
                "preserve_active": True,
            }
        )
    except Exception as exc:
        await session.rollback()
        persisted = await repo.get_document(profile.id, document.id)
        if persisted is not None:
            persisted.processing_status = "failed"
            persisted.processing_error = "The ingestion job could not be queued."
            await session.commit()
        try:
            await aws_ingestion.delete_source(storage_key)
        except Exception:
            pass
        raise HTTPException(
            status_code=503, detail="Could not queue the page for processing."
        ) from exc

    return _to_out(document, 0)


@router.get("/documents/{document_id}/chunks", response_model=list[ChunkOut])
async def preview_chunks(
    document_id: int,
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_selected_site),
) -> list[ChunkOut]:
    repo = KnowledgeRepository(session)
    document = await repo.get_document(profile.id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if document.processing_status != "ready":
        raise HTTPException(status_code=409, detail="Document is not ready.")
    chunks = await repo.list_chunks(document.id)
    return [ChunkOut(id=c.id, content=c.content) for c in chunks]


@router.patch("/documents/{document_id}", response_model=DocumentOut)
async def toggle_document(
    document_id: int,
    body: ToggleRequest,
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_selected_site),
) -> DocumentOut:
    repo = KnowledgeRepository(session)
    document = await repo.get_document(profile.id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if document.processing_status != "ready":
        raise HTTPException(status_code=409, detail="Document is not ready.")
    await repo.set_active(document, body.is_active)
    await session.commit()
    rows = {doc.id: count for doc, count in await repo.list_documents(profile.id)}
    return _to_out(document, rows.get(document.id, 0))


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: int,
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_selected_site),
) -> None:
    repo = KnowledgeRepository(session)
    document = await repo.get_document(profile.id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    storage_key = document.storage_key
    await repo.delete_document(document)
    await session.commit()
    if storage_key:
        try:
            await aws_ingestion.delete_source(storage_key)
        except Exception:
            # The bucket lifecycle rule is the final cleanup safety net.
            pass
