.PHONY: check verify lint backend-test frontend-test

PYTHON ?= .venv/bin/python
CHAT_PYTHON ?= .venv-chat/bin/python
RUFF ?= .venv/bin/ruff

lint:
	$(RUFF) check backend scripts mcp_server deploy chat_app
	$(RUFF) format --check backend scripts mcp_server deploy chat_app

# Fast feedback; intentionally excludes Firestore concurrency checks.
check: lint
	$(PYTHON) -m pytest -q -m 'not firestore'
	$(CHAT_PYTHON) -m pytest -q chat_app/tests -m 'not firestore'
	npm run typecheck --prefix frontend

# Full release/CI gate. Requires the local Firestore emulator.
verify: lint
	@test -n "$$FIRESTORE_EMULATOR_HOST" || { echo 'Set FIRESTORE_EMULATOR_HOST (see README).'; exit 1; }
	$(PYTHON) -m pytest -q
	$(CHAT_PYTHON) -m pytest -q chat_app/tests
	npm run typecheck --prefix frontend
	npm run test:e2e:production --prefix frontend

backend-test:
	$(PYTHON) -m pytest -q

frontend-test:
	npm run test:e2e --prefix frontend
