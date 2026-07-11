from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.api.dependencies import get_current_profile
from app.models.profile import AssistantProfile
from app.repositories.knowledge_repository import KnowledgeRepository
from app.schemas.knowledge import ChunkOut, DocumentOut, ToggleRequest
from app.services.ingestion_service import (
    SUPPORTED_EXTENSIONS,
    ExtractionError,
    UnsupportedFileType,
    ingest_document,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def _to_out(document, chunk_count: int) -> DocumentOut:
    return DocumentOut(
        id=document.id,
        title=document.title,
        type=document.type,
        is_active=document.is_active,
        chunk_count=chunk_count,
        created_at=document.created_at,
    )


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_current_profile),
) -> list[DocumentOut]:
    rows = await KnowledgeRepository(session).list_documents(profile.id)
    return [_to_out(doc, count) for doc, count in rows]


@router.post("/documents", response_model=DocumentOut, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_current_profile),
) -> DocumentOut:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 10 MB limit.")

    try:
        document, chunk_count = await ingest_document(
            session, profile.id, file.filename or "untitled", data
        )
    except UnsupportedFileType as exc:
        raise HTTPException(
            status_code=415,
            detail=f"{exc} Supported types: {', '.join(sorted(SUPPORTED_EXTENSIONS))}.",
        ) from exc
    except ExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return _to_out(document, chunk_count)


@router.get("/documents/{document_id}/chunks", response_model=list[ChunkOut])
async def preview_chunks(
    document_id: int,
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_current_profile),
) -> list[ChunkOut]:
    repo = KnowledgeRepository(session)
    document = await repo.get_document(profile.id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    chunks = await repo.list_chunks(document.id)
    return [ChunkOut(id=c.id, content=c.content) for c in chunks]


@router.patch("/documents/{document_id}", response_model=DocumentOut)
async def toggle_document(
    document_id: int,
    body: ToggleRequest,
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_current_profile),
) -> DocumentOut:
    repo = KnowledgeRepository(session)
    document = await repo.get_document(profile.id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    await repo.set_active(document, body.is_active)
    await session.commit()
    rows = {doc.id: count for doc, count in await repo.list_documents(profile.id)}
    return _to_out(document, rows.get(document.id, 0))


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: int,
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_current_profile),
) -> None:
    repo = KnowledgeRepository(session)
    document = await repo.get_document(profile.id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    await repo.delete_document(document)
    await session.commit()
