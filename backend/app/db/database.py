import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import exc
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.core.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=15,
    pool_pre_ping=True,
    pool_recycle=1800,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except exc.SQLAlchemyError as e:
            logger.error("Critical database error during transaction (fail-closed): %s", e)
            await session.rollback()
            raise
        except Exception as e:
            logger.exception("Unexpected database session failure: %s", e)
            await session.rollback()
            raise


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Session for background tasks and startup code outside request DI."""
    async with AsyncSessionLocal() as session:
        yield session
