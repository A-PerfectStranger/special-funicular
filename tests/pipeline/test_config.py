import json
from pathlib import Path

import pytest

from scripts.validate_deploy import validate


@pytest.mark.parametrize("target", ["staging", "production"])
def test_checked_in_destinations_are_blocked(target: str) -> None:
    config = json.loads(Path(f"infra/environments/{target}.json").read_text())
    assert "destino bloqueado/no configurado" in validate(config, target)


def test_valid_config_cannot_remove_budget_or_enable_pickup() -> None:
    config = {
        "environment": "staging",
        "provider": "aws",
        "configured": True,
        "account_id": "123456789012",
        "region": "us-east-1",
        "deploy_role_arn": "arn:aws:iam::123456789012:role/deploy-staging",
        "base_url": "https://synthetic.example.invalid",
        "total_credit_limit_usd": 150,
        "synthetic_only": True,
        "pickup_enabled": False,
        "staging_evidence_verified": True,
    }
    assert validate(config, "staging") == []
    assert validate(config, "production")
    for key, value in [
        ("total_credit_limit_usd", 151),
        ("total_credit_limit_usd", True),
        ("pickup_enabled", True),
        ("synthetic_only", False),
        ("base_url", "http://insecure.invalid"),
        ("configured", "true"),
        ("staging_evidence_verified", False),
        ("deploy_role_arn", "arn:aws:iam::000000000000:role/wrong"),
    ]:
        assert validate({**config, key: value}, "staging"), key


def test_actions_are_pinned_and_cd_never_claims_deployment() -> None:
    import re

    import yaml

    for path in Path(".github/workflows").glob("*.yml"):
        workflow = yaml.safe_load(path.read_text())
        assert workflow["permissions"] == {"contents": "read"}
        for job in workflow["jobs"].values():
            for step in job.get("steps", []):
                if "uses" in step:
                    assert re.fullmatch(r"[A-Za-z0-9_./-]+@[a-f0-9]{40}", step["uses"])
    cd = yaml.safe_load(Path(".github/workflows/cd.yml").read_text())
    assert cd["concurrency"]["cancel-in-progress"] is False
    assert "exit 2" in cd["jobs"]["validate-staging"]["steps"][-1]["run"]
