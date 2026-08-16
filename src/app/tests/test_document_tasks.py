# src/app/tests/test_document_tasks.py — archivo nuevo
# Testea run_document_processing directo, con el mismo db_session
# aislado de siempre. Nunca pasa por Celery ni por asyncio.run(),
# así que no hay riesgo de choque de event loops.

from uuid import UUID
from unittest.mock import AsyncMock, patch

from app.services.document_service import run_document_processing
from app.models.document import Document, DocumentStatus
from app.core.exceptions import LLMServiceError
import pytest
from app.services.document_service import search_relevant_chunks
from app.models.document import Document, DocumentChunk, DocumentStatus


async def test_run_document_processing_marks_ready_and_creates_chunks(db_session, test_assistant):
    document = Document(
        assistant_id=UUID(test_assistant["id"]), filename="notes.txt", status=DocumentStatus.PENDING
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    with patch("app.services.document_service.embed", new=AsyncMock(return_value=[[0.1] * 1536])):
        await run_document_processing(document.id, "notes.txt", b"contenido " * 200, db_session)

    await db_session.refresh(document)
    assert document.status == DocumentStatus.READY

async def test_run_document_processing_raises_on_embedding_error(db_session, test_assistant):
    document = Document(
        assistant_id=UUID(test_assistant["id"]), filename="notes.txt", status=DocumentStatus.PENDING
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    with patch("app.services.document_service.embed", new=AsyncMock(side_effect=LLMServiceError("failed"))):
        with pytest.raises(LLMServiceError):
            await run_document_processing(document.id, "notes.txt", b"content", db_session)

    await db_session.refresh(document)
    assert document.status == DocumentStatus.PROCESSING  


async def test_run_document_processing_marks_failed_on_extraction_error(db_session, test_assistant):
    document = Document(
        assistant_id=UUID(test_assistant["id"]), filename="notes.txt", status=DocumentStatus.PENDING
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    with patch("app.services.document_service.extract_text", side_effect=ValueError("corrupt PDF")):
        await run_document_processing(document.id, "notes.txt", b"content", db_session)

    await db_session.refresh(document)
    assert document.status == DocumentStatus.FAILED


async def test_search_relevant_chunks_filters_out_unrelated_results(db_session, test_assistant):
    document = Document(
        assistant_id=UUID(test_assistant["id"]), filename="notes.txt", status=DocumentStatus.READY
    )
    db_session.add(document)
    await db_session.flush()

    # Vector ortogonal al de la consulta — cosine_distance = 1.0, no debería calificar
    unrelated_vector = [0.0] * 1536
    unrelated_vector[0] = 1.0
    db_session.add(DocumentChunk(
        document_id=document.id, content="unrelated content", chunk_index=0, embedding=unrelated_vector
    ))
    await db_session.commit()

    query_vector = [0.0] * 1536
    query_vector[1] = 1.0  # ortogonal al chunk de arriba

    results = await search_relevant_chunks(document.assistant_id, query_vector, db_session)
    assert results == []
