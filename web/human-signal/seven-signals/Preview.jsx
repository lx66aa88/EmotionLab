import { useRef, useState } from 'react';
import { SIGNALS } from './signals.js';
import { SignalSculpture, SignalSilhouette, useReducedMotion } from './SignalSculpture.jsx';
import mark from './mark.svg';

const modelIndex = index => String(index).padStart(2, '0');
const stepByKey = { ArrowLeft: -1, ArrowUp: -1, ArrowRight: 1, ArrowDown: 1 };

function Index({ selected, onSelect }) {
  const choices = useRef([]);
  function navigate(event, index) {
    let next;
    if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = SIGNALS.length - 1;
    else if (stepByKey[event.key]) next = (index + stepByKey[event.key] + SIGNALS.length) % SIGNALS.length;
    else return;
    event.preventDefault();
    onSelect(next);
    choices.current[next].focus();
  }

  return <section className="signal-index" aria-labelledby="index-heading">
    <div className="index-heading">
      <h2 id="index-heading">信号索引 <span lang="en">SIGNAL INDEX</span></h2>
      <p className="key-hint"><kbd>←</kbd><kbd>→</kbd> 切换类别</p>
    </div>
    <div className="index-rail" role="radiogroup" aria-labelledby="index-heading">
      {SIGNALS.map((signal, index) => <button key={signal.name} type="button" role="radio"
        aria-checked={selected === index} aria-label={`${signal.name} ${signal.zh}`}
        tabIndex={selected === index ? 0 : -1} ref={element => { choices.current[index] = element; }}
        onClick={() => onSelect(index)} onKeyDown={event => navigate(event, index)}>
        <span className="index-code" aria-hidden="true">{modelIndex(index)}</span>
        <SignalSilhouette category={index}/>
        <span className="index-name" lang="en">{signal.name}</span>
        <span className="index-zh">{signal.zh}</span>
      </button>)}
    </div>
  </section>;
}

function PlayIcon({ paused }) {
  return <svg viewBox="0 0 16 16" aria-hidden="true" fill="currentColor">
    {paused ? <path d="M5 3.2 13 8l-8 4.8Z"/> : <path d="M4.4 3h2v10h-2zm5.2 0h2v10h-2z"/>}
  </svg>;
}

function MotionControls({ paused, onPause, preference, onPreference }) {
  const systemReduced = useReducedMotion();
  const still = systemReduced || preference !== 'auto';
  return <figcaption className="stage-controls">
    <button type="button" className="play-toggle" disabled={still} onClick={onPause}>
      <PlayIcon paused={paused || still}/>
      <span>{still ? '静态展示' : paused ? '继续播放' : '暂停动效'}</span>
    </button>
    <label className="motion-setting">
      <span>动效</span>
      <select value={preference} onChange={event => onPreference(event.target.value)}>
        <option value="auto">{systemReduced ? '随系统 · 静态' : '随系统'}</option>
        <option value="reduce">减少动态</option>
        <option value="low">轻量静态</option>
      </select>
      <svg viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="m2 4 4 4 4-4" stroke="currentColor" strokeWidth="1.2"/></svg>
    </label>
  </figcaption>;
}

export default function Preview() {
  const [category, setCategory] = useState(0);
  const [paused, setPaused] = useState(false);
  const [preference, setPreference] = useState('auto');
  const signal = SIGNALS[category];

  return <div className="catalogue" data-preference={preference}>
    <a className="skip" href="#signal-index">跳到信号索引</a>
    <header className="masthead">
      <div className="brand"><img src={mark} alt="" width="28" height="28"/><span>EMOTIONLAB</span><small>T6.1</small></div>
      <div className="preview-label"><span>设计预览</span><span lang="en">DESIGN PREVIEW</span></div>
    </header>
    <main>
      <div className="exhibit">
        <div className="identity">
          <h1 lang="en"><span>SEVEN</span><span>SIGNALS</span></h1>
          <p lang="en">Seven Expressions,<br/>{' '}One Visual Language</p>
        </div>
        <section className="specimen" aria-labelledby="specimen-name" style={{ '--specimen-accent': signal.accent }}>
          <div className="specimen-form"><span className="material-chip" aria-hidden="true"/><span lang="en">{signal.form}</span><span>{signal.formZh}</span></div>
          <h2 id="specimen-name" lang="en">{signal.name}</h2>
          <div className="specimen-zh">{signal.zh}</div>
          <p>{signal.note}</p>
        </section>
        <figure className="stage">
          <div className="viewport" style={{ '--specimen-accent': signal.accent }}>
            <div className="viewport-heading"><span lang="en">SIGNAL / {modelIndex(category)}</span><span>手动选择 · 未连接模型</span></div>
            <div className="viewport-field" aria-hidden="true">
              <span className="field-cross field-cross-left"/><span className="field-cross field-cross-right"/>
              <span className="field-orbit field-orbit-outer"/><span className="field-orbit field-orbit-inner"/>
            </div>
            <SignalSculpture category={category} playback={paused ? 'paused' : 'playing'}
              motion={preference === 'reduce' ? 'reduced' : 'system'} quality={preference === 'low' ? 'low' : 'full'}/>
          </div>
          <MotionControls paused={paused} onPause={() => setPaused(value => !value)}
            preference={preference} onPreference={setPreference}/>
        </figure>
      </div>
      <div id="signal-index" tabIndex={-1}><Index selected={category} onSelect={setCategory}/></div>
    </main>
  </div>;
}
