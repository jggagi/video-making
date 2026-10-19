# EP05 v02 editable project

The project targets exactly 120 seconds at 60 fps (7,200 frames) with native 4K landscape and portrait outputs. `segments.json` preserves the source script as `original_script`, the revised `display_subtitle`, and separate `tts_phonetic_text`; display-only prefix/suffix fields are not spoken.

`narration-preview.md` records the final narration inputs. Q authorized the ten prepared inputs in this chat. The final set uses eight newly synthesized Bailian `cosyvoice-v3-flash / longtian_v3` cues and exact verified S09/S10 caches. The first longer S09 take and the authorized preview are retained under `public/audio/revision-history/`. No new provider call is needed to reproduce the film.

The four acts are staged around compression, a red-hot ceiling, atmospheric heat returning to the ground, and a silent radiator unfolding into space. See `brief.md` for the intended experience and `scientific-notes.md` for physical assumptions and deliberate schematic choices.

```sh
npm ci
npm run typecheck
python3 scripts/build_audio.py --mix
python3 scripts/sync_audio.py
node scripts/render.mjs video landscape
node scripts/render.mjs video portrait
python3 scripts/verify_project.py
python3 scripts/collect_qa.py --capture --metrics --compact
```

On Q's Mac use the verified `agent-dev run --` wrapper for dependency/build/render jobs, serially for the two full 4K exports. Existing `node_modules` is reused locally; install from the lockfile on another checkout. The master and narration caches are shared by both compositions. Font resolution uses installed macOS PingFang SC, Menlo and Arial; fonts are not redistributed.

The 25-frame digital vacuum is `[5400,5425)`, samples `[4320000,4340000)`. Subtitle phrase timing is estimated within measured PCM cue spans; it is not ASR or word alignment. Actual final-media evidence and remaining human/device checks are recorded in `../review/acceptance.md`.

Frame QA requires Pillow; this Mac uses the app-bundled Python runtime. Compact capture still decodes all32 native samples per edition on AgentDev temporary storage, retains four native images and every frame hash, and saves contact sheets/12 motion pairs. All other native frames can be reconstructed from the verified final movie.
