# 巴别图书馆的尽头 · 可复现工程

本工程只制作小红书版：原生竖屏 2160×3840、60 fps、120 秒、7200 帧。最终路径和状态以 [交付清单](../delivery.json) 为准；原稿在 [source/script.md](../source/script.md)，改编稿、制作意图和科学边界分别见 [adapted-script.md](adapted-script.md)、[brief.md](brief.md) 与 [scientific-notes.md](scientific-notes.md)。账号发布另按用户明确指令执行。

## 时间轴与入口

- [timeline.json](timeline.json)：`fps`、`totalFrames`、`platforms`，以及 `scenes[]`、`narration[]`、`events[]`。所有区间采用 `[startFrame, endFrame)`；48000 Hz 音频样本位置为 `frame × 800`。
- [segments.json](segments.json)：旁白段按序包含 `id`、`startFrame`、`endFrame`、`display_subtitle`、`tts_phonetic_text` 和 `chunks[]`。它是字幕/音频构建的输入。
- [src/Root.tsx](src/Root.tsx) 注册 `PortraitVertical` Composition；[package.json](package.json) 固定 Remotion 4.0.534、React 19.1.0 和 TypeScript 5.9.3。当前仓库根目录的 `node_modules` 提供这些已锁定依赖，不需要为本片另装或升级依赖。
- [src/Geometry.tsx](src/Geometry.tsx) 与 [src/Film.tsx](src/Film.tsx) 使用 DOM/SVG 矢量画面；制作不依赖云端图片/视频生成。

## 音频输入与授权边界

[audio-authorization.json](audio-authorization.json) 把本次十段的有声旁白授权绑定到精确文本 SHA-256、Aliyun Bailian、`longtian_v3`。实际返回的模型和音色记录在 [provider-manifest.json](public/audio/provider-manifest.json)：`cosyvoice-v3-flash` / `longtian_v3`。本记录只描述当前 S01–S10 的授权证据；之后的任务仍按当时的用户指令、已有效授权和提供商规则判断。

[synthesize.py](scripts/synthesize.py) 的 `--authorized all` 是可能调用云端的命令，不是工程初始化步骤：脚本会先校验授权和文本哈希、复用设置与文本完全匹配的缓存，只有缺少匹配缓存时才尝试调用。不要把它放入自动安装或构建脚本；改动旁白文本后重新核对当时的授权范围、文本哈希与项目记录。已生成的逐段原始、标准化与 48 kHz cue 文件保存在 `public/audio/{raw,canonical,cues}/`，摘要与有效模型/音色在 provider manifest。

[build_audio.py](scripts/build_audio.py) 不调用提供商。它读取 `segments.json`、授权、provider manifest 与每段 `cue_path` / `cue_sha256` / `actual_samples_48k` / `duration_seconds`，校验完整 48 kHz 单声道 PCM16 cue，将完整语音放在段首；语音超出时间窗时失败，不裁字、不变速。输出 `audio-timing.json`（段边界、实测活动区间和哈希、估算字幕对齐）、[captions.srt](../小红书/captions.srt)、旁白/程序化配乐/音效三条 48 kHz 立体声 PCM stem、精确 120 秒 `master.wav`、`mix-manifest.json` 和 `review/audio-qa.json`。字幕按实测 PCM 活动区间和分句字数估算，并非 ASR 或强制对齐；音频 QA 不代表人工听音。

## 制作命令

从仓库根目录执行。先运行轻量检查；在 Q 的本地 Mac 上启动构建/渲染/完整媒体扫描前，按仓库说明检查当前 `agent-dev status --json` 卷身份与错误。重工作经 `agent-dev run -- ...` 串行执行；不要因卷检查失败改到其他临时位置绕过。

```sh
# 源码类型检查与不读取 cue 的音频输入/授权校验
npm --prefix deliveries/si-babel-library/project run typecheck
python3 deliveries/si-babel-library/project/scripts/build_audio.py --validate-source

# 仅在已有精确授权且明确需要补缺失 cue 时手动执行；可能产生云端调用
python3 deliveries/si-babel-library/project/scripts/synthesize.py --authorized all

# 从已核验的本地 cues 构建 PCM stems / master / SRT / audio QA
cd deliveries/si-babel-library/project
agent-dev run -- python3 scripts/build_audio.py --mix

# 关键源帧、封面、带真实声音短样片、静音视频轨
agent-dev run -- node scripts/render.mjs stills
agent-dev run -- node scripts/render.mjs covers
agent-dev run -- node scripts/render.mjs preview 0 419
agent-dev run -- node scripts/render.mjs preview 4380 4559
agent-dev run -- node scripts/render.mjs video

# 把 READY 指针中的暂存视频与精确 master 合成最终 MP4
agent-dev run -- python3 scripts/mux.py

# 返回仓库根目录再做成片检查
cd ../../..
# 当前Mac已核验的QA Python；后续用Codex load_workspace_dependencies重新定位
BABEL_QA_PYTHON=/Users/guoq/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
agent-dev run -- python3 skills/dual-platform-video/scripts/validate_delivery.py \
  deliveries/si-babel-library --scan-source
agent-dev run -- "$BABEL_QA_PYTHON" skills/dual-platform-video/scripts/scan_visual_qc.py \
  --media deliveries/si-babel-library/小红书/si-babel-library-xiaohongshu-120s-portrait.mp4 \
  --expected-frames 7200 \
  --output-dir deliveries/si-babel-library/review/visual-qc-xiaohongshu
```

在 Mac 上 [render.mjs](scripts/render.mjs) 使用已安装的 Google Chrome（`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`）；视频/预览模式校验原生尺寸、帧率和总帧数。`video` 输出静音视频轨和 `review/render-staging.json`，`mux.py` 检查暂存文件哈希、PCM 母带长度与目标不存在后生成清单指定的 MP4 和 `review/mux-provenance.json`。`stills` 与 `covers` 写固定 PNG 路径，会替换同名图片；如需保留当前证据，先另存。预览与完整视频的已有目标、mux 目标或暂存指针会被拒绝，需先检查并人工处理现有文件，不能直接覆盖。

完整交付检查应同时满足：音频 QA 的技术指标；从最终 MP4 起始处连续扫描全部 7200 帧；检查开场、转折、快速段、字幕、安全区、暗部和结尾静帧；再分别记录连续人工观看/听音及目标手机/App 播放。扫描只筛查机器可检测的视觉异常，不能证明画面体验、发音、听感或设备播放通过。每种证据及真实状态记录在 [review/acceptance.md](../review/acceptance.md)；自动结果不能代填人工验收。详细门槛见仓库 [验收流程](../../../skills/dual-platform-video/SKILL.md)、[逐帧视觉完整性](../../../skills/dual-platform-video/references/visual-integrity.md) 与 [声音和媒体 QA](../../../skills/dual-platform-video/references/production-and-qa.md)。

## 预览

[serve-preview.py](scripts/serve-preview.py) 仅监听本机 `127.0.0.1:3158`，支持 MP4 Range 请求。完成对应的两个短预览和/或完整成片后，从 `project/` 启动：

```sh
python3 scripts/serve-preview.py
```

在本机浏览器打开 `http://127.0.0.1:3158/watch.html`；页面为交付目录的 [watch.html](../watch.html)，可切换开场、矩阵短样片和最终视频。需要浏览器 seek 时保持服务运行；用 `Ctrl-C` 结束。

## 环境与版本

已验证的制作基线是本仓库现有 Node 依赖、Python、FFmpeg/FFprobe、Mac 上的 Google Chrome，以及 `agent-dev` 管理的构建临时空间。视觉扫描还依赖工程运行时中已有的 NumPy 与 Pillow。不要在项目初始化时自动下载依赖或调用生成服务。其他操作系统属于选择性适配：需自行提供锁文件对应的 Node 依赖、Python/FFmpeg/FFprobe、兼容 Chromium，并调整脚本中的 Mac Chrome 路径、AgentDev 暂存路径及 Mac 卷门槛；当前未验证此类移植。保持本次单平台成片与既有文件；修订另建版本目录，发布账号操作需要单独明确指令。
