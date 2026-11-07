#!/usr/bin/env bash
set -euo pipefail
: "${RELEASE_SHA:=$(git rev-parse HEAD)}"
image="retiro-backend:${RELEASE_SHA}"
cleanup() {
  docker rm -f e0-api >/dev/null 2>&1 || true
  docker compose -p e0 down -v
}
trap cleanup EXIT
test "$(docker image inspect "$image" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')" = "$RELEASE_SHA"
test "$(docker image inspect "$image" --format '{{.Config.User}}')" = '10001:10001'
docker compose -p e0 up -d --wait db
docker run --rm --network e0_default -e APP_ENV=test -e DB_HOST=db -e DB_USER=app_migrator -e DB_PASSWORD=synthetic-migrator "$image" python manage.py migrate --noinput
docker run -d --name e0-api --network e0_default -p 127.0.0.1:8000:8000 -e APP_ENV=test -e DB_HOST=db "$image"
python - <<'PY'
import json
import time
from urllib.request import urlopen
for attempt in range(30):
    try:
        with urlopen('http://127.0.0.1:8000/health/ready', timeout=5) as response:
            assert response.status == 200
            assert json.load(response) == {'status': 'ready'}
            assert response.headers['Cache-Control'] == 'no-store'
        break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit('Imagen no alcanzo readiness')
with urlopen('http://127.0.0.1:8000/v1/capabilities', timeout=5) as response:
    assert json.load(response)['pickup_enabled'] is False
PY
docker exec e0-api python manage.py worker --check
if docker exec e0-api python manage.py worker; then
  echo 'Worker no implementado no debe iniciar' >&2
  exit 1
fi
