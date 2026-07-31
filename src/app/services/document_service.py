from io import BytesIO
from uuid import UUID

from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk, DocumentStatus, EMBEDDING_DIM
from app.services.assistant_service import _get_assistant_for_user


def extract_text(filename: str, content: bytes) -> str:
    if filename.lower().endswith(".pdf"):
        reader = PdfReader(BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return content.decode("utf-8", errors="ignore")  # .txt, .md, etc.


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 150) -> list[str]:
    """
    Parte el texto en fragmentos de chunk_size caracteres, con overlap
    caracteres compartidos entre fragmentos consecutivos. El overlap existe
    para que una idea que caiga justo en el borde de un corte no se pierda
    completamente en ninguno de los dos fragmentos.
    """
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

        # DÍA 2 — mock: vector de ceros, solo para probar que el guardado
        # de chunks funciona antes de tocar la API real
        for i, chunk_content in enumerate(chunks):
            db.add(DocumentChunk(
                document_id=document.id,
                content=chunk_content,
                chunk_index=i,
                embedding=[0.0] * EMBEDDING_DIM,
            ))

        document.status = DocumentStatus.READY
        await db.commit()
    except Exception as e:
        document.status = DocumentStatus.FAILED
        document.error_message = str(e)
        await db.commit()
        raise

    await db.refresh(document)
    return document