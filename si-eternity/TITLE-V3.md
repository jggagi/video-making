# Title v3 · 一眼万年

This note records the current title edition for **一眼万年 (ONE BLINK, TEN MILLENNIA)**. The film remains 180 seconds, 60 fps, 10,800 frames, 1920 × 1080. The current compositions are `OneBlinkTenMillennia` and `OneBlinkTenMillenniaVoicedV3`. The older `HalfSecondEternity` and `HalfSecondEternityVoicedV2` IDs are no longer registered.

## Opening title

The opening title overlays Act 1 local frames 60–360. A single frame-driven alpha rises from 0 to 1 over frames 60–105, holds through frame 300, and fades to 0 by frame 360. The content scrim and competing scene text follow that same fade.

The centered Chinese title is `一 眼 万 年`, set in white at 88 px and weight 300 with `0 0 30px rgba(6,182,212,0.5)` cyan text shadow. Its letter spacing interpolates from 16 px at frame 60 to 36 px at frame 360. The English line is `O N E   B L I N K ,   T E N   M I L L E N N I A`, in cyan at 20 px with `0.4em` tracking. The amber monospace formula reads `[ Δt_atom = 0.30s  |  Δt_bit = 10^4 Years ]`.

## Act 4 transition and ending

The eyelid transition now fades into the laboratory during Act 4 local frames 1900–2100, retracts over local frames 2100–2400, and is fully open at the droplet impact on global frame 9600. The impact stays at its original global frame and time: **9600 / 160 s**.

The world fades to void `#050811` on global frames 10480–10500. The HUD fades over frames 10470–10500. The closing quote, **人类眨眼一瞬，硅基已历万年。**, begins after the HUD has cleared. The title `一 眼 万 年` is 128 px; its cyan laser pass travels across the title on Act 4 local frames 3420–3570 (global 10620–10770). The ending title remains on the void through the final frame, global 10799.

The physical clock still reaches 500 ms at global frame 10200. The subjective-years counter is now explicitly linear: `10000 × clamp(globalFrame / 10200)`, so it reads exactly **10,000.0 years** at frame 10200. The impact occurs earlier, at frame 9600. The HUD labels the altitude **NORMALIZED REFERENCE TRAJECTORY**; the 500 ms reference clock and the impact are separate editorial cues.

## V3 narration and mix

The voice plan and manifest are in `audio-v3/`. V3 changes cue 01 to the ten-millennia line and cue 21 to the new closing quote. Those two clips were generated with Bailian CLI 2.3.0 using the `cosyvoice-v3-flash` model, `longtian_v3` voice, and rate 0.96. The other twenty verified v2 voice clips are reused by hash. The v2 procedural music and sound-design stems remain unchanged.

`voice:plan` and `voice:generate` default to the v3 plan. Generating audio only calls Bailian when a changed clip is not already available and matched to its manifest. The v3 soundtrack master is `public/audio-v3/soundtrack.wav`. To mix v3 narration with the existing v2 music and sound-design stems:

```sh
node scripts/audio.mjs mix --edition audio-v3 --stems-edition audio-v2
```

`npm run render` (or `npm run render:voiced`) renders the full voiced v3 edition to `out/one-blink-ten-millennia-v3.mp4`. `npm run render:silent` renders the silent edition to `out/one-blink-ten-millennia-silent-v3.mp4`. The focused voiced previews are:

| Command | Frame range | Output |
| --- | --- | --- |
| `npm run preview:opening` | Global 0–479 | `out/opening-title-v3.mp4` |
| `npm run preview:ending` | Global 10440–10799 | `out/ending-title-v3.mp4` |

`npm run titles` renders stills at the opening, impact, clock endpoint, and ending-title checkpoints. The renderer modes are `titles`, `opening-voiced`, and `ending-voiced`; the two voiced preview modes include the v3 soundtrack.

## Retained history and validation

Earlier v1 and v2 MP4 exports and source ZIPs remain in `out/`, including `the-half-second-eternity.mp4`, `the-half-second-eternity-voiced-v2.mp4`, `si-eternity-project.zip`, and `si-eternity-voiced-v2-project.zip`. The old composition IDs are not retained as aliases. `BRIEF.md`, `AUDIO-V2.md`, and `VALIDATION.md` are unchanged historical records.

V3 technical validation passed and is recorded in `out/title-v3-validation.json`: 1920×1080, 60 fps, exactly 10,800 video frames; strict complete audio/video decode; fast-start MP4; unchanged render-source snapshot and both prior full-film hashes. Encoded audio is AAC 48 kHz stereo, approximately −18.15 LUFS and −1.43 dBTP, with zero-lag correlation 0.999945 against the complete PCM master. The PCM and video are exactly 180 s; the container is 180.011 s because decoded AAC carries 512 padding samples.

The opening and ending previews contain exactly 480 and 360 video frames. The representative encoded-film frames 120, 10200, 10650 and 10799 were visually inspected, including the exact `10,000.0 YEARS` HUD endpoint and completed final card. This is representative-frame review; continuous human listening and final-device playback remain open.

Bailian TTS generated only the two revised cues. One additional Bailian ASR call read back those two clips; its unnormalized result is retained in `audio-v3/asr-revisions-review.json`. It renders “一万年” as “1万年” and matches the closing quote literally. No full-film human listening claim follows from this ASR check.

The editable archive `out/one-blink-ten-millennia-v3-project.zip` contains source, all 22 active voice clips, original music and sound-design stems, v3 master/narration, and their manifests. `scripts/package-v3.py` checks ZIP CRCs and individual SHA-256 values; its final archive ledger is `out/package-v3-manifest.json`. Old MP4 exports are excluded from the archive; reproducing the history-hash checks requires the retained workspace exports.
