from datetime import date

from fakes import FakeCategorizer
from helpers import auth, create_account, import_csv, register
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.categorize.taxonomy import Category
from app.models import CategoryOverride, CategorySource, Transaction

RULE_CSV = (
    "Date,Description,Debit,Credit\n"
    "2025-02-01,STARBUCKS,5.00,\n"
    "2025-02-02,WHOLE FOODS,40.00,\n"
    "2025-02-03,FLIBBERTIGIBBET,7.50,\n"
    "2025-02-04,FLIBBERTIGIBBET,8.50,\n"
    "2025-02-05,WOMBAT EMPORIUM,9.50,\n"
)

SECOND_CSV = "Date,Description,Debit,Credit\n2025-02-06,FLIBBERTIGIBBET,10.00,\n"


async def _seed(client: AsyncClient, token: str) -> str:
    account = await create_account(client, token)
    response = await import_csv(client, token, account["id"], content=RULE_CSV)
    assert response.status_code == 201, response.text
    return str(account["id"])


async def test_pipeline_tiers_and_merchant_cache(
    client: AsyncClient, db_session: AsyncSession, fake_categorizer: FakeCategorizer
) -> None:
    token = await register(client, "alice@example.com")
    await _seed(client, token)

    fake_categorizer.responses["FLIBBERTIGIBBET"] = Category.dining
    fake_categorizer.responses["WOMBAT EMPORIUM"] = Category.travel

    response = await client.post("/api/transactions/categorize", headers=auth(token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["categorized"] == 5
    assert body["by_source"] == {"user": 0, "rule": 2, "llm": 3, "fallback": 0}
    assert body["fallback_reasons"] == []

    # Two transactions share one merchant -> one LLM call with 2 unique items.
    assert len(fake_categorizer.calls) == 1
    assert sorted(fake_categorizer.calls[0][0]) == ["FLIBBERTIGIBBET", "WOMBAT EMPORIUM"]

    transactions = (await db_session.scalars(select(Transaction))).all()
    by_merchant = {t.merchant_raw: t for t in transactions}
    assert by_merchant["STARBUCKS"].category == "dining"
    assert by_merchant["STARBUCKS"].category_source is CategorySource.rule
    assert by_merchant["STARBUCKS"].confidence == 0.9
    assert by_merchant["WOMBAT EMPORIUM"].category == "travel"
    assert by_merchant["WOMBAT EMPORIUM"].category_source is CategorySource.llm
    flib = [t for t in transactions if t.merchant_raw == "FLIBBERTIGIBBET"]
    assert len(flib) == 2
    assert all(t.category == "dining" for t in flib)
    assert all(t.category_source is CategorySource.llm for t in flib)


async def test_patch_writes_override_and_override_tier_wins(
    client: AsyncClient, db_session: AsyncSession, fake_categorizer: FakeCategorizer
) -> None:
    token = await register(client, "alice@example.com")
    account_id = await _seed(client, token)

    transactions = (await db_session.scalars(select(Transaction))).all()
    flib = next(t for t in transactions if t.merchant_raw == "FLIBBERTIGIBBET")

    patch = await client.patch(
        f"/api/transactions/{flib.id}", json={"category": "fees"}, headers=auth(token)
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["category"] == "fees"
    assert patch.json()["category_source"] == "user"
    assert patch.json()["confidence"] == 1.0

    overrides = (await db_session.scalars(select(CategoryOverride))).all()
    assert len(overrides) == 1
    assert overrides[0].merchant_pattern == "FLIBBERTIGIBBET"
    assert overrides[0].category == "fees"

    fake_categorizer.responses["FLIBBERTIGIBBET"] = Category.dining
    second = await import_csv(client, token, account_id, content=SECOND_CSV)
    assert second.status_code == 201

    categorize = await client.post("/api/transactions/categorize", headers=auth(token))
    assert categorize.status_code == 200
    body = categorize.json()
    assert body["by_source"] == {"user": 2, "rule": 2, "llm": 1, "fallback": 0}

    # LLM was never asked about the overridden merchant, and received the
    # user's correction as a few-shot example.
    assert fake_categorizer.calls[0][0] == ["WOMBAT EMPORIUM"]
    assert fake_categorizer.calls[0][1] == ["fees"]

    new_flib = (
        await db_session.scalars(
            select(Transaction).where(Transaction.posted_date == date(2025, 2, 6))
        )
    ).first()
    assert new_flib is not None
    assert new_flib.category == "fees"
    assert new_flib.category_source is CategorySource.user
    assert new_flib.confidence == 1.0


async def test_llm_failure_falls_back_gracefully(
    client: AsyncClient, db_session: AsyncSession, fake_categorizer: FakeCategorizer
) -> None:
    token = await register(client, "alice@example.com")
    await _seed(client, token)
    fake_categorizer.fail = True

    response = await client.post("/api/transactions/categorize", headers=auth(token))
    assert response.status_code == 200
    body = response.json()
    assert body["categorized"] == 5
    assert body["by_source"] == {"user": 0, "rule": 2, "llm": 0, "fallback": 3}
    assert any("fake client failure" in reason for reason in body["fallback_reasons"])

    transactions = (await db_session.scalars(select(Transaction))).all()
    unknown = [t for t in transactions if t.merchant_raw not in {"STARBUCKS", "WHOLE FOODS"}]
    assert len(unknown) == 3
    assert all(t.category == "other" for t in unknown)
    assert all(t.category_source is CategorySource.rule for t in unknown)
    assert all(t.confidence == 0.0 for t in unknown)


async def test_llm_batch_cap_25(client: AsyncClient, fake_categorizer: FakeCategorizer) -> None:
    token = await register(client, "alice@example.com")
    account = await create_account(client, token)

    names = [f"MERCHANT {chr(65 + i)}" for i in range(26)] + [
        f"MERCHANT A{chr(65 + i)}" for i in range(4)
    ]
    rows = ["Date,Description,Amount"]
    for index, name in enumerate(names, start=1):
        rows.append(f"2025-03-{index:02d},{name},-{index}.00")
    content = "\n".join(rows) + "\n"

    response = await import_csv(client, token, account["id"], content=content)
    assert response.status_code == 201

    categorize = await client.post("/api/transactions/categorize", headers=auth(token))
    assert categorize.status_code == 200
    body = categorize.json()
    assert body["categorized"] == 30
    assert [len(call[0]) for call in fake_categorizer.calls] == [25, 5]


async def test_patch_validation_and_scoping(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    alice = await register(client, "alice@example.com")
    bob = await register(client, "bob@example.com")
    await _seed(client, alice)

    transactions = (await db_session.scalars(select(Transaction))).all()
    transaction = transactions[0]

    bad = await client.patch(
        f"/api/transactions/{transaction.id}", json={"category": "gambling"}, headers=auth(alice)
    )
    assert bad.status_code == 422

    forbidden = await client.patch(
        f"/api/transactions/{transaction.id}", json={"category": "other"}, headers=auth(bob)
    )
    assert forbidden.status_code == 404

    categorize = await client.post("/api/transactions/categorize", headers=auth(bob))
    assert categorize.status_code == 200
    assert categorize.json()["categorized"] == 0


async def test_categorize_empty(client: AsyncClient) -> None:
    token = await register(client, "alice@example.com")
    response = await client.post("/api/transactions/categorize", headers=auth(token))
    assert response.status_code == 200
    body = response.json()
    assert body["categorized"] == 0
    assert body["transactions"] == []
