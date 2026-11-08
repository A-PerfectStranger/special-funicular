"""Inspection must reject extra write authority and accept equivalent IAM JSON shapes."""

from scripts.e1_policy_inspection import only_pool_reads, protects_application_keys


def test_api_policy_rejects_secret_and_crypto_access_including_not_action() -> None:
    assert only_pool_reads(
        [{"Statement": [{"Effect": "Allow", "Action": "cognito-idp:DescribeUserPoolDomain"}]}]
    )
    for statement in [
        {"Effect": "Allow", "Action": ["cognito-idp:DescribeUserPool", "kms:Sign"]},
        {"Effect": "Allow", "Action": "secretsmanager:GetSecretValue"},
        {"Effect": "Allow", "NotAction": "iam:DeleteRole"},
    ]:
        assert not only_pool_reads([{"Statement": [statement]}])


def test_key_denial_requires_all_admin_actions_and_the_actual_service_role_scope() -> None:
    statement = {
        "Effect": "Deny",
        "Principal": {"AWS": "*"},
        "Resource": "*",
        "Action": [
            "kms:DisableKey",
            "kms:ScheduleKeyDeletion",
            "kms:PutKeyPolicy",
            "kms:CreateGrant",
        ],
        "Condition": {
            "ArnLike": {"aws:PrincipalArn": ["arn:aws:iam::028364485203:role/retiro-staging-*"]}
        },
    }
    assert protects_application_keys({"Statement": [statement]})
    statement["Action"] = ["kms:DisableKey"]
    assert not protects_application_keys({"Statement": [statement]})
