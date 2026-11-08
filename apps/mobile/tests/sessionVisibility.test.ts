import assert from 'node:assert/strict';
import test from 'node:test';
import { SessionVisibility } from '../src/sessionVisibility.ts';
import type { MobileRole } from '../src/identity.ts';

function deferred() {
  let resolve!: (role: MobileRole) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<MobileRole>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const settle = () => new Promise(resolve => setImmediate(resolve));

function fixture() {
  const checks: ReturnType<typeof deferred>[] = [];
  let role: MobileRole | null = null, visible = false;
  let form: { photo: string } | null = null;
  const gate = new SessionVisibility(() => {
    const check = deferred(); checks.push(check); return check.promise;
  }, (next, show) => {
    if (next !== undefined) role = next;
    visible = show;
    // The app keeps Family mounted for a hidden PADRE; logout/rejection unmounts it.
    if (role !== 'PADRE') form = null;
    else form ??= { photo: '' };
  });
  gate.start('active');
  gate.beginInteractive(); gate.finishInteractive('PADRE');
  return { gate, checks, state: () => ({ role, visible, form }) };
}

test('native gallery preserves its mounted form behind the mask until online revalidation', async () => {
  const { gate, checks, state } = fixture();
  const original = state().form!;
  await gate.photoActivity(async () => {
    gate.changed('background');
    assert.equal(state().visible, false);
    assert.equal(state().form, original);
    original.photo = 'synthetic-selected-image';
    gate.changed('active');
    assert.equal(state().visible, false);
    checks.at(-1)!.resolve('PADRE'); await settle();
  });
  assert.equal(state().visible, true);
  assert.equal(state().form, original);
  assert.equal(state().form!.photo, 'synthetic-selected-image');
});

test('ordinary background discards family data and picker cancellation releases retention', async () => {
  const { gate, checks, state } = fixture();
  await assert.rejects(gate.photoActivity(async () => { throw new Error('Picker cancelled'); }));
  gate.changed('background');
  assert.deepEqual(state(), { role: null, visible: false, form: null });
  gate.changed('active'); checks.at(-1)!.resolve('PADRE'); await settle();
  assert.equal(state().visible, true);
  assert.equal(state().form!.photo, '');
});

test('revocation or network failure on return discards the family form', async () => {
  const { gate, checks, state } = fixture();
  gate.changed('background'); gate.changed('active');
  checks.at(-1)!.reject(new Error('Session revoked or offline')); await settle();
  assert.deepEqual(state(), { role: null, visible: false, form: null });
});

test('late online responses cannot expose data in background or after logout', async () => {
  const { gate, checks, state } = fixture();
  gate.changed('active'); const pending = checks.at(-1)!;
  gate.changed('background'); pending.resolve('PADRE'); await settle();
  assert.equal(state().visible, false);
  gate.changed('active'); const logoutRace = checks.at(-1)!;
  gate.beginInteractive(); gate.finishInteractive(null);
  logoutRace.resolve('PADRE'); await settle();
  assert.deepEqual(state(), { role: null, visible: false, form: null });
});

test('OIDC return does not race a second check while interactive authentication is pending', async () => {
  const { gate, checks, state } = fixture();
  gate.beginInteractive(); const count = checks.length;
  gate.changed('background'); gate.changed('active');
  assert.equal(checks.length, count);
  checks[0].resolve('GUARDIA'); await settle();
  assert.equal(state().role, null);
  gate.finishInteractive('PADRE');
  assert.equal(state().visible, true);
  assert.equal(state().role, 'PADRE');
});

test('unmounted activity ignores pending checks and authentication completion', async () => {
  const { gate, checks, state } = fixture();
  gate.changed('active'); const pending = checks.at(-1)!;
  gate.dispose();
  const before = state();
  pending.resolve('GUARDIA'); gate.finishInteractive(null); await settle();
  assert.deepEqual(state(), before);
});
