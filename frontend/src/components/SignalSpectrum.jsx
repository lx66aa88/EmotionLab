import { LABELS, ZH } from "../live/session.js";

export default function SignalSpectrum({
  prediction,
  source,
  sculptureLabel,
  controls,
}) {
  const view = {
    photo: "PHOTO · RAW",
    frozen: "SINGLE FRAME · RAW",
    raw: "LIVE · RAW",
    ema: "LIVE · EMA",
  }[source];
  const held =
    prediction && sculptureLabel != null && sculptureLabel !== prediction.label;
  return (
    <section className="spectrum" aria-labelledby="spectrum-title">
      <div className="section-label">
        <h2 id="spectrum-title">
          七类概率 <span lang="en">SIGNAL SPECTRUM</span>
        </h2>
        <span className="mono" lang="en">
          {view}
        </span>
      </div>
      {controls}
      <div
        className="distribution"
        aria-label="七类概率，统一从 0 到 100% 刻度"
      >
        <div className="scale mono" aria-hidden="true">
          <span>0</span>
          <span>50</span>
          <span>100%</span>
        </div>
        {LABELS.map((name, index) => {
          const probability = prediction?.probabilities[index]?.probability;
          const highest = prediction?.label === index;
          const sculpture = prediction && sculptureLabel === index;
          const percentage =
            probability === undefined
              ? "—"
              : probability > 0 && probability < 0.00005
                ? "<0.01%"
                : (probability * 100).toFixed(2) + "%";
          return (
            <div
              key={name}
              className={`signal-row${highest ? " is-highest" : ""}`}
              data-sculpture-row={sculpture ? "" : undefined}
            >
              <div className="signal-name">
                <span className="probability-marker" aria-hidden="true">
                  {highest ? "▲" : held && sculpture ? "◇" : ""}
                </span>
                <span lang="en">{name}</span>
                <span className="signal-zh">{ZH[index]}</span>
                {highest && <span className="sr-only">最高概率</span>}
                {sculpture && <span className="sr-only">当前雕塑</span>}
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
                {percentage}
              </span>
            </div>
          );
        })}
      </div>
      <p className="data-note spectrum-key">
        {prediction ? (
          <>
            ▲ 最高概率{held && " · ◇ 当前雕塑"}
            {source === "ema" && " · EMA α=0.45"}
          </>
        ) : (
          "等待有效预测。"
        )}
      </p>
    </section>
  );
}
