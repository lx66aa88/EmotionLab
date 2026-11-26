const steps = [
  ["check", "输入检查"],
  ["preprocess", "图像预处理"],
  ["infer", "模型推理"],
  ["compose", "结果生成"],
];
export default function ProcessRail({ stage, done, busy }) {
  const active = steps.findIndex(([key]) => key === stage);
  return (
    <ol className="process-rail" aria-label="真实处理阶段">
      {steps.map(([key, title], i) => (
        <li
          key={key}
          className={
            done || (busy && i < active)
              ? "complete"
              : busy && i === active
                ? "current"
                : ""
          }
          aria-current={busy && i === active ? "step" : undefined}
        >
          <span className="step-num mono">
            {done || (busy && i < active) ? "↳" : `0${i + 1}`}
          </span>
          <span>{title}</span>
          <span className="step-rule" />
        </li>
      ))}
    </ol>
  );
}
