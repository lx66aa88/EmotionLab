const polar = (angle, radius, sweep, width, cx, cy, aspect = 1) => [
  cx + (Math.cos(angle) * radius - Math.sin(angle) * sweep) * aspect,
  cy + Math.sin(angle) * radius + Math.cos(angle) * sweep,
  width,
];

const pose = (x = 0, y = 0, rotation = 0, sx = 1, sy = 1) =>
  `translate(${x.toFixed(2)}px, ${y.toFixed(2)}px) rotate(${rotation.toFixed(2)}deg) scale(${sx}, ${sy})`;

function fault() {
  return Array.from({ length: 11 }, (_, i) => {
    const j = i - 5;
    const short = Math.abs(j);
    return {
      points: [
        [60 + short * 10 + j * 4, 318 + j * 9 - short * 3, 0.6],
        [178 + j * 6, 214 + j * 11, 14 + (i % 3) * 2],
        [232 + j * 8, 244 + j * 9, 12],
        [307 + j * 3, 144 + j * 12, 18],
        [366 + j * 6, 154 + j * 11, 14],
        [496 - short * 12 + j * 4, 59 + j * 8 + short * 5, 0.6],
      ],
      roundness: 0.17,
      bow: -0.36,
      origin: [273, 200],
      poses: [pose(j * -1.1, j * -1.2, j * -0.38), pose(j * 1.9, j * 2.15, j * 0.74), pose(j * -0.6, j * -0.45)],
      delay: i * 19,
    };
  });
}

function recoil() {
  return Array.from({ length: 11 }, (_, i) => {
    const j = i - 5;
    return {
      points: [
        [118 + j * 8, 149 + j * 6, 0.65],
        [184 + j * 8, 98 + j * 8, 13],
        [318 + j * 5, 83 + j * 9, 19],
        [415 + j * 10, 153 + j * 4, 18],
        [399 + j * 8, 261 + j * 7, 18],
        [298 + j * 3, 322 + j * 9, 18],
        [183 - j * 5, 289 + j * 8, 14],
        [157 + j * 2, 221 + j * 9, 8],
        [208 + j * 6, 202 + j * 6, 0.65],
      ],
      bow: 0.42,
      origin: [322, 206],
      poses: [pose(-3, j * 0.5, 2 + j * 0.35), pose(7 + j, -5, -6 + j * 0.85, 0.96, 0.9), pose(-2, 1, 1.6)],
      delay: i * 38,
    };
  });
}

function filament() {
  return Array.from({ length: 14 }, (_, i) => {
    const left = i < 7;
    const j = i % 7;
    const side = left ? -1 : 1;
    return {
      points: left ? [
        [277 + j * 4, 36 + j * 7, 0.4],
        [206 + j * 10, 117 - j * 2, 5.5],
        [143 + j * 13, 208 + j * 2, 8],
        [194 + j * 9, 285 - j * 3, 7],
        [281 - j * 6, 374 - j * 4, 0.45],
      ] : [
        [282 + j * 5, 36 + j * 5, 0.4],
        [327 + j * 10, 108 + j * 2, 5.5],
        [334 + j * 11, 191 - j * 4, 8],
        [304 + j * 9, 286 + j * 2, 6.2],
        [242 + j * 6, 361 + j * 3, 0.45],
      ],
      bow: 0.53,
      origin: [278, 201],
      poses: [pose(side * 3, -j, side * 2, 0.97, 1.04), pose(side * -4, j * 0.9, side * -3, 1.04, 0.97), pose(side * 2, -1, side * 1.4)],
      delay: j * 46 + (left ? 0 : 130),
    };
  });
}

function bloom() {
  const fanOrder = [0, 12, 1, 11, 2, 10, 3, 9, 4, 8, 5, 7, 6];
  return fanOrder.map(i => {
    const j = i - 6;
    const angle = -2.985 + i * 0.229;
    const reach = 267 - Math.abs(j) * 7.5 + (i % 2) * 8;
    return {
      points: [
        polar(angle, 13 + Math.abs(j) * 1.8, j * 2.0, 1, 281, 327),
        polar(angle, 66, -3, 14, 281, 327),
        polar(angle, reach * 0.49, -14, 22, 281, 327),
        polar(angle, reach * 0.76, -11, 28 + (i % 3) * 2, 281, 327),
        polar(angle, reach * 0.94, 4, 13, 281, 327),
        polar(angle, reach, 21, 0.7, 281, 327),
      ],
      bow: 0.58,
      origin: [281, 327],
      poses: [pose(0, -1, j * 0.58, 1.035, 1.04), pose(0, -4, j * 0.91, 1.04, 1.06), pose(0, 1, j * -0.22, 0.986, 0.98)],
      delay: Math.abs(j) * 37,
    };
  });
}

function fall() {
  return Array.from({ length: 11 }, (_, i) => {
    const j = i - 5;
    return {
      points: [
        [96 + j * 11, 151 - j * 5, 0.55],
        [178 + j * 12, 81 + j * 5, 13],
        [279 + j * 16, 115 + j * 8, 22],
        [321 + j * 14, 199 + j * 7, 19],
        [284 + j * 10, 286 + j * 5, 12],
        [261 + j * 9 + j * j * 0.66, 368 - Math.abs(j) * 9 + j * 2, 0.55],
      ],
      bow: -0.48,
      origin: [221, 95],
      poses: [pose(-2, 2, -1 - j * 0.27, 0.995, 1.018), pose(j * 0.8, 8 + Math.abs(j), -2 + j * 0.2, 0.975, 1.045), pose(1, 5, 0.8, 0.99, 1.023)],
      delay: i * 55,
    };
  });
}

function burst() {
  const lengths = [154, 178, 134, 186, 168, 137, 181, 159, 177, 143, 176];
  return lengths.map((reach, i) => {
    const angle = i * Math.PI * 2 / lengths.length - 0.2 + (i % 3) * 0.036;
    const center = [278, 207];
    const [x, y] = [Math.cos(angle), Math.sin(angle)];
    const width = i % 2 ? 20 : 15;
    return {
      points: [
        polar(angle, 45 + (i % 3) * 3, 8, 0.5, ...center, 1.16),
        polar(angle, 72, -4, 12, ...center, 1.16),
        polar(angle, reach * 0.64, -17, width, ...center, 1.16),
        polar(angle, reach * 0.86, -13, 12, ...center, 1.16),
        polar(angle, reach, 1, 0.5, ...center, 1.16),
      ],
      bow: 0.66,
      origin: center,
      poses: [pose(x * -5, y * -5, -2, 0.965, 0.965), pose(x * 13, y * 13, 3.1, 1.035, 1.035), pose(x * 4, y * 4, 1.1, 1.014, 1.014)],
      delay: (i % 3) * 21,
    };
  });
}

function plane() {
  return Array.from({ length: 7 }, (_, index) => {
    const i = 6 - index;
    const reach = 209 - Math.abs(3 - i) * 11;
    const baseline = 136 + i * 24;
    return {
      points: Array.from({ length: 16 }, (_, j) => {
        const theta = j * Math.PI / 8;
        return [280 + Math.cos(theta) * reach, baseline + Math.sin(theta) * (39 - i * 0.8), 5.5 + (1 + Math.sin(theta)) * 3.2];
      }),
      closed: true,
      bow: 0.35,
      origin: [280, baseline],
      poses: [pose(0, (i - 3) * 1.1, 0, 1.005, 1.03), pose(0, (i - 3) * 1.8, 0, 1.012, 1.045), pose(0, (i - 3) * -0.64, 0, 0.994, 0.986)],
      delay: i * 48,
    };
  });
}

// The index is the frozen EmotionLab model label. Palette entries run from shadow to specular light.
export const SIGNALS = [
  {
    name: 'Angry', zh: '愤怒', form: 'Fault', formZh: '断层', motion: 'fault', duration: 4200,
    accent: '#ff7258', metal: ['#271013', '#6f1d25', '#dd4f39', '#ff9a73', '#fff1d9'],
    note: '棱面沿斜轴压紧，张力穿过错位的断口，再逐层释放。', ribbons: fault,
  },
  {
    name: 'Disgust', zh: '厌恶', form: 'Recoil', formZh: '回折', motion: 'recoil', duration: 5650,
    accent: '#bcc766', metal: ['#171b0c', '#45471c', '#899341', '#d0d77a', '#fff6c5'],
    note: '偏心的卷层向内收紧，弧口始终留出一块空隙。', ribbons: recoil,
  },
  {
    name: 'Fear', zh: '恐惧', form: 'Filament', formZh: '牵丝', motion: 'filament', duration: 3820,
    accent: '#c3adff', metal: ['#1b132b', '#423364', '#8e73c1', '#c0a9f8', '#f7eaff'],
    note: '两束细带隔空牵引，细微的错拍沿长轴传递。', ribbons: filament,
  },
  {
    name: 'Happy', zh: '快乐', form: 'Bloom', formZh: '舒展', motion: 'bloom', duration: 5280,
    accent: '#ffc66a', metal: ['#301c0c', '#845218', '#dca143', '#facc7d', '#fff5d1'],
    note: '弧面从低处向两侧舒展，光沿扇缘展开，再缓慢归拢。', ribbons: bloom,
  },
  {
    name: 'Sad', zh: '悲伤', form: 'Fall', formZh: '沉降', motion: 'fall', duration: 7050,
    accent: '#8bb3ed', metal: ['#111b2d', '#273c5d', '#557cae', '#94b7df', '#e5f3ff'],
    note: '带面自高处垂落，重量顺着弯曲的长尾慢慢转移。', ribbons: fall,
  },
  {
    name: 'Surprise', zh: '惊喜', form: 'Burst', formZh: '迸开', motion: 'burst', duration: 4680,
    accent: '#8ce9d9', metal: ['#0c2222', '#215956', '#4da99f', '#9ce7d7', '#ecfff4'],
    note: '尖叶由空心向外迸开，扩张迅速，回落时保留环状间隔。', ribbons: burst,
  },
  {
    name: 'Neutral', zh: '中立', form: 'Plane', formZh: '基面', motion: 'plane', duration: 8360,
    accent: '#c7d1cb', metal: ['#151b19', '#424d49', '#7f8d88', '#c6d0cb', '#f5f9ed'],
    note: '平行的环层保持水平，只沿纵轴轻微调节间距。', ribbons: plane,
  },
];

export function signalFor(category) {
  return Number.isInteger(category) ? SIGNALS[category] : undefined;
}
