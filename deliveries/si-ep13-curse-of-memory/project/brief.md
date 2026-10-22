# EP13 production brief

## Purpose and story

- Work: 《无法遗忘的诅咒》 (WHEN FORGETTING BECOMES ILLEGAL), 一眼万年 Season 3, Episode 13.
- Audience experience: leave the viewer with the image of a painful memory that first fades with time, then is welded into permanent replay; the core intuition is that forgetting can be merciful.
- Treat the SI memory lock as a fictional thought experiment. Telemetry and numerical values are illustrative, not measurements or clinical claims.
- Preserve the source's complete narration and display wording in the order and segment boundaries recorded in adapted-script.md. Captions are revealed in readable phrase-sized subdivisions; final subdivision timing follows the actual PCM narration, not estimates from text length.

## Locked delivery specification

- Xiaohongshu vertical edition only.
- Native canvas: 2160 × 3840, 60 fps, exactly 90 seconds / 5,400 frames.
- Frame ranges are half-open: [startFrame, endFrame). Total range is [0, 5400).
- Logical layout: 1080 × 1920, rasterized at 2× for native output. No encoded 1080p intermediate is enlarged.
- Audio master target: stereo PCM, 48 kHz, 4,320,000 samples per channel, target -16 LUFS, true peak no higher than -1.0 dBTP.
- The provider manifest records Aliyun Bailian, effective model cosyvoice-v3-flash, voice longtian_v3, and rate 1.0 for the generated cues. S01 active speech measures [48000, 472868) at 48 kHz; S02 active speech begins at sample 480000. The final mixed PCM is verified separately.
- Deterministic frame-driven output: no random or wall-clock state. No static composition or merely blinking hold exceeds 180 frames.

## Visual direction and composition

Use pure deterministic 2D SVG/flat graphics, with no 3D geometry, perspective transform, camera rotation or 3D scene. The visual language is a 1970s amber-phosphor oscilloscope combined with an archival film strip: deep espresso cathode black (#120D0A), warm amber (#FF9E00), muted sepia (#78350F), bone-white (#FEF3C7), gold (#F59E0B) and trauma rust-red (#DC2626). A subtle horizontal scanline texture uses 2 logical pixels of pitch at 4% opacity, over a warm vignette.

Keep continuous 2D spatial evolution throughout long scenes: draw-on curve motion, translating scanlines, shifting graticule/film-strip geometry, changing waveform shape, accumulating trails, and controlled collapse or fade. Brightness pulses, counters, and flicker alone do not satisfy the motion rule.

The fixed three-line HUD stays left aligned in the 9%–14% top band, begins at 6% canvas width, and ends no farther right than 84%. Use 30 logical-pixel monospace text (10 pixels at a 360-pixel preview width), with the abbreviated strings in telemetry-lexicon.json. This preserves legibility inside the mobile safe zone. The first line switches at frame 1320. Full source wording remains in the lexicon.

Keep subtitles bold and at least 42 logical pixels (14 pixels at 360-pixel preview width), in no more than two lines. Place their anchor in the 24%–28% band measured up from the bottom (72%–76% from the top); keep the full bounding box within the safe region. The approved S01 caption window is [60, 592), while its authored source window [60, 540) stays unchanged. The 31 phrase captions are distributed by character weight inside measured active PCM spans; this is estimated phrase timing, not ASR or forced word alignment. The foreground closing quotation remains visible; subtitles reveal its phrases progressively. Show the subtle disclaimer only on [5160, 5400), at opacity 0.35.

## Acts and intended visible change

1. **[0, 1320) — merciful biological fade.** A 2D graticule supports the exact plot of the chosen exponential memory model R(t) = exp(-t/S). A trauma waveform begins jagged, then progressively smooths and fades as the playhead travels from DAY 001 through DAY 030, DAY 365 and YEAR 10. Introduce the season and title as clean 2D type.
2. **[1320, 2820) — decay welded flat.** At frame 1320, a bone-white horizontal beam lifts the curve to a fixed 100.000% retention line. Quantization stems and brackets lock the historical signals; move/draw them continuously.
3. **[2820, 4380) — phosphor accumulation.** 2D Lissajous/rose traces from YEAR 01, YEAR 03, YEAR 07 and YEAR 15 accumulate without decay. Their overlap grows into a bone-white and rust-red tangle by frame 3900, obscuring the present.
4. **[4380, 5400) — overload, then release.** Sustain visibly changing 2D saturation through frame 4859. Put the CRT snap impulse in [4859, 4860), ending exactly at the silence boundary. Keep absolute silence on [4860, 4890). Start the warm, slightly out-of-tune piano at frame 4890. The full foreground quote appears at the release; its subtitle phrases progress with narration. Narration for S08 begins no earlier than frame 4902. Collapse the tangled traces to a breathing amber line, then let the line and dust attenuate.

The exact geometry sources and all key frame events are in timeline.json. Full and compact on-screen wording pairs are in telemetry-lexicon.json. The accepted S01 cue starts at sample 37571 so its measured voice onset lands at sample 48000 (1.0 s); active speech ends at sample 472868 (9.8514167 s). S02 active speech starts at sample 480000 (10.0 s). Complete cue windows overlap by 13,483 samples (0.2808958 s), while the measured active speech windows do not overlap. Neither cue is shortened or accelerated.

## Sound and timing rules

Use the shared 90-second stereo PCM master for the edition. Narration text, visible captions, effects and music remain distinct layers. The source calls for procedural cassette/vinyl texture and calibration tone at frame 60, a soft chord at 840, fading tape hiss at 1500, a magnetic relay at 1920, CRT whine/phase-lock at 2160, feedback stacking at 2940, a Shepard rise at 3900, and a high-frequency harmonic cluster at 4500. The exact effects spans and frame-to-sample mapping are in timeline.json.

The frame-4860 snap/silence conflict is resolved as follows: the snap occupies the frame immediately before the boundary, silence is [4860, 4890), piano starts at frame 4890, and S08 narration starts at or after frame 4902. If a transient overlaps narration elsewhere, shape it according to the production guide by moving the speech onset 9–18 frames or reducing the 1–4 kHz effect energy; preserve the event's narrative placement and verify the final mix. Apply true-peak limiting and measure the encoded file before claiming compliance.

## Acceptance state

The source verifier records exact script text, approved voice placement, caption structure, native composition settings, event frames, and the PCM master's stereo 48 kHz format, exact length, and blackout silence. The final MP4 is now present and the source verifier reports PASS; encoded-media validation is recorded separately in review/acceptance.md. It does not measure LUFS or true peak. Encoded render checks, visual review, continuous viewing/listening, target-device playback, and audience feedback remain separately unverified until evidence is recorded.
