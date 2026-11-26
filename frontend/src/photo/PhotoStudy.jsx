/** Photo geometry is from the local detector in oriented source coordinates. */
export function PhotoWindow({ data, selected, onSelect, showCrop, disabled }) {
  const face = data.faces.find((f) => f.id === selected);
  const { width, height } = data.photo;
  const position = (box) => ({
    left: `${(Math.max(0, box[0]) / width) * 100}%`,
    top: `${(Math.max(0, box[1]) / height) * 100}%`,
    width: `${((Math.min(width, box[0] + box[2]) - Math.max(0, box[0])) / width) * 100}%`,
    height: `${((Math.min(height, box[1] + box[3]) - Math.max(0, box[1])) / height) * 100}%`,
  });
  return (
    <div
      className="photo-window"
      style={{
        aspectRatio: `${width} / ${height}`,
        maxWidth: `min(100%, calc(var(--observation-image-height, 520px) * ${width / height}))`,
      }}
    >
      <img
        src={data.photo.preview}
        alt="已按 EXIF 校正方向的照片；编号框来自本机真实人脸检测"
      />
      {data.faces.map((f) => (
        <button
          key={f.id}
          className={`face-box ${selected === f.id ? "chosen" : ""}`}
          style={position(f.box)}
          onClick={() => onSelect(f.id)}
          disabled={disabled}
          aria-label={`选择第 ${f.id} 张人脸`}
          aria-pressed={selected === f.id}
        >
          <span className="mono">{String(f.id).padStart(2, "0")}</span>
        </button>
      ))}
      {showCrop && face && (
        <div
          className="crop-outline"
          style={position(face.crop.box)}
          aria-hidden="true"
        />
      )}
    </div>
  );
}

export default function PhotoStudy({ data, selected, onSelect, scene, busy }) {
  const face = data.faces.find((f) => f.id === selected);
  return (
    <div className="photo-study">
      <div className="photo-caption">
        <strong>
          {data.count ? `检测到 ${data.count} 张人脸` : "没有检测到人脸"}
        </strong>
        <span className="mono">{data.detect_ms.toFixed(0)} ms / LOCAL</span>
      </div>
      {!data.count ? (
        <p className="photo-note">{data.message}</p>
      ) : (
        <>
          <p className="photo-note">
            {scene === "selecting"
              ? data.count === 1
                ? "已预选 01。请确认这张人脸，再检查裁剪。"
                : "先明确选择一张人脸，再确认裁剪；不会自动选择最大脸。"
              : scene === "cropping"
                ? "请检查方形裁剪和最终灰度输入，确认后才可分析。"
                : `已确认第 ${selected} 张人脸的裁剪。改选后需要重新确认。`}
          </p>
          <div className="face-candidates" role="group" aria-label="候选人脸">
            {data.faces.map((f) => (
              <button
                key={f.id}
                className={`face-candidate ${selected === f.id ? "selected" : ""}`}
                onClick={() => onSelect(f.id)}
                disabled={busy}
                aria-pressed={selected === f.id}
                aria-label={`候选人脸 ${f.id}`}
              >
                <img
                  src={f.crop_preview}
                  alt={`候选人脸 ${f.id} 的方形裁剪预览`}
                />
                <span className="candidate-number mono">
                  {String(f.id).padStart(2, "0")}{" "}
                  {selected === f.id ? "✓" : "↗"}
                </span>
                <span className="detection-score">
                  检测分数
                  <br />
                  <span className="mono">{f.detection_score.toFixed(4)}</span>
                </span>
              </button>
            ))}
          </div>
          {face && scene !== "selecting" && (
            <div className="crop-study">
              <div className="study-images">
                <figure>
                  <img
                    src={face.crop_preview}
                    alt={`选中第 ${face.id} 张人脸的正方形彩色裁剪`}
                  />
                  <figcaption>
                    方形裁剪 <span className="mono">{face.crop.box[2]}²</span>
                  </figcaption>
                </figure>
                <span className="study-arrow">→</span>
                <figure>
                  <img
                    className="pixelated"
                    src={face.input_preview}
                    alt={
                      scene === "cropping"
                        ? "待确认的最终 48×48 L 灰度模型输入"
                        : "已确认的最终 48×48 L 灰度模型输入"
                    }
                  />
                  <figcaption>
                    灰度输入 <span className="mono">48² / L</span>
                  </figcaption>
                </figure>
              </div>
              <p className="photo-note">
                以检测框中心扩展至 1.25
                倍正方形，超出照片时复制边缘补齐。灰度转换后用 LANCZOS
                缩放，不拉伸人脸。
              </p>
              <dl className="crop-record mono">
                <div>
                  <dt>裁剪 x / y / 边长</dt>
                  <dd>{face.crop.box.slice(0, 3).join(" / ")}</dd>
                </div>
                <div>
                  <dt>补边 左 / 上 / 右 / 下</dt>
                  <dd>{face.crop.padding_ltrb.join(" / ")}</dd>
                </div>
                <div>
                  <dt>照片方向</dt>
                  <dd>
                    {data.preparation?.converted ? (
                      data.preparation.localDecoderFallback ? (
                        <>
                          原片 EXIF {data.preparation.exifOrientation} /{" "}
                          {data.preparation.orientationApplied
                            ? "已校正"
                            : "无需旋转"}
                          <br />
                          检测输入 / 无 EXIF
                        </>
                      ) : (
                        <>浏览器已定向 / 检测输入无 EXIF</>
                      )
                    ) : (
                      <>
                        EXIF {data.photo.exif_orientation ?? "—"}
                        {data.photo.orientation_applied
                          ? " / 已校正"
                          : " / 无需旋转"}
                      </>
                    )}
                  </dd>
                </div>
              </dl>
            </div>
          )}
        </>
      )}
      <p className="photo-note photo-boundary">
        普通照片演示预测 · 自然照片准确率未独立验证。
        <br />
        检测分数用于定位人脸，与表情类别概率不同。
      </p>
    </div>
  );
}
