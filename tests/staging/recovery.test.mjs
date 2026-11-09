import assert from 'node:assert/strict';
import test from 'node:test';
import { withRecovery } from './recovery.mjs';

test('recovery cannot overwrite the original failure phase', async () => {
  let phase = 'revocation', captured, capturedError;
  const original = new Error('Controlled test failure');
  await assert.rejects(withRecovery(async () => { throw original; }, async () => {
    phase = 'restoration';
  }, (stage, error) => { captured ??= phase; capturedError ??= error; }), error => error === original);
  assert.equal(captured, 'revocation');
  assert.equal(capturedError, original);
  assert.equal(phase, 'restoration');
});

test('a recovery failure is reported and cannot turn a passed operation into success', async () => {
  const stages = [];
  await assert.rejects(withRecovery(async () => {}, async () => {
    throw new Error('Recovery failed');
  }, stage => stages.push(stage)));
  assert.deepEqual(stages, ['recovery']);
});

test('both failures remain distinguishable and the original is retained', async () => {
  const stages = [], original = new Error('Original');
  await assert.rejects(withRecovery(async () => { throw original; }, async () => {
    throw new Error('Recovery');
  }, stage => stages.push(stage)), error => error === original);
  assert.deepEqual(stages, ['operation', 'recovery']);
});
