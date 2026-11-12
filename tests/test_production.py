"""Production cost, isolation, digest and rollback boundaries; cloud acceptance is separate."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from cfnlint.decode import decode

from scripts import commission_production as commission
from scripts import deploy_production as deploy
from scripts import production
from scripts import production_preflight as billing
from scripts.validate_deploy import validate

SHA = "a" * 40
DIGEST = "sha256:" + "b" * 64


def base() -> dict[str, str]:
    values = {
        key: key
        for key in [
            "DbHost",
            "Logs",
            "ApiExecution",
            "MigrationExecution",
            "BootstrapExecution",
            "MasterSecret",
            "Public0",
            "Public1",
            "AppSecurityGroup",
            "ExpressInfrastructure",
            "DatabaseKeyArn",
        ]
    }
    values.update({"Cluster": "retiro-production", "ImageRepository": production.IMAGE_REPOSITORY})
    for key in ["DjangoSecret", "RuntimePassword", "MigrationPassword"]:
        values[key] = (
            f"arn:aws:secretsmanager:us-east-1:{production.ACCOUNT}:secret:retiro-production/{key}-abcdef"
        )
    for key in ["Deploy", "Migrate"]:
        values[key] = f"arn:aws:iam::{production.ACCOUNT}:role/retiro-production-{key}"
    return values


def billing_data() -> tuple[dict, dict, dict, dict, datetime]:
    now = datetime.now(UTC)
    budget = {
        "TimeUnit": "CUSTOM",
        "BudgetType": "COST",
        "BudgetLimit": {"Unit": "USD", "Amount": "150"},
        "CostTypes": {"IncludeCredit": False, "IncludeRefund": False},
        "TimePeriod": {
            "Start": (now - timedelta(days=1)).isoformat(),
            "End": (now + timedelta(days=150)).isoformat(),
        },
    }
    credit = {
        "accountPlanRemainingCredits": {"unit": "USD", "amount": "120"},
        "accountPlanExpirationDate": (now + timedelta(days=150)).isoformat(),
    }
    cost = {"ResultsByTime": [{"Total": {"UnblendedCost": {"Unit": "USD", "Amount": "20"}}}]}
    plan = {
        "schema_version": 1,
        "operator_verified_official_prices": True,
        "window_hours": 3,
        "pricing_checked_at": now.isoformat(),
        "custody_until": (now + timedelta(days=100)).isoformat(),
        "new_resources_and_custody_reserve_usd": 40,
        "existing_retained_reserve_usd": 27,
        "contingency_reserve_usd": 30,
    }
    return budget, credit, cost, plan, now


def test_billing_reserves_include_gross_spend_and_entire_custody() -> None:
    budget, credit, cost, plan, now = billing_data()
    assert all(billing.evaluate(budget, credit, cost, plan, now).values())
    for amount, expected in [("53", True), ("53.01", False)]:
        cost["ResultsByTime"][0]["Total"]["UnblendedCost"]["Amount"] = amount
        assert (
            billing.evaluate(budget, credit, cost, plan, now)["usage_and_reserves_within_ceiling"]
            is expected
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("operator_verified_official_prices", False),
        ("window_hours", 4),
        ("custody_until", "2020-01-01T00:00:00+00:00"),
        ("pricing_checked_at", "2020-01-01T00:00:00+00:00"),
        ("new_resources_and_custody_reserve_usd", 41),
        ("existing_retained_reserve_usd", 0),
        ("contingency_reserve_usd", 0),
        ("new_resources_and_custody_reserve_usd", "NaN"),
    ],
)
def test_missing_stale_or_unfinanced_cost_plan_blocks(field: str, value: Any) -> None:
    budget, credit, cost, plan, now = billing_data()
    plan[field] = value
    assert not all(billing.evaluate(budget, credit, cost, plan, now).values())


def test_billing_missing_usage_pagination_credit_expiry_and_net_budget_block() -> None:
    budget, credit, cost, plan, now = billing_data()
    for modified in [{}, {**cost, "NextPageToken": "more"}]:
        assert not all(billing.evaluate(budget, credit, modified, plan, now).values())
    for modified in [
        {**credit, "accountPlanRemainingCredits": {"unit": "USD", "amount": "96.99"}},
        {**credit, "accountPlanExpirationDate": (now + timedelta(days=96)).isoformat()},
    ]:
        assert not all(billing.evaluate(budget, modified, cost, plan, now).values())
    budget["CostTypes"]["IncludeCredit"] = True
    assert not all(billing.evaluate(budget, credit, cost, plan, now).values())


def test_failed_billing_cannot_provision_or_store_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def blocked(*a: Any) -> Any:
        raise RuntimeError("preflight blocked")

    monkeypatch.setattr(commission, "preflight", blocked)
    monkeypatch.setattr(commission, "aws", lambda *a: pytest.fail("must not mutate AWS"))
    monkeypatch.setattr(
        commission, "read", lambda *a, **k: pytest.fail("must stop before provisioning")
    )
    with pytest.raises(RuntimeError, match="preflight blocked"):
        commission.foundation({})


def test_cloud_definitions_keep_credentials_and_business_roles_separate() -> None:
    b = base()
    for mode in ["api", "migrate", "bootstrap"]:
        task = production.definition(b, production.IMAGE_REPOSITORY + "@" + DIGEST, SHA, mode)
        container = task["containerDefinitions"][0]
        env = {item["name"]: item["value"] for item in container["environment"]}
        secrets = {item["name"]: item["valueFrom"] for item in container["secrets"]}
        assert env["APP_ENV"] == "production" and env["PGSSLMODE"] == "verify-full"
        assert all(
            env[key] == "false"
            for key in [
                "E1_IDENTITY_ENABLED",
                "E2_FAMILY_ENABLED",
                "E3_PICKUP_ENABLED",
                "E4_OPERATIONS_ENABLED",
            ]
        )
        assert container["image"] == production.IMAGE_REPOSITORY + "@" + DIGEST
        assert container["readonlyRootFilesystem"] and container["user"] == "10001:10001"
        assert ("portMappings" in container) is (mode == "api")
        if mode == "api":
            assert env["PGUSER"] == "retiro_runtime"
            assert set(secrets.values()) == {b["RuntimePassword"], b["DjangoSecret"]}
        elif mode == "migrate":
            assert env["PGUSER"] == "retiro_migrator"
            assert set(secrets.values()) == {b["MigrationPassword"], b["DjangoSecret"]}
            assert task["executionRoleArn"] == b["MigrationExecution"]
        else:
            assert env["PGUSER"] == "retiro_bootstrap"
            assert secrets["PGPASSWORD"] == b["MasterSecret"] + ":password::"
            assert "NOLOGIN" in container["command"][2]


def test_production_infrastructure_is_separate_and_has_no_secret_read_in_deploy() -> None:
    template = json.loads(Path("infra/aws/production-base.json").read_text())
    r = template["Resources"]
    db = r["Database"]["Properties"]
    assert db["PubliclyAccessible"] is False and db["DeletionProtection"] is True
    assert db["StorageEncrypted"] is True and db["BackupRetentionPeriod"] == 7
    assert db["KmsKeyId"] == {"Fn::GetAtt": ["DatabaseKey", "Arn"]}
    assert r["DatabaseParameters"]["Properties"]["Parameters"]["rds.force_ssl"] == "1"
    assert r["Vpc"]["Properties"]["CidrBlock"] == "10.62.0.0/16"
    assert r["Database"]["DeletionPolicy"] == r["DatabaseKey"]["DeletionPolicy"] == "Retain"
    assert "Repository" not in r  # same source digest, not a new production build
    for role in ["Deploy", "Migrate"]:
        text = json.dumps(r[role])
        assert "GetSecretValue" not in text and "kms:Decrypt" not in text
        assert "ecr:PutImage" not in text
        trust = r[role]["Properties"]["AssumeRolePolicyDocument"]["Statement"][0]
        assert trust["Condition"]["StringEquals"][
            "token.actions.githubusercontent.com:sub"
        ].endswith(":ref:refs/heads/main")
    assert "SecurityGroupIngress" not in r["AppSecurityGroup"]["Properties"]


def test_unconfigured_or_enabled_business_is_never_accepted_as_production() -> None:
    config = json.loads(production.CONFIG.read_text())
    assert validate(config)  # real observed endpoints are still required
    production.technical_only(config)
    for field in production.FLAGS:
        with pytest.raises(RuntimeError, match="cannot enable business"):
            production.technical_only({**config, field: True})


def test_obsolete_candidate_cannot_touch_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(production.subprocess, "check_output", lambda *a, **k: "c" * 40 + "\tref")
    monkeypatch.setattr(
        production, "aws", lambda *a: pytest.fail("obsolete candidate cannot proceed")
    )
    with pytest.raises(RuntimeError, match="OBSOLETE"):
        production.candidate(SHA, DIGEST)


def test_wrong_digest_and_wrong_identity_block(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(production.subprocess, "check_output", lambda *a, **k: SHA + "\tref")
    monkeypatch.setattr(production, "aws", lambda *a: {"imageDetails": [{"imageDigest": "wrong"}]})
    with pytest.raises(RuntimeError, match="tag/digest"):
        production.candidate(SHA, DIGEST)
    monkeypatch.setattr(
        production,
        "aws",
        lambda *a: {
            "Account": production.ACCOUNT,
            "Arn": f"arn:aws:sts::{production.ACCOUNT}:assumed-role/retiro-staging-Deploy/test",
        },
    )
    with pytest.raises(RuntimeError, match="isolated production"):
        production.identity("Deploy")


def test_database_key_privacy_and_backup_drift_blocks_before_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    b = base()
    db = {
        "PubliclyAccessible": False,
        "StorageEncrypted": True,
        "KmsKeyId": b["DatabaseKeyArn"],
        "BackupRetentionPeriod": 7,
        "DeletionProtection": True,
        "Endpoint": {"Address": b["DbHost"]},
        "DBInstanceStatus": "available",
    }
    for field, value in [
        ("PubliclyAccessible", True),
        ("KmsKeyId", "other"),
        ("BackupRetentionPeriod", 1),
    ]:
        calls = []

        def call(*args: str, calls: list = calls, field: str = field, value: Any = value) -> dict:
            calls.append(args[1])
            return {"DBInstances": [{**db, field: value}]}

        monkeypatch.setattr(deploy, "aws", call)
        with pytest.raises(RuntimeError, match="drift"):
            deploy.wait_database(b)
        assert calls == ["describe-db-instances"]


def test_failed_migration_never_reports_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deploy, "register", lambda *a: "migration-task")
    monkeypatch.setattr(deploy, "run_isolated_task", lambda *a: {"containers": [{"exitCode": 2}]})
    monkeypatch.setattr(deploy, "report", lambda *a: pytest.fail("no migration success"))
    with pytest.raises(RuntimeError, match="migration failed"):
        deploy.migrate(base(), SHA, DIGEST)


def test_failed_candidate_rolls_back_code_and_checks_restored_health(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    checks = []
    reports = []
    monkeypatch.setattr(deploy, "gateway", lambda: {})
    monkeypatch.setattr(deploy, "rollback_definition", lambda *a: "old-task")
    monkeypatch.setattr(deploy, "runtime_digests", lambda d: {d})
    monkeypatch.setattr(deploy, "register", lambda *a: "new-task")
    monkeypatch.setattr(deploy, "candidate", lambda *a: None)

    def aws(*args: str) -> dict:
        calls.append(args)
        return {
            "taskDefinition": {
                "containerDefinitions": [{"image": production.IMAGE_REPOSITORY + "@" + DIGEST}]
            }
        }

    def verify(*args: Any) -> Any:
        checks.append(args[1])
        if args[1] == "new-task":
            raise RuntimeError("failed readiness")
        return "https://verified.ecs.us-east-1.on.aws", {"probes": {"passed": True}}

    monkeypatch.setattr(deploy, "aws", aws)
    monkeypatch.setattr(deploy, "verify_running", verify)
    monkeypatch.setattr(deploy, "report", lambda *a: reports.append(a))
    with pytest.raises(RuntimeError, match="rollback verified"):
        deploy.deploy(base(), SHA, DIGEST, "expiry")
    assert checks == ["new-task", "old-task"]
    assert [c[-1] for c in calls if c[1] == "update-express-gateway-service"] == [
        "new-task",
        "old-task",
    ]
    assert all(c[0] == "ecs" for c in calls)
    assert reports[0][1]["passed"] is False and reports[0][1]["rollback_verified"] is True


def test_failed_stack_is_not_deleted_or_recreated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        commission,
        "read",
        lambda *a, **k: {
            "Stacks": [
                {
                    "StackStatus": "ROLLBACK_COMPLETE",
                    "Tags": [
                        {"Key": "Project", "Value": "retiro-seguro"},
                        {"Key": "Environment", "Value": "production"},
                    ],
                }
            ]
        },
    )
    monkeypatch.setattr(
        commission.subprocess, "run", lambda *a, **k: pytest.fail("must not mutate stack")
    )
    with pytest.raises(RuntimeError, match="nothing deleted"):
        commission.deploy_stack("retiro-production-base", Path("template"), [])


def test_production_pipeline_requires_full_staging_then_isolated_migration() -> None:
    template, errors = decode("infra/aws/production-lifecycle.yaml")
    assert template and not errors
    schedules = [
        v for v in template["Resources"].values() if v["Type"] == "AWS::Scheduler::Schedule"
    ]
    assert len(schedules) == 2
    assert all("retiro-production" in json.dumps(s) for s in schedules)
    import yaml

    workflow = yaml.safe_load(Path(".github/workflows/cd.yml").read_text())
    jobs = workflow["jobs"]
    assert "e1-acceptance" in jobs["production-prepare"]["needs"]
    assert "e2-acceptance" in jobs["production-prepare"]["needs"]
    assert jobs["production-migrate"]["needs"] == ["publish", "production-prepare"]
    assert set(jobs["production"]["needs"]) == {
        "publish",
        "staging",
        "e1-acceptance",
        "e2-acceptance",
        "production-migrate",
    }
    assert workflow["concurrency"]["cancel-in-progress"] is False
    for key in ["production-prepare", "production-migrate", "production"]:
        assert jobs[key]["permissions"] == {"contents": "read", "id-token": "write"}
        assert "environment" not in jobs[key]  # no new manual promotion approval
