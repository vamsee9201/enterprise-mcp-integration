.PHONY: check verify lint backend-test frontend-test

PYTHON ?= .venv/bin/python
RUFF ?= .venv/bin/ruff

lint:
	$(RUFF) check backend scripts mcp_server
	$(RUFF) format --check backend scripts mcp_server

# Fast feedback; intentionally excludes PostgreSQL-only concurrency checks.
check: lint
	$(PYTHON) -m pytest -q -m 'not postgres'
	npm run typecheck --prefix frontend

# Full release/CI gate. Requires a disposable PostgreSQL database.
verify: lint
	@test -n "$$TEST_DATABASE_URL" || { echo 'Set TEST_DATABASE_URL to a disposable PostgreSQL database (see README).'; exit 1; }
	$(PYTHON) -m pytest -q
	npm run typecheck --prefix frontend
	npm run test:e2e:production --prefix frontend

backend-test:
	$(PYTHON) -m pytest -q

frontend-test:
	npm run test:e2e --prefix frontend
