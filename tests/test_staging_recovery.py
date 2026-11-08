"""A failed first bootstrap must not delete retained data or take foreign secrets."""

from typing import Any

import pytest

from scripts import prepare_staging_account


def test_retained_database_blocks_stack_deletion(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []

    def read(*args: str, **kwargs: str) -> dict[str, Any]:
        calls.append(args)
        if args[:2] == ("iam", "get-role"):
            return {"Role": {}}
        if args[1] == "describe-stacks":
            return {"Stacks": [{"StackStatus": "ROLLBACK_COMPLETE"}]}
        return {
            "StackResources": [
                {
                    "ResourceType": "AWS::RDS::DBCluster",
                    "PhysicalResourceId": "keep",
                    "ResourceStatus": "DELETE_SKIPPED",
                }
            ]
        }

    monkeypatch.setattr(prepare_staging_account, "read", read)
    with pytest.raises(SystemExit, match="retained RDS"):
        prepare_staging_account.main()
    assert not any("delete-stack" in call for call in calls)


def test_foreign_secret_is_never_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    def read(*args: str, **kwargs: str) -> dict[str, Any] | None:
        if args[0] == "iam":
            return {}
        if args[0] == "cloudformation":
            return None
        return {"ARN": "foreign", "Tags": [{"Key": "Project", "Value": "other"}]}

    monkeypatch.setattr(prepare_staging_account, "read", read)
    with pytest.raises(SystemExit, match="ownership"):
        prepare_staging_account.main()


@pytest.mark.parametrize("kind", ["AWS::RDS::DBSubnetGroup", "AWS::RDS::DBCluster"])
def test_residual_metadata_without_database_can_recover(
    kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    calls: list[tuple[str, ...]] = []

    def read(*args: str, **kwargs: str) -> dict[str, Any] | None:
        calls.append(args)
        if args[:2] == ("iam", "get-role"):
            return {}
        if args[1] == "describe-stacks":
            return {"Stacks": [{"StackStatus": "ROLLBACK_COMPLETE"}]}
        if args[1] == "describe-stack-resources":
            return {
                "StackResources": [
                    {
                        "ResourceType": kind,
                        "PhysicalResourceId": "not-present",
                        "ResourceStatus": "DELETE_SKIPPED",
                    }
                ]
            }
        if args[0] in {"rds", "secretsmanager"}:
            return None
        return {}

    monkeypatch.setattr(prepare_staging_account, "read", read)
    monkeypatch.setattr(
        prepare_staging_account.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess([], 0),
    )
    prepare_staging_account.main()
    assert any("delete-stack" in call for call in calls)
