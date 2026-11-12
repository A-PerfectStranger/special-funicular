"""Private initial SQL roles for dark production. Injected into the operator ECS task."""

import json
import os
import sys
from typing import Any

import psycopg
from psycopg import sql

DISABLED_ROLES = ["school_read", "system_read", "importer", "archiver", "notifier"]


def provision(root: psycopg.Connection[Any]) -> None:
    """Grant-only bootstrap: reject unsafe existing identities, never reset domain data."""
    with root.transaction():
        root.execute("SELECT pg_advisory_xact_lock(1650034001)")
        for role in ["runtime", "migrator", "evidence_writer", *DISABLED_ROLES]:
            name = "retiro_" + role
            login = role in {"runtime", "migrator"}
            existing = root.execute(
                "SELECT rolsuper,rolbypassrls,rolcreatedb,rolcreaterole,rolcanlogin "
                "FROM pg_roles WHERE rolname=%s",
                (name,),
            ).fetchone()
            if existing is not None and existing != (False, False, False, False, login):
                raise RuntimeError("Unsafe or already operational SQL identity; no bootstrap")
            if not existing:
                root.execute(
                    sql.SQL(
                        "CREATE ROLE {} {} NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE"
                    ).format(sql.Identifier(name), sql.SQL("LOGIN" if login else "NOLOGIN"))
                )
            if login:
                variable = "RUNTIME_PASSWORD" if role == "runtime" else "MIGRATOR_PASSWORD"
                password = os.environ[variable]
                if len(password) < 48:
                    raise RuntimeError("Managed SQL credentials required")
                root.execute(
                    sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                        sql.Identifier(name),
                        sql.Literal(password),
                    )
                )
        # No runtime membership can turn its narrow function grants into writer power.
        if root.execute(
            "SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member "
            "WHERE r.rolname='retiro_runtime'"
        ).fetchone():
            raise RuntimeError("Runtime role membership forbidden")
        root.execute("REVOKE ALL ON DATABASE retiro FROM PUBLIC")
        root.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        root.execute("GRANT CONNECT ON DATABASE retiro TO retiro_runtime,retiro_migrator")
        root.execute(
            "GRANT USAGE ON SCHEMA public TO retiro_runtime,retiro_migrator,retiro_evidence_writer"
        )
        root.execute("GRANT CREATE ON SCHEMA public TO retiro_migrator,retiro_evidence_writer")
        root.execute("GRANT retiro_evidence_writer TO retiro_migrator")
        for role in DISABLED_ROLES:
            root.execute(
                sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
                    sql.Identifier("retiro_" + role),
                )
            )


def main() -> None:
    if os.environ.get("APP_ENV") != "production" or os.environ.get("PGSSLMODE") != "verify-full":
        raise RuntimeError("Verified private production TLS required")
    with psycopg.connect(autocommit=True) as root:
        if root.execute("SELECT current_user").fetchone() != ("retiro_bootstrap",):
            raise RuntimeError("Operator bootstrap identity required")
        if root.execute("SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()").fetchone() != (
            True,
        ):
            raise RuntimeError("SQL TLS required")
        provision(root)
    print(json.dumps({"production_roles_provisioned": True, "business_enabled": False}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print('{"status":"BLOCKED","code":"PRODUCTION_SQL_BOOTSTRAP_FAILED"}')
        sys.exit(2)
