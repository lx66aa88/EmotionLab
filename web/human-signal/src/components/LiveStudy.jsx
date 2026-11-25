import {useEffect, useRef, useState} from 'react';
import {LiveSession} from '../liveSession.js';
import Spectrum from './Spectrum.jsx';

const initial = {status:'off',message:'摄像头已关闭',data:null,prediction:null,faces:[],stats:null};
export function useLiveSignal(enabled) {
  const video = useRef(null), session = useRef(null);
  const [live,setLive] = useState(initial);
  const [memory,setMemory] = useState(null);
  useEffect(() => {
    if (!enabled) return;
    let mounted = true;
    const engine = new LiveSession({video:video.current,emit:patch => {if(mounted)setLive(previous => ({...previous,...patch}));}});
    session.current = engine;setLive(initial);
    const leave = () => {if(document.hidden)engine.stop();};
    const unload = () => engine.stop();
    document.addEventListener('visibilitychange',leave);window.addEventListener('pagehide',unload);
    return () => {mounted=false;engine.stop();session.current=null;document.removeEventListener('visibilitychange',leave);window.removeEventListener('pagehide',unload);};
  },[enabled]);
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    fetch('/api/live-info',{signal:controller.signal}).then(r=>r.json()).then(setMemory).catch(()=>{});
    return ()=>controller.abort();
  },[enabled, Math.floor((live.stats?.frameId || 0)/20)]);
  return {...live,video,memory,start:()=>session.current?.start(),stop:()=>session.current?.stop(),
    pause:()=>session.current?.pause(),resume:()=>session.current?.resume(),select:box=>session.current?.select(box)};
}

const statusText = {off:'CAMERA OFF',requesting:'PERMISSION',waiting:'ACQUIRING',tracking:'LIVE',no_face:'NO FACE',
  target_lost:'TARGET LOST',paused:'PAUSED',camera_error:'CAMERA NOTICE',backend_error:'ENGINE RETRY',stale:'STALE',interrupted:'INTERRUPTED'};
export function LiveControls({live}) {
  const running = !['off','camera_error','requesting'].includes(live.status);
  return <>
    <div className="primary-controls live-controls">
      {!running ? <button className="primary-button" disabled={live.status==='requesting'} onClick={live.start}>{live.status==='requesting'?'等待摄像头授权':'开启摄像头'}<span aria-hidden="true">↗</span></button>
        : <button className="primary-button" onClick={live.status==='paused'?live.resume:live.pause}>{live.status==='paused'?'恢复分析':'暂停分析'}<span aria-hidden="true">{live.status==='paused'?'↗':'Ⅱ'}</span></button>}
      {(running || live.status==='requesting') && <button className="text-button" onClick={live.stop}>{live.status==='requesting'?'取消开启':'关闭摄像头'} <span>×</span></button>}
    </div>
    <p className="input-requirement">授权后仅采集视频，不采集音频。<br/>采样帧 → 此 Mac 的 localhost 接口 → 内存中检测与推理。<br/>不录制、不保存、不传往外部服务；离开此页即关闭。</p>
    <p className="photo-notice">默认跟踪最大人脸；点击框或下方编号可切换。<br/>按位置连续跟踪，非身份识别；交叉或遮挡后请核对目标。</p>
    {live.status==='camera_error' && <div className="error-box" role="alert">{live.message}</div>}
  </>;
}

export function LiveWindow({live}) {
  const selected = live.data?.selected_face_id;
  const videoOn = !['off','requesting','camera_error'].includes(live.status);
  const [mirror,setMirror] = useState(true);
  return <div className={`instrument live-instrument state-${live.status}`}>
    <div className="instrument-top mono"><span><span className="green">⌖</span> LIVE OBSERVATION</span><span className="camera-indicator"><i className={videoOn?'on':''}/>{statusText[live.status]}</span></div>
    <div className="live-viewport">
      <div className="live-video-plane" style={{aspectRatio:live.data?.frame_size?.join(' / ') || '4 / 3'}}>
        <video ref={live.video} autoPlay playsInline muted aria-label="本机摄像头实时预览" className={mirror?'mirrored':''}/>
        <div className="face-overlay" aria-label="本帧检测到的人脸">
          {live.faces.map(face => <button key={face.id} className={`tracking-box ${selected===face.id?'is-target':''}`} aria-label={`跟踪人脸 ${face.id}`} aria-pressed={selected===face.id}
            onClick={()=>live.select(face.box)} style={{left:`${(mirror?1-face.box[0]-face.box[2]:face.box[0])*100}%`,top:`${face.box[1]*100}%`,width:`${face.box[2]*100}%`,height:`${face.box[3]*100}%`}}>
            <span className="tracking-label mono">{selected===face.id?'TARGET':'FACE'} / {String(face.id).padStart(2,'0')}</span><i className="tl"/><i className="tr"/><i className="bl"/><i className="br"/>
          </button>)}
        </div>
        {!videoOn && <div className="camera-idle"><span className="camera-aperture" aria-hidden="true">⌖</span><span className="mono">A LIVE STUDY OF EXPRESSION</span><p>{live.status==='requesting'?'等待你的授权':'让表情，进入画面。'}</p><small>只有点击开启后，才会请求摄像头权限。</small></div>}
      </div>
      <div className="live-frame-note mono"><span>{mirror?'MIRRORED PREVIEW':'NATURAL PREVIEW'}</span><span>LOCAL / NO RECORDING</span></div>
    </div>
    <div className="instrument-bottom"><span className="live-status" role="status" aria-live="polite"><i/>{live.message || (live.status==='tracking'?`正在跟踪人脸 ${selected} · ${live.faces.length} 张人脸`:'等待采样')}</span><button className="text-button mirror-button" aria-pressed={mirror} onClick={()=>setMirror(!mirror)}>镜像 {mirror?'开':'关'}</button></div>
  </div>;
}

export function LiveDetails({live}) {
  const [raw,setRaw] = useState(false);
  const prediction = raw ? live.data?.prediction : live.prediction;
  const stats = live.stats;
  return <div className="live-details">
    <div className="live-measurement-strip mono" aria-label="实际采样测量">
      <span>MODEL <strong>{stats?.inferenceMs!=null?`${stats.inferenceMs.toFixed(1)} ms`:'—'}</strong></span>
      <span>ROUND TRIP <strong>{stats?`${stats.roundTripMs.toFixed(1)} ms`:'—'}</strong></span>
      <span>UPDATES <strong>{live.status==='tracking' && stats?.hz?`${stats.hz.toFixed(2)} Hz`:'—'}</strong></span>
      <span>FRAME <strong>{stats?String(stats.frameId).padStart(4,'0'):'—'}</strong></span>
    </div>
    <div className="analysis-deck">
      <section className="input-section live-input-study">
        <div className="section-label"><h2>当前跟踪与模型输入 <span>/ LIVE INPUT</span></h2><span className="mono">48² / L</span></div>
        <div className="live-target-list" role="group" aria-label="选择实时人脸目标">
          {live.faces.length?live.faces.map(f=><button className="text-button" key={f.id} aria-pressed={f.id===live.data?.selected_face_id} onClick={()=>live.select(f.box)}>人脸 {f.id}{f.id===live.data?.selected_face_id?' · 当前目标':' ↗'}</button>):<p>{live.status==='paused'?'分析已暂停':live.status==='off'?'等待开启摄像头':'尚无当前有效人脸'}</p>}
        </div>
        <div className="live-crop-study">
          {live.data?.input?<img src={live.data.input.preview} alt="当前目标经固定方形裁剪后生成的真实48×48灰度模型输入"/>:<span className="empty-crop mono">48²</span>}
          <p>先检测人脸，再裁剪与转灰度。<br/>YuNet → square-edge-v1 → LANCZOS 48²<br/><span className="mono">T3 + w16 + w32 / RAW + FLIP / ⅓</span></p>
        </div>
        <p className="data-note">预览持续播放，分析受控采样。测量条为最近一次已完成采样；更新频率按最近最多 12 次响应计算，不是视频帧率。</p>
        <p className="data-note">{live.memory?`服务进程启动以来峰值内存 ${(live.memory.peak_rss_bytes/1048576).toFixed(1)} MiB；不含浏览器，每 20 次采样刷新。`:'等待本机内存观测。'}</p>
      </section>
      <div className="live-spectrum-section">
        <div className="probability-mode" role="group" aria-label="概率显示方式"><button aria-pressed={!raw} onClick={()=>setRaw(false)}>平滑显示</button><button aria-pressed={raw} onClick={()=>setRaw(true)}>原始模型输出</button></div>
        <Spectrum prediction={prediction}/>
        <p className="data-note">{raw?'此处显示本帧原始七类概率，未经平滑。':'仅实时显示使用时间平滑（450 ms）；左侧大字始终为平滑结果。模型原始输出、照片结果及历史成绩均保持不变。'}</p>
        <details className="live-raw-details"><summary>核对本帧完整原始概率与平滑值</summary>
          <table><caption>帧 {live.data?.frame_id || '—'} · 原始输出 / 仅显示平滑</caption><thead><tr><th>类别</th><th>原始概率</th><th>平滑概率</th></tr></thead><tbody>{live.data?.prediction?.probabilities.map((p,i)=><tr key={p.label}><th>{p.emotion_zh}</th><td className="mono">{p.probability.toPrecision(7)}</td><td className="mono">{live.prediction?.probabilities[i]?.probability.toPrecision(7) || '—'}</td></tr>)}</tbody></table>
        </details>
      </div>
    </div>
  </div>;
}
