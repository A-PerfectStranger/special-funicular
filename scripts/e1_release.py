"""E1 task definitions share the approved image; credentials stay process-specific."""

import copy
from typing import Any

from scripts.commission_staging import task_definition


def require_configuration(config: dict[str, str]) -> None:
    required = [
        "Issuer",
        "PoolId",
        "WebClientId",
        "MobileClientId",
        "WebRedirect",
        "MobileRedirect",
        "ApiTaskArn",
        "ArchiveTaskArn",
        "ArchiveExecutionArn",
        "SystemReadPassword",
        "ArchivePassword",
        "Bucket",
        "EncryptionKeyArn",
        "SigningKeyArn",
    ]
    if any(not config.get(key) for key in required):
        raise RuntimeError("BLOCKED: complete E1 stack outputs required")
    if config["EncryptionKeyArn"] == config["SigningKeyArn"]:
        raise RuntimeError("BLOCKED: separate encryption and signing keys required")
    if config["Issuer"] != f"https://cognito-idp.us-east-1.amazonaws.com/{config['PoolId']}":
        raise RuntimeError("BLOCKED: unexpected Cognito issuer")
    if not config["WebRedirect"].startswith("https://") or not config["WebRedirect"].endswith(
        "/auth/callback"
    ):
        raise RuntimeError("BLOCKED: exact HTTPS web callback required")
    if config["MobileRedirect"] != "retiro-seguro-staging://auth/callback":
        raise RuntimeError("BLOCKED: staging mobile callback required")


def api_definition(
    base: dict[str, str], config: dict[str, str], image: str, sha: str
) -> dict[str, Any]:
    require_configuration(config)
    definition = copy.deepcopy(task_definition(base, image, sha, False))
    definition["taskRoleArn"] = config["ApiTaskArn"]
    container = definition["containerDefinitions"][0]
    environment = {item["name"]: item["value"] for item in container["environment"]}
    environment.update(
        {
            "E1_IDENTITY_ENABLED": "true",
            "AWS_REGION": "us-east-1",
            "OIDC_ISSUER": config["Issuer"],
            "OIDC_COGNITO_POOL_ID": config["PoolId"],
            "OIDC_WEB_CLIENT_ID": config["WebClientId"],
            "OIDC_MOBILE_CLIENT_ID": config["MobileClientId"],
            "OIDC_WEB_REDIRECT_URI": config["WebRedirect"],
            "OIDC_MOBILE_REDIRECT_URI": config["MobileRedirect"],
            "OIDC_MFA_POLICY": "cognito_required_totp",
        }
    )
    container["environment"] = [{"name": key, "value": value} for key, value in environment.items()]
    container["secrets"].append(
        {"name": "SYSTEM_READ_PASSWORD", "valueFrom": config["SystemReadPassword"]}
    )
    return definition


def archive_definition(
    base: dict[str, str], config: dict[str, str], image: str, sha: str
) -> dict[str, Any]:
    require_configuration(config)
    definition = copy.deepcopy(task_definition(base, image, sha, False))
    definition["family"] = "retiro-staging-archive"
    definition["taskRoleArn"] = config["ArchiveTaskArn"]
    definition["executionRoleArn"] = config["ArchiveExecutionArn"]
    container = definition["containerDefinitions"][0]
    container.pop("portMappings", None)
    container["command"] = [
        "python",
        "-m",
        "archive_worker.runner",
        "--max-runtime-seconds",
        "10800",
    ]
    environment = {item["name"]: item["value"] for item in container["environment"]}
    environment.update(
        {
            "PGUSER": "retiro_archiver",
            "AWS_REGION": "us-east-1",
            "ARCHIVE_BUCKET": config["Bucket"],
            "ARCHIVE_KMS_KEY_ARN": config["EncryptionKeyArn"],
            "MANIFEST_KMS_KEY_ARN": config["SigningKeyArn"],
            "ARCHIVE_RETENTION_DAYS": "7",
        }
    )
    container["environment"] = [{"name": key, "value": value} for key, value in environment.items()]
    container["secrets"] = [{"name": "PGPASSWORD", "valueFrom": config["ArchivePassword"]}]
    container["logConfiguration"]["options"]["awslogs-stream-prefix"] = "archive"
    return definition
