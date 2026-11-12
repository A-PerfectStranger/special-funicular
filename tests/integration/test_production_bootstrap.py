"""Fresh PostgreSQL with production's actual TLS/bootstrap/migration/runtime roles.

The dedicated local container is stopped and retained for inspection, not reset.
No cloud connection, fixture reuse or evidence deletion occurs here.
"""

import os
import subprocess
import time
import uuid
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
import yaml

from scripts.bootstrap_production_database import provision

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def cluster() -> Iterator[dict[str, str]]:
    name = "retiro-production-verify-" + uuid.uuid4().hex[:12]
    directory = Path("work") / name
    directory.mkdir(parents=True, mode=0o700)
    certificate = directory.resolve() / "server.crt"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "2",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost,IP:127.0.0.1",
            "-keyout",
            str(directory / "server.key"),
            "-out",
            str(certificate),
        ],
        check=True,
        capture_output=True,
    )
    # The isolated Docker daemon's root entrypoint copies this synthetic-only key
    # into a postgres-owned 0600 file before starting TLS. It is never exported.
    (directory / "server.key").chmod(0o600)
    image = yaml.safe_load(Path("compose.yaml").read_text())["services"]["db"]["image"]
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            name,
            "--label",
            "Project=retiro-seguro",
            "--label",
            "Data=synthetic",
            "-p",
            "127.0.0.1::5432",
            "-e",
            "POSTGRES_USER=retiro_bootstrap",
            "-e",
            "POSTGRES_DB=retiro",
            "-e",
            "POSTGRES_PASSWORD=synthetic-bootstrap-only",
            "--mount",
            f"type=bind,src={directory.resolve()},dst=/run/synthetic-cert,readonly",
            "--entrypoint",
            "sh",
            image,
            "-ec",
            "cp /run/synthetic-cert/server.key /tmp/server.key; "
            "cp /run/synthetic-cert/server.crt /tmp/server.crt; "
            "chown postgres:postgres /tmp/server.key /tmp/server.crt; "
            "chmod 600 /tmp/server.key; chmod 644 /tmp/server.crt; "
            "exec docker-entrypoint.sh postgres -c ssl=on "
            "-c ssl_cert_file=/tmp/server.crt -c ssl_key_file=/tmp/server.key",
        ],
        check=True,
        capture_output=True,
    )
    try:
        port = (
            subprocess.check_output(["docker", "port", name, "5432/tcp"], text=True)
            .strip()
            .rsplit(":", 1)[1]
        )
        env = {
            **os.environ,
            "APP_ENV": "production",
            "DJANGO_DEBUG": "false",
            "DJANGO_SECRET_KEY": "managed-production-test-only-" * 3,
            "DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1,testserver",
            "PGHOST": "127.0.0.1",
            "PGPORT": port,
            "PGDATABASE": "retiro",
            "PGUSER": "retiro_bootstrap",
            "PGPASSWORD": "synthetic-bootstrap-only",
            "PGSSLMODE": "verify-full",
            "PGSSLROOTCERT": str(certificate),
            "RUNTIME_PASSWORD": "synthetic-runtime-only-" * 3,
            "MIGRATOR_PASSWORD": "synthetic-migrator-only-" * 3,
            "E1_IDENTITY_ENABLED": "false",
            "E2_FAMILY_ENABLED": "false",
            "E3_PICKUP_ENABLED": "false",
            "E4_OPERATIONS_ENABLED": "false",
        }
        root_dsn = psycopg.conninfo.make_conninfo(
            host=env["PGHOST"],
            port=port,
            dbname="retiro",
            user="retiro_bootstrap",
            password=env["PGPASSWORD"],
            sslmode="verify-full",
            sslrootcert=str(certificate),
        )
        env["PRODUCTION_TEST_ROOT_DSN"] = root_dsn
        for attempt in range(60):
            try:
                with psycopg.connect(root_dsn, connect_timeout=1):
                    break
            except psycopg.OperationalError:
                if attempt == 59:
                    pytest.fail("isolated PostgreSQL TLS startup failed")
                time.sleep(0.25)
        python = str(Path(".venv/bin/python").absolute())
        for label, command in [
            ("bootstrap", [python, "scripts/bootstrap_production_database.py"]),
            ("migration", [python, "apps/backend/manage.py", "migrate_locked", "--noinput"]),
        ]:
            child = (
                env
                if label == "bootstrap"
                else {**env, "PGUSER": "retiro_migrator", "PGPASSWORD": env["MIGRATOR_PASSWORD"]}
            )
            result = subprocess.run(command, env=child, text=True, capture_output=True, timeout=120)
            (directory / f"{label}.log").write_text(result.stdout + result.stderr)
            assert result.returncode == 0, f"production {label} failed; inspect private work/ log"
        with pytest.MonkeyPatch.context() as context:
            context.setenv("RUNTIME_PASSWORD", env["RUNTIME_PASSWORD"])
            context.setenv("MIGRATOR_PASSWORD", env["MIGRATOR_PASSWORD"])
            yield env
    finally:
        subprocess.run(["docker", "stop", "--time", "5", name], check=True, capture_output=True)


def test_fresh_production_schema_enforces_real_runtime_and_writer_permissions(
    cluster: dict[str, str],
) -> None:
    with psycopg.connect(cluster["PRODUCTION_TEST_ROOT_DSN"], autocommit=True) as root:
        provision(root)  # Repeat is grant-only and leaves the migrated schema intact.
        names = root.execute(
            "SELECT rolname,rolcanlogin FROM pg_roles "
            "WHERE rolname LIKE 'retiro_%' ORDER BY rolname"
        ).fetchall()
        assert {name for name, login in names if login} == {
            "retiro_bootstrap",
            "retiro_migrator",
            "retiro_runtime",
        }
        # Every protected table remains forced RLS after the complete migration graph.
        assert root.execute(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON c.relnamespace=n.oid "
            "WHERE n.nspname='public' AND c.relrowsecurity AND NOT c.relforcerowsecurity"
        ).fetchone() == (0,)
        assert root.execute("SELECT count(*) FROM evidence_event").fetchone() == (0,)
    dsn = psycopg.conninfo.make_conninfo(
        cluster["PRODUCTION_TEST_ROOT_DSN"],
        user="retiro_runtime",
        password=cluster["RUNTIME_PASSWORD"],
    )
    with psycopg.connect(dsn, autocommit=True) as runtime:
        assert runtime.execute("SELECT id FROM public.e1_current_account()").fetchall() == []
        assert runtime.execute("SELECT count(*) FROM school_roster_student").fetchone() == (0,)
        assert runtime.execute(
            "SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()"
        ).fetchone() == (True,)
        for statement in [
            "SELECT count(*) FROM evidence_event",
            "CREATE TABLE public.forbidden(id integer)",
            "SET ROLE retiro_evidence_writer",
            "UPDATE evidence_event SET kind='forbidden'",
            "DELETE FROM evidence_event",
            "TRUNCATE evidence_event",
            "ALTER TABLE evidence_event DISABLE ROW LEVEL SECURITY",
            "SELECT e4_notification_status()",
        ]:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                runtime.execute(statement)
    result = subprocess.run(
        [str(Path(".venv/bin/python").absolute()), "apps/backend/manage.py", "check"],
        env={**cluster, "PGUSER": "retiro_runtime", "PGPASSWORD": cluster["RUNTIME_PASSWORD"]},
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0
    # Actual production URL configuration and runtime SQL, without enabling any
    # business route. Cloud TLS/ingress attestation remains a separate live gate.
    result = subprocess.run(
        [
            str(Path(".venv/bin/python").absolute()),
            "-c",
            """
import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
import django
django.setup()
from django.test import Client
c = Client()
assert c.get('/health/ready', secure=True).json() == {'status': 'ready'}
assert c.get('/v1/capabilities', secure=True).json()['pickup_enabled'] is False
for path in ['/auth/login', '/portal/', '/v1/me/students', '/v1/me/pickups',
             '/v1/guard/confirm-pickup', '/v1/me/notification-device', '/admin/']:
    assert c.get(path, secure=True).status_code == 404
""",
        ],
        cwd="apps/backend",
        env={**cluster, "PGUSER": "retiro_runtime", "PGPASSWORD": cluster["RUNTIME_PASSWORD"]},
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, "production technical HTTP boundary failed"


def test_production_sql_rejects_a_different_tls_server_identity(cluster: dict[str, str]) -> None:
    dsn = psycopg.conninfo.make_conninfo(
        cluster["PRODUCTION_TEST_ROOT_DSN"], host="127.0.0.2", hostaddr="127.0.0.1"
    )
    with pytest.raises(psycopg.OperationalError):
        psycopg.connect(dsn, connect_timeout=1)


def test_unsafe_existing_role_blocks_and_rolls_back_bootstrap(cluster: dict[str, str]) -> None:
    with psycopg.connect(cluster["PRODUCTION_TEST_ROOT_DSN"], autocommit=True) as root:
        root.execute("ALTER ROLE retiro_runtime BYPASSRLS")
        try:
            with pytest.raises(RuntimeError, match="Unsafe"):
                provision(root)
        finally:
            root.execute("ALTER ROLE retiro_runtime NOBYPASSRLS")


def test_production_bootstrap_cannot_silently_disable_an_operational_role(
    cluster: dict[str, str],
) -> None:
    with psycopg.connect(cluster["PRODUCTION_TEST_ROOT_DSN"], autocommit=True) as root:
        root.execute("ALTER ROLE retiro_importer LOGIN")
        try:
            with pytest.raises(RuntimeError, match="already operational"):
                provision(root)
        finally:
            root.execute("ALTER ROLE retiro_importer NOLOGIN")
