import uuid
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import NullPool

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


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session():
    """Una conexión y transacción externa por test. Los commit() que
    haga el código de la app usan SAVEPOINT internamente (gracias a
    join_transaction_mode) en vez de cerrar esta transacción externa.
    Al final, el rollback() descarta todo de una."""
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
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(client):
    """Registra un usuario y devuelve sus datos + password en texto plano
    (lo necesitás para el test de login)."""
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
    """Loguea al test_user y devuelve el header listo para usar."""
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
    """Un segundo usuario completamente distinto, para los tests
    de ownership: 'usuario A no puede tocar recursos de usuario B'."""
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
    """Un asistente creado por el usuario principal (test_user)."""
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
