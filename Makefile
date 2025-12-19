SHELL := /bin/bash

BACKEND_DIR := backend
FRONTEND_DIR := frontend
PYTHON := python3
VENV_DIR := .venv
VENV_PY := $(VENV_DIR)/bin/python

.PHONY: help dev dev-backend dev-frontend \
        install install-backend install-frontend \
        backend-install backend-venv backend-reqs \
        backend-alembic-check backend-alembic-heads \
        smoke smoke-backend smoke-frontend clean

help:
	@echo ""
	@echo "Readar Make targets:"
	@echo "  make dev-backend            Start FastAPI (127.0.0.1:8000)"
	@echo "  make dev-frontend           Start Vite frontend"
	@echo "  make dev                    Print instructions"
	@echo "  make install                Install backend + frontend dependencies"
	@echo "  make smoke                  Run basic smoke checks"
	@echo "  make backend-alembic-check  Show current Alembic revision"
	@echo "  make backend-alembic-heads  Show Alembic heads"
	@echo "  make clean                  Remove node_modules + backend __pycache__"
	@echo ""

# --- Backend install helpers (venv is created in backend/.venv) ---

backend-venv:
	@cd $(BACKEND_DIR) && test -d "$(VENV_DIR)" || ($(PYTHON) -m venv $(VENV_DIR))
	@cd $(BACKEND_DIR) && $(VENV_PY) -m pip install --upgrade pip

backend-reqs: backend-venv
	@cd $(BACKEND_DIR) && $(VENV_PY) -m pip install -r requirements.txt

backend-install: backend-reqs
	@echo "Backend venv + deps installed."

install-backend: backend-reqs
	@echo "Backend deps installed."

# --- Frontend install helpers ---

install-frontend:
	@echo ">> Installing frontend deps..."
	@cd $(FRONTEND_DIR) && npm install

install: install-backend install-frontend

# --- Dev commands ---

dev:
	@echo "Open TWO terminals:"
	@echo "  Terminal A: make dev-backend"
	@echo "  Terminal B: make dev-frontend"
	@echo ""

dev-backend: backend-reqs
	@cd $(BACKEND_DIR) && $(VENV_PY) -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

dev-frontend:
	@cd $(FRONTEND_DIR) && npm install
	@cd $(FRONTEND_DIR) && npm run dev

# --- Alembic helpers (using backend venv) ---

backend-alembic-check: backend-reqs
	@cd $(BACKEND_DIR) && $(VENV_PY) -m alembic current

backend-alembic-heads: backend-reqs
	@cd $(BACKEND_DIR) && $(VENV_PY) -m alembic heads

# --- Smoke checks ---

smoke: smoke-backend smoke-frontend

smoke-backend:
	@echo ">> Backend health:"
	@curl -i http://127.0.0.1:8000/health || true

smoke-frontend:
	@echo ">> Frontend environment:"
	@node -v || true
	@npm -v || true
	@echo ">> VITE_API_BASE_URL should be set in frontend/.env.local (or .env):"
	@cat frontend/.env.local 2>/dev/null || true
	@cat frontend/.env 2>/dev/null || true

clean:
	@echo ">> Removing node_modules and Python caches (careful)..."
	@rm -rf frontend/node_modules
	@find backend -type d -name "__pycache__" -exec rm -rf {} +
