#!/usr/bin/env bash
set -euo pipefail
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run python apps/backend/manage.py check
uv run python apps/backend/manage.py makemigrations --check --dry-run
uv run pytest
npm ci
npm run lint
npm run typecheck
npm test
