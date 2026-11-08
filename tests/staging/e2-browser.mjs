// No provider errors, screenshots, traces, credentials or token URLs are serialized.
import { chromium } from 'playwright';
import { TOTP, Secret } from 'otpauth';
import { randomBytes, createHash, randomUUID } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { nativeCallback } from './native-callback.mjs';
import { IdentityClient } from '../../apps/mobile/src/identity.ts';
const fixture = JSON.parse(readFileSync(0, 'utf8'));
const providerOrigin = 'https://retiro-e1-028364485203.auth.us-east-1.amazoncognito.com';
const run = promisify(execFile), clients = [], checks = [];
let browser, step = 'launch', minimumSequence = 0, passed = false;
const assert = value => { if (!value) throw new Error('Trial assertion failed'); };
const otpUsed = new Map();
async function control(action) { await run('python3', ['-m', 'scripts.e2_fixture_control', action]); }
async function submit(page) { await page.locator('button[type="submit"]:visible,input[type="submit"]:visible').first().click({ noWaitAfter: true }); }
function clientFor(name) {
  const user = fixture.users[name];
  let saved = null;
  const client = new IdentityClient({ apiUrl: fixture.origin, redirectUri: fixture.mobile_redirect,
    request: fetch, readRefresh: async () => saved, writeRefresh: async value => { saved = value; }, clearRefresh: async () => { saved = null; },
    pkce: async () => { const verifier = randomBytes(32).toString('base64url'); return { verifier, challenge: createHash('sha256').update(verifier).digest('base64url') }; },
    browser: async (url, redirect) => {
      const context = await browser.newContext();
      try {
        const page = await context.newPage();
        const capture = await nativeCallback(page, redirect);
        try {
          await page.goto(url);
          await page.waitForURL(value => value.origin === providerOrigin);
          await page.locator('input[name="username"]:visible,input[autocomplete="username"]:visible').first().fill(name);
          const password = page.locator('input[type="password"]:visible').first();
          if (!await password.isVisible()) await submit(page);
          assert(new URL(page.url()).origin === providerOrigin);
          await password.fill(user.password); await submit(page);
          const otp = page.locator('input[autocomplete="one-time-code"]:visible,input[name="totpCode"]:visible,input[name="code"]:visible,input[name="softwareTokenMfaCode"]:visible,input[name="mfaCode"]:visible').first();
          await otp.waitFor({ state: 'visible' });
          const totp = new TOTP({ algorithm: 'SHA1', digits: 6, period: 30, secret: Secret.fromBase32(user.totp_seed) });
          let value = totp.generate();
          if (otpUsed.get(name) === value) { await page.waitForTimeout(31000-Date.now()%30000); value = totp.generate(); }
          otpUsed.set(name, value);
          assert(new URL(page.url()).origin === providerOrigin);
          await otp.fill(value); await submit(page);
          return await capture.callback;
        } finally { await capture.dispose(); }
      } finally { await context.close(); }
    },
  });
  clients.push(client); return client;
}
async function denied(action) { let rejected = false; try { await action(); } catch { rejected = true; } assert(rejected); }
async function mutate(client, path, body, key = randomUUID()) {
  const result = await client.familyRequest(path, body, key);
  assert(result.status === 'APPLIED' && Number.isSafeInteger(result.event_sequence));
  minimumSequence = Math.max(minimumSequence, result.event_sequence); return result;
}
try {
  browser = await chromium.launch({ headless: true, ...(process.env.E1_CHROMIUM_PATH ? { executablePath: process.env.E1_CHROMIUM_PATH } : {}) });
  const primary = Object.keys(fixture.users).find(n => fixture.users[n].principal);
  const secondary = Object.keys(fixture.users).find(n => !fixture.users[n].principal);
  const p = clientFor(primary), s = clientFor(secondary);
  step = 'wrong_contact';
  await denied(() => p.activate(fixture.users[secondary].invitation));
  step = 'primary_activation'; await p.activate(fixture.users[primary].invitation);
  step = 'secondary_activation'; await s.activate(fixture.users[secondary].invitation);
  step = 'invitation_replay'; await denied(() => p.activate(fixture.users[primary].invitation));
  checks.push('verified_contact_and_one_use_activation');
  step = 'ordinary_login'; assert(await p.login() === 'PADRE'); assert(await s.login() === 'PADRE');
  const student = fixture.batch.students[0].id;
  const own = await p.familyRequest('/v1/students'), secondaryOwn = await s.familyRequest('/v1/students');
  assert(own.students.length === 1 && own.students[0].id === student && own.students[0].principal);
  assert(secondaryOwn.students.length === 1 && !secondaryOwn.students[0].principal);
  await denied(() => p.familyRequest(`/v1/students/${randomUUID()}/family`));
  checks.push('exact_children_and_capabilities');
  // Chromium canvas supplies a small synthetic JPEG; no source file or person photograph.
  const canvasPage = await browser.newPage();
  const photo = await canvasPage.evaluate(() => { const c = document.createElement('canvas'); c.width = 12; c.height = 12; return c.toDataURL('image/jpeg').split(',')[1]; });
  await canvasPage.close();
  const body = { student_id: student, name: 'Cuidador sintético', document: 'E2-SYNTHETIC', photo };
  step = 'family_mutations';
  await denied(() => s.familyRequest('/v1/caregivers', body, randomUUID()));
  const key = randomUUID(), caregiver = await mutate(p, '/v1/caregivers', body, key);
  assert((await mutate(p, '/v1/caregivers', body, key)).id === caregiver.id);
  await denied(() => p.familyRequest('/v1/caregivers', { ...body, name: 'Changed' }, key));
  const tomorrowDate = new Date(Date.now()+86400000);
  const tomorrow = tomorrowDate.toISOString().slice(0,10);
  const recurrence = { start_date: tomorrow, end_date: new Date(Date.now()+8*86400000).toISOString().slice(0,10),
    weekdays: [((tomorrowDate.getUTCDay()+6)%7)+1], from: '13:00', until: '13:15' };
  const authBody = { student_id: student, caregiver_id: caregiver.id, recurrence };
  await denied(() => s.familyRequest('/v1/authorizations', authBody, randomUUID()));
  await denied(() => p.familyRequest('/v1/authorizations', { ...authBody, recurrence: { ...recurrence, from: '20:00', until: '20:15' } }, randomUUID()));
  const authorization = await mutate(p, '/v1/authorizations', authBody);
  const expanded = (await p.familyRequest(`/v1/students/${student}/family`)).authorizations.find(a => a.id === authorization.id).schedule;
  assert(expanded.length === 2 && expanded.every(s => new Date(s.from).getUTCHours() === 18));
  await mutate(p, `/v1/caregivers/${caregiver.id}/update`, { ...body, version: 1, document: 'E2-CHANGED' });
  let records = await p.familyRequest(`/v1/students/${student}/family`);
  assert(records.authorizations.find(a => a.id === authorization.id).revoked);
  const another = await mutate(p, '/v1/authorizations', authBody);
  await mutate(p, `/v1/authorizations/${another.id}/revoke`, { student_id: student });
  checks.push('primary_only_idempotency_caregiver_versions_revocation');
  step = 'principal_change'; await control('principal');
  await denied(() => p.check()); await denied(() => s.check());
  assert(await p.login() === 'PADRE'); assert(await s.login() === 'PADRE');
  await denied(() => p.familyRequest('/v1/authorizations', authBody, randomUUID()));
  await mutate(s, '/v1/authorizations', authBody);
  checks.push('technical_principal_invalidates_sessions_and_authorizations');
  step = 'school_restriction'; await control('block'); await denied(() => s.check());
  assert(await s.login() === 'PADRE');
  // A last mutation anchors all preceding technical events in the external chain.
  await mutate(s, '/v1/caregivers', body);
  await denied(() => s.familyRequest('/v1/authorizations', authBody, randomUUID()));
  checks.push('school_restriction_cannot_be_expanded');
  step = 'technical_deactivation'; await control('deactivate');
  await denied(() => s.check()); await denied(() => s.login());
  checks.push('technical_deactivation_denies_existing_and_new_sessions');
  step = 'audit_anchor'; await control('original-principal');
  assert(await p.login() === 'PADRE');
  await mutate(p, '/v1/caregivers', body);
  passed = true;
} catch { passed = false; }
finally {
  for (const client of clients) await client.logout().catch(() => {});
  if (browser) await browser.close();
  writeFileSync('work/e2-browser-acceptance.json', JSON.stringify({ sha: process.env.E2_RELEASE_SHA ?? process.env.GITHUB_SHA, trial_id: fixture.trial_id,
    passed, step, checks, minimum_sequence: minimumSequence, e2_accepted: false,
    scope: 'Real synthetic IdP and shared mobile protocol; requires independent WORM verification and the other E2 checks. No Android physical-device claim.' }, null, 2)+'\n');
}
if (!passed) { process.stderr.write('BLOCKED: E2 synthetic protocol trial failed at '+step+'\n'); process.exitCode = 2; }
