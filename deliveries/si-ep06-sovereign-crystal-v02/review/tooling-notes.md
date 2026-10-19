# EP06 v02 render and QA tooling

The scripts in `project/scripts/` support native 4K landscape and portrait output for the 120-second, 60 fps, 7,200-frame edition. They use the existing measured PCM master and `audio-timing.json`; they do not synthesize narration or remix the audio. Render tooling expects the Remotion entry point `project/src/index.ts` to register `Landscape4K` (3840×2160) and `PortraitVertical` (2160×3840).

`timeline.json` defines contiguous authored scene coverage, `segments.json` defines narration windows, and `audio-timing.json` records measured PCM and caption spans. QA checks the authored scene clock separately and verifies that every measured voice span matches its narration window; it does not infer or fabricate timing. The separately recorded user-approved 12-second proof establishes visual style; it does not stand in for review of the completed 120-second editions.

## Rendering

Run heavy commands from the repository root through `/Users/guoq/.local/bin/agent-dev run -- ...` after the current `agent-dev status --json` preflight. The renderer requires `TMPDIR` on `/Volumes/AgentDev/`, bundles into that temporary directory, uses Chromium GL angle and concurrency 1, and refuses to replace an existing full MP4. Repeated preview stills and clips receive revision suffixes.

```text
node deliveries/si-ep06-sovereign-crystal-v02/project/scripts/render.mjs --help
node deliveries/si-ep06-sovereign-crystal-v02/project/scripts/render.mjs stills [landscape|portrait] [frames...]
node deliveries/si-ep06-sovereign-crystal-v02/project/scripts/render.mjs preview <layout> <start> <end>
node deliveries/si-ep06-sovereign-crystal-v02/project/scripts/render.mjs review <layout>
node deliveries/si-ep06-sovereign-crystal-v02/project/scripts/render.mjs video <layout>
```

Stills default to frames 360, 960, 1500, 2190, 3120, 3900, 4800, 5759, 5760, 5790, 6500, 7100 and 7199. Review clips are 180 frames each at frames 660–839, 3000–3179, 4740–4919, 5700–5879 and 6960–7139. Preview clips are one-third size. Full MP4s use H.264, BT.709, yuv420p, CRF 17, fast preset, AAC stereo at 48 kHz/320 kbps and JPEG frame intermediates at quality 94. Remotion 4.0.534 applies MP4 fast-start muxing automatically for `.mp4` outputs.

The dependencies were cloned copy-on-write from the already-installed v02 proof project with `cp -cR`; no install or network request was made. The renderer resolves the installed Chrome app at `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` when no bundled Remotion headless shell exists.

## Technical checks

- `verify_project.py` checks the 120-second manifest, 7,200-frame clock, 10 authored/measured narration windows, cue hashes, timed caption bounds, absolute silence metadata, SFX clock and exact PCM-master format/hash. It does not check exported video or certify visual approval.
- `verify_shared_audio.py` compares AAC decoded at zero offset against the unchanged PCM master and records cue-window correlation/level metrics; AAC similarity is a technical measure, not a listening judgment.
- `collect_qa.py` probes final files and can extract native encoded frames plus 360-pixel review sheets. These samples support review but do not replace continuous human viewing, listening or target-device playback.
- `finalize_metadata.py` binds hashes and measured technical reports into fresh review evidence. It leaves `delivery.json` and human-acceptance fields untouched.
- `package_project.py` creates a deterministic editable-project ZIP, excludes dependencies and rendered exports, and refuses to replace an existing package with different contents.

Syntax checks, help output and source validation are separate from media render/decode checks. The approved proof covers style only; continuous review of each 120-second edition, listening and device/platform playback remain separate acceptance steps.

Root additionally exercised `capture_motion.py` against a real 3-second portrait choice preview: frame0/frame150 extraction, a two-cell contact sheet, and the actual ffmpeg ROI/edgedetect/difference pipeline succeeded (YAVG1.8312). Temporary smoke-test files were removed. Final-film source hashes, pair maps and evidence are recorded by the later full capture run; this small filter test is not final-media acceptance.

`collect_qa.py` uses `-xerror -err_detect explode` for strict full-file decode, so a decoder-reported error cannot silently count as a passing exit.
