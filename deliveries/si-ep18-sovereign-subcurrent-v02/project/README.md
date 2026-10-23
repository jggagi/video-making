# 心印潜流 · v02 可编辑工程

本版是视觉修订：以更锐利的角形冰山重构画面，复用 v01 已核验的完全相同音频母带，不重新合成或处理音频。母带 SHA-256：`64c6b71729ed1a1bd948149d1051c2682a7237bd57aff59c9c752d0122b6f02d`。成片规格为小红书原生竖屏 2160×3840、60 fps、90 秒，共 5400 帧。依赖锁定在 Remotion 4.0.534，并复用仓库现有的父级 Node 依赖；不要升级或安装依赖。渲染脚本使用本机 Google Chrome 可执行文件 `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`。Canvas 场景以 1080×1920 逻辑画布绘制，再由 Remotion 按原生分辨率捕获。字体来自渲染机器的系统字体，不随项目分发；换机器后须检查文字布局。

在 Q 的 Mac 上，先按仓库指引核验 AgentDev 与 WD_BLACK 身份和容量，再通过 `/Users/guoq/.local/bin/agent-dev run -- ...` 运行构建、全帧绘图检查、渲染、mux 和媒体 QA。渲染脚本会拒绝覆盖已有的静帧、预览和暂存记录。完整视频捕获使用单并发、PNG 中间帧、H.264、yuv420p 和 bt709；Remotion bundle 与无声视频轨写入 AgentDev 临时目录，正式 MP4 只写入 `delivery.json` 指定的位置。

从仓库根目录按需执行以下步骤：

1. 确认 `delivery.json` 的身份为 `si-ep18-sovereign-subcurrent-v02` / `心印潜流 · v02`，平台仅为小红书，输出路径为 `小红书/si-ep18-sovereign-subcurrent-v02-xiaohongshu-90s-portrait.mp4`。确认 `public/audio/master.wav` 的 SHA-256 与上方记录一致；不一致时停止，先查明音频来源，不要覆盖或重建母带。
2. 运行 `node node_modules/typescript/bin/tsc --noEmit --project deliveries/si-ep18-sovereign-subcurrent-v02/project/tsconfig.json`。
3. 运行 `node deliveries/si-ep18-sovereign-subcurrent-v02/project/scripts/verify_frames.mjs`。它从 `project/src/Scene.tsx` 导入 `drawScene(ctx, frame)`，在逻辑尺寸 1080×1920 上实际执行全部 5400 帧，检查抛错和非有限画布数值；这不判断画面的美感或科学表达。
4. 保留已核验的八段旁白和 PCM 母带，不运行音频合成流程。确认字幕仍与既有 cue 和音频时间相符；在母带 SHA-256 匹配后，可运行 `python3 deliveries/si-ep18-sovereign-subcurrent-v02/project/scripts/make_assets_manifest.py` 生成并绑定当前 v02 源码、素材和可用合成证据。
5. 运行 `node deliveries/si-ep18-sovereign-subcurrent-v02/project/scripts/render.mjs stills` 生成每个 cue 的代表帧，运行 `node deliveries/si-ep18-sovereign-subcurrent-v02/project/scripts/render.mjs covers` 生成 cover A（3960 帧）和 cover B（2160 帧）。如需预览或无声视频轨，分别执行 `node deliveries/si-ep18-sovereign-subcurrent-v02/project/scripts/render.mjs preview 120 299` 和 `node deliveries/si-ep18-sovereign-subcurrent-v02/project/scripts/render.mjs video`。
6. 只有已有音频合成身份记录与母带 SHA-256 核验结果仍绑定到同一母带后，视频轨才可继续 mux。执行 `python3 deliveries/si-ep18-sovereign-subcurrent-v02/project/scripts/mux.py` 会复核 AgentDev 暂存、48 kHz 立体声 PCM16 母带及最终 H.264/AAC 文件规格。
7. 用带 NumPy、Pillow 的现有 Python 环境运行 `python3 deliveries/si-ep18-sovereign-subcurrent-v02/project/scripts/collect_qa.py`，再运行 `python3 deliveries/si-ep18-sovereign-subcurrent-v02/project/scripts/verify_encoded_audio.py` 与 `python3 deliveries/si-ep18-sovereign-subcurrent-v02/project/scripts/verify_project.py`。QA 会重新解码成片并将结果绑定到实际 MP4 SHA-256；包含每个 cue 的手机尺寸联系表、每段场景的运动差异测量、封面帧和来自原生帧的高分辨率检查裁图。运动差异与自动元数据只作测量，不代表视觉通过。
8. 在开始视觉扫描前，先为 v02 选择与新画面相符的检查：连续检查全画面，并跟踪贯穿本版镜头的常暗 ROI。旧 `collect_ending_roi_evidence.py` 是基于 v01 稳定 HUD 的历史辅助脚本；稳定 HUD 在结尾消失，因此该脚本不代表 v02 的结尾检查。全画面扫描、ROI 证据与人工审阅分别记录。
9. 上传与恢复探针属于仓库归档流程。只有归档完成并在 `delivery.json` 绑定最终影片 SHA 后，才运行 `python3 deliveries/si-ep18-sovereign-subcurrent-v02/project/scripts/restore_probe.py` 检查 v02 最终影片的恢复与重复跳过行为。

原始剧本保留在 `../source/script.md`，经审校授权的 90 秒制作稿在 `adapted-script.md`。本版复用 v01 音频；字幕、声音和视觉隐喻的审核应依据 v02 当前素材。旧集报告、旧时间轴和旧视觉结论不作为本版证据。

技术检查、代表帧审阅、连续观看和目标设备播放分别记录。源码、绘图冒烟、ffprobe、音频相关性或自动视觉筛查都不能替代人类通片观看与手机播放；未实际完成的验收状态继续标为 pending。
