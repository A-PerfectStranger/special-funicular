import assert from 'node:assert/strict';
import test from 'node:test';
import { chromium } from 'playwright';
import { safeFailure, documentScope } from './diagnostics.mjs';

test('error reports retain only fixed categories and never remote text or callback secrets', () => {
  const secret = 'synthetic-credential-and-authorization-code';
  const error = new Error(`page.goto: net::ERR_CONNECTION_RESET at https://user:${secret}@example.invalid/?code=${secret}`);
  assert.deepEqual(safeFailure(error), { failure_kind: 'browser_network', network_error: 'ERR_CONNECTION_RESET' });
  assert.deepEqual(safeFailure(new Error(`net::ERR_UNTRUSTED_PROVIDER_TEXT ${secret}`)),
    { failure_kind: 'browser_network', network_error: 'OTHER_NETWORK_ERROR' });
  assert.deepEqual(safeFailure({ name: 'TimeoutError', message: secret }),
    { failure_kind: 'timeout', network_error: null });
  assert.deepEqual(safeFailure(new Error(secret)), { failure_kind: 'unknown', network_error: null });
});

test('document scope never serializes a URL, code, path or foreign origin', () => {
  for (const [url, scope] of [
    ['https://api.invalid/auth/callback?code=synthetic-secret', 'api'],
    ['https://idp.invalid/oauth?code=synthetic-secret', 'provider'],
    ['https://foreign.invalid/?secret=synthetic-secret', 'other'],
    ['not a URL', 'other'],
  ]) assert.equal(documentScope(url, 'https://api.invalid', 'https://idp.invalid'), scope);
});

test('an actual Chromium navigation failure is classified without preserving its URL', async () => {
  const browser = await chromium.launch({
    ...(process.env.E1_CHROMIUM_PATH ? { executablePath: process.env.E1_CHROMIUM_PATH } : {}),
    headless: true,
  });
  try {
    const page = await browser.newPage();
    await page.route('https://synthetic.invalid/**', route => route.abort('connectionreset'));
    let failure;
    try { await page.goto('https://synthetic.invalid/?code=synthetic-secret'); }
    catch (error) { failure = safeFailure(error); }
    assert.deepEqual(failure, { failure_kind: 'browser_network', network_error: 'ERR_CONNECTION_RESET' });
  } finally { await browser.close(); }
});
