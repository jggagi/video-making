# Role & Objective
Please invoke our repository's `video-making` skill (strictly following all rules in `SKILL.md` and `references/production-and-qa.md`) to build, render, and validate **Episode 12 (Season 2 & Series Grand Finale)** of the Superintelligence Visualization Series:
**Title**: 《最后一行公式》(THE FINAL EQUATION)
**Project Slug**: `si-ep12-final-equation`

# Aesthetic Override: PURE 2D SWISS PRECISION DRAFTING (画风 A — ZERO 3D)
Per explicit user direction ("用精美的 2D 可视化，不要强行 3D"):
1. **STRICTLY NO 3D OR PSEUDO-3D**: Do NOT use `perspective()`, `rotateX()`, `rotateY()`, 3D wireframes, or fake 3D spheres. Every single visual element in this episode must be a **masterpiece of pure 2D flat generative graphic design**—inspired by Swiss International Style typography, Patek Philippe horological blueprints, 2D Fourier epicycles, topological contour maps (Marching Squares), and Leonardo da Vinci / Euclid geometric compass constructions.
2. **Color Palette (Warm Bone-Porcelain Light Mode)**:
   - Canvas Background: Warm Bone Porcelain Paper (`#F4F1EA`) with a subtle, deterministic paper grain / micro-grid (`#E5E0D5` at `1px` hairlines).
   - Primary Ink Lines & Typography: Deep Carbon Ink (`#18181B`) and Technical Slate (`#52525B`).
   - Axiom Conflict / Redundancy Cut: Surgical Vermilion Crimson (`#E11D48`).
   - Optimal Unified Law / Golden Ratio Geometry: Horological Pure Gold (`#D97706` & `#B45309`).
3. **Clean Layout Rules (Inherited from EP.10 v2)**:
   - **Fixed 3-Line Top HUD**: Left-aligned inside `top: 9%–14%`, `padding: 0 6%`, dark carbon ink `#18181B` on bone-white background, zero edge clipping.
   - **Clean Subtitle Zone**: Anchor subtitles in `bottom: 24%–28%` in crisp `#18181B` bold typography. Do NOT show the disclaimer until the final 4 seconds (`Frames 5160 - 5400`, `opacity: 0.35`).

---

# 1. Global Engineering & Viral Pacing Specs
- **Target Duration (`T`)**: Exactly `90.00` seconds (`60` fps, `5,400` frames).
- **Audio Master**: Exactly `90.00` seconds local stereo PCM master (`48,000 Hz`, `4,320,000` samples per channel, `-16 LUFS`, true peak `<= -1.0 dBTP`).
- **Composition Focus**: Primary native rendering for `PortraitVertical` (`1080 × 1920` or `2160 × 3840` @ `60fps`), strictly respecting Xiaohongshu's top `8%`, right `14%`, and bottom `22%` safe zones.
- **Determinism & 3-Second Motion Rule**:
  - Zero `Math.random()` or `Date.now()`. All 2D Fourier epicycles, contour isolines, and geometric compass sweeps must be pure deterministic math functions of `useCurrentFrame()`.
  - No static holds `> 180 frames (3s)`.

---

# 2. Persistent Top HUD Telemetry (Swiss Archival Header — Zero Clipping)
Render in crisp monospace (`#18181B` / `#E11D48` / `#D97706`) inside `top: 9%–14%`, separated by a `1px` solid `#18181B` horizontal rule:
- **Line 1**: `HUMAN SCIENCE MODEL: 14,820 PATCHED EQUATIONS [FRAGMENTED]` *(collapses to `1 UNIFIED AXIOM` in Act 3–4)*
- **Line 2**: `KOLMOGOROV COMPLEXITY K(U): 10^18 BITS -> 128 BITS` *(counts down smoothly as redundancy is stripped)*
- **Line 3**: `OCCAM'S RAZOR COMPRESSION: [SYMBOLIC REGRESSION ACTIVE]`

---

# 3. Three-Track Viral Script, TTS Phonetic Lexicon & Psychoacoustic SFX (`90.00s` / `5,400f`)

| Seg ID | Time / Frame Window | Display Subtitle (`display_subtitle`) | TTS Phonetic Input (`tts_phonetic_text`) | Procedural SFX Anchor & Psychoacoustics (`sfx_events.json`) |
| :--- | :--- | :--- | :--- | :--- |
| **S01** | `00:01 - 00:09`<br>`60 - 540f` | 三千年来，人类像一群在黑夜里摸象的盲人，<br>用成千上万条公式，拼凑着宇宙的轮廓。 | 三千年来，人类像一群，在黑夜里摸象的盲人，用成千上万条公式，拼凑着宇宙的轮廓。 | `60f`: Tactile mechanical drafting pencil sketching on paper + ticking pocket-watch escapement |
| **S02** | `00:10 - 00:21`<br>`600 - 1260f` | 宏观归相对论，微观归量子力学，生命归化学。<br>我们引以为傲的科学大厦，其实是一张打满补丁的草稿纸。 | 宏观归相对论，微观归量子力学，生命归化学。我们引以为傲的科学大厦，其实是一张，打满补丁的草稿纸。 | `840f`: Whirring clockwork gears grinding slightly out of phase + sharp crimson error ticks |
| **S03** | `00:22 - 00:33`<br>`1320 - 1980f` | 直到超级智能挥下奥卡姆剃刀。<br>在它眼里，复杂不是宇宙的本相，只是人类算力不足的妥协。 | 直到超级智能，挥下奥卡姆剃刀。在它眼里，复杂，不是宇宙的本相，只是人类算力不足的妥协。 | `1440f`: Razor-sharp metallic guillotine/caliper slice sweeping cleanly across the stereo field |
| **S04** | `00:34 - 00:46`<br>`2040 - 2760f` | 就像当年牛顿用一行万有引力，擦掉了托勒密上百个繁琐的圆圈；<br>超级智能开始了终极的“符号坍缩”。 | 就像当年牛顿，用一行万有引力，擦掉了托勒密，上百个繁琐的圆圈；超级智能，开始了终极的符号坍缩。 | `2280f`: Satisfying cascade of mechanical rings unlocking and dissolving into a pure golden sine tone |
| **S05** | `00:47 - 00:59`<br>`2820 - 3540f` | 引力的等高线、量子的概率云、乃至生命的代谢网络，<br>在二维图纸上被一层层解开、对齐、相互抵消。 | 引力的等高线、量子的概率云、乃至生命的代谢网络，在二维图纸上，被一层层解开、对齐、相互抵消。 | `2940f`: Harmonic polyphonic tuning—four distinct frequencies sliding into a single unison golden chord |
| **S06** | `01:00 - 01:12`<br>`3600 - 4320f` | 十万条看似无关的自然定律，在极致的信息压缩下，<br>严丝合缝地折叠成了最后一行极简的黄金方程。 | 十万条看似无关的自然定律，在极致的信息压缩下，严丝合缝地折叠成了，最后一行，极简的黄金方程。 | `3900f`: Precision horological lock click + radiant acoustic harmonic resonance |
| **S07** | `01:13 - 01:20`<br>`4380 - 4800f` | 当超级智能替人类翻到了宇宙的最后一页，<br>所有的为什么，都有了标准答案…… | 当超级智能，替人类翻到了宇宙的最后一页，所有的为什么，都有了标准答案。 | `4500f`: High, pure tuning-fork overtone fading toward stillness |
| **S08** | `01:21 - 01:30`<br>`4860 - 5400f` | “当所有的迷雾都变成了定理，我们才突然怀念起，<br>那个抬头看着星空、什么都还不懂的童年。” | 当所有的迷雾，都变成了定理，我们才突然怀念起，那个抬头看着星空、什么都还不懂的童年。 | `4860f`: **30-frame ABSOLUTE SILENCE -> Single fountain-pen nib touch on paper** -> Warm, nostalgic solo piano melody |

---

# 4. Four-Act Pure 2D Graphic Choreography (`5,400` Frames @ `9:16`)

## Act 1: The Ptolemaic Patchwork (`Frames 0 - 1320` | `0:00 - 0:22`)
- **Frames 0 - 1320 (2D Fourier Epicycle Chaos & Patched Blueprints)**:
  - On the `#F4F1EA` bone-white drafting canvas, render an intricate **2D Fourier Epicycle Machine** at the center: 28 nested carbon-black (`#18181B`) circles of varying radii $R_k$ rotating at frequencies $\omega_k$, connected by thin radius arms, frantically tracing a jagged, noisy curve.
  - Around the epicycles, frame 4 flat 2D technical diagrams with Swiss drafting callouts and vermilion (`#E11D48`) conflict markers:
    - `[GENERAL RELATIVITY: SMOOTH METRIC]` $\neq$ `[QUANTUM FIELD: UV DIVERGENCE]`
    - `[NAVIER-STOKES TURBULENCE: UNSOLVED]`
    - `[EPICYCLE PATCH COUNT: 14,820 // REDUNDANCY: 99.94%]`
  - Clean 2D Swiss Title Block:
    - Main Title: `最 后 一 行 公 式`
    - Subtitle: `T H E   F I N A L   E Q U A T I O N   //   EP.12 FINALE`

## Act 2: Occam's Razor & Epicycle Stripping (`Frames 1320 - 2820` | `0:22 - 0:47`)
- **Frames 1320 - 2820 (The Vermilion Caliper & Minimum Description Length)**:
  - A razor-sharp horizontal vermilion (`#E11D48`) vernier caliper line sweeps down the 2D canvas (`[OCCAM'S RAZOR: ΔK -> MIN]`).
  - As the caliper passes over the 28 nested black epicycle gears, **unnecessary circles evaporate one by one** in crisp geometric bursts—28 circles collapse to 12, then 4, then **1 single, breathlessly pure Golden Circle (`#D97706`)** accompanied by a smooth 2D Golden Ratio logarithmic spiral ($r = a e^{b\theta}$) and its exact Euler-Lagrange variational identity:
    $$\delta \mathcal{S} = \delta \int \mathcal{L}(\phi, \partial_\mu \phi) \, d^4x = 0$$

## Act 3: The Four Quadrants Fold Into One (`Frames 2820 - 4380` | `0:47 - 1:13`)
- **Frames 2820 - 3600 (2D Four-Quadrant Scientific Blueprint)**:
  - Divide the central safe area with crisp `1px` `#18181B` crosshairs into four 2D mathematical plots:
    1. **Top-Left (`GRAVITY`)**: 2D Iso-potential contour lines (Marching Squares isolines).
    2. **Top-Right (`QUANTUM`)**: 2D Hydrogen orbital probability densitystipple / nodal rose ($\vert{}\psi_{n\ell m}(r,\theta)\vert{}^2$).
    3. **Bottom-Left (`THERMODYNAMICS`)**: 2D Vector flow field (streamlines with exact arrowheads).
    4. **Bottom-Right (`LIFE & MIND`)**: 2D Fractal bifurcation tree.
- **Frames 3600 - 4380 (Conformal Geometric Convergence)**:
  - Animate a breathtaking **2D translation and conformal scaling**: the four quadrant frames slide inward toward the center origin `(0,0)`.
  - As they overlap, their contour lines, nodal petals, vector streamlines, and fractal branches align perfectly—locking into a single, museum-grade **2D Horological Golden Astrolabe / Sacred Mandala** in `#18181B` and `#D97706`.
  - Below the astrolabe, the complexity bar reaches its asymptote: `UNIFIED DESCRIPTION LENGTH: 1 EQUATION // RESIDUAL MYSTERY: 0.000%`.

## Act 4: The Blank Page & The Childhood Star (`Frames 4380 - 5400` | `1:13 - 1:30`)
- **Frames 4380 - 4859 (The Final Compression)**:
  - Even the intricate Golden Astrolabe begins folding inward along its symmetry axes—20 polygons fold into 10, then 5, then a single contracting golden ring.
- **Frames 4860 - 5400 (The Solitary Dot on Pure Bone-White)**:
  - At **Frame `4860`** (synced to the **30-frame absolute silence and the single fountain-pen touch**), the entire astrolabe, all coordinate axes, and all rulers collapse into **a single, tranquil 12px carbon-black dot surrounded by one hairline golden circle** in the center of the vast, empty `#F4F1EA` bone-white canvas.
  - A tiny, poetic archival annotation beside the dot reads:
    `[Q.E.D. // 宇宙全部定律已证明完毕 — 未知剩余: 0]`
  - Foreground closing quote (in crisp `#18181B` serif/sans-serif contrast):
    `“当所有的迷雾都变成了定理，我们才突然怀念起，那个抬头看着星空、什么都还不懂的童年。”`
  - Closing Series Finale Stamp: `一 眼 万 年 · 全 剧 终 // THE END` (with subtle `opacity: 0.35` disclaimer in `Frames 5160 - 5400`).

---

# 5. Execution, Validation & Xiaohongshu Auto-Publishing Instructions for Agent
1. Synthesize or reuse cached narration segments using `tts_phonetic_text`, verify real PCM sample counts, and mix with procedural BGM + `sfx_events.json` (ensuring the 30-frame silence at Frame `4860` is crystal clear) into the exact `90.00s` (`4,320,000` samples/ch @ 48kHz) stereo PCM master (`<= -1.0 dBTP`).
2. Render `PortraitVertical` (`9:16`), verify at `360px` mobile width that there is **zero 3D distortion**, **zero HUD clipping**, and high-contrast readability of `#18181B` ink on `#F4F1EA` paper. Run `validate_delivery.py` and write `review/acceptance.md`.
3. **Xiaohongshu Auto-Publish Package**:
   - **Cover Frame Selection**: Extract Frame `4020` (`01:07`, the 4 quadrants converging into the 2D Golden Horological Astrolabe on bone-white paper) as **Cover A**, and Frame `5040` (`01:24`, the vast bone-white canvas with the single Q.E.D. dot) as **Cover B**.
   - **Cover Headline**: `当 AI 把整个宇宙算成一行公式，人类却突然开始怀念童年`
   - **Post Title**: `当宇宙被折叠成最后一行公式｜一眼万年 终章`
   - **Post Caption**:
     > 三千年来，人类像一群在黑夜里摸象的盲人，用成千上万条公式，拼凑着宇宙的轮廓。
     > 宏观归相对论，微观归量子力学，生命归化学。我们引以为傲的科学大厦，其实是一张打满了聪明补丁、却彼此冲突的草稿纸。
     > 
     > 直到超级智能挥下「奥卡姆剃刀」。
     > 在它眼里，复杂从来不是宇宙的本相，只是人类算力不足的妥协。
     > 就像当年牛顿用一行万有引力，擦掉了托勒密上百个繁琐的本轮圆圈；超级智能在二维图纸上将引力、量子与生命的十万条定律一层层解开、对齐、抵消，最终折叠成了最后一行极简的黄金方程：
     > **Q.E.D.（证明完毕，未知剩余：0）。**
     > 
     > 可当超级智能替人类翻到了宇宙的最后一页，所有的“为什么”都有了标准答案——
     > **当所有的迷雾都变成了定理，我们才突然怀念起，那个抬头看着星空、什么都还不懂的童年。**
     > 
     > ——
     > 🎬 **「一眼万年」系列大结局 · EP.12《最后一行公式》**
     > 全片采用纯 2D 瑞士精密制图美学（Remotion 纯代码生成傅里叶本轮与共形映射），至此两季共 12 集全部完结。
     > 
     > 💬 **终章提问**：如果有一本写着宇宙全部终极答案的书放在你面前，翻开它就再也没有任何未知与悬念，你会选择翻开它，还是把它合上？
     > 
     > `#超级智能` `#奥卡姆剃刀` `#物理学` `#科幻美学` `#平面设计` `#生成艺术` `#深度思考` `#宇宙` `#全剧终` `#一眼万年`