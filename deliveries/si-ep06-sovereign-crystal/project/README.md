# EP06 主权心印 可编辑工程

原生 Remotion 4.0.534 / React19 / TypeScript5.9.3。两版120秒、60fps、7200帧，共用同一master.wav。完整原稿在../source，科学校订见scientific-notes.md。动画由帧、固定种子、RK4与解析势函数驱动。

现有仓库根依赖可直接复用；独立恢复时用package-lock.json运行npm ci。Q的Mac先核验agent-dev status --json，再通过agent-dev run串行渲染。

```sh
npm run typecheck
python3 scripts/build_audio.py --mix
python3 scripts/sync_audio.py --write
node scripts/render.mjs stills landscape
node scripts/render.mjs stills portrait
node scripts/render.mjs video landscape
node scripts/render.mjs video portrait
python3 scripts/collect_qa.py
```

运行时不需要任何密钥：已有本地旁白缓存、母带和程序化画面均可离线重导出。synthesize.py只有明确授权且本地鉴权配置可用时才重录，不是重导出的前提。不得重新生成另一画幅的声音。

字幕按真实PCM活动范围按语句权重分配；无逐字强制对齐证据。技术、模型代表帧、连续人工听看、真机App播放分别记录，不互相代替。
