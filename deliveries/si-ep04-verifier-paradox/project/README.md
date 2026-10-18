# EP.04 可编辑工程

共享 120 秒 / 60 fps 状态与音轨，两个独立原生 4K Composition。依赖版本由 package-lock.json 固定，当前制作沿用仓库已安装的 Remotion 4.0.534 / React 19.1.0。

```sh
npm run typecheck
python3 scripts/verify_project.py
node scripts/render.mjs stills landscape
node scripts/render.mjs stills portrait
python3 scripts/build_audio.py --audit
python3 scripts/build_audio.py --mix
python3 scripts/export_captions.py
node scripts/render.mjs preview portrait 5700 5849
node scripts/render.mjs video landscape
node scripts/render.mjs video portrait
python3 scripts/collect_qa.py
```

在 Q 的本地 Mac 上，渲染命令通过 `/Users/guoq/.local/bin/agent-dev run --` 执行，先检查卷身份与容量，完整双版串行渲染。初始静帧允许无声，正式成片要求十段实测 PCM 和完整共享 master.wav。未生成的声音不能用预览字幕时长冒充已对齐。

`segments.json` 保存原文、显示文本和 TTS 文本；`sfx_events.json` 保存事件帧/样本锚点；`audio-timing.json` 在混音完成后由真实 PCM 更新。`CanvasWorld.tsx` 负责空间几何，`Film.tsx` 负责独立双画幅排版和精确 HUD。
