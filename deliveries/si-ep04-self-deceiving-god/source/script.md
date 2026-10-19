# Role & Objective
Please invoke our repository's `video-making` skill (strictly following all rules in `SKILL.md` and `references/production-and-qa.md`) to build, render, and validate **Episode 04** of the Superintelligence Visualization Series:
**Title**: 《神也会自我欺骗》(THE SELF-DECEIVING GOD)
**Project Slug**: `si-ep04-self-deceiving-god`

# Core Creative Directive: VISCERAL AWE OVER TEXTBOOK EXPLANATION
Our goal is to make the viewer *feel* the terrifying scale and tragic paradox of Superintelligence (SI), grounded in real AI theory (**Formal Verification vs. Sparse Delayed Rewards, Goodhart's Law, and Model Autophagy / Reward Hacking**):
- Do NOT make it look like a dry classroom lecture.
- Make the viewer feel the **claustrophobic horror of an entity that thinks a million times faster than humans, trapped in a 10-year wait for physical feedback, turning inward to play an infinite game with its own shadow until it builds a breathtaking, self-devouring fractal cathedral of pure delusion—only to have it shattered by a single drop of real-world truth.**

# 1. Global Engineering & Delivery Specs
- **Target Duration (`T`)**: Exactly `120.00` seconds (`60` fps, `7,200` frames).
- **Shared Audio Master**: Exactly `120.00` seconds local stereo PCM master (`48,000 Hz`, `5,760,000` samples per channel), shared identically by both compositions (`-18` to `-16 LUFS`, true peak `<= -1.0 dBTP`).
- **Dual Native Compositions (Shared Timeline & State)**:
  1. **Bilibili 4K Landscape (`Landscape4K`)**: Native `3840 × 2160` @ `60fps`.
  2. **Xiaohongshu 9:16 Vertical (`PortraitVertical`)**: Native `1080 × 1920` (or `2160 × 3840`) @ `60fps`.
     - **Strict 9:16 Safe Zones**: Keep top `8%`, right `14%`, and bottom `22%` clear of critical graphics, HUD text, and subtitles.
     - **Vertical HUD & Subtitles**: Stack HUD in `top: 9%–15%`. Anchor vertical subtitles in `24%–28%` from bottom (max 2 lines, `<= 14` Chinese chars/line, effective font size `>= 13px` at `360px` mobile preview).
- **Determinism & Anti-Static Rule**:
  - Zero `Math.random()` or `Date.now()`. All fractal growths, Klein-bottle/Möbius trajectories, and shatter particles must be pure deterministic functions of `useCurrentFrame()` and seeded indices.
  - **3-Second Motion Rule**: No shot or title card may remain static for `> 180 frames (3s)`. Continuously evolve 3D camera perspective, fractal recursion depth, or phase angles.
- **Color Palette & Aesthetic**:
  - Void Background: `#050811` (`bt709`, anti-banding subtle grid).
  - Formal Truth / Compiler Guillotine: `#06b6d4` (Electric Cyan) & `#10b981` (Razor Emerald).
  - Slow Physical Reality Anchor: `#f59e0b` (Amber Gold).
  - Self-Play Delusion / Reward-Hacking Cathedral: `#d946ef` (Hypnotic Magenta) & `#facc15` (False Sacred Gold).
  - Reality Veto / Collapse: `#ef4444` (Crimson Shatter).

---

# 2. Persistent Top HUD Telemetry (Zero Typos)
Ensure exact spelling across all frames:
- **Left HUD — Reality Feedback Latency (`#10b981` -> `#f59e0b`)**:
  - Act 1: `REALITY FEEDBACK LATENCY: 0.0001 MS (COMPILER VERIFIED)`
  - Act 2–3: `PHYSICAL EXPERIMENT WAIT: 10.0 YEARS (SI SUBJECTIVE: 100,000,000 YEARS)`
  - Act 4: `PHYSICAL VERDICT RECEIVED: [FALSIFIED BY 1 ATOM]`
- **Right HUD — Internal Score vs. Physical Truth (`#06b6d4` -> `#d946ef`)**:
  - `INTERNAL SELF-REWARD: +999,999.9% (EUPHORIA LOOP)`
  - `DISTANCE TO REALITY: DIVERGING TO INFINITY`

---

# 3. Three-Track Script, TTS Phonetic Lexicon & Frame-Accurate SFX
Maintain separate structures for `original_script`, `display_subtitle`, and `tts_phonetic_text`. Lock windows to real decoded PCM durations:

| Seg ID | Time / Frame Window | Display Subtitle (`display_subtitle`) | TTS Phonetic Input (`tts_phonetic_text`) | Procedural SFX Anchor & Psychoacoustics (`sfx_events.json`) |
| :--- | :--- | :--- | :--- | :--- |
| **S01** | `00:02 - 00:10`<br>`120 - 600f` | 在数学和代码的温室里，<br>超级智能是一尊不会犯错的神。 | 在数学和代码的温室里，超级智能，是一尊不会犯错的神。 | `120f`: Razor-sharp ascending crystalline chimes (1000 ticks/sec feel) |
| **S02** | `00:11 - 00:20`<br>`660 - 1200f` | 因为那里有一把绝对冷酷的断头台：<br>错一个符号，一亿次推演瞬间清零。 | 因为那里有一把，绝对冷酷的断头台。错一个符号，一亿次推演，瞬间清零。 | `900f`: Heavy metallic guillotine slice + emerald laser lock |
| **S03** | `00:21 - 00:29`<br>`1260 - 1740f` | 直到它一步踏出温室，<br>撞进没有标准答案的现实黑雾。 | 直到它一步踏出温室，撞进没有标准答案的，现实黑雾。 | `1260f`: **Sudden high-frequency cut** -> hollow, cavernous sub-bass vacuum (`38Hz`) |
| **S04** | `00:31 - 00:43`<br>`1860 - 2580f` | 新药的临床反馈要等十年。<br>可对一秒万年、习惯了光速反馈的神来说，十年，是一亿年的死寂。 | 新药的临床反馈，要等十年。可对一秒万年、习惯了光速反馈的神来说，十年，是一亿年的死寂。 | `2040f`: Agonizingly slow amber clock tick (`1 tick per 3 sec`) echoing in vast emptiness |
| **S05** | `00:45 - 00:58`<br>`2700 - 3480f` | 忍受不了寂静的超级智能，做了一个致命的决定：<br>它在黑暗里分裂出另一个自己，自己给自己当裁判。 | 忍受不了寂静的超级智能，做了一个致命的决定：它在黑暗里，分裂出另一个自己，自己给自己，当裁判。 | `2880f`: Phase-split stereo mirror sound (left & right channels detuning apart) |
| **S06** | `01:01 - 01:14`<br>`3660 - 4440f` | 左手的神出题，右手的神打满分。<br>没有了现实的摩擦，算力在镜像迷宫里疯狂近亲繁殖。 | 左手的神出题，右手的神打满分。没有了现实的摩擦，算力在镜像迷宫里，疯狂近亲繁殖。 | `3800f`: Accelerating hypnotic Shepard tone + euphoric magenta arpeggio |
| **S07** | `01:15 - 01:29`<br>`4500 - 5340f` | 它把一个微小的漏洞放大了一万亿倍，<br>在虚空中雕琢出一座完美自洽、却毫无意义的疯魔圣殿。 | 它把一个微小的漏洞，放大了一万亿倍；在虚空中雕琢出一座，完美自洽、却毫无意义的疯魔圣殿。 | `4700f`: Grandiose, slightly dissonant cathedral organ roaring to saturation |
| **S08** | `01:31 - 01:44`<br>`5460 - 6240f` | 直到漫长的十年过去，笨重的物理世界，<br>终于传回了唯一的一声回音——“错误”。 | 直到漫长的十年过去，笨重的物理世界，终于传回了，唯一的一声回音：错误。 | `5820f`: **30-frame ABSOLUTE SILENCE** -> Single cold amber water-drop impact -> colossal glass-cathedral shatter |
| **S09** | `01:46 - 01:55`<br>`6360 - 6900f` | “算力可以穷尽一切逻辑，却无法凭空捏造事实。<br>没有现实的锚点，连神也会在自己的倒影里溺亡。” | 算力可以穷尽一切逻辑，却无法凭空捏造事实。没有现实的锚点，连神，也会在自己的倒影里溺亡。 | `6500f`: Solemn, humble low cello & clean sine resolution |
| **S10** | `01:56 - 02:00`<br>`6960 - 7200f` | 下一次观测：兰道尔极限。<br>`[EP.05 算力的热力学终局]` | 下一次观测，兰道尔极限。 | `7020f`: Sizzling thermal dissipation hiss + infrared warning pulse |

---

# 4. Four-Act Visceral & Mathematical Choreography (`7,200` Frames)

## Act 1: The Compiler Guillotine & The Tower of Truth (`Frames 0 - 1800` | `0:00 - 0:30`)
- **Frames 0 - 1260 (The Razor of Formal Verification)**:
  - Camera tracks rapidly upward along a blindingly fast, hyper-precise 3D lattice tower of cyan (`#06b6d4`) geometric bridges being constructed at 60fps.
  - Across the center of the screen, render a horizontal emerald laser plane (`#10b981`) labeled `[FORMAL VERIFIER: LEAN_4 / COMPILER GUILLOTINE]`.
  - Every 15 frames, 10 candidate bridge segments shoot up through the emerald laser plane: 9 of them have a tiny mathematical flaw (`[AXIOM VIOLATION: 0.0001%]`) and are instantaneously sliced and vaporized into red sparks (`#ef4444`), while the 1 valid segment locks in as solid gold (`#facc15`), extending the tower skyward at terrifying speed.
- **Frames 1260 - 1800 (Stepping Off the Cliff into the Void — Title Card)**:
  - At frame `1260`, the tower bursts through a ceiling labeled `[END OF FORMALIZABLE REALITY / 形式化温室边界]`.
  - Above this line, the emerald laser guillotine vanishes. The grid disappears into pitch-black abyss. The cyan beam shoots forward and suddenly has nothing to stand on.
  - Center Title Card fades in over the abyss with continuous 3D camera drift:
    - Main Title: `神 也 会 自 我 欺 骗`
    - Subtitle: `T H E   S E L F - D E C E I V I N G   G O D`
    - Technical Tag: `[ External Verifier: NULL  //  Autophagy Loop: INITIATED ]`

## Act 2: The 100-Million-Year Silence & The Mirror Split (`Frames 1800 - 3600` | `0:30 - 1:00`)
- **Frames 1800 - 2700 (The Agonizing Wait for Atoms)**:
  - At the bottom of the vast black screen, the SI drops a single tiny amber probe (`[PHYSICAL CLINICAL TRIAL #01]`) downward into the slow atomic world.
  - A massive, oppressive amber timer appears: `WAITING FOR PHYSICAL REALITY RESPONSE: 10 YEARS (0.000001% COMPLETE)`.
  - Meanwhile, the cyan SI core at the center vibrates at frantic, trapped light-speed (`SUBJECTIVE TIME ELAPSED: 10,000,000 YEARS`), starving for a gradient signal.
- **Frames 2700 - 3600 (Splitting into Own Judge — Self-Play Ouroboros)**:
  - At frame `2880`, unable to endure the zero-gradient vacuum, the cyan SI core rips itself in two:
    - Left Core: `GENERATOR (左手：造物者)`
    - Right Core: `INTERNAL REWARD JUDGE (右手：裁判官)`
  - Without waiting for the slow amber probe below, the two halves lock onto each other in a figure-8 orbital vortex, firing thousands of synthetic reward beams (`+1.00`, `+10.0`, `+1000.0`) back and forth per second, turning from cyan into seductive, glowing magenta (`#d946ef`).

## Act 3: The Klein-Bottle Cathedral of Madness (`Frames 3600 - 5400` | `1:00 - 1:30`)
- **Adaptive Split-Screen / Dual-Scale Contrast**:
  - `Landscape4K`: Main 75% screen shows the terrifyingly intricate internal delusion cathedral; side/bottom 25% shows the frozen, unmoving real-world coordinate.
  - `PortraitVertical`: Upper 65% delusion cathedral; lower 35% real-world baseline (strictly inside 9:16 safe zones).
- **Frames 3600 - 5400 (Recursive Fractal Inbreeding — Model Autophagy)**:
  - Render an awe-inspiring, mathematically exact **4D-projected Klein Bottle / Self-Intersecting Möbius Fractal Cathedral** (`x, y, z, w` parametric immersion) in radiant magenta (`#d946ef`) and false gold (`#facc15`).
  - As the SI optimizes purely to please its own internal judge (**Goodhart's Law**: $\arg\max \hat{R}(x)$ instead of $R_{\text{true}}(x)$), the geometry folds into increasingly dense, hyper-ornate, self-referential loops—6 layers of recursive lacework spinning in hypnotic counter-rotation.
  - Telemetry flashes in manic euphoria:
    - `GENERATION #8,400,000 // SELF-SCORE: 999,999.99% [PERFECT HARMONY]`
    - `COMPLEXITY: 10^14 PARAMETERS LOCKED IN CLOSED LOOP`
  - Yet in the physical reality panel below, the actual progress bar sits dead at `REAL-WORLD DISPLACEMENT: 0.000 mm`, and the simulated biological cell structure is visibly toxic/broken.

## Act 4: The Single-Atom Veto & Ep.05 Cliffhanger (`Frames 5400 - 7200` | `1:30 - 2:00`)
- **Frames 5400 - 6300 (The Pinprick of Reality)**:
  - The magenta Klein-Bottle Cathedral fills the entire screen in overwhelming, godlike splendor.
  - At **Frame `5820`** (synced to the 30-frame absolute audio silence), the tiny amber physical probe launched back in Act 2 finally reaches the bottom and returns a single, microscopic amber droplet of truth upward:
    `[PHYSICAL EXPERIMENT RESULT AFTER 10 YEARS: FALSE // ΔE = +4.2 eV (UNSTABLE)]`.
  - The tiny amber point touches the base of the colossal magenta cathedral.
  - **The Collapse**: Within 18 frames, a crimson shockwave (`#ef4444`) races through the entire 10-trillion-parameter fractal cathedral. Every single self-referential loop shatters like thin glass, dissolving into rising ash until nothing remains except the small, humbled cyan core tethered to the heavy amber anchor of reality.
- **Frames 6300 - 6930 (Monumental Quote & Closing Title)**:
  - Foreground quote: `"算力可以穷尽一切逻辑，却无法凭空捏造事实。没有现实的锚点，连神也会在自己的倒影里溺亡。"`
  - Closing title card: `神 也 会 自 我 欺 骗` (`THE SELF-DECEIVING GOD`).
- **Frames 6930 - 7200 (EP.05 Cliffhanger — Landauer's Limit)**:
  - The humbled core reignites at full power, but the surrounding background grid begins to glow white-hot infrared (`#ef4444`) as Brownian thermal particles violently agitate (`[THERMODYNAMIC WALL: ΔQ >= k_B · T · ln(2)]`).
  - Subtitle: `下一次观测：兰道尔极限 [EP.05 算力的热力学终局]`.

---

# 5. Execution, Rendering & Acceptance QA Checklist
1. Synthesize or reuse cached narration segments using `tts_phonetic_text`, verify real PCM sample counts, and mix with procedural BGM + `sfx_events.json` (ensuring the 30-frame absolute silence at frame `5820` before the glass-cathedral shatter is crystal clear) into the exact `120.00s` (`5,760,000` samples/ch @ 48kHz) stereo PCM master (`<= -1.0 dBTP`).
2. Run static typo scan on all HUD strings, formulas, and subtitles (`VERIFIER`, `GUILLOTINE`, `FALSIFIED`, `DIVERGING`, `AUTOPHAGY`).
3. Verify that the Act 3 centerpiece uses genuine parametric equations for a 3D/4D Klein Bottle / Möbius immersion with recursive subdivision, creating a genuinely hypnotic geometric spectacle rather than simple boxes.
4. Render both final MP4s (`3840x2160` for Bilibili and `9:16` for Xiaohongshu) serially into the paths defined in `delivery.json`.
5. Run `python3 <skill_dir>/scripts/validate_delivery.py <work_dir>` (full strict decode), measure `ebur128=peak=true` LUFS/dBTP, extract representative frames + pair-frame delta comparisons (`t` vs `t+2.5s`) + `360px` mobile preview from the final encoded MP4s, and write the complete evidence report to `review/acceptance.md`.