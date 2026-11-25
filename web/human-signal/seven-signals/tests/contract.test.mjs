import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';
import { geometryFor } from '../geometry.js';
import { SIGNALS, signalFor } from '../signals.js';

test('the visual catalogue follows the frozen manifest and the LIVE labels', async () => {
  const manifest = JSON.parse(readFileSync(new URL('../../../../configs/inference/best_triple.json', import.meta.url), 'utf8'));
  const { LABELS, ZH } = await import('../../src/liveSession.js');
  assert.deepEqual(SIGNALS.map(signal => signal.name), manifest.labels);
  assert.deepEqual(SIGNALS.map(signal => signal.name), LABELS);
  assert.deepEqual(SIGNALS.map(signal => signal.zh), ZH);
  assert.equal(new Set(SIGNALS.map(signal => signal.motion)).size, 7);
});

test('seven finite, distinct rest geometries share the same ribbon primitives', () => {
  const signatures = SIGNALS.map((_, index) => {
    const mesh = geometryFor(index);
    assert.ok(mesh.length >= 7 && mesh.length <= 14);
    for (const strip of mesh) {
      for (const field of ['silhouette', 'edge', 'lines', 'cuts']) {
        assert.match(strip[field], /^M[\d.\s,LMZ-]+$/);
      }
    }
    return mesh.map(strip => strip.silhouette).join('');
  });
  assert.equal(new Set(signatures).size, 7);
  for (const invalid of [-1, 7, '0', 'length', Infinity, null]) {
    assert.equal(signalFor(invalid), undefined);
    assert.deepEqual(geometryFor(invalid), []);
  }
});

test('the reusable React component preserves caller confidence and separates sources', async () => {
  const vite = await createServer({ configFile: fileURLToPath(new URL('../vite.config.js', import.meta.url)),
    server: { middlewareMode: true, watch: null }, optimizeDeps: { noDiscovery: true, include: [] } });
  try {
    const { SignalSculpture } = await vite.ssrLoadModule('/SignalSculpture.jsx');
    const render = props => renderToStaticMarkup(createElement(SignalSculpture, props));
    const confidence = 0.44073051687629117;
    const prediction = render({ category: 0, source: 'prediction', confidence });
    assert.ok(prediction.includes(`data-confidence="${confidence}"`));
    assert.ok(prediction.includes(`<data value="${confidence}">${confidence}</data>`));
    assert.match(prediction, /模型预测 · Angry 愤怒/);
    for (const boundary of [0, 1]) {
      assert.ok(render({ category: 6, source: 'prediction', confidence: boundary }).includes(`data-confidence="${boundary}"`));
    }
    assert.match(render({ category: 0, source: 'target', confidence }), /目标表情 · Angry 愤怒/);
    for (const props of [{ source: 'target' }, { source: 'preview' }, { source: 'prediction', confidence: -0.1 },
      { source: 'prediction', confidence: 1.02 }, { source: 'prediction', confidence: NaN }, { source: 'prediction', category: null }]) {
      assert.doesNotMatch(render({ category: 0, confidence, ...props }), /data-confidence|ss-confidence/);
    }
    assert.doesNotMatch(render({ category: null, source: 'prediction' }), /ss-ribbon/);
    assert.match(render({ category: 3, playback: 'paused' }), /data-mode="paused"/);
    assert.match(render({ category: 3, quality: 'low' }), /data-mode="static"/);
  } finally {
    await vite.close();
  }
});
