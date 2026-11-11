#!/usr/bin/env bash
# Ubuntu 24.04 hosted runners; keep full Playwright dependencies and signed APT indexes.
set -euo pipefail
cd "$(dirname "$0")/.."

ubuntu_sources=/etc/apt/sources.list.d/ubuntu.sources
if [ ! -f "$ubuntu_sources" ]; then
  echo 'BLOCKED: Ubuntu deb822 sources required for the CI browser setup' >&2
  exit 2
fi
retiro_sudo=()
if [ "$(id -u)" -ne 0 ]; then
  retiro_sudo=(sudo -n)
fi

# Avoid the hosted runner's Azure mirror selector. Keep suites, components,
# Signed-By and all unrelated repositories unchanged; use official HTTPS origins.
"${retiro_sudo[@]}" sed -i \
  -e 's|mirror+file:/etc/apt/apt-mirrors.txt|https://archive.ubuntu.com/ubuntu|g' \
  -e 's|mirror+file:/etc/apt/apt-security-mirrors.txt|https://security.ubuntu.com/ubuntu|g' \
  -e 's|http://azure.archive.ubuntu.com/ubuntu|https://archive.ubuntu.com/ubuntu|g' \
  -e 's|https://azure.archive.ubuntu.com/ubuntu|https://archive.ubuntu.com/ubuntu|g' \
  -e 's|http://archive.ubuntu.com/ubuntu|https://archive.ubuntu.com/ubuntu|g' \
  -e 's|http://security.ubuntu.com/ubuntu|https://security.ubuntu.com/ubuntu|g' \
  "$ubuntu_sources"

# Fail on an incomplete index refresh instead of accepting stale indexes, and
# bound each network attempt. Playwright invokes APT itself with this policy.
"${retiro_sudo[@]}" tee /etc/apt/apt.conf.d/99retiro-browser-network >/dev/null <<'APT'
Acquire::Retries "2";
Acquire::http::Timeout "20";
Acquire::https::Timeout "20";
APT::Update::Error-Mode "any";
APT

npx playwright install --with-deps chromium
