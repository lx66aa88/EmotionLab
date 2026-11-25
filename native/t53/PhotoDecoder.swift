// Local-only T5.3 adapter. Uses Apple's installed ImageIO, no third-party decoder.
import Foundation
import ImageIO
import CoreGraphics
import Darwin

let maxBytes = 128 * 1024 * 1024
let maxPixels = 100_000_000
let maxSide = 32_768
let outputEdge = 4096
let outputBytes = 12 * 1024 * 1024

func emit(_ value: [String: Any]) {
    guard let data = try? JSONSerialization.data(withJSONObject: value, options: [.sortedKeys]) else { exit(2) }
    FileHandle.standardOutput.write(data)
}
func fail(_ message: String, _ code: String = "decode") -> Never {
    emit(["detail": message, "code": code]); exit(1)
}

// Bound bytes before creating an image source. No filename, temporary file or URL.
var bytes = Data()
while true {
    let part = FileHandle.standardInput.readData(ofLength: 65_536)
    if part.isEmpty { break }
    if bytes.count + part.count > maxBytes { fail("原照片超过 128 MiB 的保护范围。", "byte_limit") }
    bytes.append(part)
}
if bytes.isEmpty { fail("照片为空。", "empty") }
// Reject incomplete ISO-BMFF top-level boxes before ImageIO can tolerate truncation.
if bytes.count >= 8 && String(data: bytes[4..<8], encoding: .ascii) == "ftyp" {
    func u32(_ at: Int) -> UInt64 {
        return (0..<4).reduce(UInt64(0)) { ($0 << 8) | UInt64(bytes[at + $1]) }
    }
    var at = 0, boxes = 0
    var hasMeta = false
    while at < bytes.count {
        boxes += 1
        if boxes > 65_536 || at + 8 > bytes.count { fail("HEIF 容器不完整或过于复杂。") }
        var length = u32(at)
        let kind = String(data: bytes[(at+4)..<(at+8)], encoding: .ascii)
        var header = 8
        if length == 1 {
            if at + 16 > bytes.count { fail("HEIF 容器已截断。") }
            length = (u32(at+8) << 32) | u32(at+12); header = 16
        } else if length == 0 { length = UInt64(bytes.count - at) }
        if length < UInt64(header) || length > UInt64(bytes.count - at) { fail("HEIF 容器已截断或长度无效。") }
        if kind == "meta" { hasMeta = true }
        at += Int(length)
    }
    if !hasMeta { fail("HEIF 缺少主图像元数据。") }
}
let noCache = [kCGImageSourceShouldCache: false] as CFDictionary
guard let source = CGImageSourceCreateWithData(bytes as CFData, noCache),
      let type = CGImageSourceGetType(source) as String? else { fail("照片无法解码或文件已损坏。") }
let allowed = ["public.heic": "HEIF", "public.heif": "HEIF", "public.tiff": "TIFF"]
guard let format = allowed[type] else { fail("本机后备只处理 HEIC/HEIF 和单页 TIFF。", "format") }
if CGImageSourceGetCount(source) != 1 { fail("请选择单帧照片，不支持多页 TIFF 或 HEIF 序列。", "frames") }
guard let props = CGImageSourceCopyPropertiesAtIndex(source, 0, noCache) as? [CFString: Any],
      let width = (props[kCGImagePropertyPixelWidth] as? NSNumber)?.intValue,
      let height = (props[kCGImagePropertyPixelHeight] as? NSNumber)?.intValue,
      width > 0, height > 0 else { fail("无法读取照片尺寸。") }
if width > maxSide || height > maxSide || width > maxPixels / height {
    fail("这张照片超过 1 亿像素或单边 32768 像素的内存保护范围。", "pixel_limit")
}
let orientation = (props[kCGImagePropertyOrientation] as? NSNumber)?.intValue ?? 1
let options: [CFString: Any] = [
    kCGImageSourceShouldCache: false,
    kCGImageSourceCreateThumbnailFromImageAlways: true,
    kCGImageSourceCreateThumbnailWithTransform: true,
    kCGImageSourceThumbnailMaxPixelSize: min(outputEdge, max(width, height)),
    kCGImageSourceShouldAllowFloat: false
]
// Always derive from primary full image; do not use an embedded preview.
guard let thumbnail = CGImageSourceCreateThumbnailAtIndex(source, 0, options as CFDictionary),
      CGImageSourceGetStatusAtIndex(source, 0) == .statusComplete else { fail("照片解码不完整，请选择完整文件。") }
let w = thumbnail.width, h = thumbnail.height
if w > outputEdge || h > outputEdge || w < 1 || h < 1 { fail("照片缩小失败。") }
guard let colorSpace = CGColorSpace(name: CGColorSpace.sRGB),
      let context = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: w * 4,
                             space: colorSpace, bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue) else { fail("照片转换内存不足。") }
context.setFillColor(CGColor(srgbRed: 1, green: 1, blue: 1, alpha: 1))
context.fill(CGRect(x: 0, y: 0, width: w, height: h))
context.draw(thumbnail, in: CGRect(x: 0, y: 0, width: w, height: h))
guard let rgb = context.makeImage() else { fail("照片颜色转换失败。") }
var encoded = Data()
for quality in [0.92, 0.85, 0.75] {
    let target = NSMutableData()
    guard let dest = CGImageDestinationCreateWithData(target, "public.jpeg" as CFString, 1, nil) else { fail("JPEG 编码器不可用。") }
    // A new destination gets no source EXIF, GPS, names or comments. A standard sRGB profile is permitted.
    CGImageDestinationAddImage(dest, rgb, [kCGImageDestinationLossyCompressionQuality: quality] as CFDictionary)
    if !CGImageDestinationFinalize(dest) { fail("照片压缩失败。") }
    // Strip generated EXIF/XMP and comments without another lossy encode.
    let jpeg = target as Data
    var clean = Data(jpeg.prefix(2)), at = 2
    while at + 4 <= jpeg.count {
        if jpeg[at] != 0xff { fail("JPEG 编码结果无效。") }
        let marker = jpeg[at+1]
        if marker == 0xda || marker == 0xd9 { clean.append(jpeg.suffix(from: at)); break }
        let size = Int(jpeg[at+2]) * 256 + Int(jpeg[at+3])
        if size < 2 || at + 2 + size > jpeg.count { fail("JPEG 编码结果已截断。") }
        if marker != 0xe1 && marker != 0xfe { clean.append(jpeg[at..<(at+2+size)]) }
        at += 2 + size
    }
    encoded = clean
    if encoded.count <= outputBytes { break }
}
if encoded.count > outputBytes { fail("自动压缩仍超过 12 MiB，请选择较小照片。", "output_limit") }
let oriented = orientation >= 5 && orientation <= 8 ? [height, width] : [width, height]
emit(["jpeg": encoded.base64EncodedString(), "info": [
    "converted": true, "originalBytes": bytes.count, "outputBytes": encoded.count,
    "originalSize": oriented, "sourceSize": [width, height], "outputSize": [w, h],
    "originalFormat": format, "outputFormat": "JPEG", "exifOrientation": orientation,
    "orientationApplied": orientation >= 2 && orientation <= 8,
    "metadataRemoved": true, "alphaBackground": "white", "color": "8-bit sRGB / SDR",
    "decoder": "Apple ImageIO / t53-imageio-v1", "localDecoderFallback": true
]])
