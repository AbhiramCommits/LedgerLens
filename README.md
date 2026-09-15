# LedgerLens

Full-stack personal-finance expense categorizer (skeleton — no business logic yet).

## Stack

- `backend/` — Python 3.12, FastAPI, SQLAlchemy 2.x (async), Alembic, Pydantic v2, managed with `uv`
- `frontend/` — React 18, TypeScript, Vite, TanStack Query, React Router, Recharts, Tailwind CSS
- `docker-compose.yml` — `db` (postgres:16), `api` (FastAPI, hot reload), `web` (Vite dev server, proxies `/api` → `api`)

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
