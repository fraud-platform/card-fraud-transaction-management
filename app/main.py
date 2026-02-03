"""Card Fraud Transaction Management Service.

This service provides APIs for ingesting fraud decision events and querying
transaction data. Uses PostgreSQL with the fraud_gov schema.
"""

import logging
from asyncio import Task
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.api.routes.bulk import router as bulk_router
from app.api.routes.cases import router as cases_router
from app.api.routes.decision_events import router as decision_events_router
from app.api.routes.health import router as health_router
from app.api.routes.notes import router as notes_router
from app.api.routes.reviews import router as reviews_router
from app.api.routes.worklist import router as worklist_router
from app.core.auth import setup_authentication
from app.core.config import AppEnvironment, Settings, get_settings
from app.core.database import create_async_engine, create_session_factory
from app.core.errors import TransactionManagementError, get_status_code
from app.core.logging import setup_logging
from app.ingestion.kafka_consumer import start_kafka_consumer, stop_kafka_consumer

logger = logging.getLogger(__name__)

# API version prefix
API_V1_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan context manager."""
    settings = get_settings()

    logger.info(
        "Starting Card Fraud Transaction Management Service",
        extra={
            "app": settings.app.name,
            "env": settings.app.env,
            "version": settings.app.version,
        },
    )

    engine = create_async_engine(settings.database)
    session_factory = create_session_factory(engine)

    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory

    setup_logging(settings)
    setup_authentication(settings)

    kafka_task: Task[Any] | None = None
    if settings.app.env != AppEnvironment.TEST and settings.kafka.enabled:
        kafka_task = await start_kafka_consumer(settings, session_factory)

    yield

    if kafka_task:
        await stop_kafka_consumer()

    await engine.dispose()

    logger.info("Card Fraud Transaction Management Service stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Card Fraud Transaction Management API",
        description=(
            "API for ingesting fraud decision events and querying transaction data. "
            "Uses PostgreSQL with the fraud_gov schema (shared with card-fraud-rule-management)."
        ),
        version=settings.app.version,
        lifespan=lifespan,
        docs_url="/docs" if settings.app.env != AppEnvironment.PROD else None,
        redoc_url="/redoc" if settings.app.env != AppEnvironment.PROD else None,
        openapi_url="/openapi.json" if settings.app.env != AppEnvironment.PROD else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.security.cors_allowed_origins,
        allow_credentials=settings.security.cors_allow_credentials,
        allow_methods=settings.security.cors_allow_methods,
        allow_headers=settings.security.cors_allow_headers,
    )

    app.include_router(health_router, prefix=API_V1_PREFIX)
    app.include_router(decision_events_router, prefix=API_V1_PREFIX)
    app.include_router(reviews_router, prefix=API_V1_PREFIX)
    app.include_router(notes_router, prefix=API_V1_PREFIX)
    app.include_router(cases_router, prefix=API_V1_PREFIX)
    app.include_router(worklist_router, prefix=API_V1_PREFIX)
    app.include_router(bulk_router, prefix=API_V1_PREFIX)

    setup_telemetry(app, settings)

    @app.exception_handler(TransactionManagementError)
    async def domain_error_handler(  # type: ignore[reportUnusedFunction]
        request: Request, exc: TransactionManagementError
    ) -> JSONResponse:
        """Handle domain-specific errors and return appropriate HTTP responses."""
        status_code = get_status_code(exc)
        return JSONResponse(
            status_code=status_code,
            content={"detail": exc.message, **({"errors": exc.details} if exc.details else {})},
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(  # type: ignore[reportUnusedFunction]
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Handle unexpected exceptions and return 500 error responses."""
        logger.exception(
            "Unhandled exception",
            extra={
                "path": request.url.path,
                "method": request.method,
                "error": str(exc),
            },
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    return app


def setup_telemetry(app: FastAPI, settings: Settings) -> None:
    """Setup OpenTelemetry instrumentation."""
    if not settings.observability.otlp_endpoint:
        return

    resource = Resource(
        attributes={
            SERVICE_NAME: settings.observability.service_name,
        }
    )

    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(
        endpoint=settings.observability.otlp_endpoint,
        insecure=settings.observability.otlp_insecure,
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)


def run() -> None:
    """Run the application using uvicorn."""
    import uvicorn

    settings = get_settings()

    uvicorn.run(
        "app.main:create_app",
        host=settings.server.host,
        port=settings.server.port,
        reload=settings.app.env == AppEnvironment.LOCAL,
        workers=1 if settings.app.env == AppEnvironment.LOCAL else settings.server.workers,
        log_level=settings.app.log_level.lower(),
    )


if __name__ == "__main__":
    run()
