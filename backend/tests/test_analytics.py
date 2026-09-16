from datetime import date, timedelta
from decimal import Decimal

from helpers import auth, create_account, import_csv, register
from httpx import AsyncClient


def _month_key(value: date) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def _seed_csv() -> tuple[str, str, str]:
    today = date.today()
    this_month = today.replace(day=1)
    prev_month = (this_month - timedelta(days=1)).replace(day=1)
    csv = (
        "Date,Description,Debit,Credit\n"
        f"{prev_month.replace(day=5)},STARBUCKS,5.00,\n"
        f"{prev_month.replace(day=6)},WHOLE FOODS,40.00,\n"
        f"{this_month.replace(day=7)},PAYCHECK,,1250.00\n"
        f"{this_month.replace(day=8)},STARBUCKS,6.00,\n"
    )
    return csv, _month_key(prev_month), _month_key(this_month)


async def _seed_categorized(client: AsyncClient, token: str) -> tuple[str, str]:
    csv, prev_key, this_key = _seed_csv()
    account = await create_account(client, token)
    response = await import_csv(client, token, account["id"], content=csv)
    assert response.status_code == 201, response.text
    categorize = await client.post("/api/transactions/categorize", headers=auth(token))
    assert categorize.status_code == 200
    body = categorize.json()
    assert body["categorized"] == 4
    assert body["by_source"]["rule"] == 4
    return prev_key, this_key


async def test_totals_by_category(client: AsyncClient) -> None:
    token = await register(client, "alice@example.com")
    prev_key, this_key = await _seed_categorized(client, token)

    response = await client.get(
        "/api/analytics/by-category", params={"month": prev_key}, headers=auth(token)
    )
    assert response.status_code == 200
    totals = {item["category"]: item for item in response.json()["totals"]}
    assert len(totals) == 13
    assert Decimal(str(totals["dining"]["total"])) == Decimal("-5.00")
    assert totals["dining"]["count"] == 1
    assert Decimal(str(totals["groceries"]["total"])) == Decimal("-40.00")
    assert totals["groceries"]["count"] == 1
    assert Decimal(str(totals["income"]["total"])) == Decimal("0")
    assert totals["transport"]["count"] == 0

    response = await client.get(
        "/api/analytics/by-category", params={"month": this_key}, headers=auth(token)
    )
    assert response.status_code == 200
    totals = {item["category"]: item for item in response.json()["totals"]}
    assert Decimal(str(totals["income"]["total"])) == Decimal("1250.00")
    assert totals["income"]["count"] == 1
    assert Decimal(str(totals["dining"]["total"])) == Decimal("-6.00")
    assert totals["dining"]["count"] == 1

    bob = await register(client, "bob@example.com")
    response = await client.get(
        "/api/analytics/by-category", params={"month": this_key}, headers=auth(bob)
    )
    assert response.status_code == 200
    bob_totals = response.json()["totals"]
    assert all(Decimal(str(item["total"])) == Decimal("0") for item in bob_totals)


async def test_monthly_trend(client: AsyncClient) -> None:
    token = await register(client, "alice@example.com")
    prev_key, this_key = await _seed_categorized(client, token)

    response = await client.get(
        "/api/analytics/monthly-trend", params={"months": 6}, headers=auth(token)
    )
    assert response.status_code == 200
    months = response.json()["months"]
    assert len(months) == 6
    assert months[-1]["month"] == this_key
    assert months[-2]["month"] == prev_key

    current = months[-1]
    assert Decimal(str(current["total"])) == Decimal("1244.00")
    assert Decimal(str(current["income"])) == Decimal("1250.00")
    assert Decimal(str(current["expenses"])) == Decimal("-6.00")
    assert current["count"] == 2

    previous = months[-2]
    assert Decimal(str(previous["total"])) == Decimal("-45.00")
    assert Decimal(str(previous["income"])) == Decimal("0")
    assert previous["count"] == 2

    for entry in months[:-2]:
        assert Decimal(str(entry["total"])) == Decimal("0")
        assert entry["count"] == 0


async def test_analytics_validation(client: AsyncClient) -> None:
    token = await register(client, "alice@example.com")
    response = await client.get(
        "/api/analytics/by-category", params={"month": "2025-13"}, headers=auth(token)
    )
    assert response.status_code == 422
    response = await client.get(
        "/api/analytics/by-category", params={"month": "nope"}, headers=auth(token)
    )
    assert response.status_code == 422
