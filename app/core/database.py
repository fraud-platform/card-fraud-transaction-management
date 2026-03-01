"""Database connection and session management."""

import logging
from collections.abc import AsyncGenerator
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.ext.asyncio import (
    create_async_engine as sqlalchemy_create_async_engine,
)
from sqlalchemy.orm import declarative_base

from app.core.config import DatabaseConfig

logger = logging.getLogger(__name__)

Base = declarative_base()

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _normalize_asyncpg_runtime_url(url: str) -> tuple[str, bool | None]:
    """Strip unsupported asyncpg query params and map sslmode to asyncpg ssl arg."""
    split = urlsplit(url)
    ssl_mode: str | None = None
    filtered: list[tuple[str, str]] = []
    for key, value in parse_qsl(split.query, keep_blank_values=True):
        if key.lower() == "sslmode":
            ssl_mode = value
            continue
        filtered.append((key, value))

    normalized_url = urlunsplit(
        (
            split.scheme,
            split.netloc,
            split.path,
            urlencode(filtered, doseq=True),
            split.fragment,
        )
    )

    ssl_enabled: bool | None = None
    if isinstance(ssl_mode, str):
        mode = ssl_mode.strip().lower()
        if mode in {"require", "verify-ca", "verify-full"}:
            ssl_enabled = True
        elif mode in {"disable", "allow", "prefer"}:
            ssl_enabled = False

    return normalized_url, ssl_enabled


def create_async_engine(config: DatabaseConfig) -> AsyncEngine:
    """Create async database engine."""
    runtime_url, ssl_enabled = _normalize_asyncpg_runtime_url(config.async_url)
    connect_args: dict[str, Any] = {
        "server_settings": {"timezone": "UTC"},
    }
    if ssl_enabled is not None:
        connect_args["ssl"] = ssl_enabled

    engine = sqlalchemy_create_async_engine(
        runtime_url,
        echo=config.echo,
        pool_size=config.pool_size,
        max_overflow=config.max_overflow,
        pool_timeout=config.pool_timeout,
        pool_recycle=config.pool_recycle,
        pool_pre_ping=True,
        # For asyncpg, set server timezone (timeout parameter removed as it causes
        # Windows proactor event loop issues during connection pool cleanup)
        connect_args=connect_args,
    )
    logger.info(
        "Database engine created",
        extra={
            "host": config.host,
            "port": config.port,
            "database": config.name,
        },
    )
    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create async session factory."""
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


def get_engine() -> AsyncEngine:
    """Get or create the global database engine."""
    global _engine
    if _engine is None:
        from app.core.config import get_settings

        settings = get_settings()
        _engine = create_async_engine(settings.database)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the global session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = create_session_factory(get_engine())
    return _session_factory


async def reset_engine() -> None:
    """Reset the database engine and session factory.

    Useful for tests to ensure fresh connections.
    """
    global _engine, _session_factory

    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Get database session as async context manager."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
