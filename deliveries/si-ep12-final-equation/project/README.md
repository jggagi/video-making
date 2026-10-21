# EP12 project notes

This is the portrait-only 90-second finale project: 2160 × 3840 at 60 fps, 5,400 frames. The composition uses a 1080 × 1920 logical canvas at 2× native scale and the approved pure 2D Swiss drafting palette. See [brief.md](brief.md) for the creative lock and [timeline.json](timeline.json) for exact frame, safe-zone, sound, and cover anchors.

The original script and segment display/TTS strings are preserved. `telemetry-lexicon.json` retains the full source HUD and technical labels alongside the three compact display rows. The numerical counters and “unknown: 0” overlays are fictional narrative telemetry; supporting references and historical limitations are in [scientific-notes.md](scientific-notes.md).

The silence is `[4860,4890)`, the pen touch is at frame 4890, and the closing disclaimer appears only in `[5160,5400)` at opacity 0.35. Do not speed up or truncate the closing narration to force a fit.

The Xiaohongshu folder contains the final media, captions and publication text package. Cover A (frame 4020) and Cover B (frame 5040) are extracted from the final encoded movie; separate native headline variants are included. The package does not submit content or perform account automation.

## Rebuild and checks

Use the pinned Remotion 4.0.534 / React 19.1.0 toolchain; this checkout reuses its existing parent dependencies. Installed macOS PingFang SC, Songti SC and Menlo fonts are local dependencies with hashes in assets-manifest.json; licensed system font files are not redistributed. No remote assets are fetched during render.

```sh
node ../../../node_modules/typescript/bin/tsc --noEmit
python3 scripts/verify_project.py
agent-dev run -- node scripts/render.mjs preview 3900 4079
agent-dev run -- node scripts/render.mjs video
agent-dev run -- python3 scripts/mux.py
agent-dev run -- python3 scripts/collect_qa.py
```

The renderer refuses to replace formal native staging evidence, and the muxer refuses to overwrite a final movie. Use a fresh version directory for creative revisions. Audio synthesis reuses verified caches and requires the explicit authorization record; a new build does not need new provider calls. Consult public/audio/provider-manifest.json for actual CLI-reported identity and measured PCM durations. The single approved S02 timing exception is in audio-timing-overrides.json. Captions match original display text with editorial line breaks; phrase timing is estimated within measured speech spans, not word-aligned by ASR.
