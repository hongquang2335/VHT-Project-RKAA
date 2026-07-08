from __future__ import annotations

import json
import logging

from rkaa.core.logging import (
    JsonFormatter,
    configure_logging,
    get_correlation_id,
    set_correlation_id,
)


def test_json_logging_contains_required_fields() -> None:
    set_correlation_id("corr-123")
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="rkaa.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello world",
        args=(),
        exc_info=None,
    )

    payload = json.loads(formatter.format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "rkaa.test"
    assert payload["message"] == "hello world"
    assert payload["correlation_id"] == "corr-123"
    assert "timestamp" in payload


def test_logging_redacts_sensitive_content() -> None:
    set_correlation_id("corr-456")
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="rkaa.test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="password=super-secret-value",
        args=(),
        exc_info=None,
    )

    payload = json.loads(formatter.format(record))

    assert payload["message"] == "[REDACTED SENSITIVE CONTENT]"


def test_configure_logging_applies_configured_level() -> None:
    configure_logging("debug")

    assert logging.getLogger().level == logging.DEBUG


def test_correlation_id_is_stored_in_context() -> None:
    set_correlation_id("corr-789")

    assert get_correlation_id() == "corr-789"
