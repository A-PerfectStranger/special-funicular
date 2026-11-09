// Bounded anonymous navigation diagnostic, never functional acceptance.
import { chromium } from 'playwright';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { safeFailure, documentScope } from './diagnostics.mjs';

const origin = JSON.parse(readFileSync('infra/environments/staging.json', 'utf8')).base_url;
const provider = 'https://retiro-e1-028364485203.auth.us-east-1.amazoncognito.com';
let browser, phase = 'launch', status = null, scope = null, passed = false, failure = {};
try {
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  page.on('response', response => {
    if (response.request().isNavigationRequest() && response.request().frame() === page.mainFrame()) {
      status = response.status(); scope = documentScope(response.url(), origin, provider);
    }
  });
  phase = 'web_login_get';
  const response = await page.goto(origin + '/auth/login');
  phase = 'web_login_response';
  if (response?.status() !== 200) throw new Error('Acceptance assertion failed');
  phase = 'web_login_submit';
  await page.getByRole('button', { name: 'Ingresar con MFA' }).click();
  phase = 'provider_origin';
  await page.waitForURL(url => url.origin === provider);
  phase = 'provider_form';
  await page.locator('input[name="username"]:visible,input[autocomplete="username"]:visible').first().waitFor();
  passed = true;
} catch (error) { failure = safeFailure(error); }
finally { if (browser) await browser.close(); }
const report = { passed, phase, status, scope, ...failure, acceptance: false };
mkdirSync('work', { recursive: true });
writeFileSync('work/public-navigation.json', JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report));
if (!passed) process.exitCode = 2;
