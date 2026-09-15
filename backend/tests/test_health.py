import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.parametrize("path", ["/health", "/api/health"])
async def test_health(path: str) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(path)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]
