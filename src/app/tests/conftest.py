import uuid
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import NullPool
from sqlalchemy import text
import asyncpg
from app.app import app
from app.core.config import settings
from app.core.dependencies import get_db
from app.db.session import Base
from app.core.redis import close_redis

# Engine dedicado a los tests, apuntando a la DB de test
test_engine = create_async_engine(
    settings.DATABASE_TEST_URL,
    echo=False,
    poolclass=NullPool,
)

async def _ensure_vector_extension():

    dsn = settings.DATABASE_TEST_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    finally:
        await conn.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    await _ensure_vector_extension()  

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session():

    connection = await test_engine.connect()
    trans = await connection.begin()

    session = AsyncSession(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    yield session

    await session.close()
    await trans.rollback()
    await connection.close()


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        try:
            yield db_session
        except Exception:
            await db_session.rollback()
            raise
        
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(client):

    payload = {
        "email": f"user_{uuid.uuid4().hex[:8]}@test.com",
        "password": "TestPass1234",
        "full_name": "Test User",
    }
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 201
    return {**response.json(), "password": payload["password"]}


@pytest_asyncio.fixture
async def auth_headers(client, test_user):
    response = await client.post(
        "/auth/login",
        data={
            "username": test_user["email"],
            "password": test_user["password"],
        },
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def other_user_headers(client):

    payload = {
        "email": f"other_{uuid.uuid4().hex[:8]}@test.com",
        "password": "OtherPass1234",
        "full_name": "Other User",
    }
    await client.post("/auth/register", json=payload)
    response = await client.post(
        "/auth/login",
        data={
            "username": payload["email"],
            "password": payload["password"],
        },
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def test_assistant(client, auth_headers):
    response = await client.post(
        "/assistants",
        json={"name": "Test Assistant", "system_prompt": "You are helpful."},
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def cleanup_redis():
    yield
    await close_redis()

    
from unittest.mock import AsyncMock, patch

@pytest_asyncio.fixture
async def test_document(client, auth_headers, test_assistant):

    fake_embeddings = [[0.1] * 1536]
    with patch("app.services.document_service.embed", new=AsyncMock(return_value=fake_embeddings)):
        response = await client.post(
            f"/assistants/{test_assistant['id']}/documents",
            files={"file": ("notes.txt", b"El horario de atencion es de 9 a 18.", "text/plain")},
            headers=auth_headers,
        )
    assert response.status_code == 201
    return response.json()