from __future__ import annotations

from fastapi.testclient import TestClient

from rkaa.main import app


def test_validation_error_has_standard_shape() -> None:
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/test/items/not-an-int", headers={"X-Correlation-ID": "corr-1"})

    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"
    assert response.json()["message"] == "Request validation failed."
    assert response.json()["correlation_id"] == "corr-1"
    assert "errors" in response.json()["details"]


def test_not_found_error_has_standard_shape() -> None:
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/test/not-found", headers={"X-Correlation-ID": "corr-2"})

    assert response.status_code == 404
    assert response.json() == {
        "error_code": "NOT_FOUND",
        "message": "Resource not found.",
        "correlation_id": "corr-2",
        "details": {},
    }


def test_internal_error_has_standard_shape() -> None:
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/test/crash", headers={"X-Correlation-ID": "corr-3"})

    assert response.status_code == 500
    assert response.json() == {
        "error_code": "INTERNAL_ERROR",
        "message": "An unexpected error occurred.",
        "correlation_id": "corr-3",
        "details": {},
    }


def test_error_response_contains_correlation_id() -> None:
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/test/not-found")

    assert response.status_code == 404
    assert response.json()["correlation_id"]
    assert response.headers["X-Correlation-ID"] == response.json()["correlation_id"]
