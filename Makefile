.PHONY: up down test lint migrate

up:
	docker compose up -d --build

down:
	docker compose down

test:
	docker compose run --rm api uv run pytest

lint:
	docker compose run --rm api uv run ruff check .
	docker compose run --rm api uv run mypy app tests
	docker compose run --rm web npm run lint

migrate:
	docker compose up -d --wait db
	docker compose run --rm api uv run alembic upgrade head
