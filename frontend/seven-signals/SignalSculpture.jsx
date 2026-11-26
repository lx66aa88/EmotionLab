import { memo, useEffect, useId, useLayoutEffect, useRef, useState, useSyncExternalStore } from 'react';
import { geometryFor, VIEW_BOX } from './geometry.js';
import { signalFor } from './signals.js';
import './sculpture.css';

const motionQuery = '(prefers-reduced-motion: reduce)';
const readReducedMotion = () => window.matchMedia(motionQuery).matches;
const subscribeReducedMotion = listener => {
  const media = window.matchMedia(motionQuery);
  media.addEventListener('change', listener);
  return () => media.removeEventListener('change', listener);
};

export function useReducedMotion() {
  return useSyncExternalStore(subscribeReducedMotion, readReducedMotion, () => false);
}

function useStageVisibility(element) {
  const [inView, setInView] = useState(true);
  const [visible, setVisible] = useState(() => typeof document === 'undefined' || !document.hidden);
  useEffect(() => {
    const observer = typeof IntersectionObserver === 'function'
      ? new IntersectionObserver(([entry]) => setInView(entry.isIntersecting))
      : null;
    observer?.observe(element.current);
    const update = () => setVisible(!document.hidden);
    document.addEventListener('visibilitychange', update);
    return () => {
      observer?.disconnect();
      document.removeEventListener('visibilitychange', update);
    };
  }, [element]);
  return inView && visible;
}

function Material({ id, metal }) {
  const [dark, shadow, body, edge, white] = metal;
  return <defs>
    <linearGradient id={`${id}-body`} x1="18%" y1="0%" x2="78%" y2="100%">
      <stop stopColor={shadow}/><stop offset=".23" stopColor={edge}/>
      <stop offset=".42" stopColor={body}/><stop offset=".67" stopColor={dark}/>
      <stop offset=".87" stopColor={body}/><stop offset="1" stopColor={shadow}/>
    </linearGradient>
    <linearGradient id={`${id}-shadow`} x1="0%" y1="0%" x2="100%" y2="90%">
      <stop stopColor={dark}/><stop offset=".29" stopColor={shadow}/>
      <stop offset=".55" stopColor={dark}/><stop offset="1" stopColor={body}/>
    </linearGradient>
    <linearGradient id={`${id}-reflection`} x1="12%" y1="83%" x2="87%" y2="9%">
      <stop stopColor={shadow}/><stop offset=".19" stopColor={body}/>
      <stop offset=".39" stopColor={white}/><stop offset=".47" stopColor={edge}/>
      <stop offset=".66" stopColor={shadow}/><stop offset=".82" stopColor={edge}/>
      <stop offset="1" stopColor={body}/>
    </linearGradient>
    <linearGradient id={`${id}-rim`} x1="2%" y1="96%" x2="100%" y2="10%">
      <stop stopColor={body}/><stop offset=".23" stopColor={white}/>
      <stop offset=".52" stopColor={edge}/><stop offset=".74" stopColor={body}/>
      <stop offset=".94" stopColor={white}/>
    </linearGradient>
  </defs>;
}

const Surface = memo(function Surface({ category, low }) {
  const id = useId();
  const signal = signalFor(category);
  const [dark, , , edge, white] = signal.metal;
  const paint = role => `url(#${id}-${role})`;
  return <svg className="ss-surface" viewBox={VIEW_BOX} aria-hidden="true" focusable="false"
    style={{ '--ss-profile': `ss-${signal.motion}`, '--ss-duration': `${signal.duration}ms` }}>
    <Material id={id} metal={signal.metal}/>
    {geometryFor(category).map((ribbon, i) => {
      const [first, peak, last] = ribbon.poses;
      const [x, y] = ribbon.origin;
      return <g key={i} className="ss-ribbon" fillRule="evenodd" style={{
        '--ss-first': first, '--ss-peak': peak, '--ss-last': last,
        '--ss-delay': `${ribbon.delay}ms`, transformOrigin: `${x}px ${y}px`,
      }}>
        <path d={ribbon.silhouette} fill={dark} transform="translate(2 3.5)"/>
        <path d={ribbon.silhouette} fill={paint('body')} stroke={edge} strokeOpacity=".51" strokeWidth=".52"/>
        <path d={ribbon.darkFace} fill={paint('shadow')} opacity=".86"/>
        <path d={ribbon.lightFace} fill={paint('reflection')} opacity=".8"/>
        {!low && <g fill="none">
          <path d={ribbon.cuts} stroke={white} strokeWidth=".37" opacity=".32"/>
          <path d={ribbon.lines} stroke={dark} strokeWidth=".54" opacity=".64"/>
        </g>}
        <path d={ribbon.edge} stroke={paint('rim')} strokeWidth=".86" fill="none"/>
      </g>;
    })}
  </svg>;
});

export const SignalSilhouette = memo(function SignalSilhouette({ category }) {
  return <svg viewBox={VIEW_BOX} aria-hidden="true" focusable="false" className="ss-silhouette">
    {geometryFor(category).map((ribbon, i) => <path key={i} d={ribbon.silhouette}
      fill="currentColor" fillRule="evenodd" stroke="var(--silhouette-ground, #111411)" strokeWidth="2.7"/>) }
  </svg>;
});

const sourceLabel = { preview: '设计预览', prediction: '模型预测', target: '目标表情' };

/** Category is a frozen model index, or null for an empty signal. Confidence is a fraction from the caller. */
export function SignalSculpture({ category, source = 'preview', confidence, playback = 'playing',
  motion = 'system', quality = 'full', className = '' }) {
  const signal = signalFor(category);
  const index = signal ? category : null;
  const stack = useRef(null);
  const generation = useRef(0);
  const reducedMotion = useReducedMotion();
  const visible = useStageVisibility(stack);
  const staticPose = reducedMotion || motion === 'reduced' || quality === 'low';
  const running = !staticPose && playback === 'playing' && visible;
  const [scene, setScene] = useState(() => ({ current: { category: index, key: 0 }, exit: null, entering: false }));

  useLayoutEffect(() => {
    const canTransition = running && index !== null && typeof Element.prototype.animate === 'function';
    if (scene.current.category === index) {
      if (!canTransition && scene.entering) setScene({ current: scene.current, exit: null, entering: false });
      return;
    }
    const current = { category: index, key: ++generation.current };
    let exit = null;
    if (canTransition) {
      let visibleOpacity = 0;
      for (const element of stack.current.children) {
        const style = getComputedStyle(element);
        const opacity = Number(style.opacity);
        visibleOpacity += opacity;
        if (!exit || opacity > exit.opacity) {
          exit = { key: Number(element.dataset.layerKey), category: Number(element.dataset.layerCategory), opacity, transform: style.transform };
        }
      }
      // A new transition can only keep one outgoing layer. Carry the current
      // opacity across both layers so the stage does not dim when interrupted.
      if (exit) exit.opacity = Math.min(1, visibleOpacity);
    }
    setScene({ current, exit, entering: canTransition });
  }, [index, running, scene]);

  useLayoutEffect(() => {
    if (!scene.entering) return;
    const { firstElementChild: leaving, lastElementChild: entering } = stack.current;
    const direction = !scene.exit || scene.current.category > scene.exit.category ? 1 : -1;
    const exit = scene.exit && leaving.animate([
      { opacity: scene.exit.opacity, transform: scene.exit.transform },
      { opacity: 0, transform: `translateX(${-direction * 12}px) scale(.982)` },
    ], { duration: 220, easing: 'cubic-bezier(.37, .05, .62, 1)', fill: 'forwards' });
    const entry = entering.animate([
      { opacity: 0, transform: `translateX(${direction * 14}px) scale(.975)` },
      { opacity: 1, transform: 'translateX(0) scale(1)' },
    ], { duration: 280, easing: 'cubic-bezier(.22, .75, .22, 1)', fill: 'both' });
    entry.onfinish = () => setScene(previous => previous === scene
      ? { current: scene.current, exit: null, entering: false } : previous);
    return () => { entry.cancel(); exit?.cancel(); };
  }, [scene]);

  const mode = staticPose ? 'static' : running ? 'playing' : 'paused';
  const shownConfidence = source === 'prediction' && signal && Number.isFinite(confidence) && confidence >= 0 && confidence <= 1
    ? String(confidence) : null;
  const provenance = sourceLabel[source] || sourceLabel.preview;
  const accessibleName = signal
    ? `${provenance} · ${signal.name} ${signal.zh} · ${signal.formZh}雕塑`
    : `${provenance} · 暂无有效类别`;
  const layer = (record, leaving = false) => record && record.category !== null &&
    <div key={record.key} className="ss-layer" data-layer-key={record.key}
      data-layer-category={record.category} data-leaving={leaving ? 'true' : undefined}>
      <Surface category={record.category} low={quality === 'low'}/>
    </div>;

  return <div className={`ss-sculpture ${className}`} data-source={source} data-category={index}
    data-mode={mode} data-quality={quality} data-confidence={shownConfidence}>
    <div className="ss-stack" ref={stack} role="img" aria-label={accessibleName}>
      {layer(scene.exit, true)}
      {layer(scene.current)}
    </div>
    {shownConfidence !== null && <p className="ss-confidence">置信度 <data value={shownConfidence}>{shownConfidence}</data></p>}
  </div>;
}
