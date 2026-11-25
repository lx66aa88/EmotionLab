import assert from 'node:assert/strict';
import test from 'node:test';
import { CHALLENGE, challengeReducer, challengeScore, initialChallenge, nextClockWake, shuffledTargets } from '../src/challengeGame.js';
import { readChallengeSignal } from '../src/challengeSignal.js';
import { SIGNALS } from '../seven-signals/signals.js';

// Synthetic unit events test the reducer only. Production reads LiveSession.
const step = (state, type, at, extra) => challengeReducer(state, { type, at, ...extra });
const tick = (state, at = state.deadline) => step(state, 'tick', at, { deadline: state.deadline });
const start = (order = CHALLENGE.targets) => step(initialChallenge(), 'start', 1000, { order });
const raw = (state, frame, captured, label = state.rounds[state.index].label, at = captured + 70) =>
  step(state, 'signal', at, { signal: { kind: 'raw', frame, captured, label, probability: .62 } });
const invalid = (state, kind, frame, captured) => step(state, 'signal', captured + 70, { signal: { kind, frame, captured } });
const round = state => state.rounds[state.index];
const settleMatch = (s, frame = 1) => [0, 1, 2].reduce((state, i) => raw(state, frame + i, s.since + 120 + i * 333), s);

test('shuffle produces each frozen label once; all seven original sculptures are mapped', () => {
  assert.deepEqual(SIGNALS.map(({ name, zh, form }) => [name, zh, form]), [
    ['Angry', '愤怒', 'Fault'], ['Disgust', '厌恶', 'Recoil'], ['Fear', '恐惧', 'Filament'],
    ['Happy', '快乐', 'Bloom'], ['Sad', '悲伤', 'Fall'], ['Surprise', '惊喜', 'Burst'], ['Neutral', '中立', 'Plane'],
  ]);
  for (const random of [() => 0, () => .41, () => .999]) {
    const list = shuffledTargets(random);
    assert.deepEqual([...list].sort(), CHALLENGE.targets);
    assert.equal(start(list).rounds[0].label, list[0]);
  }
  assert.notDeepEqual(shuffledTargets(() => 0), shuffledTargets(() => .999));
  assert.equal(start([0, 0, 0, 0, 0, 0, 0]).phase, 'idle');
});

test('countdown and exact 8-second window reject prep and post-buzzer responses', () => {
  let state = start();
  assert.equal(state.deadline, 4000);
  assert.equal(tick(state, 3999).seconds, 1);
  assert.equal(raw(state, 1, 3500), state);
  state = tick(state);
  assert.equal(state.seconds, 8);
  assert.equal(state.deadline, 12000);
  assert.equal(raw(state, 2, 3999), state);
  state = raw(raw(state, 3, 11310), 4, 11630);
  state = raw(state, 5, 11960, 0, 12000);
  assert.equal(round(state).outcome, 'miss');
  assert.equal(round(state).attempts[0].matches, 2);
  assert.equal(challengeScore(state), 0);
});

test('a match requires consecutive frames and elapsed time; record actual RAW evidence and score once', () => {
  let state = tick(start());
  state = raw(state, 1, 4110);
  assert.equal(state.attempt.matches, 1);
  assert.equal(state.phase, 'playing');
  assert.equal(raw(state, 1, 4210), state);
  assert.equal(raw(state, 2, 4110), state);
  state = raw(raw(state, 2, 4210), 3, 4320);
  assert.equal(state.phase, 'playing', 'three frames too close together do not score');
  state = raw(state, 4, 4660);
  const [record] = round(state).attempts;
  assert.equal(round(state).outcome, 'matched');
  assert.equal(record.matches, 4);
  assert.equal(record.source, 'live_raw');
  assert.deepEqual(record.winningFrames.map(frame => frame.frame), [1, 2, 3, 4]);
  assert.equal(challengeScore(state), 1);
  for (const type of ['retry', 'skip', 'signal']) assert.equal(step(state, type, 5000), state);
});

test('mismatch, absent face, quality guard, and long gaps interrupt a streak', () => {
  let state = tick(start());
  state = raw(state, 1, 4100);
  state = raw(state, 2, 4440, 3);
  assert.equal(state.attempt.streak.length, 0);
  state = raw(state, 3, 4780);
  state = invalid(state, 'no_face', 4, 5110);
  assert.equal(state.attempt.streak.length, 0);
  state = raw(state, 5, 5450);
  state = invalid(state, 'low_quality', 6, 5780);
  assert.equal(state.attempt.streak.length, 0);
  state = raw(state, 7, 6110);
  state = raw(state, 8, 7700);
  assert.equal(state.attempt.streak.length, 1);
  assert.equal(state.attempt.matches, 5);
  assert.equal(state.attempt.noFace, 1);
  assert.equal(state.attempt.unclear, 1);
  assert.equal(challengeScore(state), 0);
});

test('absence cannot score even for Neutral; timeout distinguishes absence, uncertainty, and backend', () => {
  const neutralFirst = [6, 0, 1, 2, 3, 4, 5];
  for (const [kind, expected] of [['no_face', 'no_face'], ['target_lost', 'no_face'],
    ['close', 'unclear'], ['multiple', 'unclear'], ['service', 'service']]) {
    let state = tick(start(neutralFirst));
    state = tick(invalid(state, kind, 1, 4200));
    assert.equal(round(state).outcome, expected);
    assert.equal(round(state).attempts[0].source, 'live_status');
    assert.equal(round(state).attempts[0].matches, 0);
    assert.equal(challengeScore(state), 0);
  }
});

test('retry retains the prior attempt, requires fresh frames, and grants at most one point', () => {
  let state = tick(start());
  state = tick(raw(state, 1, 4500, 2));
  state = step(state, 'retry', 12300);
  assert.equal(round(state).attempts[0].outcome, 'miss');
  assert.equal(state.attempt.judged, 0);
  state = tick(state);
  assert.equal(raw(state, 2, 15200), state);
  state = settleMatch(state, 3);
  assert.equal(round(state).attempts.length, 2);
  assert.equal(challengeScore(state), 1);
});

test('pause preserves remaining time, rejects stale timer and frames, and clears the streak', () => {
  let state = tick(start());
  state = raw(raw(state, 1, 4100), 2, 4440);
  const originalDeadline = state.deadline;
  state = step(state, 'pause', 4800, { reason: 'manual' });
  assert.equal(state.pause.remaining, 7200);
  assert.equal(state.attempt.streak.length, 0);
  assert.equal(state.current, null);
  assert.equal(raw(state, 3, 4770), state);
  state = step(state, 'resume', 15000);
  assert.equal(state.deadline, 22200);
  assert.equal(step(state, 'tick', 15003, { deadline: originalDeadline }), state);
  assert.equal(raw(state, 3, 14995), state);
  state = raw(state, 4, 15200);
  assert.equal(state.attempt.matches, 3, 'attempt count retains previous actual hits');
  assert.equal(state.attempt.streak.length, 1, 'streak restarts');
});

test('no camera after skip holds the next preparation; camera faults never increment the score', () => {
  let state = tick(start());
  state = step(state, 'pause', 4100, { reason: 'camera_error' });
  assert.equal(state.attempt.cameraFaults, 1);
  state = step(state, 'skip', 4200, { cameraReady: false });
  assert.equal(state.rounds[0].outcome, 'skipped');
  assert.equal(state.rounds[0].attempts[0].source, 'live_status');
  assert.equal(state.phase, 'paused');
  assert.equal(state.pause.remaining, CHALLENGE.prepareMs);
  assert.equal(challengeScore(state), 0);
});

test('skip, complete, replay, and early finish retain only the correct run history', () => {
  let state = settleMatch(tick(start()));
  state = step(state, 'next', 5300);
  for (let i = 1; i < 7; i++) {
    assert.equal(state.index, i);
    state = step(state, 'skip', 5500 + i);
  }
  assert.equal(state.phase, 'finished');
  assert.deepEqual(state.rounds.map(round => round.outcome), ['matched', ...Array(6).fill('skipped')]);
  assert.equal(challengeScore(state), 1);
  state = step(state, 'reset', 9000);
  assert.deepEqual(state, initialChallenge());
  state = step(state, 'start', 10000, { order: shuffledTargets(() => 0) });
  state = step(state, 'finish', 11000);
  assert.equal(state.finishedEarly, true);
  assert.deepEqual(state.rounds.map(round => round.outcome), ['ended', ...Array(6).fill(null)]);
  assert.equal(challengeScore(state), 0);
});

test('clock expires old visible data and a streak even with no further input', () => {
  let state = raw(tick(start()), 1, 4100);
  assert.equal(nextClockWake(state, 5001), 0);
  state = tick(state, 5601);
  assert.equal(state.attempt.streak.length, 0);
  state = tick(state, 5900);
  assert.deepEqual(state.current, { kind: 'stale' });
});

function snapshot(label = 3, first = .70, second = .20) {
  return { camera: true, status: 'ok', faces: [{ id: 1 }], metrics: { frameId: 5 }, smoothed: { label: 6 }, data: {
    frame_id: 5, captured_at: 1000, selected_box: [0, 0, .6, .6], selected_id: 1, input_preview: 'IGNORED',
    raw_prediction: { label, probabilities: CHALLENGE.targets.map(i => ({ label: i, probability: i === label ? first : i === 0 ? second : 0 })) },
  } };
}

test('adapter reads the actual RAW top class and returns metadata only; rejects expired and unrelated frames', () => {
  const s = snapshot();
  assert.deepEqual(readChallengeSignal(s, 1250), { kind: 'raw', label: 3, probability: .7, captured: 1000, frame: 5 });
  assert.equal(readChallengeSignal(s, 2800).kind, 'stale');
  assert.equal(readChallengeSignal(s, 999).kind, 'stale');
  assert.equal(readChallengeSignal({ ...s, metrics: { frameId: 4 } }, 1250).kind, 'stale');
  assert.equal(readChallengeSignal({ ...s, paused: true }, 1250).kind, 'waiting');
});

test('adapter distinguishes no face, multi-face, low quality, absent target and nearly tied RAW outputs', () => {
  const s = snapshot();
  assert.equal(readChallengeSignal({ ...s, status: 'no_face', faces: [] }, 1250).kind, 'no_face');
  assert.equal(readChallengeSignal({ ...s, status: 'low_quality' }, 1250).kind, 'low_quality');
  assert.equal(readChallengeSignal({ ...s, faces: [{ id: 2 }] }, 1250).kind, 'unclear');
  assert.equal(readChallengeSignal({ ...s, faces: [{ id: 1 }, { id: 2 }] }, 1250).kind, 'multiple');
  assert.equal(readChallengeSignal(snapshot(3, .49, .46), 1250).kind, 'close');
  assert.equal(readChallengeSignal(snapshot(3, .5, .46), 1250).kind, 'raw');
});
