# EP14《死后第七年，他还在回微信》

Native portrait2160×3840 /60fps /90.00seconds /5400frames. The single 48kHz stereo PCM master contains4320000samples/channel. Use the pinned root Remotion4.0.534 toolchain; no dependency upgrade was performed.

- `node ../../../node_modules/typescript/bin/tsc --noEmit`
- `python3 scripts/verify_project.py`
- `agent-dev run -- <bundled-python> scripts/generate_rd.py` generates the deterministic2D Gray–Scott cache if missing; inspect its CLI first.
- `agent-dev run -- node scripts/render.mjs stills`
- `agent-dev run -- node scripts/render.mjs preview 3900 4079`
- `agent-dev run -- node scripts/render.mjs video` stages native video on verified AgentDev scratch.
- `agent-dev run -- python3 scripts/mux.py` publishes the verified video with the PCM master as AAC.
- `agent-dev run -- <bundled-python> scripts/collect_qa.py` collects encoded evidence; it does not judge the film.

Run the repository delivery validator and continuous all-frame scanner as documented in the production skill. Rendered covers A/B must be extracted from final MP4 at frames2100/3840; headline editions are separate.

Read brief.md, scientific-notes.md, timeline.json, segments.json, assets-manifest.json and review/acceptance.md for purpose, corrections, timing, provenance and actual acceptance scope. Human listening, continuous human viewing and device/App playback are separate observations. The publishing package is not an account submission.

The delivered MP4 includes an exact-state redraw of absolute frame405 after the first capture showed a repeated-text artifact. The rejected capture, native redraw, five-frame indexing fixture, repair command/audio packet digests, full final scan and final encoded neighbor evidence are retained in `../review/`. See `capture-repair.json` and `validation-provenance.json`; no neighbor-frame substitution or interpolation was used. Rendering commands refuse existing outputs to preserve versions.
