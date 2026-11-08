"""Private E1 grants only. Injected into a bootstrap ECS task; never logs passwords."""

import json
import os
import sys

import psycopg
from psycopg import sql


def main() -> None:
    if os.environ.get("APP_ENV") != "staging" or os.environ.get("PGSSLMODE") != "verify-full":
        raise RuntimeError("Private TLS staging bootstrap required")
    with psycopg.connect(autocommit=True) as root, root.transaction():
        if root.execute("SELECT current_user").fetchone() != ("retiro_bootstrap",):
            raise RuntimeError("Isolated bootstrap identity required")
        for name in [
            "school_read",
            "system_read",
            "importer",
            "archiver",
            "notifier",
            "evidence_writer",
        ]:
            role = "retiro_" + name
            exists = root.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone()
            if not exists:
                root.execute(
                    sql.SQL(
                        "CREATE ROLE {} {} NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE"
                    ).format(
                        sql.Identifier(role),
                        sql.SQL("NOLOGIN" if name == "evidence_writer" else "LOGIN"),
                    )
                )
            if name != "evidence_writer":
                password = os.environ["E1_" + name.upper() + "_PASSWORD"]
                if len(password) < 48:
                    raise RuntimeError("Invalid managed credential")
                root.execute(
                    sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                        sql.Identifier(role), sql.Literal(password)
                    )
                )
                root.execute(
                    sql.SQL("GRANT CONNECT ON DATABASE retiro TO {}").format(sql.Identifier(role))
                )
            root.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
        root.execute("GRANT retiro_evidence_writer TO retiro_migrator")
        root.execute("GRANT CREATE ON SCHEMA public TO retiro_evidence_writer")
        for name in ["school_read", "system_read", "importer", "archiver", "notifier"]:
            if root.execute(
                "SELECT rolsuper,rolbypassrls,rolcreatedb,rolcreaterole "
                "FROM pg_roles WHERE rolname=%s",
                ("retiro_" + name,),
            ).fetchone() != (False, False, False, False):
                raise RuntimeError("Unsafe existing role")
    print(
        json.dumps(
            {"e1_roles_provisioned": True, "schema_migrated": False, "idp_worm_accepted": False}
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("BLOCKED: E1 private database provisioning failed", file=sys.stderr)
        raise SystemExit(2) from None
