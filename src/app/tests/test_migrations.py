import asyncio
import os
import sys
from uuid import uuid4

import asyncpg
import pytest
from sqlalchemy.engine import make_url

from app.core.config import settings


async def test_fresh_and_existing_data_upgrade_preserve_schema_and_indexes():
    if os.environ.get("TEST_ALLOW_SCHEMA_RESET") != "1":
        pytest.fail("Migration tests require explicit disposable-database opt-in")
    base_url = make_url(settings.DATABASE_TEST_URL)
    admin = await asyncpg.connect(base_url.set(drivername="postgresql").render_as_string(hide_password=False))
    name = f"shion_migration_{uuid4().hex}"
    await admin.execute(f'CREATE DATABASE "{name}"')
    target = base_url.set(database=name)
    env = dict(os.environ, DATABASE_URL=target.render_as_string(hide_password=False))
    async def alembic(*args):
        proc = await asyncio.create_subprocess_exec(sys.executable, "-m", "alembic", *args,
            env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        output, _ = await proc.communicate()
        assert proc.returncode == 0, output.decode()
    async def connect():
        return await asyncpg.connect(target.set(drivername="postgresql").render_as_string(hide_password=False))
    try:
        await alembic("upgrade", "head")
        conn = await connect()
        try:
            assert await conn.fetchval("SELECT format_type(atttypid, atttypmod) FROM pg_attribute WHERE attrelid = 'document_chunks'::regclass AND attname = 'embedding'") == "vector(1536)"
            assert await conn.fetchval("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_document_chunks_embedding_hnsw'")
        finally:
            await conn.close()
        await alembic("downgrade", "baff9cff71dd")
        conn = await connect()
        doc_id = uuid4()
        try:
            user_id, assistant_id = uuid4(), uuid4()
            await conn.execute("INSERT INTO users VALUES ($1, $2, 'unused', 'Test User', true, now())", user_id, f"{user_id}@test.com")
            await conn.execute("INSERT INTO assistants (id,user_id,name,system_prompt,is_active,created_at,updated_at) VALUES ($1,$2,'test','help',true,now(),now())", assistant_id, user_id)
            await conn.execute("INSERT INTO documents (id,assistant_id,filename,status,created_at,original_content) VALUES ($1,$2,'legacy.txt','READY',now(),$3)", doc_id, assistant_id, b"legacy content")
            await conn.execute("INSERT INTO document_chunks (id,document_id,content,chunk_index,embedding,created_at) VALUES ($1,$2,'legacy content',0,$3,now())", uuid4(), doc_id, str([0.1] * 1536))
        finally:
            await conn.close()
        await alembic("upgrade", "head")
        await alembic("check")
        conn = await connect()
        try:
            row = await conn.fetchrow("SELECT original_content, embedding_model, attempts FROM documents WHERE id=$1", doc_id)
            assert row["original_content"] == b"legacy content"
            assert row["embedding_model"] is None
            assert row["attempts"] == 0
            assert await conn.fetchval("SELECT count(*) FROM document_chunks WHERE document_id=$1", doc_id) == 1
            assert await conn.fetchval("SELECT count(*) FROM pg_constraint WHERE conname='uq_document_chunk_index'") == 1
        finally:
            await conn.close()
    finally:
        await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        await admin.close()
