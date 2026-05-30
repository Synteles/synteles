.PHONY: install format lint type security check test coverage clean

install:
	uv sync --group dev

format:
	uv run ruff format .
	uv run ruff check . --fix

lint:
	uv run ruff format . --check
	uv run ruff check .

type:
	uv run mypy adapters agents core tools tests

security:
	uv run bandit -rq -c pyproject.toml .

check: lint type security

test:
	uv run pytest

coverage:
	uv run pytest --cov --cov-report=term-missing --cov-report=html

clean:
	rm -rf .mypy_cache .ruff_cache htmlcov .coverage __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
