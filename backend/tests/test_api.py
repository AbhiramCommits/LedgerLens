import uuid
from decimal import Decimal

from helpers import auth, create_account, import_csv, register
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Transaction


async def test_register_login_and_auth(client: AsyncClient) -> None:
    await register(client, "alice@example.com")

    login = await client.post(
        "/api/auth/login", json={"email": "alice@example.com", "password": "password123"}
    )
    assert login.status_code == 200
    assert login.json()["access_token"]
    assert login.json()["token_type"] == "bearer"

    bad_password = await client.post(
        "/api/auth/login", json={"email": "alice@example.com", "password": "wrongpass"}
    )
    assert bad_password.status_code == 401

    duplicate = await client.post(
        "/api/auth/register", json={"email": "alice@example.com", "password": "password123"}
    )
    assert duplicate.status_code == 409

    anonymous = await client.get("/api/accounts")
    assert anonymous.status_code == 401

    garbage = await client.get("/api/accounts", headers=auth("not-a-jwt"))
    assert garbage.status_code == 401


async def test_accounts_are_scoped(client: AsyncClient) -> None:
    token = await register(client, "alice@example.com")
    await create_account(client, token, "Checking")
    await create_account(client, token, "Savings")

    listing = await client.get("/api/accounts", headers=auth(token))
    assert listing.status_code == 200
    body = listing.json()
    assert len(body) == 2
    assert {account["name"] for account in body} == {"Checking", "Savings"}
    assert all(account["currency"] == "USD" for account in body)


async def test_import_flow_and_dedupe(client: AsyncClient, db_session: AsyncSession) -> None:
    token = await register(client, "alice@example.com")
    account = await create_account(client, token)

    first = await import_csv(client, token, account["id"])
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["inserted"] == 3
    assert body["skipped"] == 0
    assert len(body["errors"]) == 1
    assert body["errors"][0]["row_number"] == 5

    status_res = await client.get(f"/api/imports/{body['batch_id']}", headers=auth(token))
    assert status_res.status_code == 200
    batch = status_res.json()
    assert batch["status"] == "complete"
    assert batch["row_count"] == 4
    assert batch["filename"] == "transactions.csv"

    second = await import_csv(client, token, account["id"])
    assert second.status_code == 201
    assert second.json()["inserted"] == 0
    assert second.json()["skipped"] == 3

    count = await db_session.scalar(select(func.count()).select_from(Transaction))
    assert count == 3

    amounts = sorted((await db_session.scalars(select(Transaction.amount))).all())
    assert amounts == [Decimal("-45.99"), Decimal("-4.50"), Decimal("1250.00")]

    merchants = set((await db_session.scalars(select(Transaction.merchant_raw))).all())
    assert merchants == {"COFFEE SHOP", "PAYCHECK", "GAS STATION"}


async def test_duplicates_within_file(client: AsyncClient, db_session: AsyncSession) -> None:
    token = await register(client, "alice@example.com")
    account = await create_account(client, token)
    content = (
        "Date,Description,Amount\n"
        "2025-05-01,CAFE,5.00\n"
        "2025-05-01,CAFE,5.00\n"
    )
    response = await import_csv(client, token, account["id"], content=content)
    assert response.status_code == 201
    assert response.json()["inserted"] == 1
    assert response.json()["skipped"] == 1


async def test_cross_user_isolation(client: AsyncClient) -> None:
    alice = await register(client, "alice@example.com")
    bob = await register(client, "bob@example.com")
    account = await create_account(client, alice)
    imported = await import_csv(client, alice, account["id"])
    batch_id = imported.json()["batch_id"]

    response = await client.get(f"/api/imports/{batch_id}", headers=auth(bob))
    assert response.status_code == 404

    response = await import_csv(client, bob, account["id"])
    assert response.status_code == 404

    response = await client.get("/api/accounts", headers=auth(bob))
    assert response.status_code == 200
    assert response.json() == []


async def test_import_unknown_account(client: AsyncClient) -> None:
    token = await register(client, "alice@example.com")
    response = await import_csv(client, token, str(uuid.uuid4()))
    assert response.status_code == 404


async def test_import_unmappable_csv(client: AsyncClient) -> None:
    token = await register(client, "alice@example.com")
    account = await create_account(client, token)
    response = await client.post(
        "/api/imports",
        data={"account_id": account["id"]},
        files={"file": ("bad.csv", b"foo,bar\n1,2\n", "text/csv")},
        headers=auth(token),
    )
    assert response.status_code == 422
