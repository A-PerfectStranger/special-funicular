import assert from 'node:assert/strict';
import test from 'node:test';
import { previewFor } from './preview.ts';

test('ninguna vista de ejemplo concede autorización o habilita retiros', () => {
  for (const role of ['PADRE', 'GUARDIA'] as const) {
    assert.equal(previewFor(role).canAuthorize, false);
    assert.match(previewFor(role).message, /no est/);
  }
});
