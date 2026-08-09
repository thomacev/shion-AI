import asyncio
import base64
from uuid import UUID

from app.core.celery_app import celery_app
from app.core.exceptions import LLMServiceError
from app.core.logger import logger
from app.db.session import AsyncSessionLocal
from app.models.document import Document, DocumentStatus
from app.services.document_service import run_document_processing


@celery_app.task(
    name="process_document",
    bind=True,
    autoretry_for=(LLMServiceError,),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=3,
)
def process_document_task(self, document_id: str, filename: str, content_b64: str) -> None:
    current_retry = self.request.retries
    logger.info(
        "Document processing task started",
        extra={
            "document_id": document_id,
            "filename": filename,
            "retry_count": current_retry,
        },
    )

    try:
        content = base64.b64decode(content_b64)
        asyncio.run(_process_document_async(UUID(document_id), filename, content))

        logger.info(
            "Document processing task completed successfully",
            extra={"document_id": document_id, "filename": filename},
        )
    except LLMServiceError as exc:
        if current_retry >= self.max_retries:
            logger.error(
                "Document processing task failed: max retries reached",
                extra={
                    "document_id": document_id,
                    "retry_count": current_retry,
                    "error": str(exc),
                },
            )
            asyncio.run(
                _mark_document_failed(UUID(document_id), "All retries failed due to LLM service error")
            )
        else:
            logger.warning(
                "Document processing task encountered LLM error, scheduling retry",
                extra={
                    "document_id": document_id,
                    "retry_count": current_retry + 1,
                    "max_retries": self.max_retries,
                    "error": str(exc),
                },
            )
        raise
    except Exception as exc:
        logger.error(
            "Document processing task failed unexpectedly",
            extra={"document_id": document_id, "error": str(exc)},
            exc_info=True,
        )
        asyncio.run(
            _mark_document_failed(UUID(document_id), f"Unexpected error: {str(exc)}")
        )
        raise


async def _process_document_async(document_id: UUID, filename: str, content: bytes) -> None:
    async with AsyncSessionLocal() as db:
        await run_document_processing(document_id, filename, content, db)


async def _mark_document_failed(document_id: UUID, error_message: str) -> None:
    async with AsyncSessionLocal() as db:
        document = await db.get(Document, document_id)
        if document:
            document.status = DocumentStatus.FAILED
            document.error_message = error_message
            await db.commit()
            logger.info(
                "Document marked as failed in database",
                extra={"document_id": str(document_id), "error_reason": error_message},
            )