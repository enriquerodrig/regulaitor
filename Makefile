.PHONY: help setup lint test test-cov precommit ingest serve eval redteam docker deploy clean

UV ?= uv

help:
	@echo "RegulAItor - available targets:"
	@echo "  setup      Install dependencies via uv"
	@echo "  lint       Run ruff, black --check, mypy"
	@echo "  test       Run pytest"
	@echo "  precommit  Run pre-commit on all files"
	@echo "  ingest     Ingest corpus (TODO H1)"
	@echo "  serve      Run Streamlit UI (TODO H6)"
	@echo "  eval       Run evaluation harness (TODO H8)"
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

ingest:
	@echo "TODO: implementar en H1"

serve:
	@echo "TODO: implementar en H6"

eval:
	@echo "TODO: implementar en H8"

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
