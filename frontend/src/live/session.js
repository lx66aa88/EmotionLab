// Reusable capture lifecycle for T54 and a future T7 consumer. No persisted frames.
export const LABELS = [
  "Angry",
  "Disgust",
  "Fear",
  "Happy",
  "Sad",
  "Surprise",
  "Neutral",
];
export const ZH = ["愤怒", "厌恶", "恐惧", "快乐", "悲伤", "惊喜", "中立"];
export const STALE_MS = 1800;
export function smoothPrediction(raw, previous, alpha = 0.45) {
  const values = raw.probabilities.map((p, i) =>
    previous
      ? alpha * p.probability +
        (1 - alpha) * previous.probabilities[i].probability
      : p.probability,
  );
  const sum = values.reduce((a, b) => a + b, 0);
  const probabilities = values.map((v, i) => ({
    label: i,
    emotion: LABELS[i],
    emotion_zh: ZH[i],
    probability: v / sum,
  }));
  const label = probabilities.reduce(
    (best, p, i) =>
      p.probability > probabilities[best].probability ? i : best,
    0,
  );
  return {
    label,
    emotion: LABELS[label],
    emotion_zh: ZH[label],
    probabilities,
    probability_sum: 1,
  };
}
export function intervalFor(duration, previous = 333) {
  // Budget includes encode, detect, all six model views and localhost transport.
  return Math.max(
    250,
    Math.min(2500, 0.65 * previous + 0.35 * Math.max(333, duration * 1.35)),
  );
}
export function cameraError(error) {
  return (
    {
      NotAllowedError:
        "摄像头权限被拒绝。请在浏览器与 macOS 隐私设置中允许此页面使用摄像头，再点击开启。",
      NotFoundError: "没有可用摄像头。请连接摄像头后重试。",
      NotReadableError:
        "摄像头无法读取，可能被其他程序占用。请关闭占用程序后重试。",
      TrackStartError: "摄像头无法启动，可能被其他程序占用。请释放设备后重试。",
      OverconstrainedError: "当前摄像头不支持请求的格式，请更换设备后重试。",
      SecurityError: "浏览器禁止摄像头访问。请用本机 localhost 页面打开。",
      AbortError: "摄像头启动被中断，请重试。",
    }[error?.name] ||
    error?.message ||
    "摄像头无法打开，请检查设备与浏览器权限。"
  );
}

export class LiveSession {
  constructor({
    video,
    canvas,
    onChange,
    mediaDevices = navigator.mediaDevices,
    request = (...args) => fetch(...args),
    now = () => performance.now(),
    later = (...args) => setTimeout(...args),
    cancelLater = (id) => clearTimeout(id),
  }) {
    Object.assign(this, {
      video,
      canvas,
      onChange,
      mediaDevices,
      request,
      now,
      later,
      cancelLater,
    });
    this.epoch = 0;
    this.sequence = 0;
    this.lastAccepted = 0;
    this.inFlight = false;
    this.running = false;
    this.interval = 333;
    this.times = [];
    this.smooth = null;
    this.track = null;
    this.stream = null;
    this.state = {
      status: "off",
      message: "摄像头尚未开启",
      camera: false,
      paused: false,
      faces: [],
      data: null,
      smoothed: null,
      metrics: null,
    };
  }
  emit(patch) {
    this.state = { ...this.state, ...patch };
    this.onChange({ ...this.state });
  }
  clear(patch = {}) {
    this.smooth = null;
    this.emit({ data: null, smoothed: null, faces: [], ...patch });
  }
  async open() {
    if (this.stream || this.state.status === "opening") return;
    const epoch = ++this.epoch;
    this.clear({ status: "opening", message: "等待摄像头授权", metrics: null });
    try {
      if (!this.mediaDevices?.getUserMedia)
        throw new Error(
          "此浏览器无法访问摄像头，请使用支持摄像头的本机浏览器。",
        );
      const stream = await this.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          frameRate: { ideal: 30, max: 30 },
          facingMode: "user",
        },
        audio: false,
      });
      if (epoch !== this.epoch) {
        stream.getTracks().forEach((t) => t.stop());
        return;
      }
      this.stream = stream;
      this.video.srcObject = stream;
      for (const track of stream.getVideoTracks()) {
        track.onended = () => this.close("摄像头已断开，请重新开启");
        track.onmute = () => {
          if (!this.running) return;
          ++this.epoch;
          this.cancelLater(this.timer);
          this.cancelLater(this.expiry);
          this.controller?.abort();
          this.clear({
            status: "interrupted",
            message: "视频信号暂时中断",
            metrics: null,
          });
        };
        track.onunmute = () => {
          if (!this.running) return;
          this.emit({ status: "waiting", message: "视频已恢复，等待新采样" });
          this.schedule(0);
        };
      }
      await this.video.play();
      if (epoch !== this.epoch) return;
      this.running = true;
      this.track = null;
      this.point = null;
      this.times = [];
      this.interval = 333;
      this.lastVideoTime = -1;
      this.emit({
        camera: true,
        paused: false,
        status: "waiting",
        message: "视频已开启，等待检测人脸",
      });
      this.schedule(0, epoch);
    } catch (error) {
      if (epoch !== this.epoch) return;
      this.close(cameraError(error), "camera_error");
    }
  }
  schedule(delay, epoch = this.epoch) {
    this.cancelLater(this.timer);
    if (this.running && epoch === this.epoch)
      this.timer = this.later(() => this.sample(epoch), delay);
  }
  pause() {
    if (!this.stream) return;
    this.running = false;
    ++this.epoch;
    this.cancelLater(this.timer);
    this.cancelLater(this.expiry);
    this.controller?.abort();
    this.track = null;
    this.point = null;
    this.times = [];
    this.clear({
      paused: true,
      status: "paused",
      message: "分析已暂停 · 视频预览继续",
      metrics: null,
    });
  }
  resume() {
    if (!this.stream || this.running) return;
    this.running = true;
    ++this.epoch;
    this.times = [];
    this.lastVideoTime = -1;
    this.clear({
      paused: false,
      status: "waiting",
      message: "分析已恢复，等待新采样",
      metrics: null,
    });
    this.schedule(0);
  }
  choose(face) {
    if (!this.running) return;
    // Cancel logically, but keep inFlight true until the old request really settles.
    ++this.epoch;
    this.controller?.abort();
    this.cancelLater(this.expiry);
    this.times = [];
    this.track = face?.normalized_box || null;
    this.point = null;
    this.clear({
      status: "waiting",
      message: face ? `正在重新定位所选人脸 ${face.id}` : "重新选择最大人脸",
      metrics: null,
    });
    this.schedule(0);
  }
  close(message = "摄像头已关闭", status = "off") {
    this.running = false;
    ++this.epoch;
    this.cancelLater(this.timer);
    this.cancelLater(this.expiry);
    this.controller?.abort();
    this.stream?.getTracks().forEach((t) => {
      t.onended = null;
      t.onmute = null;
      t.onunmute = null;
      t.stop();
    });
    this.stream = null;
    this.video.pause();
    this.video.srcObject = null;
    this.canvas.width = 1;
    this.canvas.height = 1;
    this.track = null;
    this.times = [];
    this.clear({
      camera: false,
      paused: false,
      status,
      message,
      metrics: null,
    });
  }
  async sample(epoch) {
    if (!this.running || epoch !== this.epoch) return;
    if (this.inFlight) {
      this.schedule(50, epoch);
      return;
    }
    const video = this.video;
    if (
      video.readyState < 2 ||
      !video.videoWidth ||
      video.currentTime === this.lastVideoTime ||
      this.stream?.getVideoTracks().some((t) => t.muted)
    ) {
      this.schedule(100, epoch);
      return;
    }
    this.inFlight = true;
    this.lastVideoTime = video.currentTime;
    const started = this.now(),
      frameId = ++this.sequence;
    let timeout;
    try {
      const scale = Math.min(
        1,
        960 / Math.max(video.videoWidth, video.videoHeight),
      );
      const width = Math.round(video.videoWidth * scale);
      const height = Math.round(video.videoHeight * scale);
      if (this.canvas.width !== width) this.canvas.width = width;
      if (this.canvas.height !== height) this.canvas.height = height;
      this.canvas
        .getContext("2d", { alpha: false })
        .drawImage(video, 0, 0, this.canvas.width, this.canvas.height);
      const blob = await new Promise((resolve) =>
        this.canvas.toBlob(resolve, "image/jpeg", 0.86),
      );
      if (epoch !== this.epoch || !this.running) return;
      if (!blob) throw new Error("视频采样失败，请关闭并重新开启摄像头。");
      this.controller = new AbortController();
      timeout = this.later(() => this.controller?.abort(), 5000);
      const params = new URLSearchParams({
        frame_id: String(frameId),
        captured_at: String(started),
      });
      if (this.track) params.set("track", this.track.join(","));
      const response = await this.request(`/api/live/frame?${params}`, {
        method: "POST",
        headers: { "Content-Type": "image/jpeg" },
        body: blob,
        signal: this.controller.signal,
      });
      const data = await response.json();
      if (
        epoch !== this.epoch ||
        !this.running ||
        data.frame_id <= this.lastAccepted
      )
        return;
      if (!response.ok)
        throw new Error(
          response.status === 409
            ? "本机分析忙碌，正在等待下一次采样。"
            : data.detail || "推理后端暂时不可用，正在重试。",
        );
      const ended = this.now(),
        elapsed = ended - started;
      this.lastAccepted = data.frame_id;
      this.interval = intervalFor(elapsed, this.interval);
      if (elapsed > STALE_MS) {
        this.clear({
          status: "stale",
          message: "此帧处理过久，已丢弃；正在降低采样频率",
          metrics: null,
        });
        return;
      }
      this.times = [...this.times, ended].slice(-12);
      const hz =
        this.times.length > 1
          ? (1000 * (this.times.length - 1)) / (ended - this.times[0])
          : null;
      const metrics = {
        roundTripMs: elapsed,
        totalMs: data.total_ms,
        inferenceMs: data.inference_ms,
        detectMs: data.detect_ms,
        updateHz: hz,
        intervalMs: this.interval,
        frameId: data.frame_id,
      };
      if (data.selected_box) this.track = data.selected_box;
      if (data.status === "ok") {
        this.smooth = smoothPrediction(data.raw_prediction, this.smooth);
        this.emit({
          status: "ok",
          message: data.message,
          data,
          faces: data.faces,
          smoothed: this.smooth,
          metrics,
        });
      } else {
        this.clear({
          status: data.status,
          message: data.message,
          data,
          faces: data.faces,
          metrics,
        });
      }
      this.cancelLater(this.expiry);
      this.expiry = this.later(
        () => {
          if (epoch === this.epoch && this.running)
            this.clear({
              status: "stale",
              message: "等待新画面 · 上次结果已过期",
              metrics: null,
            });
        },
        Math.max(50, STALE_MS - elapsed),
      );
    } catch (error) {
      if (epoch === this.epoch && this.running) {
        this.interval = Math.min(2500, Math.max(800, this.interval * 1.4));
        const message =
          error.name === "AbortError"
            ? "本机推理请求超时，正在重试。"
            : error instanceof TypeError || error instanceof SyntaxError
              ? "本机推理服务连接中断，正在重试。"
              : error.message || "本机推理服务暂时不可用，正在重试。";
        this.clear({ status: "backend_error", message, metrics: null });
      }
    } finally {
      this.cancelLater(timeout);
      this.inFlight = false;
      if (epoch === this.epoch && this.running)
        this.schedule(
          Math.max(0, this.interval - (this.now() - started)),
          epoch,
        );
    }
  }
}
