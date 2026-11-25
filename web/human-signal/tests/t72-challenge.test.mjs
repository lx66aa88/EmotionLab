import assert from 'node:assert/strict';
import test from 'node:test';
import { CHALLENGE } from '../src/challengeGame.js';
import { challengeReducerT72, initialChallengeT72, MAX_POINTS, roundPoints, totalPoints } from '../src/challengeGameT72.js';

const act = (state, type, at, fields) =>
  challengeReducerT72(state, { type, at, revision: state.revision, ...fields });
const open = () => act(initialChallengeT72(), 'start', 1000, { order: CHALLENGE.targets });
const tick = (state, at = state.deadline) => act(state, 'tick', at);
const round = state => state.rounds[state.index];
const read = (state, signal, at, revision) =>
  act(state, 'signal', at, { signal, revision: revision ?? state.revision });
const raw = (state, frame, captured, label = round(state).label, at = captured + 70) =>
  read(state, { kind: 'raw', frame, captured, label, probability: .63 }, at);

test('seven stable matches yield exactly 700 points, with an independent elapsed time per round', () => {
  let state = open();
  for (const label of CHALLENGE.targets) {
    state = tick(state);
    const begins = state.since;
    const playing = state.revision;
    for (let hit = 0; hit < 3; hit++) state = raw(state, 3 * label + hit + 1, begins + 80 + 250 * hit);
    assert.equal(round(state).label, label);
    assert.equal(round(state).outcome, 'matched');
    assert.equal(roundPoints(round(state)), 100);
    assert.equal(totalPoints(state), (label + 1) * 100);
    const [result] = round(state).attempts;
    assert.equal(result.matchMs, 650);
    assert.equal(result.spanMs, 500);
    assert.equal(result.source, 'live_raw');
    assert.deepEqual(result.frameIds, [1, 2, 3].map(id => id + 3 * label));
    assert.ok(!('winningFrames' in result) && !('probability' in result) && !('captured' in result));
    assert.equal(act(state, 'signal', begins + 660, { revision: playing }), state);
    assert.equal(act(state, 'retry', begins + 660), state);
    state = act(state, 'next', begins + 700);
  }
  assert.equal(state.phase, 'finished');
  assert.equal(state.finishedEarly, false);
  assert.equal(totalPoints(state), MAX_POINTS);
  assert.equal(MAX_POINTS, 700);
});

test('a late browser wake uses the original boundary and can cross both windows', () => {
  const preparing = open();
  const playing = tick(preparing, 4750);
  assert.equal(playing.since, 4000);
  assert.equal(playing.deadline, 12000);
  assert.equal(tick(preparing, 5150).seconds, 7);
  const tooLate = tick(preparing, 16000);
  assert.equal(tooLate.phase, 'resolved');
  assert.equal(round(tooLate).attempts[0].source, 'none');
  assert.equal(round(tooLate).outcome, 'unclear');
  assert.equal(act(playing, 'skip', 12000).phase, 'resolved');
  assert.equal(totalPoints(tooLate), 0);
});

test('preparation pause and play pause each preserve their own remaining budget', () => {
  let state = act(open(), 'pause', 2100, { reason: 'manual' });
  assert.deepEqual(state.pause, { from: 'prepare', remaining: 1900, reason: 'manual' });
  state = act(state, 'resume', 10100);
  assert.equal(state.deadline, 12000);
  state = tick(state, 12300);
  assert.equal(state.since, 12000);
  assert.equal(state.deadline, 20000);
  state = raw(state, 1, 12360);
  const oldWindow = state.revision;
  state = act(state, 'pause', 12850, { reason: 'manual' });
  assert.equal(state.pause.remaining, 7150);
  assert.equal(state.attempt.streak.length, 0);
  state = act(state, 'resume', 30100);
  assert.equal(state.deadline, 37250);
  assert.equal(act(state, 'tick', 30110, { revision: oldWindow }), state);
  assert.equal(raw(state, 2, 12800, 0, 30110), state);
  for (const [frame, time] of [[2, 30200], [3, 30450], [4, 30700]]) state = raw(state, frame, time);
  assert.equal(round(state).attempts[0].matchMs, 1520);
  assert.equal(round(state).attempts[0].matches, 4);
});

test('a miss and a retry are distinct attempts; a skipped no-face round retains its evidence', () => {
  let state = tick(open());
  state = tick(raw(state, 1, 4510, 3));
  assert.equal(round(state).outcome, 'miss');
  assert.equal(round(state).attempts[0].matchMs, null);
  assert.equal(totalPoints(state), 0);
  const oldWindow = state.revision;
  state = act(state, 'retry', 12200);
  assert.equal(act(state, 'retry', 12201, { revision: oldWindow }), state);
  state = tick(state);
  for (const [frame, time] of [[2, 15300], [3, 15550], [4, 15800]]) state = raw(state, frame, time);
  assert.deepEqual(round(state).attempts.map(attempt => attempt.outcome), ['miss', 'matched']);
  state = tick(act(state, 'next', 16000));
  state = read(state, { kind: 'no_face', frame: 5, captured: 19100 }, 19140);
  state = tick(state);
  assert.equal(round(state).outcome, 'no_face');
  state = act(state, 'skip', 27100);
  assert.equal(state.rounds[1].outcome, 'skipped');
  assert.equal(state.rounds[1].attempts[0].noFace, 1);
  assert.equal(state.rounds[1].attempts[0].outcome, 'no_face');
  assert.equal(totalPoints(state), 100);
});

test('deadline, freshness, scope, and three-hit timing apply before awarding any points', () => {
  let state = tick(open());
  state = raw(raw(state, 1, 4100), 2, 4230);
  const fromFirst = state.revision;
  state = raw(state, 3, 4350);
  assert.equal(totalPoints(state), 0, 'three frames alone are insufficient');
  assert.equal(raw(state, 4, 4500, 0, 6300), state, 'expired before reaching the reducer');
  state = act(state, 'skip', 4800, { cameraReady: true });
  assert.equal(act(state, 'skip', 4801, { revision: fromFirst }), state);
  state = tick(state);
  assert.equal(state.index, 1);
  assert.equal(read(state, { kind: 'raw', frame: 4, captured: state.since, label: 1 }, state.since + 50, fromFirst), state);
  assert.equal(raw(state, 4, state.since - 1), state);
  state = raw(raw(state, 5, state.deadline - 650), 6, state.deadline - 400);
  state = raw(state, 7, state.deadline - 150, 1, state.deadline);
  assert.equal(round(state).outcome, 'miss');
  assert.equal(totalPoints(state), 0);
});

test('camera interruptions, rapid finish and replay retain only the intended run', () => {
  let state = tick(open());
  state = act(state, 'pause', 5100, { reason: 'manual' });
  state = act(state, 'interrupt', 5101, { reason: 'camera_error' });
  assert.equal(state.attempt.cameraFaults, 1);
  assert.equal(act(state, 'interrupt', 5102, { reason: 'camera_error' }), state);
  const paused = state.revision;
  state = act(state, 'skip', 5200, { cameraReady: false });
  assert.equal(state.pause.from, 'prepare');
  assert.equal(state.pause.remaining, CHALLENGE.prepareMs);
  assert.equal(act(state, 'skip', 5201, { revision: paused }), state);
  state = act(state, 'finish', 5300);
  assert.equal(state.finishedEarly, true);
  assert.deepEqual(state.rounds.map(round => round.outcome), ['skipped', 'ended', null, null, null, null, null]);
  assert.equal(act(state, 'finish', 5301), state);
  const finished = state.revision;
  state = act(state, 'reset', 5400);
  assert.equal(state.rounds.length, 0);
  assert.equal(totalPoints(state), 0);
  state = act(state, 'start', 5500, { order: CHALLENGE.targets });
  assert.equal(act(state, 'finish', 5501, { revision: finished }), state);
});
