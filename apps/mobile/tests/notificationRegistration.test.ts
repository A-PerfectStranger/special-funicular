import assert from 'node:assert/strict';
import test from 'node:test';
import { FamilyRequestError } from '../src/identity.ts';
import { registerDevice, notificationRegistrationMessage, NotificationRegistrationError } from '../src/notificationRegistration.ts';
import type { NotificationRegistrationDependencies } from '../src/notificationRegistration.ts';

const nativeToken = 'synthetic-private-native-token';
const expoToken = 'ExpoPushToken[synthetic-private-token]';
function harness(overrides: Partial<NotificationRegistrationDependencies> = {}) {
  const calls: string[] = [];
  const dependencies: NotificationRegistrationDependencies = {
    available: true,
    createChannel: async () => { calls.push('channel'); },
    permission: async () => { calls.push('permission'); return true; },
    deviceToken: async () => { calls.push('device'); return { type: 'android', data: nativeToken }; },
    expoToken: async device => {
      calls.push('provider');
      assert.deepEqual(device, { type: 'android', data: nativeToken });
      return { data: expoToken };
    },
    register: async token => { calls.push('account'); assert.equal(token, expoToken); return { registered: true }; },
    ...overrides,
  };
  return { dependencies, calls };
}

async function rejectsCode(action: () => Promise<unknown>, code: string) {
  await assert.rejects(action, error => {
    assert(error instanceof NotificationRegistrationError);
    assert.equal(error.code, code);
    const publicText = [error.message, error.stack, notificationRegistrationMessage(error), JSON.stringify(error)].join(' ');
    for (const secret of [nativeToken, expoToken, 'synthetic-sensitive-value', 'Authorization']) {
      assert(!publicText.includes(secret));
    }
    assert(!('cause' in error));
    return true;
  });
}

test('device registration requires permission, both token services and explicit account confirmation', async () => {
  const { dependencies, calls } = harness();
  assert.equal(await registerDevice(dependencies), expoToken);
  assert.deepEqual(calls, ['channel', 'permission', 'device', 'provider', 'account']);
});

test('unavailable builds and denied permissions never fetch tokens or register a device', async () => {
  const unavailable = harness({ available: false });
  await rejectsCode(() => registerDevice(unavailable.dependencies), 'N01-FAILED');
  assert.deepEqual(unavailable.calls, []);
  const denied = harness({ permission: async () => false });
  await rejectsCode(() => registerDevice(denied.dependencies), 'N03-DENIED');
  assert.deepEqual(denied.calls, ['channel']);
});

test('native failures cannot be mistaken for provider or server failures and never expose SDK text', async () => {
  const { dependencies, calls } = harness({ deviceToken: async () => {
    throw Object.assign(new Error(`Authorization: ${nativeToken}`), { code: 'E_REGISTRATION_FAILED' });
  } });
  await rejectsCode(() => registerDevice(dependencies), 'N04-NATIVE_REGISTRATION');
  assert.deepEqual(calls, ['channel', 'permission']);
});

for (const [sdkCode, expected] of [
  ['ERR_NOTIFICATIONS_NETWORK_ERROR', 'N05-PROVIDER_NETWORK'],
  ['ERR_NOTIFICATIONS_SERVER_ERROR', 'N05-PROVIDER_REJECTED'],
  ['synthetic-sensitive-value', 'N05-FAILED'],
]) {
  test(`provider failure ${expected} never reaches account registration or includes a raw response`, async () => {
    const { dependencies, calls } = harness({ expoToken: async () => {
      throw Object.assign(new Error(`private response ${expoToken}`), { code: sdkCode });
    } });
    await rejectsCode(() => registerDevice(dependencies), expected);
    assert.deepEqual(calls, ['channel', 'permission', 'device']);
  });
}

test('invalid native and provider tokens stop before another service receives them', async () => {
  const native = harness({ deviceToken: async () => ({ type: 'android', data: null }) });
  await rejectsCode(() => registerDevice(native.dependencies), 'N04-INVALID_RESPONSE');
  assert(!native.calls.includes('provider') && !native.calls.includes('account'));
  for (const data of [null, '', nativeToken, 'ExpoPushToken[bad]', 'ExponentPushToken[secret\nsynthetic]']) {
    const provider = harness({ expoToken: async () => ({ data }) });
    await rejectsCode(() => registerDevice(provider.dependencies), 'N05-INVALID_RESPONSE');
    assert(!provider.calls.includes('account'));
  }
});

test('a successful HTTP response without registered=true never announces success', async () => {
  for (const result of [null, {}, { registered: false }, { registered: 'true' }, { error: expoToken }]) {
    const { dependencies } = harness({ register: async () => result });
    await rejectsCode(() => registerDevice(dependencies), 'N06-INVALID_RESPONSE');
  }
});

test('server rejection has a bounded HTTP support code without its body or headers', async () => {
  const { dependencies } = harness({ register: async () => { throw new FamilyRequestError(403); } });
  await rejectsCode(() => registerDevice(dependencies), 'N06-HTTP_403');
  const unknown = harness({ register: async () => { throw { status: expoToken, message: nativeToken }; } });
  await rejectsCode(() => registerDevice(unknown.dependencies), 'N06-FAILED');
});

test('late device completion after the deadline never reaches Expo or the account', async () => {
  let finish: (value: { type: string; data: unknown }) => void = () => {};
  const { dependencies, calls } = harness({ deviceToken: () => new Promise(resolve => { finish = resolve; }) });
  await rejectsCode(() => registerDevice(dependencies, 5), 'N04-TIMEOUT');
  finish({ type: 'android', data: nativeToken });
  await Promise.resolve();
  assert.deepEqual(calls, ['channel', 'permission']);
});

test('late provider completion after the deadline cannot register an account', async () => {
  let finish: (value: { data: unknown }) => void = () => {};
  const { dependencies, calls } = harness({ expoToken: () => new Promise(resolve => { finish = resolve; }) });
  await rejectsCode(() => registerDevice(dependencies, 5), 'N05-TIMEOUT');
  finish({ data: expoToken });
  await Promise.resolve();
  assert(!calls.includes('account'));
});

test('an ambiguous account response times out without claiming failure or success on the server', async () => {
  let finish: (value: unknown) => void = () => {};
  const { dependencies } = harness({ register: () => new Promise(resolve => { finish = resolve; }) });
  await rejectsCode(() => registerDevice(dependencies, 5), 'N06-TIMEOUT');
  finish({ registered: true });
  await Promise.resolve();
});

test('the permission decision is not subject to token-service deadlines', async () => {
  const { dependencies } = harness({ permission: () => new Promise(resolve => setTimeout(() => resolve(true), 20)) });
  assert.equal(await registerDevice(dependencies, 5), expoToken);
});

test('unclassified errors have a fixed public message without raw provider details', () => {
  assert.equal(notificationRegistrationMessage(new Error(expoToken)),
    'El registro de avisos no está confirmado. Código de soporte: N00.');
});
