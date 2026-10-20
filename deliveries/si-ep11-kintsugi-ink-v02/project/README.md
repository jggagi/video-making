# EP11 v02 project checks

This edition is Xiaohongshu-only: native 2160×3840, 60 fps, 90 seconds, and 5,400 frames. The source script remains byte-identical to v01; `delivery.json` records its SHA-256. The approved film clock has eight locked narration segments and exact PCM silence at frames `[4860,4890)`. The replacement visual direction uses `CanyonScene` and `HandScene` Three.js canvases; `Terrain` and `Eternity` are obsolete.

Run commands from the repository root. The source verifier checks the manifest, preserved raw-script hash, locked timeline/segments, caption lines, scene wiring, deterministic frame inputs, and legacy-scene/HUD removal. Missing integration is reported as `INCOMPLETE`, never `PASS`. Exit code `0` means all included checks passed, `1` means a failed invariant, and `2` means an artifact is still pending.

```sh
python3 deliveries/si-ep11-kintsugi-ink-v02/project/scripts/verify_project.py
```

After the audio build has produced SFX events, measured captions, and the PCM master, require them explicitly:

```sh
python3 deliveries/si-ep11-kintsugi-ink-v02/project/scripts/verify_project.py --require-audio
```

The project typecheck is:

```sh
npm --prefix deliveries/si-ep11-kintsugi-ink-v02/project run typecheck
```

After the final encoded MP4 and PCM master exist, collect evidence with the project helper:

```sh
python3 deliveries/si-ep11-kintsugi-ink-v02/project/scripts/collect_qa.py
```

It extracts the specified final-MP4 representative frames at 360×640, three native 4K inspection frames, and in-shot frame pairs 150 frames apart. It measures AAC and PCM-master EBU R128 loudness and compares decoded AAC with the master over 1–4, 47–50, and 86–89 seconds. Reports and generated images are bound to the MP4 SHA-256. Collection is a media job; on Q's Mac, complete the repository workstation storage preflight before running it. This script does not render or encode media.

The compact source package can be created after QA evidence is ready:

```sh
python3 deliveries/si-ep11-kintsugi-ink-v02/project/scripts/package_project.py
```

It verifies ZIP CRCs and each member hash. The package omits movies, dependencies, temporary artifacts, full-resolution review PNGs, and private provider/authorization/credential configuration.

Final media validation, continuous visual screening, and archive catalog creation are separate steps. See the delivery README and `skills/dual-platform-video/references/github-archive.md`; do not treat source checks or extracted frames as media, human, audience, or device acceptance.

## Reproduce the locked render

The exact Node dependency tree is in package-lock.json. This film was rendered with Node24.21.0, Remotion4.0.534 and Chrome155.0.8059.85. PythonQA used Python3.12.14, NumPy2.3.5 and Pillow12.3.0; requirements.txt records these two Python libraries. FFmpeg/FFprobe must be on PATH. No generated image or video service is needed. The licensed generic hand GLBs and their MIT license are local. Typography requires the three macOS system fonts listed in assets-manifest.json; font binaries are not redistributed.

On Q's Mac, read the workstation instructions and verify current volume identities before dependency or render jobs. From this project directory, use `agent-dev run -- npm ci` only when dependencies need restoring, then `agent-dev run -- node scripts/render.mjs stills` for native stills, `agent-dev run -- node scripts/render.mjs preview 2820 3719` for a narrated excerpt, and `agent-dev run -- node scripts/render.mjs video` for the formal movie. The renderer refuses to overwrite an existing moving-image output. Preserve old files before making a new version. Its bundle and intermediate frames use the validated AgentDev temporary directory, with one render worker.

All current narration WAVs and the verified PCM master are packaged. Re-rendering uses this local cache and does not invoke TTS. `scripts/build_audio.py` is for intentional audio changes; it checks the prepared-text authorization and caches before synthesis. No ASR or word-level forced alignment is implied.
