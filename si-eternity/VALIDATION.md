# Validation — The Half-Second Eternity

Completed on 2026-10-15, America/Los_Angeles. All work is isolated in `si-eternity/`; the existing films were preserved.

## Source and geometry

- `npm run typecheck`: passed against the complete project.
- `npm run check`: passed. Twelve TypeScript source files contain no prohibited wall-clock/random/timer/network calls, external asset URLs, or incomplete placeholders.
- Timeline: 1800 + 2700 + 2700 + 3600 = 10800 frames at 60 fps, exactly 180 seconds. Continuous bilingual subtitle cues run to frame 10500, followed by the final title.
- Reference HUD: starts at 0 ms / 120 mm / cognitive step 1; reaches 500 ms / 0 mm / step 10,000,000,000 / ten centuries at frame 10200 and holds. The height uses the documented normalized gravity trajectory.
- Search model: 600 nodes, 576 pruned, 24 survivors. Every prune starts exactly 45 integer frames after that node's spawn, flashes red for 45 frames, and fades to 0.06 opacity. The golden path is one connected root-to-leaf chain. Surviving branches retain their ancestors.
- Manifold: 64 distinct vertices and 160 adjacent edges. All vertices were checked at every one of the 2700 local frames: finite projection and no viewport overflow. Observed projection extents were approximately x=817–1735 and y=409–834. Rotation preserves the 4D norm and locks at frame 2580.
- Collapse: local frames 2200–2580 converge, then 2580–2699 hold the point inside the requested 2200–2700 collapse phase. The exact terminal command is visible before the act ends.
- Crystal: 12 vertices, 30 edges, 20 triangular faces; five edges per vertex, two faces per edge, Euler characteristic 2; rotations preserve the unit radius.
- Asymmetry: 500 digital nodes; gear angle exactly 0.002° per local frame, with ±0.8 px bounded deterministic jitter.
- Impact: absent at local frame 2399, present at 2400, matching global frame 9600. The user explicitly approved preserving this event separately from the frame-10200 reference clock endpoint.
- All ten direct dependency pins match the standalone lockfile. No new dependency installation or upgrades were needed on this machine.

## Actual render and media

The complete film was rendered with the installed Chrome through the workstation's `agent-dev` wrapper, with two rendering workers. External volume identity and capacity were checked before rendering. Internal free space was warning-only under the user's workstation policy.

`out/the-half-second-eternity.mp4`:

| Measured property | Result |
| --- | --- |
| Dimensions | 1920 × 1080 |
| Video codec | H.264, 4:2:0 full range (`yuvj420p`) |
| Frame rate | 60/1, both average and nominal |
| Frame count | 10800 |
| Stream and container duration | 180.000000 seconds |
| File size | 76,671,341 bytes |
| Audio | No audio stream; intentionally silent |
| Fast start | Passed: `moov` at byte 32, before `mdat` at byte 129935 |
| Complete decode | Passed: FFmpeg with `-xerror -err_detect explode` exited 0 |

Metadata and container checks are retained in `out/media-info.json` and `out/container-check.json`. `out/render-source-sha256.json` records the source/configuration snapshot used for the render. `out/artifact-sha256.json` records the delivered media and source ZIP hashes.

## Visual review

Nineteen representative Chromium stills were rendered. The root agent inspected the laboratory, fiber circuit, pruning, golden path, manifold, split-screen mechanism, crystalline end state, and final typography. Review found and corrected viewport clipping, a ruler/label overlap, font fallback order, zoom intrusion into the HUD, and overlapping title crossfades.

After export, FFmpeg decoded the entire MP4 and extracted sixteen samples at frames 180, 870, 1240, 1740, 3240, 4350, 4920, 6120, 7170, 7860, 9599, 9600, 9810, 10440, 10720, and 10799. The exported zoom transition, exact pre-impact/impact boundary, and last frame were inspected directly. The final title is fully visible on frame 10799. `out/final-contact-sheet.jpg` shows all sixteen encoded-film samples.

`out/one-shot-preview.mp4` is an eight-second derivative of the final film, covering 156–164 seconds, encoded as H.264/yuv420p with fast start for convenient preview. The reproducible `npm run sample` command renders the same frame interval directly from the composition.

## Boundaries

The evidence establishes source checks, mathematical invariants, real Chromium rendering, measured final media, complete decoding, and sampled visual review. A continuous human screening, playback on the user's final display, a fresh independent `npm ci`, and other operating systems were not tested. The speculative SI counters, code fragments and physical transformation remain the concept illustrations documented in README.md.

The local Code Buddy status helper was attempted; its relay and attached-device connection were unavailable. This did not affect source or rendering.
