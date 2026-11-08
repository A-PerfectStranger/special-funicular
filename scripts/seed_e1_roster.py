"""Injected into an isolated ECS fixture task. No root/migration/identity secrets."""

import json
import os
import uuid
from typing import Any

import psycopg
from psycopg import sql


def seed_roster(db: psycopg.Connection[Any], data: dict[str, Any]) -> None:
    if data.get("schema_version") != 1 or data.get("synthetic_only") is not True:
        raise RuntimeError("Synthetic fixture marker required")
    if len(data["schools"]) != 2 or len(data["accounts"]) != 13:
        raise RuntimeError("Exact E1 fixture required")
    correlation = uuid.uuid5(uuid.NAMESPACE_URL, json.dumps(data, sort_keys=True))
    with db.transaction():
        if db.execute("SELECT current_user").fetchone() != ("retiro_importer",):
            raise RuntimeError("Isolated fixture importer required")
        if db.execute(
            "SELECT to_regprocedure('public.e1_audit_fixture_command(uuid,text)')"
        ).fetchone() == (None,):
            raise RuntimeError("Fixture audit migration required")
        db.execute("SELECT pg_advisory_xact_lock(728491650218)")
        tables: list[tuple[str, str, dict[str, Any]]] = [
            ("school_roster_school", "schools", {"active": True}),
            ("school_roster_site", "sites", {}),
            ("identity_account", "accounts", {"active": True, "version": 1}),
            ("school_roster_parent", "parents", {}),
            ("school_roster_student", "students", {"active": True}),
            ("school_roster_link", "links", {"active": True, "version": 1}),
        ]
        for table, key, defaults in tables:
            for row in data[key]:
                fields = {**row, **defaults}
                columns = list(fields)
                db.execute(
                    sql.SQL(
                        "INSERT INTO public.{} ({}) VALUES ({}) ON CONFLICT(id) DO NOTHING"
                    ).format(
                        sql.Identifier(table),
                        sql.SQL(",").join(map(sql.Identifier, columns)),
                        sql.SQL(",").join(sql.Placeholder() for _ in columns),
                    ),
                    tuple(fields.values()),
                )
                # A repeat must describe the exact existing fixture, never rebind a subject/child.
                actual = db.execute(
                    sql.SQL("SELECT {} FROM public.{} WHERE id=%s").format(
                        sql.SQL(",").join(map(sql.Identifier, columns)), sql.Identifier(table)
                    ),
                    (row["id"],),
                ).fetchone()
                expected = tuple(
                    uuid.UUID(value)
                    if name == "id" or name.endswith("_id") and value is not None
                    else value
                    for name, value in fields.items()
                )
                if actual != expected:
                    raise RuntimeError("Existing fixture differs; no implicit reset/rebinding")
        db.execute("SELECT e1_audit_fixture_command(%s,'PROVISION')", (correlation,))


def main() -> None:
    if os.environ.get("APP_ENV") != "staging" or os.environ.get("PGSSLMODE") != "verify-full":
        raise RuntimeError("Synthetic private TLS staging only")
    with psycopg.connect() as db:
        if db.execute("SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()").fetchone() != (
            True,
        ):
            raise RuntimeError("Authenticated TLS database required")
        seed_roster(db, json.loads(os.environ["E1_FIXTURE_DATA"]))
    print(
        json.dumps(
            {
                "synthetic_roster_seeded": True,
                "schools": 2,
                "accounts": 13,
                "students": 6,
                "real_school_activated": False,
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("BLOCKED: synthetic roster seed failed; no partial transaction")
        raise SystemExit(2) from None
