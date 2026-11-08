"""Private importer task: audited synthetic snapshot, no root/migrator or AWS credentials."""

import json
import os
import uuid
from typing import Any

import psycopg
from psycopg import sql

ROSTER_TABLES = {
    "schools": "school_roster_school",
    "sites": "school_roster_site",
    "accounts": "identity_account",
    "parents": "school_roster_parent",
    "students": "school_roster_student",
    "links": "school_roster_link",
}


def verify_roster_rows(db: psycopg.Connection[Any], data: dict[str, Any]) -> None:
    if data.get("synthetic_only") is not True or data.get("schema_version") != 1:
        raise RuntimeError("Original synthetic import manifest required")
    for group, table in ROSTER_TABLES.items():
        for row in data[group]:
            fields = {
                **row,
                **(
                    {"active": True}
                    if group in {"schools", "accounts", "students", "links"}
                    else {}
                ),
            }
            names = list(fields)
            actual = db.execute(
                sql.SQL("SELECT {} FROM public.{} WHERE id=%s").format(
                    sql.SQL(",").join(map(sql.Identifier, names)), sql.Identifier(table)
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
                raise RuntimeError("Original roster or identity binding changed")


def verify_closed_fixture(db: psycopg.Connection[Any], data: dict[str, Any]) -> None:
    verify_roster_rows(db, data)
    for group, table in ROSTER_TABLES.items():
        count = db.execute(
            sql.SQL("SELECT count(*) FROM public.{}").format(sql.Identifier(table))
        ).fetchone()
        if count != (len(data[group]),):
            raise RuntimeError("Staging dataset is not the closed synthetic fixture")


def inspect_boundaries(db: psycopg.Connection[Any]) -> dict[str, bool]:
    roles = [
        "retiro_" + suffix
        for suffix in ["runtime", "school_read", "system_read", "importer", "archiver", "notifier"]
    ]
    checks: dict[str, bool] = {}
    checks["separate_nonprivileged_sql_roles"] = db.execute(
        "SELECT count(*)=6 AND bool_and(NOT rolsuper AND NOT rolbypassrls "
        "AND NOT rolcreatedb AND NOT rolcreaterole) FROM pg_roles WHERE rolname=ANY(%s)",
        (roles,),
    ).fetchone() == (True,)
    checks["no_service_can_write_evidence_or_assume_writer"] = db.execute(
        "SELECT bool_and(NOT has_table_privilege(r,'public.evidence_event',"
        "'INSERT,UPDATE,DELETE,TRUNCATE') "
        "AND NOT has_function_privilege(r,'public.e1_append(text,uuid,uuid,uuid,jsonb)','EXECUTE') "
        "AND NOT pg_has_role(r,'retiro_evidence_writer','MEMBER') "
        "AND NOT has_schema_privilege(r,'public','CREATE')) FROM unnest(%s::text[]) r",
        (roles,),
    ).fetchone() == (True,)
    checks["writer_cannot_login"] = db.execute(
        "SELECT NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls "
        "FROM pg_roles WHERE rolname='retiro_evidence_writer'"
    ).fetchone() == (True,)
    tables = [
        "identity_account",
        "identity_session",
        "identity_loginrequest",
        "identity_entrylimit",
        "identity_retiredrefresh",
        "school_roster_school",
        "school_roster_site",
        "school_roster_student",
        "school_roster_parent",
        "school_roster_link",
        "evidence_event",
        "evidence_head",
        "evidence_archivejob",
        "evidence_receipt",
        "django_session",
    ]
    checks["domain_rls_enabled_forced_and_service_not_owner"] = db.execute(
        "SELECT count(*)=%s AND bool_and(c.relrowsecurity AND c.relforcerowsecurity "
        "AND pg_get_userbyid(c.relowner)<>ALL(%s)) FROM pg_class c "
        "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' "
        "AND c.relname=ANY(%s)",
        (len(tables), roles, tables),
    ).fetchone() == (True,)
    checks["system_reader_has_no_minor_or_full_evidence_tables"] = db.execute(
        "SELECT bool_and(NOT has_table_privilege('retiro_system_read',t,'SELECT')) "
        "FROM unnest(%s::text[]) t",
        (
            [
                "public.school_roster_student",
                "public.school_roster_parent",
                "public.school_roster_link",
                "public.identity_account",
                "public.evidence_event",
            ],
        ),
    ).fetchone() == (True,)
    checks["definer_functions_have_fixed_search_path"] = db.execute(
        "SELECT count(*)>0 AND bool_and('search_path=pg_catalog'=ANY(p.proconfig)) FROM pg_proc p "
        "JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' "
        "AND p.proname LIKE 'e1_%' AND p.prosecdef"
    ).fetchone() == (True,)
    if not all(checks.values()):
        raise RuntimeError("Database boundary inspection failed")
    return checks


def main() -> None:
    if os.environ.get("APP_ENV") != "staging" or os.environ.get("PGSSLMODE") != "verify-full":
        raise RuntimeError("Private TLS staging only")
    with psycopg.connect() as db:
        if db.execute("SELECT current_user").fetchone() != ("retiro_importer",):
            raise RuntimeError("Isolated importer required")
        if db.execute("SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()").fetchone() != (
            True,
        ):
            raise RuntimeError("Authenticated TLS required")
        expected = json.loads(os.environ["E1_EXPECTED_ROSTER"])
        verify_closed_fixture(db, expected)
        checks = inspect_boundaries(db)
        checks["roster_matches_original_import"] = True
        rows = db.execute(
            "SELECT * FROM e1_export_fixture_snapshot(%s)", (uuid.uuid4(),)
        ).fetchall()
    # Connection/transaction is closed before stdout/CloudWatch transport.
    print("E1_PRIVATE_DB_BOUNDARIES=" + json.dumps(checks), flush=True)
    total = 0
    for sequence, event_id, canonical, digest in rows:
        record = json.dumps(
            {
                "sequence": sequence,
                "event_id": str(event_id),
                "canonical_base64": canonical,
                "digest": digest,
            }
        )
        total += len(record.encode())
        if total > 16 * 1024 * 1024:
            raise RuntimeError("Private snapshot exceeds limit")
        print("E1_PRIVATE_SNAPSHOT_ROW=" + record, flush=True)
    print("E1_PRIVATE_SNAPSHOT_END=" + str(len(rows)), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("BLOCKED: private synthetic snapshot export failed")
        raise SystemExit(2) from None
