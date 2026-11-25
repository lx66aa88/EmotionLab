# T5.3 本机解码资源与许可

本阶段没有添加 Python/npm 第三方包，没有升级现有 PyTorch、NumPy、Pillow 或 OpenCV。`PhotoDecoder.swift` 是本工程新增适配代码；可执行文件仅链接本机 macOS Foundation、ImageIO、CoreGraphics、Swift 系统库。框架沿用用户已安装 macOS 的许可，不随工程复制 Apple 框架；本工程没有将 Apple 框架重新标为开源。

固定源码、二进制 SHA-256、实际编译器和系统版本见 `BUILD.json`。当前实测 macOS 27.0.1 (26A434)、arm64、Apple Swift 6.4.2；编译部署目标为 macOS 13.0，但只验收当前 Mac，没有声称其他 macOS、Intel、Windows 或 Linux 通过。启动只执行随工程保存、摘要核对的本机二进制；不运行 Swift 编译器、不安装包、不联网下载。

API 依据（Apple 官方文档，2026-11-08 核对）：

- [ThumbnailWithTransform](https://developer.apple.com/documentation/imageio/kcgimagesourcecreatethumbnailwithtransform)：使缩略图方向与比例匹配图像。
- [ThumbnailMaxPixelSize](https://developer.apple.com/documentation/imageio/kcgimagesourcethumbnailmaxpixelsize)：限制输出最长边。
- [ShouldCache](https://developer.apple.com/documentation/imageio/kcgimagesourceshouldcache)：创建源时关闭完整解码缓存。
- [CreateThumbnailFromImageAlways](https://developer.apple.com/documentation/imageio/kcgimagesourcecreatethumbnailfromimagealways)：从主图生成，避免直接取内嵌低清预览。

没有复制外部解码器源代码，也未添加 libheif/pillow-heif。既有 OpenCV/YuNet 与字体许可继续见 `vendor/t52/licenses/`、`models/face_detection_yunet/` 和前端 public 内原许可。

测试照片来源与转换方法在本轮 `results/t53_photo_compat_20261108/fixtures/SOURCES.json`。HEIC/HEIF 是以完整真实照片重新编码得到的有效容器，不是改后缀、只有文件头的占位文件，也不冒充 iPhone 相机原片。素材不用于训练或准确率评估，不表示被摄者或 NASA 为本项目背书。
