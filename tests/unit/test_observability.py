"""Unit tests for observability middleware metrics labels."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry, generate_latest

from app.core.observability import Metrics, ObservabilityMiddleware


def _metric_lines(metrics_text: str, metric_name: str) -> list[str]:
    return [line for line in metrics_text.splitlines() if line.startswith(f"{metric_name}{{")]


def test_observability_uses_route_template_for_path_params() -> None:
    """Metrics route labels should use route templates, not raw path values."""
    app = FastAPI()
    registry = CollectorRegistry()
    metrics = Metrics(registry)
    app.add_middleware(ObservabilityMiddleware, metrics_instance=metrics)

    @app.get("/api/v1/transactions/{transaction_id}")
    async def get_transaction(transaction_id: str) -> dict[str, str]:
        return {"transaction_id": transaction_id}

    client = TestClient(app)
    response = client.get("/api/v1/transactions/0195f0fd-aaaa-7bbb-8ccc-0123456789ab")
    assert response.status_code == 200

    metrics_text = generate_latest(registry).decode("utf-8")
    request_lines = _metric_lines(metrics_text, "http_requests_total")

    assert any('route="/api/v1/transactions/{transaction_id}"' in line for line in request_lines)
    assert all(
        "/api/v1/transactions/0195f0fd-aaaa-7bbb-8ccc-0123456789ab" not in line
        for line in request_lines
    )


def test_observability_uses_bounded_label_for_unmatched_paths() -> None:
    """404 paths should map to a bounded fallback route label."""
    app = FastAPI()
    registry = CollectorRegistry()
    metrics = Metrics(registry)
    app.add_middleware(ObservabilityMiddleware, metrics_instance=metrics)

    @app.get("/api/v1/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)
    response = client.get("/api/v1/does-not-exist/12345")
    assert response.status_code == 404

    metrics_text = generate_latest(registry).decode("utf-8")
    request_lines = _metric_lines(metrics_text, "http_requests_total")

    assert any('route="__unmatched__"' in line for line in request_lines)
