"""E0 static infrastructure security boundaries; live commissioning is separate."""

import json
from pathlib import Path


def test_staging_database_is_private_encrypted_and_bounded() -> None:
    resources = json.loads(Path("infra/aws/staging-base.json").read_text())["Resources"]
    db = resources["Database"]["Properties"]
    assert db["StorageEncrypted"] is True
    assert db["BackupRetentionPeriod"] == 1
    assert db["DeletionProtection"] is True
    assert db["DBInstanceClass"] == "db.t4g.micro"
    assert db["AllocatedStorage"] == "20"
    assert db["PubliclyAccessible"] is False
    assert resources["Database"]["DeletionPolicy"] == "Retain"
    assert "SecurityGroupIngress" not in resources["AppSecurityGroup"]["Properties"]


def test_runtime_execution_cannot_read_migration_or_master_credentials() -> None:
    resources = json.loads(Path("infra/aws/staging-base.json").read_text())["Resources"]
    policies = resources["ApiExecution"]["Properties"]["Policies"][0]["PolicyDocument"]["Statement"]
    secrets = next(p for p in policies if p["Action"] == ["secretsmanager:GetSecretValue"])[
        "Resource"
    ]
    assert secrets == [
        {"Fn::If": ["Create" + name, {"Ref": name}, {"Ref": "Existing" + name}]}
        for name in ["RuntimePassword", "DjangoSecret"]
    ]
    for name in ["Deploy", "Migrate"]:
        trust = resources[name]["Properties"]["AssumeRolePolicyDocument"]["Statement"][0]
        assert (
            trust["Condition"]["StringEquals"]["token.actions.githubusercontent.com:aud"]
            == "sts.amazonaws.com"
        )
        assert trust["Condition"]["StringEquals"][
            "token.actions.githubusercontent.com:sub"
        ].endswith(":ref:refs/heads/main")
    assert (
        resources["Deploy"]["Properties"]["RoleName"]
        != resources["Migrate"]["Properties"]["RoleName"]
    )
