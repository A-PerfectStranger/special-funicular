"""A configured E3 candidate cannot silently bypass its real E2/E3/WORM gate."""

import json
from pathlib import Path

import pytest
import yaml

from scripts.e1_release import api_definition
from scripts.e3_fixture_data import CASES, fixture_batch
from scripts.provision_e2_fixtures import cohort
from scripts.validate_deploy import validate
from tests.test_e1_release import configuration


def test_e3_candidate_is_explicit_and_never_receives_importer_or_archive_credentials() -> None:
    base, config = configuration()
    with pytest.raises(RuntimeError, match="requires E2"):
        api_definition(base, config, "image", "sha", enable_pickup=True)
    api = api_definition(base, config, "image", "sha", enable_family=True, enable_pickup=True)
    container = api["containerDefinitions"][0]
    assert {e["name"]: e["value"] for e in container["environment"]}["E3_PICKUP_ENABLED"] == "true"
    assert len(container["secrets"]) == 3
    candidate = json.loads(Path("infra/environments/staging.json").read_text())
    assert candidate["pickup_enabled"] is False and candidate["synthetic_only"] is True
    assert candidate["e3_enabled"] is True
    assert not validate(candidate)
    for values in [{"e2_enabled": False}, {"e1_enabled": False}, {"environment": "production"}]:
        assert "E3 requires synthetic staging and E1/E2 gates" in validate({**candidate, **values})


def test_required_pipeline_runs_e3_before_the_independent_chain_verifier() -> None:
    cd = yaml.safe_load(Path(".github/workflows/cd.yml").read_text())
    assert (
        cd["jobs"]["e2-acceptance"]["with"]["enable_pickup"]
        == "${{ needs.staging.outputs.e3_enabled == 'true' }}"
    )
    shared = yaml.safe_load(Path(".github/workflows/e2-checks.yml").read_text())
    steps = shared["jobs"]["family"]["steps"]
    trial = next(i for i, s in enumerate(steps) if "scripts.run_e3_browser" in s.get("run", ""))
    verifier = next(i for i, s in enumerate(steps) if "--role E1Verifier" in s.get("run", ""))
    assert trial < verifier and steps[trial]["if"] == "inputs.enable_pickup"
    assert "work/e3-browser-acceptance.json" in steps[verifier]["run"]


def test_synthetic_faults_are_bounded_and_use_independent_student_episodes() -> None:
    import uuid

    source = cohort("a" * 40, str(uuid.uuid4()))
    batch = fixture_batch(source)
    assert len(batch["students"]) == len(CASES) == 8
    assert len({s["id"] for s in batch["students"]}) == 8
    assert batch["students"][0]["id"] != source["batch"]["students"][0]["id"]
    assert batch["parents"] == source["batch"]["parents"]
    assert source["batch"]["students"][0]["windows"][0]["from"] == "07:00"
