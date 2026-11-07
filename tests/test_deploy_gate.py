import json
from pathlib import Path

import pytest

from scripts.validate_deploy import validate


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_unconfigured_targets_are_blocked(environment: str) -> None:
    config = json.loads(Path(f"infra/environments/{environment}.json").read_text())
    assert "missing account_id" in validate(config)
    assert "missing base_url" in validate(config)


def test_synthetic_gate_rejects_unsafe_configuration() -> None:
    config = json.loads(Path("infra/environments/staging.json").read_text())
    config.update(pickup_enabled=True, synthetic_only=False, credit_ceiling_usd=151)
    errors = validate(config)
    assert "E0 permits synthetic data only, with pickups disabled" in errors
    assert "verify actual spend/remaining credits and the 150 USD ceiling" in errors
