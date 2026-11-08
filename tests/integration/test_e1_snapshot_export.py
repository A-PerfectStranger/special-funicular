"""Real PostgreSQL export permissions and canonical-byte preservation, not AWS acceptance."""

import base64
import json
import uuid

import psycopg
import pytest

from scripts.e1_snapshot_data import rewrite_copy, validate_local_chain
from scripts.export_e1_snapshot import inspect_boundaries
from tests.integration.e1_support import connect

pytestmark = pytest.mark.integration


def test_only_private_importer_can_export_and_the_rewrite_remains_pg_canonical() -> None:
    for role in ["runtime", "archiver", "notifier", "school_read", "system_read"]:
        with connect(role) as db, pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("SELECT * FROM e1_export_fixture_snapshot(%s)", (uuid.uuid4(),))
    with connect("importer") as db:
        assert all(inspect_boundaries(db).values())
        correlation = uuid.uuid4()
        data = db.execute("SELECT * FROM e1_export_fixture_snapshot(%s)", (correlation,)).fetchall()
        rows = [
            dict(
                zip(
                    ["sequence", "event_id", "canonical_base64", "digest"],
                    [sequence, str(eid), canonical, digest],
                    strict=True,
                )
            )
            for sequence, eid, canonical, digest in data
        ]
        validate_local_chain(rows)
        last = json.loads(base64.b64decode(rows[-1]["canonical_base64"]))
        assert last["kind"] == "SYNTHETIC_SNAPSHOT_READ" and last["correlation_id"] == str(
            correlation
        )
        forged = rewrite_copy(rows)
        assert forged != rows
        validate_local_chain(forged)
        for record in forged:
            payload = base64.b64decode(record["canonical_base64"], validate=True)
            # The rewrite preserves PostgreSQL's format rather than inventing a new serializer.
            assert (
                bytes(
                    db.execute(
                        "SELECT convert_to((%s::jsonb)::text,'UTF8')", (payload.decode(),)
                    ).fetchone()[0]
                )
                == payload
            )
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("SELECT * FROM evidence_event")
