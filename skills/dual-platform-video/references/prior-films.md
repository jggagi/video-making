# Superintelligence 短片的复用索引

这些文件位于最初工作区 `/Users/guoq/Documents/ChatGPT/video/`，源码也保存在本仓库。它们是可选的实现参考，技能在别的工作区也应能执行。引用前先核实实际 Composition、媒体与版本；不复制旧报告作为新作品验收。两案共同提供“确定性数学渲染＋共享状态/PCM 工作流＋独立双画幅”的参考，新片将这些方法用于 3840 × 2160 原生 4K 和 9:16 交付；历史版规格分别如下，不能据此补写不存在的导出。

## 《一眼万年 / One Blink, Ten Millennia》：同时间轴的横竖屏

- `si-eternity/README.md`、`TITLE-V3.md`、`src/Root.tsx`：实际 Composition、素材、配音版本和渲染入口。现存横屏为 1920 × 1080，180 秒、60 fps、10,800 帧；不能标成已完成的 4K 版本。代码/矢量场景可参考后另做原生 4K 栅格化与验收。
- `si-eternity/PORTRAIT-V4.md`、`src/portrait/`：1080 × 1920 的 9:16 版与横屏同为 180 秒，复用相同事件帧和 `public/audio-v3/soundtrack.wav` PCM 母带，竖屏重新布置主物、HUD 与字幕，避免裁切。
- `si-eternity/src/`：由帧和固定种子驱动的节点、搜索树、流形等数学场景；复用确定性状态与独立布局的方法，不能把实时随机数或系统时钟带入渲染。
- `si-eternity/AUDIO-V2.md`、`public/audio-v3/`：配音缓存、独立发音文本、真实时长、混音与版本来源。
- `si-eternity/scripts/validate-portrait-v4.py`：实际导出抽帧、PCM/编码音轨同步、AAC 填充与旧版本保留。

复用其“共享时间轴＋独立布局＋同一 PCM 母带”的方法；**180 秒不是新默认**，当前目标由 `delivery.json` 的 `T` 决定，缺省 120 秒。

## 《7±2 的囚笼 / The Cage of 7±2》：原生 4K 与手机交付

- `si-cage-7plus2/README.md`、`UHD-V3.md`、`src/Root.tsx`：180 秒、60 fps、10,800 帧，从矢量/DOM 逻辑画布原生渲染到 3840 × 2160，区分原生输出与已编码视频放大。
- `si-cage-7plus2/src/`：帧驱动、固定种子的节点负载、搜索剪枝和空间变换，用程序化数学状态表达认知容量与超智能；主物状态、镜头坐标和 HUD 应保持一致，声音触发来自事件帧。
- `si-cage-7plus2/XHS-V1.md`、`src/xhs/`、`xhs-timeline.json`：独立 9:16 布局、可读字幕、手机总览、封面与发布文件。历史竖屏母版为 2160 × 3840，发布版为 1080 × 1920，由 180 秒另编为 60 秒。它复用源 PCM/配音缓存再混音，不能声称与 180 秒版复用整条母带。新片两版锁定同一 `T`、同一 PCM 母带，不照搬该删节方案。
- `si-cage-7plus2/VOICED-V2.md`：段落缓存、完整保留源 PCM、提供商 WAV 头修复问题、只在本地检查且不上传 ASR 的边界。
- `si-cage-7plus2/scripts/validate-xhs.py`、`validate-uhd.py`：独立验证实际成片、音频与关键事件。
- 两工程的 `scripts/package*.py`：保留可编辑源码、本地素材、精简 QA、ZIP 完整性与哈希清单，排除依赖和完整旧成片。

制作复盘形成的发音词表、事件帧音效、竖屏安全区、持续空间运动、HUD 拼写与暗部色带检查见 [制作与验收](production-and-qa.md)。历史实现不等于已满足新增门槛，不追改其时长或验收状态。

青金色、科幻题材、固定幕数、60 fps、具体配音模型/声音和段落不是普遍创作要求。本技能采用 60 fps 作为可改的连续制作默认，时长和画幅以当前用户约定为准。旧项目的 TTS、声音/人物授权或“不上传 ASR”约定只适用于其原始范围；新任务先核实当前会话授权，不盲目复制许可或禁令。
