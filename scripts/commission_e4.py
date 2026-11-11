"""Operator-only E4 IAM/alert commissioning. No notices, imports or school activation."""

import argparse
import json
import re
import subprocess
from pathlib import Path

from scripts.aws_cli import aws
from scripts.commission_e1 import billing_preflight, outputs, validate_operator


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alert-topic-arn", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"arn:aws:sns:us-east-1:028364485203:[A-Za-z0-9_-]+", args.alert_topic_arn):
        raise RuntimeError("BLOCKED: project operator alert topic required")
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        raise RuntimeError("BLOCKED: clean reviewed checkout required")
    validate_operator(aws("sts", "get-caller-identity"))
    billing = billing_preflight()
    subscribed = aws("sns", "list-subscriptions-by-topic", "--topic-arn", args.alert_topic_arn)
    if subscribed.get("NextToken") or not any(
        value.get("SubscriptionArn", "").startswith("arn:aws:sns:")
        for value in subscribed.get("Subscriptions", [])
    ):
        raise RuntimeError("BLOCKED: confirmed operator alert subscription required")
    base, e1 = outputs("retiro-staging-base"), outputs("retiro-staging-e1")
    names = {}
    for field, name in [
        ("ExpoAccessTokenSecretArn", "retiro-staging/e4/ExpoAccessToken"),
        ("AllowedDevicesSecretArn", "retiro-staging/e4/AllowedDeviceHashes"),
    ]:
        secret = aws("secretsmanager", "describe-secret", "--secret-id", name)
        if secret.get("DeletedDate") or not any(
            "AWSCURRENT" in stages for stages in secret.get("VersionIdsToStages", {}).values()
        ):
            raise RuntimeError("BLOCKED: current E4 managed secret required")
        names[field] = secret["ARN"]
    parameters = {
        **names,
        "SchoolReadPasswordArn": e1["SchoolReadPassword"],
        "NotifierPasswordArn": e1["NotifierPassword"],
        "ExistingLogsArn": f"arn:aws:logs:us-east-1:028364485203:log-group:{base['Logs']}:*",
        "ExistingLogsName": base["Logs"],
        "OperatorAlertTopicArn": args.alert_topic_arn,
    }
    result = subprocess.run(
        [
            "aws",
            "cloudformation",
            "deploy",
            "--region",
            "us-east-1",
            "--stack-name",
            "retiro-staging-e4",
            "--template-file",
            "infra/aws/e4-staging.yaml",
            "--capabilities",
            "CAPABILITY_NAMED_IAM",
            "--no-fail-on-empty-changeset",
            "--parameter-overrides",
            *[f"{key}={value}" for key, value in parameters.items()],
            "--tags",
            "Project=retiro-seguro",
            "Environment=staging",
            "Data=synthetic",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("BLOCKED: E4 stack failed; inspect private events")
    report = {
        "sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "billing": billing,
        "stack_outputs_present": bool(outputs("retiro-staging-e4")),
        "e4_accepted": False,
        "scope": (
            "IAM/alert resources only; provider, alarm delivery "
            "and integrated acceptance remain required"
        ),
    }
    Path("work").mkdir(exist_ok=True)
    Path("work/e4-commission.json").write_text(json.dumps(report, indent=2) + "\n")
    print("E4 resources commissioned; no deployment, notification or acceptance claimed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print("BLOCKED: E4 commissioning rejected; inspect configuration privately")
        raise SystemExit(2) from None
