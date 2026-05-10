.PHONY: help setup lint test test-cov precommit ingest rag-build mcp-server serve serve-api eval eval-subset eval-from-cache redteam docker deploy clean regenerate-fixtures smoke-document

UV ?= uv

help:
	@echo "RegulAItor - available targets:"
	@echo "  setup      Install dependencies via uv"
	@echo "  lint       Run ruff, black --check, mypy"
	@echo "  test       Run pytest"
	@echo "  precommit  Run pre-commit on all files"
	@echo "  ingest     Parse PDF corpora into manifests + processed/ (H1)"
	@echo "  rag-build  Chunk + embed + populate LanceDB store (H2)"
	@echo "  mcp-server Run the MCP server on stdio (H3)"
	@echo "  regenerate-fixtures  Regenerate synthesized policy PDFs (H5)"
	@echo "  smoke-document       Run analyze CLI on the clean policy fixture (H5)"
	@echo "  serve      Run Streamlit UI (H6)"
	@echo "  serve-api  Run FastAPI server on port 8000 (H7)"
	@echo "  eval       Run full evaluation (~$7 Anthropic credit; populates cache)"
	@echo "  eval-subset       Run first 5 chat + ~1 doc case for harness debugging (~$1)"
	@echo "  eval-from-cache   Regenerate report from cached responses (free; fails on miss)"
	@echo "  redteam    Run red team suite (TODO H9)"
	@echo "  docker     Build docker image (TODO H16)"
	@echo "  deploy     Deploy to HF Spaces (TODO H16)"
	@echo "  clean      Remove caches and build artifacts"

setup:
	$(UV) sync --extra dev
	$(UV) run pre-commit install

lint:
	$(UV) run ruff check .
	$(UV) run black --check .
	$(UV) run mypy

test:
	$(UV) run pytest

test-cov:
	$(UV) run pytest --cov-report=html
	@echo "HTML coverage report in htmlcov/"

precommit:
	$(UV) run pre-commit run --all-files

ingest: ## Parse PDF corpora -> corpus/processed/ + corpus/manifests/
	$(UV) run python -m scripts.ingest --corpus all --lang all --use-local-only

rag-build: ## chunk + embed + rerank-warmup + upsert LanceDB + extend manifest
	$(UV) run python -m scripts.rag_build --corpus all --lang all

mcp-server: ## Run the MCP server on stdio (H3)
	$(UV) run python -m regulaitor.mcp_server

serve: ## Run the Streamlit MVP UI (H6)
	$(UV) run streamlit run src/regulaitor/ui_streamlit/app.py

serve-api: ## Run the FastAPI server with auto-reload on port 8000 (H7)
	$(UV) run uvicorn regulaitor.api.main:app --reload --port 8000

eval: ## Run full evaluation (~$7 Anthropic credit; populates cache)
	$(UV) run python -m scripts.evaluate

eval-subset: ## Run first 5 chat + ~1 doc case for harness debugging (~$1)
	$(UV) run python -m scripts.evaluate --subset 5

eval-from-cache: ## Regenerate report from cached responses (free; fails on miss)
	$(UV) run python -m scripts.evaluate --cache-only

redteam:
	@echo "TODO: implementar en H9"

docker:
	@echo "TODO: implementar en H16"

deploy:
	@echo "TODO: implementar en H16"

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "__pycache__" -exec rm -rf {} +

regenerate-fixtures: ## Regenerate evals/document_cases/*.pdf from .source.md (H5)
	$(UV) run python -m scripts.regenerate_document_fixtures

smoke-document: ## Run analyze CLI on the clean synthesized policy fixture (H5)
	$(UV) run python -m scripts.analyze --file evals/document_cases/synthesized_policy_clean.pdf --lang es --corpus ai_act,gdpr
