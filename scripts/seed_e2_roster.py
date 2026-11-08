"""Injected into the isolated private importer task. Payload contains no invitation plaintext."""

import copy
import hashlib
import json
import os
import uuid
from typing import Any

import psycopg


def seed(db: psycopg.Connection[Any], data: dict[str, Any]) -> None:
    with db.transaction():
        if db.execute("SELECT current_user").fetchone() != ("retiro_importer",):
            raise RuntimeError("Importer required")
        if data["action"] == "seed":
            batch = data["batch"]
            bad = copy.deepcopy(batch)
            bad["id"] = str(uuid.uuid4())
            for link in bad["links"]:
                link["principal"] = True
            bad_raw = json.dumps(bad, sort_keys=True)
            try:
                with db.transaction():
                    db.execute(
                        "SELECT e2_import('STAGE',%s,%s,%s,'E2_SYNTHETIC_OPERATOR','')",
                        (bad["id"], bad_raw, hashlib.sha256(bad_raw.encode()).hexdigest()),
                    )
            except psycopg.errors.InvalidParameterValue:
                pass
            else:
                raise RuntimeError("Invalid batch accepted")
            if db.execute(
                "SELECT count(*) FROM school_roster_student WHERE id=%s",
                (batch["students"][0]["id"],),
            ).fetchone() != (0,):
                raise RuntimeError("Fresh unactivated cohort required")
            raw = json.dumps(batch, sort_keys=True)
            hashed = hashlib.sha256(raw.encode()).hexdigest()
            for op in ["STAGE", "APPROVE", "PROMOTE"]:
                db.execute(
                    "SELECT e2_import(%s,%s,%s,%s,%s,%s)",
                    (
                        op,
                        batch["id"],
                        raw if op == "STAGE" else "",
                        hashed,
                        "E2_SYNTHETIC_OPERATOR",
                        "E2_SYNTHETIC_APPROVAL",
                    ),
                )
            for parent in data["parents"]:
                db.execute(
                    "SELECT e2_invite(%s,%s,%s,%s,%s)",
                    (
                        parent["id"],
                        parent["hash"],
                        "E2_SYNTHETIC_OPERATOR",
                        "E2_SYNTHETIC_APPROVAL",
                        uuid.uuid4(),
                    ),
                )
        else:
            db.execute(
                "SELECT e2_technical(%s,%s,%s,%s,%s::jsonb,%s,%s,%s)",
                (
                    data["operation"],
                    uuid.uuid4(),
                    data["school_id"],
                    data["target"],
                    json.dumps(data["data"]),
                    "E2_SYNTHETIC_OPERATOR",
                    "E2_SYNTHETIC_APPROVAL",
                    "Isolated E2 synthetic acceptance",
                ),
            )


def main() -> None:
    if os.environ.get("APP_ENV") != "staging" or os.environ.get("PGSSLMODE") != "verify-full":
        raise RuntimeError("Private synthetic TLS task required")
    data = json.loads(os.environ["E2_FIXTURE_COMMAND"])
    with psycopg.connect() as db:
        if db.execute("SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()").fetchone() != (
            True,
        ):
            raise RuntimeError("Verified TLS connection required")
        seed(db, data)
    print("E2 private synthetic command committed.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("BLOCKED: E2 synthetic command rejected; no partial transaction.")
        raise SystemExit(2) from None
