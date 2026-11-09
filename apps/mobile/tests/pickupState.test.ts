import assert from 'node:assert/strict';
import test from 'node:test';
import { OnlinePermission, isOperationId, type PickupOperation } from '../src/pickupState.ts';
const enabled: PickupOperation = { operation_id: 'f8fcba07-9901-488c-977c-f3e64492e813', state: 'HABILITADA',
  server_now: '2026-11-08T18:00:00Z', permission_expires_at: '2026-11-08T18:00:30Z',
  may_handover: true, incident_reason: '', report_result: '', report_protected: false };
test('permission expires by monotonic freshness even with no network response', () => {
  const p = new OnlinePermission();
  p.observe(enabled, 100, 200);
  assert.equal(p.allowed(200), true); assert.equal(p.allowed(1200), false);
  p.observe(enabled, 100, 1500); assert.equal(p.allowed(1500), false);
});
test('pending, incident, malformed expiry, reported and offline never grant permission', () => {
  for (const state of ['PENDIENTE_ARCHIVO', 'INCIDENCIA', 'ENTREGA_REPORTADA'] as const) {
    const p = new OnlinePermission(); p.observe({ ...enabled, state }, 100, 200); assert.equal(p.allowed(200), false);
  }
  for (const permission_expires_at of [null, 'invalid', '2026-11-08T18:01:00Z']) {
    const p = new OnlinePermission(); p.observe({ ...enabled, permission_expires_at }, 100, 200); assert.equal(p.allowed(200), false);
  }
  const p = new OnlinePermission(); p.observe(enabled, 100, 200); p.invalidate(); assert.equal(p.allowed(200), false);
});
test('round trip is subtracted and local wall-clock changes cannot renew expiry', () => {
  const p = new OnlinePermission();
  p.observe({ ...enabled, permission_expires_at: '2026-11-08T18:00:00.400Z' }, 100, 300);
  assert.equal(p.allowed(499), true); assert.equal(p.allowed(500), false);
  assert.equal(isOperationId(enabled.operation_id), true); assert.equal(isOperationId('token-or-file'), false);
});
