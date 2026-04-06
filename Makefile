.PHONY: dev migrate migrate-create test lint format

dev:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

migrate:
	cd backend && uv run alembic upgrade head

migrate-create:
	cd backend && uv run alembic revision --autogenerate -m "$(msg)"

test:
	cd backend && uv run pytest -v

lint:
	cd backend && uv run ruff check .

format:
	cd backend && uv run ruff format .
