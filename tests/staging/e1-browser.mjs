// Real synthetic IdP/BFF smoke. No credentials, URLs with codes, traces or screenshots are logged.
import { chromium } from 'playwright';
import { TOTP, Secret } from 'otpauth';
import { randomBytes, createHash, randomUUID } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { IdentityClient } from '../../apps/mobile/src/identity.ts';

const fixture = JSON.parse(readFileSync(0, 'utf8'));
const origin = fixture.origin;
const providerOrigin = 'https://retiro-e1-028364485203.auth.us-east-1.amazoncognito.com';
const checks = [];
let browser;
let step = 'browser_start';
const assert = (condition) => { if (!condition) throw new Error('Acceptance assertion failed'); };
const secret = () => randomBytes(32).toString('base64url');
const lastOtp = new Map();

async function submit(page) {
  await page.locator('button[type="submit"]:visible,input[type="submit"]:visible').first().click({ noWaitAfter: true });
}
async function providerLogin(page, username) {
  await page.waitForURL(url => url.origin === providerOrigin);
  const user = fixture.users[username];
  await page.locator('input[name="username"]:visible,input[autocomplete="username"]:visible').first().fill(username);
  const password = page.locator('input[type="password"]:visible').first();
  if (!await password.isVisible()) await submit(page);
  assert(new URL(page.url()).origin === providerOrigin);
  await password.fill(user.password);
  await submit(page);
  const otp = page.locator('input[autocomplete="one-time-code"]:visible,input[name="totpCode"]:visible,input[name="code"]:visible,input[name="softwareTokenMfaCode"]:visible,input[name="mfaCode"]:visible').first();
  await otp.waitFor({ state: 'visible' });
  const totp = new TOTP({ algorithm: 'SHA1', digits: 6, period: 30, secret: Secret.fromBase32(user.totp_seed) });
  let value = totp.generate();
  if (lastOtp.get(username) === value) {
    await page.waitForTimeout(31000 - Date.now() % 30000);
    value = totp.generate();
  }
  lastOtp.set(username, value);
  assert(new URL(page.url()).origin === providerOrigin);
  await otp.fill(value);
  await submit(page);
}
async function webLogin(username) {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(origin + '/auth/login');
  await page.getByRole('button', { name: 'Ingresar con MFA' }).click();
  await providerLogin(page, username);
  await page.waitForURL(origin + '/portal/');
  return { context, page };
}
async function jsonResponse(context, path, status = 200) {
  const response = await context.request.get(origin + path);
  assert(response.status() === status);
  assert(response.headers()['cache-control'] === 'no-store');
  return response.json();
}
async function mobile(username, role) {
  let stored = null;
  let firstRefresh = null;
  const dependencies = {
    apiUrl: origin, redirectUri: fixture.mobile_redirect, request: fetch,
    readRefresh: async () => stored,
    writeRefresh: async (value) => { stored = value; if (!firstRefresh) firstRefresh = value; },
    clearRefresh: async () => { stored = null; },
    pkce: async () => { const verifier = secret(); return { verifier, challenge: createHash('sha256').update(verifier).digest('base64url') }; },
    browser: async (url, redirect) => {
      const context = await browser.newContext();
      try {
        const page = await context.newPage();
        const callback = page.waitForResponse(response => (response.headers()['location'] ?? '').startsWith(redirect + '?'));
        callback.catch(() => {}); // Context closure must not create an unhandled rejection.
        await page.goto(url);
        await providerLogin(page, username);
        return (await callback).headers()['location'];
      } finally { await context.close(); }
    },
  };
  const client = new IdentityClient(dependencies);
  assert(await client.login() === role);
  assert(await client.check() === role);
  assert(await client.login(true) === role);
  // Restart requires online refresh; then logout with the token from before rotation.
  const restarted = new IdentityClient(dependencies);
  assert(await restarted.check() === role);
  const response = await fetch(origin + '/v1/auth/logout', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: firstRefresh }), signal: AbortSignal.timeout(10000),
  });
  assert(response.status === 200);
  let denied = false;
  try { await restarted.check(); } catch { denied = true; }
  assert(denied);
  await restarted.logout().catch(() => {});
}

try {
  assert(new URL(origin).protocol === 'https:');
  const proxyUrl = process.env.HTTPS_PROXY ? new URL(process.env.HTTPS_PROXY) : null;
  const proxy = proxyUrl ? {
    server: `${proxyUrl.protocol}//${proxyUrl.hostname}:${proxyUrl.port}`,
    ...(proxyUrl.username ? { username: decodeURIComponent(proxyUrl.username), password: decodeURIComponent(proxyUrl.password) } : {}),
  } : undefined;
  browser = await chromium.launch({
    ...(process.env.E1_CHROMIUM_PATH ? { executablePath: process.env.E1_CHROMIUM_PATH } : {}),
    headless: true, proxy,
  });
  step = 'school_three_protected_logins';
  const system = await webLogin('e1-system');
  const before = await jsonResponse(system.context, '/v1/system/school-access-records?limit=100');
  const initial = new Set(before.records.map(record => record.sequence));
  for (let index = 0; index < 3; index++) {
    const school = await webLogin('e1-a-admin');
    try {
      await school.page.getByRole('heading', { name: 'Portal escolar' }).waitFor();
      assert((await jsonResponse(school.context, '/v1/me')).role === 'ADMIN_ESCUELA');
      await jsonResponse(school.context, '/v1/system/school-access-records', 403);
      // A forged/unbound callback cannot replace the protected session or add a login.
      assert((await school.context.request.get(origin + '/auth/callback?state=invalid&code=invalid')).status() === 401);
      if (index === 0) {
        await school.page.getByRole('button', { name: 'Reautenticar con MFA' }).click();
        await providerLogin(school.page, 'e1-a-admin');
        await school.page.waitForURL(origin + '/portal/');
      }
      await school.page.getByRole('button', { name: 'Cerrar sesión' }).click();
      await jsonResponse(school.context, '/v1/me', 401);
    } finally { await school.context.close(); }
  }
  const after = await jsonResponse(system.context, '/v1/system/school-access-records?limit=100');
  const added = after.records.filter(record => !initial.has(record.sequence));
  assert(added.length === 3 && added.every(record => record.result === 'OPENED'));
  const fields = ['actor_id', 'event_id', 'occurred_at', 'result', 'school_id', 'sequence'];
  assert(after.records.every(record => JSON.stringify(Object.keys(record).sort()) === JSON.stringify(fields)));
  const unrelated = await jsonResponse(system.context, '/v1/system/school-access-records?school=' + randomUUID());
  assert(unrelated.records.length === 0);
  const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  assert((await jsonResponse(system.context, '/v1/system/school-access-records?from=' + tomorrow)).records.length === 0);
  const paged = await jsonResponse(system.context, '/v1/system/school-access-records?limit=1');
  assert(paged.records.length === 1 && paged.next_cursor);
  const next = await jsonResponse(system.context, '/v1/system/school-access-records?limit=1&before=' + paged.next_cursor);
  assert(next.records.length === 1 && next.records[0].sequence < paged.records[0].sequence);
  await system.context.close();
  checks.push({ id: step, passed: true });
  step = 'mobile_parent_mfa_pkce_reauth_refresh_logout';
  await mobile('e1-a-p1', 'PADRE');
  checks.push({ id: step, passed: true });
  step = 'mobile_guard_mfa_pkce_reauth_refresh_logout';
  await mobile('e1-b-guard', 'GUARDIA');
  checks.push({ id: step, passed: true });
} catch {
  checks.push({ id: step, passed: false });
} finally {
  if (browser) await browser.close();
}
const passed = checks.length === 3 && checks.every(check => check.passed);
writeFileSync('work/e1-browser-acceptance.json', JSON.stringify({
  sha: process.env.GITHUB_SHA, scope: 'Real synthetic Cognito/BFF and mobile protocol; native Android return, SQL isolation and WORM recovery are separate',
  checked_at: new Date().toISOString(), checks, passed, e1_accepted: false,
}, null, 2) + '\n');
console.log('E1 browser/protocol checks: ' + (passed ? 'PASS' : 'FAIL (' + step + ')'));
process.exitCode = passed ? 0 : 2;
