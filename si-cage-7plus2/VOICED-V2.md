# 百炼配音版 v2

> 历史版本记录：本文的 1080p 参数与重建命令对应 v2 源工程 ZIP。当前工作区已升级为 4K UHD v3，最新入口和交付文件见 [UHD-V3.md](UHD-V3.md)；本文件保留配音来源、混音和历史验收信息。当前 `render:voiced` 输出 4K，旧版复现请使用 v2 归档。

Current narrated film: `out/cage-of-seven-plus-two-voiced-v2-1080p.mp4`. It is **180.000 seconds, 1920×1080, 60 fps, 10,800 video frames**, with 48kHz stereo AAC audio. The original score edition and its ZIP remain available under their original filenames.

## Voice and provenance

The user selected Bailian and explicitly approved upgrading `bl` from 2.3.0 to **2.3.1**. The CLI and installed Bailian skills were upgraded and their versions matched before synthesis. Authentication was configured, the default TTS voice catalog resolved to `cosyvoice-v3-flash`, and `longtian_v3` was listed as 龙天 / 磁性理智男.

Seventeen segments were newly synthesized using `bl speech synthesize`: **17 successful requests, zero failed requests**, 344 input characters including punctuation and spaces, 76.803292 seconds of source speech. One representative closing-quote sample was generated first and reused in the batch by text/settings/content hash. CLI output reported `cosyvoice-v3-flash` and `longtian_v3` on each segment. Independent provider-side model/voice version fields were not returned and remain null. Usage and actual billing were not reported; no claim of zero cost is made.

The voice uses rate 0.96, mono 24kHz PCM16 WAV. `7±2` is sent as `七加减二`; trailing visual ellipses become spoken comma pauses. Visible subtitles and the closing quote remain unchanged. The 16 existing subtitle cues plus the visible closing quote form the 17 voice segments. All canonical files and provider originals are retained separately. The provider's streaming WAV headers declared a longer data length than the physical payload; normalization changed the container only, with input payload and decoded canonical PCM hashes verified identical.

## Timing and mix

- Voice clips fit their existing subtitle windows without acceleration: every `atempo` value is 1.0, and every 24kHz source sample is retained after exact 2× resampling to 48kHz.
- At frame 1200 the original 200ms overload burst is preserved sample-for-sample. Frames **1212–1241** are digital silence. Post-crash narration is placed at frame **1242 / 20.700 seconds**, leaving half a second of quiet after the burst.
- The manifold score still begins at frame 6700. The first manifold narration is placed later within its subtitle interval, at frame 7200, leaving the music entrance audible and keeping the two parts of that sentence close together.
- The overload stem stays at unity gain. Only the order and atmosphere stems duck by 7dB under voice, with a 150ms lead, 90ms attack, and 450ms release.
- Per-cue normalization targets −20dBFS non-silent RMS, caps gain at +6dB and voice sample peaks at −3dBFS. There is no blanket mix clipping or master loudness normalization.
- Measured full-mix integrated loudness is **−21.1 LUFS**; oversampled true peak is **−2.5 dBTP**.

`scripts/mux-voiced.mjs` copies the original encoded video stream and replaces only the audio. Before/after encoded-video stream hashes match: `SHA256=468ce96133f582c5cd3607f9788d8127303d05eb5b9893183cc9d6a4d312d774`.

## Rebuild and playback

Studio composition: `CageOfSevenPlusTwoVoicedV2`. Playback and remuxing use cached local audio and do not call the provider. No credentials, signed URLs, or raw API responses are included in this project.

```sh
npm run voice:plan
npm run voice:generate
npm run voice:mix
npm run render:voiced
node scripts/export-captions.mjs --voiced
python3 scripts/validate-voiced.py
python3 scripts/package.py --voiced
```

`voice:generate` validates cached file/content hashes and only calls Bailian for missing clips. Before any new provider request, follow the installed Bailian skill's current version/auth preflight. Source edits that invalidate a cache stop rather than overwrite an unmatched result. On Q's workstation, heavy jobs use the validated `agent-dev run -- ...` wrapper under workstation rules. If the base MP4 is missing in an independent source copy, `render:voiced` first renders the original visuals locally, then replaces its audio.

Full-length voice and mix: `public/audio-voiced-v2/narration.wav`, `soundtrack.wav`. Per-segment originals, canonical WAVs, aligned WAVs and normalization records remain in that directory. Text, plan, provider receipts and sample provenance are in `audio-voiced-v2/`. The narrated bilingual SRT is `out/cage-of-seven-plus-two-voiced-v2-bilingual.srt`.

## Verification and remaining checks

`out/voiced-v2-validation.json` records successful PCM/timing checks, all segment sample counts, unchanged original stems and overload samples, the exact half-second quiet interval, final 180-second format, complete strict audio/video decoding and loudness measurements. The film SHA-256 is `f6f7b34821e573223f27d5a66ff08dda01e550364a0fef0e502f1a551252d25b`.

Continuous human listening, subjective voice performance, pronunciation acceptance and final-device playback remain open. The user explicitly chose **local checks only**, so ASR is skipped and no narration audio was uploaded for recognition. `audio-voiced-v2/asr-status.json` records the decision and the earlier automatic-review block. `node scripts/check-voice-content.mjs prepare` builds a local 79.353-second voice review without a provider call. No ASR correctness or exact pronunciation claim is made.

The v2 source/audio archive is `out/cage-of-seven-plus-two-voiced-v2-project.zip`; its CRC and all included-file hashes are verified and recorded in `out/voiced-v2-package-manifest.json`. The full MP4 is delivered separately.
