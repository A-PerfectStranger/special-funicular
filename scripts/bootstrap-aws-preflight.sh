#!/usr/bin/env bash
# Run in AWS CloudShell. Creates only a GitHub federation provider/read-only role.
set -euo pipefail
if [[ $# -ne 1 || ! "$1" =~ ^[0-9a-f]{40}$ ]]; then
  echo 'Usage: bash bootstrap-aws-preflight.sh <reviewed full commit SHA>' >&2
  exit 2
fi
retiro_bootstrap_dir="$(mktemp -d)"
trap 'rm -rf -- "$retiro_bootstrap_dir"' EXIT
retiro_account_id="$(aws sts get-caller-identity --query Account --output text)"
retiro_provider_arn="arn:aws:iam::$retiro_account_id:oidc-provider/token.actions.githubusercontent.com"
# List explicitly so an AccessDenied/network failure cannot be mistaken for absence.
retiro_providers="$(aws iam list-open-id-connect-providers --output json)"
retiro_existing_provider="$(python3 -c 'import json,sys; expected=sys.argv[1]; print(next((p["Arn"] for p in json.load(sys.stdin)["OpenIDConnectProviderList"] if p["Arn"] == expected), ""))' "$retiro_provider_arn" <<< "$retiro_providers")"
if [[ -n "$retiro_existing_provider" ]]; then
  retiro_audiences="$(aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$retiro_existing_provider" --query ClientIDList --output json)"
  if ! python3 -c 'import json,sys; sys.exit(0 if "sts.amazonaws.com" in json.load(sys.stdin) else 1)' <<< "$retiro_audiences"; then
    echo 'BLOCKED: existing GitHub provider does not include sts.amazonaws.com; no shared configuration changed.' >&2
    exit 2
  fi
fi
curl --proto '=https' --tlsv1.3 -fsSL \
  "https://raw.githubusercontent.com/A-PerfectStranger/special-funicular/$1/infra/aws/github-preflight.yaml" \
  -o "$retiro_bootstrap_dir/github-preflight.yaml"
aws cloudformation validate-template \
  --template-body "file://$retiro_bootstrap_dir/github-preflight.yaml" --region us-east-1 >/dev/null
aws cloudformation deploy --region us-east-1 \
  --stack-name retiro-seguro-github-preflight \
  --template-file "$retiro_bootstrap_dir/github-preflight.yaml" \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides "ExistingOidcProviderArn=$retiro_existing_provider" \
  --tags Project=retiro-seguro --no-fail-on-empty-changeset
aws cloudformation describe-stacks --region us-east-1 \
  --stack-name retiro-seguro-github-preflight \
  --query 'Stacks[0].Outputs[?OutputKey==`PreflightRoleArn`].OutputValue | [0]' --output text
