from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.core.config import settings

# 1. Obtenemos la URL y corregimos el esquema ANTES de crear el engine
database_url = settings.DATABASE_URL

if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# 2. Creamos el engine pasando la variable 'database_url' ya saneada
# Recommendation: usar echo=False en producción para no saturar los logs en Railway
engine = create_async_engine(database_url, echo=False)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()

async def check_embedding_schema():
    from sqlalchemy import text
    async with engine.connect() as conn:
        dimension = await conn.scalar(text(
            "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
            "WHERE attrelid = to_regclass('document_chunks') AND attname = 'embedding' AND NOT attisdropped"
        ))
    if dimension != f"vector({settings.EMBEDDING_DIM})":
        raise RuntimeError("Embedding schema mismatch; apply migrations and verify EMBEDDING_DIM")
