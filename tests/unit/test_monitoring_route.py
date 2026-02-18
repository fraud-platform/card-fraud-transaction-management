"""Unit tests for monitoring route security."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.monitoring import router


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


def test_metrics_endpoint_returns_500_when_token_missing(monkeypatch) -> None:
    from app.api.routes import monitoring

    class _Settings:
        metrics_token = None

    monkeypatch.setattr(monitoring, "get_settings", lambda: _Settings())

    client = TestClient(_build_app())
    response = client.get("/metrics")

    assert response.status_code == 500
    assert "Metrics token not configured" in response.json()["detail"]


def test_metrics_endpoint_returns_403_when_token_invalid(monkeypatch) -> None:
    from app.api.routes import monitoring

    class _Settings:
        metrics_token = "secret-token"

    monkeypatch.setattr(monitoring, "get_settings", lambda: _Settings())

    client = TestClient(_build_app())
    response = client.get("/metrics", headers={"X-Metrics-Token": "wrong-token"})

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid metrics token"


def test_metrics_endpoint_returns_200_with_valid_token(monkeypatch) -> None:
    from app.api.routes import monitoring

    class _Settings:
        metrics_token = "secret-token"

    monkeypatch.setattr(monitoring, "get_settings", lambda: _Settings())

    client = TestClient(_build_app())
    response = client.get("/metrics", headers={"X-Metrics-Token": "secret-token"})

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
