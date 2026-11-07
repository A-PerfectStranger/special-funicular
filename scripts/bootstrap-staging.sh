#!/usr/bin/env bash
# Run in CloudShell; reviewed immutable source, synthetic staging only.
set -euo pipefail
if [[ $# -ne 2 || ! "$1" =~ ^[0-9a-f]{40}$ ]]; then
  echo 'Usage: bash bootstrap-staging.sh <reviewed full SHA> <budget alert email>' >&2
  exit 2
fi
retiro_stage_dir="$(mktemp -d)"
trap 'rm -rf -- "$retiro_stage_dir"' EXIT
[[ "$(aws sts get-caller-identity --query Account --output text)" == '028364485203' ]] || { echo 'BLOCKED: wrong account'; exit 2; }
for retiro_file in budget.yaml staging-base.json; do
 curl --proto '=https' --tlsv1.3 -fsSL "https://raw.githubusercontent.com/A-PerfectStranger/special-funicular/$1/infra/aws/$retiro_file" -o "$retiro_stage_dir/$retiro_file"
done
aws freetier get-account-plan-state --region us-east-1 --output json > "$retiro_stage_dir/plan.json"
retiro_period="$(python3 -c 'from datetime import datetime,UTC,timedelta; d=datetime.now(UTC).date(); print(f"Start={d.replace(day=1)},End={d+timedelta(days=1)}")')"
aws ce get-cost-and-usage --region us-east-1 --time-period "$retiro_period" --granularity MONTHLY --metrics UnblendedCost --filter '{"Not":{"Dimensions":{"Key":"RECORD_TYPE","Values":["Credit","Refund"]}}}' --output json > "$retiro_stage_dir/cost.json"
retiro_expiry="$(python3 - "$retiro_stage_dir" <<'PY'
import json,sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime,UTC
p=Path(sys.argv[1]); plan=json.loads((p/'plan.json').read_text()); cost=json.loads((p/'cost.json').read_text())
c=plan['accountPlanRemainingCredits']; expiry=datetime.fromisoformat(plan['accountPlanExpirationDate'].replace('Z','+00:00'))
assert c['unit']=='USD' and Decimal(str(c['amount']))>=150 and expiry>datetime.now(UTC), 'BLOCKED: credits'
assert cost['ResultsByTime'] and not cost.get('NextPageToken'), 'BLOCKED: missing gross usage'
assert all(r['Total']['UnblendedCost']['Unit']=='USD' for r in cost['ResultsByTime']), 'BLOCKED: currency'
assert sum(Decimal(r['Total']['UnblendedCost']['Amount']) for r in cost['ResultsByTime'])<150, 'BLOCKED: ceiling'
print(int(expiry.timestamp()))
PY
)"
# Two budgets are not created: reuse this single total 150 USD project budget.
aws cloudformation deploy --region us-east-1 --stack-name retiro-seguro-budget --template-file "$retiro_stage_dir/budget.yaml" --parameter-overrides "AlertEmail=$2" BudgetStartEpoch=1793923200 "BudgetEndEpoch=$retiro_expiry" --no-fail-on-empty-changeset
retiro_engine="$(aws rds describe-db-engine-versions --region us-east-1 --engine aurora-postgresql --default-only --query 'DBEngineVersions[0].EngineVersion' --output text)"
python3 - "$retiro_engine" <<'PY'
import sys
v=tuple(map(int,sys.argv[1].split('.')[:2])); assert v>=(16,3), 'BLOCKED: auto-pause needs a supported engine'
PY
[[ "$(aws rds describe-orderable-db-instance-options --region us-east-1 --engine aurora-postgresql --engine-version "$retiro_engine" --db-instance-class db.serverless --query 'length(OrderableDBInstanceOptions)' --output text)" -gt 0 ]] || { echo 'BLOCKED: serverless not orderable'; exit 2; }
aws cloudformation validate-template --region us-east-1 --template-body "file://$retiro_stage_dir/staging-base.json" >/dev/null
aws cloudformation deploy --region us-east-1 --stack-name retiro-staging-base --template-file "$retiro_stage_dir/staging-base.json" --capabilities CAPABILITY_NAMED_IAM --parameter-overrides "EngineVersion=$retiro_engine" --tags Project=retiro-seguro Environment=staging --no-fail-on-empty-changeset
aws cloudformation describe-stacks --region us-east-1 --stack-name retiro-staging-base --query 'Stacks[0].Outputs[?OutputKey==`Deploy` || OutputKey==`Migrate`]' --output table
