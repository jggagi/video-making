# 《兰道尔极限》 EP.05

Two native Remotion compositions share a 7200-frame / 60 fps state, analytical physics, captions and one exact 48 kHz stereo PCM master. `Landscape4K` is 3840×2160; `PortraitVertical` is 2160×3840. This project uses the repository's existing pinned Remotion 4.0.534 dependencies. PingFang SC and Menlo are locally installed macOS fonts; they are referenced rather than redistributed. No remote resources are fetched during rendering.

Read `brief.md`, `scientific-notes.md`, `segments.json`, `timeline.json`, `layout-contract.json`, and `../review/acceptance.md` before revising. The supplied script is immutable in `../source/script.md`; the scientifically corrected adaptation is separate.

From this project directory:

```sh
npm run typecheck
python3 scripts/verify_project.py
node scripts/render.mjs stills landscape
node scripts/render.mjs stills portrait
python3 scripts/sync_audio.py
python3 scripts/build_audio.py --mix
node scripts/render.mjs video landscape
node scripts/render.mjs video portrait
python3 scripts/collect_qa.py --help
```

On Q's Mac, run heavy jobs serially through `/Users/guoq/.local/bin/agent-dev run -- ...` after a fresh volume preflight. The voice synthesis script requires a separate explicit authorization manifest and does not silently change provider or voice. Do not accelerate or truncate narration to fit a window. Final media checks and human/device approval are separate states.
