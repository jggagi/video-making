# 啃食尾巴的神 · 可编辑工程

原生竖屏4K、60fps、90秒。使用仓库锁定的Remotion4.0.534和现有父级依赖；不需要升级或安装新依赖。纯二维Canvas刻线与SVG排版；字体使用本机Songti SC / PingFang SC / Menlo，渲染等待document.fonts.ready。字体文件不作为可再分发资产上传，其他机器须提供对应或经过版面复核的替代字体。

在Q的Mac上先核验agent-dev卷身份，再通过agent-dev run执行typecheck、stills、preview、video、mux与QA。src/Root.tsx的PortraitVertical锁定2160×3840/60fps/5400帧。scripts/render.mjs视频导出是外置临时视频轨，scripts/mux.py复用本地精确PCM母带生成正式MP4。

声音脚本为scripts/audio_pipeline.py，原稿与改编、配音缓存、时间轴、音效帧和QA各自保留。正式媒体必须经过技能validate_delivery.py及完整逐帧视觉筛查，源码检查不能代替成片验收。


复核与重建顺序（仓库根目录，保留已有正式文件；渲染脚本拒绝覆盖）：

1. 核验工作站外置卷身份与容量；使用现有父级依赖，无需安装。
2. 运行 `node node_modules/typescript/bin/tsc --noEmit --project deliveries/si-ep17-godel-ouroboros/project/tsconfig.json`。
3. 通过 `agent-dev run -- node deliveries/si-ep17-godel-ouroboros/project/scripts/verify_frames.mjs` 执行全部5400帧绘图冒烟检查；它验证运行和有限坐标，不验证像素质量。
4. 通过同一包装器运行 `render.mjs preview <首帧> <末帧>` 检查原生样片，再运行 `render.mjs video`。视频轨与bundle位于AgentDev临时目录，完整视频捕获使用并发1。
5. 通过包装器运行 `python3 deliveries/si-ep17-godel-ouroboros/project/scripts/mux.py`，只复用现有精确PCM母带。
6. 用现有NumPy/Pillow环境运行 `collect_qa.py`、`verify_encoded_audio.py`，再执行技能的全片 `scan_visual_qc.py` 和 `validate_delivery.py --scan-source`。报告绑定实际成片SHA。
7. 按仓库归档流程生成目录、本地final、作品与final两份Release；`restore_probe.py`仅恢复本次新增EP17一份成片，并验证重复恢复跳过。

原稿超出指定窗口的实测、90秒改编授权和新分段见 `audio-authorization.json`、`adapted-script.md` 与 `../review/audio-original-samples.json`。字幕为实测PCM段内的手工短句估时，没有额外ASR；人类听音及真机播放以 `../review/acceptance.md` 的真实状态为准。

首次全片尝试在提前淡入的不可能三角上暴露了负余数索引；已对两个跨幕周期归一化，并增加全5400帧真实绘图执行检查。失败检查和废弃样片另存，正式媒体通过后才列入final。
