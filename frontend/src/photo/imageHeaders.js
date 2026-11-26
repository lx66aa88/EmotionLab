// Local-only input adaptation. The frozen detector/classifier contracts stay unchanged.
export const PHOTO_LIMITS = Object.freeze({
  sourceBytes: 128 * 1024 * 1024,
  sourcePixels: 100_000_000,
  sourceSide: 32_768,
  outputSide: 4096,
  outputBytes: 12 * 1024 * 1024,
  headerBytes: 2 * 1024 * 1024,
});

export function formatBytes(bytes) {
  return bytes >= 1024 * 1024
    ? `${(bytes / 1024 / 1024).toFixed(2)} MiB`
    : `${(bytes / 1024).toFixed(1)} KiB`;
}

export function fitPhoto(width, height, edge = PHOTO_LIMITS.outputSide) {
  if (
    !Number.isInteger(width) ||
    !Number.isInteger(height) ||
    Math.min(width, height) < 1
  )
    throw new Error("无法读取照片尺寸，请换一张完整的照片。");
  if (
    width * height > PHOTO_LIMITS.sourcePixels ||
    Math.max(width, height) > PHOTO_LIMITS.sourceSide
  )
    throw new Error(
      "这张照片超过 1 亿像素或单边 32768 像素的内存保护范围，请先导出较小版本。",
    );
  const ratio = Math.min(1, edge / Math.max(width, height));
  return [
    Math.max(1, Math.round(width * ratio)),
    Math.max(1, Math.round(height * ratio)),
  ];
}

function readTiffDirectory(buffer, little, start = 0) {
  const view = new DataView(buffer);
  if (start + 2 > view.byteLength) throw new Error("TIFF 元数据不完整。");
  const count = view.getUint16(start, little),
    end = start + 2 + count * 12;
  if (end + 4 > view.byteLength) throw new Error("TIFF 元数据不完整。");
  if (view.getUint32(end, little))
    throw new Error("请选择单帧照片，不支持多页 TIFF。");
  let width, height;
  for (let n = 0; n < count; n++) {
    const at = start + 2 + n * 12,
      tag = view.getUint16(at, little),
      type = view.getUint16(at + 2, little);
    if (
      (tag === 256 || tag === 257) &&
      view.getUint32(at + 4, little) === 1 &&
      [3, 4].includes(type)
    ) {
      const value =
        type === 3
          ? view.getUint16(at + 8, little)
          : view.getUint32(at + 8, little);
      if (tag === 256) width = value;
      else height = value;
    }
  }
  if (!width || !height) throw new Error("无法读取 TIFF 照片尺寸。");
  return { format: "TIFF", width, height };
}

// Inspect dimensions before decoding large files; never trust the filename/MIME.
export function readPhotoHeader(buffer) {
  const b = new Uint8Array(buffer),
    v = new DataView(buffer);
  const text = (start, end) => String.fromCharCode(...b.subarray(start, end));
  const result = (format, width, height, extra = {}) => ({
    format,
    width,
    height,
    ...extra,
  });
  if (b.length >= 24 && text(0, 8) === "\x89PNG\r\n\x1a\n") {
    for (let offset = 8; offset + 12 <= b.length; ) {
      const length = v.getUint32(offset),
        kind = text(offset + 4, offset + 8);
      if (kind === "acTL") throw new Error("请选择单帧照片，不支持动图。");
      if (kind === "IDAT" || kind === "IEND" || offset + length + 12 > b.length)
        break;
      offset += length + 12;
    }
    return result("PNG", v.getUint32(16), v.getUint32(20));
  }
  if (b.length >= 4 && b[0] === 255 && b[1] === 216) {
    for (let offset = 2; offset + 4 <= b.length; ) {
      if (b[offset] !== 255) break;
      while (b[offset] === 255) offset++;
      const marker = b[offset++];
      if (marker === 0xda || marker === 0xd9) break;
      if (marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) continue;
      if (offset + 2 > b.length) break;
      const length = v.getUint16(offset);
      if (length < 2 || offset + length > b.length) break;
      if (
        [
          0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd,
          0xce, 0xcf,
        ].includes(marker) &&
        length >= 8
      )
        return result("JPEG", v.getUint16(offset + 5), v.getUint16(offset + 3));
      offset += length;
    }
    throw new Error(
      "无法读取 JPEG 尺寸，文件可能损坏或包含过多附加数据。请重新导出照片。",
    );
  }
  if (b.length >= 30 && text(0, 4) === "RIFF" && text(8, 12) === "WEBP") {
    const kind = text(12, 16);
    if (kind === "VP8X") {
      if (b[20] & 2) throw new Error("请选择单帧照片，不支持动图。");
      return result(
        "WEBP",
        1 + b[24] + (b[25] << 8) + (b[26] << 16),
        1 + b[27] + (b[28] << 8) + (b[29] << 16),
      );
    }
    if (kind === "VP8 " && b[23] === 0x9d && b[24] === 1 && b[25] === 0x2a)
      return result(
        "WEBP",
        v.getUint16(26, true) & 0x3fff,
        v.getUint16(28, true) & 0x3fff,
      );
    if (kind === "VP8L" && b[20] === 0x2f)
      return result(
        "WEBP",
        1 + b[21] + ((b[22] & 0x3f) << 8),
        1 + (b[22] >> 6) + (b[23] << 2) + ((b[24] & 15) << 10),
      );
    throw new Error("无法读取 WebP 照片，请重新导出。");
  }
  if (b.length >= 26 && text(0, 2) === "BM") {
    const dib = v.getUint32(14, true);
    return dib === 12
      ? result("BMP", v.getUint16(18, true), v.getUint16(20, true))
      : result(
          "BMP",
          Math.abs(v.getInt32(18, true)),
          Math.abs(v.getInt32(22, true)),
        );
  }
  if (b.length >= 8 && ["II", "MM"].includes(text(0, 2))) {
    const little = text(0, 2) === "II";
    if (v.getUint16(2, little) !== 42)
      throw new Error("暂不支持这种 TIFF 变体，请选择普通单页照片。");
    const start = v.getUint32(4, little);
    if (start < 8) throw new Error("TIFF 元数据不完整。");
    if (start + 2 > b.length)
      return result("TIFF", undefined, undefined, {
        directoryOffset: start,
        littleEndian: little,
      });
    const count = v.getUint16(start, little),
      end = start + 2 + count * 12;
    if (end + 4 > b.length)
      return result("TIFF", undefined, undefined, {
        directoryOffset: start,
        littleEndian: little,
      });
    return readTiffDirectory(buffer, little, start);
  }
  if (b.length >= 16 && text(4, 8) === "ftyp") {
    const brands = text(8, Math.min(b.length, 64));
    if (/heic|heix|hevc|hevx|mif1|msf1/.test(brands))
      return result("HEIF", undefined, undefined, { nativeConversion: true });
  }
  throw new Error(
    "请选择 JPEG、PNG、WebP、BMP、单页 TIFF 或 HEIC/HEIF 照片；不支持 GIF、视频或损坏文件。",
  );
}

function checkAbort(signal) {
  if (signal?.aborted) throw new DOMException("已取消照片处理", "AbortError");
}

function loadPhoto(file, signal, format) {
  return new Promise((resolve, reject) => {
    checkAbort(signal);
    const image = new Image(),
      url = URL.createObjectURL(file);
    const cleanup = () => {
      image.onload = image.onerror = null;
      signal?.removeEventListener("abort", abort);
      URL.revokeObjectURL(url);
    };
    const abort = () => {
      cleanup();
      image.src = "";
      reject(new DOMException("已取消照片处理", "AbortError"));
    };
    image.decoding = "async";
    image.onload = () => {
      cleanup();
      resolve(image);
    };
    image.onerror = () => {
      cleanup();
      image.src = "";
      reject(
        new Error(
          `浏览器暂不能自动解码这张 ${format} 照片。可用 Mac「预览」导出 JPEG/PNG 后重试。`,
        ),
      );
    };
    signal?.addEventListener("abort", abort, { once: true });
    image.src = url;
  });
}

function jpegBlob(canvas, quality) {
  return new Promise((resolve, reject) =>
    canvas.toBlob(
      (blob) =>
        blob
          ? resolve(blob)
          : reject(new Error("照片压缩未完成，请重新选择。")),
      "image/jpeg",
      quality,
    ),
  );
}

export async function preparePhoto(file, { signal } = {}) {
  checkAbort(signal);
  if (!file.size) throw new Error("照片为空，请重新选择。");
  if (file.size > PHOTO_LIMITS.sourceBytes)
    throw new Error(
      "原照片超过 128 MiB 的内存保护范围，请先导出较小版本。常见手机原片会自动适配。",
    );
  let header = readPhotoHeader(
    await file.slice(0, PHOTO_LIMITS.headerBytes).arrayBuffer(),
  );
  // TIFF may put its image directory after the compressed pixel data. Read just
  // that bounded directory instead of treating a valid large photo as corrupt.
  if (header.directoryOffset !== undefined) {
    const offset = header.directoryOffset;
    if (offset + 2 > file.size) throw new Error("TIFF 元数据不完整。");
    const count = new DataView(
      await file.slice(offset, offset + 2).arrayBuffer(),
    ).getUint16(0, header.littleEndian);
    const length = 2 + count * 12 + 4;
    if (offset + length > file.size) throw new Error("TIFF 元数据不完整。");
    header = readTiffDirectory(
      await file.slice(offset, offset + length).arrayBuffer(),
      header.littleEndian,
    );
  }
  checkAbort(signal);
  if (header.width && header.height) fitPhoto(header.width, header.height);
  // Already valid inputs keep their exact bytes/pixels and original EXIF behavior.
  if (
    !header.nativeConversion &&
    header.width &&
    header.height &&
    Math.max(header.width, header.height) <= PHOTO_LIMITS.outputSide &&
    file.size <= PHOTO_LIMITS.outputBytes
  ) {
    return {
      file,
      info: {
        converted: false,
        originalBytes: file.size,
        outputBytes: file.size,
        originalSize: [header.width, header.height],
        outputSize: [header.width, header.height],
        originalFormat: header.format,
        outputFormat: header.format,
      },
    };
  }
  let image;
  try {
    image = await loadPhoto(file, signal, header.format);
  } catch (error) {
    // Keep the original Pillow-supported TIFF path available when the browser
    // has no native codec. Never forward an oversized file to the old server.
    if (
      error.name !== "AbortError" &&
      !header.nativeConversion &&
      header.width &&
      header.height &&
      header.width * header.height <= 25_000_000 &&
      Math.max(header.width, header.height) <= 20_000 &&
      file.size <= 20 * 1024 * 1024
    ) {
      checkAbort(signal);
      return {
        file,
        info: {
          converted: false,
          originalBytes: file.size,
          outputBytes: file.size,
          originalSize: [header.width, header.height],
          outputSize: [header.width, header.height],
          originalFormat: header.format,
          outputFormat: header.format,
          localDecoderFallback: true,
        },
      };
    }
    throw error;
  }
  let canvas;
  try {
    checkAbort(signal);
    // Browser decoding applies EXIF orientation. Export has no EXIF, preventing a second rotation.
    const originalSize = [image.naturalWidth, image.naturalHeight];
    let [width, height] = fitPhoto(...originalSize);
    canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d", { alpha: false });
    if (!context) throw new Error("浏览器图像转换不可用，请重新打开页面。");
    context.fillStyle = "#fff";
    context.fillRect(0, 0, width, height);
    context.imageSmoothingEnabled = true;
    context.imageSmoothingQuality = "high";
    context.drawImage(image, 0, 0, width, height);
    let blob;
    for (const quality of [0.92, 0.85, 0.75]) {
      checkAbort(signal);
      blob = await jpegBlob(canvas, quality);
      if (blob.size <= PHOTO_LIMITS.outputBytes) break;
    }
    checkAbort(signal);
    if (blob.size > PHOTO_LIMITS.outputBytes)
      throw new Error("自动压缩仍超过处理范围，请导出较小版本后重试。");
    return {
      file: new File([blob], "prepared-photo.jpg", { type: "image/jpeg" }),
      info: {
        converted: true,
        originalBytes: file.size,
        outputBytes: blob.size,
        originalSize,
        outputSize: [width, height],
        originalFormat: header.format,
        outputFormat: "JPEG",
        metadataRemoved: true,
      },
    };
  } finally {
    image.src = "";
    if (canvas) {
      canvas.width = 1;
      canvas.height = 1;
    }
  }
}
