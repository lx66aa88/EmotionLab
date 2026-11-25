import { LABELS, STALE_MS } from './liveSession.js';
import { CHALLENGE } from './challengeGame.js';

// Project the accepted LIVE event to game metadata. Never retain an image,
// an EMA result, or a prediction from a different capture session here.
export function readChallengeSignal(snapshot, at) {
  if (!snapshot.camera || snapshot.paused) return { kind: 'waiting' };
  const { status, data, faces, metrics } = snapshot;
  if (status === 'backend_error') return { kind: 'service' };
  if (status === 'stale') return { kind: 'stale' };
  if (!['ok', 'no_face', 'target_lost', 'low_quality'].includes(status)) return { kind: 'waiting' };
  const { frame_id: frame, captured_at: captured } = data ?? {};
  if (!Number.isSafeInteger(frame) || frame < 1 || frame !== metrics?.frameId ||
      !Number.isFinite(captured) || captured < 0 || captured > at || at - captured >= STALE_MS) {
    return { kind: 'stale' };
  }
  const origin = { frame, captured };
  if (status === 'no_face') return { kind: 'no_face', ...origin };
  if (status === 'target_lost') return { kind: 'target_lost', ...origin };
  if (faces?.length > 1) return { kind: 'multiple', ...origin };
  if (status === 'low_quality') return { kind: 'low_quality', ...origin };
  if (faces?.length !== 1 || !data.selected_box || faces[0].id !== data.selected_id) {
    return { kind: 'unclear', ...origin };
  }

  const { label, probabilities } = data.raw_prediction ?? {};
  if (!Number.isInteger(label) || !LABELS[label] || !Array.isArray(probabilities) ||
      probabilities.length !== LABELS.length || probabilities.some((row, index) =>
        row?.label !== index || !Number.isFinite(row.probability) || row.probability < 0 || row.probability > 1)) {
    return { kind: 'unclear', ...origin };
  }
  const probability = probabilities[label].probability;
  const runnerUp = Math.max(...probabilities.filter(row => row.label !== label).map(row => row.probability));
  // An uncalibrated RAW score is a ranking, so require a small lead over second place.
  const kind = probability - runnerUp + Number.EPSILON >= CHALLENGE.lead ? 'raw' : 'close';
  return { kind, ...origin, label, probability };
}
