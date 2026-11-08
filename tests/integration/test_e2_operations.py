"""Private CLI security and transaction boundaries, using real PostgreSQL."""

import io
import json
import os
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from school_roster.management.commands.family_ops import read_batch

from tests.integration.e1_support import connect, digest
from tests.integration.test_e2_family import batch, import_batch

pytestmark = pytest.mark.integration
IMPORT_URL = "postgresql://retiro_importer:synthetic-importer-only@127.0.0.1:5432/"


@pytest.fixture(autouse=True)
def runtime_database(django_db_blocker: Any) -> Any:
    with django_db_blocker.unblock():
        yield


def test_schema_rejects_duplicate_keys_unknown_fields_and_noncanonical_contacts(
    tmp_path: Path,
) -> None:
    data = batch()
    path = tmp_path / "batch.json"
    path.write_text(json.dumps(data))
    assert read_batch(str(path))[1] == data
    path.write_text('{"schema_version":1,"schema_version":2}')
    with pytest.raises(ValueError):
        read_batch(str(path))
    path.write_text(json.dumps({**data, "claimed_role": "ADMIN_SISTEMA"}))
    with pytest.raises(ValueError):
        read_batch(str(path))


def test_cli_invitation_never_reaches_stdout_or_plaintext_database(tmp_path: Path) -> None:
    data = batch()
    import_batch(data)
    output = tmp_path / "invitation"
    stdout = io.StringIO()
    env = {"IMPORT_DATABASE_URL": IMPORT_URL + os.environ.get("PGDATABASE", "retiro")}
    with patch.dict(os.environ, env):
        call_command(
            "family_ops",
            "invite",
            id=data["parents"][0]["id"],
            operator="synthetic-operator",
            approval="school-approved",
            output=str(output),
            stdout=stdout,
        )
        token = output.read_text()
        assert len(token) == 43 and output.stat().st_mode & 0o777 == 0o600
        assert (
            token not in stdout.getvalue()
            and data["parents"][0]["contact"] not in stdout.getvalue()
        )
        with pytest.raises(CommandError):
            call_command(
                "family_ops",
                "invite",
                id=data["parents"][0]["id"],
                operator="synthetic-operator",
                approval="school-approved",
                output=str(output),
                stdout=stdout,
            )
        assert output.read_text() == token
    # Application processes have no SELECT on invitations; test inspect via migration identity.
    import psycopg

    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as db:
        db.execute("SET ROLE retiro_evidence_writer")
        row = db.execute(
            "SELECT token_hash,expires_at-issued_at FROM identity_invitation WHERE parent_id=%s",
            (data["parents"][0]["id"],),
        ).fetchone()
        assert row[0] == digest(token) and row[1].total_seconds() == 86400


def test_failed_cli_stage_cannot_partially_import_and_error_is_redacted(tmp_path: Path) -> None:
    data = batch()
    path = tmp_path / "batch.json"
    raw = json.dumps(data)
    path.write_text(raw)
    stdout = io.StringIO()
    with patch.dict(
        os.environ, {"IMPORT_DATABASE_URL": IMPORT_URL + os.environ.get("PGDATABASE", "retiro")}
    ):
        with pytest.raises(CommandError) as error:
            call_command(
                "family_ops",
                "stage",
                id=data["id"],
                file=str(path),
                sha256="0" * 64,
                operator="synthetic-operator",
                stdout=stdout,
            )
        assert data["parents"][0]["contact"] not in str(error.value)
    with connect("importer") as db:
        assert db.execute(
            "SELECT count(*) FROM school_roster_student WHERE id=%s", (data["students"][0]["id"],)
        ).fetchone() == (0,)


def test_cloud_seed_uses_the_same_private_boundary_and_never_receives_raw_invites() -> None:
    from scripts.seed_e2_roster import seed
    from tests.integration.test_e2_family import issue, redeem

    payload = batch()
    raw_tokens = {p["id"]: "synthetic-unused-" + p["id"] for p in payload["parents"]}
    command = {
        "action": "seed",
        "batch": payload,
        "parents": [
            {"id": p["id"], "hash": digest(raw_tokens[p["id"]])} for p in payload["parents"]
        ],
    }
    with connect("importer") as db:
        seed(db, command)
    token = issue(payload)
    redeem(payload, token)


def test_consumed_cohort_is_not_reset_for_another_gate() -> None:
    from scripts.seed_e2_roster import CohortUsed, seed

    payload = batch()
    command = {
        "action": "seed",
        "batch": payload,
        "parents": [
            {"id": p["id"], "hash": digest("synthetic " + p["id"])} for p in payload["parents"]
        ],
    }
    with connect("importer") as db:
        seed(db, command)
        with pytest.raises(CohortUsed):
            seed(db, command)
        assert db.execute(
            "SELECT count(*) FROM school_roster_student WHERE id=%s",
            (payload["students"][0]["id"],),
        ).fetchone() == (1,)


def test_live_bulk_scope_drill_runs_with_the_private_importer_only() -> None:
    from scripts.seed_e2_roster import bulk_drill
    from tests.integration.e1_support import roster

    first = batch()
    second = roster()
    data = {
        "action": "bulk-drill",
        "batch": first,
        "other_school_id": str(second["school"]),
        "other_site_id": str(second["site"]),
    }
    # Only the synthetic test connections change identity; SQL/RLS/locks remain real.
    with patch.dict(
        os.environ, {"PGUSER": "retiro_importer", "PGPASSWORD": "synthetic-importer-only"}
    ):
        with connect("importer") as db:
            bulk_drill(db, data)


def test_private_technical_fixture_validates_oidc_subject_then_deactivates() -> None:
    from scripts.seed_e2_roster import seed
    from tests.integration.e1_support import login, roster

    scope = roster()
    target = scope["accounts"]["PADRE"]
    access, _, _ = login(target)
    command = {
        "action": "deactivate",
        "operation": "DEACTIVATE",
        "school_id": str(scope["school"]),
        "target": str(scope["student"]),
        "data": {},
        "issuer": "https://idp.example",
        "account_parent_id": str(scope["parent"]),
        "expected_accounts": [{"parent_id": str(scope["parent"]), "subject": str(target)}],
    }
    with connect("importer") as db:
        seed(db, command)
    with connect() as db:
        assert db.execute("SELECT e1_authenticate(%s,true)", (digest(access),)).fetchone() == (
            None,
        )
    # A prepared subject mismatch cannot execute even the fixed technical command.
    command["expected_accounts"][0]["subject"] = str(uuid.uuid4())
    with connect("importer") as db, pytest.raises(RuntimeError, match="subject"):
        seed(db, command)
