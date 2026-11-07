#!/usr/bin/env bash
set -euo pipefail
uv run pip-audit --local --progress-spinner off
npm audit --audit-level=low
docker run --rm -v "$PWD:/repo:ro" ghcr.io/gitleaks/gitleaks@sha256:e1b35e12a8c6fa8901f060459cfb6b2fc4c484d3afbe3b029733a3bbfab07055 dir /repo --redact --config /repo/.gitleaks.toml
docker run --rm -v "$PWD:/repo:ro" ghcr.io/gitleaks/gitleaks@sha256:e1b35e12a8c6fa8901f060459cfb6b2fc4c484d3afbe3b029733a3bbfab07055 git /repo --redact --config /repo/.gitleaks.toml
