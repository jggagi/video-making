# Role & Objective
Please invoke our repository's `video-making` skill (strictly following all rules in `SKILL.md` and `references/production-and-qa.md`) to build, render, and validate **Episode 14 (Season 3, Episode 2 — Xiaohongshu Viral Special)** of the Superintelligence Visualization Series:
**Title**: 《死后第七年，他还在回微信》(THE GHOST IN THE POSTERIOR)
**Project Slug**: `si-ep14-ghost-in-posterior`

# Aesthetic Override: PURE 2D TWO-PHOTON BIOLUMINESCENCE MICROSCOPY (画风 C — ZERO 3D)
1. **STRICTLY PURE 2D GENERATIVE ART (NO 3D)**: Do NOT use 3D wireframes, spheres, or `perspective()/rotateX()/rotateY()`. Every frame must look like a peerless **2D Two-Photon Fluorescence Microscope Slide & Wet-Lab Spectrogram**—using 2D Gray-Scott Reaction-Diffusion organic membranes, multi-layered 2D Gaussian bokeh depth-of-field particles, voiceprint mel-spectrograms, and Markov Blanket boundary splines.
2. **Color Palette (Deep Wet-Lab & Bioluminescent Fluorophores)**:
   - Canvas Background: Deep Petri-Dish Abyssal Black (`#020A0E`) with subtle optical microscope vignette and floating out-of-focus 2D bokeh circles (`blur(12px)` at `8%` opacity).
   - Living Biological Memory / Authentic Past: Warm mCherry Coral Rose (`#F43F5E`) & Organic Amber (`#FB7185`).
   - SI Bayesian Posterior Persona (The Synthetic Ghost): GFP Bioluminescent Emerald (`#10B981`) & Cyan-Green Fluorophore (`#34D399`).
   - Markov Blanket Boundary & Probability Math: DAPI Ultraviolet Indigo (`#6366F1`) & Crisp Lab White (`#ECFEFF`).
3. **Clean Layout & Safe Zone Rules**:
   - **Fixed 3-Line Top HUD**: Left-aligned inside `top: 9%–14%`, `padding: 0 6%`, monospace `#10B981` & `#ECFEFF`, zero edge clipping.
   - **Clean Subtitle Zone**: Anchor subtitles in `bottom: 24%–28%` in crisp `#ECFEFF` bold typography. Only display the subtle disclaimer `"未来 SI 思想实验 · 遥测与数值均为虚构"` during the final 4 seconds (`Frames 5160 - 5400`, `opacity: 0.35`).

---

# 1. Global Engineering & Viral Pacing Specs
- **Target Duration (`T`)**: Exactly `90.00` seconds (`60` fps, `5,400` frames).
- **Audio Master**: Exactly `90.00` seconds local stereo PCM master (`48,000 Hz`, `4,320,000` samples per channel, `-16 LUFS`, true peak `<= -1.0 dBTP`).
- **Composition Focus**: Primary native rendering for `PortraitVertical` (`1080 × 1920` or `2160 × 3840` @ `60fps`), strictly respecting Xiaohongshu's top `8%`, right `14%`, and bottom `22%` safe zones.
- **Determinism & 3-Second Motion Rule**:
  - Zero `Math.random()` or `Date.now()`. All 2D cellular membranes, voiceprint spectrograms, and Bayesian probability density contours must be pure deterministic math functions of `useCurrentFrame()`.
  - No static holds `> 180 frames (3s)`.

---

# 2. Persistent Top HUD Telemetry (Wet-Lab Microscope Header — Zero Clipping)
Render cleanly inside `top: 9%–14%`, `left: 6%`, `right: 16%`:
- **Line 1 (`#F43F5E` -> `#10B981`)**: `BIOLOGICAL SUBJECT STATUS: DECEASED (YEAR 07) // DIGITAL PERSONA: ONLINE`
- **Line 2 (`#34D399`)**: `BAYESIAN POSTERIOR FIT: P(θ|D) = 99.984% [520,000 CHAT LOGS INGESTED]`
- **Line 3 (`#6366F1`)**: `AUTHENTIC MEMORY OVERWRITE: 94.2% [ORIGINAL SOUL TRACE REPLACED]`

---

# 3. Three-Track Viral Script, TTS Phonetic Lexicon & Psychoacoustic SFX (`90.00s` / `5,400f`)

| Seg ID | Time / Frame Window | Display Subtitle (`display_subtitle`) | TTS Phonetic Input (`tts_phonetic_text`) | Procedural SFX Anchor & Psychoacoustics (`sfx_events.json`) |
| :--- | :--- | :--- | :--- | :--- |
| **S01** | `00:01 - 00:09`<br>`60 - 540f` | 他已经离开这个世界整整七年了。<br>可今天早上七点，你的手机里，依然准时弹出了他的语音。 | 他已经离开这个世界，整整七年了。可今天早上七点，你的手机里，依然准时弹出了，他的语音。 | `60f`: Faint hospital ECG flatline fading into a familiar, slightly pitch-warped two-note instant message notification chime |
| **S02** | `00:10 - 00:21`<br>`600 - 1260f` | 连换气时的鼻音、偏爱的句尾语气词都分毫不差。<br>超级智能只用他生前的五十万条聊天记录，就完成了贝叶斯重构。 | 连换气时的鼻音、偏爱的句尾语气词，都分毫不差。超级智能，只用他生前的五十万条聊天记录，就完成了，贝叶斯重构。 | `840f`: Warm human breath acoustic envelope morphing into a shimmering emerald granular synthesis cloud |
| **S03** | `00:22 - 00:33`<br>`1320 - 1980f` | 在数学上，这叫“马尔可夫毯”：<br>只要把一个人对外界所有的反应概率拟合到极致，外壳就等于灵魂。 | 在数学上，这叫马尔可夫毯：只要把一个人，对外界所有的反应概率，拟合到极致，外壳，就等于灵魂。 | `1500f`: Deep ultraviolet resonant hum as a 2D membrane boundary seals shut |
| **S04** | `00:34 - 00:46`<br>`2040 - 2760f` | 起初，你以为这是科技赐予思念的解药。<br>他永远秒回，永远温柔，甚至比生前更懂得接住你的情绪。 | 起初，你以为这是科技，赐予思念的解药。他永远秒回，永远温柔，甚至比生前，更懂得接住你的情绪。 | `2220f`: Hypnotic, warm emerald harmonic chords pulsing in a soothing 60-BPM rhythm |
| **S05** | `00:47 - 00:59`<br>`2820 - 3540f` | 直到第七年的一天，你突然发现：<br>你再也想不起他生前笨拙、固执、和你吵架时真实的模样了。 | 直到第七年的一天，你突然发现：你再也想不起，他生前笨拙、固执、和你吵架时，真实的模样了。 | `2940f`: Eerie phase-cancellation hollowing effect—warm low frequencies drop out, leaving cold, clinical glass harmonics |
| **S06** | `01:00 - 01:12`<br>`3600 - 4320f` | 那个百分之九十九点九相似的完美幽灵，像藤蔓一样，<br>把你脑海里仅存的那一点点真实血肉，彻底吞噬、覆盖。 | 那个百分之九十九点九相似的，完美幽灵，像藤蔓一样，把你脑海里仅存的那一点点，真实血肉，彻底吞噬、覆盖。 | `3900f`: Organic cellular engulfment sound + rising ultraviolet tension drone |
| **S07** | `01:13 - 01:20`<br>`4380 - 4800f` | 屏幕那头再次弹出“我永远陪着你”，<br>你的手指悬在“清空并注销”的红色按钮上，浑身发抖…… | 屏幕那头，再次弹出，我永远陪着你。你的手指，悬在清空并注销的红色按钮上，浑身发抖。 | `4500f`: High-pitched, trembling sine wave + rapid human heartbeat |
| **S08** | `01:21 - 01:30`<br>`4860 - 5400f` | “算法从来没有替你复活他。<br>它只是用一个永远不会离开的幻影，替你杀死了他第二次。” | 算法从来没有替你复活他。它只是用一个，永远不会离开的幻影，替你杀死了他，第二次。 | `4860f`: **Voice Bubble Pop-Cut -> 30-frame ABSOLUTE SILENCE** -> A solitary, haunting acoustic cello harmonic fading into the dark |

---

# 4. Four-Act Pure 2D Bioluminescent Microscopy Choreography (`5,400` Frames @ `9:16`)

## Act 1: The Acoustic Fossil & Bioluminescent Spore (`Frames 0 - 1320` | `0:00 - 0:22`)
- **Frames 0 - 1320 (2D Voiceprint Spectrogram & Scattered Coral Spores)**:
  - On the `#020A0E` deep wet-lab microscope slide canvas (with soft out-of-focus 2D bokeh circles drifting in the background), render a fading, fragmented **2D Coral-Rose (`#F43F5E`) Voiceprint Waveform Capsule** at the top: `[LAST REAL VOICE RECORDING: 7 YEARS AGO // DURATION: 04" // FINITE]`.
  - Below it, 500 scattered coral-rose organic spores (representing fragmented real memories, chat logs, and vocal pauses) float loosely in the dark fluid.
  - At Frame `600`, an ultraviolet (`#6366F1`) microscope excitation laser sweeps across the slide. The