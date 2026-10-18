# 《百万分身》EP.03 v02

独立版本，可编辑程序画面与共享声音。规范和叙事见 brief.md；原始要求见 ../source/script.md。

沿用仓库根已安装的 Remotion4.0.534 / React19.1.0；独立恢复工程时使用本目录 package-lock.json 安装，系统需具备 Chrome、ffmpeg、中文字体与 Python numpy/Pillow。渲染过程无需联网。

```sh
# 从仓库根执行，Q本机的重型任务通过工作站runner
node_modules/.bin/tsc --noEmit --project deliveries/si-ep03-million-mind-v02/project/tsconfig.json
/Users/guoq/.local/bin/agent-dev run -- node deliveries/si-ep03-million-mind-v02/project/scripts/render.mjs stills landscape
/Users/guoq/.local/bin/agent-dev run -- node deliveries/si-ep03-million-mind-v02/project/scripts/render.mjs video landscape
/Users/guoq/.local/bin/agent-dev run -- node deliveries/si-ep03-million-mind-v02/project/scripts/render.mjs video portrait
```

两版共用 public/audio/master.wav，渲染严禁调用提供商。变更画幅不重做配音。build_audio.py 的 --generate 明确触发百炼调用并可能计费；--mix 仅用本地已核验缓存。源字幕三轨位于 segments.json，实际 PCM 与短句时序位于 audio-timing.json，音效锚点位于 sfx_events.json。真人听音及手机 App 播放状态见 ../review/acceptance.md。

正式输出后，在本project目录运行 `python3 scripts/sync_audio.py --prepare` 和 `python3 scripts/sync_audio.py --apply`，将同一份已测量 AAC 码流无损封装进两版，逐份验证视频数据未改变。字幕导出前先完成 `build_audio.py --mix`，再运行 `export_captions.py` 保留未朗读的 EP.04 片尾标签。

最终两份MP4已经完成并通过完整严格解码，实际声音为−17.2 LUFS / −1.4 dBTP。可编辑ZIP含源码、十段原始和规范化旁白、stem与PCM母带、两版SRT和精简QA；不包含依赖或成片。独立恢复时进入project目录按锁文件安装依赖，再运行上述scripts内的脚本；Chrome、ffmpeg与字体仍需本机具备。换平台不触发新的旁白调用。
