# 一眼万年 · One Blink, Ten Millennia

An editable, fully procedural Remotion visual essay: **180 seconds · 60 fps · 10,800 frames · 1920 × 1080**. The current horizontal silent composition ID is `OneBlinkTenMillennia`; the voiced v3 composition is `OneBlinkTenMillenniaVoicedV3`.

The current v3 edition uses the title **一眼万年 (ONE BLINK, TEN MILLENNIA)**, a revised opening and ending title sequence, and an updated v3 narration plan. The earlier silent and voiced-v2 exports and project ZIPs remain in `out/`. The current source composition IDs replace the older `HalfSecondEternity` and `HalfSecondEternityVoicedV2` IDs; those IDs are not registered as aliases. See [TITLE-V3.md](TITLE-V3.md) for the title, timing, audio lineage, and validation details.

`BRIEF.md`, `AUDIO-V2.md`, and `VALIDATION.md` are preserved as records of the original brief and earlier editions. Current v3 technical checks and representative encoded-frame inspection are recorded in `out/title-v3-validation.json`. Continuous human listening remains open.

## Native portrait edition v4

The additional portrait composition, `OneBlinkTenMillenniaPortraitV4`, is an independently laid-out **1080 × 1920** version on the same 180-second / 60 fps timeline. The existing horizontal composition IDs, renders, and v3 instructions remain unchanged. Portrait v4 reuses the same v3 soundtrack and does not add narration or a new mix. See [PORTRAIT-V4.md](PORTRAIT-V4.md) for layout, timing, validation, and packaging details.

```sh
npm run portrait:stills
npm run portrait:preview
npm run portrait:render
```

The preview writes `out/portrait-layout-preview-v4.mp4`; the full portrait render writes `out/one-blink-ten-millennia-portrait-v4.mp4`. Portrait v4 technical media QA and representative encoded-frame inspection passed; results are in `out/portrait-v4-validation.json`. The source/audio archive is `out/one-blink-ten-millennia-portrait-v4-project.zip`, with its archive ledger at `out/package-portrait-v4-manifest.json`. Continuous human listening and playback in the phone app remain open.

## Run

```sh
cd si-eternity
npm ci
npm run start
```

The project pins Remotion **4.0.534**, React **19.1.0**, and TypeScript **5.9.3**. This checkout can also use the already installed parent `node_modules`; no dependency changes to the existing films are required. An independent copy uses `npm ci` and its own lockfile.

```sh
npm run typecheck
npm run check
npm run stills
npm run sample
npm run render
```

Studio opens on port **3106**. `render` and `render:voiced` export the current voiced film to `out/one-blink-ten-millennia-v3.mp4`; `render:silent` exports `out/one-blink-ten-millennia-silent-v3.mp4`. `titles` renders title-check stills. `preview:opening` and `preview:ending` render voiced title previews to `out/opening-title-v3.mp4` and `out/ending-title-v3.mp4`. `node scripts/render.mjs frame 9600` exports one frame. Paths resolve relative to the project, even when a script is invoked elsewhere.

The renderer uses installed Google Chrome on macOS, or Remotion's Headless Shell when that path is unavailable. Override with `REMOTION_BROWSER_EXECUTABLE=/absolute/path/to/chrome`. `REMOTION_CONCURRENCY` defaults to 2 and accepts 1–4. On Q's Mac, run dependency and heavy render jobs through `/Users/guoq/.local/bin/agent-dev run -- ...` after a fresh volume check, according to the workstation instructions.

## Horizontal v3 film structure

| Component | Global frames (end exclusive) | Duration | Visual event |
| --- | --- | --- | --- |
| `Act1Speed.tsx` | 0–1800 | 30 s | Pipette, amber drop, frozen blink, 25× zoom into fiber circuits; opening title at local frames 60–360 |
| `Act2BreadthMCTS.tsx` | 1800–4500 | 45 s | 600-node golden-angle search, 96% pruning, one connected gold path |
| `Act3DepthManifold.tsx` | 4500–7200 | 45 s | Formal code waterfall, memory threshold, rotating 64-vertex 4D lattice, collapse |
| `Act4SplitWorld.tsx` | 7200–10800 | 60 s | 500 lab nodes versus mechanical inertia, one-shot pulse, levitating crystal, final title |

`MainComposition.tsx` mounts the four acts with `Series` and overlays the persistent `GlobalHUD`. The HUD and subtitle timeline use global frames; each act receives its local frame. The final title sequence fills the final 300 frames, global 10500–10799.

`src/lib/timeline.ts` owns bilingual subtitle cues and the reference clock. `src/lib/math.ts` contains deterministic easing, seeded samples, and 4D rotation. `src/components/Visuals.tsx` supplies shared procedural elements. `BRIEF.md` preserves the original requested specification.

## Clock and interpretation

The original timing relationship remains intact: the droplet impact is **global frame 9600 / local Act 4 frame 2400 / film time 160 s**. The physical reference clock reaches **500.0000 ms at global frame 10200 / film time 170 s**. The subjective-years counter is linear, `10000 × clamp(globalFrame / 10200)`, and reaches **10,000.0 years** at frame 10200. The displayed altitude is labelled **NORMALIZED REFERENCE TRAJECTORY**; the impact and the reference clock endpoint are separate editorial events.

The final 300 frames transition to the deep void `#050811`, show the Chinese closing line and title, and keep the title visible through frame 10799. The updated opening and ending typography, eyelid transition, and subtitle/audio details are documented in [TITLE-V3.md](TITLE-V3.md).

The film is a speculative illustration, not a measured SI benchmark or physical simulation. Search probabilities, verifier confidence, formal-code fragments, cognitive-depth counters, and the superconductor transformation are narrative graphics. The 64-vertex figure is a 4D lattice projected to 3D and then 2D, rather than a literal 16-vertex tesseract or a computed Calabi–Yau surface. The 12-vertex crystal is an icosahedron.

## Audio editions

The silent composition remains available. The voiced v3 composition uses the v3 voice plan and the updated opening and ending cues. The default voice plan and `voice:generate` target `audio-v3`; generating uncached narration requires the configured Bailian CLI. Playback and Remotion rendering use local files and do not call the provider.

The v3 master mix is `public/audio-v3/soundtrack.wav`. Its narration plan and manifest are in `audio-v3/`; it reuses twenty verified v2 voice clips by hash, while the changed ten-millennia and final title cues use v3 clips. The original score and sound-design stems remain in `public/audio-v2/` and are reused unchanged. To rebuild the v3 master against those v2 stems:

```sh
node scripts/audio.mjs mix --edition audio-v3 --stems-edition audio-v2
```

The v2 audio details and measurements remain documented in [AUDIO-V2.md](AUDIO-V2.md) as historical edition notes; they are not v3 validation results.

## Determinism and verification

Scene geometry, branches, particles, code lines, jitter, projections, and transitions are deterministic functions of the frame or a fixed seed. The compositions use SVG/CSS and local audio assets; there are no external image/video URLs, network fetches, runtime timers, or unseeded random calls in the scene code. The Chinese title uses platform Chinese sans-serif fallbacks; available glyphs may vary by operating system.

`npm run check` checks source constraints and exported scene models and timeline. `npm run typecheck` checks all TypeScript. The v3 full render, strict full audio/video decode, source snapshot, prior-export hashes, and audio synchronization checks passed. Encoded frames at 120, 10200, 10650 and 10799 were inspected. The report is `out/title-v3-validation.json`; continuous human listening and final-device playback remain open. Earlier [VALIDATION.md](VALIDATION.md) is retained as v1 history.

The editable archive is `out/one-blink-ten-millennia-v3-project.zip`. It contains the current source, cached narration, independent music/SFX stems, v3 master, manifests, and validation records. `scripts/package-v3.py` verifies ZIP CRCs and every included file hash before publishing; `out/package-v3-manifest.json` records the archive hash. Historical MP4 exports are retained in the workspace and excluded from the source archive.
