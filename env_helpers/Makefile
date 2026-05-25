# Makefile — common project tasks via Poetry
#
# Usage:
#   make install        install all deps (main + dev + notebook)
#   make format         auto-format code with ruff
#   make lint           lint code with ruff
#   make test           run tests with coverage
#   make clean          remove venv and caches

.PHONY: install install-prod format lint check test clean export-requirements

# Install all dependency groups
install:
	poetry install --with dev,notebook

# Install production deps only (e.g. before building a Docker image)
install-prod:
	poetry install --without dev,notebook

# Auto-format code (fixes in place)
format:
	poetry run ruff format .
	poetry run ruff check --fix .

# Lint without fixing
lint:
	poetry run ruff check .

# Format check + lint (no changes written — useful in CI)
check:
	poetry run ruff format --check .
	poetry run ruff check .

# Run tests with coverage report
test:
	poetry run pytest --cov=. --cov-report=term-missing

# Export a requirements.txt from the lockfile (pip / Docker compatible)
export-requirements:
	poetry export \
		-f requirements.txt \
		--output requirements.txt \
		--without dev,notebook \
		--without-hashes
	@echo "requirements.txt updated"

# Remove the virtual environment and Python caches
clean:
	poetry env remove --all 2>/dev/null || true
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache  -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "Environment cleaned"
