import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readCapabilities } from '../src/capabilities.ts';

test('never enables pickup from unsupported or malformed server responses', () => {
  for (const value of [null, {}, true, { api_version: 'v1', pickup_enabled: true },
    { api_version: 'v2', pickup_enabled: false }, { pickup_enabled: 'false' }]) {
    assert.equal(readCapabilities(value), null);
  }
  assert.deepEqual(readCapabilities({ api_version: 'v1', pickup_enabled: false }), {
    api_version: 'v1', pickup_enabled: false,
  });
});
