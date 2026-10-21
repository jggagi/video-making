# EP12 production brief — 《最后一行公式》

## Locked delivery

- Xiaohongshu portrait only: native 2160 × 3840, 60 fps, exactly 5,400 frames / 90 seconds.
- Audio master target: stereo PCM, 48 kHz, 4,320,000 samples per channel, −16 LUFS, true peak at or below −1 dBTP.
- The supplied `source/script.md` and `segments.json` are the source of truth for display subtitles and TTS phonetic text. Preserve every supplied string; do not rewrite or shorten narration.
- Pure 2D Swiss precision drafting. No 3D or pseudo-3D, perspective transforms, 3D wireframes, or fake spheres. Motion is deterministic and frame-driven; no `Math.random()` or `Date.now()`, and no static hold exceeds 180 frames.

## Audience, image, and feeling

Make the finale legible to a general audience. The memory image is a page of intricate diagrams collapsing into one lonely dot. The emotional arc moves from the joy of knowing toward nostalgia for the wonder of not yet knowing. Let the geometry perform that change; avoid adding explanatory labels that compete with it.

## Art and layout contract

- Canvas: warm bone `#F4F1EA`, with deterministic `#E5E0D5` 1 px hairlines or micro-grid.
- Ink: carbon `#18181B`; technical slate `#52525B`; conflict/redaction `#E11D48`; convergence gold `#D97706` and `#B45309`.
- Logical composition: 1080 × 1920, scaled 2× to the native canvas. Keep the compact HUD at `x=64`, width `856` logical pixels (ends at `x=920`), within the 14% right safe zone. The supplied 30 px logical type scales to 10 px at 360 px preview width. Keep the HUD left aligned in the 9%–14% top band; fit-check the rendered text at 360 px.
- Three compact monospace HUD rows only. Keep every row at or below 43 ASCII characters. The full source wording and exact abbreviated display strings are recorded in `telemetry-lexicon.json`.
- Keep subtitles in the 24%–28% bottom band, at most two lines, with at least 39 logical px type (13 px at 360 px preview width). Maintain strong carbon-on-bone contrast and safe-zone clearance.
- The final disclaimer appears only in frames 5160–5399, at opacity 0.35: `科幻思想实验｜数值与终极统一为叙事设定`.

## Acts and visual movement

All intervals are half-open `[startFrame, endFrame)`. The exact shot and sound boundaries are in `timeline.json`.

1. **Patchwork, `[0,1320)`** — an intricate 2D epicycle drawing and conflicting technical diagrams on the drafting page. Vermilion marks expose the patchwork; do not present its fictional telemetry as measurements.
2. **Compression, `[1320,2820)`** — a flat vermilion caliper sweep removes redundant circles in a readable sequence. Geometry settles toward one gold circle; the action expresses the story's thought experiment, not a discovered physical law.
3. **Convergence, `[2820,4380)`** — four flat 2D panels for gravity contours, quantum probability, thermodynamic flow, and life/mind patterns translate and scale inward. Their visual alignment is symbolic; it does not assert a validated common theory.
4. **The dot, `[4380,5400)`** — the astrolabe contracts between frames 4380 and 4859. At frame 4860, axes and diagrams resolve to one centered 12 px logical carbon dot with a gold hairline circle on open bone paper. Preserve the quiet and the closing quotation; place the disclaimer only in the final four seconds.

## Sound and text

Use the original segment text exactly. Keep the full master at 90 seconds; do not speed up or truncate speech. The absolute-silence interval is `[4860,4890)`. The fountain-pen touch is anchored at frame 4890, followed by the warm solo piano. No audio stem may leak into the silence interval. See `timeline.json` for all supplied SFX anchors and the exact closing timing.

## Scientific and publication boundary

This is a science-fiction thought experiment. The HUD numbers, compression countdown, `Q.E.D.`, and “unknown remaining: 0” are fictional telemetry and narrative claims, not empirical results. The Euler–Lagrange stationary-action identity is genuine mathematics, but it is not a discovered final unified law. The Newton/epicycle comparison remains in the original script as a historical simplification and is qualified in `scientific-notes.md`; do not silently rewrite the user's script or caption.

`小红书/publish-package.json` and `.md` are text-only draft materials. Cover A and B are specified at frames 4020 and 5040 and remain pending until rendered. Preparing this package does not submit or automate a platform account action.

## Measured narration exception

Q approved using the existing gap after S02: full audio ends at sample 1,022,911 (21.310646s), active speech ends at 21.063458s, and the subtitle ends at frame 1264. The original source window remains unchanged in segments.json. All visual/SFX key frames and the exact 90-second total remain fixed. Complete cues keep their source PCM, natural rate 1.0, and a 22,845-sample gap before S03. Details: audio-timing-overrides.json.
