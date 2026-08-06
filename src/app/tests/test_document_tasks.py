# src/app/tests/test_document_tasks.py — archivo nuevo
# Testea run_document_processing directo, con el mismo db_session
# aislado de siempre. Nunca pasa por Celery ni por asyncio.run(),
# así que no hay riesgo de choque de event loops.

from uuid import UUID
from unittest.mock import AsyncMock, patch

from app.services.document_service import run_document_processing
from app.models.document import Document, DocumentStatus
from app.core.exceptions import LLMServiceError


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


async def test_run_document_processing_marks_failed_on_embedding_error(db_session, test_assistant):
    document = Document(
        assistant_id=UUID(test_assistant["id"]), filename="notes.txt", status=DocumentStatus.PENDING
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    with patch("app.services.document_service.embed", new=AsyncMock(side_effect=LLMServiceError("falló"))):
        await run_document_processing(document.id, "notes.txt", b"contenido", db_session)

    await db_session.refresh(document)
    assert document.status == DocumentStatus.FAILED