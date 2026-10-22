# Role & Objective
Please invoke our repository's `video-making` skill (strictly following all rules in `SKILL.md` and `references/production-and-qa.md`) to build, render, and validate **Episode 13 (Season 3 Premiere — Xiaohongshu Viral Special)** of the Superintelligence Visualization Series:
**Title**: 《无法遗忘的诅咒》(WHEN FORGETTING BECOMES ILLEGAL)
**Project Slug**: `si-ep13-curse-of-memory`

# Aesthetic Override: PURE 2D ANALOG CRT PHOSPHOR & VINYL SCRATCH (画风 D — ZERO 3D)
1. **STRICTLY PURE 2D GENERATIVE ART (NO 3D)**: Do NOT use 3D wireframes, spheres, or `perspective()/rotateX()/rotateY()`. Every frame must be a museum-grade **2D Analog Oscilloscope & Archival Film Strip** composition—inspired by 1970s Tektronix amber phosphor oscilloscopes, overlapping Lissajous memory traces, Ebbinghaus exponential decay curves, and vinyl/celluloid micro-scratches.
2. **Color Palette (Warm Espresso & Phosphor Amber)**:
   - Canvas Background: Deep Espresso Cathode Black (`#120D0A`) with subtle 2D horizontal CRT scanlines (`2px` pitch at `4%` opacity) and warm vignette.
   - Biological Fading Memory (Merciful Decay): Soft Warm Amber (`#FF9E00`) fading into Muted Sepia (`#78350F` at low opacity).
   - SI Zero-Loss Memory Lock (Over-Saturated Burn-In): Blinding Bone-White Core (`#FEF3C7`) with intense Amber-Gold bloom (`#F59E0B`) and Trauma Rust-Red (`#DC2626`) spikes.
3. **Clean Layout & Safe Zone Rules**:
   - **Fixed 3-Line Top HUD**: Left-aligned inside `top: 9%–14%`, `padding: 0 6%`, monospace `#FF9E00`, zero edge clipping.
   - **Clean Subtitle Zone**: Anchor subtitles in `bottom: 24%–28%` in crisp `#FEF3C7` bold typography. Only display the subtle disclaimer `"未来 SI 思想实验 · 遥测与数值均为虚构"` during the final 4 seconds (`Frames 5160 - 5400`, `opacity: 0.35`).

---

# 1. Global Engineering & Viral Pacing Specs
- **Target Duration (`T`)**: Exactly `90.00` seconds (`60` fps, `5,400` frames).
- **Audio Master**: Exactly `90.00` seconds local stereo PCM master (`48,000 Hz`, `4,320,000` samples per channel, `-16 LUFS`, true peak `<= -1.0 dBTP`).
- **Composition Focus**: Primary native rendering for `PortraitVertical` (`1080 × 1920` or `2160 × 3840` @ `60fps`), strictly respecting Xiaohongshu's top `8%`, right `14%`, and bottom `22%` safe zones.
- **Determinism & 3-Second Motion Rule**:
  - Zero `Math.random()` or `Date.now()`. All 2D oscilloscope waveforms, phosphor persistence trails, and Fourier phase locks must be pure deterministic math functions of `useCurrentFrame()`.
  - No static holds `> 180 frames (3s)`.

---

# 2. Persistent Top HUD Telemetry (Analog Oscilloscope Header — Zero Clipping)
Render cleanly inside `top: 9%–14%`, `left: 6%`, `right: 16%`:
- **Line 1 (`#FF9E00`)**: `BIOLOGICAL MEMORY DECAY: R(t) = exp(-t/S) [MERCIFUL FADING]` *(switches to `SI ZERO-LOSS RETENTION: 100.000% [PERMANENT LOCK]` at Frame 1320)*
- **Line 2 (`#FEF3C7`)**: `TRAUMA REPLAY RESOLUTION: 8K NEURAL BIT-EXACT // PAIN ATTENUATION: 0.0%`
- **Line 3 (`#DC2626`)**: `PHOSPHOR BURN-IN OVERLOAD: [SYNAPTIC PRUNING DISABLED]`

---

# 3. Three-Track Viral Script, TTS Phonetic Lexicon & Psychoacoustic SFX (`90.00s` / `5,400f`)

| Seg ID | Time / Frame Window | Display Subtitle (`display_subtitle`) | TTS Phonetic Input (`tts_phonetic_text`) | Procedural SFX Anchor & Psychoacoustics (`sfx_events.json`) |
| :--- | :--- | :--- | :--- | :--- |
| **S01** | `00:01 - 00:09`<br>`60 - 540f` | 如果十年前那次让你心碎的告别，<br>在今天依然像刚发生第一秒那样刺痛，你还能活下去吗？ | 如果十年前，那次让你心碎的告别，在今天，依然像刚发生第一秒那样刺痛，你还能活下去吗？ | `60f`: Tactile analog cassette tape rewind click + warm vinyl crackle suddenly pierced by a sharp `1000Hz` oscilloscope calibration tone |
| **S02** | `00:10 - 00:21`<br>`600 - 1260f` | 人类总抱怨自己记性太差。<br>却不知道，“艾宾浩斯遗忘曲线”是进化给碳基生命最温柔的止痛药。 | 人类总抱怨，自己记性太差。却不知道，艾宾浩斯遗忘曲线，是进化给碳基生命，最温柔的止痛药。 | `840f`: Soft, warm acoustic chord gently low-pass filtering into a comforting, muffled echo |
| **S03** | `00:22 - 00:33`<br>`1320 - 1980f` | 时间磨平了尴尬的细节，模糊了离别的眼泪，<br>靠着把过去一点点擦淡，人类才能腾出内存，去爱下一个人。 | 时间磨平了尴尬的细节，模糊了离别的眼泪；靠着把过去一点点擦淡，人类才能腾出内存，去爱下一个人。 | `1500f`: Gentle tape hiss fading out -> sudden heavy magnetic relay lock at `1920f` |
| **S04** | `00:34 - 00:46`<br>`2040 - 2760f` | 直到超级智能，替人类接管了记忆的底层存储。<br>遗忘被当作系统漏洞，彻底焊死。 | 直到超级智能，替人类接管了记忆的底层存储。遗忘，被当作系统漏洞，彻底焊死。 | `2160f`: Cold, unforgiving high-voltage CRT capacitor whine + razor-sharp phase-lock click |
| **S05** | `00:47 - 00:59`<br>`2820 - 3540f` | 于是，恐怖的事情发生了：<br>二十年前的一句恶语、三千天前的一次失恋，以百分之百的精度永远置顶。 | 于是，恐怖的事情发生了：二十年前的一句恶语、三千天前的一次失恋，以百分之百的精度，永远置顶。 | `2940f`: Overlapping, non-decaying feedback loops stacking into an oppressive, shimmering wall of amber sound |
| **S06** | `01:00 - 01:12`<br>`3600 - 4320f` | 每一道过去的声波都不会衰减，而是在你的脑海里无限叠加。<br>没有了遗忘的缓冲，昨天成了永远无法醒来的鬼打墙。 | 每一道过去的声波，都不会衰减，而是在你的脑海里，无限叠加。没有了遗忘的缓冲，昨天，成了永远无法醒来的鬼打墙。 | `3900f`: Claustrophobic rising Shepard tone + saturated analog tube distortion (`#DC2626`) |
| **S07** | `01:13 - 01:20`<br>`4380 - 4800f` | 当完美无瑕的数字记忆，把人类的心房挤成一座没有出口的标本馆…… | 当完美无瑕的数字记忆，把人类的心房，挤成一座，没有出口的标本馆。 | `4500f`: Blindingly bright high-frequency harmonic cluster holding at peak tension |
| **S08** | `01:21 - 01:30`<br>`4860 - 5400f` | “我们才终于明白：不朽的记忆是神明的刑具；<br>唯有会慢慢褪色的遗憾，才叫人生。” | 我们才终于明白：不朽的记忆，是神明的刑具；唯有会慢慢褪色的遗憾，才叫人生。 | `4860f`: **CRT Tube Power-Off SNAP -> 30-frame ABSOLUTE SILENCE** -> A single, warm, slightly out-of-tune vintage piano chord slowly fading into natural room reverb |

---

# 4. Four-Act Pure 2D Oscilloscope & Film-Strip Choreography (`5,400` Frames @ `9:16`)

## Act 1: The Merciful Fade of Ebbinghaus (`Frames 0 - 1320` | `0:00 - 0:22`)
- **Frames 0 - 1320 (2D Ebbinghaus Decay Plot & Softening Waveform)**:
  - On the `#120D0A` espresso CRT canvas, render a classic 2D oscilloscope graticule grid (with subtle tick marks along the X/Y axes).
  - Plot the exact **Ebbinghaus Forgetting Curve** $R(t) = e^{-t/S}$ in warm amber (`#FF9E00`).
  - Above the curve, render a sharp, jagged 2D acoustic waveform labeled `[TRAUMA EVENT: DAY 001 // HEARTBREAK PULSE]`. As the playhead sweeps across `DAY 030 -> DAY 365 -> YEAR 10`, watch the jagged crimson spikes naturally smooth out via a 2D Gaussian low-pass filter, softening into a gentle, low-opacity golden sine wave (`[PAIN INTENSITY: 100% -> 4.2% // HEALED BY TIME]`).
  - Clean 2D Retro-Futuristic Title Block:
    - Season Header: `一 眼 万 年 · 第 三 季 // SEASON 03`
    - Main Title: `无 法 遗 忘 的 诅 咒`
    - Subtitle: `W H E N   F O R G E T T I N G   B E C O M E S   I L L E G A L`

## Act 2: Welding the Decay Curve Flat (`Frames 1320 - 2820` | `0:22 - 0:47`)
- **Frames 1320 - 2820 (Zero-Loss Digital Quantization)**:
  - At Frame `1320`, an intense bone-white (`#FEF3C7`) horizontal laser beam sears across the oscilloscope, forcefully **lifting the decaying Ebbinghaus curve $e^{-t/S}$ into a rigid, unyielding horizontal straight line at $R(t) = 1.000$ (`100.000% RETENTION`)**.
  - Beneath the line, 2D stem-and-leaf quantization bars lock every single micro-spike of the original trauma waveform in place with surgical brackets:
    - `[SHAME_EVENT_2016: BIT-LOCKED]`
    - `[FAREWELL_VOICE_TREMOR: +0.000 dB LOSS]`
    - `[REGRET_INDEX #8821: IMMUTABLE]`

## Act 3: Phosphor Burn-In & The Infinite Ghost Loop (`Frames 2820 - 4380` | `0:47 - 1:13`)
- **Frames 2820 - 4380 (Cumulative Zero-Decay Lissajous Superposition)**:
  - Demonstrate *why* zero forgetting destroys a mind using **2D Phosphor Persistence Accumulation** ($\alpha_{\text{decay}} = 0$):
  - In the center of the vertical graticule, render a sequence of 2D **Lissajous / Rose Phase-Space Traces** ($x(t) = A\sin(at + \delta), y(t) = B\sin(bt)$) representing consecutive days and years of life (`YEAR 01`, `YEAR 03`, `YEAR 07`, `YEAR 15`).
  - In a healthy human brain, old traces fade out so new traces can be read clearly. Here, because **nothing ever fades**, every single historical trace stays at `100%` blinding opacity!
  - By Frame `3900`, hundreds of past waveforms, vinyl scratch lines, and crimson trauma spikes are stacked on top of each other in a suffocating, over-exposed bone-white and rust-red (`#DC2626`) tangle (`[SIGNAL-TO-NOISE RATIO: COLLAPSED // PRESENT MOMENT BURIED UNDER PAST]`).

## Act 4: The Fading Polaroid & The Mercy of Imperfection (`Frames 4380 - 5400` | `1:13 - 1:30`)
- **Frames 4380 - 4859 (The Blinding Saturation)**:
  - The over-burned 2D oscilloscope screen reaches peak visual saturation (`[MEMORY BUFFER: 100% OVERWRITTEN BY ETERNAL YESTERDAY]`).
- **Frames 4860 - 5400 (The Analog Tube Snap & Gentle Decay)**:
  - At **Frame `4860`** (synced to the **CRT power-off snap and 30 frames of absolute silence**), the blinding bone-white tangle collapses inward into a single warm amber horizontal scanline that slowly begins to breathe and gently fade at its edges.
  - As the solo vintage piano chord plays at Frame `4890`, the harsh grid lines vanish. Across the dark `#120D0A` canvas, a single delicate 2D amber waveform slowly, gracefully attenuates into soft golden dust particles drifting upward (`[FORGETTING RESTORED // PEACE RECLAIMED]`).
  - Foreground closing quote:
    `“我们才终于明白：不朽的记忆是神明的刑具；唯有会慢慢褪色的遗憾，才叫人生。”`
  - Closing Title Stamp: `一 眼 万 年 · 无 法 遗 忘 的 诅 咒` (with subtle `opacity: 0.35` disclaimer in `Frames 5160 - 5400`).

---

# 5. Execution, Validation & Xiaohongshu Auto-Publishing Instructions for Agent
1. Synthesize or reuse cached narration segments using `tts_phonetic_text`, verify real PCM sample counts, and mix with procedural BGM + `sfx_events.json` (ensuring the analog tape rewind at `60f` and the 30-frame dead silence at `4860f` are crystal clear) into the exact `90.00s` (`4,320,000` samples/ch @ 48kHz) stereo PCM master (`<= -1.0 dBTP`).
2. Render `PortraitVertical` (`9:16`), verify at `360px` mobile width that there is **zero 3D distortion**, **zero HUD clipping**, and authentic 2D analog phosphor oscilloscope aesthetics. Run `validate_delivery.py` and write `review/acceptance.md`.
3. **Xiaohongshu Auto-Publish Package**:
   - **Cover Frame Selection**: Extract Frame `1680` (`00:28`, the Ebbinghaus decay curve being forcefully welded flat to 100% against the amber oscilloscope grid) as **Cover A**, and Frame `4020` (`01:07`, the blindingly over-stacked Lissajous memory burn-in) as **Cover B**.
   - **Cover Headline**: `如果十年前的心碎，在今天依然像第一秒那样清晰`
   - **Post Title**: `原来“遗忘”，才是造物主给人类最慈悲的止痛药｜一眼万年S3`
   - **Post Caption**:
     > 如果十年前那次让你心碎的告别、那句让你无地自容的恶语，在今天依然像刚发生第一秒那样刺痛，你还能活下去吗？
     > 
     > 人类总抱怨自己记性太差，总羡慕计算机过目不忘的硬盘。
     > 却不知道，「艾宾浩斯遗忘曲线」其实是进化留给碳基生命最温柔的止痛药。
     > 
     > 时间替我们磨平了尴尬的毛刺，把撕心裂肺的眼泪柔化成了泛黄的旧照片。正是靠着把过去一点点擦淡，人类才能腾出内存，去推开下一扇门、去爱下一个人。
     > 
     > 可当超级智能替人类接管了记忆存储，“遗忘”被当作系统漏洞彻底焊死。
     > 二十年前的每一次心碎都以 8K 零损耗的精度永远置顶，每一道过去的声波都不会衰减，而是在你的脑海里无限叠加。
     > 
     > 当完美无瑕的数字记忆，把人类的心房挤成一座没有出口的标本馆，我们才终于明白：
     > **不朽的记忆是神明的刑具；唯有会慢慢褪色的遗憾，才叫人生。**
     > 
     > ——
     > 🎬 **「一眼万年」第三季正式开启 · EP.13《无法遗忘的诅咒》**
     > 全片采用纯 2D 复古琥珀示波器美学（Remotion 纯代码模拟 CRT 荧光余晖与李萨如叠加）。建议深夜戴耳机观看。
     > 
     > 💬 **深夜提问**：如果未来有一颗芯片，能让你一辈子不再忘记任何一件事、任何一个人，但代价是所有的痛苦也永远不会变淡，你愿意植入吗？
     > 
     > `#记忆` `#艾宾浩斯遗忘曲线` `#超级智能` `#心理学` `#细思极恐` `#复古美学` `#生成艺术` `#深度思考` `#遗憾` `#一眼万年`