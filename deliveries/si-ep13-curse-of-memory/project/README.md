# EP13 project notes

This folder documents the production plan for 《无法遗忘的诅咒》, an exactly 90-second, 60 fps native 2160 × 3840 Xiaohongshu edition. The composition is a deterministic, flat 2D amber CRT/SVG treatment. It uses no 3D geometry or camera perspective.

## Project references

- Original creative brief and full source script: ../source/script.md
- Source subtitle/TTS segments: segments.json
- Production brief: brief.md
- Preserved display and phonetic script: adapted-script.md
- Integer-frame scene and audio event map: timeline.json
- Full source telemetry and compact display terms: telemetry-lexicon.json
- Xiaohongshu copy package: ../小红书/publish-package.md and publish-package.json

The frame schedule uses half-open intervals and totals exactly 5,400 frames. The provider manifest records Aliyun Bailian, effective model cosyvoice-v3-flash, longtian_v3 at rate 1.0. S01 active voice is measured on [48000, 472868), S02 begins at sample 480000, and their complete cue windows overlap by 13,483 samples without overlapping active speech. The generated master is stereo 48 kHz with 4,320,000 samples per channel; verify_project.py confirms its exact digital silence on [4860, 4890). The -16 LUFS target and -1.0 dBTP ceiling still require their separate measurement evidence.

The snap occupies [4859, 4860), silence occupies [4860, 4890), piano begins at frame 4890, and S08 voice begins at or after frame 4902. Phrase caption windows are recorded in audio-timing.json using character-weighted timing within the measured PCM spans; they are not word-aligned.

## Current evidence state

Source verification is recorded in review/source-check.json. Its source, timing, HUD, event and PCM checks pass; the overall report is INCOMPLETE because the final MP4 is absent. The checker only confirms video-file presence when it exists; encoded-media checks, frame review, full watch/listen and phone playback remain pending. No audience feedback has been collected or recorded. The Xiaohongshu copy package is prepared as copy only; this file does not state that the post was submitted, reviewed or published.
