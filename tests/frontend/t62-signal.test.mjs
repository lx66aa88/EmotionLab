import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import test from 'node:test';
import { smoothPrediction } from '../../frontend/src/live/session.js';
import { CLOSE_LEAD, updateSignalPresentation } from '../../frontend/src/live/signalPresentation.js';
// Synthetic symmetric near ties isolate presentation behavior from the course images.
const distribution = (label, values) => ({
  label,
  probabilities: values.map((probability, index) => ({ label: index, probability })),
});
const pair = [
  distribution(0, [.44, .4, .03, .04, .03, .03, .03]),
  distribution(1, [.4, .44, .03, .04, .03, .03, .03]),
];
const sample = (smoothed, frameId, status = 'ok') => ({ status, smoothed, metrics: { frameId } });
let ema = null;
const samples = Array.from({ length: 42 }, (_, i) => {
  ema = smoothPrediction(pair[i % 2], ema);
  return sample(ema, i + 1);
}).slice(-12);

test('Alternating near-ties from synthetic predictions update frame metadata without oscillating sculpture', () => {
  let view = updateSignalPresentation(null, samples[0]);
  const category = view.category;
  assert.equal(new Set(samples.map(frame => frame.smoothed.label)).size, 2);
  for (const frame of samples.slice(1)) {
    const previous = structuredClone(frame);
    view = updateSignalPresentation(view, frame);
    const lead = frame.smoothed.probabilities[frame.smoothed.label].probability -
      frame.smoothed.probabilities[category].probability;
    assert.ok(lead < CLOSE_LEAD);
    assert.equal(view.category, category);
    assert.equal(view.frameId, frame.metrics.frameId);
    assert.deepEqual(frame, previous);
  }
});

test('A close candidate needs a distinct new sample; a clear lead switches immediately', () => {
  const [first, close] = samples;
  const view = updateSignalPresentation(null, first);
  const held = updateSignalPresentation(view, close);
  assert.notEqual(close.smoothed.label, view.category);
  assert.equal(held.category, view.category);
  assert.equal(updateSignalPresentation(held, close), held);
  assert.equal(updateSignalPresentation(held, first), held);
  assert.equal(updateSignalPresentation(held, sample(close.smoothed, close.metrics.frameId + 1)).category, close.smoothed.label);
  const happy = distribution(3, [.02, .02, .02, .88, .02, .02, .02]);
  assert.equal(updateSignalPresentation(held, sample(happy, close.metrics.frameId + 1)).category, 3);
});

test('Inactive, paused, interrupted, stale and invalid LIVE states clear the prior presentation', () => {
  const previous = updateSignalPresentation(null, samples[0]);
  for (const status of ['off', 'waiting', 'no_face', 'target_lost', 'low_quality', 'paused', 'interrupted', 'stale', 'backend_error', 'camera_error']) {
    assert.equal(updateSignalPresentation(previous, { ...samples[1], status }), null);
  }
  assert.equal(updateSignalPresentation(previous, { status: 'ok' }), null);
  assert.equal(updateSignalPresentation(null, samples[1]).category, samples[1].smoothed.label);
});
