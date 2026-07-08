from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rkaa.main import app  # noqa: E402


def pytest_configure() -> None:
    """Ensure tests can import the local src package layout."""


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
