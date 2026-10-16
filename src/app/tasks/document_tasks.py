import asyncio
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.gemini_client import task_gemini_client
from app.core.logger import logger
from app.db.session import database_url
from app.models.document import Document
from app.services.document_service import (
    recoverable_document_ids,
    run_document_processing,
)


@asynccontextmanager
async def worker_session():
    # Each asyncio.run owns and disposes its own connections.
    engine = create_async_engine(database_url, poolclass=NullPool)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            yield db
    finally:
        await engine.dispose()


@celery_app.task(name="process_document", acks_late=True, reject_on_worker_lost=True,
                 soft_time_limit=settings.DOCUMENT_TIMEOUT_SECONDS + 10,
                 time_limit=settings.DOCUMENT_TIMEOUT_SECONDS + 30)
def process_document_task(document_id: str) -> None:
    asyncio.run(_process_document_async(UUID(document_id)))


async def _process_document_async(document_id: UUID) -> None:
    async with worker_session() as db:
        document = await db.get(Document, document_id)
        if document is None:
            return
        filename, content = document.filename, document.original_content or b""
        await db.commit()
        async with task_gemini_client():
            await run_document_processing(document_id, filename, content, db)


async def _recover_document_ids() -> list[UUID]:
    async with worker_session() as db:
        return await recoverable_document_ids(db)


@celery_app.task(name="recover_documents")
def recover_documents_task() -> None:
    for document_id in asyncio.run(_recover_document_ids()):
        try:
            process_document_task.apply_async(args=[str(document_id)], retry=False)
        except Exception as exc:  # noqa: BLE001 -- Leave pending work for the next recovery scan on any publication failure.
            logger.warning("Recovery dispatch unavailable", document_id=str(document_id),
                           error_type=type(exc).__name__)
            break
