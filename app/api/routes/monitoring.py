"""Monitoring and metrics endpoints.

Provides Prometheus metrics endpoint for observability.
"""

import hmac
import logging
import os

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response

from app.core.config import get_settings
from app.core.observability import metrics_endpoint

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Monitoring"])


@router.get("/metrics")
async def get_metrics(request: Request) -> Response:
    """Prometheus metrics endpoint for scraping.

    SECURITY: Requires X-Metrics-Token header for authentication.

    Returns application metrics in Prometheus text format.
    """
    settings = get_settings()
    expected_token = getattr(settings, "metrics_token", None) or os.getenv("METRICS_TOKEN")
    if not expected_token:
        logger.error(
            "Metrics endpoint accessed but METRICS_TOKEN not configured",
            extra={"security_event": True, "event_type": "METRICS_NOT_CONFIGURED"},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Metrics token not configured. Set METRICS_TOKEN environment variable.",
        )

    provided_token = request.headers.get("X-Metrics-Token")
    if not hmac.compare_digest(provided_token or "", expected_token):
        logger.warning(
            "Unauthorized metrics access attempt",
            extra={
                "security_event": True,
                "event_type": "METRICS_ACCESS_DENIED",
                "client_ip": request.client.host if request.client else "unknown",
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid metrics token",
        )

    return metrics_endpoint()
