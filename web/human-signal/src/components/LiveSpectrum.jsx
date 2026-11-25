import { LABELS, ZH } from '../liveSession.js';

// Same HUMAN SIGNAL rows and scale, with the correct provenance for each view.
export default function LiveSpectrum({ prediction, raw = false, singleFrame = false, sculptureLabel }) {
  return <section className="spectrum" aria-labelledby="spectrum-title">
    <div className="section-label">
      <h2 id="spectrum-title">表情信号谱 <span>/ SIGNAL SPECTRUM</span></h2>
      <span className="mono">{prediction ? (singleFrame ? 'SINGLE FRAME · RAW' : raw ? 'RAW MODEL OUTPUT' : 'EMA DISPLAY') : 'AWAITING SIGNAL'}</span>
    </div>
    <div className="distribution" aria-label={singleFrame ? '定格帧的七类原始模型概率' : raw ? '未经平滑的七类模型概率' : '七类实时平滑显示概率'}>
      <div className="scale mono"><span>0</span><span>50</span><span>100%</span></div>
      {LABELS.map((name, index) => {
        const probability = prediction?.probabilities[index]?.probability;
        const sculpture = prediction && sculptureLabel === index;
        return <div className={`signal-row ${prediction?.label === index ? 'is-highest' : ''}`} key={name}
          data-sculpture-row={sculpture ? '' : undefined}>
          <div className="signal-name">
            <span className="mono signal-index">0{index + 1}</span><span lang="en">{name}</span><span className="signal-zh">{ZH[index]}</span>
            {sculpture && <span className="sr-only">当前雕塑</span>}
          </div>
          <div className="signal-track" aria-hidden="true"><div className="signal-fill" style={{transform: `scaleX(${probability ?? 0})`}}/></div>
          <span className="signal-value mono" data-probability={probability}>{probability === undefined ? '—' : (probability * 100).toFixed(2) + '%'}</span>
        </div>;
      })}
    </div>
    <p className="data-note">{prediction ? (raw || singleFrame ? '条长映射本帧原始模型概率。' : '条长映射实时 EMA 显示值。') : '当前没有有效预测。'}</p>
  </section>;
}
