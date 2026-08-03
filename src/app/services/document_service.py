from io import BytesIO
from uuid import UUID

from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk, DocumentStatus, EMBEDDING_DIM
from app.services.assistant_service import _get_assistant_for_user
from app.services.embedding_service import embed
from app.core.exceptions import ResourceNotFoundError


def extract_text(filename: str, content: bytes) -> str:
    if filename.lower().endswith(".pdf"):
        reader = PdfReader(BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return content.decode("utf-8", errors="ignore")  # .txt, .md, etc.


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 150) -> list[str]:

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return [c.strip() for c in chunks if c.strip()]


async def process_document(
    assistant_id: UUID,
    user_id: UUID,
    filename: str,
    content: bytes,
    db: AsyncSession,
) -> Document:
    await _get_assistant_for_user(assistant_id, user_id, db)

    document = Document(assistant_id=assistant_id, filename=filename, status=DocumentStatus.PROCESSING)
    db.add(document)
    await db.flush()

    try:
        text = extract_text(filename, content)
        chunks = chunk_text(text)
        embeddings = await embed(chunks)

        # DÍA 2 — mock: vector de ceros, solo para probar que el guardado
        # de chunks funciona antes de tocar la API real
        for i, (chunk_content, vector) in enumerate(zip(chunks, embeddings)):
            db.add(DocumentChunk(
                document_id=document.id,
                content=chunk_content,
                chunk_index=i,
                embedding=vector,
            ))

        document.status = DocumentStatus.READY
        await db.commit()
    except Exception as e:
        document.status = DocumentStatus.FAILED
        document.error_message = str(e)
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
) -> list[Document]:
    await _get_assistant_for_user(assistant_id, user_id, db)

    stmt = (
        select(Document)
        .where(Document.assistant_id == assistant_id)
        .order_by(Document.created_at.desc())
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
    await db.delete(document)  # AsyncSession.delete() es coroutine, necesita await
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