# EP11 v03 project checks

This Xiaohongshu edition remains native 2160×3840, 60 fps, 90 seconds, and 5,400 frames. It preserves the original script, v02 narration master, locked segments, captions, science notes, and 30-frame absolute-silence interval. `HandScene` remains a frame-driven Three.js canvas. The canyon uses two muted local Blender movies. `public/video/canyon-v03.mp4` maps to composition frames `[550,3600)` with the v02 crossfade; within `[2812,3274)`, `public/video/hero-v03.mp4` replaces it with a camera that follows the returning shard and its matching socket. Only one movie decoder is mounted at a time. The old procedural `CanyonScene` source is retained as superseded, inactive history.

The two Blender movies are pending native rendering and encoding. The source verifier reports missing media as `PENDING`, and the renderer refuses to render until both exist. The base media contract is 2160×3840, 30 fps, 1,525 frames over 3,050 composition frames. The hero insert has 231 frames at the same native dimensions and cadence, covering 462 composition frames at 60 fps. Do not treat a source typecheck or an absent-asset placeholder as media acceptance.

Run source checks from the repository root. The verifier checks the delivery and original-source hashes, locked timeline and segments, caption lines, active hand-scene wiring, both canyon video mounts and frame contracts, deterministic frame inputs, and legacy-scene/HUD removal. A missing movie is `INCOMPLETE`, never `PASS`. Exit code `0` means all included checks passed, `1` means a failed invariant, and `2` means an artifact is pending.

```sh
python3 deliveries/si-ep11-kintsugi-ink-v03/project/scripts/verify_project.py
```

After the audio build has produced SFX events, measured captions, and the PCM master, require them explicitly:

```sh
python3 deliveries/si-ep11-kintsugi-ink-v03/project/scripts/verify_project.py --require-audio
```

The project typecheck is:

```sh
npm --prefix deliveries/si-ep11-kintsugi-ink-v03/project run typecheck
```

After the final encoded MP4 and PCM master exist, collect evidence with the project helper:

```sh
python3 deliveries/si-ep11-kintsugi-ink-v03/project/scripts/collect_qa.py
```

It extracts final-MP4 representative frames at 360×640, five native 4K inspection frames, and in-shot frame pairs 150 frames apart. It measures AAC and PCM-master EBU R128 loudness and compares decoded AAC with the master over 1–4, 47–50, and 86–89 seconds. Reports and images are bound to the MP4 SHA-256. This is a media job and does not render or encode.

The compact source package can be created after QA evidence is ready:

```sh
python3 deliveries/si-ep11-kintsugi-ink-v03/project/scripts/package_project.py
```

It verifies ZIP CRCs and each member hash. The package includes both exact canyon movie dependencies and native Blender scenes; it omits other movies, dependencies, temporary artifacts, full-resolution review PNGs, and private provider/authorization/credential configuration.

Final media validation, continuous visual screening, and archive catalog creation remain separate steps. Do not treat source checks or extracted frames as media, human, audience, or device acceptance.

## Reproduce the locked render

The exact Node dependency tree is in `package-lock.json`. The inherited runtime is Node 24.21.0, Remotion 4.0.534, and Chrome 155.0.8059.85; Python QA uses Python 3.12.14, NumPy 2.3.5, and Pillow 12.3.0. FFmpeg/FFprobe must be on `PATH`. No cloud image or video service is used. The licensed hand GLBs and MIT license are local. Typography requires the three macOS system fonts listed in `assets-manifest.json`; font binaries are not redistributed.

The current `node_modules` entry is a symlink to v02's existing dependency tree. From this project directory, after verifying current workstation volume identities, use `agent-dev run -- node scripts/render.mjs stills`, `agent-dev run -- node scripts/render.mjs preview 2760 3359`, or `agent-dev run -- node scripts/render.mjs video`. The render helper checks for both canyon movies before starting. It refuses to overwrite an existing moving-image output. Its bundle and intermediate frames use the validated AgentDev temporary directory, with one render worker.

The verified PCM master and narration WAVs are copied locally. Re-rendering uses this cache and does not invoke TTS. `scripts/build_audio.py` is for intentional audio changes; it checks prepared-text authorization and caches before synthesis. No ASR or word-level forced alignment is implied.

## Reproduce Blender source footage

Blender 4.5.9 LTS arm64 is the tested local application; no install or preference changes are required. `blender/scene.py` builds the original procedural geometry and all native keyframes; `blender/porcelain-canyon-v03.blend` is the saved editable scene. Build tests and rejected render caches are not substituted for final media.

Create an empty dedicated folder below AgentDev Scratch, then run `blender/render_saved.py` through Blender with `--background --factory-startup --disable-autoexec`, `--blend`, `--out`, and the recorded engine/samples. The guard binds saved-scene SHA-256, actual dimensions, cadence, renderer, samples and Blender version; mismatched caches cannot be resumed. `project/encode.py` validates and encodes all1525native frames without resampling or spatial scaling, and writes a per-frame hash ledger. `blender/reframe_hero.py` derives the separate hero camera without changing mesh or material data; its projection report covers every source frame1132–1362. Render that range into a separate guarded cache and use `encode_hero.py` to validate and encode the insert. The exact commands and effective configuration are recorded in `review/render-provenance.json` after rendering.

The film uses authored metallic geometry reveal, not a fluid simulation. See `blender/ART-DIRECTION.md` for visual decisions and `blender/verify_scene.py` for independently reopening the saved scene and checking actual solid meshes and keyed return poses.
