# EP18 v03 engineering notes

This editable Remotion project produces the Xiaohongshu-only portrait film
`si-ep18-sovereign-subcurrent-v03`: 2160×3840, 60 fps, 90 seconds, 5400 frames.
It is a pure-2D composition. `../delivery.json`, `segments.json`,
`timeline.json`, `sfx_events.json`, and `audio-plan.json` are the current v03
contracts; this project does not reuse v02 review results.

## Build and delivery checks

Run commands from the repository root. The project package is pinned by
`package-lock.json`; use the repository's existing dependency environment.

```sh
cd deliveries/si-ep18-sovereign-subcurrent-v03/project
npm run typecheck
node scripts/verify_frames.mjs
python3 scripts/audio_pipeline.py synthesize --ids S01 S02 S03 S04 S05 S06 S07 S08
python3 scripts/audio_pipeline.py mix
npm run stills
npm run covers
npm run render
python3 scripts/mux.py
python3 scripts/verify_encoded_audio.py
python3 scripts/collect_qa.py
python3 scripts/make_assets_manifest.py
```

Narration synthesis contacts the configured provider. Use it only under the
current v03 authorization and retain its `review/audio-synthesis.json` identity
and text-hash evidence. Mixing and muxing require the v03 reports and current
PCM master. The encoded-audio verifier measures PCM-master/AAC correlation and
checks exact zero PCM samples for frames `[4860, 4890)` (30 frames); it does not
claim that lossy AAC silence is bit-exact.

`collect_qa.py` binds its report to the final MP4 SHA-256, measures encoded
media metadata and EBU R128 loudness, saves phone review frames plus native
frames 3720, 4897, 4920, and 2400, and measures motion in the configured act
pairs. The 4897 near-glint supplemental frame is not assessed by the collector.
These measurements and contact sheets are evidence for review, not visual or
human acceptance.

Run the separate full-frame visual screen and delivery validator from the
repository root after collection:

```sh
python3 skills/xiaohongshu-video/scripts/scan_visual_qc.py \
  --media deliveries/si-ep18-sovereign-subcurrent-v03/小红书/si-ep18-sovereign-subcurrent-v03-xiaohongshu-90s-portrait.mp4 \
  --expected-frames 5400 \
  --output-dir deliveries/si-ep18-sovereign-subcurrent-v03/review/visual-qc-xiaohongshu
python3 skills/xiaohongshu-video/scripts/validate_delivery.py \
  deliveries/si-ep18-sovereign-subcurrent-v03 --scan-source
```

## Acceptance still pending

Review cover candidates A and B at native resolution and inspect the
supplemental near-glint frame. Complete continuous human playback with the
actual narration and sound, then confirm playback on the target phone. The
delivery manifest's `qa` fields remain pending until those checks are actually
performed. A clean automated scan or successful render does not complete these
human/device checks.

## Final-backup restore probe

After the v03 final movie has been uploaded and recorded in the current final
backup catalog, run `scripts/restore_probe.py` from an environment whose
`TMPDIR` is on the verified AgentDev volume. It downloads only the single v03
Xiaohongshu final into an isolated directory, verifies byte count and SHA-256,
repeats the restore to confirm the matching file is skipped, and writes
`review/final-restore-probe.json`. Do not run it against v02 or a historical
catalog entry.


## 本版实测时间与复查

本片正式旁白合成语速为1.65，未对既有波形做变速。S07完整PCM实测8.290917秒，将起点提前至4300帧，保留原始4380帧窗口记录，且在4800帧前结束。S08从4890帧后起音以保留30帧绝对静音。原始台词与字幕逐字保留，字幕为真实PCM范围内的分句估算，未用ASR。

`make_previews.py`串行制作三个原生带声样片；`review_previews.py`需要NumPy/Pillow，会核查样片规格、全局音频时钟并收集实际编码手机帧。`verify_project.py`使用工程内保存的source/script.md，无需原Downloads路径。`fetch_fonts.py`记录官方Google Fonts来源；已随工程保留字体与OFL，不需要在渲染时联网。

最终清单、逐帧视觉报告与模型观察都必须绑定当前MP4散列。连续真人听看与手机App播放未实际完成时继续记录pending；账号发布不属于本次制作。
