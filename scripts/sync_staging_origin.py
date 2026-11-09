"""Operator-only update of an existing E1 callback after an Express hostname changes."""

import argparse
import json
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any

from scripts.aws_cli import aws
from scripts.commission_e1 import validate_operator

STACK = "retiro-staging-e1"


def require_web_origin(reviewed: str, callback: str) -> None:
    if not re.fullmatch(r"https://[a-z0-9-]+\.ecs\.us-east-1\.on\.aws", reviewed):
        raise RuntimeError("BLOCKED: reviewed Express HTTPS origin required")
    if callback != reviewed + "/auth/callback":
        raise RuntimeError("BLOCKED: STAGING_ORIGIN_DRIFT; operator callback sync required")


def validate_change_set(changes: list[dict[str, Any]]) -> None:
    if len(changes) != 1:
        raise RuntimeError("BLOCKED: callback update must modify exactly one resource")
    change = changes[0].get("ResourceChange", {})
    if (
        change.get("LogicalResourceId") != "WebClient"
        or change.get("ResourceType") != "AWS::Cognito::UserPoolClient"
        or change.get("Action") != "Modify"
        or change.get("Replacement") != "False"
        or change.get("Scope") != ["Properties"]
        or not change.get("Details")
        or any(
            detail.get("Target", {}).get("Attribute") != "Properties"
            or detail.get("Target", {}).get("Name") != "CallbackURLs"
            for detail in change["Details"]
        )
    ):
        raise RuntimeError("BLOCKED: change set exceeds the existing web callback")


def values(stack: dict[str, Any]) -> dict[str, str]:
    return {item["OutputKey"]: item["OutputValue"] for item in stack["Outputs"]}


def sync(configuration: dict[str, Any]) -> None:
    validate_operator(aws("sts", "get-caller-identity"))
    if (
        configuration.get("synthetic_only") is not True
        or configuration.get("pickup_enabled") is not False
        or configuration.get("account_id") != "028364485203"
    ):
        raise RuntimeError("BLOCKED: configured synthetic staging required")
    origin = configuration["base_url"]
    require_web_origin(origin, origin + "/auth/callback")
    service = aws(
        "ecs", "describe-express-gateway-service", "--service-arn", configuration["service"]
    )["service"]
    if service.get("status", {}).get("statusCode") != "ACTIVE":
        raise RuntimeError("BLOCKED: active observed Express service required")
    paths = service["activeConfigurations"][0]["ingressPaths"]
    if len(paths) != 1 or paths[0]["endpoint"].removeprefix("https://") != origin[8:]:
        raise RuntimeError("BLOCKED: observed hostname differs from reviewed configuration")
    before = aws("cloudformation", "describe-stacks", "--stack-name", STACK)["Stacks"][0]
    previous = values(before)
    parameters = {p["ParameterKey"]: p["ParameterValue"] for p in before["Parameters"]}
    if set(parameters) != {"WebOrigin", "MobileRedirect", "ExistingLogsArn"}:
        raise RuntimeError("BLOCKED: unexpected E1 stack parameters")
    if parameters["WebOrigin"] != origin:
        change_set = "callback-origin-" + uuid.uuid4().hex
        aws(
            "cloudformation",
            "create-change-set",
            "--stack-name",
            STACK,
            "--change-set-name",
            change_set,
            "--change-set-type",
            "UPDATE",
            "--use-previous-template",
            "--capabilities",
            "CAPABILITY_NAMED_IAM",
            "--parameters",
            json.dumps(
                [
                    {"ParameterKey": key, "ParameterValue": origin}
                    if key == "WebOrigin"
                    else {"ParameterKey": key, "UsePreviousValue": True}
                    for key in parameters
                ]
            ),
        )
        aws(
            "cloudformation",
            "wait",
            "change-set-create-complete",
            "--stack-name",
            STACK,
            "--change-set-name",
            change_set,
        )
        planned = aws(
            "cloudformation",
            "describe-change-set",
            "--stack-name",
            STACK,
            "--change-set-name",
            change_set,
        )
        if planned.get("Status") != "CREATE_COMPLETE":
            raise RuntimeError("BLOCKED: callback change set not ready")
        validate_change_set(planned.get("Changes", []))
        print("Verified change set: existing WebClient.CallbackURLs only; no replacement")
        aws(
            "cloudformation",
            "execute-change-set",
            "--stack-name",
            STACK,
            "--change-set-name",
            change_set,
        )
        aws("cloudformation", "wait", "stack-update-complete", "--stack-name", STACK)
    current = values(aws("cloudformation", "describe-stacks", "--stack-name", STACK)["Stacks"][0])
    require_web_origin(origin, current["WebRedirect"])
    if {k: v for k, v in previous.items() if k != "WebRedirect"} != {
        k: v for k, v in current.items() if k != "WebRedirect"
    }:
        raise RuntimeError("BLOCKED: preserved E1 resource outputs changed")
    client = aws(
        "cognito-idp",
        "describe-user-pool-client",
        "--user-pool-id",
        current["PoolId"],
        "--client-id",
        current["WebClientId"],
    )["UserPoolClient"]
    if client.get("CallbackURLs") != [origin + "/auth/callback"]:
        raise RuntimeError("BLOCKED: actual web callback differs from reviewed origin")
    print("Existing E1 web callback synchronized; no acceptance or account provisioning claimed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", required=True)
    args = parser.parse_args()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    latest = subprocess.check_output(
        ["git", "ls-remote", "origin", "refs/heads/main"], text=True
    ).split()[0]
    if (
        head != args.sha
        or latest != args.sha
        or subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
    ):
        raise RuntimeError("BLOCKED: clean reviewed latest-main checkout required")
    sync(json.loads(Path("infra/environments/staging.json").read_text()))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("BLOCKED: staging callback synchronization incomplete; inspect privately")
        raise SystemExit(2) from None
