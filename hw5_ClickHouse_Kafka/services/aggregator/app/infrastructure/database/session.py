from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


_engine = create_async_engine(
    settings.database_url,
    pool_size=settings.pg_pool_size,
    max_overflow=settings.pg_max_overflow,
    pool_pre_ping=True,
)

AsyncSessionFactory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    await _engine.dispose()
