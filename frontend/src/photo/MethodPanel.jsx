export default function MethodPanel({
  details,
  setDetails,
  health,
  result,
  events,
  preview,
  prediction,
  photo,
  selectedFace,
}) {
  return (
    <section className="method" id="method">
      <button
        className="method-toggle"
        aria-expanded={details}
        aria-controls="method-content"
        onClick={() => setDetails(!details)}
      >
        <span>
          打开仪器内部 <span className="muted">/ 方法、模型与边界</span>
        </span>
        <span className="mono">{details ? "CLOSE −" : "EXPLORE +"}</span>
      </button>
      {details && (
        <div id="method-content" className="method-content">
          <div className="method-intro">
            <span className="eyebrow mono">THREE MODELS. ONE SIGNAL.</span>
            <h2>
              把过程，
              <br />
              留给好奇的人。
            </h2>
            <p>
              普通照片先在本机自动适配：HEIC/HEIF 与 TIFF 使用 Apple ImageIO
              独立受控解码；其他格式沿用浏览器处理。大图等比缩至长边 4096
              以内，并转为不超过 12 MiB 的
              JPEG；已合适的照片保留原始像素。随后经 YuNet 定位、明确选脸、确认
              48×48 灰度裁剪，才送入冻结分类器。预裁剪入口继续严格检查 48×48 L。
            </p>
          </div>
          <div className="method-data">
            <h3>01 / 冻结融合架构</h3>
            <div className="architecture">
              {["T3 · e56", "w16 · e97", "w32 · e93"].map((name) => (
                <div key={name}>
                  <strong className="mono">{name}</strong>
                  <span>原图 + 水平翻转</span>
                  <span className="mono">½ + ½ → ⅓</span>
                </div>
              ))}
            </div>
            <p>
              各视图 softmax 概率平均，三模型等权融合；CPU
              单线程，启动后常驻复用。
            </p>
            <h3>02 / 本次观测</h3>
            <dl className="metrics">
              <div>
                <dt>真实模型推理耗时</dt>
                <dd className="mono">
                  {result ? `${result.inference_ms.toFixed(2)} ms` : "尚未推理"}
                </dd>
              </div>
              <div>
                <dt>服务端总处理耗时</dt>
                <dd className="mono">
                  {result ? `${result.total_ms.toFixed(2)} ms` : "—"}
                </dd>
              </div>
              <div>
                <dt>模型版本</dt>
                <dd>{health?.version || "等待本地服务"}</dd>
              </div>
              <div>
                <dt>已完成阶段</dt>
                <dd>
                  {events.length
                    ? events
                        .map(
                          (s) =>
                            ({
                              check: "检查",
                              preprocess: "预处理",
                              infer: "推理",
                              compose: "生成",
                            })[s],
                        )
                        .join(" → ")
                    : "—"}
                </dd>
              </div>
              <div>
                <dt>输入 SHA-256</dt>
                <dd className="mono hash">{preview?.sha256 || "—"}</dd>
              </div>
            </dl>
            {prediction && (
              <table>
                <caption>未经校准的七类完整模型输出</caption>
                <thead>
                  <tr>
                    <th scope="col">类别 / 固定顺序</th>
                    <th scope="col">原始概率</th>
                  </tr>
                </thead>
                <tbody>
                  {prediction.probabilities.map((p) => (
                    <tr key={p.label}>
                      <th scope="row">
                        {p.label} / {p.emotion} · {p.emotion_zh}
                      </th>
                      <td className="mono">{p.probability.toPrecision(10)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {photo && (
              <>
                <h3>照片适配 / 固定记录</h3>
                <p>
                  {photo.detector.detector} · square-edge-v1
                  <br />
                  检测耗时 {photo.detect_ms.toFixed(2)} ms；
                  {selectedFace
                    ? `所选第 ${selectedFace} 张人脸`
                    : photo.count
                      ? "尚未选择人脸"
                      : "未检测到人脸，未运行表情分类"}
                  。灰度转换与 LANCZOS 缩放在分类器外完成，T4 float32 / 255
                  不变。原图与中间裁剪经内存和管道处理；本机解码进程禁止文件写入及联网。
                </p>
              </>
            )}
            <h3>03 / 历史数据集验证成果与局限</h3>
            <p className="validation-number mono">
              72.610755<small>%</small>
              <span>PublicTest · 2606 / 3589</span>
            </p>
            <p>
              此为 T4 已核验的历史验证成果，本页没有重新全量评估。PublicTest
              用于反复选模，并存在历史重复图像的局限；不代表独立测试或真实场景准确率。PrivateTest
              最终评估尚未进行。
            </p>
            <p>
              模型描述的是七类表情的图像特征，不能推断人的真实感受、心理状态或人格。
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
