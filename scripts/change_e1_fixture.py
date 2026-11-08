"""Injected synthetic-only status command. Never changes identity binding, role or roster."""

import hashlib
import json
import os
import uuid
from typing import Any

import psycopg


def links_fingerprint(db: psycopg.Connection[Any]) -> str:
    links = db.execute(
        "SELECT id,school_id,student_id,parent_id,active,principal,version "
        "FROM public.school_roster_link ORDER BY id"
    ).fetchall()
    return hashlib.sha256(json.dumps(links, default=str).encode()).hexdigest()


def change(
    db: psycopg.Connection[Any], target: str, issuer: str, subject: str, active: bool
) -> None:
    with db.transaction():
        if db.execute("SELECT current_user").fetchone() != ("retiro_importer",):
            raise RuntimeError("Private importer required")
        before = links_fingerprint(db)
        account = db.execute(
            "SELECT issuer,subject,role,school_id,site_id FROM public.identity_account "
            "WHERE id=%s FOR UPDATE",
            (target,),
        ).fetchone()
        if not account or account[:2] != (issuer, subject):
            raise RuntimeError("Exact preloaded identity required; no rebinding")
        db.execute("UPDATE public.identity_account SET active=%s WHERE id=%s", (active, target))
        after = db.execute(
            "SELECT issuer,subject,role,school_id,site_id FROM public.identity_account WHERE id=%s",
            (target,),
        ).fetchone()
        if after != account or links_fingerprint(db) != before:
            raise RuntimeError("Identity or roster changed unexpectedly")
        db.execute(
            "SELECT public.e1_audit_fixture_account(%s,%s,%s)",
            (uuid.uuid4(), target, "RESET" if active else "REVOKE"),
        )


if __name__ == "__main__":
    try:
        if os.environ.get("APP_ENV") != "staging" or os.environ.get("PGSSLMODE") != "verify-full":
            raise RuntimeError("Private TLS staging only")
        data = json.loads(os.environ["E1_FIXTURE_CONTROL"])
        if data.get("synthetic_only") is not True or type(data.get("active")) is not bool:
            raise RuntimeError("Synthetic status command required")
        with psycopg.connect(autocommit=True) as connection:
            if connection.execute(
                "SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()"
            ).fetchone() != (True,):
                raise RuntimeError("Authenticated TLS required")
            failures = 0
            for target in data["targets"]:
                try:
                    change(
                        connection, target["id"], data["issuer"], target["subject"], data["active"]
                    )
                except Exception:
                    failures += 1
            if failures:
                raise RuntimeError("Not all synthetic statuses were applied")
        print("Synthetic fixture status applied; identity and roster unchanged")
    except Exception:
        print("BLOCKED: private synthetic status command failed")
        raise SystemExit(2) from None
