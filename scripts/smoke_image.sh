#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
set -a
source .env
set +a
IMAGE="${1:?image tag required}"
container_id=$(docker run -d --rm --read-only --tmpfs /tmp \
  --network retiro-seguro_default -p 127.0.0.1:18000:8000 \
  -e APP_ENV=development -e DJANGO_SECRET_KEY -e DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 \
  -e PGHOST=db -e PGPORT=5432 -e PGDATABASE -e PGUSER -e PGPASSWORD "$IMAGE")
trap 'docker stop "$container_id" >/dev/null' EXIT
uv run python - <<'PY'
import json, time, urllib.request
for attempt in range(40):
    try:
        with urllib.request.urlopen('http://127.0.0.1:18000/health/live', timeout=2) as r:
            assert json.load(r) == {'status': 'ok'}
        break
    except OSError:
        time.sleep(.25)
else:
    raise SystemExit('Image did not become live')
for path, expected in [('/health/ready', {'status':'ready'}),
                       ('/v1/capabilities', {'api_version':'v1','pickup_enabled':False})]:
    with urllib.request.urlopen('http://127.0.0.1:18000' + path, timeout=3) as r:
        assert json.load(r) == expected
print('Container live/ready/capabilities: passed')
PY
test "$(docker inspect --format '{{.Config.User}}' "$container_id")" = '10001:10001'
docker exec "$container_id" python -c 'import os; assert "MIGRATION_DATABASE_URL" not in os.environ'
docker run --rm --read-only --tmpfs /tmp -e APP_ENV=development \
  -e DJANGO_SECRET_KEY -e DJANGO_ALLOWED_HOSTS=localhost "$IMAGE" python manage.py runworker --check
