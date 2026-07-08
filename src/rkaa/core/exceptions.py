"""Application exceptions for RKAA."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base application error with API-facing metadata."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}


class NotFoundError(AppError):
    """Raised when a resource cannot be found."""

    def __init__(self, message: str = "Resource not found.") -> None:
        super().__init__(message, error_code="NOT_FOUND")
