import { signalFor } from "../../seven-signals/signals.js";

// One extra accepted frame for near ties only. This never edits the EMA distribution.
export const CLOSE_LEAD = 0.04;

export function updateSignalPresentation(previous, state) {
  const prediction = state.smoothed;
  const frameId = state.metrics?.frameId;
  if (
    state.status !== "ok" ||
    !signalFor(prediction?.label) ||
    !Number.isSafeInteger(frameId)
  )
    return null;
  if (previous && frameId <= previous.frameId) return previous;

  const winner = prediction.label;
  if (
    !previous ||
    previous.category === winner ||
    previous.challenger === winner
  ) {
    return { category: winner, frameId, challenger: null };
  }

  const probabilities = prediction.probabilities;
  const lead =
    probabilities[winner].probability -
    probabilities[previous.category].probability;
  return lead >= CLOSE_LEAD
    ? { category: winner, frameId, challenger: null }
    : { category: previous.category, frameId, challenger: winner };
}
