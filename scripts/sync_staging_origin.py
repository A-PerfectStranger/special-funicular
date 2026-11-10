"""Operator-only update of an existing E1 callback after an Express hostname changes."""

import argparse
import json
import os
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any

from scripts.aws_cli import aws
from scripts.commission_e1 import validate_operator

STACK = "retiro-staging-e1"


def gateway_origin(service: dict[str, Any]) -> str:
    if service.get("status", {}).get("statusCode") != "ACTIVE":
        raise RuntimeError("BLOCKED: active observed Express service required")
    configurations = service.get("activeConfigurations", [])
    if len(configurations) != 1 or len(configurations[0].get("ingressPaths", [])) != 1:
        raise RuntimeError("BLOCKED: single active gateway origin required")
    endpoint = configurations[0]["ingressPaths"][0].get("endpoint")
    if not isinstance(endpoint, str):
        raise RuntimeError("BLOCKED: single active gateway origin required")
    origin = endpoint if endpoint.startswith("https://") else "https://" + endpoint
    require_web_origin(origin, origin + "/auth/callback")
    return origin


def release_origin() -> str:
    origin = os.environ.get("STAGING_RELEASE_ORIGIN", "")
    require_web_origin(origin, origin + "/auth/callback")
    return origin


def safe_failure(error: Exception) -> str:
    # Our errors contain fixed messages; AWS CLI text has already been reduced to a code.
    fixed = {
        "BLOCKED: reviewed Express HTTPS origin required",
        "BLOCKED: STAGING_ORIGIN_DRIFT; operator callback sync required",
        "BLOCKED: callback update must modify exactly one resource",
        "BLOCKED: change set exceeds the existing web callback",
        "BLOCKED: configured synthetic staging required",
        "BLOCKED: active observed Express service required",
        "BLOCKED: single active gateway origin required",
        "BLOCKED: unexpected E1 stack parameters",
        "BLOCKED: callback change set not ready",
        "BLOCKED: preserved E1 resource outputs changed",
        "BLOCKED: actual web callback differs from reviewed origin",
        "BLOCKED: clean reviewed latest-main checkout required",
        "BLOCKED: active API does not belong to the approved candidate",
        "Wrong AWS account",
        "Verified AWS operator identity required",
        "CI/runtime roles are not provisioning operators",
    }
    if isinstance(error, RuntimeError) and str(error) in fixed:
        return str(error)
    match = re.fullmatch(
        r"(sts\.get-caller-identity|ecs\.describe-express-gateway-service|"
        r"ecs\.describe-task-definition|ecr\.describe-images|cloudformation\.(?:describe-stacks|create-change-set|"
        r"wait|describe-change-set|execute-change-set)|cognito-idp\.describe-user-pool-client)"
        r": ([A-Za-z0-9_]{1,64})",
        str(error),
    )
    if isinstance(error, RuntimeError) and match:
        known = {
            "AccessDenied",
            "AccessDeniedException",
            "ResourceNotFoundException",
            "ValidationError",
            "ExpiredToken",
            "ExpiredTokenException",
            "InvalidClientTokenId",
            "ThrottlingException",
            "UnrecognizedClientException",
            "CliRequestFailed",
            "ImageNotFoundException",
            "RepositoryNotFoundException",
        }
        return match[1] + ": " + (match[2] if match[2] in known else "AWS_REQUEST_FAILED")
    return "UNCLASSIFIED_FAILURE; inspect privately"


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


def sync(configuration: dict[str, Any], expected_sha: str) -> None:
    validate_operator(aws("sts", "get-caller-identity"))
    if (
        configuration.get("synthetic_only") is not True
        or configuration.get("pickup_enabled") is not False
        or configuration.get("account_id") != "028364485203"
    ):
        raise RuntimeError("BLOCKED: configured synthetic staging required")
    service = aws(
        "ecs", "describe-express-gateway-service", "--service-arn", configuration["service"]
    )["service"]
    origin = gateway_origin(service)
    definition = aws(
        "ecs",
        "describe-task-definition",
        "--task-definition",
        service["activeConfigurations"][0]["taskDefinitionArn"],
    )["taskDefinition"]
    containers = definition.get("containerDefinitions", [])
    if len(containers) != 1:
        raise RuntimeError("BLOCKED: active API does not belong to the approved candidate")
    environment = {v["name"]: v["value"] for v in containers[0].get("environment", [])}
    if environment.get("GIT_SHA") != expected_sha or not re.fullmatch(
        r"028364485203\.dkr\.ecr\.us-east-1\.amazonaws\.com/retiro-staging/backend@sha256:[0-9a-f]{64}",
        containers[0].get("image", ""),
    ):
        raise RuntimeError("BLOCKED: active API does not belong to the approved candidate")
    images = aws(
        "ecr",
        "describe-images",
        "--repository-name",
        "retiro-staging/backend",
        "--image-ids",
        "imageTag=" + expected_sha,
    ).get("imageDetails", [])
    if len(images) != 1 or containers[0]["image"] != (
        "028364485203.dkr.ecr.us-east-1.amazonaws.com/retiro-staging/backend@"
        + images[0].get("imageDigest", "")
    ):
        raise RuntimeError("BLOCKED: active API does not belong to the approved candidate")
    print("Observed approved candidate origin: " + origin)
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
    sync(json.loads(Path("infra/environments/staging.json").read_text()), args.sha)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("BLOCKED: staging callback synchronization incomplete; " + safe_failure(error))
        raise SystemExit(2) from None
