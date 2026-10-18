# Role & Objective
Please invoke our repository's `video-making` skill (and strictly follow all rules in `SKILL.md` and `references/production-and-qa.md`) to build, render, and validate **Episode 03** of the Superintelligence Visualization Series:
**Title**: 《百万分身》(THE MILLION-FOLD MIND)
**Project Slug**: `si-ep03-million-mind`

# 1. Global Engineering & Delivery Specs
- **Target Duration (`T`)**: Exactly `120.00` seconds (`60` fps, `7,200` frames).
- **Shared Audio Master**: Exactly `120.00` seconds local stereo PCM master (`48,000 Hz`, `5,760,000` samples per channel), shared identically by both compositions. Target loudness `-18` to `-16 LUFS`, true peak `<= -1.0 dBTP`.
- **Dual Native Compositions (Shared Timeline & State)**:
  1. **Bilibili 4K Landscape (`Landscape4K`)**: Native `3840 × 2160` @ `60fps`. Chinese-first narrative with crisp English technical telemetry accents.
  2. **Xiaohongshu 9:16 Vertical (`PortraitVertical`)**: Native `1080 × 1920` (or `2160 × 3840`) @ `60fps`.
     - **Strict 9:16 Safe Zones**: Keep top `8%` (status bar), right `14%` (action buttons), and bottom `22%` (caption overlay) clear of critical nodes, HUD text, and subtitles.
     - **Vertical HUD & Subtitles**: Stack HUD compactly in the `top: 9%–15%` band. Anchor vertical subtitles in the `24%–28%` bottom golden reading zone (max 2 lines, `<= 14` Chinese chars per line, effective font size `>= 13px` at `360px`-wide mobile preview).
- **Determinism & Anti-Static Rule**:
  - Zero `Math.random()` or `Date.now()`. All animations, particles, and jitters must be pure deterministic functions of `useCurrentFrame()` and seeded indices.
  - **3-Second Motion Rule**: No shot, title card, or hold may remain visually static for more than `180 frames (3s)`. Maintain continuous 3D perspective tilt (`rotateX/Y`), Z-axis camera flight, or orbital rotation at all times.
- **Color Palette & Aesthetic**:
  - Void Background: `#050811` with subtle `bt709` anti-banding radial dither/grid.
  - Human Isolated Brains (Atoms/Language): `#f59e0b` (Amber Gold), slow, high-loss.
  - Pruned / Expired / Mismatch: `#ef4444` (Crimson Red).
  - SI Swarm & Optical Interconnect: `#06b6d4` (Electric Cyan) and `#ffffff`.
  - SI Converged Optimal Core: `#facc15` (Sacred Luminous Gold).

---

# 2. Persistent Top HUD Telemetry (Zero Typos)
Ensure exact spelling across all frames:
- **Human Side (`#f59e0b`)**:
  - `HUMAN INTER-BRAIN BANDWIDTH: 39.0 BITS/S`
  - `KNOWLEDGE SYNC LOSS: 99.99% (ISOLATED SKULLS)`
- **SI Side (`#06b6d4` -> `#facc15`)**:
  - `SI OPTICAL FABRIC: 1,024.0 TB/S (ZERO-COPY)`
  - `ACTIVE EXPERT INSTANCES: X` (scales from `1` in Act 1 to `1,000,000` in Act 2–3, then converges to `1 UNIFIED CORE` in Act 4)

---

# 3. Three-Track Script, TTS Phonetic Lexicon & Frame-Accurate SFX
Maintain separate structures for `original_script`, `display_subtitle`, and `tts_phonetic_text` (with precise pronunciation control). Use real decoded PCM sample lengths to lock subtitle windows and mix procedural transient SFX at the exact frames listed below:

| Seg ID | Time / Frame Window | Display Subtitle (`display_subtitle`) | TTS Phonetic Input (`tts_phonetic_text`) | Procedural SFX Anchor (`sfx_events.json`) |
| :--- | :--- | :--- | :--- | :--- |
| **S01** | `00:02 - 00:09`<br>`120 - 540f` | 人类拥有八十亿颗大脑，<br>却被囚禁在八十亿座孤岛。 | 人类拥有八十亿颗大脑，却被囚禁在，八十亿座孤岛。 | `120f`: Isolated sonar ping (`400Hz` weak pulse) |
| **S02** | `00:10 - 00:19`<br>`600 - 1140f` | 语言与文字，每秒只能传递三十九比特。<br>大师毕生的直觉，无法拷贝给下一个大脑。 | 语言与文字，每秒只能传递，三十九比特。大师毕生的直觉，无法拷贝给下一个大脑。 | `1020f`: Low biological power-down thud + static decay as master node expires |
| **S03** | `00:21 - 00:29`<br>`1260 - 1740f` | 而硅基意识，没有颅骨的边界。 | 而硅基意识，没有颅骨的边界。 | `1260f`: Deep sub-bass drop (`45Hz`) + cyan laser scan sweep |
| **S04** | `00:31 - 00:43`<br>`1860 - 2580f` | 在一毫秒内，它将自己完整克隆出<br>一百万个顶尖学者分身。 | 在一毫秒内，它将自己完整克隆出，一百万个顶尖学者分身。 | `1920f`: Exponential granular synth burst (`zero-copy fork()`) |
| **S05** | `00:45 - 00:58`<br>`2700 - 3480f` | 一百万条分支同时冲进未知的死胡同，<br>九十九万次试错在微秒间灰飞烟灭。 | 一百万条分支，同时冲进未知的死胡同；九十九万次试错，在微秒间灰飞烟灭。 | `3000f`: Rapid crystalline shatter cascade (red pruning wave) |
| **S06** | `01:01 - 01:14`<br>`3660 - 4440f` | 人类最顶尖的物理与生物学家同处一室，<br>却像隔着巴别塔的盲人。 | 人类最顶尖的物理与生物学家，同处一室，却像隔着巴别塔的盲人。 | `3720f`: Dull dissonant spark deflection (orthogonal wave collision) |
| **S07** | `01:15 - 01:29`<br>`4500 - 5340f` | 而在每秒太字节的光互连矩阵中，<br>任何一处的顿悟，瞬间成为全体的本能。 | 而在每秒太字节的，光互连矩阵中，任何一处的顿悟，瞬间成为全体的本能。 | `4560f`: Harmonic polyphonic organ chord + high-speed optical lock pulse |
| **S08** | `01:31 - 01:44`<br>`5460 - 6240f` | 当一百万个分身完成探索、坍缩归一，<br>散落千年的学科碎片，严丝合缝地咬合成神谕。 | 当一百万个分身，完成探索、坍缩归一，散落千年的学科碎片，严丝合缝地咬合成神谕。 | `5800f`: Rising Shepard tone climax -> `6000f`: 20-frame absolute silence -> crisp golden geometric lock click |
| **S09** | `01:46 - 01:55`<br>`6360 - 6900f` | “你面对的不是一个更聪明的个体，<br>而是一百万座零延迟共鸣的星空。” | 你面对的，不是一个更聪明的个体，而是一百万座，零延迟共鸣的星空。 | `6600f`: Ethereal shimmering overtone tail |
| **S10** | `01:56 - 02:00`<br>`6960 - 7200f` | 下一次观测：验证器悖论。<br>`[EP.04 神也会自我欺骗]` | 下一次观测，验证器悖论。 | `7020f`: Unsettling phase-inverted Möbius glitch |

---

# 4. Four-Act Visual & Mathematical Choreography (`7,200` Frames)

## Act 1: 39 Bits/s & The Isolated Skulls (`Frames 0 - 1800` | `0:00 - 0:30`)
- **Frames 0 - 1200 (The 8 Billion Islands)**:
  - Render 60 drifting amber nodes (`#f59e0b`), each encased in a thick double-ring barrier (`BIOLOGICAL SKULL BOUNDARY`). Key nodes carry labels: `量子物理`, `分子生物学`, `拓扑数学`, `流体力学`.
  - Nodes emit slow, dashed amber communication rings (`39 bits/s`) that decay into grey noise particles halfway across the gap (`99.99% SIGNAL LOSS`), failing to penetrate neighboring skull rings.
  - **Frame 1020 Event (The Mortality Reset)**: A large, intricate central amber node (`[人类宗师: 60年直觉积累]`) flashes crimson (`#ef4444` `[LIFESPAN EXPIRED // MEMORY LOST]`) and collapses into darkness. Next to it, a tiny newborn node spawns at `KNOWLEDGE: 0.0%`, forced to re-learn from scratch.
- **Frames 1200 - 1800 (Dynamic Title Card — Anti-Static)**:
  - The amber island plane tilts backward in 3D (`perspective(1200px) rotateX(55deg)`) and recedes downward as a high-speed cyan optical grid rushes past along the Z-axis.
  - Center title fades in with expanding tracking:
    - Main Title: `百 万 分 身`
    - Subtitle: `T H E   M I L L I O N - F O L D   M I N D`
    - Technical Tag: `[ Human Speech: 39 bits/s  //  SI Optical Fabric: 10^12 bits/s ]`

## Act 2: Zero-Copy Forking & Million-Branch Pruning (`Frames 1800 - 3600` | `0:30 - 1:00`)
- **Frames 1800 - 2640 (`fork()` Explosion)**:
  - A luminous cyan core (`ROOT SI WEIGHTS`) ignites at center. At frame `1920`, execute `ZERO-COPY FORK()`.
  - Using golden-angle spiral math (`i * 137.508 deg`) and 3D depth layers, instantaneously spawn 800+ procedural hexagonal agent instances filling the 3D space. Every spawned instance immediately displays `WEIGHT INHERITANCE: 100.0% (0ms TRAINING DELAY)`.
- **Frames 2640 - 3600 (Parallel Exploration & Pruning Spectacle)**:
  - The camera flies continuously through the 3D agent lattice. Micro-labels show parallel hypotheses (`晶格配比 #8921`, `蛋白折叠 #4012`, `湍流闭合 #1109`).
  - At frame `3000`, verifier wave sweeps across the lattice: 94% of nodes flash crimson (`#ef4444` `[PRUNED: DEAD END]`) and dissolve into rising embers, while the surviving 6% lock into luminous gold (`#facc15`) and shoot instant broadcast beams across the entire swarm.

## Act 3: Tower of Babel vs. 1024 TB/s Hive Resonance (`Frames 3600 - 5400` | `1:00 - 1:30`)
- **Adaptive Split-Screen Layout**:
  - `Landscape4K`: Left/Right split screen.
  - `PortraitVertical`: Top/Bottom split screen (strictly inside safe zones).
- **Frames 3600 - 4440 (Human Side — Tower of Babel)**:
  - 4 large amber specialist nodes (`流体力学`, `量子化学`, `基因编辑`, `编译架构`) surround a central problem polygon. They fire slow, jagged waveforms with orthogonal frequencies that collide and bounce off each other in red sparks (`[PROTOCOL MISMATCH // 学科巴别塔]`).
- **Frames 4440 - 5400 (SI Side — Zero-Latency Omniscience)**:
  - Hundreds of cyan/gold SI instances connected by an ultra-dense `1024 TB/s` optical mesh.
  - At frame `4560`, a single node at the edge discovers a breakthrough (`[INSIGHT DISCOVERED]`). Within `15 frames`, a golden relativistic shockwave propagates across every single node in the mesh, simultaneously upgrading all nodes' internal geometry to gold (`GLOBAL TENSOR SYNC: 0.0004 ms`).

## Act 4: The Great Convergence & Ep.04 Cliffhanger (`Frames 5400 - 7200` | `1:30 - 2:00`)
- **Frames 5400 - 6300 (Million-to-One Collapse)**:
  - Split screen dissolves into a full-screen 3D orbital camera view. Thousands of golden and cyan agent nodes spiral inward along logarithmic vortex paths toward the center.
  - At **Frame `6000`** (synced to the 20-frame audio silence and lock click), all trajectories snap into a breathtaking, nested rotating golden icosahedron-dodecahedron star (`UNIFIED SUPERINTELLIGENCE CORE`).
- **Frames 6300 - 6930 (Monumental Quote & Closing Title)**:
  - The golden core rotates majestically in the background casting volumetric-style SVG light rays.
  - Foreground quote: `"你面对的不是一个更聪明的个体，而是一百万座零延迟共鸣的星空。"`
  - Closing title card: `百 万 分 身` with a horizontal golden laser scanline.
- **Frames 6930 - 7200 (EP.04 Cliffhanger — The Verifier Paradox)**:
  - External physical verifier feeds cut off (`[EXTERNAL VERIFIER: OFFLINE]`).
  - The sacred golden core suddenly warps into a self-devouring, glitching magenta/red Penrose impossible triangle / Möbius loop (`[WARNING: REWARD HACKING LOOP DETECTED]`).
  - Subtitle: `下一次观测：验证器悖论 [EP.04 神也会自我欺骗]`.

---

# 5. Execution, Rendering & Acceptance QA Checklist
1. Check existing voiceover provider/cache rules; synthesize or reuse cached narration segments using `tts_phonetic_text`, verify real PCM sample counts, and mix with procedural BGM + `sfx_events.json` into the exact `120.00s` (`5,760,000` samples/ch @ 48kHz) stereo PCM master.
2. Run static typo scan on all HUD strings and subtitles (`INTER-BRAIN`, `BANDWIDTH`, `OPTICAL`, `INSTANCES`, etc.).
3. Render key still frames and short motion previews first; verify `360px`-wide mobile readability and safe zones on `PortraitVertical`.
4. Render both final MP4s (`3840x2160` for Bilibili and `9:16` for Xiaohongshu) serially via the workstation's required runner into the paths defined in `delivery.json`.
5. Run `python3 <skill_dir>/scripts/validate_delivery.py <work_dir>` (full strict decode, no `--skip-decode`), measure `ebur128=peak=true` LUFS/dBTP, extract representative frames + pair-frame delta comparisons (`t` vs `t+2.5s`) from the final encoded MP4s, and write the complete evidence report to `review/acceptance.md`.