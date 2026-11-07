#!/usr/bin/env bash
# CloudShell operator: SOURCE_SHA APPROVED_IMAGE_SHA OCI_DIGEST
set -euo pipefail
if [[ $# -ne 3 || ! "$1" =~ ^[0-9a-f]{40}$ || ! "$2" =~ ^[0-9a-f]{40}$ || ! "$3" =~ ^sha256:[0-9a-f]{64}$ ]]; then
  echo 'Usage: commission-staging.sh <reviewed source SHA> <approved image SHA> <OCI digest>' >&2
  exit 2
fi
[[ "$(aws sts get-caller-identity --query Account --output text)" == '028364485203' ]] || { echo 'BLOCKED: wrong account'; exit 2; }
retiro_commission_dir="$(mktemp -d)"
retiro_evidence_dir="$PWD/work"
mkdir -p "$retiro_evidence_dir"
trap 'rm -rf -- "$retiro_commission_dir"' EXIT
curl --proto '=https' --tlsv1.3 -fsSL "https://github.com/A-PerfectStranger/special-funicular/archive/$1.tar.gz" -o "$retiro_commission_dir/source.tar.gz"
tar -xzf "$retiro_commission_dir/source.tar.gz" -C "$retiro_commission_dir"
cd "$retiro_commission_dir/special-funicular-$1"
aws cloudformation deploy --region us-east-1 --stack-name retiro-staging-lifecycle --template-file infra/aws/staging-lifecycle.yaml --capabilities CAPABILITY_NAMED_IAM --parameter-overrides "StopNotBefore=$(python3 -c 'from datetime import datetime,UTC,timedelta; print((datetime.now(UTC)+timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ"))')" --tags Project=retiro-seguro Environment=staging --no-fail-on-empty-changeset
python3 -m scripts.commission_staging --sha "$2" --digest "$3"
cp staging-evidence.json "$retiro_evidence_dir/staging-evidence.json"
echo 'Saved public synthetic evidence to work/staging-evidence.json'
