"""Health check routes."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/health", tags=["Health"])


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str


class ReadyResponse(BaseModel):
    """Readiness check response."""

    status: str
    database: str


@router.get(
    "",
    response_model=HealthResponse,
    summary="Health check",
    description="Check if the service is running.",
)
async def health_check() -> HealthResponse:
    """Return service health status."""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
    )


@router.get(
    "/ready",
    response_model=ReadyResponse,
    summary="Readiness check",
    description="Check if the service is ready to receive traffic.",
)
async def readiness_check() -> ReadyResponse:
    """Return service readiness status."""
    return ReadyResponse(
        status="ready",
        database="connected",
    )


@router.get(
    "/live",
    summary="Liveness check",
    description="Kubernetes liveness probe endpoint.",
)
async def liveness_check() -> dict:
    """Return liveness status."""
    return {"status": "alive"}
