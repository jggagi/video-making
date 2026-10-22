# EP14 acceptance record

Work:《死后第七年，他还在回微信》/ THE GHOST IN THE POSTERIOR.
Target: portrait2160×3840,60fps,5400frames,90.00seconds.

## Source and approved changes

- Original truncated attachment is unchanged in source/script.md. The user-supplied completion is separately transcribed and hashed in source/user-completion.md.
- The user approved readable three-line HUD abbreviations with full original telemetry preserved, and S03's scientific correction. See project/scientific-notes.md.
- Actual natural-rate PCM measurements required adjusted narration starts: S01f75,S02f669,S07f4320. The user explicitly approved them. S03–S06 retain authored active onsets. S08 complete source remains cached; only2880measured digital-zero tail samples are omitted during placement.
- The fixed scene boundaries, SFX event anchors and [4860,4890) silence remain authored frame boundaries. Source windows and measured placements are separate data.

## Engineering and audio evidence

- Pinned Remotion4.0.534/React19.1.0; existing root toolchain reused. TypeScript and source-only spelling checks pass. Composition registration is native2160×3840/60fps/5400frames.
- Visuals use flat SVG, actual deterministic2D Gray–Scott simulation, a local mel-spectrum cache, Fourier membrane boundaries and2D bokeh. Texture snapshots are256×192 source concentration data; vector typography/membranes/filaments are rasterized natively. This is not real microscopy or a brain model.
- No3D transforms, Math.random or Date.now calls in scene sources. Font readiness and all66 texture-image decodes are awaited. Capture configuration/source hashes are in capture-provenance.json.
- Bailian eight-cue generation explicitly returned cosyvoice-v3-flash/longtian_v3 at rate1.0. Raw streaming WAV headers overflowed declared length; untouched originals and separately reconstructed canonical files preserve actual PCM hashes.
- The local master is48kHz stereo PCM16,4320000samples/channel, measured−16.0LUFS/−1.9dBTP. Explicit4x oversampled latency-compensated limiter applied. All stems and master are exactzero over samples[3888000,3912000).
- First message-chime note anchors at sample48000/frame60, second at59520. S01 active voice starts60000/frame75. Pop-cut attacks at4859 and ends at4860, followed by30frames digitalzero, then synthesized bowed-cello harmonic at4890.
- 33 phrase captions preserve joined display text; timings are estimated character-weighted within measured active PCM, with reviewed semantic line breaks. No ASR or word-level alignment claim.

## Representative preflight

Native3-second clips with actual narration/master cover opening, cellular engulfment, and the81-second quench. Encoded mobile frames and a180-frame dense-segment scan were checked; the dense scan had no flags. A first source candidate was refined after seeing overly radial vines, overly symmetric RD seeds and poor subtitle line breaks. Initial evidence is retained under preflight-initial/.

Model visual observation: readable360px HUD and subtitle size, no observed edge clipping or3D distortion; warm jagged cells persist as green filaments advance; quench visibly removes the organism, leaving a small coral spore. Current closing quote was checked as a native still. This is representative observation, not a continuous human viewing or listening result.

## Final encoded-media gates

Full native capture and exact-frame repair: COMPLETE. Initial mux SHA `fcc7f70f0c52…` had a repeated red-HUD tile artifact at frame405. It remains in candidate-01-rejected/. Frame406 was a neighbor flag and visually normal. The unchanged deterministic scene was rendered again at absolute405; only405 was overlaid, then the video was re-encoded atCRF15. A five-frame lossless fixture confirmed the index rule. AAC packet hashes are identical before/after. See capture-repair.json.

Final media SHA-256: `d56c8394eb08f30b1645981fc7fc951f714b3651e1fec813fc3ad2bbcc005ee9`.

- Strict full-file media validation: PASS; H.264/bt709/yuv420p,2160×3840,60fps,5400decoded frames; video/audio/container each90.000000s, fast-start. Final source check9/9PASS.
- Continuous final screening: PASS, all5400frames fromzero, noflags; visual-qc-xiaohongshu-final/report.json is bound to the current hash. This is scaled heuristic screening, not full-resolution perceptual proof.
- Final encoded representative/model observation: PASS within stated scope. All22sample frames,8pairs, native membrane/engulfment/spore crops and final404–406neighbors were viewed. At360px width, key HUD/core labels/subtitles remain readable and unclipped; no3D distortion, repeated tile or severe dark-gradient banding was observed. Motion-ROI differences exclude HUD/subtitle/counter. See representative-review.json and encoded-qa-d56c8394eb08/.
- Encoded audio:−16.0LUFS/−1.8dBTP; three PCM comparison windows have zero lag and correlations0.999846–0.999960. The lossless master has exact4320000samples/channel and exactzero blackout. AAC decoding includes256padding samples beyond the90s presentation timeline. AAC has low boundary residue during the blackout: leading25ms peak−71.46dBFS, trailing−108.67; interior−148.02. Absolute digitalzero is guaranteed in the PCM master, not lossy decodedAAC. Container/audio/video timelines remain exactly90s.
- Captions: independent text audit confirms all33blocks round-trip exactly to approved display text,13characters/line maximum and measured active-voice bounds. Pronunciation has no human listening verdict.
- Covers: native final-MP4 framesA2100/B3840 extracted; separate native headline variants generated and viewed. Hashes are in 小红书/publish-package.json. Package READY; account submission NOT_RUN.
- Local final: PASS, verified APFS clone at final/si-ep14-ghost-in-posterior/小红书/ with the same61,925,852bytes/SHA-256.
- Original GitHub archive: PASS, source commit026ed33c82352890f9dc4f0250a11c6c84532e43 pushed before uploads. EP14 published Release has6assets:1formal film and5review previews, including the retained rejected candidate. Fresh remote inventory, sizes and SHA-256 match; see github-film-verification.json. Uploader also verified the whole249asset archive.
- Independent final backup: PASS, dedicated published final-si-ep14-ghost-in-posterior-bb31a8702522 Release contains only the formal film. Current final/backup-verification.json freshly checked all56local/remote assets across27Releases against catalog SHAff6b6aff43dbab482442b5290241b92549f8b7772db4d221f476d4a7351cc2be.
- Actual restore probe: PASS for the new EP14 final only. Isolated download restored61,925,852bytes with matching SHA-256; repeat skipped the verified file with the sameinode; temporary data cleaned. This does not claim that all historical films were downloaded. See final-restore-probe.json.

Published archives: [Film Release](https://github.com/jggagi/video-making/releases/tag/film-si-ep14-ghost-in-posterior-bb31a8702522), [final backup](https://github.com/jggagi/video-making/releases/tag/final-si-ep14-ghost-in-posterior-bb31a8702522).

## Creative self-assessment and model observation

The intended remembered image is the green organism vanishing at81seconds and leaving one imperfect coral spore. The central action is visibly carried by the warm-cell-to-green conversion, empty membrane and unpressed delete control. Model observation found that this causal contrast is visible without reading the small English instrument annotations. Sound emotion, sustained engagement and the requested emotional impact remain unmeasured without listening/audience evidence.

## Human and platform acceptance

Continuous human viewing: NOT_RUN.
Human listening and pronunciation review: NOT_RUN.
Target-phone/App playback: NOT_RUN.
Actual audience emotional response: NOT_COLLECTED.
Xiaohongshu account upload/submission: NOT_RUN; a requested publication package will be delivered.

No source check, decode result, model observation or technical loudness measurement substitutes for those human/device gates.
