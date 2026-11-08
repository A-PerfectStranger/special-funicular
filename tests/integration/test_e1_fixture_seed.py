"""Private acceptance fixtures use real importer/RLS/constraints, no IdP simulation claim."""

import uuid
from typing import Any

import pytest

from scripts.e1_fixture_data import catalogue, roster_payload
from scripts.seed_e1_roster import seed_roster
from tests.integration.e1_support import connect


def payload() -> dict[str, Any]:
    return roster_payload(
        "https://fixture.example",
        {
            name: {
                "sub": str(uuid.uuid5(uuid.NAMESPACE_URL, "local-e1/" + name)),
                "password": "never-export-this",
                "totp_seed": "never-export-this",
            }
            for name in catalogue()
        },
    )


def test_fixture_catalogue_has_two_families_each_school_and_never_exports_credentials() -> None:
    data = payload()
    assert len(data["schools"]) == 2 and len(data["accounts"]) == 13
    assert len(data["students"]) == 6 and len(data["parents"]) == 8
    assert len(data["links"]) == 12
    assert "never-export-this" not in str(data)
    for student in data["students"]:
        links = [link for link in data["links"] if link["student_id"] == student["id"]]
        assert sum(link["principal"] for link in links) == 1


@pytest.mark.integration
def test_private_seed_is_idempotent_and_refuses_rebinding() -> None:
    data = payload()
    with connect("importer") as importer:
        seed_roster(importer, data)
        seed_roster(importer, data)
        assert importer.execute(
            "SELECT count(*) FROM identity_account WHERE issuer='https://fixture.example'"
        ).fetchone() == (13,)
        data["accounts"][0]["subject"] = str(uuid.uuid4())
        with pytest.raises(RuntimeError, match="no implicit"):
            seed_roster(importer, data)
        actual = importer.execute(
            "SELECT subject FROM identity_account WHERE id=%s", (data["accounts"][0]["id"],)
        ).fetchone()
        assert actual[0] != data["accounts"][0]["subject"]
