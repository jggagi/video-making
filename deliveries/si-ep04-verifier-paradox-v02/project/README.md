# EP04 v2 · 机制图解版

保留原剧本、旁白和声音时间轴，重做所有主要图示。旧版位于相邻si-ep04-verifier-paradox，不覆盖。理论依据与数值定义见theory-and-visual-model.md，视觉合同见visual-contract.md。

依赖锁定Remotion4.0.534/React19.1.0/TypeScript5.9.3。现有仓库工具链可直接使用，无需重新安装。macOS渲染用系统Chrome及本地中文字体；独立重建需合法安装中文字体并核对布局。

从本目录运行 `npm run typecheck`，`node scripts/render.mjs stills portrait 960 3040 3900 5790 7100`。正式渲染遵循工作站README和agent-dev卷检查，用 `agent-dev run -- node scripts/render.mjs video landscape` 后串行渲染portrait。`python3 scripts/sync_audio.py --prepare`、`--apply`保证两片共用同一AAC包；原PCM母带已复用，勿为画幅再生成配音。

`python3 scripts/verify_project.py`检查工程，仓库技能validate_delivery.py全片严格解码，collect_qa.py从实际最终MP4抽帧/测量。人工完整听看与真实手机App遮挡另记，不由自动检查代替。Zip包括可编辑源、模型数据、共享音频、字幕及紧凑QA，不包含依赖或最终MP4。
