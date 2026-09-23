"""Smoke test for the health endpoint."""

import httpx

# Public contract of GET /health. Bump deliberately together with the release;
# the value is written out literally on purpose so that an accidental change to
# `app.version` (or to pyproject's version without updating the API) fails here.
EXPECTED_HEALTH_BODY = {"status": "ok", "version": "0.1.0"}


async def test_health_returns_ok_and_version(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/health")

    assert response.status_code == 200
    assert response.json() == EXPECTED_HEALTH_BODY
