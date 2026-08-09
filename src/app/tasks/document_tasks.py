import asyncio
import base64
from uuid import UUID

from app.core.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.services.document_service import run_document_processing
from app.core.exceptions import LLMServiceError
from app.models.document import Document, DocumentStatus
from app.core.logger import logger



@celery_app.task(
    name="process_document",
    bind=True,
    autoretry_for=(LLMServiceError,),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=3,
)
def process_document_task(self,document_id: str, filename: str, content_b64: str) -> None:
    content = base64.b64decode(content_b64)
    try:
        asyncio.run(_process_document_async(UUID(document_id), filename, content))
    except LLMServiceError:
        if self.request.retries >= self.max_retries:
            logger.error("document_processing_failed", document_id=document_id)
            asyncio.run(_mark_document_failed(UUID(document_id), "All retries failed"))
        raise


async def _process_document_async(document_id: UUID, filename: str, content: bytes) -> None:
    async with AsyncSessionLocal() as db:
        await run_document_processing(document_id, filename, content, db)


async def _mark_document_failed(document_id: UUID, error_message: str) -> None:
    async with AsyncSessionLocal() as db:
        document = await db.get(Document, document_id)
        document.status = DocumentStatus.FAILED
        document.error_message = error_message
        await db.commit()