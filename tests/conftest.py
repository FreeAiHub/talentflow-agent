"""Shared pytest fixtures."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from talentflow.api.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    """HTTP client bound to the FastAPI app (runs lifespan events)."""
    with TestClient(app) as test_client:
        yield test_client
