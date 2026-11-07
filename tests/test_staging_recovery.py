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
