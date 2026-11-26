const names = [
  "Angry",
  "Disgust",
  "Fear",
  "Happy",
  "Sad",
  "Surprise",
  "Neutral",
];
const zh = ["愤怒", "厌恶", "恐惧", "快乐", "悲伤", "惊喜", "中立"];
export default function Spectrum({ prediction }) {
  return (
    <section className="spectrum" aria-labelledby="spectrum-title">
      <div className="section-label">
        <h2 id="spectrum-title">
          表情信号谱 <span>/ SIGNAL SPECTRUM</span>
        </h2>
        <span className="mono">
          {prediction ? "MODEL OUTPUT" : "AWAITING INPUT"}
        </span>
      </div>
      <div
        className="distribution"
        aria-label="七类模型概率，统一 0 到 100 百分比刻度"
      >
        <div className="scale mono">
          <span>0</span>
          <span>50</span>
          <span>100%</span>
        </div>
        {names.map((name, index) => {
          const probability = prediction?.probabilities[index]?.probability;
          return (
            <div
              className={`signal-row ${prediction?.label === index ? "is-highest" : ""}`}
              key={name}
            >
              <div className="signal-name">
                <span className="mono signal-index">0{index + 1}</span>
                <span>{name}</span>
                <span className="signal-zh">{zh[index]}</span>
              </div>
              <div className="signal-track" aria-hidden="true">
                <div
                  className="signal-fill"
                  style={{ transform: `scaleX(${probability ?? 0})` }}
                />
              </div>
              <span
                className="signal-value mono"
                data-probability={probability}
              >
                {probability === undefined
                  ? "—"
                  : (probability * 100).toFixed(2) + "%"}
              </span>
            </div>
          );
        })}
      </div>
      <p className="data-note">
        {prediction
          ? "条长直接映射模型概率；显示数值四舍五入至两位。"
          : "接收图像后生成七类分布。此处尚无预测数据。"}
      </p>
    </section>
  );
}
