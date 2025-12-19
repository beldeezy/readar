SHELL := /bin/bash

BACKEND_DIR := backend
FRONTEND_DIR := frontend
PYTHON := python3
VENV_DIR := $(BACKEND_DIR)/.venv
VENV_PY := $(VENV_DIR)/bin/python

.PHONY: help dev dev-backend dev-frontend backend-install backend-venv backend-reqs backend-alembic-check backend-alembic-heads

help:
	@echo ""
	@echo "Readar Make targets:"
	@echo "  make dev-backend            Start FastAPI (127.0.0.1:8000)"
	@echo "  make dev-frontend           Start Vite frontend"
	@echo "  make dev                    Print instructions + start backend"
	@echo "  make backend-install        Create backend venv + install deps"
	@echo "  make backend-alembic-check  Show current Alembic revision"
	@echo "  make backend-alembic-heads  Show Alembic heads"
	@echo ""

backend-venv:
	@test -d "$(VENV_DIR)" || ($(PYTHON) -m venv $(VENV_DIR))
	@$(VENV_PY) -m pip install --upgrade pip

backend-reqs: backend-venv
	@$(VENV_PY) -m pip install -r $(BACKEND_DIR)/requirements.txt

backend-install: backend-reqs
	@echo "Backend venv + deps installed."

dev-backend: backend-reqs
	@cd $(BACKEND_DIR) && $(VENV_PY) -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

dev-frontend:
	@cd $(FRONTEND_DIR) && npm install
	@cd $(FRONTEND_DIR) && npm run dev

dev:
	@echo "Open TWO terminals:"
	@echo "  Terminal A: make dev-backend"
	@echo "  Terminal B: make dev-frontend"
	@echo ""
	@echo "Starting backend here..."
	@$(MAKE) dev-backend

backend-alembic-check: backend-reqs
	@cd $(BACKEND_DIR) && $(VENV_PY) -m alembic current

backend-alembic-heads: backend-reqs
	@cd $(BACKEND_DIR) && $(VENV_PY) -m alembic heads
