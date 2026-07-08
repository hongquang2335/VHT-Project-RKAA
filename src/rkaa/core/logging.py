"""Structured JSON logging for RKAA."""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from uuid import uuid4

_SENSITIVE_KEYS = ("password", "token", "credential", "secret")
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")


class JsonFormatter(logging.Formatter):
    """Render log records as JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": _sanitize_message(record.getMessage()),
            "correlation_id": get_correlation_id(),
        }
        return json.dumps(payload, ensure_ascii=True)


def _sanitize_message(message: str) -> str:
    lowered = message.lower()
    if not any(key in lowered for key in _SENSITIVE_KEYS):
        return message
    return "[REDACTED SENSITIVE CONTENT]"


def get_correlation_id() -> str:
    return _correlation_id.get()


def set_correlation_id(correlation_id: str) -> None:
    _correlation_id.set(correlation_id)


def new_correlation_id() -> str:
    return uuid4().hex


def configure_logging(level: str) -> None:
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root_logger.addHandler(handler)
    root_logger.setLevel(level.upper())
