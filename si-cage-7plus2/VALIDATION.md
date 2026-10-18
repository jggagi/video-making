# EP.02 validation record

> 历史版本记录：本文记录原始 1080p 配乐版。当前 4K UHD v3 的规格和验收入口见 [UHD-V3.md](UHD-V3.md) 及 `out/uhd-v3-validation.json`。

## Source and audio

- TypeScript: `npm run typecheck` passed.
- Source/timeline checks: `npm run check` passed. Four acts total 10,800 frames; no runtime randomness, wall-clock animation or external URLs in scene sources.
- PCM: actual WAV headers and samples confirm 180.000 seconds, 48,000 Hz, stereo PCM16, 8,640,000 sample frames, 800 samples per video frame.
- Nine-layer accumulation: independent 250 ms spectral windows detect each activated 220 Hz harmonic and reject not-yet-active harmonics. Layer gains rise additively; the stack is held until the snap.
- Snap: noise starts at sample 960,000, global frame 1200. It ends at sample 969,600, frame 1212. All master samples from frame 1212 through frame 1799 are exactly zero. No overload stem samples remain after the burst.
- Polyphony: the four original imitative parts enter at global frames 6700, 6820, 6940 and 7060. Actual PCM at frame 7130 contains their four distinct fundamentals, approximately 246.94, 293.66, 392.00 and 493.88 Hz. The score uses diatonic C-major pitches and planned 48-note developments, truncated at the oracle transition.
- Reproducibility: two independent synthesis runs produced identical master and three full-length stem hashes. The master SHA-256 is `d6dc699f3be2546d2ba07d179106583dc4125bac0f914d138460e8f419770331`.
- Level: master sample peak is −8.946 dBFS. Saturation is deliberate within the noise generator; the mix does not blanket-clip or normalize the stems.
- Actual stills: 12 frames rendered at 1920×1080 and inspected as a contact sheet. Encoded preview frames 1199 and 1200 were inspected separately to confirm the amber-to-red snap. The Act 1 telemetry panel was subsequently moved to the left to avoid colliding with falling labels; final export uses that correction.
- Geometry sweep: 204,000 Act 3 and 192,000 Act 4 vertices were finite, with safe projection denominators. Act 3 wireframe bounds were x847.934–1381.610, y287.088–796.042; Act 4 bounds were x970.690–1349.881, y261.397–614.293. All four moving telemetry labels fit inside the content area. Decorative halos extend under the HUD intentionally.

Machine-readable details: `out/audio-validation.json`, `out/audio-ep2-manifest.json`, `out/reproducibility.json`.

## Completed full export

- Full film: `out/cage-of-seven-plus-two-1080p.mp4`, H.264 / AAC, 1920×1080, 60 fps, exactly 10,800 video frames / 180.000 seconds of video. Presented AAC and container duration are 180.011 seconds due to codec padding; the source PCM is exactly 180.000 seconds.
- Full film and both previews passed strict complete audio/video decoding with FFmpeg `-xerror`.
- The refreshed overload preview is 270 frames / 4.500 seconds; it was extracted from the final corrected film. The manifold preview is 600 frames / 10.000 seconds of video, with 10.005 seconds presented AAC/container duration.
- Decoded overload preview RMS: nine-layer stack 0.020776, burst 0.213495, post-cut silence 0.0. The noise remains clearly separated from the preceding stack after AAC encoding. PCM transitions are sample-exact; AAC can smear transient edges slightly.
- FFmpeg EBU R128 measurement: integrated master loudness −29.2 LUFS; oversampled true peak −2.5 dBTP. The score deliberately retains the short noise burst and a quiet background. No blanket master loudness normalization was applied.
- Thirteen final encoded frames were extracted, including 1199, 1200 and 10799. The corrected snap frame, manifold frame and final EP.03 frame were inspected individually. Final frames are `out/final-frame-01.png` through `out/final-frame-13.png`; `out/contact-sheet.png` shows all thirteen.
- Sixteen bilingual SRT cues were exported with valid, nonoverlapping frame bounds. Millisecond SRT timing is rounded from the source frame timeline; embedded subtitles retain exact frame timing.
- Full film SHA-256: `e08c1bc00614201f57b1b1a7c6143d82a1ec9e64958fff69f21cb387e52f6cbb`.

Final media measurements: `out/media-validation.json`, `out/loudness-summary.txt`. The project archive is CRC-checked and every included file hash is verified by `scripts/package.py`; its receipt is `out/package-manifest.json`.

## Remaining human checks

Continuous human listening, perceived harshness versus loudspeaker/headphone level, subjective musical quality, and playback on the final device remain unverified. Automated spectral/peak/decode checks do not establish those outcomes. The supplied preview clips allow these judgments without replaying the whole film.
