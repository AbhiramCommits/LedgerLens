from typing import Any, cast

from httpx import AsyncClient, Response

CSV = (
    "Date,Description,Debit,Credit\n"
    "2025-01-05,COFFEE SHOP,4.50,\n"
    "2025-01-06,PAYCHECK,,1250.00\n"
    "2025-01-07,GAS STATION,45.99,\n"
    "not-a-date,BAD ROW,10.00,\n"
)


async def register(client: AsyncClient, email: str, password: str = "password123") -> str:
    response = await client.post(
        "/api/auth/register", json={"email": email, "password": password}
    )
    assert response.status_code == 201, response.text
    return str(response.json()["access_token"])


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def create_account(
    client: AsyncClient, token: str, name: str = "Checking"
) -> dict[str, Any]:
    response = await client.post("/api/accounts", json={"name": name}, headers=auth(token))
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


async def import_csv(
    client: AsyncClient, token: str, account_id: str, content: str = CSV
) -> Response:
    return await client.post(
        "/api/imports",
        data={"account_id": account_id},
        files={"file": ("transactions.csv", content, "text/csv")},
        headers=auth(token),
    )
