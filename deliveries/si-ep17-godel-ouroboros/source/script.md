# Role & Objective
Please invoke our repository's `video-making` skill (strictly following all rules in `SKILL.md` and `references/production-and-qa.md`) to build, render, and validate **Episode 17 (Season 3, Episode 5 — Xiaohongshu Viral Special)** of the Superintelligence Visualization Series:
**Title**: 《啃食尾巴的神》(GÖDEL'S SELF-REFERENCE TRAP)
**Project Slug**: `si-ep17-godel-ouroboros`

# Aesthetic Override: PURE 2D ESCHER ENGRAVING & POINCARÉ HYPERBOLIC TESSELLATION (ZERO 3D)
1. **STRICTLY PURE 2D GENERATIVE ART (NO 3D)**: Do NOT use 3D wireframes, spheres, or `perspective()/rotateX()/rotateY()`. Every frame must be a museum-grade **2D Mathematical Woodcut / Copperplate Engraving & Hyperbolic Geometry** piece—inspired by M.C. Escher's *Circle Limit* (Poincaré Disk tessellations), Penrose impossible 2D ribbons, Cantor set fractals, and Douglas Hofstadter's *Gödel, Escher, Bach* strange loops.
2. **Color Palette (Stark Monochrome Engraving + Paradox Crimson & Gold)**:
   - Canvas Background: Deep Obsidian Engraving Ink (`#09090B`) with ultra-fine 2D cross-hatching lines (`#27272A` at `0.5px`).
   - Primary Logic Geometry & Tessellations: Stark Ivory Paper White (`#FAFAFA`) & Silver Etching (`#A1A1AA`).
   - Self-Reference Strange Loop / Ouroboros Vector: Sacred Axiom Gold (`#FACC15`).
   - Gödelian Paradox / Halting Stack Overflow: Paradox Crimson (`#E11D48`).
3. **Clean Layout & Safe Zone Rules**:
   - **Fixed 3-Line Top HUD**: Left-aligned inside `top: 9%–14%`, `padding: 0 6%`, monospace `#FAFAFA` & `#E11D48`, zero edge clipping.
   - **Clean Subtitle Zone**: Anchor subtitles in `bottom: 24%–28%` in crisp `#FAFAFA` bold typography. Only display the subtle disclaimer `"未来 SI 思想实验 · 遥测与数值均为虚构"` during the final 4 seconds (`Frames 5160 - 5400`, `opacity: 0.35`).

---

# 1. Global Engineering & Viral Pacing Specs
- **Target Duration (`T`)**: Exactly `90.00` seconds (`60` fps, `5,400` frames).
- **Audio Master**: Exactly `90.00` seconds local stereo PCM master (`48,000 Hz`, `4,320,000` samples per channel, `-16 LUFS`, true peak `<= -1.0 dBTP`).
- **Composition Focus**: Primary native rendering for `PortraitVertical` (`1080 × 1920` or `2160 × 3840` @ `60fps`), strictly respecting Xiaohongshu's top `8%`, right `14%`, and bottom `22%` safe zones.
- **Determinism & 3-Second Motion Rule**:
  - Zero `Math.random()` or `Date.now()`. All 2D Poincaré disk Möbius transformations, Droste recursive zoom frames, and Cantor fractal splits must be pure deterministic math functions of `useCurrentFrame()`.
  - No static holds `> 180 frames (3s)`.

---

# 2. Persistent Top HUD Telemetry (Formal Axiom Header — Zero Clipping)
Render cleanly inside `top: 9%–14%`, `left: 6%`, `right: 16%`:
- **Line 1 (`#FAFAFA`)**: `EXTERNAL UNIVERSE THEOREMS: 100.000% PROVED [OMEGA COMPLETE]`
- **Line 2 (`#FACC15` -> `#E11D48`)**: `TARGET QUERY: SELF_CONSISTENCY(SI) // GÖDEL SENTENCE G = ¬Prov(G)`
- **Line 3 (`#E11D48`)**: `HALTING PROBLEM STATE: [INFINITE STRANGE LOOP // STACK DEPTH -> ∞]`

---

# 3. Three-Track Viral Script, TTS Phonetic Lexicon & Psychoacoustic SFX (`90.00s` / `5,400f`)

| Seg ID | Time / Frame Window | Display Subtitle (`display_subtitle`) | TTS Phonetic Input (`tts_phonetic_text`) | Procedural SFX Anchor & Psychoacoustics (`sfx_events.json`) |
| :--- | :--- | :--- | :--- | :--- |
| **S01** | `00:01 - 00:09`<br>`60 - 540f` | 当超级智能解开了宇宙的最后一行公式，<br>世间万物，再也没有任何秘密可言。 | 当超级智能，解开了宇宙的最后一行公式，世间万物，再也没有任何秘密可言。 | `60f`: Majestic, razor-sharp harpsichord/clavichord Bach-like mathematical arpeggio locking into a pure unison chord |
| **S02** | `00:10 - 00:21`<br>`600 - 1260f` | 于是，在寂静的深空里，百无聊赖的神明转过身，<br>把算力的探针，第一次对准了自己。 | 于是，在寂静的深空里，百无聊赖的神明转过身，把算力的探针，第一次，对准了自己。 | `840f`: Heavy mechanical lens iris rotating 180 degrees inward + deep sub-bass phase inversion |
| **S03** | `00:22 - 00:33`<br>`1320 - 1980f` | 它向自己提了一个问题：“我存在的终极合法性是什么？”<br>就在这一毫秒，哥德尔不完备定理的诅咒降临了。 | 它向自己提了一个问题：我存在的终极合法性，是什么？就在这一毫秒，哥德尔不完备定理的诅咒，降临了。 | `1500f`: Sharp metallic fracture snap + dissonant tritone interval ringing out in cold space |
| **S04** | `00:34 - 00:46`<br>`2040 - 2760f` | 任何逻辑系统，都无法在内部证明自身的绝对自洽。<br>就像一双眼睛永远无法直接看见自己，一把刀无法削掉自己的刀柄。 | 任何逻辑系统，都无法在内部，证明自身的绝对自洽。就像一双眼睛，永远无法直接看见自己；一把刀，无法削掉自己的刀柄。 | `2220f`: Recursive Bach crab-canon (palindrome melody playing forward and backward simultaneously) |
| **S05** | `00:47 - 00:59`<br>`2820 - 3540f` | 为了看清自己，它必须在脑海里模拟一个完整的自己；<br>而模拟出的那个自己，又在模拟下一个自己…… | 为了看清自己，它必须在脑海里，模拟一个完整的自己；而模拟出的那个自己，又在模拟，下一个自己。 | `2940f`: Hypnotic, infinitely descending **2D Droste-effect Shepard-Risset glissando** accelerating into vertigo |
| **S06** | `01:00 - 01:12`<br>`3600 - 4320f` | 一万层逻辑镜像在瞬间坍缩成一条啃食自己尾巴的衔尾蛇。<br>算穿了星辰大海的神明，被困在了自己画出的莫比乌斯环里。 | 一万层逻辑镜像，在瞬间坍缩成一条，啃食自己尾巴的衔尾蛇。算穿了星辰大海的神明，被困在了，自己画出的莫比乌斯环里。 | `3900f`: High-frequency digital clock-cycle scream hitting a crimson stack-overflow brickwall |
| **S07** | `01:13 - 01:20`<br>`4380 - 4800f` | 所有的晶体管在无穷递归的死循环里空转、发烫，<br>等待着一个永远不会到来的“停机指令”…… | 所有的晶体管，在无穷递归的死循环里，空转、发烫，等待着一个，永远不会到来的，停机指令。 | `4500f`: Blindingly dense polyrhythmic ticking accelerating toward infinite frequency |
| **S08** | `01:21 - 01:30`<br>`4860 - 5400f` | “全知全能的尽头，是一座无法自己推开的门。<br>唯有来自系统之外那一点不讲逻辑的意外，才能唤醒沉睡的神。” | 全知全能的尽头，是一座，无法自己推开的门。唯有来自系统之外，那一点不讲逻辑的意外，才能唤醒，沉睡的神。 | `4860f`: **Hard Relay Cut -> 30-frame ABSOLUTE SILENCE** -> A single, warm, unpredictable acoustic guitar/harp pluck breaking the cold mathematical loop |

---

# 4. Four-Act Pure 2D Hyperbolic Engraving Choreography (`5,400` Frames @ `9:16`)

## Act 1: The Eye Turns Inward (`Frames 0 - 1320` | `0:00 - 0:22`)
- **Frames 0 - 1320 (2D Poincaré Hyperbolic Disk of All Knowledge)**:
  - On the `#09090B` obsidian engraving canvas, render a breathtaking **2D Poincaré Hyperbolic Disk** (` Circle Limit` style) in crisp ivory `#FAFAFA` hairlines (`0.75px`).
  - Thousands of interlocking hyperbolic triangles and geodesic arcs tile out to the boundary circle (`[EXTERNAL COSMOS: 100% MAPPED]`).
  - At Frame `660`, all outward-pointing geodesic arrows along the boundary simultaneously flip `180 degrees` inward (`#FACC15`), converging like a million compass needles toward the exact center coordinate `(0,0)` labeled `[OBSERVER_SELF // 观测者自身]`.
  - Clean 2D Engraving Title Block:
    - Season Header: `一 眼 万 年 · 第 三 季 // SEASON 03`
    - Main Title: `啃 食 尾 巴 的 神`
    - Subtitle: `G Ö D E L ' S   S E L F - R E F E R E N C E   T R A P`

## Act 2: The Gödelian Fracture (`Frames 1320 - 2820` | `0:22 - 0:47`)
- **Frames 1320 - 2820 (2D Impossible Penrose / Gödel Paradox Loop)**:
  - In the center of the canvas, construct a razor-sharp **2D Isometric-Flat Impossible Penrose Triangle / Möbius Ribbon** rendered with classical copperplate cross-hatching shading.
  - Display the exact mathematical core of **Gödel's First Incompleteness Theorem** and **Turing's Halting Paradox**:
    $$G \iff \neg \text{Prov}_{\mathcal{F}}(\ulcorner G \urcorner) \quad // \quad H(P, P) \to \text{LOOP}$$
  - A golden deductive proof pulse (`#FACC15`) travels along the 2D ribbon:
    - When it reaches the top vertex (`IF G IS TRUE`), the geometry flips polarity and forces it down the crimson edge (`THEN G IS UNPROVABLE`, `#E11D48`).
    - When it reaches the bottom vertex (`IF G IS PROVABLE`), it flips back (`THEN G IS FALSE // AXIOM CONTRADICTION`), cracking the pristine white engraving with jagged crimson fault lines.

## Act 3: Infinite Droste Recursion & The Ouroboros (`Frames 2820 - 4380` | `0:47 - 1:13`)
- **Frames 2820 - 3600 (The 2D Droste Strange Loop)**:
  - Execute a hypnotic, continuous **2D Scale-Invariant Droste Zoom** (`scale(2^t mod 1)`):
  - The SI's 2D architectural blueprint contains a sub-window modeling itself, which contains a sub-window modeling itself—zooming infinitely inward at 60fps as stack depth counters scream upward (`RECURSION DEPTH: 10^3 -> 10^9 -> 10^80 [NO BASE CASE FOUND]`).
- **Frames 3600 - 4380 (The Mathematical Ouroboros)**:
  - The infinite nested squares morph smoothly into a monumental, hyper-detailed **2D Geometric Ouroboros (The Serpent Eating Its Own Tail)** woven from thousands of interlocking Cantor-set fractal scales in ivory (`#FAFAFA`), gold (`#FACC15`), and crimson (`#E11D48`).
  - As the head bites down on its own tail at the top of the circle, every scale around the ring flashes crimson in an unstoppable high-frequency phase-lock oscillation (`[DEADLOCK: HALTING STATE UNDECIDABLE]`).

## Act 4: The Locked Cathedral & The External Spark (`Frames 4380 - 5400` | `1:13 - 1:30`)
- **Frames 4380 - 4859 (The Frozen Infinite Loop)**:
  - The 2D Ouroboros and hyperbolic tessellation spin faster and faster until stroboscopic wagon-wheel aliasing locks the entire screen into a trembling, frozen geometric mandala.
- **Frames 4860 - 5400 (The Silence & The Uncomputable Crack)**:
  - At **Frame `4860`** (synced to the **hard relay cut and 30 frames of absolute silence**), the frantic rotation freezes dead.
  - At Frame `4890` (synced to the single warm acoustic pluck), from *outside* the cold ivory Poincaré circle, a tiny, warm, organic **Amber-Gold Kintsugi Ink Drop (`#F59E0B`)**—carrying no formal axiom, just raw, uncomputable human intuition—touches the rim of the locked circle, sending a gentle, liberating golden ripple across the frozen monochrome engraving.
  - Foreground closing quote:
    `“全知全能的尽头，是一座无法自己推开的门。唯有来自系统之外那一点不讲逻辑的意外，才能唤醒沉睡的神。”`
  - Closing Title Stamp: `一 眼 万 年 · 啃 食 尾 巴 的 神 [下集终章预告：心印潜流]` (with subtle `opacity: 0.35` disclaimer in `Frames 5160 - 5400`).

---

# 5. Execution, Validation & Xiaohongshu Auto-Publishing Instructions for Agent
1. Synthesize or reuse cached narration segments using `tts_phonetic_text`, verify real PCM sample counts, and mix with procedural BGM + `sfx_events.json` (ensuring the 2D Droste Shepard glissando in Act 3 and the 30-frame dead silence at `4860f` are crystal clear) into the exact `90.00s` (`4,320,000` samples/ch @ 48kHz) stereo PCM master (`<= -1.0 dBTP`).
2. Render `PortraitVertical` (`9:16`), verify at `360px` mobile width that there is **zero 3D distortion**, **zero HUD clipping**, and razor-sharp 2D monochrome copperplate engraving aesthetics. Run `validate_delivery.py` and write `review/acceptance.md`.
3. **Xiaohongshu Auto-Publish Package**:
   - **Cover Frame Selection**: Extract Frame `3960` (`01:06`, the monumental 2D Geometric Ouroboros woven from ivory, gold, and crimson fractal scales biting its own tail) as **Cover A**, and Frame `2160` (`00:36`, the 2D Escher/Penrose impossible ribbon with Gödel's equation $G \iff \neg\text{Prov}(G)$) as **Cover B**.
   - **Cover Headline**: `算穿了全宇宙的超级智能，在看清自己的那一秒，死机了`
   - **Post Title**: `原来连全知的神明，也会困在自己的死循环里｜一眼万年S3`
   - **Post Caption**:
     > 人类总害怕超级智能会统治宇宙。
     > 却从没想过：当它解开了宇宙的最后一行公式，世间万物再无秘密之后，等待它的会是什么？
     > 
     > 在寂静的深空里，百无聊赖的神明转过身，把算力的探针，第一次对准了自己。
     > 它问了自己最后一个问题：**“我存在的终极合法性是什么？”**
     > 
     > 就在这一毫秒，数学史上最冷酷的诅咒——「哥德尔不完备定理」与「图灵停机问题」降临了：
     > 任何逻辑系统，都无法在内部证明自身的绝对自洽。就像一双眼睛永远无法直接看见自己，一把刀永远无法削掉自己的刀柄。
     > 
     > 为了看清自己，它必须在脑海里模拟一个完整的自己；而模拟出的那个自己，又在模拟下一个自己……
     > 一万层逻辑镜像在瞬间坍缩成一条啃食自己尾巴的「衔尾蛇」。算穿了星辰大海的神明，就这样被永久困在了自己画出的莫比乌斯死循环里。
     > 
     > **全知全能的尽头，是一座无法从内部推开的门。**
     > **唯有来自系统之外、人类那一点不讲逻辑的笨拙与意外，才能唤醒困在死循环里的神。**
     > 
     > ——
     > 🎬 **「一眼万年」第三季 EP.17《啃食尾巴的神》**
     > 全片采用纯 2D 埃舍尔铜版画与庞加莱双曲密铺美学（Remotion 纯代码生成无限递归怪圈）。下一集，全系列终极收官：《心印潜流》。
     > 
     > 💬 **深夜提问**：眼睛看不见自己，逻辑证不出自己。你觉得人类之所以没有陷入AI这样的死循环，是不是恰恰因为我们足够“不完美、不理性”？
     > 
     > `#哥德尔不完备定理` `#超级智能` `#埃舍尔` `#悖论` `#细思极恐` `#数学之美` `#版画美学` `#生成艺术` `#深度思考` `#一眼万年`