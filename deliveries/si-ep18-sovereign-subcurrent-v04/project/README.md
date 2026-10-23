# 心印潜流 · 人与影 · v04

源自用户对v03的反馈，独立修订并保留旧版。90秒，原生竖屏4K/60fps，常速八段旁白。

先读brief.md、adapted-script.md、segments.json。使用已有锁定依赖，不安装新包。Mac重作业先检查agent-dev卷状态，然后通过agent-dev run运行。

1. python3 scripts/audio_pipeline.py synthesize --ids S01 （短样本，核对后补其余）
2. python3 scripts/audio_pipeline.py mix
3. python3 scripts/make_captions.py
4. npm run typecheck；node scripts/verify_frames.mjs
5. node scripts/render.mjs stills；原生有声短样片；再完整render与mux
6. 最终逐帧筛查、媒体验证、编码抽帧、声画同步与归档/恢复抽测。

先前版本的通过状态不适用于本版。连续人工听看和手机/App试播分别记录。
