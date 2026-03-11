"""
presentation.errors

Maps domain and application exceptions to HTTP responses.

Rules:
    ValueError from a use case    → 400 Bad Request
    KeyError / LookupError        → 404 Not Found
    NotImplementedError           → 501 (should never reach prod)
    Everything else               → 500 Internal Server Error

Register these handlers in app.py. Do not repeat try/except
blocks in individual routers — let errors propagate here.
"""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )


async def lookup_error_handler(request: Request, exc: LookupError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again."},
    )
