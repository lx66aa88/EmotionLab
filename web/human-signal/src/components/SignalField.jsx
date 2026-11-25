import { useEffect, useRef } from 'react';

/** 2,304 samples. Idle is explicitly conceptual; uploaded pixels are exact. */
export default function SignalField({ pixels, light, matrix }) {
  const canvas = useRef(null);
  const frame = useRef(null);
  const pointer = useRef(null);
  useEffect(() => {
    const node = canvas.current;
    const ctx = node.getContext('2d', { alpha: true });
    const draw = () => {
      ctx.clearRect(0, 0, 480, 480);
      for (let y = 0; y < 48; y++) for (let x = 0; x < 48; x++) {
        if (pixels) {
          const value = pixels[y * 48 + x];
          ctx.fillStyle = `rgb(${value},${value},${value})`;
          ctx.fillRect(x * 10, y * 10, matrix ? 8.6 : 10, matrix ? 8.6 : 10);
          continue;
        }
        const dx = (x - 23.5) / 21;
        const dy = (y - 23.5) / 21;
        const angle = Math.atan2(dy, dx);
        const radius = Math.hypot(dx * 0.92, dy * 1.12);
        const rim = 0.62 + Math.sin(angle * 3 + 0.7) * 0.075;
        const ribbon = Math.exp(-Math.pow((radius - rim) / 0.19, 2));
        const striation = 0.25 + 0.75 * Math.pow(Math.cos(radius * 43 + angle * 2.4), 2);
        const lightness = 0.36 + 0.64 * ((dx - dy + 2) / 4);
        let intensity = ribbon * striation * lightness;
        if (pointer.current) intensity += 0.2 * Math.exp(-Math.hypot(x - pointer.current[0], y - pointer.current[1]) / 5);
        intensity = Math.min(1, intensity);
        if (intensity < 0.035) continue;
        const a = Math.round(intensity * (light ? 135 : 221));
        ctx.fillStyle = light ? `rgba(35,55,35,${intensity})` : `rgb(${Math.round(a * 0.91)},${a},${Math.round(a * 0.79)})`;
        const size = 2.1 + intensity * 5.5;
        ctx.fillRect(x * 10 + (10 - size) / 2, y * 10 + (10 - size) / 2, size, size);
      }
    };
    draw();
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const move = (event) => {
      if (pixels || reduced) return;
      const rect = node.getBoundingClientRect();
      pointer.current = [(event.clientX - rect.left) / rect.width * 48, (event.clientY - rect.top) / rect.height * 48];
      if (frame.current) cancelAnimationFrame(frame.current);
      frame.current = requestAnimationFrame(draw);
    };
    const leave = () => { pointer.current = null; draw(); };
    node.addEventListener('pointermove', move);
    node.addEventListener('pointerleave', leave);
    return () => { cancelAnimationFrame(frame.current); node.removeEventListener('pointermove', move); node.removeEventListener('pointerleave', leave); };
  }, [pixels, light, matrix]);
  return <canvas ref={canvas} width="480" height="480" role="img" aria-label={pixels ? '真实 48 乘 48 灰度像素矩阵，亮度直接对应原始像素' : '原创概念采样场，48 乘 48 格点，等待输入；这不是预测结果'}/>;
}
