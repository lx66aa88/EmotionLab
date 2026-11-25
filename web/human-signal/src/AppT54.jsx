import {useEffect,useLayoutEffect,useRef,useState} from 'react';
import PhotoApp from './AppT53.jsx';
import {LiveSession} from './liveSession.js';
import SignalField from './components/SignalField.jsx';
import Spectrum from './components/LiveSpectrum.jsx';
import {FrozenFaceBoxes, FrozenFaceStudy} from './components/FrozenFrame.jsx';
import './styles-t54.css';

function Header({light,setLight}) {
  return <header className="site-header"><a className="brand" href="#observation" aria-label="EmotionLab 首页"><svg viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M2 11V2h9m10 0h9v9m0 10v9h-9m-10 0H2v-9M11 16h10m-5-5v10" stroke="currentColor" strokeWidth="1.6"/></svg><span>EMOTION<span className="brand-lab">LAB</span><sup>↗</sup></span></a><span className="header-center mono">EXPRESSION RESEARCH / VOL. 005</span><div className="header-actions"><a className="text-button" href="#live-method">方法与边界 ↗</a><button className="theme-button" aria-label={light?'切换暗色模式':'切换明亮模式'} onClick={()=>setLight(!light)}>◐</button></div></header>;
}
export function LiveApp({createSession = options=>new LiveSession(options), Signal, updateSignal, FreezeSession,
  Chart = Spectrum, theme}) {
  const video=useRef(null), canvas=useRef(null), session=useRef(null);
  const frozenCanvas=useRef(null), freezeSession=useRef(null);
  const [frozen,setFrozen]=useState(null), [freezeNotice,setFreezeNotice]=useState('');
  const [state,setState]=useState({status:'off',message:'摄像头尚未开启',faces:[]});
  const [localLight,setLight]=useState(false), [view,setView]=useState('smooth'), [mirrored,setMirrored]=useState(true);
  const light=theme?.light ?? localLight;
  const [videoRatio,setVideoRatio]=useState(16 / 9);
  useEffect(()=>{document.documentElement.dataset.theme=light?'light':'dark';},[light]);
  useLayoutEffect(()=>{
    const update = updateSignal
      ? next => setState(previous => ({...next, visualSignal: updateSignal(previous.visualSignal, next)}))
      : setState;
    const live=createSession({video:video.current,canvas:canvas.current,onChange:next=>{
      if (!next.camera) {
        freezeSession.current?.clear();
        setFreezeNotice('');
      }
      update(next);
    }});
    session.current=live;
    const freeze=FreezeSession && new FreezeSession({live,canvas:frozenCanvas.current,onChange:setFrozen});
    freezeSession.current=freeze;
    const hide=()=>{if(document.hidden) live.close('页面已隐藏，摄像头已关闭');};
    const leave=()=>live.close('已离开页面，摄像头已关闭');
    document.addEventListener('visibilitychange',hide); window.addEventListener('pagehide',leave);
    return ()=>{
      document.removeEventListener('visibilitychange',hide);window.removeEventListener('pagehide',leave);
      if (freeze) {freeze.onChange=()=>{};freeze.clear();}
      live.onChange=()=>{};live.close();
    };
  },[]);
  const raw=state.data?.raw_prediction, prediction=state.smoothed, metrics=state.metrics;
  const hasSignal=state.status==='ok' && !!prediction;
  const displayedPrediction = frozen ? frozen.result?.prediction
    : hasSignal ? (view === 'raw' ? raw : prediction) : null;
  const visualCategory = !frozen && view === 'smooth' ? state.visualSignal?.category : displayedPrediction?.label;
  const headline = Signal
    ? displayedPrediction?.probabilities[visualCategory ?? displayedPrediction.label]
    : hasSignal ? prediction.probabilities[prediction.label] : null;
  const held = Signal && headline && headline.label !== displayedPrediction.label;
  const source = frozen ? 'frozen' : view === 'raw' ? 'raw' : 'ema';
  const viewSwitch = !frozen && <div className="live-probability-switch" role="group" aria-label="实时概率视图">
      <button aria-pressed={view==='smooth'} onClick={()=>setView('smooth')}>平滑显示 · EMA</button>
      <button aria-pressed={view==='raw'} onClick={()=>setView('raw')}>本帧原始 · RAW</button>
    </div>;
  const spectrum = <div className="live-spectrum">
    {!theme && viewSwitch}
    <Chart source={source} raw={view==='raw'} singleFrame={!!frozen} prediction={displayedPrediction}
      sculptureLabel={Signal ? headline?.label : undefined} controls={theme ? viewSwitch : undefined}/>
    {!theme && !frozen && <p className="data-note">{view==='smooth'
      ? Signal ? 'EMA（α=0.45）。领先接近时短暂保留雕塑，绿色标记仍指向本帧 EMA 最高值。' : '本图为实时显示 EMA（α=0.45），仅用于减少抖动。'
      : '本图为冻结三模型输出，未经平滑。'} 平滑不改变模型输出或历史指标。</p>}
  </div>;
  const selected=state.data?.selected_id;
  const fmt=n=>Number.isFinite(n)?n.toFixed(0)+' ms':'—';
  const frameRatio = frozen ? frozen.width / frozen.height : state.camera ? videoRatio : 16 / 9;
  const updateVideoRatio = ({currentTarget: {videoWidth, videoHeight}}) => {
    if (videoWidth && videoHeight) setVideoRatio(videoWidth / videoHeight);
  };
  const freezeNow=()=>setFreezeNotice(freezeSession.current.freeze());
  const chooseFrozen=id=>freezeSession.current.choose(id);
  return <div className={`app live-app status-${state.status}`} data-live-status={state.status}
    data-frozen-phase={frozen?.phase} data-capture-id={frozen?.id}>
    {!theme && <><a className="skip-link" href="#observation">跳到观测台</a><Header light={light} setLight={setLight}/></>}
    <main id="observation" tabIndex={theme ? -1 : undefined}>
      <div className="mastline">
        <span className="mono">{theme ? frozen ? 'FROZEN FRAME' : 'LIVE' : 'HUMAN SIGNAL'}
          <span className="muted">{theme ? frozen ? ' / 定格分析' : ' / 实时观测' : ' / 人类表情信号观测所'}</span></span>
        <span className="connection mono"><i className={state.camera?'ready':''}/>{theme
          ? frozen ? '摄像头仍开启' : state.camera ? state.paused ? '分析暂停 · 预览开启' : '摄像头已开启' : '摄像头关闭'
          : frozen ? 'FROZEN FRAME' : state.camera ? state.paused?'LIVE · PAUSED':'LIVE · LOCAL ONLY':'CAMERA · OFF'}</span>
      </div>
      <section className="observatory live-observatory" aria-label="实时表情观测台">
        <div className="editorial">
          {!theme && <div className="scene-label mono"><span className="green">02</span><span>{frozen?'FROZEN FRAME / 定格分析':'OBSERVE THE PRESENT'}</span></div>}
          {headline ? <div className="result-editorial live-result">
            <p className="result-kicker">{frozen ? '单帧分析 · 原始模型输出' : Signal && view==='raw' ? '当前目标 · 本帧原始 / RAW' : '当前目标 · 平滑显示 / EMA 0.45'}{held && ' · 视觉保持'}</p>
            <h1 className={`result-title ${headline.emotion.length>6?'long-title':''}`}>{headline.emotion.toUpperCase()}<span className="result-dot">.</span></h1>
            <div className="result-caption"><span className="result-zh">{headline.emotion_zh}</span><span className="model-score mono">{(headline.probability*100).toFixed(theme ? 2 : 1)}<small>%</small></span></div>
            <p className="live-raw-summary">{frozen ? `三模型推理 ${fmt(frozen.result.inference_ms)} · 定格人脸 ${frozen.face.id}` : Signal && view==='raw'
              ? <span className="mono">FRAME {metrics?.frameId}</span>
              : <>本帧原始最高：{raw.emotion} · {raw.emotion_zh}<br/><span className="mono">{(raw.probabilities[raw.label].probability*100).toFixed(2)}% / FRAME {metrics?.frameId}</span></>}</p>
          </div> : frozen || (theme && state.camera) ? <h1 className="frozen-title">{frozen ? '定格分析' : '实时观测'}</h1>
            : <div className="title-block"><h1>HUMAN<br/><span>SIGNAL</span><sup>↗</sup></h1><p className="hero-cn">让表情，<br/>发生在此刻。</p><p className="hero-en">A live study.<br/>One face. One present moment.</p></div>}
          <div className="primary-controls live-controls">
            {!state.camera ? <><button className="primary-button" disabled={state.status==='opening'} onClick={()=>session.current.open()}>{state.status==='opening'?'等待摄像头授权':'开启摄像头'}<span aria-hidden="true">↗</span></button>{state.status==='opening'&&<button className="text-button" onClick={()=>session.current.close('已取消摄像头授权等待')}>取消开启 ×</button>}</> : <>
              {FreezeSession && <button className="primary-button freeze-action" onKeyDown={event=>{
                if (event.repeat && (event.key === 'Enter' || event.key === ' ')) event.preventDefault();
              }} onClick={event=>{
                if (event.detail > 1) return;
                if (frozen) {freezeSession.current.resume();setFreezeNotice('');}
                else freezeNow();
              }}>
                <span className="freeze-action-label">{frozen?'继续实时识别':'定格并分析'}<small className="mono" lang="en">{frozen?'RESUME LIVE':'FREEZE & ANALYZE'}</small></span>
                <span aria-hidden="true">{frozen?'↗':'⌖'}</span>
              </button>}
              {frozen ? <button className="text-button refreeze-action" disabled={['detecting','analyzing'].includes(frozen.phase)} onClick={freezeNow}>重新定格最新画面</button>
                : <button className={FreezeSession?'text-button':'primary-button'} onClick={()=>state.paused?session.current.resume():session.current.pause()}>{state.paused?'恢复分析':'暂停分析'} <span aria-hidden="true">{state.paused?'↗':'Ⅱ'}</span></button>}
              <button className="text-button" onClick={()=>session.current.close()}>关闭摄像头 <span>×</span></button>
            </>}
          </div>
          {theme ? <p className="input-requirement">{frozen ? '定格期间摄像头保持开启，画面停止采样。' : '视频在这台 Mac 上处理，不采集音频或保存画面。'}</p>
            : <p className="input-requirement">仅在点击后请求摄像头权限 · 不采集音频。<br/>采样画面仅发送至此 Mac 的同源 localhost 接口。<br/>不录制、不保存画面，不上传第三方。</p>}
          <div className={`live-notice ${frozen?.phase==='error' || ['camera_error','backend_error'].includes(state.status)?'has-error':''}`} role="status" aria-live="polite">{freezeNotice || frozen?.message || state.message}</div>
          {!frozen && (!theme || state.faces.length > 1) && <p className="live-target-rule">{theme
            ? '点击人脸框或编号切换目标。交叉或快速移动后，请重新确认目标。'
            : <>首次选择最大人脸，后续按位置连续性跟踪。<br/>多人时点击框或下方编号切换；不识别身份。<br/>交叉、快速移动时请重新确认目标。</>}</p>}
        </div>
        <div className="instrument live-instrument">
          <div className="instrument-top mono"><span><span className="green">⌖</span> {frozen?'FROZEN FRAME':'LIVE OBSERVATION'}</span><span className="live-indicator">{frozen?'单帧分析':state.camera?'VIDEO ON':'STANDBY'}</span></div>
          <div className="live-viewport">
            <div className={`live-frame ${mirrored?'mirrored':''}${frozen?' is-frozen':''}`} style={{aspectRatio:frameRatio, '--frame-ratio':frameRatio}}>
              <video ref={video} autoPlay playsInline muted aria-label="本机摄像头实时预览" aria-hidden={!!frozen}
                className={state.camera?'visible':''} onLoadedMetadata={updateVideoRatio} onResize={updateVideoRatio}/>
              {FreezeSession && <canvas ref={frozenCanvas} className="frozen-frame-canvas" hidden={!frozen}
                role="img" aria-label="点击时捕获的定格画面"/>}
              {frozen && <><span key={frozen.id} className="frozen-capture-outline" aria-hidden="true"/>
                <FrozenFaceBoxes frame={frozen} mirrored={mirrored} onChoose={chooseFrozen}/></>}
              {!state.camera && <div className="live-empty"><div className="live-aperture"><span className="corner tl"/><span className="corner tr"/><span className="corner bl"/><span className="corner br"/><SignalField light={light}/></div><span className="mono">CAMERA IS OFF · YOUR MOMENT IS YOURS</span></div>}
              {state.camera && state.faces.map(face=>{const [x,y,w,h]=face.normalized_box;return <button key={face.id} disabled={state.paused} className={`face-track ${selected===face.id?'tracked':''}`} style={{left:`${(mirrored?1-x:x)*100}%`,top:`${y*100}%`,width:`${w*100}%`,height:`${h*100}%`}} aria-label={`跟踪人脸 ${face.id}${selected===face.id?'，当前目标':''}`} onClick={()=>session.current.choose(face)}><span className="corner tl"/><span className="corner tr"/><span className="corner bl"/><span className="corner br"/><span className="track-label mono">{selected===face.id?'TARGET':'FACE'} {String(face.id).padStart(2,'0')}</span></button>;})}
            </div>
            <span className="live-stage-note mono">{frozen ? '单帧分析 / SINGLE FRAME' : state.camera ? state.paused?'PREVIEW ONLY / ANALYSIS PAUSED':hasSignal?'SAMPLED FACE / LOCAL INFERENCE':'WAITING FOR A VALID SIGNAL':'NO CAPTURE BEFORE CONSENT'}</span>
          </div>
          <div className="instrument-bottom"><span className="live-status"><i className={headline?'signal-current':''}/>{frozen ? `已定格 · ${frozen.width} × ${frozen.height}` : state.status==='ok'?`当前目标 ${selected} · ${state.faces.length} 张人脸`:state.status==='no_face'?'未检测到人脸':state.status==='paused'?'分析已暂停':state.camera?'等待有效结果':'摄像头关闭'}</span><button className="text-button mirror-toggle" aria-pressed={mirrored} onClick={()=>setMirrored(!mirrored)}>{mirrored?'镜像预览':'原向预览'} ↔</button></div>
        </div>
      </section>
      {frozen ? <div className="live-telemetry frozen-telemetry mono" aria-label="单帧分析耗时">
        <div><span>CAPTURE / 定格</span><strong>{fmt(frozen.captureMs)}</strong></div>
        <div><span>DETECT / 定位与裁剪</span><strong>{fmt(frozen.detectMs)}</strong></div>
        <div><span>MODEL / 三模型推理</span><strong>{fmt(frozen.result?.inference_ms)}</strong></div>
      </div> : <div className="live-telemetry mono" aria-label="真实实时测量"><div><span>MODEL / 推理</span><strong>{fmt(metrics?.inferenceMs)}</strong></div><div><span>DETECT / 定位</span><strong>{fmt(metrics?.detectMs)}</strong></div><div><span>END TO END / 采样至结果</span><strong>{fmt(metrics?.roundTripMs)}</strong></div><div><span>UPDATE / 实际更新</span><strong>{Number.isFinite(metrics?.updateHz)?metrics.updateHz.toFixed(2)+' Hz':'等待测量'}</strong></div><div><span>SAMPLE / 当前间隔</span><strong>{fmt(metrics?.intervalMs)}</strong></div></div>}
      <div className={`analysis-deck live-analysis${Signal ? ' with-seven-signals' : ''}${frozen?.phase==='ok'?' frozen-result-deck':''}`}>
        {Signal && <><Signal prediction={displayedPrediction} category={headline?.label}
          status={frozen?.phase ?? state.status} frameId={frozen?.id ?? metrics?.frameId} source={source}/>{spectrum}</>}
        {frozen ? <FrozenFaceStudy frame={frozen} onChoose={chooseFrozen}/> : <section className="input-section" aria-labelledby="live-input-title"><div className="section-label"><h2 id="live-input-title">当前目标与模型输入 <span>/ FACE STUDY</span></h2></div><div className="live-face-picker">{state.faces.map(face=><button key={face.id} aria-pressed={selected===face.id} onClick={()=>session.current.choose(face)}>人脸 {String(face.id).padStart(2,'0')}{selected===face.id?' · 当前目标':''}</button>)}{state.camera && !state.paused && <button onClick={()=>session.current.choose(null)}>重选最大人脸 ↶</button>}</div>
          {state.data?.input_preview && hasSignal ? <div className="live-input-study"><img src={state.data.input_preview} alt="本帧经人脸裁剪后的实际48×48、8位L灰度模型输入"/><p><span className="mono">48 × 48 / L / FLOAT32 ÷ 255</span><br/>先检测人脸，再裁剪与预处理。<br/>三模型 × 原图与水平翻转。</p></div> : <p className="live-empty-copy">{state.camera?'等待清晰人脸采样。当前没有有效预测。':'开启后展示实际人脸模型输入。'}</p>}
          <p className="data-note">{state.data?.quality ? `清晰度 ${state.data.quality.sharpness.toFixed(1)} · 灰度标准差 ${state.data.quality.contrast.toFixed(1)}。仅作模糊/低对比显示保护。` : '无脸、目标消失、低质量或超时会清空预测。'}<br/>框来自最近一次采样检测，并非逐视频帧定位。</p>
        </section>}
        {!Signal && spectrum}
      </div>
      {!frozen && <details className="live-details"><summary>核对七类原始概率与平滑值 <span className="mono">RAW / DISPLAY ↗</span></summary><table><caption>同一采样帧；原始数值不改写。无有效当前结果时留空。</caption><thead><tr><th>固定类别</th><th>本帧原始</th><th>平滑显示</th></tr></thead><tbody>{['Angry','Disgust','Fear','Happy','Sad','Surprise','Neutral'].map((name,i)=><tr key={name}><th>{i} / {name}</th><td data-raw={hasSignal?raw.probabilities[i].probability:undefined}>{hasSignal?raw.probabilities[i].probability.toPrecision(10):'—'}</td><td data-smoothed={hasSignal?prediction.probabilities[i].probability:undefined}>{hasSignal?prediction.probabilities[i].probability.toPrecision(10):'—'}</td></tr>)}</tbody></table></details>}
      <div className="ethics-note"><span className="note-symbol">↳</span><p>我们观测表情的信号，不替你定义感受。<span>模型概率未经校准，不代表真实内心情绪，不用于心理或医疗诊断。自然摄像头场景准确率未独立验证。</span></p></div>
      <section className="live-method" id="live-method"><span className="eyebrow mono">THREE MODELS. ONE SIGNAL.</span><h2>画面流动，判断有节制。</h2><div><p>视频预览由浏览器独立刷新；初始约每秒 3 次采样，按编码、检测和推理的真实耗时自适应。最多一个请求，繁忙帧直接跳过；过期或先前会话结果不能回填。画面不刷新时停止重复采样。</p><p>固定 YuNet 双尺度定位 → 1.25 倍方形裁剪与边缘补齐 → L 灰度与 LANCZOS 48×48 → 原 T4 float32 / 255 → T3、w16、w32 原图/翻转各 ½、模型各 ⅓。三模型权重与七类标签保持不变。</p><p>七类原始概率保留；EMA 只影响实时显示，目标丢失或切换时重置。结果超过 1.8 秒失效。暂停保留视频预览；关闭、切回 PHOTO 或页面隐藏释放全部摄像头轨道与采样资源。推理已开始时可能在本机完成，迟到结果会被丢弃。</p><p>画面经内存发送到本页同源的 localhost 接口，不写入文件，不录制，不采集音频。当前页面没有外部图像服务。历史 PublicTest 72.610755% 仅为既有验证成果，不是本次摄像头准确率。</p></div></section>
    </main><footer><span className="footer-brand">HUMAN SIGNAL<span>© EMOTIONLAB / 2026</span></span><span className="mono">LIVE STUDY · LOCAL FIRST</span><span>本地运行 <span className="green">↗</span></span></footer><canvas ref={canvas} className="sr-only" aria-hidden="true"/>
  </div>;
}
export default function AppT54({Photo = PhotoApp, Live = LiveApp, GalleryHeader, Challenge}) {
  const [mode,setMode]=useState('photo');
  const [light,setLight]=useState(false);
  const theme=GalleryHeader ? {light,setLight} : undefined;
  const Stage=mode==='photo'?Photo:mode==='live'?Live:Challenge;
  const navigation=<nav className="capture-mode-bar" aria-label={Challenge?'HUMAN SIGNAL 模式':'PHOTO 或 LIVE 输入模式'}>
    {!GalleryHeader && <span className="mono">HUMAN SIGNAL <span className="muted">/ INPUT</span></span>}
    <div><button aria-pressed={mode==='photo'} onClick={()=>setMode('photo')}><span lang="en">PHOTO</span> <small>照片</small></button>
      <button aria-pressed={mode==='live'} onClick={()=>setMode('live')}><span lang="en">LIVE</span> <small>实时摄像头</small><i aria-hidden="true"/></button>
      {Challenge && <button className="challenge-mode-link" aria-pressed={mode==='challenge'} onClick={()=>setMode('challenge')}><span lang="en">CHALLENGE</span> <small>表情挑战</small></button>}</div>
    {!GalleryHeader && <span className="mono mode-local">ON THIS MAC ↗</span>}
  </nav>;
  return <>
    {GalleryHeader ? <GalleryHeader navigation={navigation} mode={mode} theme={theme}/> : navigation}
    <div className="capture-stage" key={mode}><Stage theme={theme}/></div>
  </>;
}
