# Role & Objective
Please invoke our repository's `video-making` skill (strictly following all rules in `SKILL.md` and `references/production-and-qa.md`) to build, render, and validate **Episode 11 (Xiaohongshu Viral Special)** of the Superintelligence Visualization Series under a brand new aesthetic direction:
**Title**: 《逆转的沙漏》(REVERSING THE HOURGLASS)
**Project Slug**: `si-ep11-kintsugi-ink`

# Aesthetic Override: Digital Kintsugi & Oriental Ink-Flow (画风 B)
Departing from our previous dark neon grid style, this episode adopts a museum-grade **Digital Kintsugi & Organic Ink-Wash** aesthetic:
- **Color Palette**: 
  - Background: Deep Xuan paper ink-black (`#0C0C0E`) with subtle organic fiber texture.
  - Aging / Entropy: Ink smoke gray (`#52525B`) and porcelain micro-crack lines (`#3F3F46`).
  - SI Intervention / Reversal: Molten Kintsugi gold (`#F59E0B` and `#FBBF24`) glowing with additive soft light.
- **Visual Metaphors**: 
  - Aging is represented as Voronoi porcelain micro-fractures and Curl-Noise ink dissipation across a 3D parametric Waddington surface.
  - Reversal is represented as glowing liquid gold flowing automatically along every fracture, sealing the cracks and reversing cellular descent.
  - The final scene features two porcelain-like particle silhouettes united inside an eternal gold-repaired Möbius ribbon ($\infty$).

# 1. Global Engineering & Viral Pacing Specs
- **Target Duration (`T`)**: Exactly `90.00` seconds (`60` fps, `5,400` frames).
- **Audio Master**: Exactly `90.00` seconds local stereo PCM master (`48,000 Hz`, `4,320,000` samples per channel, `-16 LUFS`, true peak `<= -1.0 dBTP`).
- **Composition Focus**: Primary native rendering for `PortraitVertical` (`1080 × 1920` or `2160 × 3840` @ `60fps`).
  - **Strict 9:16 Safe Zones**: Keep top `8%`, right `14%`, and bottom `22%` clear of critical ink flows, HUD text, and subtitles.
  - **Vertical HUD & Subtitles**: Stack clean fixed-width 3-line telemetry in `top: 9%–14%`. Anchor vertical subtitles in the `24%–28%` bottom golden reading band (max 2 lines, `<= 13` Chinese chars/line, effective font size `>= 15px` at `360px` mobile preview).
- **Determinism & 3-Second Motion Rule**:
  - Zero `Math.random()` or `Date.now()`. All ink dissipation, Kintsugi gold flow vectors, and Möbius rotations must be pure deterministic math functions of `useCurrentFrame()`.
  - No static holds `> 180 frames (3s)`.

---

# 2. Persistent Top HUD Telemetry (Fixed 3-Line Header, Zero Clipping, Zero Typos)
Render cleanly inside `top: 9%–14%`, `left: 6%`, `right: 16%`:
- **Line 1 (`#A1A1AA` -> `#F59E0B`)**:
  `BIOLOGICAL AGE INDEX: 20.0 YRS -> 78.5 YRS` *(reverses smoothly back to `22.0 YRS [KINTSUGI SEALED]` in Act 3–4)*
- **Line 2 (`#52525B`)**:
  `PORCELAIN FRACTURE ENTROPY: X%` *(rises from `0.0%` to `89.4%` in Act 1, sealed to `0.000%` in Act 3)*
- **Line 3 (`#F59E0B`)**:
  `KINTSUGI CELLULAR REPROGRAMMING: [MÖBIUS EQUILIBRIUM LOCKED]`

---

# 3. Three-Track Viral Script, TTS Phonetic Lexicon & Psychoacoustic SFX (`90.00s` / `5,400f`)

| Seg ID | Time / Frame Window | Display Subtitle (`display_subtitle`) | TTS Phonetic Input (`tts_phonetic_text`) | Procedural SFX Anchor & Psychoacoustics (`sfx_events.json`) |
| :--- | :--- | :--- | :--- | :--- |
| **S01** | `00:01 - 00:09`<br>`60 - 540f` | 人类把生老病死，当作不可违抗的天命；<br>但在超级智能眼里，衰老，只是一道写错的方程。 | 人类把生老病死，当作不可违抗的天命；但在超级智能眼里，衰老，只是一道，写错的方程。 | `60f`: Low-frequency ceramic resonance bowl hum + subtle ink brush stroke on paper |
| **S02** | `00:10 - 00:21`<br>`600 - 1260f` | 你的身体里有三百七十万亿颗细胞。<br>变老，不过是它们在表观遗传的山谷里，顺着时间滑向谷底。 | 你的身体里，有三百七十万亿颗细胞。变老，不过是它们，在表观遗传的山谷里，顺着时间，滑向谷底。 | `840f`: Curl-noise ink smoke dispersion sound + slow descending pitch |
| **S03** | `00:22 - 00:33`<br>`1320 - 1980f` | 人类吃药、手术，就像拿一把笨重的大锤去修手表：<br>用力太小挡不住衰老，用力太大，就会坠入癌变的深渊。 | 人类吃药、手术，就像拿一把笨重的大锤，去修手表：用力太小，挡不住衰老；用力太大，就会坠入，癌变的深渊。 | `1560f`: Clumsy heavy porcelain crack sound + sharp vermilion ink blot warning |
| **S04** | `00:34 - 00:46`<br>`2040 - 2760f` | 直到超级智能同时伸出十万维的分子探针，<br>在衰老与失控之间，算出了那条比发丝还窄一万倍的黄金山脊。 | 直到超级智能，同时伸出十万维的分子探针，在衰老与失控之间，算出了那条，比发丝还窄一万倍的，黄金山脊。 | `2280f`: High-precision liquid gold micro-nozzle hum + shimmering harmonic chord |
| **S05** | `00:47 - 00:59`<br>`2820 - 3540f` | 它不替你对抗时间，它直接擦除岁月留下的信息划痕。<br>三百七十万亿颗细胞同时接到指令，开始逆流而上。 | 它不替你对抗时间，它直接擦除，岁月留下的信息划痕。三百七十万亿颗细胞，同时接到指令，开始逆流而上。 | `2940f`: Magnificent upward ink-flow rush with glowing gold tracing lines |
| **S06** | `01:00 - 01:12`<br>`3600 - 4320f` | 白发退回青丝，布满裂纹的基因重归二十岁的山巅。<br>生命第一次挣脱了单向流淌的沙漏。 | 白发退回青丝，布满裂纹的基因，重归二十岁的山巅。生命第一次，挣脱了单向流淌的沙漏。 | `3900f`: Full-spectrum traditional Guqin string resonance fused with celestial synth |
| **S07** | `01:13 - 01:20`<br>`4380 - 4800f` | 当超级智能终于抹去了生老病死的刻度…… | 当超级智能，终于抹去了，生老病死的刻度。 | `4500f`: Suspended bell resonance fading into profound silence |
| **S08** | `01:21 - 01:30`<br>`4860 - 5400f` | “死亡不再是终点；只是那句人类说了几千年的‘白头偕老’，<br>从此成了再也无人能懂的远古词汇。” | 死亡不再是终点；只是那句，人类说了几千年的，白头偕老，从此成了，再也无人能懂的，远古词汇。 | `4860f`: **30-frame ABSOLUTE SILENCE -> Single warm gold droplet impact** -> Deep, poignant acoustic resolution |

---

# 4. Four-Act Kintsugi-Ink Visual Choreography (`5,400` Frames @ `9:16`)

## Act 1: The Porcelain Avalanche of Time (`Frames 0 - 1320` | `0:00 - 0:22`)
- **Frames 0 - 1320 (3D Xuan-Paper Waddington Surface & Voronoi Fractures)**:
  - Center vertical canvas renders a 3D Waddington potential mesh styled as **dark Xuan paper with ink contour lines**.
  - At the summit (`AGE: 20.0`), a glowing porcelain-white particle cluster resides. As time progresses, Voronoi micro-fractures spread across the surface, and dark ink smoke particles roll down into the `SENESCENCE BASIN`.
  - Title card overlays cleanly in sleek typography:
    - Main Title: `逆 转 的 沙 漏`
    - Subtitle: `D I G I T A L   K I N T S U G I   O F   T I M E`

## Act 2: The Porcelain Fix of Molten Gold (`Frames 1320 - 2820` | `0:22 - 0:47`)
- **Frames 1320 - 2820 (Kintsugi Healing Across the Saddle-Point)**:
  - Instead of crude hammers, glowing **molten Kintsugi gold (`#F59E0B`)** flows dynamically along every single porcelain fracture line on the terrain.
  - The gold seals the cracks and traces out an exquisite, glowing golden saddle-point path between aging and mutation, illuminating the dark Xuan paper surface like an ancient repaired masterpiece.

## Act 3: 37 Trillion Particles Flowing Upward (`Frames 2820 - 4380` | `0:47 - 1:13`)
- **Frames 2820 - 4380 (The Golden Reversal)**:
  - Guided by the Kintsugi gold veins, all ink-stained particles transform into radiant gold flakes and surge upward along the mountain ridges in unison.
  - The vertical telemetry updates rapidly: `BIOLOGICAL AGE: 78.5 -> 50.0 -> 22.0 YRS [KINTSUGI REPROGRAMMING COMPLETE]`.

## Act 4: The Golden Möbius & The Forgotten Vow (`Frames 4380 - 5400` | `1:13 - 1:30`)
- **Frames 4380 - 5400 (The Eternity of Gold)**:
  - At Frame `4860` (synced to the 30-frame absolute silence), the ink canvas fades to deep ink-black (`#0C0C0E`).
  - Two minimalist **porcelain-wireframe silhouettes** merge and orbit inside a glowing **Golden Möbius Strip ($\infty$)** that slowly rotates in the center.
  - Foreground closing quote:
    `“死亡不再是终点；只是那句人类说了几千年的‘白头偕老’，从此成了再也无人能懂的远古词汇。”`
  - Closing title card: `一眼万年 · 逆转的沙漏` (with low-opacity disclaimer during `Frames 5160 - 5400`).

---

# 5. Execution & Xiaohongshu Publishing Execution
1. Render the `PortraitVertical` master video using the Kintsugi-Ink style parameters into `delivery.json`.
2. Automatically select the cover frame from `01:24` (The golden Möbius ring enclosing porcelain wireframe silhouettes) and prepare the following Xiaohongshu post:
   - **Cover Title**: `当 AI 把人类寿命锁死在25岁，“白头偕老”成了远古词汇`
   - **Post Caption**: 
     > 人类把生老病死，当作不可违抗的天命；但在超级智能眼里，衰老，只是一场可以被数字金缮修复的瓷器裂纹。
     > 
     > 现代生物学发现，细胞变老不是基因坏了，而是岁月在表观遗传上留下了“信息划痕”。人类过去抗衰老，就像拿笨重的大锤修手表。直到超级智能伸出十万维探针，在衰老与失控之间算出了黄金窄脊——它不对抗时间，它用流动的赤金，直接擦除了岁月留下的划痕。
     > 
     > 370万亿颗细胞逆流而上，重归20岁的山巅。
     > 可当生命真正挣脱了倒计时的沙漏，最让人怔住的却是：
     > **那句人类说了几千年、最浪漫的誓言「白头偕老」，从此成了再也无人能懂的远古词汇。**
     > 
     > ——
     > 🎬 **「一眼万年」第二季 EP.11《逆转的沙漏》**（数字金缮水墨风特供版）
     > 💬 **深夜提问**：如果未来每个人都能永远停留在25岁，你觉得“白头偕老”的遗憾消失后，爱情会变得更珍贵，还是更廉价？
     > 
     > `#超级智能` `#抗衰老` `#白头偕老` `#数字金缮` `#科幻美学` `#数字艺术` `#深度思考` `#时间` `#一眼万年`
3. Execute validation and publish according to peak engagement hours.