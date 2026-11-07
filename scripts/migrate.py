"""Run migrations with a separate identity, never exposing its URL in logs."""

import os
import subprocess
import sys
from urllib.parse import unquote, urlparse


def main() -> int:
    url = urlparse(os.environ.get("MIGRATION_DATABASE_URL", ""))
    if url.scheme not in {"postgresql", "postgres"} or not url.hostname or not url.username:
        print("BLOCKED: MIGRATION_DATABASE_URL is required", file=sys.stderr)
        return 2
    env = os.environ.copy()
    env.update(
        {
            "PGHOST": url.hostname,
            "PGPORT": str(url.port or 5432),
            "PGUSER": unquote(url.username),
            "PGPASSWORD": unquote(url.password or ""),
            "PGDATABASE": url.path.lstrip("/"),
        }
    )
    return subprocess.call(
        [sys.executable, "apps/backend/manage.py", "migrate", "--noinput"], env=env
    )


if __name__ == "__main__":
    raise SystemExit(main())
