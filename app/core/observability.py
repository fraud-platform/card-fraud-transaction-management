"""
Observability module for Transaction Management API.

Provides:
- Structured logging with JSON format and correlation IDs
- Request correlation ID (request_id) generation and propagation
- Prometheus metrics collection (HTTP, DB)
- Request tracking middleware for latency and status codes

Usage:
    from app.core.observability import (
        get_request_id,
        set_correlation_id,
        get_logger,
        metrics,
        metrics_endpoint,
    )
"""

import logging
import time
import uuid
from collections.abc import Callable
from contextvars import ContextVar

from fastapi import Request, Response
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Match
from starlette.types import ASGIApp

_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
_user_id_ctx: ContextVar[str] = ContextVar("user_id", default="")


def generate_request_id() -> str:
    """Generate a unique request ID for correlation."""
    return str(uuid.uuid4())


def get_request_id() -> str:
    """Get the current request ID from context."""
    return _request_id_ctx.get()


def set_correlation_id(request_id: str) -> None:
    """Set the correlation ID for the current request context."""
    _request_id_ctx.set(request_id)


def get_user_id() -> str:
    """Get the current user ID from context."""
    return _user_id_ctx.get()


def set_user_id(user_id: str) -> None:
    """Set the user ID for the current request context."""
    _user_id_ctx.set(user_id)


_registry = CollectorRegistry()


class Metrics:
    """
    Centralized metrics collection for the application.

    Metrics groups:
    - HTTP: Request rate, errors, latency
    - Database: Connection pool, query timing
    """

    def __init__(self, registry: CollectorRegistry) -> None:
        """Initialize all metrics with proper labels."""
        self.registry = registry

        self.http_requests_total = Counter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "route", "status_code"],
            registry=self.registry,
        )

        self.http_request_duration_seconds = Histogram(
            "http_request_duration_seconds",
            "HTTP request latency in seconds",
            ["method", "route"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
            registry=self.registry,
        )

        self.http_requests_in_progress = Gauge(
            "http_requests_in_progress",
            "HTTP requests currently in progress",
            ["method", "route"],
            registry=self.registry,
        )

        self.http_errors_total = Counter(
            "http_errors_total",
            "Total HTTP errors",
            ["error_type", "method", "route"],
            registry=self.registry,
        )

        self.db_pool_size = Gauge(
            "db_pool_size",
            "Database connection pool size",
            registry=self.registry,
        )

        self.db_pool_overflow = Gauge(
            "db_pool_overflow",
            "Database connection pool overflow",
            registry=self.registry,
        )

        self.db_pool_checked_out = Gauge(
            "db_pool_checked_out",
            "Database connections currently checked out",
            registry=self.registry,
        )

        self.db_query_duration_seconds = Histogram(
            "db_query_duration_seconds",
            "Database query duration in seconds",
            ["operation"],
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
            registry=self.registry,
        )

        self.db_queries_total = Counter(
            "db_queries_total",
            "Total database queries",
            ["operation", "status"],
            registry=self.registry,
        )


metrics = Metrics(_registry)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Middleware that adds observability to all requests."""

    def __init__(
        self,
        app: ASGIApp,
        metrics_instance: Metrics | None = None,
        skip_paths: list[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.metrics = metrics_instance or metrics
        self.skip_paths = set(
            skip_paths or ["/health", "/ready", "/live", "/metrics", "/docs", "/openapi.json"]
        )

    @staticmethod
    def _route_path(route: object | None) -> str | None:
        route_path = getattr(route, "path", None)
        if isinstance(route_path, str) and route_path:
            return route_path
        return None

    def _resolve_route_pattern(self, request: Request) -> str:
        route_path = self._route_path(request.scope.get("route"))
        if route_path:
            return route_path

        route_path = self._route_path(getattr(request.state, "route", None))
        if route_path:
            return route_path

        router = getattr(request.app, "router", None)
        routes = getattr(router, "routes", None)
        if not routes:
            return "__unmatched__"

        partial_match_path: str | None = None
        for route in routes:
            match, _ = route.matches(request.scope)
            route_path = self._route_path(route)
            if not route_path:
                continue
            if match == Match.FULL:
                return route_path
            if match == Match.PARTIAL and partial_match_path is None:
                partial_match_path = route_path

        return partial_match_path or "__unmatched__"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID", generate_request_id())
        set_correlation_id(request_id)

        route_pattern = self._resolve_route_pattern(request)

        is_skipped_path = any(route_pattern.startswith(path) for path in self.skip_paths)

        self.metrics.http_requests_in_progress.labels(
            method=request.method, route=route_pattern
        ).inc()

        start_time = time.time()

        try:
            response = await call_next(request)

            latency_ms = (time.time() - start_time) * 1000

            self.metrics.http_requests_total.labels(
                method=request.method,
                route=route_pattern,
                status_code=response.status_code,
            ).inc()
            self.metrics.http_request_duration_seconds.labels(
                method=request.method, route=route_pattern
            ).observe(latency_ms / 1000)

            response.headers["X-Request-ID"] = request_id

            if not is_skipped_path:
                logger = logging.getLogger("app.request")
                logger.info(
                    f"{request.method} {route_pattern}",
                    extra={
                        "method": request.method,
                        "route": route_pattern,
                        "status_code": response.status_code,
                        "latency_ms": round(latency_ms, 2),
                    },
                )

            return response

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000

            error_type = type(e).__name__
            self.metrics.http_requests_total.labels(
                method=request.method,
                route=route_pattern,
                status_code=500,
            ).inc()
            self.metrics.http_errors_total.labels(
                error_type=error_type, method=request.method, route=route_pattern
            ).inc()
            self.metrics.http_request_duration_seconds.labels(
                method=request.method, route=route_pattern
            ).observe(latency_ms / 1000)

            logger = logging.getLogger("app.request")
            logger.error(
                f"{request.method} {route_pattern} - {error_type}: {str(e)}",
                extra={
                    "method": request.method,
                    "route": route_pattern,
                    "status_code": 500,
                    "latency_ms": round(latency_ms, 2),
                    "error_type": error_type,
                    "error_message": str(e),
                },
                exc_info=True,
            )

            raise

        finally:
            self.metrics.http_requests_in_progress.labels(
                method=request.method, route=route_pattern
            ).dec()


class DBMetricsWrapper:
    """Wrapper to track database query metrics."""

    def __init__(self, metrics_instance: Metrics | None = None) -> None:
        self.metrics = metrics_instance or metrics

    def track(self, operation: str):
        from contextlib import contextmanager

        @contextmanager
        def _tracker():
            start = time.time()
            status = "success"

            class _Context:
                pass

            ctx = _Context()

            try:
                yield ctx
            except Exception:
                status = "error"
                raise
            finally:
                duration = time.time() - start
                self.metrics.db_query_duration_seconds.labels(operation=operation).observe(duration)
                self.metrics.db_queries_total.labels(operation=operation, status=status).inc()

        return _tracker()


db_metrics = DBMetricsWrapper()


def metrics_endpoint() -> Response:
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(_registry),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger with structured formatting configured."""
    return logging.getLogger(name)
