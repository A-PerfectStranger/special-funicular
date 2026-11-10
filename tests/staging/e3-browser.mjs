// No provider errors, screenshots, traces, credentials or token URLs are serialized.
import { chromium } from 'playwright';
import { TOTP, Secret } from 'otpauth';
import { randomBytes, createHash, randomUUID } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { nativeCallback } from './native-callback.mjs';
import { safeFailure } from './diagnostics.mjs';
import { IdentityClient, PickupRequestError } from '../../apps/mobile/src/identity.ts';
const fixture = JSON.parse(readFileSync(0, 'utf8'));
const providerOrigin = 'https://retiro-e1-028364485203.auth.us-east-1.amazoncognito.com';
const run = promisify(execFile), clients = [], checks = [];
let browser, step = 'launch', minimumSequence = 0, passed = false, httpStatus = null;
let failure = {};
const assert = value => { if (!value) throw new Error('Trial assertion failed'); };
let dropResponse = false;
async function network(url, options) {
  const response = await fetch(url, options);
  if (dropResponse && String(url).endsWith('/v1/guard/confirm-pickup') && response.ok) { dropResponse = false; await response.arrayBuffer(); throw new Error('Injected response loss after server commit'); }
  return response;
}
const otpUsed = new Map();
async function control(action) { await run('python3', ['-m', 'scripts.e2_fixture_control', action]); }
async function submit(page) { await page.locator('button[type="submit"]:visible,input[type="submit"]:visible').first().click({ noWaitAfter: true }); }
function clientFor(name) {
  const user = fixture.users[name];
  let saved = null;
  const client = new IdentityClient({ apiUrl: fixture.origin, redirectUri: fixture.mobile_redirect,
    request: network, readRefresh: async () => saved, writeRefresh: async value => { saved = value; }, clearRefresh: async () => { saved = null; },
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
const allChecks = { student: true, caregiver: true, document: true };
const episodes = {};
async function observe(guard, id, until) {
  const end = Date.now() + 18000;
  while (Date.now() < end) {
    const value = await guard.pickupRequest(`/v1/guard/operations/${id}`);
    if (until(value)) return value;
    await new Promise(resolve => setTimeout(resolve, 200));
  }
  throw new Error('Timed out waiting for a durable state');
}
async function decide(guard, entry, checks = allChecks) {
  const id = randomUUID();
  await guard.pickupRequest('/v1/guard/confirm-pickup', { token: entry.qr, checks }, id);
  return id;
}
async function physical(guard, id, delivered, observed) {
  const key = randomUUID(), body = { delivered, witnessed_at: observed, reason: 'Synthetic observed door result; no physical student involved' };
  const result = await guard.pickupRequest(`/v1/guard/operations/${id}/report-handover`, body, key);
  assert((await guard.pickupRequest(`/v1/guard/operations/${id}/report-handover`, body, key)).report_event_id === result.report_event_id);
  minimumSequence = Math.max(minimumSequence, result.event_sequence);
  return observe(guard, id, value => value.report_protected === true);
}
try {
  browser = await chromium.launch({ headless: true, ...(process.env.E1_CHROMIUM_PATH ? { executablePath: process.env.E1_CHROMIUM_PATH } : {}) });
  const primary = Object.keys(fixture.users).find(n => fixture.users[n].principal);
  const p = clientFor(primary), g = clientFor('e1-a-guard'), other = clientFor('e1-b-guard');
  step = 'login';
  assert(await p.login() === 'PADRE'); assert(await g.login() === 'GUARDIA'); assert(await other.login() === 'GUARDIA');
  const capability = await fetch(fixture.origin+'/v1/pickup/capabilities', { cache: 'no-store' }).then(r => r.json());
  assert(capability.pickup_enabled === true && capability.synthetic_only === true);
  const canvasPage = await browser.newPage();
  const photo = await canvasPage.evaluate(() => { const c = document.createElement('canvas'); c.width = 12; c.height = 12; return c.toDataURL('image/jpeg').split(',')[1]; });
  await canvasPage.close();
  // Bogota synthetic fixture: schedule is selected in the site timezone, not the
  // browser's timezone. Leave a full minute for all eight audited preparations.
  let start = Math.ceil((Date.now()+90000)/60000)*60000;
  let local = new Date(start-5*3600000), finishLocal = new Date(start+15*60000-5*3600000);
  if (local.toISOString().slice(0,10) !== finishLocal.toISOString().slice(0,10)) {
    start = Date.parse(local.toISOString().slice(0,10)+'T00:00:00Z')+86400000+5*3600000+60000;
    local = new Date(start-5*3600000); finishLocal = new Date(start+15*60000-5*3600000);
  }
  const date = local.toISOString().slice(0,10);
  const recurrence = { start_date: date, end_date: date, weekdays: [((local.getUTCDay()+6)%7)+1], from: local.toISOString().slice(11,16), until: finishLocal.toISOString().slice(11,16) };
  step = 'prepare_qr';
  for (const student of fixture.batch.students) {
    const caregiver = await mutate(p, '/v1/caregivers', { student_id: student.id, name: 'E3 synthetic caregiver', document: 'E3-SYNTHETIC', photo });
    const authorization = await mutate(p, '/v1/authorizations', { student_id: student.id, caregiver_id: caregiver.id, recurrence });
    const issued = await p.pickupRequest(`/v1/authorizations/${authorization.id}/issue-qr`, { valid_from: new Date(start).toISOString() }, randomUUID());
    assert(/^[A-Za-z0-9_-]{43}$/.test(issued.qr));
    episodes[student.name.split(' ').at(-1)] = { ...issued, authorization: authorization.id, student: student.id };
    minimumSequence = Math.max(minimumSequence, issued.event_sequence);
  }
  await denied(() => g.pickupRequest('/v1/guard/resolve-qr', { token: episodes.success.qr }));
  await denied(() => g.pickupPhoto(episodes.success.qr));
  checks.push('before_start_no_data_or_photo');
  step = 'wait_valid_from';
  while (Date.now() <= start+100) await new Promise(resolve => setTimeout(resolve, Math.min(1000, start+101-Date.now())));
  // A midnight boundary can defer valid_from beyond the five-minute MFA/idle window.
  // Start fresh interactive sessions after waiting; never relax server freshness.
  step = 'fresh_mfa_after_schedule_wait';
  assert(await p.login() === 'PADRE');
  assert(await g.login() === 'GUARDIA');
  assert(await other.login() === 'GUARDIA');
  step = 'scope_other_site_denied';
  await denied(() => other.pickupRequest('/v1/guard/resolve-qr', { token: episodes.success.qr }));
  step = 'scope_parent_denied';
  await denied(() => p.pickupRequest('/v1/guard/resolve-qr', { token: episodes.success.qr }));
  step = 'same_site_resolution';
  assert((await g.pickupRequest('/v1/guard/resolve-qr', { token: episodes.success.qr })).caregiver.document === 'E3-SYNTHETIC');
  step = 'same_site_photo';
  assert((await g.pickupPhoto(episodes.success.qr)).startsWith('data:image/jpeg;base64,'));
  checks.push('same_site_guard_only_authenticated_minimal_photo');
  step = 'lost_response_success';
  const id = randomUUID(); dropResponse = true;
  await denied(() => g.pickupRequest('/v1/guard/confirm-pickup', { token: episodes.success.qr, checks: allChecks }, id));
  assert(!dropResponse);
  const enabled = await observe(g, id, value => value.state !== 'PENDIENTE_ARCHIVO');
  assert(enabled.state === 'HABILITADA' && enabled.may_handover);
  assert(Date.parse(enabled.permission_expires_at)-Date.parse(enabled.server_now) <= 30000);
  await denied(() => other.pickupRequest(`/v1/guard/operations/${id}`));
  const delivered = await physical(g, id, true, enabled.server_now);
  assert(delivered.state === 'ENTREGA_REPORTADA' && !delivered.may_handover);
  await denied(() => g.pickupRequest('/v1/guard/confirm-pickup', { token: episodes.success.qr, checks: allChecks }, randomUUID()));
  checks.push('lost_response_same_id_timely_worm_30s_idempotent_physical_report');
  step = 'concurrency_50';
  const attempts = await Promise.all(Array.from({ length: 50 }, async () => {
    try { return await decide(g, episodes.concurrency); } catch { return null; }
  }));
  const winners = attempts.filter(Boolean); assert(winners.length === 1);
  const concurrent = await observe(g, winners[0], value => value.state !== 'PENDIENTE_ARCHIVO');
  assert(concurrent.state === 'HABILITADA');
  await physical(g, winners[0], false, concurrent.server_now);
  checks.push('50_concurrent_requests_one_decision');
  step = 'reject_mismatch';
  const rejected = await decide(g, episodes.reject, { ...allChecks, document: false });
  const rejectState = await observe(g, rejected, value => value.state === 'INCIDENCIA');
  assert(!rejectState.may_handover);
  await physical(g, rejected, false, rejectState.server_now);
  checks.push('physical_mismatch_incident_without_permission');
  step = 'renewal_and_reschedule';
  const renewed = await p.pickupRequest(`/v1/authorizations/${episodes.renew.authorization}/issue-qr`, { valid_from: episodes.renew.valid_from }, randomUUID());
  assert(renewed.expires_at === episodes.renew.expires_at && renewed.qr !== episodes.renew.qr);
  await denied(() => g.pickupRequest('/v1/guard/resolve-qr', { token: episodes.renew.qr }));
  const moved = await p.pickupRequest(`/v1/authorizations/${episodes.reschedule.authorization}/reschedule`, { valid_from: new Date(Date.now()+30000).toISOString(), episode_id: episodes.reschedule.episode_id }, randomUUID());
  assert(moved.episode_id === episodes.reschedule.episode_id);
  await denied(() => g.pickupRequest('/v1/guard/resolve-qr', { token: episodes.reschedule.qr }));
  await denied(() => g.pickupRequest('/v1/guard/resolve-qr', { token: moved.qr }));
  await mutate(p, `/v1/authorizations/${episodes.renew.authorization}/revoke`, { student_id: episodes.renew.student });
  await denied(() => g.pickupRequest('/v1/guard/confirm-pickup', { token: renewed.qr, checks: allChecks }, randomUUID()));
  checks.push('renewal_same_expiry_reschedule_old_dead_revocation_before_decision');
  step = 'revocation_after_decision';
  const revoked = await decide(g, episodes.revoke);
  assert((await observe(g, revoked, value => value.state !== 'PENDIENTE_ARCHIVO')).may_handover);
  await control('e3-revoke');
  const revokedState = await g.pickupRequest(`/v1/guard/operations/${revoked}`);
  assert(revokedState.state === 'INCIDENCIA' && !revokedState.may_handover);
  await physical(g, revoked, false, revokedState.server_now);
  checks.push('committed_block_stops_existing_permission_without_rewriting_decision');
  // Private control defers only this explicitly approved synthetic student's
  // decision for <=15 s. Clock observations and all other archive jobs continue.
  step = 'late_archive';
  await control('e3-hold');
  const timeout = await decide(g, episodes.timeout);
  const timedOut = await observe(g, timeout, value => value.state === 'INCIDENCIA');
  assert(timedOut.incident_reason === 'EVIDENCE_TIMEOUT' && !timedOut.may_handover);
  await new Promise(resolve => setTimeout(resolve, 16000));
  const late = await g.pickupRequest(`/v1/guard/operations/${timeout}`);
  assert(late.state === 'INCIDENCIA' && !late.may_handover);
  const lateReport = await physical(g, timeout, true, late.server_now);
  assert(lateReport.state === 'INCIDENCIA');
  checks.push('timeout_5s_real_late_worm_never_reenables_late_fact_preserved');
  step = 'permission_expiry';
  const expiry = await decide(g, episodes.expiry);
  const opened = await observe(g, expiry, value => value.state !== 'PENDIENTE_ARCHIVO');
  assert(opened.state === 'HABILITADA');
  await new Promise(resolve => setTimeout(resolve, 31000));
  const expired = await g.pickupRequest(`/v1/guard/operations/${expiry}`);
  assert(expired.state === 'INCIDENCIA' && !expired.may_handover);
  await physical(g, expiry, false, expired.server_now);
  checks.push('expired_screen_cannot_authorize_another_handover');
  passed = true;
} catch (error) { passed = false; failure = safeFailure(error); if (error instanceof PickupRequestError) httpStatus = error.status; }
finally {
  for (const client of clients) await client.logout().catch(() => {});
  if (browser) await browser.close();
  writeFileSync('work/e3-browser-acceptance.json', JSON.stringify({ sha: process.env.E2_RELEASE_SHA ?? process.env.GITHUB_SHA,
    trial_id: fixture.trial_id, passed, step, http_status: httpStatus, checks, minimum_sequence: minimumSequence, e3_accepted: false, ...failure,
    scope: 'Real synthetic IdP/mobile protocol/KMS/WORM; acceptance additionally requires independent WORM verification and CI. No physical Android or real student claim.' }, null, 2)+'\n');
}
if (!passed) { process.stderr.write('BLOCKED: E3 synthetic protocol trial failed at '+step+'\n'); process.exitCode = 2; }
