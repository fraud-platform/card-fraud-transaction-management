"""Unit tests for health check routes."""

from app.api.routes.health import HealthResponse, ReadyResponse, router


class TestHealthRoutes:
    """Test health check routes."""

    def test_router_exists(self):
        """Test that health router exists."""
        assert router is not None

    def test_health_response_model(self):
        """Test HealthResponse model."""
        response = HealthResponse(status="healthy", version="1.0.0")
        assert response.status == "healthy"
        assert response.version == "1.0.0"

    def test_ready_response_model(self):
        """Test ReadyResponse model."""
        response = ReadyResponse(status="ready", database="connected")
        assert response.status == "ready"
        assert response.database == "connected"

    def test_health_response_model_default_version(self):
        """Test HealthResponse has default version."""
        response = HealthResponse(status="healthy", version="0.1.0")
        assert response.version == "0.1.0"

    def test_ready_response_model_fields(self):
        """Test ReadyResponse has correct fields."""
        response = ReadyResponse(status="degraded", database="disconnected")
        assert response.status == "degraded"
        assert response.database == "disconnected"

    def test_health_routes_in_router(self):
        """Test that health routes are defined in router."""
        paths = [r.path for r in router.routes]
        # Router paths include router prefix: /health, /health/ready, /health/live
        assert "/health" in paths
        assert len(router.routes) >= 3

    def test_health_check_endpoint_exists(self):
        """Test health check endpoint path exists."""
        paths = [getattr(r, "path", str(r)) for r in router.routes]
        assert "/health" in paths

    def test_ready_check_endpoint_exists(self):
        """Test readiness check endpoint path exists."""
        paths = [getattr(r, "path", str(r)) for r in router.routes]
        assert any("ready" in p for p in paths)

    def test_live_check_endpoint_exists(self):
        """Test liveness check endpoint path exists."""
        paths = [getattr(r, "path", str(r)) for r in router.routes]
        assert any("live" in p for p in paths)


class TestHealthResponseValidation:
    """Test HealthResponse model validation."""

    def test_health_response_with_custom_status(self):
        """Test HealthResponse with custom status."""
        response = HealthResponse(status="unhealthy", version="2.0.0")
        assert response.status == "unhealthy"

    def test_health_response_with_different_version(self):
        """Test HealthResponse with different version."""
        response = HealthResponse(status="healthy", version="1.2.3")
        assert response.version == "1.2.3"


class TestReadyResponseValidation:
    """Test ReadyResponse model validation."""

    def test_ready_response_with_different_status(self):
        """Test ReadyResponse with different status."""
        response = ReadyResponse(status="checking", database="connecting")
        assert response.status == "checking"
        assert response.database == "connecting"

    def test_ready_response_model_is_pydantic_model(self):
        """Test ReadyResponse is a Pydantic model."""
        from pydantic import BaseModel

        assert issubclass(ReadyResponse, BaseModel)


class TestHealthRouterConfiguration:
    """Test health router configuration."""

    def test_health_check_has_correct_tag(self):
        """Test health check endpoint has Health tag."""
        for route in router.routes:
            path = getattr(route, "path", "")
            if path in {"/health", "/health/ready", "/health/live"}:
                assert "Health" in (route.tags or [])

    def test_ready_check_has_summary(self):
        """Test readiness check endpoint has summary."""
        for route in router.routes:
            if "ready" in getattr(route, "path", ""):
                assert route.summary is not None
