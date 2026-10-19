# EP05 v03 editable project

The project targets exactly 120 seconds at 60 fps (7,200 frames) with native 4K landscape and portrait outputs. `segments.json` preserves the source script as `original_script`, the revised `display_subtitle`, and separate `tts_phonetic_text`; display-only prefix/suffix fields are not spoken.

`narration-preview.md` records the final narration inputs. Q authorized the ten prepared inputs in this chat. The final set uses eight newly synthesized Bailian `cosyvoice-v3-flash / longtian_v3` cues and exact verified S09/S10 caches. The first longer S09 take and the authorized preview are retained under `public/audio/revision-history/`. No new provider call is needed to reproduce the film.

v03 addresses the user-reported portrait flashing and adds an original atmospheric musical score; see `../source/revision-request.md` and `music-notes.md`. v02 remains retained.

The four acts are staged around compression, a red-hot ceiling, atmospheric heat returning to the ground, and a silent radiator unfolding into space. See `brief.md` for the intended experience and `scientific-notes.md` for physical assumptions and deliberate schematic choices.

```sh
npm ci
npm run typecheck
python3 scripts/build_audio.py --mix
python3 scripts/sync_audio.py --write
node scripts/render.mjs video landscape
node scripts/render.mjs video portrait
python3 scripts/verify_project.py
python3 scripts/collect_qa.py --capture --metrics --compact
```

On Q's Mac use the verified `agent-dev run --` wrapper for dependency/build/render jobs, serially for the two full 4K exports. The repository-root `node_modules` is reused locally via a verified local symlink; install from the lockfile on another checkout. The master and narration caches are shared by both compositions. Font resolution uses installed macOS PingFang SC, Menlo and Arial; fonts are not redistributed.

The 25-frame digital vacuum is `[5400,5425)`, samples `[4320000,4340000)`. Subtitle phrase timing is estimated within measured PCM cue spans; it is not ASR or word alignment. Actual final-media evidence and remaining human/device checks are recorded in `../review/acceptance.md`.

Frame QA requires Pillow; this Mac uses the app-bundled Python runtime. Compact capture still decodes all32 native samples per edition on AgentDev temporary storage, retains four native images and every frame hash, and saves contact sheets/12 motion pairs. All other native frames can be reconstructed from the verified final movie.

## Current technical media QA

Both native 4K editions now exist. The Bilibili landscape file is 187,241,112 bytes, SHA-256 `12c642ba64d552b3839cf1cf2928d2cbff53a4549851fdf2797c2fc58e0c798a`; the Xiaohongshu portrait file is 202,164,075 bytes, SHA-256 `ab2765c6fb0220216ae6418f65df0dcb0a03a7b989780a41cde806ffda4594b9`. Each is 120 seconds, 60 fps and 7,200 frames (`../review/media-validation-20261019T125004.201271Z.json`). Source and strict media validation, `../review/project-check.json`, cross-edition audio correlation and encoded-audio checks report PASS; see `../review/acceptance.md` for evidence and limits.

Both encoded editions carry the same AAC packet payload hash and decode to the same 48 kHz stereo PCM stream of exactly 5,760,000 samples per channel. The shared PCM master has exact zero in frames `[5400,5425)`. AAC is lossy: the measured decoded AAC gap has a −55.19 dBFS peak across the full 25 frames and −90.31 dBFS in the interior after excluding 20 ms at each edge. These measurements do not assert digital zero in AAC. Desktop Chrome player QA passed muted playback and seeks with zero dropped frames in the sampled playback intervals; it is not listening, phone-app, or account-upload acceptance.

Each final movie was continuously scanned for all 7,200 frames by the region-based temporal screen. Portrait had zero flags. Landscape retained raw temporal-jump flags at frames 2600 and 5400; a six-frame transition review confirmed the persistent hot palette and the chapter/temperature cut, without a repeated tile or isolated flash. The screen and transition review are bounded evidence, not whole-film perceptual proof. Model-assisted sample observations and remaining acceptance gates are recorded in `../review/acceptance.md`.

## Portrait tile-capture investigation

The first complete v03 portrait CPU/PNG capture still contained repeated-tile corruption at zero-based frames `138, 142, 147, 149, 153, 164, 3842, 3853, 3857, 6928, 6992`. The original failed capture is retained at `../review/iterations/portrait-initial-capture/`. That capture used the project-local Chrome launcher, which disables GPU and GPU rasterization, and PNG frame intermediates. After it, `src/Film.tsx` gained a readiness gate that waits for `document.fonts.ready` and two `requestAnimationFrame` paint ticks before declaring a frame ready. The repaired final portrait and its full scan are now available. Because rendering, frame repair, and the readiness gate changed across iterations, the gate's individual causal effect is not isolated.

Each of the eleven replacement PNGs in `frame-repairs/portrait/` is a separate native-4K still render of the same composition at the same absolute frame index. They are not interpolated and do not substitute a neighboring frame. To reproduce the workflow from the project directory, use a fresh output location configured by the delivery manifest before a full render; keep retained evidence and existing movies intact. On Q's Mac, first check `agent-dev status --json`, then run the render through the wrapper:

```sh
agent-dev run -- node scripts/render.mjs video portrait
agent-dev run -- node scripts/render.mjs stills portrait 138 142 147 149 153 164 3842 3853 3857 6928 6992
```

The still command writes `../review/source-portrait-<frame>.png`; copy only those eleven same-index PNGs into `frame-repairs/portrait/frame-<zero-padded-frame>.png`. Scan the complete encoded candidate continuously from its first frame, without seek-based sampling:

```sh
python3 scripts/scan_temporal.py \
  --media ../小红书/si-ep05-landauer-limit-v03-xiaohongshu-120s-portrait.mp4 \
  --layout portrait --expected-frames 7200 \
  --output-dir ../review/portrait-scan-before-repair
```

The scan saves per-frame CSV/JSON and a suspicious-frame contact sheet. It is a conservative watermark/safe-strip screen, not a whole-picture perceptual pass. Apply the selected overlays into a new MP4 and report file (the tool refuses to overwrite either path), then scan that new encoded output again:

```sh
python3 scripts/repair_frames.py \
  --input ../review/iterations/portrait-initial-capture/si-ep05-landauer-limit-v03-xiaohongshu-120s-portrait.mp4 \
  --frames-dir frame-repairs/portrait \
  --output ../小红书/si-ep05-landauer-limit-v03-xiaohongshu-120s-portrait-repaired.mp4 \
  --expected-frames 7200 \
  --report ../review/portrait-frame-repair.json
python3 scripts/scan_temporal.py \
  --media ../小红书/si-ep05-landauer-limit-v03-xiaohongshu-120s-portrait-repaired.mp4 \
  --layout portrait --expected-frames 7200 \
  --output-dir ../review/portrait-scan-after-repair
```

`repair_frames.py` overlays only the requested zero-based frame indexes, encodes the video at CRF 15, and copies the audio stream. Its report binds input/output hashes and verifies audio packet payload hashes match byte-for-byte. The repaired portrait has since been continuously scanned for 7,200 frames with zero flags in the tool's screening regions. The landscape scan produced raw flags at 2600 and 5400; the retained triplets and source boundaries identify them as persistent authored transitions. See `../review/landscape-transition-review.json` and `../review/visual-observations.json`. These region and sample checks do not replace human continuous visual review.
