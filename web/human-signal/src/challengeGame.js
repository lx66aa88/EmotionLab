import { LABELS, STALE_MS } from './liveSession.js';

export const CHALLENGE = Object.freeze({
  prepareMs: 3000, playMs: 8000, matches: 3, spanMs: 500, maxGapMs: 1500, lead: .04,
  targets: Object.freeze(LABELS.map((_, label) => label)),
});

const clockIsRunning = state => state.phase === 'prepare' || state.phase === 'playing';
const seconds = ms => Math.ceil(Math.max(0, ms) / 1000);
const roundOf = state => state.rounds[state.index];

export function shuffledTargets(random = Math.random) {
  const targets = [...CHALLENGE.targets];
  for (let i = targets.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [targets[i], targets[j]] = [targets[j], targets[i]];
  }
  return targets;
}

export function initialChallenge() {
  return {
    phase: 'idle', rounds: [], index: 0, attempt: null,
    since: null, deadline: null, seconds: 0, current: null,
    pause: null, finishedEarly: false,
  };
}

const newAttempt = () => ({
  judged: 0, matches: 0, noFace: 0, lost: 0, unclear: 0,
  stale: 0, service: 0, cameraFaults: 0,
  lastFrame: 0, lastCapture: -1, streak: [], winningFrames: [],
});

function openClock(state, phase, at, duration) {
  return { ...state, phase, since: at, deadline: at + duration, seconds: seconds(duration), current: null, pause: null };
}

function prepare(state, at) {
  return openClock({ ...state, attempt: newAttempt() }, 'prepare', at, CHALLENGE.prepareMs);
}

function updateRound(state, next) {
  return { ...state, rounds: state.rounds.map((round, i) => i === state.index ? next : round) };
}

function settle(state, outcome) {
  const round = roundOf(state);
  const { streak, lastFrame, lastCapture, ...evidence } = state.attempt;
  const source = evidence.judged ? 'live_raw'
    : evidence.noFace || evidence.lost || evidence.unclear || evidence.stale || evidence.service || evidence.cameraFaults
      ? 'live_status' : 'none';
  return {
    ...updateRound(state, { ...round, outcome, attempts: [...round.attempts, { ...evidence, outcome, source }] }),
    phase: 'resolved', attempt: null, since: null, deadline: null, seconds: 0, current: null, pause: null,
  };
}

function timeoutOutcome(attempt) {
  if (attempt.judged) return 'miss';
  if (attempt.unclear || attempt.stale) return 'unclear';
  if (attempt.noFace || attempt.lost) return 'no_face';
  return attempt.service ? 'service' : 'unclear';
}

function advanceClock(state, at) {
  if (at >= state.deadline) {
    if (state.phase === 'prepare') return openClock(state, 'playing', at, CHALLENGE.playMs);
    return settle(state, timeoutOutcome(state.attempt));
  }
  const current = state.current?.captured !== undefined && at >= state.current.captured + STALE_MS
    ? { kind: 'stale' } : state.current;
  const latest = state.attempt.streak.at(-1);
  const attempt = latest && at > latest.captured + CHALLENGE.maxGapMs
    ? { ...state.attempt, streak: [] } : state.attempt;
  const remaining = seconds(state.deadline - at);
  return remaining !== state.seconds || current !== state.current || attempt !== state.attempt
    ? { ...state, seconds: remaining, current, attempt } : state;
}

function observe(state, signal, at) {
  if (state.phase !== 'playing' || at < state.since) return state;
  if (at >= state.deadline) return advanceClock(state, at);
  const prior = state.attempt;
  const framed = signal.frame !== undefined;
  if (signal.kind === 'raw' && !framed) return state;
  if (framed && (!Number.isSafeInteger(signal.frame) || !Number.isFinite(signal.captured) ||
      signal.frame <= prior.lastFrame || signal.captured <= prior.lastCapture || signal.captured < state.since ||
      signal.captured >= state.deadline || signal.captured > at || at - signal.captured >= STALE_MS)) return state;
  // "waiting" clears a streak during relocalization; a stale notice is not a new frame.
  if (!framed && state.current?.kind === signal.kind) return state;
  const hit = signal.kind === 'raw' && signal.label === roundOf(state).label;
  const previousHit = prior.streak.at(-1);
  const consecutive = previousHit && signal.captured > previousHit.captured &&
    signal.captured - previousHit.captured <= CHALLENGE.maxGapMs;
  const streak = hit ? [...(consecutive ? prior.streak : []), { frame: signal.frame, captured: signal.captured }] : [];
  const stable = streak.length >= CHALLENGE.matches && streak.at(-1).captured - streak[0].captured >= CHALLENGE.spanMs;
  const attempt = {
    ...prior, lastFrame: framed ? signal.frame : prior.lastFrame,
    lastCapture: framed ? signal.captured : prior.lastCapture, streak,
    judged: prior.judged + Number(signal.kind === 'raw'),
    matches: prior.matches + Number(hit),
    noFace: prior.noFace + Number(signal.kind === 'no_face'),
    lost: prior.lost + Number(signal.kind === 'target_lost'),
    unclear: prior.unclear + Number(['close', 'multiple', 'low_quality', 'unclear'].includes(signal.kind)),
    stale: prior.stale + Number(signal.kind === 'stale'),
    service: prior.service + Number(signal.kind === 'service'),
    winningFrames: stable ? streak : prior.winningFrames,
  };
  const next = { ...state, current: signal, attempt };
  return stable ? settle(next, 'matched') : next;
}

function goNext(state, at, cameraReady) {
  if (state.index + 1 === state.rounds.length) return { ...state, phase: 'finished' };
  const next = prepare({ ...state, index: state.index + 1 }, at);
  if (cameraReady !== false) return next;
  return {
    ...next, phase: 'paused', since: null, deadline: null,
    pause: { from: 'prepare', remaining: CHALLENGE.prepareMs, reason: 'camera_closed' },
  };
}

export function challengeReducer(state, action) {
  const { type, at } = action;
  switch (type) {
    case 'start': {
      const { order } = action;
      if (state.phase !== 'idle' || !Array.isArray(order) || order.length !== CHALLENGE.targets.length ||
          !CHALLENGE.targets.every(label => order.includes(label))) return state;
      return prepare({ ...initialChallenge(), rounds: order.map(label => ({ label, outcome: null, attempts: [] })) }, at);
    }
    case 'tick':
      return clockIsRunning(state) && state.deadline === action.deadline ? advanceClock(state, at) : state;
    case 'signal':
      return observe(state, action.signal, at);
    case 'pause': {
      if (!clockIsRunning(state)) return state;
      const next = advanceClock(state, at);
      if (!clockIsRunning(next)) return next;
      return {
        ...next, phase: 'paused', since: null, deadline: null, current: null,
        pause: { from: next.phase, remaining: Math.max(0, next.deadline - at), reason: action.reason },
        attempt: { ...next.attempt, streak: [], cameraFaults: next.attempt.cameraFaults + Number(action.reason === 'camera_error') },
      };
    }
    case 'resume':
      return state.phase === 'paused' ? openClock(state, state.pause.from, at, state.pause.remaining) : state;
    case 'retry':
      return state.phase === 'resolved' && roundOf(state).outcome !== 'matched'
        ? prepare(updateRound(state, { ...roundOf(state), outcome: null }), at) : state;
    case 'next':
      return state.phase === 'resolved' ? goNext(state, at, action.cameraReady) : state;
    case 'skip': {
      if (state.attempt) return goNext(settle(state, 'skipped'), at, action.cameraReady);
      const round = roundOf(state);
      return state.phase === 'resolved' && round.outcome !== 'matched'
        ? goNext(updateRound(state, { ...round, outcome: 'skipped' }), at, action.cameraReady) : state;
    }
    case 'finish': {
      if (state.phase === 'idle' || state.phase === 'finished') return state;
      const next = state.attempt ? settle(state, 'ended') : state;
      return { ...next, phase: 'finished', finishedEarly: next.rounds.some(round => !round.outcome || round.outcome === 'ended') };
    }
    case 'reset':
      return state.phase === 'finished' ? initialChallenge() : state;
    default:
      return state;
  }
}

export function nextClockWake(state, now) {
  if (!clockIsRunning(state)) return null;
  const until = state.deadline - now;
  if (until <= 0 || seconds(until) !== state.seconds) return 0;
  const step = until - (seconds(until) - 1) * 1000;
  const captured = state.attempt.streak.at(-1)?.captured;
  const breakAt = captured === undefined ? Infinity : captured + CHALLENGE.maxGapMs - now + 1;
  const expireAt = state.current?.captured === undefined ? Infinity : state.current.captured + STALE_MS - now;
  return Math.max(1, Math.min(step, breakAt, expireAt));
}

export const challengeScore = state => state.rounds.filter(round => round.outcome === 'matched').length;
