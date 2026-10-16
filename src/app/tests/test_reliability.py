import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from celery.contrib.testing.worker import start_worker
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.exceptions import ResourceBusyError
from app.models.assistant import Assistant
from app.models.conversation import Conversation, Message
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.models.user import User
from app.services.conversation_service import send_message
from app.services.document_service import run_document_processing
from app.tasks.document_tasks import process_document_task, recover_documents_task


@pytest_asyncio.fixture
async def committed_records(setup_test_db):
    from app.tests.conftest import test_engine
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as db:
        user = User(email=f"reliability-{uuid4()}@test.com", password="unused", full_name="Test User")
        db.add(user)
        await db.flush()
        assistant = Assistant(user_id=user.id, name="Test", system_prompt="Be helpful")
        db.add(assistant)
        await db.flush()
        conversation = Conversation(assistant_id=assistant.id, use_rag=False)
        document = Document(assistant_id=assistant.id, filename="notes.txt", original_content=b"original text")
        db.add_all([conversation, document])
        await db.commit()
        ids = SimpleNamespace(user=user.id, assistant=assistant.id, conversation=conversation.id,
                              document=document.id, factory=factory)
    try:
        yield ids
    finally:
        async with factory() as db:
            documents = select(Document.id).where(Document.assistant_id == ids.assistant)
            await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id.in_(documents)))
            await db.execute(delete(Document).where(Document.assistant_id == ids.assistant))
            await db.execute(delete(Message).where(Message.conversation_id == ids.conversation))
            await db.execute(delete(Conversation).where(Conversation.assistant_id == ids.assistant))
            await db.execute(delete(Assistant).where(Assistant.id == ids.assistant))
            await db.execute(delete(User).where(User.id == ids.user))
            await db.commit()


async def test_two_document_attempts_cannot_process_the_same_claim(committed_records):
    ids = committed_records
    entered, release = asyncio.Event(), asyncio.Event()
    async def slow_embed(*args, **kwargs):
        entered.set()
        await release.wait()
        return [[0.1] * 1536]
    async with ids.factory() as first, ids.factory() as second:
        with patch("app.services.document_service.embed", new=AsyncMock(side_effect=slow_embed)) as embed:
            task = asyncio.create_task(run_document_processing(ids.document, "notes.txt", b"text", first))
            try:
                await asyncio.wait_for(entered.wait(), 5)
                await run_document_processing(ids.document, "notes.txt", b"text", second)
                assert embed.await_count == 1
            finally:
                release.set()
                await task
    async with ids.factory() as db:
        document = await db.get(Document, ids.document)
        assert document.attempts == 1
        assert document.status == DocumentStatus.READY


async def test_expired_attempt_cannot_overwrite_recovered_document(committed_records):
    ids = committed_records
    entered, release = asyncio.Event(), asyncio.Event()
    calls = 0
    async def embed(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            entered.set()
            await release.wait()
            return [[0.1] * 1536]
        return [[0.2] * 1536]
    async with ids.factory() as first, ids.factory() as second:
        with patch("app.services.document_service.embed", new=AsyncMock(side_effect=embed)):
            task = asyncio.create_task(run_document_processing(ids.document, "notes.txt", b"stale", first))
            try:
                await asyncio.wait_for(entered.wait(), 5)
                await second.execute(update(Document).where(Document.id == ids.document).values(
                    lease_expires_at=datetime.now(UTC) - timedelta(seconds=1)))
                await second.commit()
                await run_document_processing(ids.document, "notes.txt", b"recovered", second)
            finally:
                release.set()
                await task
    async with ids.factory() as db:
        chunks = (await db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == ids.document))).all()
        assert [chunk.content for chunk in chunks] == ["recovered"]
        assert (await db.get(Document, ids.document)).attempts == 2


async def test_concurrent_messages_are_rejected_and_external_call_has_no_transaction(committed_records):
    ids = committed_records
    entered, release = asyncio.Event(), asyncio.Event()
    async with ids.factory() as first, ids.factory() as second:
        async def slow_chat(**kwargs):
            assert not first.in_transaction()
            entered.set()
            await release.wait()
            return {"content": "reply", "tokens_output": 1, "model": "fake"}
        with patch("app.services.conversation_service.chat", new=AsyncMock(side_effect=slow_chat)):
            task = asyncio.create_task(send_message(ids.assistant, ids.conversation, ids.user, "first", first))
            try:
                await asyncio.wait_for(entered.wait(), 5)
                with pytest.raises(ResourceBusyError):
                    await send_message(ids.assistant, ids.conversation, ids.user, "second", second)
            finally:
                release.set()
                await task
    async with ids.factory() as db:
        messages = (await db.scalars(select(Message).where(Message.conversation_id == ids.conversation))).all()
        assert len(messages) == 2
        assert (await db.get(Conversation, ids.conversation)).generation_token is None


async def test_real_worker_runs_sequential_tasks_and_recovery_dispatch(committed_records):
    ids = committed_records
    async with ids.factory() as db:
        second = Document(assistant_id=ids.assistant, filename="second.txt", original_content=b"second")
        db.add(second)
        await db.commit()
        second_id = second.id
    queue = f"repair-test-{uuid4()}"
    async def fake_embed(texts, **kwargs):
        return [[0.1] * settings.EMBEDDING_DIM for _ in texts]
    # A real consumer receives serialized broker messages. Each task calls asyncio.run.
    with (
        patch("app.services.document_service.embed", new=AsyncMock(side_effect=fake_embed)),
        start_worker(celery_app, pool="solo", concurrency=1, queues=[queue],
                     perform_ping_check=False, shutdown_timeout=15),
    ):
        for document_id in (ids.document, second_id):
            process_document_task.apply_async(args=[str(document_id)], queue=queue)
            for _ in range(100):
                async with ids.factory() as db:
                    status = (await db.get(Document, document_id)).status
                if status == DocumentStatus.READY:
                    break
                await asyncio.sleep(0.05)
            assert status == DocumentStatus.READY
    with patch("app.tasks.document_tasks.process_document_task.apply_async") as publish:
        async with ids.factory() as db:
            await db.execute(update(Document).where(Document.id == ids.document).values(status=DocumentStatus.PENDING))
            await db.commit()
        await asyncio.to_thread(recover_documents_task.run)
        assert any(call.kwargs["args"] == [str(ids.document)] for call in publish.call_args_list)
