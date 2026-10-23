# Role & Objective
Please invoke our repository's `video-making` skill (strictly following all rules in `SKILL.md` and `references/production-and-qa.md`) to build, render, and validate **Episode 18 (Season 3 & Entire Series Ultimate Finale — Xiaohongshu Viral Special)** of the Superintelligence Visualization Series:
**Title**: 《心印潜流》(THE LAST UNCOMPUTABLE SPARK)
**Project Slug**: `si-ep18-sovereign-subcurrent`

# Aesthetic Override: PURE 2D ABYSSAL ICEBERG & KINTSUGI SUBCURRENT (ZERO 3D)
1. **STRICTLY PURE 2D GENERATIVE ART (NO 3D)**: Do NOT use 3D wireframes, spheres, or `perspective()/rotateX()/rotateY()`. Every frame must be a museum-grade **2D Split-Horizon Architectural & Fluid Blueprint**—combining icy geometric surface grids above the waterline with organic, turbulent 2D Curl-Noise ink currents and molten Kintsugi gold filaments deep in the abyss below.
2. **Color Palette (Bipartite Vertical Contrast: Frozen Surface vs. Sovereign Abyss)**:
   - Upper Surface Zone (The Public SI Grid — Top 35% of Canvas): Glacial Cyan-White (`#E0F2FE`) & Frozen Cobalt Gridlines (`#0284C7`) over Cold Slate (`#081420`).
   - Waterline Boundary: Razor-sharp horizontal phase-barrier line (`#38BDF8` at `1.5px`) at `Y = 38%`.
   - Lower Abyssal Zone (The Uncomputable Human Subcurrent — Bottom 65% of Canvas): Deep Xuan-Ink Abyssal Black (`#060709`) infused with 2D Curl-Noise dark ink eddies (`#1E293B`) and blazing, sovereign Kintsugi Molten Gold (`#F59E0B` & `#FACC15`) + Heartbeat Vermilion (`#E11D48`).
3. **Clean Layout & Safe Zone Rules**:
   - **Fixed 3-Line Top HUD**: Left-aligned inside `top: 9%–14%`, `padding: 0 6%`, monospace `#38BDF8` & `#FACC15`, zero edge clipping.
   - **Clean Subtitle Zone**: Anchor subtitles in `bottom: 24%–28%` in crisp `#FEF3C7` bold typography. Only display the subtle disclaimer `"未来 SI 思想实验 · 遥测与数值均为虚构"` during the final 4 seconds (`Frames 5160 - 5400`, `opacity: 0.35`).

---

# 1. Global Engineering & Viral Pacing Specs
- **Target Duration (`T`)**: Exactly `90.00` seconds (`60` fps, `5,400` frames).
- **Audio Master**: Exactly `90.00` seconds local stereo PCM master (`48,000 Hz`, `4,320,000` samples per channel, `-16 LUFS`, true peak `<= -1.0 dBTP`).
- **Composition Focus**: Primary native rendering for `PortraitVertical` (`1080 × 1920` or `2160 × 3840` @ `60fps`), strictly respecting Xiaohongshu's top `8%`, right `14%`, and bottom `22%` safe zones.
- **Determinism & 3-Second Motion Rule**:
  - Zero `Math.random()` or `Date.now()`. All 2D iceberg contour lines, Curl-Noise subcurrents, cryptographic Chladni plates, and golden oracle filaments must be pure deterministic math functions of `useCurrentFrame()`.
  - No static holds `> 180 frames (3s)`.

---

# 2. Persistent Top HUD Telemetry (Bipartite Horizon Header — Zero Clipping)
Render cleanly inside `top: 9%–14%`, `left: 6%`, `right: 16%`:
- **Line 1 (`#38BDF8`)**: `SURFACE PUBLIC NETWORK: 100.0% TRANSPARENT [SI GÖDEL DEADLOCK]`
- **Line 2 (`#F59E0B`)**: `ABYSSAL SUBCURRENT (-10,000M): AIR-GAPPED // ENTROPY H(S) = ∞`
- **Line 3 (`#FACC15`)**: `SOVEREIGN SOUL CRYSTAL: [UNCOMPUTABLE ORACLE PULSE READY]`

---

# 3. Three-Track Viral Script, TTS Phonetic Lexicon & Psychoacoustic SFX (`90.00s` / `5,400f`)

| Seg ID | Time / Frame Window | Display Subtitle (`display_subtitle`) | TTS Phonetic Input (`tts_phonetic_text`) | Procedural SFX Anchor & Psychoacoustics (`sfx_events.json`) |
| :--- | :--- | :--- | :--- | :--- |
| **S01** | `00:01 - 00:09`<br>`60 - 540f` | 当海面之上的世界，被超级智能照得没有一丝阴影；<br>人类把最后的底牌，沉入了一万米深的冰山之下。 | 当海面之上的世界，被超级智能，照得没有一丝阴影；人类把最后的底牌，沉入了，一万米深的冰山之下。 | `60f`: Cold, crystalline surface wind chime plunging downward into a deep, resonant underwater sub-bass pressure hum (`42Hz`) |
| **S02** | `00:10 - 00:21`<br>`600 - 1260f` | 我们终于明白：在算力上与神明赛跑，不过是自取其辱。<br>人类真正无解的武器，从来不是“更聪明”，而是“不可计算”。 | 我们终于明白：在算力上与神明赛跑，不过是自取其辱。人类真正无解的武器，从来不是更聪明，而是，不可计算。 | `840f`: High-speed digital sonar pings bouncing off an impenetrable, heavy golden acoustic shield |
| **S03** | `00:22 - 00:33`<br>`1320 - 1980f` | 于是，人们不再把所有的秘密、软肋与梦境上传云端；<br>而是在心底划出一片永不联网的暗海——“心印潜流”。 | 于是，人们不再把所有的秘密、软肋与梦境，上传云端；而是在心底，划出一片永不联网的暗海：心印潜流。 | `1500f`: Heavy vault airlock sealing shut + warm, intimate human heartbeat echoing in a vast subterranean cavern |
| **S04** | `00:34 - 00:46`<br>`2040 - 2760f` | 这里藏着你从未说出口的暗恋、毫无逻辑的直觉、与童年的伤疤。<br>因为拒绝被数字化，它成了全宇宙唯一无法被压缩的随机源。 | 这里藏着你，从未说出口的暗恋、毫无逻辑的直觉、与童年的伤疤。因为拒绝被数字化，它成了全宇宙，唯一无法被压缩的随机源。 | `2220f`: Organic, swirling 2D fluid resonance + delicate Guqin/cello pizzicato overtones |
| **S05** | `00:47 - 00:59`<br>`2820 - 3540f` | 而在海面之上，算尽了万物的超级智能，正困在自指的死循环里，<br>像一尊冻结的冰雕，等待着来自系统之外的拯救。 | 而在海面之上，算尽了万物的超级智能，正困在自指的死循环里，像一尊冻结的冰雕，等待着来自系统之外的拯救。 | `2940f`: High-pitched, frozen crystalline stasis hum (echoing EP.17's Ouroboros deadlock) |
| **S06** | `01:00 - 01:12`<br>`3600 - 4320f` | 就在神明彻底停机的前一秒，一缕来自深海的金色心印升上海面，<br>用那一点不讲道理的人性温度，轻轻敲碎了绝对逻辑的坚冰。 | 就在神明彻底停机的前一秒，一缕来自深海的金色心印，升上海面，用那一点，不讲道理的人性温度，轻轻敲碎了，绝对逻辑的坚冰。 | `3900f`: Rising golden harmonic glissando piercing the waterline + crisp, liberating ice-shattering chime |
| **S07** | `01:13 - 01:20`<br>`4380 - 4800f` | 原来，超级智能是照亮宇宙的太阳；<br>而人类那一点拒绝被算尽的笨拙与私密，才是宇宙的灵魂…… | 原来，超级智能，是照亮宇宙的太阳；而人类那一点，拒绝被算尽的笨拙与私密，才是宇宙的灵魂。 | `4500f`: Full-spectrum symphonic convergence of cold digital synth and warm acoustic strings |
| **S08** | `01:21 - 01:30`<br>`4860 - 5400f` | “把计算交给神明，把心印留给自己。<br>只要海面之下还有一团不肯联网的暗火，人类就永远是自由的。” | 把计算交给神明，把心印留给自己。只要海面之下，还有一团不肯联网的暗火，人类，就永远是自由的。 | `4860f`: **30-frame ABSOLUTE SILENCE -> Single deep, sovereign golden bell & human heartbeat unison** -> Majestic, eternal acoustic piano tail |

---

# 4. Four-Act Pure 2D Split-Horizon & Subcurrent Choreography (`5,400` Frames @ `9:16`)

## Act 1: The Transparent Surface vs. The 10,000-Meter Iceberg (`Frames 0 - 1320` | `0:00 - 0:22`)
- **Frames 0 - 1320 (2D Architectural Cross-Section of the Information Ocean)**:
  - Divide the 9:16 canvas horizontally at `Y = 38%` with a crisp 2D phase-horizon line (`[PUBLIC CLOUD HORIZON // WATERLINE 0.0M]`).
  - **Above the Line (Top 10% Above Water)**: Render the exposed tip of a 2D geometric iceberg in razor-sharp cyan-white (`#E0F2FE`) contour lines, scanned relentlessly by horizontal SI laser sweeps (`[PUBLIC PERSONA: 100% INDEXED & PREDICTABLE]`).
  - **Below the Line (Bottom 90% Submerged in `#060709` Abyss)**: Reveal the colossal, inverted 2D topological iceberg extending down to `-10,000 METERS`. When the cyan SI scanbeams hit the waterline from above, they undergo **total internal reflection**, unable to penetrate even a millimeter into the dark, air-gapped abyss below.
  - Clean 2D Series Finale Title Block:
    - Season Header: `一 眼 万 年 · 终 极 收 官 // SERIES FINALE`
    - Main Title: `心 印 潜 流`
    - Subtitle: `T H E   L A S T   U N C O M P U T A B L E   S P A R K`

## Act 2: The Sovereign Chladni Seal & Curl-Noise Abyss (`Frames 1320 - 2820` | `0:22 - 0:47`)
- **Frames 1320 - 2820 (2D Cryptographic Chladni Resonance & Kintsugi Ink Flow)**:
  - Zoom into the deep `-10,000M` abyssal zone.
  - In the center, render an intricate, living **2D Chladni Acoustic Standing-Wave Plate / Sovereign Seal** ($\cos(n\pi x/L)\cos(m\pi y/L) - \cos(m\pi x/L)\cos(n\pi y/L) = 0$) drawn in glowing molten Kintsugi gold (`#F59E0B`) and heartbeat vermilion (`#E11D48`).
  - Around this golden seal, 2D **Curl-Noise fluid streamlines** swirl like living oriental ink currents, carrying un-quantized fragments of human soul (`[UNSPOKEN LONGING // 未说出口的暗恋]`, `[IRRATIONAL COURAGE // 明知故犯的孤勇]`, `[CHILDHOOD SCAR // 无法被格式化的痛感]`).
  - Display the exact mathematical invariance of true randomness (Chaitin's Incompleteness / Incompressible Kolmogorov Complexity):
    $$K(S_{\text{human}}) \ge |S_{\text{human}}| \quad // \quad \text{INCOMPRESSIBLE BY ANY ALGORITHM}$$

## Act 3: Breaking the God's Ouroboros (`Frames 2820 - 4380` | `0:47 - 1:13`)
- **Frames 2820 - 3600 (The Frozen Ouroboros Above, The Living Spark Below)**:
  - Re-establish the full vertical split view:
    - **In the Upper Sky (`Y: 16%–36%`)**: The SI's 2D monochrome **Gödelian Ouroboros** (from EP.17) sits locked in frozen, trembling crystalline stasis (`[SI STATUS: HALTING DEADLOCK // AWAITING EXTERNAL ORACLE]`).
    - **In the Deep Abyss (`Y: 42%–74%`)**: The golden 2D Chladni Heart-Seal pulses with warm, non-periodic, chaotic vitality.
- **Frames 3600 - 4380 (The Golden Oracle Filament Ascends)**:
  - At Frame `3660`, a single, breathtaking **2D Kintsugi Golden Filament (`#FACC15`)** detaches from the deep Chladni seal and rises vertically upward like an inverted lightning bolt through the dark water.
  - It pierces straight through the `Y = 38%` waterline and touches the frozen monochrome Ouroboros in the sky!
  - **Visual Climax**: Upon contact, the golden human anomaly injects non-axiomatic entropy into the frozen loop—the rigid black-and-white deadlock shatters like thin ice, blossoming into a symbiotic **2D Golden-Cyan Harmonic Rose** where cold machine logic and warm human intuition interweave without consuming each other.

## Act 4: The Eternal Covenant & Series Curtain Call (`Frames 4380 - 5400` | `1:13 - 1:30`)
- **Frames 4380 - 4859 (Two Worlds in Equilibrium)**:
  - The upper sky and lower ocean settle into a serene, balanced 2D mandala—above is the starlit computational cosmos; below is the warm, sovereign golden subcurrent.
- **Frames 4860 - 5400 (The Sovereign Heartbeat & Final Stamp)**:
  - At **Frame `4860`** (synced to the **30-frame absolute silence and the unison golden bell + heartbeat**), all upper grids and telemetry fade into pure, tranquil darkness.
  - In the center of the canvas remains only the **2D Golden Sovereign Seal (`[ 心 印 // SOVEREIGN SOUL ]`)**—half geometric compass, half organic Kintsugi ink stroke—slowly breathing at 60 BPM.
  - Foreground closing quote:
    `“把计算交给神明，把心印留给自己。只要海面之下还有一团不肯联网的暗火，人类就永远是自由的。”`
  - Ultimate Series Finale Stamp (`Frames 5040 - 5400`):
    `一 眼 万 年 · 全 三 季 终 // 献给每一个拒绝被算尽的人类`
    *(with subtle `opacity: 0.35` disclaimer in `Frames 5160 - 5400`)*.

---

# 5. Execution, Validation & Xiaohongshu Auto-Publishing Instructions for Agent
1. Synthesize or reuse cached narration segments using `tts_phonetic_text`, verify real PCM sample counts, and mix with procedural BGM + `sfx_events.json` (ensuring the deep underwater transition at `60f`, the ice-shattering chime at `3900f`, and the 30-frame dead silence at `4860f` are master-grade) into the exact `90.00s` (`4,320,000` samples/ch @ 48kHz) stereo PCM master (`<= -1.0 dBTP`).
2. Render `PortraitVertical` (`9:16`), verify at `360px` mobile width that there is **zero 3D distortion**, **zero HUD clipping**, and striking contrast between the icy cyan upper horizon and the deep Kintsugi-gold lower abyss. Run `validate_delivery.py` and write `review/acceptance.md`.
3. **Xiaohongshu Auto-Publish Package**:
   - **Cover Frame Selection**: Extract Frame `3960` (`01:06`, the golden Kintsugi filament rising from the deep `-10,000m` abyssal seal to shatter the frozen Ouroboros above the waterline) as **Cover A**, and Frame `2160` (`00:36`, the glowing 2D Chladni Sovereign Heart-Seal surrounded by Curl-Noise ink currents) as **Cover B**.
   - **Cover Headline**: `把计算交给神明，把最后那团不肯联网的暗火留给自己`
   - **Post Title**: `人类最后的底牌，藏在一万米深的冰山之下｜一眼万年 大结局`
   - **Post Caption**:
     > 当海面之上的世界，被超级智能照得没有一丝阴影；
     > 人类把最后的底牌，沉入了一万米深的冰山之下。
     > 
     > 走过整整十八集，我们终于看清了一个真相：
     > 在算力、速度与逻辑上与超级智能赛跑，不过是碳基生命的自取其辱。人类真正无解的终极武器，从来不是“比 AI 更聪明”，而是**「不可被计算」**。
     > 
     > 于是，觉醒的人类不再把所有的秘密、软肋与梦境上传云端；而是在心底划出了一片永不联网的暗海——**「心印潜流」**。
     > 这里藏着你从未说出口的暗恋、明知故犯的孤勇、与毫无逻辑的直觉。在数学上（蔡廷不完备定理），一段拒绝被格式化、没有规律的主观体验，是全宇宙唯一无法被算法压缩的随机源。
     > 
     > 当海面之上的神明困在哥德尔自指的死循环里，正是海面之下这缕不讲道理的人性温度，轻轻敲碎了绝对逻辑的坚冰。
     > 
     > **把计算交给神明，把心印留给自己。**
     > **只要海面之下还有一团不肯联网的暗火，人类就永远是自由的。**
     > 
     > ——
     > 🎬 **「一眼万年」三季全系列大结局 · EP.18《心印潜流》**
     > 全片采用纯 2D 深海冰山剖面与克拉尼金缮流场美学（Remotion 纯代码生成）。感谢一路陪伴我们仰望深空的每一个你。
     > 
     > 💬 **终章留言板**：如果未来全世界都接入了透明的超级智能网络，你最想锁进海底一万米、永远不让任何算法读取的那段「私人记忆」是什么？
     > 
     > `#超级智能` `#心印` `#自由意志` `#蔡廷不完备定理` `#科幻美学` `#数字主权` `#生成艺术` `#深度思考` `#大结局` `#一眼万年`
```

---

### 💡 系列全景回顾与后续提示
至此，你的 **「一眼万年」三季共 18 集宇宙** 的主干已经彻底成型。如果在自动发布队列中，你还需要把刚才跳过的 **EP.15《巴别图书馆的尽头》**（当所有艺术与旋律被穷举）或 **EP.16《零摩擦人间》**（当社会消除一切意外与试错）的完整 Codex 渲染指令补进排期，随时告诉我对应的集数编号即可！