const BUSY_DELAYS = [0, 100, 200, 350, 550, 800];
const MAX_EDGE = 960;

function wait(ms, signal) {
  return new Promise((resolve, reject) => {
    signal.throwIfAborted();
    const abort = () => {
      clearTimeout(timer);
      reject(signal.reason);
    };
    const timer = setTimeout(() => {
      signal.removeEventListener('abort', abort);
      resolve();
    }, ms);
    signal.addEventListener('abort', abort, {once: true});
  });
}

async function post(path, body, signal) {
  for (const delay of BUSY_DELAYS) {
    if (delay) await wait(delay, signal);
    signal.throwIfAborted();
    const response = await fetch(path, {
      method: 'POST', body, signal, headers: {'Content-Type': 'application/octet-stream'},
    });
    signal.throwIfAborted();
    if (response.ok) return response;
    if (response.status === 409) {
      await response.body?.cancel();
      continue;
    }
    const error = await response.json().catch(() => null);
    throw new Error(typeof error?.detail === 'string' ? error.detail : '本机服务未能完成分析。');
  }
  throw new Error('模型暂时繁忙，请重新定格。');
}

export class FrozenAnalysis {
  constructor({live, canvas, onChange}) {
    Object.assign(this, {live, canvas, onChange});
    this.state = null;
    this.job = null;
    this.sequence = 0;
  }

  emit(patch) {
    this.state = {...this.state, ...patch};
    this.onChange(this.state);
  }

  clear() {
    if (!this.state) return;
    const job = this.job;
    this.job = null;
    job?.abort();
    this.state = null;
    this.canvas.width = this.canvas.height = 1;
    this.onChange(null);
  }

  resume() {
    this.clear();
    this.live.resume();
  }

  freeze() {
    if (this.job) return '';
    const {video, stream, state} = this.live;
    if (!state.camera || video.readyState < 2 || !stream?.getVideoTracks().some(track =>
      track.readyState === 'live' && !track.muted)) return '视频帧尚未就绪，请稍后定格。';

    const startedAt = performance.now();
    const scale = Math.min(1, MAX_EDGE / Math.max(video.videoWidth, video.videoHeight));
    const width = Math.round(video.videoWidth * scale);
    const height = Math.round(video.videoHeight * scale);
    if (!(width >= 48 && height >= 48)) return '当前视频尺寸过小，请检查摄像头后再定格。';
    const context = this.canvas.getContext('2d', {alpha: false});
    if (!context) return '此浏览器无法捕获当前画面。';
    try {
      if (this.canvas.width !== width) this.canvas.width = width;
      if (this.canvas.height !== height) this.canvas.height = height;
      context.drawImage(video, 0, 0, width, height);
    } catch {
      // A failed capture must not leave an earlier result over a resized canvas.
      if (this.state) this.resume();
      return '无法定格当前画面，请等待视频恢复后重试。';
    }
    const captureMs = performance.now() - startedAt;

    // The draw is synchronous with the click. Pause invalidates the LIVE epoch
    // before any encoding or network request can yield.
    this.live.pause();
    this.state = null;
    this.emit({id: ++this.sequence, width, height, captureMs, phase: 'detecting',
      message: '画面已定格，正在检测人脸。', faces: []});
    void this.run(async (signal, commit) => {
      const png = await new Promise(resolve => this.canvas.toBlob(resolve, 'image/png'));
      if (!png) throw new Error('定格帧编码失败，请重新定格。');
      const detected = await (await post('/api/detect', png, signal)).json();
      const {faces, detect_ms: detectMs} = detected;
      if (!faces.length) {
        commit({phase: 'no_face', detectMs, message: '定格画面中未检测到人脸。'});
        return;
      }
      if (faces.length > 1) {
        commit({phase: 'selecting', faces, detectMs, message: '检测到多张人脸，请选择一张进行单帧分析。'});
        return;
      }
      commit({detectMs});
      await this.analyzeFace(faces[0], signal, commit);
    });
    return '';
  }

  choose(id) {
    if (this.job || this.state?.phase !== 'selecting') return;
    const face = this.state.faces.find(candidate => candidate.id === id);
    if (face) void this.run((signal, commit) => this.analyzeFace(face, signal, commit));
  }

  async analyzeFace(face, signal, commit) {
    commit({phase: 'analyzing', faces: [face], face, message: '正在分析所选人脸。'});
    const png = Uint8Array.from(atob(face.input_preview.split(',')[1]), character => character.charCodeAt(0));
    const response = await post('/api/analyze', png, signal);
    const events = (await response.text()).trim().split('\n').map(line => JSON.parse(line));
    const last = events.at(-1);
    if (last?.event !== 'result') throw new Error(last?.detail ?? '未收到完整结果，请重新定格。');
    commit({phase: 'ok', result: last, message: '单帧分析完成。'});
  }

  async run(work) {
    const job = this.job = new AbortController();
    const timeout = setTimeout(() => job.abort(), 12000);
    const cancelTimeout = () => clearTimeout(timeout);
    job.signal.addEventListener('abort', cancelTimeout, {once: true});
    const commit = patch => {
      job.signal.throwIfAborted();
      if (this.job === job) this.emit(patch);
    };
    try {
      await work(job.signal, commit);
    } catch (error) {
      if (this.job === job) this.emit({phase: 'error', message: job.signal.aborted
        ? '单帧分析超时，请重新定格。'
        : error instanceof TypeError ? '本机服务连接中断，请检查服务后重新定格。' : error.message});
    } finally {
      cancelTimeout();
      job.signal.removeEventListener('abort', cancelTimeout);
      if (this.job === job) this.job = null;
    }
  }
}
