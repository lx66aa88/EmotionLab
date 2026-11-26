import { signalFor } from './signals.js';

export const VIEW_BOX = '0 0 560 416';

function curve(points, closed, roundness) {
  const segmentCount = closed ? points.length : points.length - 1;
  const at = index => closed
    ? points[(index + points.length) % points.length]
    : points[Math.max(0, Math.min(points.length - 1, index))];

  return t => {
    const position = (closed ? (t + 1) % 1 : Math.max(0, Math.min(1, t))) * segmentCount;
    const segment = Math.min(segmentCount - 1, Math.floor(position));
    const s = position - segment;
    const s2 = s * s;
    const s3 = s2 * s;
    const a = at(segment - 1);
    const b = at(segment);
    const c = at(segment + 1);
    const d = at(segment + 2);
    const blend = axis => (2 * s3 - 3 * s2 + 1) * b[axis]
      + (s3 - 2 * s2 + s) * (c[axis] - a[axis]) * roundness
      + (-2 * s3 + 3 * s2) * c[axis]
      + (s3 - s2) * (d[axis] - b[axis]) * roundness;
    return [blend(0), blend(1), b[2] + (c[2] - b[2]) * (3 * s2 - 2 * s3)];
  };
}

const xy = (x, y) => `${x.toFixed(2)},${y.toFixed(2)}`;
const line = coordinates => `M${coordinates.join('L')}`;

export function buildRibbon({ points, closed = false, roundness = 0.44, bow = 0, ...motion }) {
  const sample = curve(points, closed, roundness);
  const steps = (closed ? points.length : points.length - 1) * (closed ? 4 : 8);

  // A width and a longitudinal bow define each cross-section of the same lofted surface.
  const rows = Array.from({ length: steps + 1 }, (_, i) => {
    const t = i / steps;
    const [x, y, width] = sample(t);
    const a = sample(t - 0.001);
    const b = sample(t + 0.001);
    const magnitude = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
    const tx = (b[0] - a[0]) / magnitude;
    const ty = (b[1] - a[1]) / magnitude;
    return u => {
      const roll = bow * width * (1 - u * u);
      return xy(x - ty * width * u + tx * roll, y + tx * width * u + ty * roll);
    };
  });

  const contour = u => rows.map(row => row(u));
  const band = (lower, upper) => {
    const edge = contour(lower);
    const back = contour(upper).reverse();
    return closed ? `${line(edge)}Z${line(back)}Z` : `${line([...edge, ...back])}Z`;
  };

  return {
    ...motion,
    silhouette: band(-1, 1),
    darkFace: band(-1, -0.37),
    lightFace: band(0.04, 0.62),
    edge: line(contour(0.92)),
    lines: [-0.79, -0.53, -0.21, 0.15, 0.36, 0.68, 0.83].map(u => line(contour(u))).join(''),
    cuts: rows.slice(2, -1).filter((_, i) => i % 2 === 0)
      .map(row => line([-0.94, -0.54, 0, 0.54, 0.94].map(row))).join(''),
  };
}

const catalog = new Map();

export function geometryFor(category) {
  const signal = signalFor(category);
  if (!signal) return [];
  if (!catalog.has(category)) catalog.set(category, signal.ribbons().map(buildRibbon));
  return catalog.get(category);
}
