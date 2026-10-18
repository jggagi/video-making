# 前两部短片的复用索引

这些文件位于最初工作区 `/Users/guoq/Documents/ChatGPT/video/`。它们是可选的实现参考，技能在别的工作区也应能执行。引用前先核实文件和实际入口；不复制旧报告作为新作品验收。

## 《一眼万年》：同时间轴的横竖屏

- `si-eternity/README.md`、`TITLE-V3.md`：实际 Composition、素材、配音版本和渲染入口。
- `si-eternity/PORTRAIT-V4.md`、`src/portrait/`：与横屏同为 180 秒，复用声音和事件时间，竖屏重新布置主物、HUD 与字幕，避免裁切。
- `si-eternity/AUDIO-V2.md`、`audio-v3/`：配音缓存、独立发音文本、真实时长、混音与版本来源。
- `si-eternity/scripts/validate-portrait-v4.py`：实际导出抽帧、PCM/编码音轨同步、AAC 填充与旧版本保留。

新技能复用其“共享时间轴＋独立布局”的方法；**180 秒不是新默认**。

## 《7±2 的囚笼》：原生 4K 与手机交付

- `si-cage-7plus2/README.md`、`UHD-V3.md`：从矢量/DOM 逻辑画布原生渲染到 3840 × 2160，区分原生输出与已编码视频放大。
- `si-cage-7plus2/XHS-V1.md`、`src/xhs/`、`xhs-timeline.json`：独立竖屏布局、可读字幕、手机总览、封面与发布文件。该历史版本由 180 秒改编成 60 秒；新技能两版统一 120 秒，不照搬该删节方案。
- `si-cage-7plus2/VOICED-V2.md`：段落缓存、完整保留源 PCM、提供商 WAV 头修复问题、只在本地检查且不上传 ASR 的边界。
- `si-cage-7plus2/scripts/validate-xhs.py`、`validate-uhd.py`：独立验证实际成片、音频与关键事件。
- 两工程的 `scripts/package*.py`：保留可编辑源码、本地素材、精简 QA、ZIP 完整性与哈希清单，排除依赖和完整旧成片。

青金色、科幻题材、固定幕数、60 fps、具体配音模型/声音和段落不是普遍创作要求。本技能采用 60 fps 作为可改的连续制作默认，时长和画幅以当前用户约定为准。
