import assert from 'node:assert/strict';
import test from 'node:test';
import { IdentityClient } from '../src/identity.ts';
import type { IdentityDependencies } from '../src/identity.ts';

const access = 'a'.repeat(43), refresh = 'r'.repeat(43), state = 's'.repeat(43);
function harness(overrides: Partial<IdentityDependencies> = {}) {
  let saved: string | null = null;
  const calls: { path: string; body: unknown; headers: HeadersInit | undefined }[] = [];
  const dependencies: IdentityDependencies = {
    apiUrl: 'https://api.example', redirectUri: 'retiro-seguro-staging://auth/callback',
    pkce: async () => ({ verifier: 'v'.repeat(43), challenge: 'c'.repeat(43) }),
    readRefresh: async () => saved, writeRefresh: async value => { saved = value; },
    clearRefresh: async () => { saved = null; },
    browser: async () => `retiro-seguro-staging://auth/callback?code=one-use-code&state=${state}`,
    request: async (url, options) => {
      const path = new URL(String(url)).pathname;
      calls.push({ path, body: options?.body ? JSON.parse(String(options.body)) : null,
        headers: options?.headers });
      const data = path.endsWith('/start')
        ? { authorization_url: 'https://idp.example/authorize', state, exchange_key: 'e'.repeat(43) }
        : path === '/v1/me' ? { role: 'PADRE', pickup_enabled: false }
          : { access_token: access, refresh_token: refresh, expires_in: 300 };
      return new Response(JSON.stringify(data), { status: 200 });
    }, ...overrides,
  };
  return { client: new IdentityClient(dependencies), calls, saved: () => saved };
}

test('PKCE browser login stores only refresh in OS storage and validates role online', async () => {
  const { client, calls, saved } = harness();
  assert.equal(await client.login(), 'PADRE');
  assert.equal(saved(), refresh);
  assert.deepEqual(calls[1].body, { state, code: 'one-use-code',
    code_verifier: 'v'.repeat(43), exchange_key: 'e'.repeat(43) });
  assert.deepEqual(calls.at(-1)?.headers, { Authorization: `Bearer ${access}` });
  assert.equal(await client.logout(), true);
  assert.equal(saved(), null);
  assert.deepEqual(calls.at(-1)?.body, { refresh_token: refresh });
});

test('callback substitution/replay never reaches exchange', async () => {
  for (const callback of [
    'evil://auth/callback?code=code&state=' + state,
    'retiro-seguro-staging://auth/callback?code=code&state=other',
    `retiro-seguro-staging://auth/callback?code=code&state=${state}&state=${state}`,
  ]) {
    const { client, calls, saved } = harness({ browser: async () => callback });
    await assert.rejects(client.login());
    assert.equal(calls.length, 1);
    assert.equal(saved(), null);
  }
});

test('no role or authorization is available without online verification', async () => {
  const { client } = harness({ readRefresh: async () => refresh,
    request: async () => { throw new Error('offline'); } });
  await assert.rejects(client.check());
  const wrongRole = harness({ request: async () => new Response(JSON.stringify({
    role: 'ADMIN_SISTEMA', pickup_enabled: false,
  })) });
  await assert.rejects(wrongRole.client.login());
});

test('logout during browser return prevents persisting a late session', async () => {
  let returnFromBrowser: (value: string) => void = () => {};
  let opened: () => void = () => {};
  const browserOpened = new Promise<void>(resolve => { opened = resolve; });
  const { client, saved } = harness({ browser: () => {
    opened();
    return new Promise<string>(resolve => { returnFromBrowser = resolve; });
  } });
  const login = client.login();
  await browserOpened;
  await client.logout();
  returnFromBrowser(`retiro-seguro-staging://auth/callback?code=code&state=${state}`);
  await assert.rejects(login);
  assert.equal(saved(), null);
});
