SHELL := /bin/bash
.SHELLFLAGS := -euo pipefail -c
export UV_LINK_MODE := copy

.PHONY: install db migrate lint typecheck test check run mobile apk image security
install:
	uv sync --frozen
	npm ci
db:
	docker compose up -d --wait
migrate:
	set -a; source .env; set +a; uv run python scripts/migrate.py
lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run cfn-lint infra/aws/budget.yaml
	npm run lint
typecheck:
	set -a; source .env; set +a; uv run mypy
	npm run typecheck
test:
	set -a; source .env; set +a; uv run pytest -q
	npm test
check: lint typecheck migrate test
	set -a; source .env; set +a; uv run python apps/backend/manage.py check
	set -a; source .env; set +a; uv run python apps/backend/manage.py makemigrations --check --dry-run
	npm exec --workspace apps/mobile -- expo install --check
run:
	set -a; source .env; set +a; uv run python apps/backend/manage.py runserver 0.0.0.0:8000
mobile:
	npm run mobile:start
apk:
	bash scripts/build-apk.sh
image:
	docker build --secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt --build-arg GIT_SHA=$$(git rev-parse HEAD) -t retiro-backend:$$(git rev-parse HEAD) .
security:
	mkdir -p work
	uv export --frozen --no-hashes --no-emit-project -o work/requirements-audit.txt >/dev/null
	uv run pip-audit --no-deps --disable-pip -r work/requirements-audit.txt
	npm audit --audit-level=low
	gitleaks git --config .gitleaks.toml --redact
	gitleaks dir --config .gitleaks.toml --redact --no-banner
