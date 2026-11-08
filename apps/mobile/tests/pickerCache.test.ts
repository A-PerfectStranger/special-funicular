import assert from 'node:assert/strict';
import test from 'node:test';
import { isTemporaryPhoto } from '../src/pickerCache.ts';
const cache = 'file:///data/user/0/org.example/cache/';

test('only an app cache copy is eligible for deletion', () => {
  assert.equal(isTemporaryPhoto(cache+'ImagePicker/synthetic.jpg', cache), true);
  for (const original of [
    'file:///storage/emulated/0/DCIM/Camera/original.jpg',
    'content://media/external/images/123',
    'file:///data/user/0/org.example/cache-other/original.jpg',
    cache, 'https://example.invalid/image.jpg',
  ]) assert.equal(isTemporaryPhoto(original, cache), false);
});

test('traversal and encoded paths cannot disguise an original as a disposable copy', () => {
  for (const original of [
    cache+'../files/original.jpg', cache+'ImagePicker/../../files/original.jpg',
    cache+'%2e%2e/files/original.jpg', cache+'%252e%252e/files/original.jpg',
    cache+'ImagePicker/a.jpg?target=original', cache+'ImagePicker/a.jpg#target',
    'not a file URI',
  ]) assert.equal(isTemporaryPhoto(original, cache), false);
});
