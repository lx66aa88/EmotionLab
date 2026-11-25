import { CHALLENGE, challengeReducer, challengeScore, initialChallenge } from './challengeGame.js';

export const MATCH_POINTS = 100;
export const MAX_POINTS = CHALLENGE.targets.length * MATCH_POINTS;
export const roundPoints = round => round.outcome === 'matched' ? MATCH_POINTS : 0;
export const totalPoints = game => challengeScore(game) * MATCH_POINTS;

export function initialChallengeT72() {
  return { ...initialChallenge(), revision: 0 };
}

function applyRule(state, action) {
  const next = challengeReducer(state, action);
  if (next === state) return state;

  let rounds = next.rounds;
  const before = state.rounds[state.index];
  const after = rounds[state.index];
  if (before && after && after.attempts.length > before.attempts.length) {
    const { winningFrames, ...attempt } = after.attempts.at(-1);
    // The current deadline already incorporates any time spent paused.
    const matchMs = attempt.outcome === 'matched' ? CHALLENGE.playMs - (state.deadline - action.at) : null;
    const spanMs = winningFrames.length ? winningFrames.at(-1).captured - winningFrames[0].captured : null;
    const record = { ...attempt, matchMs, spanMs, frameIds: winningFrames.map(frame => frame.frame) };
    const updated = { ...after, attempts: [...before.attempts, record] };
    rounds = rounds.map((round, index) => index === state.index ? updated : round);
  }

  const changedWindow = next.phase !== state.phase || next.index !== state.index;
  return { ...next, rounds, revision: state.revision + Number(changedWindow) };
}

function catchUp(state, at) {
  if (state.deadline === null || at < state.deadline) return state;
  // Anchor the 8-second window to the scheduled end of preparation, even if
  // the browser wakes up late. Captures still start only when LIVE resumes.
  if (state.phase === 'prepare') {
    const deadline = state.deadline;
    state = applyRule(state, { type: 'tick', deadline, at: deadline });
  }
  if (state.phase === 'playing' && at >= state.deadline) {
    return applyRule(state, { type: 'tick', deadline: state.deadline, at });
  }
  return state;
}

export function challengeReducerT72(state, action) {
  const { type, at, revision, reason } = action;
  const interruption = type === 'interrupt';
  if (!Number.isFinite(at) || (!interruption && revision !== state.revision)) return state;

  const current = catchUp(state, at);
  if (type === 'tick') {
    return applyRule(current, { ...action, deadline: current.deadline });
  }
  // A click or response delivered after the deadline cannot replace a timeout.
  if (current.phase === 'resolved' && state.phase !== 'resolved' && type !== 'finish') return current;
  if (interruption && current.phase === 'paused' && reason !== current.pause.reason) {
    return {
      ...current,
      pause: { ...current.pause, reason },
      attempt: { ...current.attempt, cameraFaults: current.attempt.cameraFaults + Number(reason === 'camera_error') },
    };
  }
  return applyRule(current, interruption ? { type: 'pause', at, reason } : action);
}
