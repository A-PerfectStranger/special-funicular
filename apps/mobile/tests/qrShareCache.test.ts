import assert from 'node:assert/strict';
import test from 'node:test';
import { isQrShareFile } from '../src/qrShareCache.ts';
test('QR cleanup cannot target a source photograph, directory or arbitrary cache entry', () => {
  const file = 'pickup-share-38a51d9f-229c-45f7-a2fd-a7612be6e431.png';
  assert.equal(isQrShareFile(file), true);
  for (const name of ['photo.jpg', '../'+file, 'nested/'+file, file+'/../photo.jpg', file+'.jpg', 'pickup-share-unknown.png']) assert.equal(isQrShareFile(name), false);
});
