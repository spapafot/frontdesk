"""SQS entrypoint for the document-ingestion Lambda."""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.core.db import SessionLocal
from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.ingestion_service import (
    ExtractionError,
    UnsupportedFileType,
    process_existing_document,
)

MAX_RECEIVE_COUNT = 3


def _s3_client():
    import boto3

    return boto3.client("s3", region_name=settings.aws_region)


async def _delete_source(key: str) -> None:
    try:
        await asyncio.to_thread(
            _s3_client().delete_object, Bucket=settings.ingestion_bucket, Key=key
        )
    except Exception:
        # S3 lifecycle cleanup is the safety net; processing state must still settle.
        pass


async def _mark_failed(document_id: int, profile_id: int, message: str) -> None:
    async with SessionLocal() as session:
        repo = KnowledgeRepository(session)
        document = await repo.get_document(profile_id, document_id)
        if document is None or document.processing_status == "ready":
            return
        document.processing_status = "failed"
        document.processing_error = message[:2000]
        document.is_active = False
        document.processed_at = datetime.now(timezone.utc)
        await session.commit()


async def _process_record(record: dict[str, Any]) -> None:
    payload = json.loads(record["body"])
    document_id = int(payload["document_id"])
    profile_id = int(payload["profile_id"])
    filename = str(payload["filename"])
    storage_key = str(payload["storage_key"])
    receive_count = int(
        record.get("attributes", {}).get("ApproximateReceiveCount", "1")
    )

    async with SessionLocal() as session:
        repo = KnowledgeRepository(session)
        document = await repo.get_document(profile_id, document_id)
        if document is None or document.processing_status == "ready":
            await _delete_source(storage_key)
            return
        if document.storage_key != storage_key:
            await _mark_failed(document_id, profile_id, "Ingestion object mismatch.")
            return

        document.processing_status = "processing"
        document.processing_error = None
        await session.commit()

        try:
            response = await asyncio.to_thread(
                _s3_client().get_object,
                Bucket=settings.ingestion_bucket,
                Key=storage_key,
            )
            data = await asyncio.to_thread(response["Body"].read)
            await process_existing_document(session, document, filename, data)
            document.storage_key = None
            await session.commit()
        except (UnsupportedFileType, ExtractionError) as exc:
            await session.rollback()
            await _mark_failed(document_id, profile_id, str(exc))
            await _delete_source(storage_key)
            return
        except Exception as exc:
            await session.rollback()
            if receive_count >= MAX_RECEIVE_COUNT:
                await _mark_failed(document_id, profile_id, f"Processing failed: {exc}")
                await _delete_source(storage_key)
                # Keep the final delivery failed so SQS moves it to the DLQ.
                raise
            raise

    await _delete_source(storage_key)


async def _handle(event: dict[str, Any]) -> None:
    # Provisioning fixes batch size at one, but process all records defensively.
    for record in event.get("Records", []):
        await _process_record(record)


def handler(event: dict[str, Any], context: Any) -> None:
    asyncio.run(_handle(event))
