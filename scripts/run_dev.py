#!/usr/bin/env python3
"""Run development server."""

from __future__ import annotations

import uvicorn


def main() -> None:
    """Start development server."""
    # Use factory pattern - app.main:create_app
    # Port 8002 per card-fraud-platform setup
    uvicorn.run(
        "app.main:create_app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        factory=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
