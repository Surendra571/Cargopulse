import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["application"] == "CargoPulse"
    assert "version" in data


@pytest.mark.asyncio
async def test_health_live_endpoint(async_client: AsyncClient):
    response = await async_client.get("/api/v1/healthz/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_health_overview_endpoint(async_client: AsyncClient):
    response = await async_client.get("/api/v1/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "data" in body
    assert body["data"]["application"] == "CargoPulse"
    assert "services" in body["data"]


@pytest.mark.asyncio
async def test_health_readiness_endpoint(async_client: AsyncClient):
    response = await async_client.get("/api/v1/healthz/ready")
    # Returns 503 Service Unavailable when DB or Redis is offline (expected in standalone test environment)
    assert response.status_code in (200, 503)
    data = response.json()
    assert "ready" in data
    assert "database" in data
    assert "redis" in data
