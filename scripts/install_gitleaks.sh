#!/usr/bin/env bash
# Official pinned release only. A download retry/fallback never skips checksum verification.
set -euo pipefail
mkdir -p work
for gitleaks_asset in gitleaks_8.30.1_linux_x64.tar.gz gitleaks_8.30.1_checksums.txt; do
  if ! curl --retry 3 --retry-delay 2 --retry-max-time 90 --connect-timeout 10 --max-time 30 -fsSL \
    "https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/$gitleaks_asset" -o "work/$gitleaks_asset"; then
    gh release download v8.30.1 --repo gitleaks/gitleaks --pattern "$gitleaks_asset" --dir work --clobber
  fi
done
awk '$2 == "gitleaks_8.30.1_linux_x64.tar.gz" {print $1 "  work/" $2}' work/gitleaks_8.30.1_checksums.txt | sha256sum -c -
tar -xzf work/gitleaks_8.30.1_linux_x64.tar.gz -C work gitleaks
