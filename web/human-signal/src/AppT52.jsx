import { useEffect, useRef, useState } from 'react';
import './styles-t52.css';
import SignalField from './components/SignalField.jsx';
import Spectrum from './components/Spectrum.jsx';
import ProcessRail from './components/ProcessRail.jsx';
import PhotoStudy, { PhotoWindow } from './components/PhotoStudy.jsx';
import { preparePhoto, formatBytes } from './photoPreparation.js';

function Arrow({diagonal = false}) { return <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d={diagonal ? 'M5 19 19 5M5 5h14v14' : 'M4 12h15m-6-6 6 6-6 6'} stroke="currentColor" strokeWidth="1.6"/></svg>; }
function Mark() { return <svg viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M2 11V2h9m10 0h9v9m0 10v9h-9m-10 0H2v-9M11 16h10m-5-5v10" stroke="currentColor" strokeWidth="1.6"/></svg>; }
const stageNames = {check: '正在检查输入', preprocess: '正在标准化像素', infer: '三模型推理中', compose: '正在生成结果'};
const examples = [0, 1, 2];
const userError = (error, fallback) => error instanceof TypeError ? '本地服务连接中断，请检查启动终端后重试。' : error.message || fallback;

export default function App() {
  const [mode, setMode] = useState('photo');
  const [photoInfo, setPhotoInfo] = useState(null);
  const [photo, setPhoto] = useState(null);
  const [selectedFace, setSelectedFace] = useState(null);
  const [photoPreparation, setPhotoPreparation] = useState(null);
  const [health, setHealth] = useState(null);
  const [connectionError, setConnectionError] = useState('');
  const [scene, setScene] = useState('idle');
  const [input, setInput] = useState(null);
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [stage, setStage] = useState(null);
  const [events, setEvents] = useState([]);
  const [error, setError] = useState('');
  const [matrix, setMatrix] = useState(true);
  const [light, setLight] = useState(false);
  const [details, setDetails] = useState(false);
  const [pixelIndex, setPixelIndex] = useState(1176);
  const [drag, setDrag] = useState(false);
  const upload = useRef(null);
  const controller = useRef(null);
  const generation = useRef(0);
  const imageURL = useRef(null);
  const samples = useRef(null);
  const resultTitle = useRef(null);
  const busy = ['analyzing', 'inspecting', 'preparing', 'detecting'].includes(scene);

  async function connect() {
    setConnectionError('');
    try { const response = await fetch('/api/health'); if (!response.ok) throw new Error(); setHealth(await response.json()); }
    catch { setConnectionError('本地模型服务未连接。请检查启动终端，然后重试。'); }
  }
  useEffect(() => { fetch('/api/photo-info').then(r => r.json()).then(setPhotoInfo).catch(() => setPhotoInfo({ready: false, detail: '人脸检测服务未连接，可使用预裁剪入口。'})); connect(); return () => { controller.current?.abort(); if (imageURL.current) URL.revokeObjectURL(imageURL.current); }; }, []);
  useEffect(() => { document.documentElement.dataset.theme = light ? 'light' : 'dark'; }, [light]);

  function releaseImage() { if (imageURL.current) URL.revokeObjectURL(imageURL.current); imageURL.current = null; }
  function reset() {
    generation.current += 1;
    controller.current?.abort(); releaseImage();
    setPhoto(null); setSelectedFace(null); setPhotoPreparation(null); setDrag(false);
    setInput(null); setPreview(null); setResult(null); setStage(null); setEvents([]); setError(''); setScene('idle'); setMatrix(true); setPixelIndex(1176);
    if (upload.current) upload.current.value = '';
  }
  async function capture(file, source = '本地图片') {
    if (!file) return;
    controller.current?.abort();
    const current = ++generation.current;
    controller.current = new AbortController();
    setError(''); setResult(null); setPreview(null); setEvents([]); setStage(null); setInput(null); releaseImage(); setScene('inspecting');
    if (file.size > 1024 * 1024) { setError('图片超过 1 MB。请选择已裁剪的 48×48 灰度人脸。'); setScene('idle'); return; }
    try {
      const response = await fetch('/api/inspect', {method: 'POST', headers: {'Content-Type': 'application/octet-stream'}, body: file, signal: controller.current.signal});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || '输入检查未完成。');
      if (current !== generation.current) return;
      imageURL.current = URL.createObjectURL(file);
      setInput({file, name: file.name || 'face.png', url: imageURL.current, source});
      setPreview(data); setScene('capture'); setMatrix(false);
    } catch (e) { if (e.name !== 'AbortError' && current === generation.current) { setError(userError(e, '无法连接本地服务，请检查启动终端。')); setScene('idle'); } }
  }
  function switchMode(next) { reset(); setMode(next); }
  async function detectPhoto(file) {
    if (!file) return;
    reset();
    const current = generation.current;
    controller.current = new AbortController();
    setScene('preparing');
    try {
      const prepared = await preparePhoto(file, {signal: controller.current.signal});
      if (current !== generation.current) return;
      setPhotoPreparation(prepared.info); setScene('detecting');
      const response = await fetch('/api/detect', {method: 'POST', headers: {'Content-Type': 'application/octet-stream'}, body: prepared.file, signal: controller.current.signal});
      const data = await response.json();
      if (current !== generation.current) return;
      if (!response.ok) throw new Error(data.detail || '人脸检测未完成。');
      setPhoto(data); setSelectedFace(data.count === 1 ? data.faces[0].id : null); setScene('selecting');
      if (!data.count) setError(data.message);
    } catch (e) { if (e.name !== 'AbortError' && current === generation.current) {setError(userError(e, '人脸检测未完成。')); setScene('idle');} }
  }
  function chooseFace(id) {
    if (busy) return;
    generation.current += 1; controller.current?.abort(); releaseImage();
    setSelectedFace(id); setInput(null); setPreview(null); setResult(null); setStage(null); setEvents([]); setError(''); setScene('selecting');
  }
  async function confirmCrop() {
    const face = photo?.faces.find(f => f.id === selectedFace);
    if (!face || scene !== 'cropping') return;
    const bytes = Uint8Array.from(atob(face.input_preview.split(',')[1]), c => c.charCodeAt(0));
    await capture(new File([bytes], 'confirmed-face.png', {type: 'image/png'}), `普通照片中的第 ${face.id} 张人脸`);
  }
  function receive(file) { return mode === 'photo' ? detectPhoto(file) : capture(file); }
  async function sample(index) {
    if (busy) return;
    reset(); setMode('cropped');
    const current = ++generation.current;
    controller.current?.abort(); controller.current = new AbortController();
    setScene('inspecting'); setError('');
    try {
      const response = await fetch(`/api/examples/${index}`, {signal: controller.current.signal});
      if (!response.ok) throw new Error('样例读取失败。');
      const file = new File([await response.blob()], `public_${index}.png`, {type: 'image/png'});
      if (current === generation.current) await capture(file, `已有 PublicTest 样例 0${index + 1}`);
    } catch (e) { if (e.name !== 'AbortError' && current === generation.current) { setError(userError(e, '样例读取失败。')); setScene('idle'); } }
  }
  async function analyze() {
    if (!input || busy) return;
    const current = ++generation.current;
    controller.current = new AbortController();
    setError(''); setResult(null); setEvents([]); setScene('analyzing'); setStage('check'); setMatrix(true);
    try {
      const response = await fetch('/api/analyze', {method: 'POST', headers: {'Content-Type': 'application/octet-stream'}, body: input.file, signal: controller.current.signal});
      if (!response.ok) { const data = await response.json(); throw new Error(data.detail || '分析请求未完成。'); }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '', finished = false;
      while (true) {
        const {done, value} = await reader.read();
        buffer += decoder.decode(value, {stream: !done});
        const lines = buffer.split('\n'); buffer = lines.pop();
        for (const line of lines) {
          if (!line.trim()) continue;
          const event = JSON.parse(line);
          if (current !== generation.current) { await reader.cancel(); return; }
          if (event.event === 'stage') { setStage(event.stage); setEvents(previous => [...previous, event.stage]); }
          if (event.event === 'error') throw new Error(event.detail);
          if (event.event === 'result') {
            // No synthetic numbers, smoothing or probability reordering.
            setResult(event); setScene('reveal'); finished = true;
            requestAnimationFrame(() => resultTitle.current?.focus({preventScroll: true}));
          }
        }
        if (done) break;
      }
      if (!finished) throw new Error('本地连接中断，未收到完整结果。请重试。');
    } catch (e) { if (e.name !== 'AbortError' && current === generation.current) { setError(userError(e, '推理连接失败。')); setScene('capture'); } }
  }

  const prediction = result?.prediction;
  const face = photo?.faces.find(f => f.id === selectedFace);
  const stateText = scene === 'preparing' ? '正在本机自动适配照片' : scene === 'detecting' ? '正在本机检测人脸' : scene === 'selecting' ? photo?.count ? selectedFace ? '请选择并确认这张人脸' : '请选择一张候选人脸' : '没有人脸，未运行分类' : scene === 'cropping' ? '请检查并确认灰度裁剪' : scene === 'inspecting' ? '正在检查图片' : scene === 'analyzing' ? stageNames[stage] : scene === 'reveal' ? '信号已生成' : scene === 'capture' ? '输入已就绪' : '等待视觉信号';
  const selectedValue = preview?.pixels[pixelIndex];
  const showPhoto = photo && (!preview || !matrix);
  return <div className={`app scene-${scene}`}>
    <a className="skip-link" href="#observation">跳到观测台</a>
    <header className="site-header">
      <a className="brand" href="#" aria-label="EmotionLab 首页"><Mark/><span>EMOTION<span className="brand-lab">LAB</span><sup>↗</sup></span></a>
      <div className="header-center mono">EXPRESSION RESEARCH / VOL. 005</div>
      <div className="header-actions"><button className="text-button method-button" onClick={() => {setDetails(!details); if (!details) requestAnimationFrame(() => document.getElementById('method')?.scrollIntoView({block: 'start'}));}} aria-expanded={details} aria-controls="method">方法与边界 <span>↗</span></button><button className="theme-button" onClick={() => setLight(!light)} aria-label={light ? '切换暗色模式' : '切换明亮模式'} title={light ? '暗色模式' : '明亮模式'}><span aria-hidden="true">{light ? '◑' : '◐'}</span></button></div>
    </header>
    <main id="observation">
      <div className="mastline"><span className="mono">HUMAN SIGNAL <span className="muted">/ 人类表情信号观测所</span></span><span className="connection mono"><i className={health ? 'ready' : ''}/>{health ? 'LOCAL ENGINE · READY' : connectionError ? 'LOCAL ENGINE · OFFLINE' : 'CONNECTING LOCAL ENGINE'}</span></div>
      <section className="observatory" aria-label="人脸表情观测台">
        <div className="editorial">
          <div className="scene-label mono"><span className="green">{scene === 'reveal' ? '04' : scene === 'analyzing' ? '03' : preview ? '02' : '01'}</span><span>{scene === 'reveal' ? 'SIGNAL REVEALED' : scene === 'analyzing' ? 'READING THE SIGNAL' : preview ? 'CAPTURE THE EXPRESSION' : 'A STUDY OF HUMAN EXPRESSION'}</span></div>
          {prediction ? <div className="result-editorial" key={prediction.emotion}>
            <p className="result-kicker">这张图像的最高预测类别</p>
            <h1 ref={resultTitle} tabIndex={-1} className={`result-title ${prediction.emotion.length > 6 ? 'long-title' : ''}`}>{prediction.emotion.toUpperCase()}<span className="result-dot">.</span></h1>
            <div className="result-caption"><span className="result-zh">{prediction.emotion_zh}</span><span className="model-score mono">{(prediction.probabilities[prediction.label].probability * 100).toFixed(2)}<small>%</small></span></div>
            {photo && <p className="photo-source">本次预测使用普通照片中的第 {selectedFace} 张人脸<br/><span>演示预测 · 自然照片准确率未独立验证</span></p>}
            <p className="result-interpretation">一次对表情外观的模型判断。<br/>人的感受，始终比一个标签更丰富。</p>
          </div> : <div className="title-block"><h1>HUMAN<br/><span>SIGNAL</span><sup>↗</sup></h1><p className="hero-cn">每一个表情，<br/>都有迹可循。</p><p className="hero-en">Observe the expression.<br/>Understand the signal.</p></div>}
          <div className="input-modes" role="group" aria-label="输入方式"><button className={mode === 'photo' ? 'selected' : ''} aria-pressed={mode === 'photo'} onClick={() => switchMode('photo')}>普通照片 <span className="mono">PHOTO</span></button><button className={mode === 'cropped' ? 'selected' : ''} aria-pressed={mode === 'cropped'} onClick={() => switchMode('cropped')}>预裁剪灰度 <span className="mono">48² / L</span></button></div>
          <div className="primary-controls">
            <input ref={upload} type="file" id="face-file" accept={mode === 'photo' ? '.png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff,.heic,.heif' : '.png,.jpg,.jpeg,.bmp,.tif,.tiff'} className="sr-only" tabIndex={-1} onChange={e => {receive(e.target.files?.[0]); e.target.value = '';}} aria-label={mode === 'photo' ? '选择普通照片' : '选择已裁剪的 48×48 灰度人脸'}/>
            {scene === 'selecting' && photo?.count > 0 ? <button className="primary-button" disabled={!face} onClick={() => setScene('cropping')}>确认人脸，检查裁剪<Arrow/></button> : scene === 'cropping' ? <button className="primary-button" onClick={confirmCrop}>确认裁剪，准备分析<Arrow/></button> : preview ? <button className="primary-button" onClick={analyze} disabled={busy || !health}>{scene === 'analyzing' ? '正在分析' : result ? '再次分析' : '分析表情信号'}<Arrow/></button> : <button className="primary-button" onClick={() => upload.current.click()} disabled={busy || !health}>{scene === 'preparing' ? '自动适配照片中' : scene === 'detecting' ? '本机定位人脸中' : scene === 'inspecting' ? '检查图片中' : mode === 'photo' ? '选择普通照片' : '上传人脸图像'}<Arrow diagonal/></button>}
            {preview || busy || photo ? <button className="text-button reset-button" onClick={reset}>重置 <span>↺</span></button> : <button className="text-button" onClick={() => {switchMode('cropped'); requestAnimationFrame(() => samples.current?.scrollIntoView({block: 'center'}));}}>预裁剪样例 <span>↓</span></button>}
          </div>
          <p className="input-requirement">{mode === 'photo' ? <>直接选择照片，自动适配大小与格式。<br/>大图等比缩小，选脸后自动转为 48×48 灰度。<br/>原片 ≤128 MiB / 1 亿像素；HEIC 需浏览器支持。</> : <>已裁剪人脸 · 48×48 · 8 位灰度 · ≤1 MB</>}<br/>图片仅在本机处理，不保存上传记录。</p>
          {mode === 'photo' && photoPreparation && <div className="photo-preparation" role="status" aria-label="照片自动适配结果"><strong>{photoPreparation.converted ? '✓ 已自动适配' : '✓ 照片已符合要求'}</strong><span>{photoPreparation.originalSize.join(' × ')} · {formatBytes(photoPreparation.originalBytes)}<br/>→ {photoPreparation.outputSize.join(' × ')} · {formatBytes(photoPreparation.outputBytes)} · {photoPreparation.outputFormat}</span></div>}
          {mode === 'photo' && <p className="photo-notice">演示预测 · 自然照片准确率未独立验证。</p>}
          {photo && <div className="photo-actions"><button className="text-button" disabled={busy} onClick={() => upload.current.click()}>取消并重新上传 ↗</button>{face && scene !== 'selecting' && <button className="text-button" disabled={busy} onClick={() => chooseFace(selectedFace)}>重新选择人脸 ↶</button>}</div>}
          {mode === 'photo' && photoInfo && !photoInfo.ready && <div className="error-box" role="alert">{photoInfo.detail}</div>}
          {connectionError && <div className="error-box" role="alert">{connectionError}<button onClick={connect}>重新连接</button></div>}
          {error && <div className="error-box" role="alert"><span className="mono">INPUT / NOTICE</span><p>{error}</p><button onClick={() => upload.current.click()}>重新选择图片 ↗</button>{mode === 'photo' && <button onClick={() => switchMode('cropped')}>返回预裁剪灰度入口 →</button>}</div>}
        </div>
        <div className={`instrument ${drag ? 'drag-active' : ''}`} onDragOver={event => {event.preventDefault(); if (!busy) setDrag(true);}} onDragLeave={() => setDrag(false)} onDrop={event => {event.preventDefault(); setDrag(false); if (!busy) receive(event.dataTransfer.files?.[0]);}}>
          <div className="instrument-top mono"><span><span className="green">⌖</span> OBSERVATION WINDOW</span><span>{photo ? `${photo.photo.width} × ${photo.photo.height}` : '48 × 48'}</span></div>
          <div className={`viewport ${showPhoto ? 'photo-viewport' : ''}`}>
            <div className="measurement top mono"><span>00</span><span>12</span><span>24</span><span>36</span><span>48</span></div>
            <span className="vertical-note mono">{showPhoto ? (preview ? 'LOCAL FACE DETECTION / CONFIRMED CROP' : 'LOCAL FACE DETECTION / AWAITING CONFIRMATION') : preview ? 'ACTUAL MODEL INPUT / 48 × 48 L' : 'CONCEPT FIELD / NOT A PREDICTION'}</span>
            {showPhoto ? <PhotoWindow data={photo} selected={selectedFace} onSelect={chooseFace} showCrop={scene !== 'selecting'} disabled={busy}/> : <div className={`specimen ${preview ? 'has-image' : ''}`}>
              {preview && !matrix ? <img src={preview.preview} alt="经输入检查的原始 48×48 灰度人脸，无缩放或裁剪预处理" className="specimen-image"/> : <SignalField pixels={preview?.pixels} light={light} matrix={matrix}/>}
              <span className="corner tl"/><span className="corner tr"/><span className="corner bl"/><span className="corner br"/>
              {scene === 'analyzing' && <span className="scan-line" aria-hidden="true"/>}
            </div>
            }
            {!preview && !photo && <span className="aperture-label mono">FIG. 01 <span>THE SAMPLING APERTURE</span></span>}
            {drag && <div className="drop-overlay">松开以接收图像 <Arrow diagonal/></div>}
            <span className="axis-cross" aria-hidden="true">+</span>
          </div>
          <div className="instrument-bottom"><span className="live-status" role="status" aria-live="polite"><i/>{stateText}</span><div className="view-switch" aria-label="观察视图"><button disabled={!preview} className={!matrix ? 'selected' : ''} aria-pressed={!matrix} onClick={() => setMatrix(false)}>图像</button><button disabled={!preview} className={matrix ? 'selected' : ''} aria-pressed={matrix} onClick={() => setMatrix(true)}>像素矩阵</button></div></div>
        </div>
      </section>
      {mode === 'photo' && <ol className="photo-rail mono" aria-label="照片处理进度">{[['PHOTO','照片适配'],['DETECT','定位'],['SELECT','选择'],['CROP','裁剪'],['REVEAL','预测']].map(([en,zh],i) => {const current = scene === 'detecting' ? 1 : scene === 'selecting' ? 2 : scene === 'cropping' || scene === 'capture' ? 3 : scene === 'analyzing' || result ? 4 : 0; return <li key={en} className={i === current ? 'current' : i < current ? 'complete' : ''} aria-current={i === current ? 'step' : undefined}><span>{en}</span><span>{zh}</span></li>;})}</ol>}
      <ProcessRail stage={stage} done={!!result} busy={scene === 'analyzing'}/>
      <div className="analysis-deck">
        <section className="input-section" aria-labelledby="input-title">
          <div className="section-label"><h2 id="input-title">{photo ? '人脸选择与输入确认' : preview ? '输入观察' : '从一张人脸开始'} <span>/ {preview ? 'INPUT STUDY' : 'TRY A SIGNAL'}</span></h2><span className="mono">{photo ? `${String(photo.count).padStart(2,'0')} FACES` : preview ? '2304 VALUES' : '03 SAMPLES'}</span></div>
          {photo ? <PhotoStudy data={photo} selected={selectedFace} onSelect={chooseFace} scene={scene} busy={busy}/> : preview ? <div className="input-study">
            <div className="study-images"><figure><img src={input.url} onError={e => {if (e.currentTarget.src !== preview.preview) e.currentTarget.src = preview.preview;}} alt="上传的原始人脸图片；不支持直接显示的格式采用同像素无损预览"/><figcaption>原图 <span className="mono">48² / L</span></figcaption></figure><span className="study-arrow">→</span><figure><img className="pixelated" src={preview.preview} alt="48×48 模型输入预览；实际张量为 float32 除以255"/><figcaption>模型输入 <span className="mono">/ 255</span></figcaption></figure><div className="study-meta"><span className="mono">[1, 1, 48, 48]</span><span>float32 / 255</span><span>没有自动检测或裁剪</span></div></div>
            <label className="pixel-inspector" htmlFor="pixel-index"><span>读取像素 <span className="mono">[{pixelIndex % 48}, {Math.floor(pixelIndex / 48)}]</span></span><span className="mono">{selectedValue} → {(selectedValue / 255).toFixed(4)}</span></label><input id="pixel-index" aria-label="检查像素索引" type="range" min="0" max="2303" value={pixelIndex} onChange={e => setPixelIndex(Number(e.target.value))}/>
            <div className="file-detail"><span title={input.name}>{input.name}</span><button className="text-button" disabled={busy} onClick={() => upload.current.click()}>更换图像 ↗</button></div>
          </div> : <div ref={samples} className="sample-section">
            <div className="sample-list">{examples.map(i => <button key={i} className="sample" onClick={() => sample(i)} disabled={busy || !health} aria-label={`载入样例 0${i + 1}`}><img src={`/api/examples/${i}`} alt=""/><span className="mono">0{i + 1}</span><Arrow diagonal/></button>)}</div>
            <p>已有 PublicTest 验证样例，载入后点击分析。<br/>示例只用于体验流程，不代表独立测试表现。</p>
          </div>}
        </section>
        <Spectrum prediction={prediction}/>
      </div>
      <div className="ethics-note"><span className="note-symbol" aria-hidden="true">↳</span><p>我们观测表情的信号，不替你定义感受。<span>模型输出概率不代表真实内心情绪，未经概率校准，不用于心理或医疗诊断。</span></p></div>
      <section className="method" id="method">
        <button className="method-toggle" aria-expanded={details} aria-controls="method-content" onClick={() => setDetails(!details)}><span>打开仪器内部 <span className="muted">/ 方法、模型与边界</span></span><span className="mono">{details ? 'CLOSE −' : 'EXPLORE +'}</span></button>
        {details && <div id="method-content" className="method-content">
          <div className="method-intro"><span className="eyebrow mono">THREE MODELS. ONE SIGNAL.</span><h2>把过程，<br/>留给好奇的人。</h2><p>普通照片先在浏览器本机自动适配：大图等比缩至长边 4096 以内，并转为不超过 12 MiB 的 JPEG；已合适的照片保留原始像素。随后经 YuNet 定位、明确选脸、确认 48×48 灰度裁剪，才送入冻结分类器。预裁剪入口继续严格检查 48×48 L。</p></div>
          <div className="method-data"><h3>01 / 冻结融合架构</h3><div className="architecture">{['T3 · e56', 'w16 · e97', 'w32 · e93'].map(name => <div key={name}><strong className="mono">{name}</strong><span>原图 + 水平翻转</span><span className="mono">½ + ½ → ⅓</span></div>)}</div><p>各视图 softmax 概率平均，三模型等权融合；CPU 单线程，启动后常驻复用。</p>
            <h3>02 / 本次观测</h3><dl className="metrics"><div><dt>真实模型推理耗时</dt><dd className="mono">{result ? `${result.inference_ms.toFixed(2)} ms` : '尚未推理'}</dd></div><div><dt>服务端总处理耗时</dt><dd className="mono">{result ? `${result.total_ms.toFixed(2)} ms` : '—'}</dd></div><div><dt>模型版本</dt><dd>{health?.version || '等待本地服务'}</dd></div><div><dt>已完成阶段</dt><dd>{events.length ? events.map(s => ({check: '检查',preprocess: '预处理',infer: '推理',compose: '生成'})[s]).join(' → ') : '—'}</dd></div><div><dt>输入 SHA-256</dt><dd className="mono hash">{preview?.sha256 || '—'}</dd></div></dl>
            {prediction && <table><caption>未经校准的七类完整模型输出</caption><thead><tr><th scope="col">类别 / 固定顺序</th><th scope="col">原始概率</th></tr></thead><tbody>{prediction.probabilities.map(p => <tr key={p.label}><th scope="row">{p.label} / {p.emotion} · {p.emotion_zh}</th><td className="mono">{p.probability.toPrecision(10)}</td></tr>)}</tbody></table>}
            {photo && <><h3>照片适配 / 固定记录</h3><p>{photo.detector.detector} · square-edge-v1<br/>检测耗时 {photo.detect_ms.toFixed(2)} ms；{selectedFace ? `所选第 ${selectedFace} 张人脸` : photo.count ? '尚未选择人脸' : '未检测到人脸，未运行表情分类'}。灰度转换与 LANCZOS 缩放在分类器外完成，T4 float32 / 255 不变。原图与中间裁剪不写入磁盘。</p></>}
            <h3>03 / 历史数据集验证成果与局限</h3><p className="validation-number mono">72.610755<small>%</small><span>PublicTest · 2606 / 3589</span></p><p>此为 T4 已核验的历史验证成果，本页没有重新全量评估。PublicTest 用于反复选模，并存在历史重复图像的局限；不代表独立测试或真实场景准确率。PrivateTest 最终评估尚未进行。</p><p>模型描述的是七类表情的图像特征，不能推断人的真实感受、心理状态或人格。</p>
          </div>
        </div>}
      </section>
    </main>
    <footer><span className="footer-brand">HUMAN SIGNAL<span>© EMOTIONLAB / 2026</span></span><span className="mono">48² PIXELS · 3 MODELS · 7 EXPRESSIONS</span><span>本地运行 <span className="green">↗</span></span></footer>
  </div>;
}
