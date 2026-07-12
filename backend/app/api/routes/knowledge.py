import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.api.dependencies import get_current_profile
from app.models.profile import AssistantProfile
from app.repositories.knowledge_repository import KnowledgeRepository
from app.schemas.knowledge import ChunkOut, DocumentOut, ToggleRequest
from app.services import aws_ingestion
from app.services.ingestion_service import SUPPORTED_EXTENSIONS

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def _to_out(document, chunk_count: int) -> DocumentOut:
    return DocumentOut(
        id=document.id,
        title=document.title,
        type=document.type,
        is_active=document.is_active,
        processing_status=document.processing_status,
        chunk_count=chunk_count,
        created_at=document.created_at,
        processed_at=document.processed_at,
    )


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_current_profile),
) -> list[DocumentOut]:
    rows = await KnowledgeRepository(session).list_documents(profile.id)
    return [_to_out(doc, count) for doc, count in rows]


@router.post("/documents", response_model=DocumentOut, status_code=202)
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
    if document.processing_status != "ready":
        raise HTTPException(status_code=409, detail="Document is not ready.")
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
    profile: AssistantProfile = Depends(get_current_profile),
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
