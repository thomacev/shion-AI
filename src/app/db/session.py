#async para las request de openai
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.core.config import settings
from typing import AsyncGenerator
import logging

#async
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True)

SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

Base = declarative_base()

#no se si agregarlo o no

"""async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session

logging.warning(f"DATABASE_URL = {settings.DATABASE_URL}")"""
