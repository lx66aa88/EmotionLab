# 中文工程与技术文档导航

第一次阅读先看[中文首页](../README.zh-CN.md)，接着看[系统图](SYSTEM_ARCHITECTURE.md)和[项目历程](PROJECT_HISTORY.zh-CN.md)。要动手运行，从[安装与运行](GETTING_STARTED.md)选择独立画廊、CLI 或集成网页。

| 文档 | 阅读时能找到什么 |
| --- | --- |
| [课程与需求](REQUIREMENTS.md) | 书面要求、三种数据用途、成绩组成和课程验收 |
| [系统架构](SYSTEM_ARCHITECTURE.md) | 数据到产品总图、浏览器/服务图和真实 API |
| [数据处理](DATA_PIPELINE.md) | CSV、顺序、归一化、重复风险、产品人脸裁剪 |
| [模型结构](MODEL_ARCHITECTURE.md) | 基础 CNN、残差块、w16/w32 和参数量 |
| [训练流程](TRAINING_PIPELINE.md) | 增强、优化器、前后向、选模、轮末验证 |
| [实验与误差](EXPERIMENTS.md) | 性能发展、失败实验、代价、逐类表现 |
| [三模型推理](ENSEMBLE_INFERENCE.md) | 两视图、六概率、CPU 重载与校验 |
| [产品设计](PRODUCT_DESIGN.md) 与[真实截图](PRODUCT_GALLERY.md) | HUMAN SIGNAL 的设计、五个入口及演示条件 |
| [Seven Signals](SEVEN_SIGNALS.md) | 七个原创带面形态、运动语义与代码 |
| [游戏设计](GAME_DESIGN.md) | 七轮目标、计分、RAW 稳定性与异常 |
| [软件验证](TESTING_AND_VALIDATION.md) | 自动化回归、物理/受控观测与范围 |
| [历史](PROJECT_HISTORY.zh-CN.md) | 从构思到 T10 的真实阶段与转向理由 |
| [人员与分工](TEAM_AND_CONTRIBUTIONS.md) | 四个岗位、团队指标、实施实验的讲解路径 |
| [限制](LIMITATIONS.md) 与[来源](REFERENCES.md) | 验证偏差、适用范围、第三方依赖与 AI 辅助披露 |
| [完整文件树](REPOSITORY_TREE.md) | 当前发布版代码、配置和证据目录定位 |

| 英文目录 | 对应含义 | 主要入口 |
| --- | --- | --- |
| [src](../src/) | Python 核心 | `dataset.py` 读取，`model.py`、`t3_models.py`、`t37_models.py` 定义网络，`ensemble.py` 加载推理，`t62_web.py` 启动网页，`classroom.py` 提供 CLI |
| [web/human-signal](../web/human-signal/) | React 前端及构建 | `vite.t72.config.js` 固定正式入口，`src/AppT72.jsx` 接产品，`seven-signals/` 维护雕塑与画廊 |
| [configs](../configs/) | 配置与冻结清单 | `t3/`、`t35/`、`t37/` 保存训练选择，`inference/best_triple.json` 记录部署合同 |
| [results](../results/) | 历史实验数值与图 | `t4_step2_analysis_20261104/` 统一数表和图，`t38_triple_tta_20261104/run01/summary.json` 对应冻结读数 |
| [experiments](../experiments/) | 实验阅读入口 | 按优化问题寻找逐轮日志、对比、混淆和时间 |
| [assets](../assets/) | 作品集封面与演示 | SVG Banner、实际浏览器截图和准确率图 |
| [tests](../tests/) | Python 自动化用例 | 数据契约、训练组件、冻结推理、照片与原生适配 |
| [web/human-signal/tests](../web/human-signal/tests/) | 前端回归 | 照片输入、LIVE、雕塑显示、防抖和游戏 |
| [scripts](../scripts/) | 运行与预检脚本 | 原课堂启动预检与展示图再生成 |
| [examples](../examples/) | 安全示例输入 | 原创 48×48 无人脸图案 CLI 冒烟 |
| [models](../models/) | 授权的第三方检测资产 | 固定 YuNet ONNX、来源和 MIT 提示 |
| [native](../native/) | macOS 可选照片适配 | Swift 源和原编译版本记录 |

根目录依赖锁文件针对不同历史阶段。新隔离环境使用 `requirements-web.txt`，分类 CLI 使用 `requirements-inference.txt`。
