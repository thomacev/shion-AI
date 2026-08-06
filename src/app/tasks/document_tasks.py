# src/app/tasks/document_tasks.py — nuevo
import asyncio
import base64
from uuid import UUID

from app.core.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.services.document_service import run_document_processing


@celery_app.task(name="process_document")
def process_document_task(document_id: str, filename: str, content_b64: str) -> None:
    content = base64.b64decode(content_b64)
    asyncio.run(_process_document_async(UUID(document_id), filename, content))


async def _process_document_async(document_id: UUID, filename: str, content: bytes) -> None:
    async with AsyncSessionLocal() as db:
        await run_document_processing(document_id, filename, content, db)