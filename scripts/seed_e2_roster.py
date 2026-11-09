"""Injected into the isolated private importer task. Payload contains no invitation plaintext."""

import copy
import hashlib
import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import psycopg


class CohortUsed(Exception):
    """Never reuse a durable synthetic student's invitation or episode."""


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
                raise CohortUsed()
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
        elif data["action"].startswith("e3-"):
            batch = data["e3_batch"]
            if data["action"] == "e3-seed":
                if db.execute(
                    "SELECT count(*) FROM school_roster_student WHERE id=%s",
                    (batch["students"][0]["id"],),
                ).fetchone() != (0,):
                    raise CohortUsed()
                raw = json.dumps(batch, sort_keys=True)
                hashed = hashlib.sha256(raw.encode()).hexdigest()
                for op in ["STAGE", "APPROVE", "PROMOTE"]:
                    db.execute(
                        "SELECT e2_import(%s,%s,%s,%s,"
                        "'E3_SYNTHETIC_OPERATOR','E3_SYNTHETIC_APPROVAL')",
                        (op, batch["id"], raw if op == "STAGE" else "", hashed),
                    )
            elif data["action"] == "e3-hold":
                child = next(s for s in batch["students"] if s["name"] == "E3 synthetic timeout")
                db.execute("SELECT e3_trial_hold(%s)", (child["id"],))
            elif data["action"] == "e3-revoke":
                child = next(s for s in batch["students"] if s["name"] == "E3 synthetic revoke")
                db.execute(
                    "SELECT e2_technical('SET_POLICY',%s,%s,%s,%s::jsonb,"
                    "'E3_SYNTHETIC_OPERATOR','E3_SYNTHETIC_APPROVAL','Synthetic revocation race')",
                    (
                        uuid.uuid4(),
                        batch["school_id"],
                        child["id"],
                        json.dumps({"windows": child["windows"], "blocked": True}),
                    ),
                )
            else:
                raise ValueError()
        else:
            for expected in data["expected_accounts"]:
                actual = db.execute(
                    "SELECT a.issuer,a.subject,a.role FROM school_roster_parent p "
                    "JOIN identity_account a ON a.id=p.account_id WHERE p.id=%s",
                    (expected["parent_id"],),
                ).fetchone()
                if actual != (data["issuer"], expected["subject"], "PADRE"):
                    raise RuntimeError("Activated identity differs from prepared subject")
            if data["action"] == "deactivate":
                target = db.execute(
                    "SELECT account_id FROM school_roster_parent WHERE id=%s",
                    (data["account_parent_id"],),
                ).fetchone()
                if not target or target[0] is None:
                    raise RuntimeError("No activated synthetic account")
                data = {**data, "target": str(target[0])}
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


def bulk_drill(db: psycopg.Connection[Any], data: dict[str, Any]) -> None:
    """Two approved synthetic schools contend for one new family, without IdP provisioning."""
    batches = []
    parents = [
        {"id": str(uuid.uuid4()), "contact": str(uuid.uuid4()) + "@synthetic.invalid"}
        for _ in range(2)
    ]
    with db.transaction():
        if db.execute("SELECT current_user").fetchone() != ("retiro_importer",):
            raise RuntimeError("Importer required")
        for school, site, reverse in [
            (data["batch"]["school_id"], data["batch"]["students"][0]["site_id"], False),
            (data["other_school_id"], data["other_site_id"], True),
        ]:
            student = {
                **data["batch"]["students"][0],
                "id": str(uuid.uuid4()),
                "site_id": site,
                "name": "Synthetic family scope contention",
            }
            members = list(reversed(parents)) if reverse else parents
            batch = {
                "schema_version": 1,
                "id": str(uuid.uuid4()),
                "school_id": school,
                "parents": members,
                "students": [student],
                "links": [
                    {"student_id": student["id"], "parent_id": p["id"], "principal": i == 0}
                    for i, p in enumerate(members)
                ],
            }
            raw = json.dumps(batch, sort_keys=True)
            digest = hashlib.sha256(raw.encode()).hexdigest()
            for operation in ["STAGE", "APPROVE"]:
                db.execute(
                    "SELECT e2_import(%s,%s,%s,%s,%s,%s)",
                    (
                        operation,
                        batch["id"],
                        raw if operation == "STAGE" else "",
                        digest,
                        "E2_SYNTHETIC_OPERATOR",
                        "E2_SYNTHETIC_APPROVAL",
                    ),
                )
            batches.append((batch, digest))
    names = ["e2-bulk-" + str(uuid.uuid4()) for _ in batches]

    def promote(index: int) -> bool:
        batch, digest = batches[index]
        try:
            with psycopg.connect(autocommit=True, connect_timeout=5) as client:
                client.execute("SELECT set_config('application_name',%s,false)", (names[index],))
                client.execute("SET statement_timeout='15s'")
                client.execute(
                    "SELECT e2_import('PROMOTE',%s,'',%s,%s,%s)",
                    (batch["id"], digest, "E2_SYNTHETIC_OPERATOR", "E2_SYNTHETIC_APPROVAL"),
                )
            return True
        except psycopg.errors.InvalidParameterValue:
            return False

    with db.transaction():
        db.execute("LOCK TABLE school_roster_parent IN SHARE MODE")
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = [pool.submit(promote, i) for i in range(2)]
            try:
                deadline = time.monotonic() + 10
                while True:
                    # Statistics otherwise retain the first snapshot for this transaction.
                    db.execute("SELECT pg_stat_clear_snapshot()")
                    if db.execute(
                        "SELECT count(*) FROM pg_stat_activity WHERE application_name "
                        "IN (%s,%s) AND wait_event_type='Lock'",
                        tuple(names),
                    ).fetchone() == (2,):
                        break
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Contention not reached")
                    time.sleep(0.02)
            finally:
                db.execute("COMMIT")
            if sum(result.result(timeout=15) for result in pending) != 1:
                raise RuntimeError("Concurrent cross-school promotion accepted")
    with db.transaction():
        if db.execute(
            "SELECT count(DISTINCT school_id) FROM school_roster_link WHERE parent_id IN (%s,%s)",
            tuple(p["id"] for p in parents),
        ).fetchone() != (1,):
            raise RuntimeError("Cross-school family links")
        if db.execute(
            "SELECT count(*) FROM school_roster_student WHERE id IN (%s,%s)",
            tuple(b[0]["students"][0]["id"] for b in batches),
        ).fetchone() != (1,):
            raise RuntimeError("Partial or duplicate student activation")


def main() -> None:
    if os.environ.get("APP_ENV") != "staging" or os.environ.get("PGSSLMODE") != "verify-full":
        raise RuntimeError("Private synthetic TLS task required")
    data = json.loads(os.environ["E2_FIXTURE_COMMAND"])
    with psycopg.connect(connect_timeout=5) as db:
        if db.execute("SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()").fetchone() != (
            True,
        ):
            raise RuntimeError("Verified TLS connection required")
        db.commit()
        db.execute("SET statement_timeout='30s'")
        db.commit()
        if data["action"] == "bulk-drill":
            bulk_drill(db, data)
        else:
            seed(db, data)
    print("E2 private synthetic command committed.")


if __name__ == "__main__":
    try:
        main()
    except CohortUsed:
        print("E2 synthetic cohort already reserved; history preserved.")
        raise SystemExit(42) from None
    except Exception:
        print("BLOCKED: E2 synthetic command rejected; no partial transaction.")
        raise SystemExit(2) from None
