import { memo, useId, useState } from "react";
import { SignalSculpture } from "../../seven-signals/SignalSculpture.jsx";
import { signalFor } from "../../seven-signals/signals.js";
import "./SevenSignals.css";

const Sculpture = memo(SignalSculpture);

const meanings = {
  Angry: "锐利折线，代表压力累积与张力释放。",
  Disgust: "扭曲回卷的带状结构，代表排斥、回避与收缩。",
  Fear: "向内收拢的紫色裂隙，代表紧张、警觉与未知。",
  Happy: "向外舒展的金色花瓣，代表开放、轻盈与能量释放。",
  Sad: "下垂的蓝色曲面，代表沉静、内敛与缓慢下沉。",
  Surprise: "向外扩张的青绿色旋转结构，代表瞬间变化与注意力被唤起。",
  Neutral: "稳定重复的银灰色环形，代表均衡与平稳。",
};

const sources = {
  photo: "照片 · 模型输出",
  ema: "实时 · EMA",
  raw: "实时 · RAW",
  frozen: "定格 · 单帧分析",
};
const standby = {
  idle: "等待照片输入",
  preparing: "正在适配照片",
  detecting: "正在检测人脸",
  selecting: "等待确认人脸",
  cropping: "等待确认裁剪",
  inspecting: "正在检查模型输入",
  capture: "等待开始分析",
  analyzing: "正在分析表情",
  photo_error: "等待重新选择图片",
  off: "摄像头已关闭",
  opening: "等待摄像头授权",
  waiting: "等待有效采样",
  paused: "分析已暂停",
  no_face: "未检测到人脸",
  target_lost: "当前跟踪目标已丢失",
  low_quality: "等待清晰人脸",
  backend_error: "本机推理暂不可用",
  camera_error: "摄像头暂不可用",
  stale: "上次采样已失效",
  interrupted: "视频信号暂时中断",
  error: "单帧分析未完成",
};

export default function SevenSignals({
  prediction,
  category = prediction?.label,
  status,
  source,
  frameId,
  motionControl,
}) {
  const titleId = useId();
  const [paused, setPaused] = useState(false);
  const row = prediction?.probabilities[category];
  const signal =
    status === "ok" && row?.label === category ? signalFor(category) : null;
  return (
    <section
      className="seven-signals"
      aria-labelledby={titleId}
      data-status={status}
      data-prediction-view={source}
      data-frame-id={signal ? frameId : undefined}
    >
      <div className="section-label">
        <h2 id={titleId}>
          视觉雕塑 <span lang="en">/ SEVEN SIGNALS</span>
        </h2>
        <span className="mono">{sources[source]}</span>
      </div>
      <div className="seven-signals-stage">
        <Sculpture
          category={signal ? category : null}
          source="prediction"
          playback={paused ? "paused" : "playing"}
        />
        {!signal && (
          <p className="seven-signals-standby">
            {standby[status] ?? "等待有效预测"}
          </p>
        )}
        {motionControl && (
          <button
            className="sculpture-motion mono"
            aria-label="暂停雕塑动效"
            aria-pressed={paused}
            onClick={() => setPaused(!paused)}
          >
            <span aria-hidden="true">{paused ? "▶" : "Ⅱ"}</span>
            <span>{paused ? "已暂停" : "暂停动效"}</span>
          </button>
        )}
      </div>
      {signal && (
        <details className="seven-signals-meaning">
          <summary>
            <span>视觉释义</span>
            <span
              className="seven-signals-form"
              style={{ "--sculpture-accent": signal.accent }}
            >
              <span lang="en">{signal.form}</span> {signal.formZh}
            </span>
          </summary>
          <div className="seven-signals-notes">
            <p>
              <strong>
                <span lang="en">{signal.name}</span> · {signal.zh}
              </strong>
              　{meanings[signal.name]}
            </p>
            <p>{signal.note}</p>
            <p className="data-note">
              这些形态是艺术隐喻。情绪与形态的对应关系未经科学验证。
            </p>
          </div>
        </details>
      )}
    </section>
  );
}
