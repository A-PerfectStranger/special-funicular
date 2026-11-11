#!/usr/bin/env bash
# Ubuntu 24.04 hosted runners already provide Chromium's native runtime libraries.
set -euo pipefail
cd "$(dirname "$0")/.."

# The lockfile pins Playwright and its browser revision. Do not invoke APT for
# additional font packs: runner DNS can make that unrelated setup fail.
npx playwright install chromium

# Prove that the installed browser and native libraries work. Missing libraries,
# download failures or unusable Chromium still fail the job before acceptance.
node --input-type=module <<'JS'
import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  await page.setContent('<button>Verificar conexión</button>');
  await page.getByRole('button', { name: 'Verificar conexión', exact: true }).click();
  console.log(`Chromium ${browser.version()}: launch and page interaction passed`);
} finally {
  await browser.close();
}
JS
