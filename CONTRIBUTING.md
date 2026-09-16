# Contributing to LedgerLens

Thanks for contributing. This is a portfolio project run with a lightweight Agile
workflow: small issues, short-lived branches, reviewed pull requests.

## Getting started

```sh
cp .env.example .env
make up        # builds and starts db + api + web
make migrate   # apply Alembic migrations
make seed      # optional: load the sample CSVs as the demo user
```

- API: http://localhost:18000 (docs at /docs)
- Web: http://localhost:5173
- Demo login (after `make seed`): `demo@ledgerlens.dev` / `demo-password`

## Workflow

1. Pick (or file) an issue with acceptance criteria. Issues live in the repo and
   are refined during backlog grooming.
2. Branch from `main` with a short descriptive name (`feat/llm-fallback`,
   `fix/parser-dates`, …).
3. Implement in small commits; keep the change scoped to the issue.
4. Open a pull request using the PR template. Every PR is code-reviewed by at
   least one other contributor before merge — use the "How to review" section to
   guide the reviewer.
5. Merge to `main` once CI is green and the review is approved. Demo the change
   in the sprint review.

## Quality gates

Run these before pushing (CI runs the same checks):

```sh
make test    # backend pytest (real Postgres, coverage must stay >= 80%)
             # + frontend vitest
make lint    # ruff + mypy (strict) + eslint + prettier
```

- Backend tests never mock the database — they run against a dockerized
  Postgres (a throwaway `ledgerlens_test` database is created per run).
- LLM calls in tests use a fake `CategorizerClient`; the real Anthropic client
  is unit-tested against a stubbed SDK.
- If you change an API contract, regenerate the typed frontend client with
  `make gen-api` and commit the updated `frontend/src/api/schema.d.ts`.

## Code conventions

- Backend: Python 3.12, async SQLAlchemy, Pydantic settings for all config
  (never read `os.environ` directly outside `app/config.py`).
- Frontend: React 18 + TypeScript, TanStack Query for server state, Tailwind
  classes for styling, `Intl` for dates/currency, real labels on every control.
- Keep parsing/categorization logic in pure modules (`app/ingest/`,
  `app/categorize/`) so it stays unit-testable without infrastructure.

## Reporting issues

Include steps to reproduce, expected vs actual behavior, and any relevant CSV
samples or log lines.
