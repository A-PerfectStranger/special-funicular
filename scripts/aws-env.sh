#!/usr/bin/env bash
# Source from Bash to keep login and subsequent CLI commands on the same private cache.
# No secrets are printed or loaded from AWS_VERIFICATION_CODE: OAuth codes are per attempt.
retiro_repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$retiro_repo_root/work/aws"
chmod 700 "$retiro_repo_root/work/aws"
export PATH="$retiro_repo_root/work/bin:$PATH"
export AWS_CONFIG_FILE="$retiro_repo_root/work/aws/config"
export AWS_SHARED_CREDENTIALS_FILE="$retiro_repo_root/work/aws/credentials"
export AWS_LOGIN_CACHE_DIRECTORY="$retiro_repo_root/work/aws/login-cache"
export AWS_PROFILE=aesir
export AWS_REGION=us-east-1
export AWS_DEFAULT_REGION=us-east-1
export AWS_PAGER=""
unset retiro_repo_root
