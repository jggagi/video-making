# EP16《零摩擦人间》
原生2160×3840 / 60fps / 120秒 / 7200帧，仅小红书。程序SVG临床冷白与银灰等高线，系列百炼longtian_v3旁白与原创声景。

沿用根工程锁定Remotion4.0.534，不另安装依赖。在project目录执行：
- `node ../../../node_modules/typescript/bin/tsc --noEmit`
- `python3 scripts/synthesize.py S01 --authorized`（当前EP16直接授权后才可调用；其余all顺序生成，缓存复用）
- `agent-dev run -- <bundled-python> scripts/build_audio.py`
- `agent-dev run -- node scripts/render.mjs stills`
- `agent-dev run -- node scripts/render.mjs preview 6300 6479`
- `agent-dev run -- node scripts/render.mjs video`
- `agent-dev run -- python3 scripts/mux.py`
- `agent-dev run -- <bundled-python> scripts/collect_qa.py`

需先通过当前外置卷身份与容量检查。预览与全片先后串行运行。母带完整语音不得裁切或倍速。素材来源见assets-manifest.json，科学边界见scientific-notes.md，实际验收见../review/acceptance.md。代表帧不等于人工连续听看或手机播放。
