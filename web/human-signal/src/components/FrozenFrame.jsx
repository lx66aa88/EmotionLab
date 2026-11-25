export function FrozenFaceBoxes({frame, mirrored, onChoose}) {
  return frame.faces.map(face => {
    const [x, y, w, h] = face.box;
    const left = Math.max(0, x);
    const top = Math.max(0, y);
    const right = Math.min(frame.width, x + w);
    const bottom = Math.min(frame.height, y + h);
    const style = {
      left: `${100 * (mirrored ? frame.width - right : left) / frame.width}%`,
      top: `${100 * top / frame.height}%`,
      width: `${100 * (right - left) / frame.width}%`,
      height: `${100 * (bottom - top) / frame.height}%`,
    };
    const number = String(face.id).padStart(2, '0');
    return frame.phase === 'selecting'
      ? <button key={face.id} className="frozen-face-box" style={style} onClick={() => onChoose(face.id)}
          aria-label={`分析定格人脸 ${number}`}><span className="track-label mono">FACE {number}</span></button>
      : <span key={face.id} className="frozen-face-box selected" style={style} aria-hidden="true">
          <span className="track-label mono">FACE {number}</span>
        </span>;
  });
}

export function FrozenFaceStudy({frame, onChoose}) {
  return <section className="input-section" aria-labelledby="frozen-input-title">
    <div className="section-label">
      <h2 id="frozen-input-title">定格人脸与模型输入 <span>/ FRAME STUDY</span></h2>
      <span className="mono">{frame.width} × {frame.height}</span>
    </div>
    {frame.face ? <div className="study-images frozen-study">
      <figure><img src={frame.face.crop_preview} alt="定格人脸的方形裁剪"/><figcaption>方形裁剪</figcaption></figure>
      <span className="study-arrow" aria-hidden="true">→</span>
      <figure><img className="pixelated frozen-model-input" src={frame.face.input_preview}
        alt="模型实际使用的 48×48 灰度图"/><figcaption>模型输入 <span className="mono">48² / L</span></figcaption></figure>
    </div> : frame.phase === 'selecting' ? <div className="live-face-picker" aria-label="定格人脸候选">
      {frame.faces.map(face => <button key={face.id} onClick={() => onChoose(face.id)}>
        分析人脸 {String(face.id).padStart(2, '0')}
      </button>)}
    </div> : <p className="live-empty-copy">{frame.message}</p>}
  </section>;
}
