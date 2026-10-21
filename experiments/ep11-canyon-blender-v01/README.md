# EP11 · 瓷器峡谷 Blender 样片 01

这是针对 EP11 v02 峡谷段制作的 **8 秒造型、材质与运动实验**。用户反馈三维图形不成熟后，授权先尝试 Blender 路线。本目录保留可编辑场景、生成脚本、实际渲染与验收记录；正式 EP11 影片和小红书笔记不属于本次修改范围。

## 观看

- [左右对照](media/canyon-side-by-side.mp4)：左为原版 46–54 秒，右为 Blender 样片。
- [Blender 单独播放](media/new-canyon-clean.mp4)。
- [原版片段](media/old-canyon.mp4)。
- [本地播放器](watch.html)：可在同一时间点切换对照、新版和原版。
- [原生 4K 静帧](review/hero-4k.png)。

运动样片为原生 **1080 × 1920、24 fps、192 帧、8 秒**；左右对照画布为 1440 × 1440。4K 静帧为 2160 × 3840，不能把它当作 4K 动画交付。

画面把断裂瓷器放大成峡谷：主碎片先下坠，在 1–3 秒间悬停，随后升起；金色从近处沿裂隙向远处推进。结尾仍是悬浮状态，没有呈现完整归位。声音复用 v02 的音乐和音效 46–54 秒，省略旁白。原声音部原为旁白留出较大余量，因此本样片对共享混音施加同一常量增益，目标约 −20 LUFS、真峰值上限 −1 dBTP，保持声部比例和动态；两个版本使用相同音轨。本次没有调用新的配音、图片或视频生成服务。

## 如何判断这次尝试

比较的是一次共同调整了造型、材质、灯光、摄影和渲染的制作尝试，不能把差异全部归因于引擎。Blender 负责本样片的几何、材质、灯光、动画、景深和运动模糊。若方向得到认可，可以把渲染片段作为视频素材交回原 Remotion 工程，继续处理时间轴、字幕、版式与合成；本次没有改写整片工程。

这版仍有明确限制：两岸大块釉面的造型偏抽象；主碎片还没有与母体匹配的归位缺口；金色采用沿空间推进的材质过渡与曲面，并非流体模拟。它用于判断瓷器微距的空间和材质方向是否值得继续，不能据技术检查宣称达到用户期望的艺术品质。

## 可编辑工程

- `project/porcelain-canyon-look06.blend`：最终采用的独立场景，Blender 4.5.9 LTS；原生关键帧，可直接打开、拖动 1–192 帧并编辑。该二进制场景保存在工程 ZIP 中，不放进普通 Git。
- `project/build_scene.py`、`project/geometry.py`：原始几何、材质、摄影及动画生成器，无外部网格或贴图依赖。
- `project/render_saved.py`：从已保存场景渲染，逐帧记录 SHA-256，支持校验后恢复；本机版要求输出至已验证的 AgentDev 卷。
- `project/assemble.py`：将 192 帧和既有 v02 声音合成样片，生成左右对照和技术报告；该脚本需要完整仓库中的 v02 源文件。
- `project/package_study.py`：打包并逐成员校验工程 ZIP。
- `media/canyon-8s-master.wav`：工程包中的 48 kHz 立体声 PCM 音频母版。独立打开 `.blend` 后，可用此音轨重新剪辑输出，无须调用语音服务。

工程 ZIP 不重复收录 MP4。独立恢复播放器时，把 Release 的两段视频下载到解压目录的 `media/` 中，分别命名为 `new-canyon-clean.mp4` 与 `canyon-side-by-side.mp4`。原版单独片段仍可从本仓库已有正式 v02 视频的 46–54 秒提取；并排对照已经包含该片段。

合成脚本使用已有 FFmpeg / FFprobe 和带 Pillow 的 Python；本机运行使用 Codex 随附 Python。中文标签由 Pillow 生成底板，适用于本机不含 `drawtext` 滤镜的 FFmpeg 构建。脚本拒绝覆盖已有输出，修改时应复制为新版本或先保留现有输出。

在本仓库内从保存的场景重渲染（先按仓库 AGENTS.md 检查工作站与外置卷；输出目录须全新且已存在）：

```sh
/Users/guoq/.local/bin/agent-dev run -- \
  /Users/guoq/Applications/Blender-LastSignal.app/Contents/MacOS/Blender \
  --background --factory-startup --python-exit-code 1 \
  --python experiments/ep11-canyon-blender-v01/project/render_saved.py -- \
  --blend experiments/ep11-canyon-blender-v01/project/porcelain-canyon-look06.blend \
  --out /Volumes/AgentDev/Scratch/your-new-frame-directory \
  --frames 1-192 --width 1080 --height 1920 --samples 48
```

本地播放：

```sh
node experiments/ep11-canyon-blender-v01/project/serve.mjs
```

打开其打印的 `127.0.0.1` 地址。播放器仅监听本机。

## 记录与备份

`review/render-report.json` 绑定实际 `.blend` 哈希、渲染配置及全部 192 帧；`review/assembly-qa.json` 记录编码、完整解码、音频来源与采样数；`review/acceptance.json` 分别记录技术、模型辅助画面检查、本机浏览器播放和用户验收状态。用户与目标设备验收不能从自动检查推断。

未采用的 look-01 至 look-05、第一轮中止的帧及其源场景保留在本机，不进入正式影片或本样片工程包。完整 PNG 序列属于可重建缓存，保存在外置开发卷，不放进工程 ZIP 或普通 Git。

本实验使用独立的 [Release 目录](https://github.com/jggagi/video-making/blob/main/experiments/ep11-canyon-blender-v01/review/standalone-release-catalog.json)，不加入正式影片的 `final/` 库。下载入口：[study-ep11-canyon-blender-v01](https://github.com/jggagi/video-making/releases/tag/study-ep11-canyon-blender-v01)。上传状态与远端大小、SHA-256 验证以 `review/archive-verification.json` 为准。
