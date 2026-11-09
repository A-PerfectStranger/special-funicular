// Real synthetic IdP/BFF smoke. No credentials, URLs with codes, traces or screenshots are logged.
import { chromium } from 'playwright';
import { TOTP, Secret } from 'otpauth';
import { randomBytes, createHash, randomUUID } from 'node:crypto';
import { promisify } from 'node:util';
import { execFile } from 'node:child_process';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { nativeCallback } from './native-callback.mjs';
import { withRecovery } from './recovery.mjs';
import { safeFailure, documentScope } from './diagnostics.mjs';
import { IdentityClient } from '../../apps/mobile/src/identity.ts';

const fixture = JSON.parse(readFileSync(0, 'utf8'));
const origin = fixture.origin;
const providerOrigin = 'https://retiro-e1-028364485203.auth.us-east-1.amazoncognito.com';
const checks = [];
let deniedEventSequence = null;
let browser;
let step = 'browser_start';
let phase = 'launch';
let lastHttpStatus = null;
let providerReturn = null;
let firstFailure = null;
let recoveryFailed = false;
let accessAgeMs = null;
let lastDocumentScope = null;
let lastNetworkError = null;
function captureFailure(stage, error) {
  if (stage === 'recovery') recoveryFailed = true;
  firstFailure ??= { failure_phase: phase, last_http_status: lastHttpStatus,
    provider_return: providerReturn, access_age_ms: accessAgeMs,
    ...safeFailure(error), last_network_error: lastNetworkError,
    document_scope: lastDocumentScope };
}
function observePage(page) {
  page.on('response', response => {
    if (response.request().isNavigationRequest() && response.request().frame() === page.mainFrame()) {
      lastDocumentScope = documentScope(response.url(), origin, providerOrigin);
      lastHttpStatus = response.status();
      lastNetworkError = null;
    }
  });
  page.on('requestfailed', request => {
    if (request.isNavigationRequest() && request.frame() === page.mainFrame()) {
      lastDocumentScope = documentScope(request.url(), origin, providerOrigin);
      lastNetworkError = safeFailure(new Error(request.failure()?.errorText ?? '')).network_error;
    }
  });
}
const assert = (condition) => { if (!condition) throw new Error('Acceptance assertion failed'); };
const secret = () => randomBytes(32).toString('base64url');
const lastOtp = new Map();
const run = promisify(execFile);
async function fixtureStatus(action, username) {
  phase = 'fixture_status_' + action;
  writeFileSync('work/e1-fixture-control-used', 'synthetic status command started\n');
  await run('python3', ['-m', 'scripts.e1_fixture_control', action, username]);
}

async function submit(page) {
  await page.locator('button[type="submit"]:visible,input[type="submit"]:visible').first().click({ noWaitAfter: true });
}
async function providerLogin(page, username) {
  phase = 'idp_origin';
  await page.waitForURL(url => url.origin === providerOrigin);
  phase = 'idp_username';
  const user = fixture.users[username];
  await page.locator('input[name="username"]:visible,input[autocomplete="username"]:visible').first().fill(username);
  const password = page.locator('input[type="password"]:visible').first();
  if (!await password.isVisible()) await submit(page);
  assert(new URL(page.url()).origin === providerOrigin);
  phase = 'idp_password';
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
  phase = 'idp_totp';
  await otp.fill(value);
  await submit(page);
}
async function webLogin(username) {
  const context = await browser.newContext();
  const page = await context.newPage();
  observePage(page);
  phase = 'web_login_get';
  const response = await page.goto(origin + '/auth/login');
  phase = 'web_login_response';
  assert(response?.status() === 200);
  phase = 'web_login_submit';
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
  accessAgeMs = null;
  let stored = null;
  let accessIssuedAt = 0;
  let lastBearer = null;
  let lastMe = null;
  let lastExchangeStatus = null;
  const dependencies = {
    apiUrl: origin, redirectUri: fixture.mobile_redirect,
    request: async (input, options) => {
      const labels = { '/v1/auth/mobile/start': 'start', '/v1/auth/mobile/exchange': 'exchange',
        '/v1/auth/refresh': 'refresh', '/v1/auth/logout': 'logout', '/v1/me': 'me' };
      phase = 'mobile_api_' + (labels[new URL(String(input)).pathname] ?? 'unknown');
      const response = await fetch(input, options);
      if (new URL(String(input)).pathname === '/v1/auth/mobile/exchange') lastExchangeStatus = response.status;
      if (new URL(String(input)).pathname === '/v1/me') {
        if (options?.headers?.Authorization) lastBearer = options.headers.Authorization;
        if (response.status === 200) lastMe = await response.clone().json();
      }
      lastHttpStatus = response.status;
      return response;
    },
    readRefresh: async () => stored,
    writeRefresh: async (value) => { stored = value; accessIssuedAt = Date.now(); },
    clearRefresh: async () => { stored = null; },
    pkce: async () => { const verifier = secret(); return { verifier, challenge: createHash('sha256').update(verifier).digest('base64url') }; },
    browser: async (url, redirect) => {
      const context = await browser.newContext();
      try {
        const page = await context.newPage();
        observePage(page);
        const capture = await nativeCallback(page, redirect);
        try {
          await page.goto(url);
          await providerLogin(page, username);
          phase = 'mobile_native_return';
          try { return await capture.callback; }
          catch {
            // Controlled booleans only; never serialize page text, URL or provider errors.
            providerReturn = {
              expected_provider_origin: new URL(page.url()).origin === providerOrigin,
              visible_totp_form: await page.locator('input[autocomplete="one-time-code"]:visible,input[name="totpCode"]:visible,input[name="code"]:visible,input[name="softwareTokenMfaCode"]:visible,input[name="mfaCode"]:visible').count() > 0,
              visible_alert: await page.locator('[role="alert"]:visible').count() > 0,
            };
            throw new Error('Native callback unavailable');
          }
        } finally { await capture.dispose(); }
      } finally { await context.close(); }
    },
  };
  let client = new IdentityClient(dependencies);
  assert(await client.login() === role);
  assert(await client.check() === role);
  assert(await client.login(true) === role);
  const expected = fixture.expected_scopes[username];
  assert(lastMe.role === expected.role && lastMe.school_id === expected.school_id && lastMe.site_id === expected.site_id);
  // Refresh first so revocation is tested against a recently issued, unexpired access credential.
  client = new IdentityClient(dependencies);
  assert(await client.check() === role);
  const activeBearer = lastBearer;
  const activeRefresh = stored;
  await withRecovery(async () => {
    await fixtureStatus('revoke', username);
    phase = 'mobile_fresh_access_after_revoke';
    accessAgeMs = Date.now() - accessIssuedAt;
    assert(accessAgeMs < 240000);
    const revoked = await dependencies.request(origin + '/v1/me', {
      headers: { Authorization: activeBearer }, cache: 'no-store', redirect: 'error',
    });
    assert(revoked.status === 401);
    const refresh = await fetch(origin + '/v1/auth/refresh', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: activeRefresh }), signal: AbortSignal.timeout(10000),
    });
    phase = 'mobile_revoked_refresh';
    lastHttpStatus = refresh.status;
    assert(refresh.status === 401);
    let temporaryRefresh = null;
    const disabled = new IdentityClient({ ...dependencies,
      readRefresh: async () => temporaryRefresh,
      writeRefresh: async value => { temporaryRefresh = value; },
      clearRefresh: async () => { temporaryRefresh = null; },
    });
    lastExchangeStatus = null;
    let rejected = false;
    try { await disabled.login(); } catch { rejected = true; }
    finally { await disabled.logout().catch(() => {}); }
    phase = 'mobile_disabled_login_assertion';
    assert(rejected && lastExchangeStatus === 401);
  }, () => fixtureStatus('restore', username), captureFailure);
  phase = 'mobile_fresh_access_after_restore';
  accessAgeMs = Date.now() - accessIssuedAt;
  assert(accessAgeMs < 240000);
  assert((await dependencies.request(origin + '/v1/me', {
    headers: { Authorization: activeBearer }, cache: 'no-store', redirect: 'error',
  })).status === 401);
  assert(await client.login() === role);
  assert(lastMe.role === expected.role && lastMe.school_id === expected.school_id && lastMe.site_id === expected.site_id);
  // Restart requires online refresh; then logout with the token from before rotation.
  const beforeRotation = stored;
  const restarted = new IdentityClient(dependencies);
  assert(await restarted.check() === role);
  const response = await fetch(origin + '/v1/auth/logout', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: beforeRotation }), signal: AbortSignal.timeout(10000),
  });
  assert(response.status === 200);
  let denied = false;
  try { await restarted.check(); } catch { denied = true; }
  assert(denied);
  await restarted.logout().catch(() => {});
}

async function archiveDrill() {
  const system = await webLogin('e1-system');
  const original = await browser.newContext();
  try {
    const before = await jsonResponse(system.context, '/v1/system/school-access-records?limit=100');
    const previous = new Set(before.records.map(record => record.sequence));
    const page = await original.newPage();
    observePage(page);
    await page.goto(origin + '/auth/login');
    await page.getByRole('button', { name: 'Ingresar con MFA' }).click();
    const callback = page.waitForResponse(response => {
      const url = new URL(response.url());
      return url.origin === origin && url.pathname === '/auth/callback';
    });
    callback.catch(() => {});
    await providerLogin(page, 'e1-a-admin');
    assert((await callback).status() === 401);
    await jsonResponse(original, '/portal/', 401);
    const failed = (await jsonResponse(system.context, '/v1/system/school-access-records?limit=100'))
      .records.filter(record => !previous.has(record.sequence));
    assert(failed.length === 1 && failed[0].result === 'DENIED');
    deniedEventSequence = failed[0].sequence;
    writeFileSync('work/e1-archive-denial-observed.json', JSON.stringify({ sequence: deniedEventSequence }));
    const deadline = Date.now() + 360000;
    while (!existsSync('work/e1-archive-resumed')) {
      assert(Date.now() < deadline);
      await page.waitForTimeout(250);
    }
    // A fresh login proves archiving works again; it never repairs the original attempt.
    const fresh = await webLogin('e1-a-admin');
    await fresh.context.close();
    await jsonResponse(original, '/portal/', 401);
    const after = await jsonResponse(system.context, '/v1/system/school-access-records?limit=100');
    assert(after.records.find(record => record.sequence === deniedEventSequence)?.result === 'DENIED');
    const opened = after.records.filter(record => !previous.has(record.sequence) && record.result === 'OPENED');
    assert(opened.length === 1);
  } finally {
    await original.close();
    await system.context.close();
  }
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
  if (fixture.scenario === 'archive-drill') {
    step = 'archive_absent_then_late_receipt_remains_denied';
    await archiveDrill();
    checks.push({ id: step, passed: true });
  } else {
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
  }
} catch (error) {
  captureFailure('operation', error);
  checks.push({ id: step, passed: false });
} finally {
  if (browser) await browser.close();
}
const passed = checks.length === (fixture.scenario === 'archive-drill' ? 1 : 3) && checks.every(check => check.passed);
writeFileSync(fixture.scenario === 'archive-drill' ? 'work/e1-archive-drill.json' : 'work/e1-browser-acceptance.json', JSON.stringify({
  sha: process.env.GITHUB_SHA, scope: 'Real synthetic Cognito/BFF and mobile protocol; native Android return, SQL isolation and WORM recovery are separate',
  checked_at: new Date().toISOString(), checks, passed, e1_accepted: false,
  ...(!passed ? { ...firstFailure, recovery_failed: recoveryFailed } : {}),
  ...(deniedEventSequence ? { denied_event_sequence: deniedEventSequence } : {}),
}, null, 2) + '\n');
console.log('E1 browser/protocol checks: ' + (passed ? 'PASS' : 'FAIL (' + step + ')'));
process.exitCode = passed ? 0 : 2;
