from datetime import datetime, timedelta, timezone
from uuid import UUID
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.exceptions import LLMServiceError, RetryableLLMServiceError
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.services.document_processing import chunk_text
from app.services.document_service import run_document_processing, search_relevant_chunks, recoverable_document_ids


async def make_document(db, assistant, content=b"content"):
    document = Document(assistant_id=UUID(assistant["id"]), filename="notes.txt",
                        status=DocumentStatus.PENDING, original_content=content)
    db.add(document)
    await db.commit()
    return document


async def test_processing_saves_every_chunk(db_session, test_assistant):
    content = b"contenido " * 400
    document = await make_document(db_session, test_assistant, content)
    texts = chunk_text(content.decode())
    vectors = [[0.1] * settings.EMBEDDING_DIM for _ in texts]
    with patch("app.services.document_service.embed", new=AsyncMock(return_value=vectors)):
        await run_document_processing(document.id, document.filename, content, db_session)
        await run_document_processing(document.id, document.filename, content, db_session)
    await db_session.refresh(document)
    chunks = (await db_session.scalars(select(DocumentChunk).where(
        DocumentChunk.document_id == document.id).order_by(DocumentChunk.chunk_index))).all()
    assert document.status == DocumentStatus.READY
    assert document.attempts == 1
    assert document.embedding_model == settings.EMBEDDING_MODEL
    assert [chunk.content for chunk in chunks] == texts
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(texts)))


@pytest.mark.parametrize("vectors", [[], [[0.1] * 1536], [[0.1] * 768] * 4])
async def test_incomplete_or_invalid_vectors_never_mark_ready(db_session, test_assistant, vectors):
    content = b"content " * 400
    document = await make_document(db_session, test_assistant, content)
    with patch("app.services.document_service.embed", new=AsyncMock(return_value=vectors)):
        await run_document_processing(document.id, document.filename, content, db_session)
    await db_session.refresh(document)
    assert document.status == DocumentStatus.FAILED
    assert not (await db_session.scalars(select(DocumentChunk).where(DocumentChunk.document_id == document.id))).all()


@pytest.mark.parametrize("error, expected", [
    (LLMServiceError("invalid"), DocumentStatus.FAILED),
    (RetryableLLMServiceError("temporary"), DocumentStatus.PENDING),
])
async def test_processing_errors_have_explicit_status(db_session, test_assistant, error, expected):
    document = await make_document(db_session, test_assistant)
    with patch("app.services.document_service.embed", new=AsyncMock(side_effect=error)):
        await run_document_processing(document.id, document.filename, b"content", db_session)
    await db_session.refresh(document)
    assert document.status == expected
    assert document.processing_token is None
    assert document.error_message


async def test_invalid_pdf_is_failed(db_session, test_assistant):
    document = await make_document(db_session, test_assistant)
    await run_document_processing(document.id, "bad.pdf", b"not a PDF", db_session)
    await db_session.refresh(document)
    assert document.status == DocumentStatus.FAILED


async def test_recovery_finds_expired_work_and_caps_attempts(db_session, test_assistant):
    document = await make_document(db_session, test_assistant)
    document.status = DocumentStatus.PROCESSING
    document.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.commit()
    assert document.id in await recoverable_document_ids(db_session)
    document.attempts = settings.DOCUMENT_MAX_ATTEMPTS
    await db_session.commit()
    assert document.id not in await recoverable_document_ids(db_session)
    await db_session.refresh(document)
    assert document.status == DocumentStatus.FAILED


async def test_search_filters_unrelated_and_unknown_model(db_session, test_assistant):
    document = await make_document(db_session, test_assistant)
    document.status = DocumentStatus.READY
    vector = [0.0] * settings.EMBEDDING_DIM
    vector[0] = 1.0
    db_session.add(DocumentChunk(document_id=document.id, content="content", chunk_index=0, embedding=vector))
    await db_session.commit()
    assert await search_relevant_chunks(document.assistant_id, vector, db_session) == []
    document.embedding_model, document.embedding_dim = settings.EMBEDDING_MODEL, settings.EMBEDDING_DIM
    await db_session.commit()
    assert len(await search_relevant_chunks(document.assistant_id, vector, db_session)) == 1
    query = [0.0] * settings.EMBEDDING_DIM
    query[1] = 1.0
    assert await search_relevant_chunks(document.assistant_id, query, db_session) == []
