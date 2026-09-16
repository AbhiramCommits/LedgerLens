"""Seed a demo user with the sample CSVs, then categorize everything.

Run inside the api container (docker compose run --rm api uv run python
scripts/seed.py); talks to the api service at http://api:8000. Idempotent:
re-running skips already-imported rows via the dedupe layer.
"""

import asyncio
import sys
from pathlib import Path

import httpx

API_BASE = "http://api:8000"
DEMO_EMAIL = "demo@ledgerlens.dev"
DEMO_PASSWORD = "demo-password"
SAMPLES = (
    ("Chase Checking", Path("/sample_data/chase_sample.csv")),
    ("Amex Gold", Path("/sample_data/amex_sample.csv")),
)


async def main() -> None:
    async with httpx.AsyncClient(base_url=API_BASE, timeout=60.0) as client:
        response = await client.post(
            "/api/auth/register",
            json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
        )
        if response.status_code == 409:
            response = await client.post(
                "/api/auth/login",
                json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
            )
        if response.status_code not in (200, 201):
            print(f"auth failed: {response.status_code} {response.text}")
            sys.exit(1)
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        accounts = {
            account["name"]: account["id"]
            for account in (await client.get("/api/accounts", headers=headers)).json()
        }
        for name, path in SAMPLES:
            if name not in accounts:
                created = (
                    await client.post("/api/accounts", json={"name": name}, headers=headers)
                ).json()
                accounts[name] = created["id"]
            with path.open("rb") as handle:
                imported = await client.post(
                    "/api/imports",
                    data={"account_id": accounts[name]},
                    files={"file": (path.name, handle, "text/csv")},
                    headers=headers,
                )
            if imported.status_code != 201:
                print(f"import failed for {path.name}: {imported.status_code} {imported.text}")
                sys.exit(1)
            body = imported.json()
            print(
                f"{path.name}: inserted={body['inserted']} "
                f"skipped={body['skipped']} errors={len(body['errors'])}"
            )

        categorized = (
            await client.post("/api/transactions/categorize", headers=headers)
        ).json()
        print(f"categorized: {categorized['categorized']} by_source={categorized['by_source']}")

    print(f"\nDemo ready - log in with {DEMO_EMAIL} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())
