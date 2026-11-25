// Native fallback only for HEIF/TIFF; reuse the proven browser path for other formats.
import {PHOTO_LIMITS, fitPhoto, readPhotoHeader, preparePhoto as prepareBrowser} from './photoPreparation.js';
export {formatBytes, PHOTO_LIMITS} from './photoPreparation.js';
let previous = Promise.resolve();
const aborted = signal => {if (signal?.aborted) throw new DOMException('已取消照片处理', 'AbortError');};
const pause = signal => new Promise((resolve, reject) => {
  aborted(signal);
  const cancel = () => {clearTimeout(timer); reject(new DOMException('已取消照片处理', 'AbortError'));};
  const timer = setTimeout(() => {signal?.removeEventListener('abort', cancel); resolve();}, 100);
  signal?.addEventListener('abort', cancel, {once:true});
});

async function prepare(file, {signal} = {}) {
  aborted(signal);
  if (!file.size) throw new Error('照片为空，请重新选择。');
  if (file.size > PHOTO_LIMITS.sourceBytes) throw new Error('原照片超过 128 MiB 的内存保护范围，请先导出较小版本。');
  const head = await file.slice(0, PHOTO_LIMITS.headerBytes).arrayBuffer();
  aborted(signal);
  const b = new Uint8Array(head);
  const bmff = b.length >= 16 && String.fromCharCode(...b.slice(4,8)) === 'ftyp';
  const header = bmff ? {format:'HEIF'} : readPhotoHeader(head);
  if (!bmff && header.format !== 'TIFF') return prepareBrowser(file, {signal});
  if (header.width && header.height) fitPhoto(header.width, header.height);
  let data;
  for (let attempt = 0; attempt < 15; attempt++) {
    aborted(signal);
    const response = await fetch('/api/prepare-photo', {method:'POST', headers:{'Content-Type':'application/octet-stream'}, body:file, signal});
    data = await response.json();
    aborted(signal);
    if (response.status === 409 && data.code === 'busy' && attempt < 14) {await pause(signal); continue;}
    if (!response.ok) throw new Error(data.detail || '本机照片转换未完成。');
    break;
  }
  aborted(signal);
  const bytes = Uint8Array.from(atob(data.jpeg), c => c.charCodeAt(0));
  return {file:new File([bytes], 'prepared-photo.jpg', {type:'image/jpeg'}), info:data.info};
}

export function preparePhoto(file, options = {}) {
  // Serializes canvas/native work even if a previous conversion is being cancelled.
  const job = previous.catch(() => {}).then(() => prepare(file, options));
  previous = job.then(() => undefined, () => undefined);
  return job;
}
