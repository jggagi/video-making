# EP13 adapted script

This edition preserves the source display subtitles and TTS phonetic input verbatim, in source segment order. The half-open segment windows below are the authored source windows. Measured phrase captions and their frame ranges are in project/audio-timing.json; their character-weighted timing follows active PCM spans and is not word-level synchronization.

| Segment | Frame window | Display subtitle | TTS phonetic input | Source effect cue |
| --- | --- | --- | --- | --- |
| S01 | [60, 540) | 如果十年前那次让你心碎的告别，<br>在今天依然像刚发生第一秒那样刺痛，你还能活下去吗？ | 如果十年前，那次让你心碎的告别，在今天，依然像刚发生第一秒那样刺痛，你还能活下去吗？ | Frame 60: tactile cassette rewind click and warm vinyl crackle, pierced by a sharp 1000 Hz calibration tone. |
| S02 | [600, 1260) | 人类总抱怨自己记性太差。<br>却不知道，“艾宾浩斯遗忘曲线”是进化给碳基生命最温柔的止痛药。 | 人类总抱怨，自己记性太差。却不知道，艾宾浩斯遗忘曲线，是进化给碳基生命，最温柔的止痛药。 | Frame 840: soft warm acoustic chord gently low-pass filtering into a comforting, muffled echo. |
| S03 | [1320, 1980) | 时间磨平了尴尬的细节，模糊了离别的眼泪，<br>靠着把过去一点点擦淡，人类才能腾出内存，去爱下一个人。 | 时间磨平了尴尬的细节，模糊了离别的眼泪；靠着把过去一点点擦淡，人类才能腾出内存，去爱下一个人。 | Frame 1500: gentle tape hiss fades; magnetic relay locks at frame 1920. |
| S04 | [2040, 2760) | 直到超级智能，替人类接管了记忆的底层存储。<br>遗忘被当作系统漏洞，彻底焊死。 | 直到超级智能，替人类接管了记忆的底层存储。遗忘，被当作系统漏洞，彻底焊死。 | Frame 2160: cold high-voltage CRT capacitor whine and sharp phase-lock click. |
| S05 | [2820, 3540) | 于是，恐怖的事情发生了：<br>二十年前的一句恶语、三千天前的一次失恋，以百分之百的精度永远置顶。 | 于是，恐怖的事情发生了：二十年前的一句恶语、三千天前的一次失恋，以百分之百的精度，永远置顶。 | Frame 2940: overlapping, non-decaying feedback loops build into an oppressive amber sound wall. |
| S06 | [3600, 4320) | 每一道过去的声波都不会衰减，而是在你的脑海里无限叠加。<br>没有了遗忘的缓冲，昨天成了永远无法醒来的鬼打墙。 | 每一道过去的声波，都不会衰减，而是在你的脑海里，无限叠加。没有了遗忘的缓冲，昨天，成了永远无法醒来的鬼打墙。 | Frame 3900: claustrophobic rising Shepard tone and saturated analog tube distortion. |
| S07 | [4380, 4800) | 当完美无瑕的数字记忆，把人类的心房挤成一座没有出口的标本馆…… | 当完美无瑕的数字记忆，把人类的心房，挤成一座，没有出口的标本馆。 | Frame 4500: bright high-frequency harmonic cluster reaches peak tension. |
| S08 | [4860, 5400) | “我们才终于明白：不朽的记忆是神明的刑具；<br>唯有会慢慢褪色的遗憾，才叫人生。” | 我们才终于明白：不朽的记忆，是神明的刑具；唯有会慢慢褪色的遗憾，才叫人生。 | Snap in [4859, 4860); absolute silence [4860, 4890); warm vintage piano begins at frame 4890. S08 narration begins at or after frame 4902. |

## Approved measured timing and TTS

- The source-authored S01 window remains [60, 540). The accepted playback preserves that authored entry and the complete natural-rate cue: cue samples [37571, 483011), active voice samples [48000, 472868), or approximately 1.000–9.8514167 seconds. Its caption window ends at frame 592.
- S02 active voice begins at sample 480000 (10 seconds), frame 600. The complete S01 and S02 cue intervals overlap by 13,483 samples (0.2808958 seconds); their measured active voice intervals do not overlap. No speech is cropped or accelerated.
- The provider manifest reports Aliyun Bailian, effective model cosyvoice-v3-flash, longtian_v3, rate 1.0. The existing audio-timing-overrides.json contains the approved S01 cue start and caption end; it is owned and maintained outside this document update.
- Phrase captions use character-weighted timing within measured PCM spans. The resulting windows are estimates, not ASR or forced word alignment.

## Source and performance notes

- Source script: source/script.md. Source segment data: project/segments.json.
- Preserve Chinese punctuation, wording, line breaks and the display/TTS distinction shown above.
- The final quotation is revealed progressively in readable phrase-sized units. Keep each unit within its approved measured caption window in project/audio-timing.json; do not infer timing from character count. The authored S08 segment window remains the source reference.
- S08 display may begin over the designed silence, while its voice must not begin before frame 4902. The silence remains absolute for all tracks on [4860, 4890).
- Frame 1320 is both the S03 boundary and the biological-to-SI retention transition.
- The source's full telemetry labels and their compact visible forms are paired in telemetry-lexicon.json.
