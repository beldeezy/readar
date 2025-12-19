SHELL := /bin/bash

.PHONY: help dev dev-backend dev-frontend install install-backend install-frontend \
        smoke smoke-backend smoke-frontend clean

help:
	@echo ""
	@echo "Readar Dev Commands"
	@echo "-------------------"
	@echo "make install          Install backend + frontend dependencies"
	@echo "make dev              Run backend + frontend in two terminals"
	@echo "make dev-backend       Run FastAPI backend (reload)"
	@echo "make dev-frontend      Run Vite frontend"
	@echo "make smoke             Run basic smoke tests"
	@echo "make smoke-backend     Hit /health"
	@echo "make smoke-frontend    Print frontend env + verify node/vite"
	@echo ""

install: install-backend install-frontend

install-backend:
	cd backend && .venv/bin/python -m pip install -r requirements.txt


install-frontend:
	@echo ">> Installing frontend deps..."
	cd frontend && npm install

dev:
	@echo ">> Start backend in one terminal: make dev-backend"
	@echo ">> Start frontend in another terminal: make dev-frontend"
	@echo ""
	@echo "Tip: open two terminals and run the two commands above."

dev-backend:
	cd backend && .venv/bin/python -m uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

smoke: smoke-backend smoke-frontend

smoke-backend:
	@echo ">> Backend health:"
	curl -i http://127.0.0.1:8000/health || true

smoke-frontend:
	@echo ">> Frontend environment:"
	@node -v || true
	@npm -v || true
	@echo ">> VITE_API_BASE_URL should be set in frontend/.env.local (or .env):"
	@cat frontend/.env.local 2>/dev/null || true
	@cat frontend/.env 2>/dev/null || true

clean:
	@echo ">> Removing node_modules and Python caches (careful)..."
	rm -rf frontend/node_modules
	find backend -type d -name "__pycache__" -exec rm -rf {} +

