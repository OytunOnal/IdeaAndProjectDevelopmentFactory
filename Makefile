.PHONY: dev-frontend dev-backend dev install-frontend install-backend install lint-frontend lint-backend test-backend

dev-frontend:
	cd frontend && npm run dev

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --reload-dir app --port 8000

dev:
	@echo "Run in separate terminals:"
	@echo "  make dev-frontend   → http://localhost:3000"
	@echo "  make dev-backend    → http://localhost:8000"

install-frontend:
	cd frontend && npm install

install-backend:
	cd backend && uv sync

install: install-frontend install-backend

lint-frontend:
	cd frontend && npm run lint

lint-backend:
	cd backend && uv run ruff check app/

test-backend:
	cd backend && uv run pytest
