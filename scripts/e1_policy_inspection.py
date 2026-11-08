"""Read-only proof predicates over actual IAM/KMS policy documents, no policy mutations."""

from typing import Any


def only_pool_reads(policies: list[dict[str, Any]]) -> bool:
    allowed = {
        "cognito-idp:DescribeUserPool",
        "cognito-idp:DescribeUserPoolClient",
        "cognito-idp:GetUserPoolMfaConfig",
        "cognito-idp:DescribeUserPoolDomain",
    }
    for policy in policies:
        for statement in policy["Statement"]:
            if statement.get("Effect") == "Deny":
                continue
            actions = statement.get("Action")
            actions = [actions] if isinstance(actions, str) else actions
            if (
                statement.get("Effect") != "Allow"
                or statement.get("NotAction")
                or not isinstance(actions, list)
                or not actions
                or set(actions) - allowed
            ):
                return False
    return bool(policies)


def protects_application_keys(policy: dict[str, Any]) -> bool:
    required = {"kms:DisableKey", "kms:ScheduleKeyDeletion", "kms:PutKeyPolicy", "kms:CreateGrant"}
    for statement in policy.get("Statement", []):
        actions = statement.get("Action", [])
        actions = [actions] if isinstance(actions, str) else actions
        principals = statement.get("Principal")
        roles = statement.get("Condition", {}).get("ArnLike", {}).get("aws:PrincipalArn", [])
        roles = [roles] if isinstance(roles, str) else roles
        if (
            statement.get("Effect") == "Deny"
            and principals in ["*", {"AWS": "*"}]
            and statement.get("Resource") == "*"
            and set(actions) >= required
            and "arn:aws:iam::028364485203:role/retiro-staging-*" in roles
        ):
            return True
    return False
