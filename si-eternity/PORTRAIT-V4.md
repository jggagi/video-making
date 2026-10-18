# Native Portrait Edition · v4

Portrait v4 adds a native 9:16 edition of **一眼万年 (ONE BLINK, TEN MILLENNIA)**. It is a separate Remotion composition, `OneBlinkTenMillenniaPortraitV4`, at **1080 × 1920, 60 fps, 10,800 frames, 180 seconds**. The existing horizontal silent composition `OneBlinkTenMillennia` and voiced v3 composition `OneBlinkTenMillenniaVoicedV3` remain registered at 1920 × 1080 with their existing outputs and timeline.

The portrait film is laid out for a phone screen rather than made by cropping a horizontal render. Its four portrait acts share the original frame timeline and reuse the underlying deterministic scene state:

| Act | Global frames (end exclusive) | Portrait treatment |
| --- | --- | --- |
| Act 1 | 0–1800 | Native pipette and droplet, petri dish, blink, then expanding circuit paths. The opening title remains at local frames 60–360. |
| Act 2 | 1800–4500 | The existing 600-node search state, pruning, and verified golden path are arranged in a native portrait panel. |
| Act 3 | 4500–7200 | The existing 64 vertices and 160 edges are projected into the portrait composition alongside the code stream. Shattering begins at local frame 300; the manifold collapses at local frame 2580. |
| Act 4 | 7200–10800 | Digital nodes occupy the upper panel and the mechanical gear sits below. The original digital field, gear mechanism, and laboratory SVG components are reused directly; the landscape composition is not rendered and cropped. The impact remains at global frame 9600 / local Act 4 frame 2400. |

## Portrait layout and timing

The root uses **44 px Chinese captions**, with semantic two-line breaks that preserve every character, and **50 px act headings**. The core scene area spans approximately x=80–960 and y=460–1426. The physical and subjective clocks begin at y=176 and use 40 px numerals. Captions occupy y=1440–1650; the footer identifies the piece as an AI-assisted creative thought experiment.

The existing reference timing remains shared with the horizontal film: at global frame 10200, the physical reference clock reaches 500.0000 ms and the subjective counter reads **10,000.0 年**. The portrait HUD fades from frames 10470–10500, then the ending card runs through frames 10500–10799.

The film remains an artistic thought experiment, not a measured SI benchmark or physical simulation. The years counter and normalized reference mapping are editorial graphics.

## Soundtrack

Portrait v4 uses the existing local `public/audio-v3/soundtrack.wav`, SHA-256 `7d0b79b47b888a04806b4087f3b3517c1ad9989f4080f3bf10a362cb9e651571`. It adds no narration, cloud calls, audio assets, or new mix. Remotion renders use the local soundtrack file.

## Render and inspect

Run commands from the project directory:

```sh
npm run portrait:stills
npm run portrait:preview
npm run portrait:render
```

`portrait:stills` renders the representative portrait frames selected by `scripts/render-portrait.mjs`. `portrait:preview` renders global frames 9360–10079, a 12-second layout preview at `out/portrait-layout-preview-v4.mp4`. `portrait:render` renders the complete film to `out/one-blink-ten-millennia-portrait-v4.mp4`.

For selected global frames or a horizontal source check:

```sh
node scripts/render-portrait.mjs frame 9600 10200 10799
node scripts/render-portrait.mjs landscape-check
```

The frame mode writes portrait stills to `out/portrait-v4-frame-<frame>.png`. `landscape-check` selects the original horizontal composition and writes comparison frames under `out/portrait-v4-landscape-frame-<frame>.png`.

## Validation and packaging

After the full render, `scripts/validate-portrait-v4.py` checks video format and duration, strict audio/video decoding, the soundtrack hash and synchronization, AAC padding and peak, loudness measurements, fast-start ordering, the source snapshot, and unchanged v1/v2/v3 film hashes. It compares decoded RGB pixels with the existing horizontal v3 frames at global frames 120, 9600, and 10799, then extracts portrait frames for later inspection. The report is `out/portrait-v4-validation.json`; the source hash map is `out/render-source-portrait-v4-sha256.json`.

**Technical QA passed.** The film contains exactly 10,800 video frames at 1080×1920/60 fps. Full audio/video decode, fast-start ordering, the unchanged audio-master hash, and the render-source snapshot passed. V1, v2 and v3 full-film hashes remain unchanged; the three horizontal reference frames match exactly in RGB pixels.

The full encoded audio is approximately −18.15 LUFS and −1.43 dBTP; its zero-lag correlation to the complete PCM master is 0.999945. The 12-second preview uses the master window 156–168 s with correlation 0.999939. Video and PCM durations are exactly 180 s, while the MP4 container is 180.011 s because AAC carries 512 padding samples.

Encoded frames 120, 1200, 3240, 6000, 7800, 10200, 10650 and 10799 were inspected, including a contact sheet at 360 px per phone frame. Primary captions preserve every source character and cue interval within two lines, with at most 18 characters per line. Tiny inherited SVG labels in Act 4 are hidden in the portrait layout and replaced by the larger Chinese headings. This is representative-frame review; continuous human listening and actual phone-app playback remain open.

Create the editable source archive with:

```sh
python3 scripts/package-portrait-v4.py
```

This writes `out/one-blink-ten-millennia-portrait-v4-project.zip` and `out/package-portrait-v4-manifest.json`. The archive includes portrait source, local audio, and validation records while excluding film MP4s, Remotion bundles, and `node_modules`.
