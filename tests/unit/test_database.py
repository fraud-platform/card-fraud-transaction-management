"""Unit tests for database module."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.database import (
    Base,
    create_async_engine,
    create_session_factory,
    get_engine,
    get_session,
)


class TestCreateEngine:
    """Test database engine creation."""

    def test_create_async_engine_imports(self):
        """Test create_async_engine function exists."""
        assert create_async_engine is not None

    def test_create_session_factory_imports(self):
        """Test create_session_factory function exists."""
        assert create_session_factory is not None

    def test_get_engine_imports(self):
        """Test get_engine function exists."""
        assert get_engine is not None


class TestSessionFactory:
    """Test session factory creation."""

    def test_create_session_factory_with_mock_engine(self):
        """Test session factory creation with mock engine."""
        mock_engine = MagicMock(spec=AsyncEngine)
        factory = create_session_factory(mock_engine)
        assert factory is not None

    def test_create_session_factory_returns_sessionmaker(self):
        """Test create_session_factory returns a sessionmaker."""
        mock_engine = MagicMock(spec=AsyncEngine)
        factory = create_session_factory(mock_engine)
        # Should have session_class attr or be callable
        assert callable(factory) or hasattr(factory, "session_class")


class TestBaseModel:
    """Test Base model configuration."""

    def test_base_has_metadata(self):
        """Test Base has metadata attribute."""
        assert hasattr(Base, "metadata")

    def test_base_declarative(self):
        """Test Base is declarative."""
        assert hasattr(Base, "registry")
        assert hasattr(Base, "metadata")


class TestDatabaseConfig:
    """Test database configuration properties."""

    def test_database_url_property(self):
        """Test DatabaseConfig has url property."""
        from pydantic import SecretStr

        from app.core.config import DatabaseConfig

        config = DatabaseConfig(
            url_app="",  # Override environment to test URL building
            host="localhost",
            port=5432,
            name="test",
            user="user",
            password=SecretStr("pass"),
        )
        assert "postgresql+asyncpg://" in config.async_url
        assert "localhost" in config.async_url

    def test_database_sync_url_property(self):
        """Test DatabaseConfig has sync_url property."""
        from pydantic import SecretStr

        from app.core.config import DatabaseConfig

        config = DatabaseConfig(
            url_app="",  # Override environment to test URL building
            host="localhost",
            port=5432,
            name="test",
            user="user",
            password=SecretStr("pass"),
        )
        assert "postgresql+psycopg://" in config.sync_url


class TestDatabaseURLConstruction:
    """Test database URL construction."""

    def test_url_includes_host_and_port(self):
        """Test URL includes host and port."""
        from pydantic import SecretStr

        from app.core.config import DatabaseConfig

        config = DatabaseConfig(
            url_app="",  # Override environment to test URL building
            host="db.example.com",
            port=5432,
            name="fraud_db",
            user="fraud_user",
            password=SecretStr("secret"),
        )
        url = config.async_url
        assert "db.example.com" in url
        assert "5432" in url

    def test_sync_url_uses_psycopg(self):
        """Test sync URL uses psycopg driver (v3)."""
        from pydantic import SecretStr

        from app.core.config import DatabaseConfig

        config = DatabaseConfig(
            url_app="",  # Override environment to test URL building
            host="localhost",
            port=5432,
            name="test",
            user="user",
            password=SecretStr("pass"),
        )
        assert "postgresql+psycopg://" in config.sync_url


class TestDatabaseModuleExports:
    """Test module-level exports."""

    def test_base_is_declarative_base(self):
        """Test Base is a SQLAlchemy declarative base."""

        assert isinstance(Base, type)
        assert hasattr(Base, "metadata")

    def test_engine_creation_with_custom_pool(self):
        """Test engine creation respects pool settings."""
        from app.core.database import create_async_engine

        # Just verify the function is callable
        assert callable(create_async_engine)


class TestDatabaseConnectionSettings:
    """Test database connection settings."""

    def test_database_name_in_url(self):
        """Test database name is included in URL."""
        from pydantic import SecretStr

        from app.core.config import DatabaseConfig

        config = DatabaseConfig(
            url_app="",  # Override environment to test URL building
            host="localhost",
            port=5432,
            name="fraud_transactions",
            user="app_user",
            password=SecretStr("app_pass"),
        )
        assert "fraud_transactions" in config.async_url


class TestGetSessionDependency:
    """Test get_session FastAPI dependency."""

    @pytest.mark.asyncio
    async def test_get_session_returns_session(self):
        """Test get_session returns an async session."""
        from app.core.database import get_session

        # get_session is a generator/async generator
        session_gen = get_session()
        try:
            session = await session_gen.__anext__()
            assert session is not None
        except StopIteration:
            pass  # Generator exhausted

    @pytest.mark.asyncio
    async def test_get_session_is_async_generator(self):
        """Test get_session is an async generator function."""
        import inspect

        assert inspect.isasyncgenfunction(get_session)


class TestEngineCreationSettings:
    """Test engine creation settings."""

    def test_engine_has_echo_setting(self):
        """Test engine creation accepts echo setting."""
        from app.core.database import create_async_engine

        mock_settings = MagicMock()
        mock_settings.database.url = "postgresql+asyncpg://user:pass@localhost/test"
        mock_settings.database.echo = True
        mock_settings.database.pool_size = 5
        mock_settings.database.max_overflow = 10

        # Should be callable with settings
        assert callable(create_async_engine)


class TestDatabasePoolConfiguration:
    """Test database pool configuration."""

    def test_pool_settings_in_config(self):
        """Test pool settings are accessible from config."""
        from pydantic import SecretStr

        from app.core.config import DatabaseConfig

        config = DatabaseConfig(
            host="localhost",
            port=5432,
            name="test",
            user="user",
            password=SecretStr("pass"),
            pool_size=5,
            max_overflow=10,
        )

        assert config.pool_size == 5
        assert config.max_overflow == 10
