"""Lazily initialized AWS transport for asynchronous document uploads."""

import json
from functools import lru_cache

from starlette.concurrency import run_in_threadpool

from app.core.config import settings


@lru_cache
def _s3_client():
    import boto3

    return boto3.client("s3", region_name=settings.aws_region)


@lru_cache
def _sqs_client():
    import boto3

    return boto3.client("sqs", region_name=settings.aws_region)


def is_configured() -> bool:
    return bool(settings.ingestion_bucket and settings.ingestion_queue_url)


async def upload_source(key: str, data: bytes, content_type: str | None) -> None:
    kwargs = {
        "Bucket": settings.ingestion_bucket,
        "Key": key,
        "Body": data,
        "ServerSideEncryption": "AES256",
    }
    if content_type:
        kwargs["ContentType"] = content_type
    await run_in_threadpool(_s3_client().put_object, **kwargs)


async def delete_source(key: str) -> None:
    if not key or not settings.ingestion_bucket:
        return
    await run_in_threadpool(
        _s3_client().delete_object, Bucket=settings.ingestion_bucket, Key=key
    )


async def enqueue(payload: dict) -> None:
    await run_in_threadpool(
        _sqs_client().send_message,
        QueueUrl=settings.ingestion_queue_url,
        MessageBody=json.dumps(payload),
    )
