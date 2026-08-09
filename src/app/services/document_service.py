from uuid import UUID
from app.services.document_processing import extract_text, chunk_text
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk, DocumentStatus
from app.services.assistant_service import _get_assistant_for_user
from app.services.embedding_service import embed
from sqlalchemy import select, delete
from app.core.exceptions import ResourceNotFoundError
from app.core.exceptions import ResourceNotFoundError, LLMServiceError



async def create_pending_document(
    assistant_id: UUID,
    user_id: UUID,
    filename: str,
    db: AsyncSession,
) -> Document:
    await _get_assistant_for_user(assistant_id, user_id, db)
    document = Document(assistant_id=assistant_id, filename=filename, status=DocumentStatus.PENDING)
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


async def run_document_processing(
    document_id: UUID,
    filename: str,
    content: bytes,
    db: AsyncSession,
) -> None:
    document = await db.get(Document, document_id)
    document.status = DocumentStatus.PROCESSING
    await db.commit()

    try:
        text = extract_text(filename, content)
        chunks = chunk_text(text)
    except Exception as e:
        await db.rollback()
        document = await db.get(Document, document_id)
        document.status = DocumentStatus.FAILED
        document.error_message = str(e)
        await db.commit()
        return

    try:
        embeddings = await embed(chunks, task_type="RETRIEVAL_DOCUMENT")

        await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
        for i, (chunk_content, vector) in enumerate(zip(chunks, embeddings)):
            db.add(DocumentChunk(
                document_id=document.id,
                content=chunk_content,
                chunk_index=i,
                embedding=vector,
            ))
        document.status = DocumentStatus.READY
        await db.commit()

    except LLMServiceError:
        await db.rollback()
        raise

    except Exception as e:
        await db.rollback()
        document = await db.get(Document, document_id)
        document.status = DocumentStatus.FAILED
        document.error_message = str(e)
        await db.commit()


async def search_relevant_chunks(
    assistant_id: UUID,
    query_embedding: list[float],
    db: AsyncSession,
    limit: int = 4,
) -> list[DocumentChunk]:
    stmt = (
        select(DocumentChunk)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(Document.assistant_id == assistant_id, Document.status == DocumentStatus.READY)
        .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())

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