"""Logging configuration and utilities."""

import logging
import sys
from typing import Any

import structlog
from structlog.processors import JSONRenderer, TimeStamper, add_log_level
from structlog.stdlib import add_logger_name, filter_by_level

from app.core.config import Settings


def setup_logging(settings: Settings) -> None:
    """Configure structured logging."""
    log_level = settings.app.log_level.upper()

    processors: list[Any] = [
        filter_by_level,
        add_log_level,
        add_logger_name,
        TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.observability.log_record_format == "json":
        processors.append(JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(
            file=sys.stdout,
        ),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger for a module."""
    return structlog.get_logger(name)


class LoggerMixin:
    """Mixin providing logger access."""

    @property
    def logger(self) -> structlog.BoundLogger:
        """Get logger for this instance."""
        return get_logger(self.__class__.__module__)
