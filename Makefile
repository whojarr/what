.PHONY: help setup install api web dev test demo deploy deploy-dev deploy-info deploy-remove deploy-package clean

POETRY ?= poetry
YARN ?= yarn
API_HOST ?= 127.0.0.1
API_PORT ?= 8000
WEB_HOST ?= 127.0.0.1
WEB_PORT ?= 5000

help:
	@echo "WHAT"
	@echo ""
	@echo "  make setup      Install deps + create .env from example"
	@echo "  make install    poetry install && yarn install"
	@echo "  make dev        Run API (:8000) and Web UI (:5000) together"
	@echo "  make api        Run FastAPI only  → http://$(API_HOST):$(API_PORT)/docs"
	@echo "  make web        Run Flask UI only → http://$(WEB_HOST):$(WEB_PORT)"
	@echo "  make test       Run pytest"
	@echo "  make demo       Scripted 5-turn demo (no LLM)"
	@echo "  make deploy-dev Deploy to AWS Lambda (dev stage)"
	@echo "  make deploy-info Show deployed endpoints"
	@echo ""

setup: install
	@test -f .env || (cp .env.example .env && echo "Created .env — add OPENAI_API_KEY")
	@echo "Setup done. Run: make dev"

install:
	$(POETRY) install
	$(YARN) install

api:
	$(POETRY) run uvicorn api.main:app --reload --host $(API_HOST) --port $(API_PORT)

web:
	$(POETRY) run python web/app.py

# Run API in background, Web in foreground; Ctrl+C stops both
dev:
	@echo "API:  http://$(API_HOST):$(API_PORT)/docs"
	@echo "Web:  http://$(WEB_HOST):$(WEB_PORT)"
	@trap 'kill 0' INT TERM; \
		$(POETRY) run uvicorn api.main:app --reload --host $(API_HOST) --port $(API_PORT) & \
		$(POETRY) run python web/app.py & \
		wait

test:
	$(POETRY) run pytest

demo:
	$(POETRY) run python scripts/run_demo.py

deploy-dev:
	@set -a && [ -f .env ] && . ./.env; set +a; \
		test -n "$$OPENAI_API_KEY" || (echo "Set OPENAI_API_KEY in .env" && exit 1); \
		$(YARN) deploy:dev

deploy:
	@set -a && [ -f .env ] && . ./.env; set +a; \
		test -n "$$OPENAI_API_KEY" || (echo "Set OPENAI_API_KEY in .env" && exit 1); \
		$(YARN) deploy

deploy-info:
	$(YARN) info

deploy-remove:
	$(YARN) remove

deploy-package:
	$(YARN) package

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .serverless
