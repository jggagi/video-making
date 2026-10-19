# 主权心印 · EP.06 · v02

120 seconds at 60 fps, two native layouts: `Landscape4K` 3840×2160 and `PortraitVertical` 2160×3840. The compositions render directly at these dimensions; preview scale is one third. React19, Three0.180 and Remotion4.0.534 are pinned by `package-lock.json`.

The existing narration, captions, shared PCM master, scientific corrections and mathematical model are preserved from v01. `../review/preservation.json` records their identities. `brief.md` and `timeline.json` describe the visual revision. Fonts use the Mac's Songti SC, PingFang SC and Menlo; those system fonts are not redistributed in the project.

## Rebuild on Q's Mac

Read the current workstation instructions and inspect `agent-dev status --json` before dependency or render work. Commands below run from this project directory. Respect an existing environment and current external-volume validation.

```sh
/Users/guoq/.local/bin/agent-dev run -- npm ci
npm run typecheck
python3 scripts/verify_project.py
/Users/guoq/.local/bin/agent-dev run -- node scripts/render.mjs stills portrait 960 3120 4800 5760 7100
/Users/guoq/.local/bin/agent-dev run -- node scripts/render.mjs review portrait
/Users/guoq/.local/bin/agent-dev run -- node scripts/render.mjs video landscape
/Users/guoq/.local/bin/agent-dev run -- node scripts/render.mjs video portrait
```

Render one full edition at a time. `EP06_RENDER_CONCURRENCY` accepts1 or2 frame workers (default1); choose2 only after a fresh resource check. The final production used2 workers within a single render job. Existing full MP4s are protected against overwrite; stills and previews receive revision suffixes. Use a separate work/version directory for a new formal export. The renderer uses an already-installed Chrome executable, not a newly downloaded browser.

## Inspect the delivered media

```sh
python3 scripts/collect_qa.py --capture
python3 scripts/capture_motion.py
python3 scripts/verify_shared_audio.py
python3 scripts/finalize_metadata.py
python3 scripts/serve-preview.py
```

The local player is `http://127.0.0.1:3108/watch.html`. It supports native video controls, seeking and independent landscape/portrait files. The server binds only to loopback and supports byte ranges.

QA reports bind actual encoded files by hash. Paired-frame differences are review cues, not automatic visual acceptance. `../review/acceptance.md` keeps human viewing/listening and device playback separate from automated measurements. The editable ZIP excludes dependency trees, generated bundles and video exports; its per-file manifest and CRC checks retain source/assets/captions and compact QA.
