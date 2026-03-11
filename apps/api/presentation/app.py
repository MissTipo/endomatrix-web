"""
presentation.app

FastAPI application factory.

Usage:
    uvicorn presentation.app:app --reload

The app is created by calling create_app() so it can be instantiated
in tests with different settings without side effects at import time.
The module-level `app` object is what uvicorn points at.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from presentation.errors import (
    lookup_error_handler,
    not_implemented_handler,
    unhandled_error_handler,
    value_error_handler,
)
from presentation.routers import (
    baseline_router,
    home_router,
    insights_router,
    logs_router,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="EndoMatrix API",
        description=(
            "Cycle-aware symptom pattern interpreter. "
            "Pattern recognition and interpretation — not diagnosis."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS — allow the Next.js PWA and local dev
    # Tighten origins before production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "https://endomatrixlabs.tech",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Error handlers — registered before routers so they cover all routes
    app.add_exception_handler(ValueError, value_error_handler)
    app.add_exception_handler(KeyError, lookup_error_handler)
    app.add_exception_handler(LookupError, lookup_error_handler)
    app.add_exception_handler(NotImplementedError, not_implemented_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    # Routers
    app.include_router(baseline_router)
    app.include_router(logs_router)
    app.include_router(home_router)
    app.include_router(insights_router)

    # Health check — used by Cloud Run and Docker healthchecks
    @app.get("/health", tags=["ops"], include_in_schema=False)
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
