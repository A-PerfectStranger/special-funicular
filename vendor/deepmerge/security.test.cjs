const { test } = require('node:test');
const assert = require('node:assert/strict');
const merge = require('./index.cjs');

test('GHSA-gcqx-w48m-w2h4: source and target never poison result prototype', () => {
  for (const payload of [
    '{"__proto__":{"polluted":true}}',
    '{"constructor":{"prototype":{"polluted":true}}}',
    '{"nested":{"__proto__":{"polluted":true}}}',
  ]) {
    for (const result of [merge({}, JSON.parse(payload)), merge(JSON.parse(payload), {})]) {
      assert.equal(result.polluted, undefined);
      assert.equal(Object.getPrototypeOf(result), Object.prototype);
      assert.equal(Object.prototype.polluted, undefined);
      if (result.nested) assert.equal(result.nested.polluted, undefined);
    }
  }
  const nullPrototype = Object.create(null);
  Object.defineProperty(nullPrototype, '__proto__', { value: { polluted: true }, enumerable: true });
  assert.equal(merge(nullPrototype, {}).polluted, undefined);
  assert.equal(merge({}, nullPrototype).polluted, undefined);
});

test('Expo config nested properties and array merges retain normal semantics', () => {
  const base = { android: { package: 'synthetic.development' }, plugins: ['first'] };
  const result = merge(base, { android: { versionCode: 1 }, plugins: ['second'] });
  assert.deepEqual(result, {
    android: { package: 'synthetic.development', versionCode: 1 }, plugins: ['first', 'second'],
  });
  assert.deepEqual(base.plugins, ['first']);
});
