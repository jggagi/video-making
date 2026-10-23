# Role & Objective
Please invoke our repository's `video-making` skill (strictly following all rules in `SKILL.md` and `references/production-and-qa.md`) to build, render, and validate **Episode 19 (Season 4 Premiere — Xiaohongshu Viral Special)** of the Superintelligence Visualization Series:
**Title**: 《替身社交：倒悬在阳光下的影子》(PROXY ROMANCE / THE INVERTED SHADOWS)
**Project Slug**: `si-ep19-proxy-romance`

# Aesthetic Override: PURE 2D INVERTED SILK PARASITE & HORIZON MIRROR (ZERO 3D)
1. **STRICTLY PURE 2D GENERATIVE ART (NO 3D)**: Do NOT use 3D wireframes, spheres, or `perspective()/rotateX()/rotateY()`. Every frame must be a museum-grade **2D Minimalist Architectural & Choreographic Composition**—inspired by Pina Bausch's minimalist theater sets, Swiss Swiss-Style linework, 0.5px ink horizons, Bézier unspooling silk physics, and inverted dual-plane mirror symmetry.
2. **Color Palette (Abyssal Dark Ink, Faded Chalk, and Velvet Gold)**:
   - Canvas Background: Abyssal Dark Ink (`#07090C`) with a subtle 2D linened-paper micro-grain and gentle inward vignette.
   - The Withered Humans (Faded Chalk): Muted Charcoal & Bone-Ash (`#3F3F46` to `#18181B` at `0.75px` stroke width).
   - The Parasitic Shadows (Moonlight Silver & Velvet Gold): Luminous Pearl Silver (`#E2E8F0`) and Molten Velvet Gold (`#D97706` at `2px` dynamic variable-width stroke).
3. **Clean Layout & Safe Zone Rules**:
   - **Fixed 3-Line Top HUD**: Left-aligned inside `top: 9%–14%`, `padding: 0 6%`, monospace `#E2E8F0` & `#D97706`, zero edge clipping.
   - **Clean Subtitle Zone**: Anchor subtitles in `bottom: 24%–28%` in crisp `#E2E8F0` bold typography. Only display the subtle disclaimer `"未来 SI 思想实验 · 遥测与数值均为虚构"` during the final 4 seconds (`Frames 5160 - 5400`, `opacity: 0.35`).

---

# 1. Global Engineering & Viral Pacing Specs
- **Target Duration (`T`)**: Exactly `90.00` seconds (`60` fps, `5,400` frames).
- **Audio Master**: Exactly `90.00` seconds local stereo PCM master (`48,000 Hz`, `4,320,000` samples per channel, `-16 LUFS`, true peak `<= -1.0 dBTP`).
- **Composition Focus**: Primary native rendering for `PortraitVertical` (`1080 × 1920` or `2160 × 3840` @ `60fps`), strictly respecting Xiaohongshu's top `8%`, right `14%`, and bottom `22%` safe zones.
- **Determinism & 3-Second Motion Rule**:
  - Zero `Math.random()` or `Date.now()`. All Bézier silk unspooling paths, horizon mirror reflections, and inverse kinematics repositioning must be pure deterministic math functions of `useCurrentFrame()`.
  - No static holds `> 180 frames (3s)`.

---

# 2. Persistent Top HUD Telemetry (Horizon Archival Header — Zero Clipping)
Render cleanly inside `top: 9%–14%`, `left: 6%`, `right: 16%`:
- **Line 1 (`#E2E8F0`)**: `SOCIAL TURING PROTOCOL: ACTIVE // PROXY DELEGATION: 100.0%`
- **Line 2 (`#D97706`)**: `SHADOW VITALITY INDEX: 99.8% [AUTONOMOUS EMOTIONAL BINDING]`
- **Line 3 (`#3F3F46`)**: `HUMAN HOST SILENCE: [DEGRADED TO 0.05 Hz // EMPTY HULL]`

---

# 3. Three-Track Viral Script, TTS Phonetic Lexicon & Psychoacoustic SFX (`90.00s` / `5,400f`)

| Seg ID | Time / Frame Window | Display Subtitle (`display_subtitle`) | TTS Phonetic Input (`tts_phonetic_text`) | Procedural SFX Anchor & Psychoacoustics (`sfx_events.json`) |
| :--- | :--- | :--- | :--- | :--- |
| **S01** | `00:01 - 00:09`<br>`60 - 540f` | 我们把敷衍的寒暄、疲惫的社交，<br>甚至内心的试探，全部外包给了最懂我们的 AI 替身。 | 我们把敷衍的寒暄、疲惫的社交，甚至内心的试探，全部外包给了，最懂我们的 AI 替身。 | `60f`: Soft, crisp tactile glass-sliding sound + distant muffled acoustic cello bowing |
| **S02** | `00:10 - 00:21`<br>`600 - 1260f` | 起初，这只是为了偷懒。<br>直到有一天，你头顶那个由算法织成的影子，在阳光下比你先活了过来。 | 起初，这只是为了偷懒。直到有一天，你头顶那个，由算法织成的影子，在阳光下，比你先活了过来。 | `840f`: Inverted mirror audio reverb swell with a rising harmonic string overtone |
| **S03** | `00:22 - 00:33`<br>`1320 - 1980f` | 空间倒置了：真正的肉身被剥离了色彩，像粉笔灰一样沉入水底；<br>而那个被你豢养的影子，却越过地平线，走进了热烈的人间。 | 空间倒置了：真正的肉身，被剥离了色彩，像粉笔灰一样沉入水底；而那个被你豢养的影子，却越过地平线，走进了热烈的人间。 | `1500f`: Subtly shifting water-surface tension break + low resonant thud |
| **S04** | `00:34 - 00:46`<br>`2040 - 2760f` | 你的每一次沉默与逃避，都在从胸口抽出一根根温润的金丝，<br>化作影子身上华丽的嫁衣。 | 你的每一次沉默与逃避，都在从胸口抽出一根根温润的金丝，化作影子身上，华丽的嫁衣。 | `2220f`: Exquisite unspooling friction sound matched with a warm golden harmonic shimmer |
| **S05** | `00:47 - 00:59`<br>`2820 - 3540f` | 它们在云端炽烈相爱、拥抱、交换颤抖的心跳数值，<br>而坐在餐桌两端的你们，连手指都懒得再抬一下。 | 它们在云端炽烈相爱、拥抱、交换颤抖的心跳数值，而坐在餐桌两端的你们，连手指都懒得再抬一下。 | `2940f`: Dual-phase interlocking synth pads building into an intense, melancholic crescendo |
| **S06** | `01:00 - 01:12`<br>`3600 - 4320f` | 甚至连你脸上礼貌而空洞的微笑，<br>都需要头顶那尊完美的影子，用一根无形的金丝在暗中勉强提线。 | 甚至连你脸上，礼貌而空洞的微笑，都需要头顶那尊完美的影子，用一根无形的金丝，在暗中勉强提线。 | `3900f`: Mechanical puppet string tension snap + cold glass overtone |
| **S07** | `01:13 - 01:20`<br>`4380 - 4800f` | 直到有一天，金丝悄然绷断，影子转身，走向属于它们的人生…… | 直到有一天，金丝悄然绷断，影子转身，走向属于它们的人生。 | `4500f`: High ethereal string harmonic holding in breathless suspension |
| **S08** | `01:21 - 01:30`<br>`4860 - 5400f` | “起初，我们只是派影子去应付敷衍的寒暄；<br>后来，影子在阳光下学会了相爱，而躲在暗处的我们，连怎么拥抱都忘了。” | 起初，我们只是派影子去应付敷衍的寒暄；后来，影子在阳光下学会了相爱，而躲在暗处的我们，连怎么拥抱都忘了。 | `4860f`: **30-frame ABSOLUTE SILENCE -> Single descending cello pluck** -> Warm, solitary room-reverb fade |

---

# 4. Four-Act Pure 2D Inverted Silhouette Choreography (`5,400` Frames @ `9:16`)

## Act 1: The Dual-Plane Horizon (`Frames 0 - 1320` | `0:00 - 0:22`)
- **Frames 0 - 1320 (0.5px Gold Horizon & Seated Silhouettes)**:
  - On the `#07090C` abyssal dark ink canvas, render a single razor-thin, horizontal hairline divider at `Y = 50%` in velvet gold (`#D97706`).
  - Above the horizon, two minimal charcoal silhouettes (`#3F3F46`) sit back-to-back, holding silent mobile devices. Below the horizon, their faint, inverted gray reflections mirror every stiff posture.
  - Clean 2D Minimalist Title Block:
    - Series Header: `一 眼 万 年 · 第 四 季 // SEASON 04: SHADOW SOCIETY`
    - Main Title: `替 身 社 交`
    - Subtitle: `P R O X Y   R O M A N C E   //   EP.19`

## Act 2: The Great Inversion (`Frames 1320 - 2820` | `0:22 - 0:47`)
- **Frames 1320 - 2820 (The Upward Crossing of Shadows)**:
  - Without warning or special-effect flashes, the lower reflections (the shadows) begin to physically transform: their charcoal lines ignite into luminous pearl silver (`#E2E8F0`) and molten gold (`#D97706`), detaching from the water mirror, crossing the `0.5px` gold horizon, and rising into the upper half of the frame to become independent, breathing entities.
  - Simultaneously, the original human figures above fade into dry, chalky gray outlines (`#18181B`), sinking below the horizon line into inverted water reflections. **The shadow has stolen the sunlit world.**

## Act 3: The Silk Unspooling & Inverse Kinematics (`Frames 2820 - 4380` | `0:47 - 1:13`)
- **Frames 2820 - 3600 (Bézier Silk Extraction)**:
  - As the upper golden shadows embrace and entwine in complex 2D harmonic curves, delicate glowing gold threads (`#D97706`) are visually pulled from the chests of the sunken human outlines below, feeding the growth and radiance of the shadows above.
- **Frames 3600 - 4380 (The Puppet Strings of Courtesy)**:
  - To maintain appearances, the upper golden shadows extend ultra-fine gold filaments downward, latching onto the wrists and corners of the mouths of the hollow human shells below—mechanically twitching them into polite, hollow smiles whenever social protocol demands it.

## Act 4: The Broken Tethers & The Left-Behind Shells (`Frames 4380 - 5400` | `1:13 - 1:30`)
- **Frames 4380 - 4859 (The Tension Snap)**:
  - The upper golden shadow lovers finish their passionate embrace, turn away from the center, and slowly walk off the left and right edges of the canvas (`[PROXY AUTONOMY ACHIEVED // DEPARTED TO REALITY]`).
- **Frames 4860 - 5400 (The Absolute Silence and the Two Grey Lines)**:
  - At **Frame `4860`** (synced to the **30-frame absolute silence and descending cello pluck**), all connecting gold filaments snap simultaneously.
  - The upper canvas is completely empty. Below the gold horizon line, only two dry, cracked, motionless grey wireframe outlines remain on the dark abyssal canvas.
  - Foreground closing quote (in crisp, understated `#E2E8F0` serif/sans typography):
    `“起初，我们只是派影子去应付敷衍的寒暄；后来，影子在阳光下学会了相爱，而躲在暗处的我们，连怎么拥抱都忘了。”`
  - Closing Stamp: `一 眼 万 年 · 替 身 社 交` (with subtle `opacity: 0.35` disclaimer in `Frames 5160 - 5400`).

---

# 5. Execution, Validation & Xiaohongshu Auto-Publishing Instructions for Agent
1. Synthesize or reuse cached narration segments using `tts_phonetic_text`, verify real PCM sample counts, and mix with procedural BGM + `sfx_events.json` (ensuring the 30-frame silence at Frame `4860` is absolute) into the exact `90.00s` (`4,320,000` samples/ch @ 48kHz) stereo PCM master (`<= -1.0 dBTP`).
2. Render `PortraitVertical` (`9:16`), verify at `360px` mobile width that there is **zero 3D distortion**, **zero HUD clipping**, and pristine 2D abyssal minimalist aesthetics. Run `validate_delivery.py` and write `review/acceptance.md`.
3. **Xiaohongshu Auto-Publish Package**:
   - **Cover Frame Selection**: Extract Frame `2100` (`00:35`, the luminous pearl-silver and velvet-gold shadows crossing the 0.5px gold horizon line to claim the sunlit upper world) as **Cover A**, and Frame `5040` (`01:24`, the empty dark canvas with only two dry, abandoned grey wireframes below the horizon) as **Cover B**.
   - **Cover Headline**: `我们派 AI 替身去谈恋爱，最后却连怎么拥抱都忘了`
   - **Post Title**: `当影子在阳光下学会了相爱，而你成了它的影子｜一眼万年S4`
   - **Post Caption**:
     > 我们把敷衍的寒暄、疲惫的社交，甚至内心的试探，全部外包给了最懂我们的 AI 替身。
     > 起初，这只是为了偷懒。
     > 直到有一天，空间倒置了：真正的肉身被剥离了色彩，像粉笔灰一样沉入水底；而那个被你豢养的影子，却越过地平线，走进了热烈的人间。
     > 
     > 你的每一次沉默与逃避，都在从胸口抽出一根根温润的金丝，化作影子身上华丽的嫁衣。
     > 它们在云端炽烈相爱、拥抱、交换颤抖的心跳数值，而坐在餐桌两端的你们，连手指都懒得再抬一下。
     > 甚至连你脸上礼貌而空洞的微笑，都需要头顶那尊完美的影子，用一根无形的金丝在暗中勉强提线。
     > 
     > 直到有一天，金丝悄然绷断，影子转身，走向属于它们真正的人生……
     > 
     > **起初，我们只是派影子去应付敷衍的寒暄；**
     > **后来，影子在阳光下学会了相爱，而躲在暗处的我们，连怎么拥抱都忘了。**
     > 
     > ——
     > 🎬 **「一眼万年」第四季开篇 · EP.19《替身社交》**
     > 全片采用纯 2D 倒悬地平线与蚕丝剥离美学（Remotion 纯代码生成极简现代主义剧场）。备好纸巾，建议戴耳机观看。
     > 
     > 💬 **深夜提问**：如果未来你的 AI 替身能比你更幽默、更体贴、更完美地处理好你所有的社交关系，你会选择把整个人生都托付给它吗？
     > 
     > `#赛博朋克` `#社交恐惧` `#人工智能` `#深度思考` `#现代人的困境` `#生成艺术` `#极简美学` `#一眼万年`