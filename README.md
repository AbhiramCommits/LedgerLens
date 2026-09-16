# LedgerLens

Full-stack personal-finance expense categorizer.

## Stack

- `backend/` — Python 3.12, FastAPI, SQLAlchemy 2.x (async), Alembic, Pydantic v2, managed with `uv`
- `frontend/` — React 18, TypeScript, Vite, TanStack Query, React Router, Recharts, Tailwind CSS
- `docker-compose.yml` — `db` (postgres:16), `api` (FastAPI, hot reload), `web` (Vite dev server, proxies `/api` → `api`)

## API

All routes except health require a bearer token from register/login; every
query is scoped to the authenticated user.

- `POST /api/auth/register`, `POST /api/auth/login` — JWT auth (bcrypt password hashing)
- `GET/POST /api/accounts` — list/create accounts
- `POST /api/imports` — multipart CSV upload (`file` + `account_id` form fields). Handles debit/credit split columns, multiple date formats, currency symbols, parenthesized amounts, and merchant-name cleaning; dedupes on (account, date, amount, merchant). Returns `{batch_id, inserted, skipped, errors}`
- `GET /api/imports/{batch_id}` — import batch status
- `POST /api/transactions/categorize` — three-tier categorization of uncategorized rows: user overrides → keyword rules → Claude (batched ≤25, merchant-cached, with few-shot examples from your corrections). Falls back to rules/`other` if the LLM is unavailable
- `PATCH /api/transactions/{id}` — set a category manually (writes a `category_overrides` row so future imports follow it)
- `GET /api/analytics/by-category?month=YYYY-MM` and `GET /api/analytics/monthly-trend?months=6` — spending analytics
- `GET /api/analytics/by-source?month=YYYY-MM` — categorized share by source (llm/rule/user)
- `GET /api/transactions` — paginated/sortable/filterable transaction list (`page`, `page_size`, `sort_by`, `sort_order`, `category`, `max_confidence`)

Set `ANTHROPIC_API_KEY` (and optionally `ANTHROPIC_MODEL`, default `claude-sonnet-4-5`) in `.env` to enable the LLM tier.

## Frontend

React 18 + TypeScript + Vite + TanStack Query + Recharts + Tailwind. Pages: login/register, dashboard (month picker, category donut, 6-month trend, stat tiles), transactions (sortable/filterable table with inline category editing), and CSV import (drag-and-drop with progress + categorize-now).

The API client is generated from the FastAPI OpenAPI schema — no hand-written response types:

```sh
make gen-api   # regenerates frontend/src/api/schema.d.ts from the running api
```

(Outside Docker: `OPENAPI_URL=http://localhost:18000 npm run gen-api` in `frontend/`.)

## Running it

Prerequisites: Docker with Compose (`uv` and Node 20+ only needed for running outside Docker).

```sh
cp .env.example .env
make up        # docker compose up -d --build
make migrate   # apply the initial Alembic migration
```

Open http://localhost:5173 — the page fetches the API health endpoint and renders the status.

- API health (host): http://localhost:18000/health
- API health (via Vite proxy): http://localhost:5173/api/health

> The api container listens on 8000 internally; the host port is mapped to 18000 because port 8000 was already in use. The Vite proxy talks to the api service over the internal Docker network, so the frontend is unaffected. If 8000 is free on your machine, change the mapping back to `8000:8000` in `docker-compose.yml`.

## Useful commands

```sh
make down      # stop containers
make test      # backend tests (pytest)
make lint      # ruff + mypy (backend), eslint + prettier (frontend)
make migrate   # alembic upgrade head
```
