# EP05 v03 acceptance record

**Technical media status: PASS.** Both native 4K editions have been rendered, strictly decoded, checked against the delivery manifest, and measured for shared audio. The archive/catalog and verified backup are pending. Human continuous visual review, listening/pronunciation review, and playback in the actual target phone apps remain separate user-outcome checks; they do not negate the technical media pass or block archival preparation.

## Final encoded editions

| Edition | File | SHA-256 | Size | Video |
|---|---|---|---:|---|
| Bilibili landscape | `B站/si-ep05-landauer-limit-v03-bilibili-120s-4k.mp4` | `12c642ba64d552b3839cf1cf2928d2cbff53a4549851fdf2797c2fc58e0c798a` | 187,241,112 bytes | 3840×2160, H.264/yuv420p, 60 fps, 7,200 frames, 120 seconds |
| Xiaohongshu portrait | `小红书/si-ep05-landauer-limit-v03-xiaohongshu-120s-portrait.mp4` | `ab2765c6fb0220216ae6418f65df0dcb0a03a7b989780a41cde806ffda4594b9` | 202,164,075 bytes | 2160×3840, H.264/yuv420p, 60 fps, 7,200 frames, 120 seconds |

`review/media-validation-20261019T125004.201271Z.json` reports source/manifest validation and strict full-file audio/video decode PASS for both hashes, with no failures. `review/project-check.json` reports PASS. The media validation checks exact dimensions, frame count, duration, AAC stream, 48 kHz stereo, and MP4 layout.

## Visual scan and sampled observations

Both final files were continuously decoded from frame zero for all 7,200 frames by the fixed-region temporal screen. Portrait produced zero flags. Landscape produced two raw watermark-ROI temporal-jump flags at frames 2600 and 5400. `review/landscape-transition-review.json` binds the landscape hash and records the six frames around these transitions: frame 2600 begins a persistent authored hot palette; frame 5400 is the sustained chapter/temperature cut into the deep-space scene. The neighboring frames remain in their new states, with no repeated tile or isolated flash observed in those triplets. Contact sheets are `review/landscape-transition-2600.jpg` and `review/landscape-transition-5400.jpg`.

The scan measures a scaled, fixed ROI and is not a whole-frame perceptual proof. `review/visual-observations.json` records model-assisted observations bound to both hashes: 32 representative frames and 12 motion pairs per edition, plus 32 unique neighboring frames around the eleven repaired portrait frames. The observed samples showed no repeated-tile pattern, obvious clipping/cropping, or subtitles obscuring key imagery. Fine HUD formulas and small labels were not reliably readable at contact-sheet/phone-scale previews. The sample review does not substitute for continuous human viewing.

The portrait repair is bound by `review/portrait-frame-repair.json`: eleven independent same-index native 4K PNG redraws overlay the zero-based frame indexes from the initial failure; there is no interpolation or neighboring-frame substitution. The repair report confirms the source was preserved, the H.264 video was re-encoded at CRF 15, and AAC packet payloads were identical before and after repair. The final portrait SHA matches the media-validation report. Full portrait scan evidence is `review/flicker-after-portrait/temporal-scan.json`; landscape scan evidence is `review/flicker-after-landscape/temporal-scan.json`.

## Audio and narration

Both encoded editions measure −17.0 LUFS and −1.7 dBTP. Their AAC packet payload SHA-256 values match (`53f92a7fe50e82c950a5c60e0e79bbbdf488d23bd8233a798968ee20c9cef4a5`), and decoded PCM SHA-256 values match (`4e6ed1e792e6ce4237d3a303260ee7647ac36f47c41f4efb227797f98879a179`) at exactly 48 kHz stereo and 5,760,000 samples per channel. `review/encoded-audio-details.json` reports all checks true. `review/shared-audio-correlation.json` reports PASS comparing both decodes with the shared PCM master at identical sample offsets.

The shared 120-second PCM master is SHA-256 `43bda3d78e143ccb6250b91ef1795067b88ae90b32366c7c56840e2e7390a29b`, measured −17.0 LUFS / −1.8 dBTP. Its `[5400,5425)` 25-frame vacuum window is exact digital zero. The decoded AAC is not claimed to be digitally zero: the measured full-window peak is −55.19 dBFS; in the interior excluding 20 ms at each edge it is −90.31 dBFS. These are measurements of lossy AAC pre-echo/ringing around the PCM cut.

All ten narration cues were reused; no new TTS calls were made. Both platform SRTs remain byte-identical to v02 (SHA-256 `5b064ce23b64e180825f5a3204712f1476d2ac1c9c0cde0a49be3f7284b06290`). `review/audio-alignment.json` records exact PCM cue reuse and measured anchors. Subtitle phrase divisions are estimated from measured PCM spans, not ASR or word alignment. Human pronunciation and listening judgment remain pending.

## Other technical playback evidence

`review/browser-player-qa.json` reports PASS for a real local Google Chrome player run. Playback was muted; sampled playback showed zero dropped frames (48 landscape frames and 162 portrait frames), with successful seeks at 16, 48, 80, 96.5, and 118.5 seconds and no page errors. This verifies the desktop browser player path only; it is not listening, phone-app, or account-upload acceptance.

The source physics implementation and scientific notes remain unchanged from v02. `review/physics-conservation.json` retains its numerical PASS, and the current `review/project-check.json` is PASS. The original qualifications and speculative boundaries remain in `project/scientific-notes.md` and `project/adapted-script.md`.

## Remaining records

| Gate | Status | Scope |
|---|---|---|
| Technical source, manifest, strict media decode, dimensions/duration/frame count | PASS | `review/media-validation-20261019T125004.201271Z.json` |
| Project and numerical checks | PASS | `review/project-check.json`, `review/physics-conservation.json` |
| Cross-edition AAC packet and decoded PCM identity | PASS | `review/encoded-audio-details.json` |
| PCM-master correlation | PASS | `review/shared-audio-correlation.json` |
| Fixed-region 7,200-frame scans | PASS with reviewed landscape transition flags | `review/flicker-after-portrait/`, `review/flicker-after-landscape/`, `review/landscape-transition-review.json` |
| Desktop Chrome player QA | PASS, muted and sampled | `review/browser-player-qa.json` |
| Continuous human visual review | Pending | Both complete editions |
| Human listening and pronunciation review | Pending | Voice, music balance, and spoken wording |
| Actual target phone-app playback | Pending | Bilibili and Xiaohongshu apps/devices |
| Archive/catalog and verified backup | Pending | Technical media checks are complete; archive evidence will be added when completed |

Human and target-device checks remain clearly separate from the completed technical media status.
