.PHONY: dev dev-backend dev-frontend backend-venv backend-install backend-run frontend-install frontend-run

BACKEND_DIR=backend
FRONTEND_DIR=frontend
VENV_DIR=$(BACKEND_DIR)/.venv
PY=$(VENV_DIR)/bin/python
PIP=$(VENV_DIR)/bin/pip

dev: dev-backend

dev-backend: backend-run

dev-frontend: frontend-run

backend-venv:
	@test -d "$(VENV_DIR)" || (cd $(BACKEND_DIR) && python3 -m venv .venv)

backend-install: backend-venv
	@(cd $(BACKEND_DIR) && $(PIP) install -r requirements.txt)

backend-run: backend-install
	@(cd $(BACKEND_DIR) && $(VENV_DIR)/bin/uvicorn app.main:app --reload --port 8000)

frontend-install:
	@(cd $(FRONTEND_DIR) && npm install)

frontend-run: frontend-install
	@(cd $(FRONTEND_DIR) && npm run dev)

