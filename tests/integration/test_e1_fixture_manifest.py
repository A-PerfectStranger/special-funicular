"""Read-only recovery inspection rejects reassigned links or mixed staging data."""

import uuid

import pytest

from scripts.export_e1_snapshot import verify_closed_fixture, verify_roster_rows
from scripts.seed_e1_roster import seed_roster
from tests.integration.e1_support import connect, roster
from tests.integration.test_e1_fixture_seed import payload

pytestmark = pytest.mark.integration


def test_original_fixture_binding_is_checked_without_resetting_versions_or_rows() -> None:
    data = payload()
    with connect("importer") as importer:
        seed_roster(importer, data)
        verify_roster_rows(importer, data)
        data["links"][0]["parent_id"] = str(uuid.uuid4())
        with pytest.raises(RuntimeError, match="binding changed"):
            verify_roster_rows(importer, data)


def test_export_refuses_a_mixed_dataset_before_copying_private_evidence() -> None:
    roster()
    data = payload()
    with connect("importer") as importer:
        seed_roster(importer, data)
        with pytest.raises(RuntimeError, match="not the closed synthetic fixture"):
            verify_closed_fixture(importer, data)
