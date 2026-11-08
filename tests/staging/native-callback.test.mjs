import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { chromium } from 'playwright';
import { nativeCallback } from './native-callback.mjs';

async function exercise(target, check, scriptRedirect = false) {
  const server = createServer((request, response) => {
    if (request.method === 'POST') {
      if (scriptRedirect) {
        response.writeHead(200, { 'Content-Type': 'text/html' });
        response.end('<script>window.location.assign(' + JSON.stringify(target) + ')</script>');
      } else {
        response.writeHead(302, { Location: target });
        response.end();
      }
    } else {
      response.writeHead(200, { 'Content-Type': 'text/html' });
      response.end('<form method="post"><button type="submit">Continue</button></form>');
    }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({
    ...(process.env.E1_CHROMIUM_PATH ? { executablePath: process.env.E1_CHROMIUM_PATH } : {}),
    headless: true,
  });
  try {
    const page = await browser.newPage();
    await page.goto(`http://127.0.0.1:${server.address().port}`);
    await check(page);
  } finally {
    await browser.close();
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
  }
}

test('native callback is captured even when Chromium omits the response event', { timeout: 15000 }, async () => {
  const redirect = 'retiro-seguro-staging://auth/callback';
  const expected = redirect + '?code=synthetic-code&state=synthetic-state';
  await exercise(expected, async page => {
    let responseObserved = false;
    page.on('response', response => {
      if (response.headers()['location'] === expected) responseObserved = true;
    });
    const capture = await nativeCallback(page, redirect, 5000);
    try {
      await page.locator('button').click({ noWaitAfter: true });
      assert.equal(await capture.callback, expected);
      assert.equal(responseObserved, false);
    } finally { await capture.dispose(); }
  });
});

test('a foreign native scheme never satisfies the registered callback', { timeout: 15000 }, async () => {
  await exercise('unexpected-native://auth/callback?code=synthetic', async page => {
    const capture = await nativeCallback(page, 'retiro-seguro-staging://auth/callback', 5000);
    try {
      await page.locator('button').click({ noWaitAfter: true });
      await assert.rejects(capture.callback, /Unregistered native callback/);
    } finally { await capture.dispose(); }
  });
});

test('native callback requested by provider script is captured', { timeout: 15000 }, async () => {
  const redirect = 'retiro-seguro-staging://auth/callback';
  const expected = redirect + '?code=synthetic-code&state=synthetic-state';
  await exercise(expected, async page => {
    const capture = await nativeCallback(page, redirect, 5000);
    try {
      await page.locator('button').click({ noWaitAfter: true });
      assert.equal(await capture.callback, expected);
    } finally { await capture.dispose(); }
  }, true);
});

test('script navigation to a foreign native callback is rejected', { timeout: 15000 }, async () => {
  await exercise('unexpected-native://auth/callback?code=synthetic', async page => {
    const capture = await nativeCallback(page, 'retiro-seguro-staging://auth/callback', 5000);
    try {
      await page.locator('button').click({ noWaitAfter: true });
      await assert.rejects(capture.callback, /Unregistered native callback/);
    } finally { await capture.dispose(); }
  }, true);
});
