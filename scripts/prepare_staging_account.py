"""CloudShell-only preparation: ECS SLR and safe recovery of an empty failed base stack."""

import json
import subprocess
import time
from typing import Any


def read(*args: str, absent: str = "") -> dict[str, Any] | None:
    result = subprocess.run(
        ["aws", *args, "--region", "us-east-1", "--output", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        if absent and absent in result.stderr:
            return None
        raise SystemExit(
            "BLOCKED: AWS " + ".".join(args[:2]) + " failed; inspect the operation in CloudShell"
        )
    return json.loads(result.stdout) if result.stdout.strip() else {}


def main() -> None:
    if (
        read("iam", "get-role", "--role-name", "AWSServiceRoleForECS", absent="NoSuchEntity")
        is None
    ):
        read("iam", "create-service-linked-role", "--aws-service-name", "ecs.amazonaws.com")
        time.sleep(30)
    stack = read(
        "cloudformation",
        "describe-stacks",
        "--stack-name",
        "retiro-staging-base",
        absent="does not exist",
    )
    if stack and stack["Stacks"][0]["StackStatus"] == "ROLLBACK_COMPLETE":
        resources = read(
            "cloudformation", "describe-stack-resources", "--stack-name", "retiro-staging-base"
        )
        assert resources is not None
        for resource in resources["StackResources"]:
            if (
                resource["ResourceType"].startswith("AWS::RDS::")
                and resource.get("PhysicalResourceId")
                and resource["ResourceStatus"] not in {"DELETE_COMPLETE", "CREATE_FAILED"}
            ):
                raise SystemExit(
                    "BLOCKED: retained RDS resource needs operator recovery; nothing deleted"
                )
        read("cloudformation", "delete-stack", "--stack-name", "retiro-staging-base")
        subprocess.run(
            [
                "aws",
                "cloudformation",
                "wait",
                "stack-delete-complete",
                "--region",
                "us-east-1",
                "--stack-name",
                "retiro-staging-base",
            ],
            check=True,
        )
    parameters = []
    for name in ["RuntimePassword", "MigrationPassword", "DjangoSecret"]:
        secret = read(
            "secretsmanager",
            "describe-secret",
            "--secret-id",
            "retiro-staging/" + name,
            absent="ResourceNotFoundException",
        )
        arn = ""
        if secret:
            if {t["Key"]: t["Value"] for t in secret.get("Tags", [])}.get(
                "Project"
            ) != "retiro-seguro" or secret.get("DeletedDate"):
                raise SystemExit("BLOCKED: secret ownership/state mismatch")
            arn = secret["ARN"]
        parameters.append("Existing" + name + "=" + arn)
    print("\n".join(parameters))


if __name__ == "__main__":
    main()
