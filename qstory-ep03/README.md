# 余问 QStory｜EP.03《十万亿个分身》

可编辑的 Remotion 短片工程：横版 3840×2160、30 fps、5400 帧（180 秒）。画面以确定性 SVG 程序绘制，再由 Remotion 栅格化到 4K；同时注册 1920×1080 预览版。`watch.html` 是本机成片播放器，提供从头播放与高潮、静音、片尾跳转。字幕与镜头按全片帧号求值，可直接跳到任意帧。

## 开始

在 macOS 上使用 Node.js/npm、百炼 CLI `bl`（仅重新生成配音时需要）、`ffmpeg`、`ffprobe` 和 `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`。渲染脚本固定使用此 Chrome 路径。字体使用系统 PingFang SC；工程不携带或分发字体，其他机器需要自行安装相同字体以保持字形和排版。

```bash
cd qstory-ep03
npm ci                 # 新环境安装锁定依赖；Remotion 套件版本为 4.0.534
npm run typecheck
npm run studio         # Remotion Studio，端口 3103
python3 scripts/serve-preview.py # 本机成片播放器，端口 3104，支持章节跳转
```

当前工作区也可复用仓库根目录的兼容依赖；独立检出时运行 `npm ci`。命令均在本目录执行，生成物留在本项目内：渲染输出至 `out/` 与 `review/`，最终音频输出至 `public/audio-bailian/`、`review/` 和 `src/audio-timing.json`。

## 音频、预览与导出

```bash
npm run audio
npm run stills
npm run render
```

- `npm run audio` 用百炼默认 Profile 的 CosyVoice v3 Flash / `longtian_v3`（龙天）生成中文旁白，按真实 PCM 时长安排字幕，复用原创音乐与音效，再做响度混音。需要已鉴权的百炼 CLI；会向百炼发送本片旁白文字并可能计费。缓存、原始返回音频与正规化 WAV 保存在 `public/audio-bailian/`，不保存凭据或签名下载链接。预检实际模型与音色，不把命令参数当作服务端返回证据。
- 先前的本机 Tingting 版本保留在 `public/audio/`，可通过 `npm run audio:local` 重建；此命令会改写字幕时序，重建正式百炼版本后再导出。
- `npm run stills` 输出无声的 1080p 代表帧到 `review/`，用于画面检查，不是带旁白影片。
- `npm run render` 导出有声 4K 主片：`out/QStory-EP03-十万亿个分身-4K.mp4`。编码为 H.264/AAC。首次渲染会在 `out/bundle/` 生成本工程的 Remotion bundle。
- 单帧可按需渲染：`node scripts/render.mjs frame <帧号>` 输出无声 1080p PNG；`node scripts/render.mjs frame4k <帧号>` 输出无声 4K PNG。帧号范围为 `0`–`5399`。
- `node scripts/render.mjs sample` 输出有声的高潮片段预览 `out/climax-preview-1080p.mp4`；`node scripts/render.mjs boundaries` 输出场景边界的无声 1080p PNG。

百炼 `raw/` 保留服务端原件；流式 WAV 的占位长度字段经 PCM 散列一致性核对后，在 `canonical-24k/` 修正容器头。正式混音使用已严格解码的 48kHz 片段。

字幕由 PCM 对齐后的 `src/audio-timing.json` 驱动画面。交付核验脚本同时导出实际 SRT 到 `out/QStory-EP03-zh.srt`：

```bash
python3 scripts/validate-delivery.py --metadata-only
python3 scripts/validate-delivery.py --full
```

`--metadata-only` 检查源时间轴、PCM 音频时序和字幕，并在 4K MP4 已存在时读取其元数据；完成影片渲染后用 `--full` 要求最终 MP4 并执行完整解码。两种模式都会写 `review/validation.json`。原始分镜、旁白文案和计划字幕位于 `source/`；`source/validate.py` 检查交接包的元数据，不验证 React 画面或成片。

## 文件

- `source/`：导演稿、24 镜、8 场景、25 条原始旁白/计划字幕及时间轴基线。
- `src/`：Remotion Composition、场景、视觉组件和按实际 PCM 时长生成的字幕时序。
- `scripts/`：音频制作、视频渲染和交付核验命令。
- `public/audio-bailian/`：最终百炼语音、原始片段、缓存、复用的音乐音效与混音 WAV。
- `public/audio/`：保留的本机配音版本与原创音乐音效基线。
- `out/`：Remotion bundle、4K 主片及预览导出；可重建。
- `review/`：静帧、机器音频 QA 和交付验证报告，供人工复核。

## 创作边界与验收

全片保持源文件中的 24 镜、8 场景和 25 条旁白，画面不调用实时 LLM、真实 Agent 群或外部影像；中文配音使用百炼云端语音合成。片中的协作与实验结果均为预先编排的科幻思想实验。

发布说明：

> 本片为“余问 QStory｜感受SI”系列科幻思想实验。《十万亿个分身》是规模意象，画面中的节点数量、时间比例与协作能力均为艺术设定。高带宽传输不等同于即时理解或无损意识融合；片中共享的是模型、假设与可验证的工作。实验结果为虚构模拟，不代表当前AI能力。中文旁白为百炼 AI 合成；画面为程序化绘制，音乐与音效为原创程序化合成。

构建、时间轴检查、解码和机器 QA 不等于人工验收。仍需单独完成全片听审、实际播放检查和观众理解评估；在这些检查完成前，不把自动化检查描述为成片通过。

最终输出的 MP4 与可编辑工程 ZIP 分开交付；工程 ZIP 保留源文件、音频素材、字幕及验证记录，省略 `node_modules`、Remotion bundle 与中间混音。
