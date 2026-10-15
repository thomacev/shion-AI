from uuid import UUID, uuid4
from datetime import timedelta
import asyncio
from sqlalchemy import select, delete, update, or_, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk, DocumentStatus
from app.services.document_processing import extract_pages, chunk_pages, validate_file
from app.services.assistant_service import _get_assistant_for_user
from app.services.embedding_service import embed, validate_embeddings
from app.core.config import settings
from app.core.exceptions import (ResourceNotFoundError, LLMServiceError,
    RetryableLLMServiceError, ValidationError, ResourceBusyError)
from app.core.logger import logger

MAX_DOCUMENT_SIZE_BYTES = settings.MAX_DOCUMENT_SIZE_MB * 1024 * 1024


async def create_pending_document(
    assistant_id: UUID,
    user_id: UUID,
    filename: str,
    content: bytes,
    content_type: str | None,
    db: AsyncSession,
) -> Document:
    await _get_assistant_for_user(assistant_id, user_id, db)

    validate_file(filename, content)

    document = Document(
        assistant_id=assistant_id,
        filename=filename,
        status=DocumentStatus.PENDING,
        content_type=content_type,
        original_content=content,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    logger.info(
        "Pending document record created",
        extra={
            "document_id": str(document.id),
            "assistant_id": str(assistant_id),
            "user_id": str(user_id),
            "filename": filename,
        },
    )
    return document


def eligible_documents():
    return or_(
        and_(Document.status == DocumentStatus.PENDING,
             or_(Document.next_attempt_at.is_(None), Document.next_attempt_at <= func.now())),
        and_(Document.status == DocumentStatus.PROCESSING,
             or_(Document.lease_expires_at.is_(None), Document.lease_expires_at <= func.now())),
    )


async def run_document_processing(document_id: UUID, filename: str, content: bytes,
                                  db: AsyncSession) -> None:
    token = uuid4()
    result = await db.execute(update(Document).where(
        Document.id == document_id, eligible_documents(),
        Document.attempts < settings.DOCUMENT_MAX_ATTEMPTS,
    ).values(status=DocumentStatus.PROCESSING, processing_token=token,
             lease_expires_at=func.now() + timedelta(seconds=settings.DOCUMENT_TIMEOUT_SECONDS + 60),
             attempts=Document.attempts + 1, error_message=None).returning(Document.attempts)
        .execution_options(synchronize_session=False))
    attempt = result.scalar_one_or_none()
    await db.commit()
    if attempt is None:
        return
    try:
        async with asyncio.timeout(settings.DOCUMENT_TIMEOUT_SECONDS):
            pages = await asyncio.to_thread(extract_pages, filename, content)
            chunks = chunk_pages(pages)
            vectors = await embed([chunk.content for chunk in chunks], task_type="RETRIEVAL_DOCUMENT")
            validate_embeddings(vectors, len(chunks))
            document = (await db.execute(select(Document).where(
                Document.id == document_id, Document.processing_token == token,
                Document.lease_expires_at > func.now(),
            ).with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
            if document is None:
                await db.rollback()
                return
            await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
            for i, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
                db.add(DocumentChunk(document_id=document_id, content=chunk.content,
                    chunk_index=i, embedding=vector, page_start=chunk.page_start, page_end=chunk.page_end))
            document.status = DocumentStatus.READY
            document.embedding_model = settings.EMBEDDING_MODEL
            document.embedding_dim = settings.EMBEDDING_DIM
            document.processing_token = None
            document.lease_expires_at = None
            document.next_attempt_at = None
            document.error_message = None
            await db.commit()
            logger.info("Document processing completed", document_id=str(document_id), chunks=len(chunks))
    except Exception as exc:
        await db.rollback()
        retry = isinstance(exc, (RetryableLLMServiceError, TimeoutError)) and attempt < settings.DOCUMENT_MAX_ATTEMPTS
        message = exc.message if isinstance(exc, (LLMServiceError, ValidationError)) else "Document processing failed"
        await db.execute(update(Document).where(Document.id == document_id, Document.processing_token == token)
            .values(status=DocumentStatus.PENDING if retry else DocumentStatus.FAILED,
                    error_message=message, processing_token=None, lease_expires_at=None,
                    next_attempt_at=func.now() + timedelta(seconds=min(60, 2 ** attempt)) if retry else None)
            .execution_options(synchronize_session=False))
        await db.commit()
        logger.warning("Document processing failed", document_id=str(document_id), retry=retry,
                       error_type=type(exc).__name__)


async def recoverable_document_ids(db: AsyncSession) -> list[UUID]:
    await db.execute(update(Document).where(eligible_documents(),
        Document.attempts >= settings.DOCUMENT_MAX_ATTEMPTS).values(
            status=DocumentStatus.FAILED, processing_token=None, lease_expires_at=None,
            error_message="Document processing attempts exhausted"))
    rows = await db.execute(select(Document.id).where(eligible_documents(),
        Document.attempts < settings.DOCUMENT_MAX_ATTEMPTS).order_by(Document.created_at).limit(100))
    ids = list(rows.scalars())
    await db.commit()
    return ids


async def retry_document(document_id: UUID, assistant_id: UUID, user_id: UUID, db: AsyncSession) -> Document:
    await _get_assistant_for_user(assistant_id, user_id, db)
    document = await _get_document_for_assistant(document_id, assistant_id, db)
    if document.original_content is None:
        raise ValidationError("Original file is unavailable; upload the document again")
    result = await db.execute(update(Document).where(Document.id == document_id,
        Document.status.in_([DocumentStatus.FAILED, DocumentStatus.READY])).values(
            status=DocumentStatus.PENDING, attempts=0, next_attempt_at=None, error_message=None,
            processing_token=None, lease_expires_at=None).returning(Document.id))
    if result.scalar_one_or_none() is None:
        raise ResourceBusyError("Document processing is already pending or active")
    await db.commit()
    await db.refresh(document)
    return document


async def search_relevant_chunks(
    assistant_id: UUID,
    query_embedding: list[float],
    db: AsyncSession,
    limit: int = 4,
) -> list[DocumentChunk]:
    stmt = (
        select(
            DocumentChunk,
            DocumentChunk.embedding.cosine_distance(query_embedding).label("distance"),
        )
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(Document.assistant_id == assistant_id, Document.status == DocumentStatus.READY,
               Document.embedding_model == settings.EMBEDDING_MODEL,
               Document.embedding_dim == settings.EMBEDDING_DIM)
        .order_by("distance")
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()
    
    logger.info(
        "rag_search",
        assistant_id=str(assistant_id),
        distances=[round(row.distance, 4) for row in rows],
        threshold=settings.RAG_MAX_DISTANCE,
    )

    return [row.DocumentChunk for row in rows if row.distance <= settings.RAG_MAX_DISTANCE]

async def list_documents(
    assistant_id: UUID,
    user_id: UUID,
    db: AsyncSession,
    limit: int = 50,
    offset: int = 0,
) -> list[Document]:
    await _get_assistant_for_user(assistant_id, user_id, db)
    stmt = (
        select(Document)
        .where(Document.assistant_id == assistant_id)
        .order_by(Document.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def delete_document(
    document_id: UUID,
    assistant_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> None:
    await _get_assistant_for_user(assistant_id, user_id, db)
    document = await _get_document_for_assistant(document_id, assistant_id, db)
    await db.delete(document)
    await db.commit()

    logger.info(
        "Document deleted successfully",
        extra={
            "document_id": str(document_id),
            "assistant_id": str(assistant_id),
            "user_id": str(user_id),
        },
    )

async def _get_document_for_assistant(
    document_id: UUID,
    assistant_id: UUID,
    db: AsyncSession,
) -> Document:
    stmt = select(Document).where(
        Document.id == document_id,
        Document.assistant_id == assistant_id,
    )
    result = await db.execute(stmt)
    document = result.scalar_one_or_none()
    if not document:
        logger.warning(
            "Document lookup failed: resource not found",
            extra={
                "document_id": str(document_id),
                "assistant_id": str(assistant_id),
            },
        )
        raise ResourceNotFoundError("Document not found")
    return document


async def get_document(
    document_id: UUID,
    assistant_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> Document:
    await _get_assistant_for_user(assistant_id, user_id, db)
    return await _get_document_for_assistant(document_id, assistant_id, db)