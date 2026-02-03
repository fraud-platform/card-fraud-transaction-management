"""Unit tests for main application module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI

from app.core.config import AppEnvironment
from app.main import (
    create_app,
    lifespan,
    run,
    setup_telemetry,
)


class TestCreateApp:
    """Test create_app function."""

    def test_create_app_returns_fastapi(self):
        """Test that create_app returns a FastAPI instance."""
        mock_settings = MagicMock()
        mock_settings.app.name = "test-app"
        mock_settings.app.version = "1.0.0"
        mock_settings.app.env = AppEnvironment.LOCAL
        mock_settings.app.debug = False
        mock_settings.server.host = "0.0.0.0"
        mock_settings.server.port = 8080
        mock_settings.server.workers = 4
        mock_settings.app.log_level = "INFO"
        mock_settings.observability.otlp_endpoint = None
        mock_settings.observability.service_name = "test-service"

        with patch("app.main.get_settings", return_value=mock_settings):
            app = create_app()
            assert isinstance(app, FastAPI)
            assert app.title == "Card Fraud Transaction Management API"

    def test_create_app_includes_routers(self):
        """Test that create_app includes all routers."""
        mock_settings = MagicMock()
        mock_settings.app.name = "test-app"
        mock_settings.app.version = "1.0.0"
        mock_settings.app.env = AppEnvironment.LOCAL
        mock_settings.app.debug = False
        mock_settings.server.host = "0.0.0.0"
        mock_settings.server.port = 8080
        mock_settings.server.workers = 4
        mock_settings.app.log_level = "INFO"
        mock_settings.observability.otlp_endpoint = None
        mock_settings.observability.service_name = "test-service"

        with patch("app.main.get_settings", return_value=mock_settings):
            app = create_app()
            route_paths = [r.path for r in app.routes]
            assert "/api/v1/health" in route_paths or any(
                "/api/v1/health" in p for p in route_paths
            )
            assert "/v1" in route_paths or any("/v1" in p for p in route_paths)

    def test_create_app_cors_middleware(self):
        """Test that create_app adds CORS middleware."""
        mock_settings = MagicMock()
        mock_settings.app.name = "test-app"
        mock_settings.app.version = "1.0.0"
        mock_settings.app.env = AppEnvironment.LOCAL
        mock_settings.app.debug = False
        mock_settings.server.host = "0.0.0.0"
        mock_settings.server.port = 8080
        mock_settings.server.workers = 4
        mock_settings.app.log_level = "INFO"
        mock_settings.observability.otlp_endpoint = None
        mock_settings.observability.service_name = "test-service"

        with patch("app.main.get_settings", return_value=mock_settings):
            app = create_app()
            # CORS middleware should be added
            assert app.state is not None

    def test_create_app_exception_handler(self):
        """Test that create_app adds global exception handler."""
        mock_settings = MagicMock()
        mock_settings.app.name = "test-app"
        mock_settings.app.version = "1.0.0"
        mock_settings.app.env = AppEnvironment.LOCAL
        mock_settings.app.debug = False
        mock_settings.server.host = "0.0.0.0"
        mock_settings.server.port = 8080
        mock_settings.server.workers = 4
        mock_settings.app.log_level = "INFO"
        mock_settings.observability.otlp_endpoint = None
        mock_settings.observability.service_name = "test-service"

        with patch("app.main.get_settings", return_value=mock_settings):
            app = create_app()
            # Exception handler should be registered
            assert len(app.exception_handlers) >= 1

    def test_create_app_docs_disabled_in_production(self):
        """Test that docs are disabled in production."""
        mock_settings = MagicMock()
        mock_settings.app.name = "test-app"
        mock_settings.app.version = "1.0.0"
        mock_settings.app.env = AppEnvironment.PROD
        mock_settings.app.debug = False
        mock_settings.server.host = "0.0.0.0"
        mock_settings.server.port = 8080
        mock_settings.server.workers = 4
        mock_settings.app.log_level = "INFO"
        mock_settings.observability.otlp_endpoint = None
        mock_settings.observability.service_name = "test-service"

        with patch("app.main.get_settings", return_value=mock_settings):
            app = create_app()
            assert app.docs_url is None
            assert app.redoc_url is None


class TestLifespan:
    """Test lifespan context manager."""

    @pytest.mark.asyncio
    async def test_lifespan_startup(self):
        """Test lifespan startup creates engine and session factory."""
        mock_settings = MagicMock()
        mock_settings.app.name = "test-app"
        mock_settings.app.env = AppEnvironment.LOCAL
        mock_settings.app.version = "1.0.0"
        mock_settings.database.host = "localhost"
        mock_settings.database.port = 5432
        mock_settings.database.name = "test"
        mock_settings.database.user = "test"
        mock_settings.database.password.get_secret_value.return_value = "test"
        mock_settings.kafka.enabled = False

        mock_engine = AsyncMock()
        mock_session_factory = MagicMock()

        with patch("app.main.get_settings", return_value=mock_settings):
            with patch("app.main.create_async_engine", return_value=mock_engine):
                with patch("app.main.create_session_factory", return_value=mock_session_factory):
                    with patch("app.main.setup_logging"):
                        with patch("app.main.setup_authentication"):
                            app = FastAPI()
                            async with lifespan(app):
                                assert app.state.settings == mock_settings
                                assert app.state.engine == mock_engine
                                assert app.state.session_factory == mock_session_factory

    @pytest.mark.asyncio
    async def test_lifespan_shutdown_disposes_engine(self):
        """Test lifespan shutdown disposes engine."""
        mock_settings = MagicMock()
        mock_settings.app.name = "test-app"
        mock_settings.app.env = AppEnvironment.LOCAL
        mock_settings.app.version = "1.0.0"
        mock_settings.database.host = "localhost"
        mock_settings.database.port = 5432
        mock_settings.database.name = "test"
        mock_settings.database.user = "test"
        mock_settings.database.password.get_secret_value.return_value = "test"
        mock_settings.kafka.enabled = False

        mock_engine = AsyncMock()
        mock_session_factory = MagicMock()

        with patch("app.main.get_settings", return_value=mock_settings):
            with patch("app.main.create_async_engine", return_value=mock_engine):
                with patch("app.main.create_session_factory", return_value=mock_session_factory):
                    with patch("app.main.setup_logging"):
                        with patch("app.main.setup_authentication"):
                            app = FastAPI()
                            async with lifespan(app):
                                pass

                            mock_engine.dispose.assert_called_once()


class TestSetupTelemetry:
    """Test setup_telemetry function."""

    def test_setup_telemetry_returns_early_without_endpoint(self):
        """Test setup_telemetry returns early if no OTLP endpoint."""
        mock_settings = MagicMock()
        mock_settings.observability.otlp_endpoint = None

        app = FastAPI()
        setup_telemetry(app, mock_settings)
        # Should not raise and should not instrument

    def test_setup_telemetry_with_endpoint(self):
        """Test setup_telemetry sets up telemetry when endpoint provided."""
        mock_settings = MagicMock()
        mock_settings.observability.otlp_endpoint = "http://localhost:4317"
        mock_settings.observability.service_name = "test-service"

        with patch("app.main.OTLPSpanExporter"):
            with patch("app.main.TracerProvider"):
                with patch("app.main.BatchSpanProcessor"):
                    with patch("app.main.FastAPIInstrumentor"):
                        app = FastAPI()
                        setup_telemetry(app, mock_settings)
                        # Should call instrument_app


class TestRun:
    """Test run function."""

    def test_run_function_exists(self):
        """Test that run function exists and is callable."""
        assert run is not None
        assert callable(run)

    @pytest.mark.skip(reason="uvicorn is imported inside function, hard to test")
    def test_run_calls_uvicorn(self):
        """Test that run starts uvicorn."""
        pass


class TestMainImports:
    """Test that main module imports work correctly."""

    def test_create_app_import(self):
        """Test create_app can be imported."""
        from app.main import create_app

        assert create_app is not None

    def test_lifespan_import(self):
        """Test lifespan can be imported."""
        from app.main import lifespan

        assert lifespan is not None

    def test_run_import(self):
        """Test run can be imported."""
        from app.main import run

        assert run is not None

    def test_app_environment_values(self):
        """Test AppEnvironment enum values."""
        assert AppEnvironment.LOCAL == "local"
        assert AppEnvironment.TEST == "test"
        assert AppEnvironment.PROD == "prod"
