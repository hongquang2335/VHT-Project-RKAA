"""Global API error handlers for RKAA."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from rkaa.core.exceptions import AppError
from rkaa.core.logging import get_correlation_id

logger = logging.getLogger("rkaa.errors")


def _error_payload(
    *,
    error_code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "error_code": error_code,
        "message": message,
        "correlation_id": get_correlation_id(),
        "details": details or {},
    }


async def handle_validation_error(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_error_payload(
            error_code="VALIDATION_ERROR",
            message="Request validation failed.",
            details={"errors": exc.errors()},
        ),
    )


async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=404 if exc.error_code == "NOT_FOUND" else 400,
        content=_error_payload(
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
        ),
    )


async def handle_http_exception(_request: Request, exc: HTTPException) -> JSONResponse:
    if exc.status_code == 404:
        payload = _error_payload(
            error_code="NOT_FOUND",
            message="Resource not found.",
        )
    else:
        payload = _error_payload(
            error_code="HTTP_ERROR",
            message=str(exc.detail),
        )
    return JSONResponse(status_code=exc.status_code, content=payload)


async def handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled application error: %s", exc)
    return JSONResponse(
        status_code=500,
        content=_error_payload(
            error_code="INTERNAL_ERROR",
            message="An unexpected error occurred.",
        ),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(HTTPException, handle_http_exception)
    app.add_exception_handler(Exception, handle_unexpected_error)
