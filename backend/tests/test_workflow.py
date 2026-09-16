import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import jwt
from fakes import FakeCategorizer
from helpers import auth, create_account, import_csv, register
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.categorize.taxonomy import Category
from app.models import Transaction
from app.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

WORKFLOW_CSV = (
    "Date,Description,Debit,Credit\n"
    "2026-09-01,STARBUCKS,5.50,\n"
    "2026-09-02,WHOLE FOODS,44.00,\n"
    "2026-09-03,PAYROLL ACME,,2200.00\n"
    "2026-09-04,FLIBBERTIGIBBET,12.00,\n"
)


def test_password_hashing_roundtrip() -> None:
    hashed = hash_password("s3cret-password")
    assert hashed != "s3cret-password"
    assert verify_password("s3cret-password", hashed)
    assert not verify_password("wrong-password", hashed)


def test_token_roundtrip_and_expiry() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id)
    assert decode_access_token(token) == user_id

    expired = jwt.encode(
        {"sub": str(user_id), "exp": datetime.now(UTC) - timedelta(minutes=1)},
        "dev-only-secret",
        algorithm="HS256",
    )
    assert decode_access_token(expired) is None

    tampered = token[:-4] + "abcd"
    assert decode_access_token(tampered) is None

    wrong_secret = jwt.encode(
        {"sub": str(user_id), "exp": datetime.now(UTC) + timedelta(minutes=5)},
        "a-different-secret",
        algorithm="HS256",
    )
    assert decode_access_token(wrong_secret) is None

    assert decode_access_token("not-a-jwt") is None


async def test_token_for_unknown_user_is_rejected(client: AsyncClient) -> None:
    token = create_access_token(uuid.uuid4())
    response = await client.get("/api/accounts", headers=auth(token))
    assert response.status_code == 401


async def test_full_workflow_from_register_to_analytics(
    client: AsyncClient, db_session: AsyncSession, fake_categorizer: FakeCategorizer
) -> None:
    email = "workflow@example.com"
    register_response = await client.post(
        "/api/auth/register", json={"email": email, "password": "workflow-password"}
    )
    assert register_response.status_code == 201

    login_response = await client.post(
        "/api/auth/login", json={"email": email, "password": "workflow-password"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    account = await create_account(client, token, "Workflow Checking")
    imported = await import_csv(client, token, account["id"], content=WORKFLOW_CSV)
    assert imported.status_code == 201
    assert imported.json()["inserted"] == 4

    fake_categorizer.responses["FLIBBERTIGIBBET"] = Category.shopping
    categorized = await client.post("/api/transactions/categorize", headers=auth(token))
    assert categorized.status_code == 200
    assert categorized.json()["by_source"] == {"user": 0, "rule": 3, "llm": 1, "fallback": 0}

    transactions = (await db_session.scalars(select(Transaction))).all()
    starbucks = next(t for t in transactions if t.merchant_raw == "STARBUCKS")

    patched = await client.patch(
        f"/api/transactions/{starbucks.id}",
        json={"category": "housing"},
        headers=auth(token),
    )
    assert patched.status_code == 200
    assert patched.json()["category"] == "housing"
    assert patched.json()["category_source"] == "user"

    analytics = await client.get(
        "/api/analytics/by-category", params={"month": "2026-09"}, headers=auth(token)
    )
    assert analytics.status_code == 200
    totals = {item["category"]: item for item in analytics.json()["totals"]}
    assert Decimal(str(totals["housing"]["total"])) == Decimal("-5.50")
    assert totals["housing"]["count"] == 1
    assert Decimal(str(totals["dining"]["total"])) == Decimal("0")

    sources = await client.get(
        "/api/analytics/by-source", params={"month": "2026-09"}, headers=auth(token)
    )
    assert sources.json()["sources"] == {"llm": 1, "rule": 2, "user": 1}


async def test_cross_user_transaction_isolation(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    alice = await register(client, "alice@example.com")
    bob = await register(client, "bob@example.com")

    alice_account = await create_account(client, alice, "Alice Checking")
    await import_csv(client, alice, alice_account["id"])

    alice_transactions = (await db_session.scalars(select(Transaction))).all()
    assert len(alice_transactions) == 3
    target = alice_transactions[0]

    patch = await client.patch(
        f"/api/transactions/{target.id}", json={"category": "other"}, headers=auth(bob)
    )
    assert patch.status_code == 404
    assert patch.json()["detail"] == "transaction not found"
    assert "merchant" not in patch.text

    bob_listing = await client.get("/api/transactions", headers=auth(bob))
    assert bob_listing.status_code == 200
    assert bob_listing.json()["total"] == 0
    assert bob_listing.json()["items"] == []

    bob_analytics = await client.get(
        "/api/analytics/by-category", params={"month": "2026-01"}, headers=auth(bob)
    )
    assert bob_analytics.status_code == 200
    assert all(
        Decimal(str(item["total"])) == Decimal("0") for item in bob_analytics.json()["totals"]
    )
