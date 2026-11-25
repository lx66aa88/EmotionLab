import { memo, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { CHALLENGE, challengeScore } from '../challengeGame.js';
import { MATCH_POINTS, MAX_POINTS, roundPoints, totalPoints } from '../challengeGameT72.js';
import { useChallengeT72 } from '../useChallengeT72.js';
import { SignalSculpture, SignalSilhouette, useReducedMotion } from '../../seven-signals/SignalSculpture.jsx';
import { signalFor } from '../../seven-signals/signals.js';

const Sculpture = memo(SignalSculpture);
const pad = value => String(value).padStart(2, '0');
const elapsed = ms => (ms / 1000).toFixed(2) + ' 秒';
const roundCount = CHALLENGE.targets.length;
const hints = [
  '轻轻收拢眉心，嘴唇自然合上。', '稍微皱鼻，轻抬上唇。', '抬眉、睁大眼睛，嘴唇微张。',
  '放松下巴，让嘴角向上。', '轻抬眉头，让嘴角放松向下。', '眉毛上扬，嘴自然张开。', '放松眉眼和嘴角，平视镜头。',
];
const verdicts = {
  matched: '匹配成功', miss: '超时 · 未匹配', no_face: '未检测到人脸', unclear: '模型无法判断',
  service: '推理服务暂不可用', skipped: '已跳过', ended: '提前结束',
};
const origins = { live_raw: '本机三模型 RAW', live_status: '本机采样状态', none: '无本轮读数' };
const interruptions = {
  manual: '恢复后用新画面重新累计。',
  hidden: '离开前台时已关闭摄像头。重新开启后可继续。',
  camera_closed: '重新开启摄像头后可继续。',
  camera_error: '摄像头信号中断。重新开启后可继续。',
};
const readings = {
  waiting: ['等待有效采样', '请让一张脸留在画面中央。'],
  no_face: ['未检测到人脸', '请回到画面中央。'],
  target_lost: ['跟踪目标丢失', '回到原位或重新定位。'],
  multiple: ['检测到多张人脸', '请让画面里只留下玩家。'],
  low_quality: ['模型无法判断', '试试更均匀的光线，保持正面。'],
  unclear: ['模型无法判断', '本帧没有可用读数。'],
  stale: ['读数已过期', '正在等待新画面。'],
  service: ['推理服务暂不可用', '本机服务正在重试。'],
  preview: ['预览中', '正式窗口开启后显示读数。'],
  resolved: ['判定已结束', '下一回合开启后显示新读数。'],
  paused: ['判定已暂停', '恢复后等待新画面。'],
  opening: ['等待摄像头授权'],
  camera_error: ['摄像头不可用'],
  off: ['摄像头关闭'],
};

function verdict(outcome, attempt) {
  if (outcome === 'no_face' && attempt?.noFace === 0 && attempt.lost > 0) return '跟踪目标丢失';
  return verdicts[outcome] ?? '未进行';
}

function RoundStrip({ game }) {
  return <ol className="challenge-rounds" aria-label="七回合进度">
    {CHALLENGE.targets.map(index => {
      const round = game.rounds[index];
      const current = Boolean(round) && game.index === index && game.phase !== 'finished';
      const status = round?.outcome ? verdict(round.outcome, round.attempts.at(-1)) : current ? '当前回合' : '未进行';
      return <li key={index} aria-current={current ? 'step' : undefined} data-result={round?.outcome}
        aria-label={`第 ${index + 1} 回合，${status}`}>
        <span className="mono" aria-hidden="true">{pad(index + 1)}</span>
        {round?.outcome && <span className="challenge-round-mark" aria-hidden="true">
          {round.outcome === 'matched' ? '✓' : round.outcome === 'skipped' ? '↷' : '–'}
        </span>}
      </li>;
    })}
  </ol>;
}

function phaseCopy(game, round) {
  if (game.phase === 'prepare') return ['准备', 'GET READY', '倒计时结束后开始判定。'];
  if (game.phase === 'playing') return ['挑战中', 'MATCH WINDOW', '看向镜头，保持目标表情片刻。'];
  if (game.phase === 'paused') return ['已暂停', 'PAUSED', interruptions[game.pause.reason]];
  if (game.phase === 'resolved') {
    const attempt = round.attempts.at(-1);
    return round.outcome === 'matched'
      ? ['匹配成功', 'SIGNAL LOCKED', `+${MATCH_POINTS} 分 · 用时 ${elapsed(attempt.matchMs)}`]
      : [verdict(round.outcome, attempt), 'WINDOW CLOSED', '本次 0 分，可以重试、跳过或继续。'];
  }
  return ['开始前', 'HOW TO PLAY', '每回合准备 3 秒，挑战 8 秒。'];
}

function StatusBar({ game, copy, score }) {
  const [title, english, note] = copy;
  const clockPhase = game.pause?.from ?? game.phase;
  const timed = clockPhase === 'prepare' || clockPhase === 'playing';
  const duration = (clockPhase === 'prepare' ? CHALLENGE.prepareMs : CHALLENGE.playMs) / 1000;
  return <div className="challenge-status">
    <div className="challenge-status-copy">
      <span className="mono challenge-label" lang="en">{english}</span>
      <strong>{title}</strong><span className="challenge-status-note">{note}</span>
    </div>
    <div className="challenge-clock" role="timer" aria-label={clockPhase === 'prepare' ? '准备剩余秒数' : '挑战剩余秒数'}>
      <span className="mono challenge-label">{clockPhase === 'prepare' ? '准备' : '挑战'} <span lang="en">/ SEC</span></span>
      <strong className="mono" data-seconds={timed ? game.seconds : undefined}>{timed ? pad(game.seconds) : '—'}</strong>
      <i className="challenge-clock-track" aria-hidden="true"><i style={{ transform: `scaleX(${timed ? game.seconds / duration : 0})` }}/></i>
    </div>
    <div className="challenge-tally">
      <span className="mono challenge-label">积分 <span lang="en">/ SCORE</span></span>
      <strong className="mono">{score}<small> / {MAX_POINTS}</small></strong>
    </div>
  </div>;
}

function TargetStage({ label, phase, motion, reduced, toggleMotion }) {
  const signal = signalFor(label);
  const playback = motion && phase !== 'paused' && phase !== 'finished' ? 'playing' : 'paused';
  return <section className="challenge-target challenge-panel" aria-labelledby="challenge-target-title">
    <div className="challenge-panel-heading">
      <h2 id="challenge-target-title" className="mono challenge-label"><span lang="en">TARGET</span> <span>目标表情</span></h2>
      {!reduced && <button className="challenge-motion" type="button" onClick={toggleMotion}
        aria-label="减少挑战动效" aria-pressed={!motion}>{motion ? 'Ⅱ' : '▶'} <span>动效</span></button>}
    </div>
    <div className="challenge-target-title" key={label} data-target-name>
      <span lang="en">{signal?.name ?? 'Seven Signals'}</span><span>{signal?.zh ?? '七种表情'}</span>
    </div>
    <div className="challenge-art">
      <Sculpture category={signal ? label : 3} source={signal ? 'target' : 'preview'}
        playback={playback} motion={motion && signal ? 'system' : 'reduced'}/>
    </div>
    <div className="challenge-target-caption">
      <span className="mono"><span lang="en">{signal?.form ?? 'Bloom'}</span> / {signal?.formZh ?? '作品预览'}</span>
      {signal && <p>{hints[label]}</p>}
    </div>
  </section>;
}

function CameraStage({ game, camera, video, relocate }) {
  const ready = camera.mode === 'ready';
  const current = game.current;
  const kind = !ready ? camera.mode : game.phase === 'playing' ? current?.kind ?? 'waiting'
    : game.phase === 'resolved' ? 'resolved' : game.phase === 'paused' ? 'paused' : 'preview';
  const model = kind === 'raw' || kind === 'close' ? signalFor(current?.label) : null;
  const [title, hint] = readings[kind] ?? [];
  const description = kind === 'raw' ? `RAW · ${(current.probability * 100).toFixed(1)}%`
    : kind === 'close' ? '领先不足 4 个百分点，等待更明确的读数。' : hint ?? camera.note;
  return <section className="challenge-camera challenge-panel" aria-labelledby="challenge-camera-title" data-camera={camera.mode}>
    <div className="challenge-panel-heading">
      <h2 id="challenge-camera-title" className="mono challenge-label"><span lang="en">CAMERA</span> <span>镜像预览</span></h2>
      <span className="challenge-camera-state mono"><i aria-hidden="true"/>{ready ? '画面已开启' : camera.mode === 'opening' ? '等待授权' : '画面未开启'}</span>
    </div>
    <div className="challenge-video">
      <video ref={video} autoPlay playsInline muted aria-label="本机摄像头镜像预览" aria-hidden={!ready}/>
      {!ready && <div className="challenge-aperture" aria-hidden="true"><i/><i/><span>LOCAL CAMERA</span></div>}
      <div className="challenge-viewfinder" aria-hidden="true"/>
    </div>
    <div className="challenge-reading" data-signal={kind} data-frame-id={current?.frame}
      data-model-label={model ? current.label : undefined} data-raw-probability={model ? current.probability : undefined}>
      <div className="challenge-readout">
        <span className="mono challenge-label"><span lang="en">DETECTED</span> 模型读数</span>
        <strong>{model ? <>{model.zh} <span lang="en">{model.name}</span></> : title}</strong>
      </div>
      {model && <div className="challenge-detected-art" data-category={current.label}><SignalSilhouette category={current.label}/></div>}
      <span className="challenge-reading-detail">{description}</span>
      {kind === 'target_lost' && <button className="challenge-relocate" onClick={relocate}>重新定位 <span aria-hidden="true">↶</span></button>}
    </div>
  </section>;
}

function MatchMeter({ game, round }) {
  const attempt = game.attempt ?? round?.attempts.at(-1);
  const matched = round?.outcome === 'matched';
  const hits = matched ? CHALLENGE.matches : Math.min(game.attempt?.streak.length ?? 0, CHALLENGE.matches);
  const pending = !matched && hits === CHALLENGE.matches;
  const message = matched ? '已稳定匹配' : pending ? '帧数已达标，等待覆盖半秒' : `${hits} / ${CHALLENGE.matches} 连续帧`;
  return <div className="challenge-meter">
    <span className="challenge-meter-label">匹配进度 <span className="mono" lang="en">/ SIGNAL LOCK</span></span>
    <div className="challenge-segments" role="progressbar" aria-label="连续匹配进度"
      aria-valuemin={0} aria-valuemax={CHALLENGE.matches} aria-valuenow={hits} aria-valuetext={message}>
      {Array.from({ length: CHALLENGE.matches }, (_, index) =>
        <i key={index} data-hit={index < hits || undefined} data-pending={pending && index === hits - 1 || undefined} aria-hidden="true"/>)}
    </div>
    <span className="challenge-meter-text">{message}</span>
    <span className="challenge-samples mono">命中 <b data-match-count>{attempt?.matches ?? 0}</b> / 有效 <b data-judged-count>{attempt?.judged ?? 0}</b> 帧</span>
  </div>;
}

function Controls({ game, round, camera, act, primaryRef }) {
  const ready = camera.mode === 'ready';
  const idle = game.phase === 'idle';
  const paused = game.phase === 'paused';
  const resolved = game.phase === 'resolved';
  const matched = round?.outcome === 'matched';
  const last = game.index === game.rounds.length - 1;
  const cameraLabel = ready ? '关闭摄像头' : camera.mode === 'opening' ? '取消授权等待'
    : camera.mode === 'camera_error' ? '重新开启摄像头' : '开启摄像头';
  let [action, label, mark] = ['pause', '暂停挑战', 'Ⅱ'];
  if (idle) [action, label, mark] = ['start', '开始挑战', '↗'];
  if (paused) [action, label, mark] = ['resume', '继续挑战', '↗'];
  if (resolved) [action, label, mark] = ['next', last ? '查看挑战结果' : '下一回合', '↗'];
  if (!ready && (idle || paused)) [action, label, mark] = ['camera', cameraLabel, '⌖'];

  const run = type => event => { if (event.detail <= 1) act(type); };
  const preventRepeat = event => {
    if (event.repeat && (event.key === 'Enter' || event.key === ' ')) event.preventDefault();
  };
  return <div className="challenge-controls" aria-label="挑战操作" onKeyDown={preventRepeat}>
    <button type="button" className="challenge-button challenge-primary" data-action={action} ref={primaryRef} onClick={run(action)}>
      {label} <span aria-hidden="true">{mark}</span>
    </button>
    {resolved && !matched && <button type="button" className="challenge-button" data-action="retry" onClick={run('retry')} disabled={!ready}>
      重试本回合 <span aria-hidden="true">↶</span>
    </button>}
    {action !== 'camera' && !(last && matched) && <button type="button" className="challenge-button" data-action="camera" onClick={run('camera')}>
      {cameraLabel}
    </button>}
    {!idle && !matched && <button type="button" className="challenge-button" data-action="skip" onClick={run('skip')}>
      跳过回合 <span aria-hidden="true">↷</span>
    </button>}
    {!idle && <button type="button" className="challenge-button challenge-exit" data-action="finish" onClick={run('finish')}>
      提前结束 <span aria-hidden="true">↘</span>
    </button>}
  </div>;
}

function AttemptDetails({ attempts }) {
  return <details className="challenge-attempts">
    <summary>{attempts.length} 次尝试 · 采样记录</summary>
    <ol>{attempts.map((item, index) => <li key={index} data-attempt-outcome={item.outcome} data-attempt-source={item.source}>
      <strong>{pad(index + 1)} / {verdict(item.outcome, item)} · {origins[item.source]}</strong>
      <span>命中 {item.matches} / 有效 {item.judged} 帧
        {item.noFace > 0 && ` · 无人脸 ${item.noFace} 帧`}
        {item.lost > 0 && ` · 跟踪丢失 ${item.lost} 帧`}
        {item.unclear > 0 && ` · 无法判断 ${item.unclear} 帧`}
        {item.stale > 0 && ` · 过期 ${item.stale} 次`}
        {item.service > 0 && ` · 推理异常 ${item.service} 次`}
        {item.cameraFaults > 0 && ` · 摄像头中断 ${item.cameraFaults} 次`}</span>
      {item.frameIds.length > 0 && <span className="mono" data-winning-frames={item.frameIds.join(',')}>
        判定帧 #{item.frameIds.join(' · #')} · 跨 {Math.round(item.spanMs)} ms
      </span>}
    </li>)}</ol>
  </details>;
}

function ChallengeRecord({ game, score, heading, reset }) {
  const matched = challengeScore(game);
  return <section className="challenge-record" aria-labelledby="challenge-record-title">
    <div className="challenge-record-hero">
      <div className="challenge-record-intro">
        <span className="mono challenge-label" lang="en">SESSION RESULT</span>
        <h2 id="challenge-record-title" tabIndex={-1} ref={heading}>{game.finishedEarly ? '挑战提前结束' : '七回合已完成'}</h2>
        <p>成功匹配 <strong data-success-count={matched}>{matched} / {roundCount}</strong> 回合</p>
        <button type="button" className="challenge-button challenge-primary" data-action="reset" onClick={reset}>
          重新挑战 <span aria-hidden="true">↗</span>
        </button>
      </div>
      <div className="challenge-record-score">
        <span className="mono challenge-label">本局总分 <span lang="en">/ TOTAL</span></span>
        <strong className="mono">{score}<small> / {MAX_POINTS}</small></strong>
      </div>
    </div>
    <ol className="challenge-record-list" aria-label="回合结果">
      {game.rounds.map((round, index) => {
        const signal = signalFor(round.label);
        const attempt = round.attempts.at(-1);
        const matchMs = attempt?.matchMs;
        const noFace = round.attempts.reduce((sum, item) => sum + item.noFace, 0);
        return <li key={round.label} data-ledger-target={round.label} data-outcome={round.outcome ?? 'pending'}
          data-points={roundPoints(round)} data-match-ms={matchMs ?? undefined} data-no-face={noFace}>
          <div className="challenge-record-row">
            <span className="mono challenge-row-index">{pad(index + 1)}</span>
            <div className="challenge-row-name" style={{ '--row-accent': signal.accent }}>
              <SignalSilhouette category={round.label}/><span><strong>{signal.zh}</strong><small lang="en">{signal.name}</small></span>
            </div>
            <span className="challenge-row-verdict">{verdict(round.outcome, attempt)}
              {noFace > 0 && round.outcome !== 'no_face' && <small>曾未检测到人脸</small>}
            </span>
            <span className="mono challenge-row-time">{matchMs != null ? elapsed(matchMs) : '—'}</span>
            <span className="mono challenge-row-points">{roundPoints(round)} <small>分</small></span>
          </div>
          {round.attempts.length > 0 && <AttemptDetails attempts={round.attempts}/>}
        </li>;
      })}
    </ol>
  </section>;
}

export default function ExpressionChallengeT72({ theme }) {
  const { game, camera, video, canvas, act, relocate } = useChallengeT72();
  const [motion, setMotion] = useState(true);
  const reduced = useReducedMotion();
  const resultHeading = useRef(null);
  const primary = useRef(null);
  const replaying = useRef(false);
  const finished = game.phase === 'finished';
  const round = game.rounds[game.index];
  const target = signalFor(round?.label);
  const copy = phaseCopy(game, round);
  const score = totalPoints(game);

  useEffect(() => { document.documentElement.dataset.theme = theme?.light ? 'light' : 'dark'; }, [theme?.light]);
  useLayoutEffect(() => {
    if (finished) resultHeading.current?.focus();
    else if (replaying.current) {
      replaying.current = false;
      primary.current?.focus();
    }
  }, [finished]);

  return <div className="app challenge-app" data-challenge-phase={game.phase} data-target={round?.label}
    data-round={round ? game.index + 1 : undefined} data-outcome={round?.outcome ?? undefined} data-score={score}
    data-motion={motion && !reduced ? 'on' : 'off'} style={target ? { '--target-accent': target.accent } : undefined}>
    <main id="observation" tabIndex={-1}>
      <header className="challenge-heading">
        <h1 lang="en">Expression <span>Challenge</span></h1>
        <span className="challenge-heading-note">{round && !finished ? `第 ${game.index + 1} / ${roundCount} 回合` : '表情模仿挑战'}</span>
      </header>
      <RoundStrip game={game}/>
      <div className="challenge-board" hidden={finished}>
        <StatusBar game={game} copy={copy} score={score}/>
        {game.phase === 'idle' && <p className="challenge-rules">
          七种表情各一回合。<strong>稳定匹配 +{MATCH_POINTS} 分</strong>，未匹配、超时或跳过 0 分，满分 {MAX_POINTS}。
        </p>}
        <div className="challenge-stages">
          <TargetStage label={round?.label} phase={game.phase} motion={motion} reduced={reduced} toggleMotion={() => setMotion(value => !value)}/>
          <CameraStage game={game} camera={camera} video={video} relocate={relocate}/>
        </div>
        <MatchMeter game={game} round={round}/>
        <Controls game={game} round={round} camera={camera} act={act} primaryRef={primary}/>
      </div>
      <p className="sr-only" role="status">{finished ? '' : [
        target?.zh, copy[0], game.phase === 'resolved' ? copy[2] : null,
        game.phase === 'playing' ? readings[game.current?.kind]?.[0] : null, camera.mode === 'camera_error' ? camera.note : null,
      ].filter(Boolean).join(' · ')}</p>
      {finished && <ChallengeRecord game={game} score={score} heading={resultHeading}
        reset={() => { replaying.current = true; act('reset'); }}/>}
      <p className="challenge-privacy">{finished ? '记录仅留在此页面。分数反映本局模型匹配。' : '单人游玩 · 摄像头画面仅在本机处理 · 不录像或保存人脸图像'}</p>
      <details className="challenge-method" id="challenge-method">
        <summary>玩法与判定 <span aria-hidden="true">↗</span></summary>
        <p>每回合先准备 3 秒，再判定 8 秒。稳定匹配计 {MATCH_POINTS} 分，其他结果计 0 分。重试不扣分。成功耗时从该次尝试的正式窗口开始计，到稳定匹配确认，扣除暂停时间。</p>
        <p>判定取当前单人画面的原始最高类别，领先第二名至少 4 个百分点才可比较。至少连续命中 3 帧、首尾相隔至少半秒、相邻命中间隔不超过 1.5 秒才算匹配。读数中断会清空连续进度。</p>
        <p>暂停保留预览。提前结束、切换模式或离开前台会释放摄像头。游戏分数只用于记录本局匹配，不代表真实情绪。</p>
      </details>
    </main>
    <footer className="challenge-footer"><span className="footer-brand">HUMAN SIGNAL<span>© EMOTIONLAB / 2026</span></span>
      <span className="mono" lang="en">EXPRESSION CHALLENGE · T7.2</span></footer>
    <canvas ref={canvas} width="1" height="1" className="sr-only" aria-hidden="true"/>
  </div>;
}
