import { memo, useEffect, useLayoutEffect, useReducer, useRef, useState } from 'react';
import { LiveSession } from '../liveSession.js';
import { CHALLENGE, challengeReducer, challengeScore, initialChallenge, nextClockWake, shuffledTargets } from '../challengeGame.js';
import { readChallengeSignal } from '../challengeSignal.js';
import { SignalSculpture, useReducedMotion } from '../../seven-signals/SignalSculpture.jsx';
import { signalFor } from '../../seven-signals/signals.js';

const Sculpture = memo(SignalSculpture);
const pad = value => String(value).padStart(2, '0');
const hints = [
  '轻轻收拢眉心，嘴唇自然合上。', '稍微皱鼻，轻抬上唇。', '抬起眉毛，睁大眼睛，嘴唇微张。',
  '放松下巴，让嘴角向上。', '轻抬眉头，让嘴角放松向下。', '眉毛上扬，嘴自然张开。', '放松眉眼和嘴角，平视镜头。',
];
const verdicts = {
  matched: '匹配成功', miss: '未匹配', no_face: '未检测到人脸', unclear: '模型无法判断',
  service: '推理服务暂不可用', skipped: '已跳过', ended: '提前结束',
};
const origins = { live_raw: '本机三模型 · RAW', live_status: '本机采样状态', none: '无本轮读数' };
const interruptions = {
  manual: '已暂停。恢复后从新画面重新累计。',
  hidden: '页面离开前台，摄像头已释放。重新开启后可继续。',
  camera_closed: '摄像头已关闭。重新开启后可继续。',
  camera_error: '摄像头故障或信号中断。重新开启后可继续。',
};
const signalCopy = {
  waiting: ['等待有效采样', '保持一张脸在取景框内。'],
  no_face: ['未检测到人脸', '请回到画面中央。'],
  target_lost: ['跟踪目标丢失', '请回到原位或点「重新定位」。'],
  low_quality: ['模型无法判断', '请保持清晰、正面，试试更均匀的光线。'],
  multiple: ['检测到多张人脸', '请让画面里只留下玩家。'],
  close: ['模型无法判断', '原始结果的前两类接近。'],
  unclear: ['模型无法判断', '本帧没有可用读数。'],
  stale: ['模型无法判断', '旧读数已过期，等待新画面。'],
  service: ['推理服务暂不可用', '本机服务正在重试。'],
};

function useChallenge() {
  const video = useRef(null), canvas = useRef(null), capture = useRef(null);
  const [game, dispatch] = useReducer(challengeReducer, undefined, initialChallenge);
  const [camera, setCamera] = useState({ mode: 'off', note: '摄像头尚未开启' });
  const action = (type, fields = {}) => dispatch({ type, ...fields, at: performance.now() });

  useLayoutEffect(() => {
    let wasOpen = false, plannedClose = false;
    const live = new LiveSession({ video: video.current, canvas: canvas.current, onChange: next => {
      const justOpened = next.camera && !wasOpen;
      const unexpectedlyClosed = wasOpen && !next.camera && !plannedClose;
      wasOpen = next.camera;
      if (next.status === 'interrupted') {
        live.close('摄像头信号中断，请重新开启。', 'camera_error');
        return;
      }
      if (unexpectedlyClosed || next.status === 'camera_error') action('pause', { reason: 'camera_error' });
      const mode = next.camera ? 'ready' : unexpectedlyClosed ? 'camera_error' : next.status;
      const note = next.camera ? '摄像头已开启' : next.message;
      setCamera(previous => previous.mode === mode && previous.note === note ? previous : { mode, note });
      if (justOpened) {
        // open() has not scheduled its first frame yet. Keep a preview until
        // the timed window opens; the existing session invalidates its epoch.
        live.pause();
        return;
      }
      const at = performance.now();
      dispatch({ type: 'signal', at, signal: readChallengeSignal(next, at) });
    } });
    const release = (reason, message) => {
      if (reason) action('pause', { reason });
      plannedClose = true;
      live.close(message);
      plannedClose = false;
    };
    capture.current = { live, release };
    const leave = () => release('hidden', '页面已离开前台，摄像头已关闭');
    const hide = () => { if (document.hidden) leave(); };
    document.addEventListener('visibilitychange', hide);
    window.addEventListener('pagehide', leave);
    return () => {
      document.removeEventListener('visibilitychange', hide);
      window.removeEventListener('pagehide', leave);
      capture.current = null;
      live.onChange = () => {};
      live.close();
    };
  }, []);

  useLayoutEffect(() => {
    const { live, release } = capture.current;
    if (game.phase === 'finished') {
      if (camera.mode === 'ready' || camera.mode === 'opening') release();
    } else if (camera.mode === 'ready') {
      if (game.phase === 'playing') live.resume();
      else if (live.running) live.pause();
    }
  }, [game.phase, camera.mode]);

  useEffect(() => {
    const now = performance.now();
    const delay = nextClockWake(game, now);
    if (delay === null) return;
    const wakeAt = now + delay;
    let timer;
    const tick = () => {
      const at = performance.now();
      if (at < wakeAt) timer = setTimeout(tick, Math.ceil(wakeAt - at));
      else dispatch({ type: 'tick', at, deadline: game.deadline });
    };
    timer = setTimeout(tick, Math.ceil(delay));
    return () => clearTimeout(timer);
  }, [game]);

  function primary(type) {
    const needsCamera = ['start', 'resume', 'retry'].includes(type);
    if (needsCamera && camera.mode !== 'ready') return;
    if (needsCamera) {
      const track = capture.current.live.stream?.getVideoTracks()[0];
      if (!track || track.readyState !== 'live' || track.muted) {
        capture.current.live.close('摄像头没有可用画面，请重新开启。', 'camera_error');
        return;
      }
    }
    action(type, type === 'start' ? { order: shuffledTargets() } : type === 'pause' ? { reason: 'manual' } :
      { cameraReady: camera.mode === 'ready' });
  }
  function toggleCamera() {
    const { live, release } = capture.current;
    if (camera.mode === 'ready' || camera.mode === 'opening') release('camera_closed');
    else if (!document.hidden) live.open();
  }
  return { game, camera, video, canvas, primary, toggleCamera, refocus: () => capture.current?.live.choose(null) };
}

function RoundStrip({ game }) {
  return <ol className="challenge-strip" aria-label="七回合进度">
    {CHALLENGE.targets.map(index => {
      const outcome = game.rounds[index]?.outcome;
      const current = game.rounds.length > 0 && game.index === index && game.phase !== 'finished';
      return <li key={index} aria-current={current ? 'step' : undefined}
        data-outcome={outcome ?? (current ? 'current' : 'pending')}
        aria-label={'第 ' + (index + 1) + ' 回合：' + (outcome ? verdicts[outcome] : current ? '当前回合' : '未进行')}>
        <span aria-hidden="true">{outcome === 'matched' ? '✓' : outcome === 'skipped' ? '↷' : pad(index + 1)}</span>
      </li>;
    })}
  </ol>;
}

function phaseCopy(game, outcome) {
  if (game.phase === 'prepare') return ['准备', 'GET READY', '看清目标，倒计时结束后开始判定。'];
  if (game.phase === 'playing') return ['挑战中', 'MATCH WINDOW', '自然做出表情，稍微保持一下。'];
  if (game.phase === 'paused') return ['已暂停', 'ON HOLD', interruptions[game.pause.reason]];
  if (game.phase === 'resolved') return [verdicts[outcome], outcome === 'matched' ? 'SIGNAL LOCKED' : 'WINDOW CLOSED',
    outcome === 'matched' ? '连续读数已确认，本回合计 1 分。' :
      outcome === 'miss' ? '有效读数未形成稳定匹配。可以重试、跳过或继续。' :
        '本回合没有可计分的稳定读数。可以重试、跳过或继续。'];
  return ['等待开始', 'STANDBY', '开启摄像头，再开始七回合挑战。'];
}

function TargetStage({ round, phase, motion, toggleMotion, reduced }) {
  const label = round?.label;
  const signal = signalFor(label);
  return <section className="challenge-plate challenge-target" aria-labelledby="challenge-target-title">
    <div className="challenge-plate-top mono"><h2 id="challenge-target-title">目标 <span lang="en">/ TARGET</span></h2>
      <span>{signal ? 'S–' + pad(label + 1) : 'S–01…07'}</span>
    </div>
    <div className="challenge-object" data-locked={round?.outcome === 'matched' || undefined}>
      <div className="challenge-object-grid" aria-hidden="true"/>
      {signal ? <Sculpture category={label} source="target" playback={motion && phase !== 'paused' ? 'playing' : 'paused'}/>
        : <div className="challenge-edition" aria-hidden="true"><span>07</span><small className="mono">SEVEN SIGNALS</small></div>}
      {round?.outcome === 'matched' && <span className="challenge-seal mono" aria-hidden="true">✓ LOCKED</span>}
      {!reduced && <button className="challenge-motion" type="button" onClick={toggleMotion} aria-pressed={!motion}
        aria-label="暂停雕塑动效" hidden={!signal}>{motion ? 'Ⅱ' : '▶'}</button>}
    </div>
    <div className="challenge-plate-caption">
      <strong data-target-name><span lang="en">{signal?.name ?? 'Seven Signals'}</span> <span>{signal?.zh ?? '七种表情'}</span></strong>
      <span className="challenge-form mono">{signal ? <><span lang="en">{signal.form}</span> / {signal.formZh}</> : '表情模仿实验'}</span>
    </div>
  </section>;
}

function CameraStage({ video, camera, current, game, refocus }) {
  const live = camera.mode === 'ready';
  const signal = signalFor(current?.label);
  const kind = live ? game.phase === 'playing' ? current?.kind ?? 'waiting' : 'preview' : camera.mode;
  const label = kind === 'raw' ? signal.zh
    : (signalCopy[kind]?.[0] ?? (kind === 'preview' ? '预览中 · 暂未计分'
      : kind === 'camera_error' ? '摄像头故障或权限受限' : kind === 'opening' ? '等待摄像头授权' : '摄像头关闭'));
  const detail = kind === 'raw' ? signal.name + ' · ' + (current.probability * 100).toFixed(1) + '%'
    : kind === 'close' && signal ? '首选 ' + signal.name + ' · 领先不足 4 个百分点'
      : signalCopy[kind]?.[1] ?? (kind === 'preview' ? '正式窗口内读取原始结果。' : camera.note);
  return <section className="challenge-plate challenge-camera" aria-labelledby="challenge-camera-title" data-camera={camera.mode}>
    <div className="challenge-plate-top mono"><h2 id="challenge-camera-title">你的画面 <span lang="en">/ MIRROR</span></h2>
      <span className="challenge-camera-indicator"><i data-open={live || undefined}/>{live ? 'VIDEO ON' : 'VIDEO OFF'}</span>
    </div>
    <div className="challenge-video">
      <video ref={video} autoPlay playsInline muted aria-label="本机摄像头镜像预览" aria-hidden={!live} data-visible={live || undefined}/>
      {!live && <div className="challenge-aperture" aria-hidden="true"><span>⟐</span><small className="mono">LOCAL VIEWFINDER</small></div>}
      <i className="challenge-crop tl" aria-hidden="true"/><i className="challenge-crop tr" aria-hidden="true"/>
      <i className="challenge-crop bl" aria-hidden="true"/><i className="challenge-crop br" aria-hidden="true"/>
    </div>
    <div className="challenge-plate-caption challenge-reading" data-signal={kind} data-frame-id={current?.frame}
      data-model-label={current?.label}>
      <div><small className="mono">本帧 AI 识别 <span lang="en">/ RAW</span></small><strong>{label}</strong></div>
      <span className="challenge-raw-detail">{detail}</span>
      {kind === 'target_lost' && <button className="challenge-relocate" onClick={refocus}>重新定位 ↶</button>}
    </div>
  </section>;
}

function MatchMeter({ game, round }) {
  const attempt = game.attempt ?? round?.attempts.at(-1);
  const won = round?.outcome === 'matched';
  const streak = won ? CHALLENGE.matches : Math.min(game.attempt?.streak.length ?? 0, CHALLENGE.matches);
  return <div className="challenge-meter">
    <div className="challenge-meter-title"><strong>连续匹配</strong> <span className="mono" lang="en">/ SIGNAL LOCK</span></div>
    <div className="challenge-meter-segments" role="progressbar" aria-label="连续匹配进度"
      aria-valuemin={0} aria-valuemax={CHALLENGE.matches} aria-valuenow={streak}
      aria-valuetext={won ? '已稳定匹配' : streak + ' 个连续匹配样本'}>
      {Array.from({ length: CHALLENGE.matches }, (_, i) => <i key={i} data-hit={i < streak || undefined} aria-hidden="true"/>)}
    </div>
    <span className="challenge-counts mono">命中 <b data-match-count>{attempt?.matches ?? 0}</b> 帧 / 有效 <b data-judged-count>{attempt?.judged ?? 0}</b> 帧</span>
  </div>;
}

function Controls({ game, round, camera, primary, toggleCamera }) {
  const ready = camera.mode === 'ready';
  const idle = game.phase === 'idle';
  const resolved = game.phase === 'resolved';
  const paused = game.phase === 'paused';
  const next = game.index === game.rounds.length - 1 ? '查看挑战记录' : '下一回合';
  const [op, label, english] = idle ? ['start', '开始挑战', 'START CHALLENGE']
    : paused ? ['resume', '继续挑战', 'RESUME']
      : resolved ? ['next', next, game.index === game.rounds.length - 1 ? 'VIEW RECORD' : 'NEXT ROUND']
        : ['pause', '暂停挑战', 'PAUSE'];
  const needsCamera = op === 'start' || op === 'resume';
  const matched = round?.outcome === 'matched';
  return <div className="challenge-controls" aria-label="挑战操作">
    <button className="challenge-button challenge-primary" onClick={() => primary(op)} data-action={op} disabled={needsCamera && !ready}>
      <span>{label}<small className="mono" lang="en">{english}</small></span>
      <span aria-hidden="true">{op === 'pause' ? 'Ⅱ' : '↗'}</span>
    </button>
    {resolved && !matched && <button className="challenge-button" data-action="retry" onClick={() => primary('retry')} disabled={!ready}>重试本回合 <span aria-hidden="true">↶</span></button>}
    {!idle && !matched && <button className="challenge-button" data-action="skip" onClick={() => primary('skip')}>跳过 <span aria-hidden="true">↷</span></button>}
    <button className={'challenge-button challenge-camera-control' + (!ready ? ' camera-cta' : '')}
      data-action="camera" onClick={toggleCamera}>
      <span>{ready ? '关闭摄像头' : camera.mode === 'opening' ? '取消授权等待' : camera.mode === 'camera_error' ? '重新开启摄像头' : '开启摄像头'}</span>
      <span aria-hidden="true">{ready ? '×' : '⌖'}</span>
    </button>
    {!idle && <button className="challenge-button challenge-end" data-action="finish" onClick={() => primary('finish')}>结束挑战 <span aria-hidden="true">↘</span></button>}
  </div>;
}

function Ledger({ game, reset, heading }) {
  const attempts = game.rounds.flatMap(round => round.attempts);
  const hits = attempts.reduce((sum, attempt) => sum + attempt.matches, 0);
  return <section className="challenge-ledger" aria-labelledby="challenge-ledger-title">
    <div className="challenge-ledger-lede">
      <div><span className="mono challenge-overline">SESSION RECORD / 本次会话</span>
        <h2 id="challenge-ledger-title" tabIndex={-1} ref={heading}>{game.finishedEarly ? '挑战已结束' : '七回合已完成'}</h2>
        <p>{attempts.length} 次尝试 · {hits} 帧目标命中。成绩仅用于这次游戏。</p></div>
      <button className="challenge-button challenge-primary" data-action="reset" onClick={reset}>
        <span>再玩一次<small className="mono" lang="en">NEW CHALLENGE</small></span><span aria-hidden="true">↗</span>
      </button>
    </div>
    <ol className="challenge-ledger-list">
      {game.rounds.map((round, i) => {
        const signal = signalFor(round.label);
        return <li key={round.label} data-ledger-target={round.label} data-outcome={round.outcome ?? 'pending'}>
          <span className="mono challenge-ledger-number">{pad(i + 1)}</span>
          <span className="challenge-ledger-name"><strong>{signal.zh}</strong> <span lang="en">{signal.name}</span></span>
          <span className="challenge-verdict">{round.outcome ? verdicts[round.outcome] : '未进行'}</span>
          <span className="mono challenge-ledger-points">{round.outcome === 'matched' ? '+1' : '—'}</span>
          {round.attempts.length > 0 && <details className="challenge-attempts">
            <summary>{round.attempts.length} 次尝试 · 读数记录</summary>
            <ol>{round.attempts.map((item, attemptIndex) => <li key={attemptIndex} data-attempt-outcome={item.outcome}
              data-attempt-source={item.source} data-matches={item.matches} data-judged={item.judged}>
              <span>{pad(attemptIndex + 1)} / {verdicts[item.outcome]} · {origins[item.source]}</span>
              <span>命中 {item.matches} / 有效 {item.judged} 帧
                {item.noFace + item.lost > 0 && ' · 无当前人脸 ' + (item.noFace + item.lost) + ' 帧'}
                {item.unclear > 0 && ' · 无法判断 ' + item.unclear + ' 帧'}
                {item.stale + item.service + item.cameraFaults > 0 && ' · 过期或中断 ' + (item.stale + item.service + item.cameraFaults) + ' 次'}</span>
              {item.winningFrames.length > 0 && <span className="mono" data-winning-frames={item.winningFrames.map(frame => frame.frame).join(',')}>
                判定帧 #{item.winningFrames.map(frame => frame.frame).join(' · #')} · 跨 {Math.round(item.winningFrames.at(-1).captured - item.winningFrames[0].captured)} ms
              </span>}
            </li>)}</ol>
          </details>}
        </li>;
      })}
    </ol>
  </section>;
}

export default function ExpressionChallenge({ theme }) {
  const { game, camera, video, canvas, primary, toggleCamera, refocus } = useChallenge();
  const [motion, setMotion] = useState(true);
  const reduced = useReducedMotion();
  const resultTitle = useRef(null);
  const finished = game.phase === 'finished';
  const round = game.rounds[game.index];
  const signal = signalFor(round?.label);
  const [title, english, note] = phaseCopy(game, round?.outcome);
  const timed = ['prepare', 'playing', 'paused'].includes(game.phase);
  const score = challengeScore(game);
  useEffect(() => { document.documentElement.dataset.theme = theme?.light ? 'light' : 'dark'; }, [theme?.light]);
  useLayoutEffect(() => { if (finished) resultTitle.current?.focus(); }, [finished]);

  return <div className="app challenge-app" data-challenge-phase={game.phase} data-target={round?.label}
    data-round={round ? game.index + 1 : undefined} data-outcome={round?.outcome ?? undefined} data-score={score}
    style={signal ? { '--challenge-accent': signal.accent } : undefined}>
    <main id="observation" tabIndex={-1}>
      <header className="challenge-heading">
        <div><p className="challenge-overline mono"><span>03 /</span> 表情模仿实验 <span lang="en">· INTERACTIVE STUDY</span></p>
          <h1 lang="en">EXPRESSION <span>CHALLENGE<span aria-hidden="true">↗</span></span></h1></div>
        <div className="challenge-tally"><span className="mono">AI 匹配分 <span lang="en">/ SCORE</span></span>
          <strong className="mono">{pad(score)}<small> / 07</small></strong></div>
      </header>
      <RoundStrip game={game}/>
      <div className="challenge-workbench" hidden={finished}>
        <div className="challenge-status-band">
          <div className="challenge-phase">
            <span className="mono challenge-overline">{round ? 'ROUND ' + pad(game.index + 1) : 'ROUND —'} <span lang="en">/ {english}</span></span>
            <strong>{title}</strong>
            <span className="challenge-phase-note">{note}</span>
          </div>
          <div className="challenge-clock mono" role="timer" aria-label={game.phase === 'prepare' ? '准备倒计时' : '回合剩余秒数'}>
            <strong data-seconds={timed ? game.seconds : undefined}>{timed ? pad(game.seconds) : '—'}</strong><span>SEC</span>
          </div>
        </div>
        <div className="challenge-stages">
          <TargetStage round={round} phase={game.phase} motion={motion} reduced={reduced} toggleMotion={() => setMotion(!motion)}/>
          <CameraStage video={video} camera={camera} current={game.current} game={game} refocus={refocus}/>
        </div>
        {signal && <p className="challenge-hint"><b>动作提示</b> {hints[round.label]}</p>}
        <MatchMeter game={game} round={round}/>
        <Controls game={game} round={round} camera={camera} primary={primary} toggleCamera={toggleCamera}/>
        <p className="challenge-privacy">单人游玩 · 画面仅在这台 Mac 上处理 · 不录音、录像或上传</p>
      </div>
      <p className="sr-only" role="status">{finished ? '' : [signal?.zh, title,
        game.phase === 'playing' ? signalCopy[game.current?.kind]?.[0] : camera.mode === 'camera_error' ? camera.note : null].filter(Boolean).join(' · ')}</p>
      {finished && <Ledger game={game} reset={() => primary('reset')} heading={resultTitle}/>}
      <details className="challenge-method" id="challenge-method">
        <summary><span>玩法与判定边界</span><span className="mono" lang="en">METHOD / 07 ↗</span></summary>
        <p>七类各出现一次。每回合先准备 3 秒，再用 8 秒模仿。一个回合最多 1 分；可以重试、跳过或提前结束。</p>
        <p>判定取本机三模型每个采样的原始最高类别。领先第二名至少 4 个百分点才参加判定；连续至少 3 帧、横跨至少半秒、相邻命中间隔不超过 1.5 秒才算匹配。无人脸、多脸、模糊、过期或不匹配会清空连续进度。</p>
        <p>分数只反映本次游戏中 AI 的匹配结果。识别有误差，七类难度不同，分数不代表你的情绪或表情控制能力。结束、切换模式或离开前台会释放摄像头；记录只留在当前页面会话。</p>
      </details>
    </main>
    <footer className="challenge-footer"><span className="footer-brand">HUMAN SIGNAL<span>© EMOTIONLAB / 2026</span></span>
      <span className="mono" lang="en">EXPRESSION STUDY · T7.1</span></footer>
    <canvas ref={canvas} width="1" height="1" className="sr-only" aria-hidden="true"/>
  </div>;
}
