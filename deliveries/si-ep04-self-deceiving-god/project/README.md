# EP04 — 神也会自我欺骗

Editable Remotion 4.0.534 / React 19.1 / TypeScript 5.9.3 project. Composition IDs: `Landscape4K` (3840×2160) and `PortraitVertical` (2160×3840), both 7200 frames at 60fps. Source script is preserved in `../source/script.md`. Read `brief.md` and `scientific-notes.md` for intent, assumptions and timing interpretation.

Run from this project directory using the repository's installed dependencies (or install from the exact lockfile in a fresh environment). On Q's Mac, use the verified workstation wrapper for rendering/mixing. No dependency upgrade is needed.

```sh
node_modules/.bin/tsc --noEmit
python3 scripts/verify_project.py
/Users/guoq/.local/bin/agent-dev run -- node scripts/render.mjs stills portrait 960 1500 2190 3200 4800 6500 7100
/Users/guoq/.local/bin/agent-dev run -- node scripts/render.mjs review landscape
/Users/guoq/.local/bin/agent-dev run -- node scripts/render.mjs video landscape
/Users/guoq/.local/bin/agent-dev run -- node scripts/render.mjs video portrait
python3 ../../../skills/dual-platform-video/scripts/validate_delivery.py .. --scan-source
/Users/guoq/.local/bin/agent-dev run -- python3 scripts/collect_qa.py
```

Full renders refuse to overwrite existing final output paths. Frame functions support random access; no real-time clock or unseeded randomness is used. Only runtime-local assets are read during rendering. Font dependencies: macOS PingFang SC / Hiragino Sans GB for Chinese and Arial Narrow for compact telemetry. Proprietary system fonts are not redistributed; font substitution on another OS requires a new layout review.

`segments.json` separates original text, displayed subtitles and TTS phonetic input. `audio-timing.json` records measured PCM and phrase estimates; it does not claim word-level forced alignment. `sfx_events.json` owns the frame/sample contract. Both compositions read the same `public/audio/master.wav`; final QA compares encoded AAC payloads and decoded audio windows.

Do not rerun provider synthesis for another aspect ratio. The audio generation script is restricted to these supplied texts and retains cache keys, request settings, effective model/voice and raw/canonical PCM identities. No ASR is part of the workflow. Preserve raw malformed stream WAVs and their repair evidence.

Native encoded frames, mobile previews, pair-frame deltas, media/loudness reports and remaining human/device checks live in `../review/`. Models and code cannot substitute for actual audience feedback or phone playback.
