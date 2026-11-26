import assert from 'node:assert/strict';
import test from 'node:test';
import { analysisEvents } from '../../frontend/src/api/analysisStream.js';

test('split UTF-8, a blank line and an unterminated final event', async () => {
  const bytes = new TextEncoder().encode('{"stage":"检查"}\n\n{"event":"result"}');
  const body = new ReadableStream({
    start(controller) {
      for (const byte of bytes) controller.enqueue(Uint8Array.of(byte));
      controller.close();
    },
  });
  const records = [];
  for await (const record of analysisEvents(new Response(body))) records.push(record);
  assert.deepEqual(records, [{ stage: '检查' }, { event: 'result' }]);
});

test('leaving a stream releases the upstream reader', async () => {
  let cancelled = false;
  const body = new ReadableStream({
    start(controller) { controller.enqueue(new TextEncoder().encode('{}\n')); },
    cancel() { cancelled = true; },
  });
  for await (const _ of analysisEvents(new Response(body))) break;
  assert.equal(cancelled, true);
  assert.equal(body.locked, false);
});
