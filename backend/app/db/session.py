"""
Database session management using SQLAlchemy 2.0 async engine and sessionmaker.
Supports both PostgreSQL (asyncpg) and SQLite (aiosqlite) with lazy initialization.
"""
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def get_engine() -> AsyncEngine:
    """Lazily initialize and return the SQLAlchemy AsyncEngine singleton."""
    global _engine
    if _engine is None:
        engine_kwargs = {
            "echo": settings.DATABASE_ECHO,
            "future": True,
        }

        if "sqlite" in settings.DATABASE_URL:
            engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
        else:
            engine_kwargs["pool_size"] = settings.DATABASE_POOL_SIZE
            engine_kwargs["max_overflow"] = settings.DATABASE_MAX_OVERFLOW
            engine_kwargs["pool_pre_ping"] = True

        _engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Lazily initialize and return the async sessionmaker."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency generator yielding an async database session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
