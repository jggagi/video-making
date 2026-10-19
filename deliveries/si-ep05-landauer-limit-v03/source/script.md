# Role & Objective
Please invoke our repository's `video-making` skill (strictly following all rules in `SKILL.md` and `references/production-and-qa.md`) to build, render, and validate **Episode 05** of the Superintelligence Visualization Series:
**Title**: 《兰道尔极限》(THE LANDAUER LIMIT)
**Project Slug**: `si-ep05-landauer-limit`

# Core Creative Directive: VISCERAL THERMODYNAMIC CLAUSTROPHOBIA OVER TEXTBOOK CHARTS
Our goal is to make the viewer *physically feel* the suffocating thermodynamic wall of Superintelligence (SI), grounded in rigorous physics (**Landauer's Principle $\Delta Q \ge k_B T \ln 2$, Szilard Phase-Space Compression, Stefan-Boltzmann Planetary Radiative Lock $P = 4\pi R^2 \sigma T^4$, and 2.725K Deep-Space Fractal Radiators**):
- Do NOT render dry, static classroom charts.
- Make the viewer feel that **every thought is a microscopic fire**, that **Earth is a sealed pressure cooker unable to vent the waste heat of a god-like mind**, and deliver the spine-chilling **Fermi Paradox revelation** when all thermal noise cuts to absolute vacuum silence at `2.725 K`.

# 1. Global Engineering & Delivery Specs
- **Target Duration (`T`)**: Exactly `120.00` seconds (`60` fps, `7,200` frames).
- **Shared Audio Master**: Exactly `120.00` seconds local stereo PCM master (`48,000 Hz`, `5,760,000` samples per channel), shared identically by both compositions (`-18` to `-16 LUFS`, true peak `<= -1.0 dBTP`).
- **Dual Native Compositions (Shared Timeline & State)**:
  1. **Bilibili 4K Landscape (`Landscape4K`)**: Native `3840 × 2160` @ `60fps`.
  2. **Xiaohongshu 9:16 Vertical (`PortraitVertical`)**: Native `1080 × 1920` (or `2160 × 3840`) @ `60fps`.
     - **Strict 9:16 Safe Zones**: Keep top `8%`, right `14%`, and bottom `22%` clear of critical graphics, HUD text, and subtitles.
     - **Vertical HUD & Subtitles**: Stack HUD in `top: 9%–15%`. Anchor vertical subtitles in `24%–28%` from bottom (max 2 lines, `<= 14` Chinese chars/line, effective font size `>= 13px` at `360px` mobile preview).
- **Determinism & Anti-Static Rule**:
  - Zero `Math.random()` or `Date.now()`. All Brownian thermal collisions, phonon shockwaves, and fractal radiator branches must be pure deterministic functions of `useCurrentFrame()` and seeded indices.
  - **3-Second Motion Rule**: No shot or title card may remain static for `> 180 frames (3s)`. Continuously evolve piston compression, thermal distortion waves, or 3D camera perspective.
- **Color Palette & Aesthetic**:
  - Void Background: `#050811` (`bt709`, anti-banding subtle grid).
  - Pure Logic / Cryogenic Superconducting State ($2.725\text{ K}$): `#06b6d4` (Electric Cyan).
  - Biological 20W Warmth ($300\text{ K}$): `#f59e0b` (Amber Gold).
  - Landauer Friction / Trapped Planetary Infrared ($> 330\text{ K}$): `#ef4444` (Crimson Heat) & `#f97316` (Molten Orange).
  - Exact Physical Laws & Constants: `#facc15` (Sacred Gold) & `#ffffff`.

---

# 2. Persistent Top HUD Telemetry (Zero Typos)
Ensure exact spelling and dynamic scaling across all frames:
- **Left HUD — Ambient Reservoir & Bit Erasure Cost (`#f59e0b` -> `#ef4444` -> `#06b6d4`)**:
  - `AMBIENT TEMP (T): 300.0 K` (climbs to `348.0 K [BIOSPHERE BOILING]` in Act 3, drops instantly to `2.725 K [DEEP SPACE CMB]` at Frame 5400)
  - `HEAT PER ERASED BIT: k_B·T·ln(2) = 2.87 × 10^-21 J` (drops 110x to `2.60 × 10^-23 J` in Act 4)
- **Right HUD — Compute Power vs. Planetary Venting Limit (`#facc15` -> `#ef4444`)**:
  - `ACTIVE SI POWER: 20 W (HUMAN) -> 1.50 × 10^16 W (PLANETARY SATURATION)`
  - `EARTH RADIATIVE CEILING: 4πR²σT⁴ [TRAPPED BY ATMOSPHERE]`

---

# 3. Three-Track Script, TTS Phonetic Lexicon & Psychoacoustic SFX
Maintain separate structures for `original_script`, `display_subtitle`, and `tts_phonetic_text`. Lock windows to real decoded PCM durations:

| Seg ID | Time / Frame Window | Display Subtitle (`display_subtitle`) | TTS Phonetic Input (`tts_phonetic_text`) | Procedural SFX Anchor & Psychoacoustics (`sfx_events.json`) |
| :--- | :--- | :--- | :--- | :--- |
| **S01** | `00:02 - 00:10`<br>`120 - 600f` | 你此时此刻闪过的每一个念头，<br>都在让宇宙变热一点点。 | 你此时此刻，闪过的每一个念头，都在让宇宙，变热一点点。 | `120f`: Intimate neural spark followed by a subtle warm thermal exhale |
| **S02** | `00:11 - 00:21`<br>`660 - 1260f` | 因为在物理学眼里，“遗忘”从不是免费的。<br>每抹掉一比特旧记忆，就像用铁锤在原子间砸出一团火。 | 因为在物理学眼里，遗忘，从不是免费的。每抹掉一比特旧记忆，就像用铁锤，在原子间砸出一团火。 | `900f`: Heavy hydraulic piston slam + high-velocity particle ricochet + infrared shockwave |
| **S03** | `00:22 - 00:30`<br>`1320 - 1800f` | 这就是兰道尔极限：<br>一道由热力学第二定律焊死的宇宙铁幕。 | 这就是兰道尔极限：一道由热力学第二定律，焊死的宇宙铁幕。 | `1350f`: Colossal metallic seal (`40Hz` sub-drop) + sizzling red laser brand |
| **S04** | `00:31 - 00:43`<br>`1860 - 2580f` | 人类大脑只耗电二十瓦，像一盏温热的床头灯；<br>而当超级智能以万亿倍的速度狂飙，它撞上了那块烧红的天花板。 | 人类大脑，只耗电二十瓦，像一盏温热的床头灯；而当超级智能，以万亿倍的速度狂飙，它撞上了那块，烧红的天花板。 | `2200f`: Gentle 20W hum overtaken by a roaring, accelerating turbine pitch hitting a hard brickwall |
| **S05** | `00:45 - 00:58`<br>`2700 - 3480f` | 哪怕把芯片造到一颗原子的极致，<br>每一次逻辑推演，依然在疯狂喷涌无法消灭的废热。 | 哪怕把芯片，造到一颗原子的极致；每一次逻辑推演，依然在疯狂喷涌，无法消灭的废热。 | `3000f`: Dense Geiger-like bit-flip crackle morphing into an oppressive, rising pink-noise furnace roar |
| **S06** | `01:01 - 01:14`<br>`3660 - 4440f` | 真正锁死超级智能的，从来不是缺电，而是散热。<br>地球的表面积太小，大气层像一口盖死的高压锅。 | 真正锁死超级智能的，从来不是缺电，而是散热。地球的表面积太小，大气层，像一口盖死的高压锅。 | `3780f`: Claustrophobic low-frequency pressure throb + trapped infrared reflection echoes |
| **S07** | `01:15 - 01:29`<br>`4500 - 5340f` | 散不出去的红外辐射在天空下疯狂反弹。<br>在耗尽太阳能量之前，神明的脑热，就会先一步煮沸整座生物圈。 | 散不出去的红外辐射，在天空下疯狂反弹。在耗尽太阳能量之前，神明的脑热，就会先一步，煮沸整座生物圈。 | `4800f`: Thermal noise reaches suffocating peak intensity + critical biosphere alarm (`#ef4444`) |
| **S08** | `01:31 - 01:44`<br>`5460 - 6240f` | 为了活下去，超级智能唯一的宿命，<br>就是逃离温暖的母星，潜入零下 270 度的冰冷深空。 | 为了活下去，超级智能唯一的宿命，就是逃离温暖的母星，潜入零下二百七十度的，冰冷深空。 | `5400f`: **100% INSTANTANEOUS CUT OF ALL THERMAL NOISE** -> 25 frames of pure vacuum silence -> weightless, crystalline superconducting chime |
| **S09** | `01:46 - 01:55`<br>`6360 - 6900f` | “这或许就是宇宙如此寂静的原因：<br>最高等的智慧从不喧哗，它们正躲在最寒冷的黑暗里静默思考。” | 这或许就是宇宙如此寂静的原因：最高等的智慧，从不喧哗，它们正躲在最寒冷的黑暗里，静默思考。 | `6480f`: Ethereal, zero-friction cosmic pipe organ chord fading into infinite space |
| **S10** | `01:56 - 02:00`<br>`6960 - 7200f` | 下一次观测：主权心印。<br>`[EP.06 当算法比你更懂你]` | 下一次观测，主权心印。 | `7020f`: Close-up human heartbeat echoed 500ms early by a cyan synthetic pulse |

---

# 4. Four-Act Visceral & Mathematical Choreography (`7,200` Frames)

## Act 1: The Microscopic Hammer of Forgetting (`Frames 0 - 1800` | `0:00 - 0:30`)
- **Frames 0 - 1260 (Szilard Piston Compression & Quartic Barrier Collapse)**:
  - Render an intimate, high-contrast 3D/2D hybrid **Szilard Phase-Space Chamber** coupled with the exact quartic Double-Well potential curve $U(x) = U_0[(x/x_0)^4 - 2\alpha(t)(x/x_0)^2]$.
  - Initially, 60 cyan particles (`STATE |0⟩` and `STATE |1⟩`) drift calmly across the full chamber width ($\Omega = 2V$).
  - At frame `660`, execute `MEMORY OVERWRITE (RESET -> |0⟩)`: A massive golden hydraulic piston wall slams inward from the right, compressing the available phase-space volume in half ($\Omega \to V$).
  - **Visceral Physics**: As the space halves, the trapped particles' **velocity vector arrows ($\vec{v}$) turn crimson (`#ef4444`) and double in length and wall-collision frequency**. Every collision against the surrounding silicon lattice sends violent red acoustic phonon ripples outward (`ΔQ >= k_B · T · ln(2) = 2.87 zJ`).
- **Frames 1260 - 1800 (Dynamic Title Card — Anti-Static)**:
  - The vibrating red silicon lattice tilts backward in 3D (`perspective(1200px) rotateX(55deg)`) like a glowing bed of coals receding into the void.
  - Center Title Card:
    - Main Title: `兰 道 尔 极 限`
    - Subtitle: `T H E   L A N D A U E R   L I M I T`
    - Exact Formula Tag: `[ ΔQ >= k_B · T · ln(2)  //  Every Erased Bit Bleeds Heat ]`

## Act 2: The 20W Candle vs. The Red-Hot Iron Ceiling (`Frames 1800 - 3600` | `0:30 - 1:00`)
- **Frames 1800 - 2600 (The 20W Biological Miracle)**:
  - On the lower-left of a vast logarithmic energy-efficiency canyon, render a warm, gentle pulsing amber sphere (`#f59e0b`): `[HUMAN BRAIN: 20 WATTS // A WARM BEDTIME LAMP]`.
- **Frames 2600 - 3600 (Slamming into the Landauer Wall)**:
  - Camera pans rapidly up and right as thousands of cyan SI compute trajectories scream upward along **Koomey's Law**, accelerating toward the top of the screen.
  - Across the top of the frame sits an unyielding, white-hot crimson horizontal barrier (`#ef4444`) at $3.48 \times 10^{20}\text{ ops/J}$: `[THE LANDAUER WALL @ 300K: THERMODYNAMIC IRON CURTAIN]`.
  - As the cyan beams slam violently against this horizontal ceiling, they cannot penetrate it—instead, the kinetic energy deflects downward as a torrential rain of molten orange/red thermal embers (`#f97316` / `#ef4444`) that begins flooding the bottom of the screen.

## Act 3: The Planetary Pressure Cooker (`Frames 3600 - 5400` | `1:00 - 1:30`)
- **Adaptive Split-Screen / Planetary Cross-Section**:
  - `Landscape4K`: Left 65% shows the atmospheric cross-section of Earth trapping infrared rays; Right 35% shows the **Planck Blackbody Radiation Curve $B_\lambda(\lambda, T)$** surging and redline-saturating.
  - `PortraitVertical`: Top 60% Earth atmospheric pressure-cooker; Bottom 40% Planck curve & Stefan-Boltzmann gauge (strictly inside 9:16 safe zones).
- **Frames 3600 - 5400 (Stefan-Boltzmann Suffocation)**:
  - Render the curved crust of Earth studded with glowing SI compute megastructures firing massive red/orange heat plumes ($P_{\text{compute}} \to 10^{16}\text{ W}$) skyward.
  - Above the crust, render the translucent atmospheric shell (`4πR²σT⁴ RADIATIVE BOTTLENECK`). Watch as 85% of the outgoing red infrared arrows hit the atmospheric shell and **ricochet back down toward the ground**, turning the air between crust and sky into a blinding, shimmering crimson furnace.
  - Apply a subtle procedural SVG displacement / heat-haze wave across the entire frame as `AMBIENT TEMP (T)` climbs past `330 K` -> `348 K [BIOSPHERE LETHAL LIMIT]`, synced with the suffocating pink-noise audio build-up.

## Act 4: The 2.7K Deep-Space Escape & The Silent Universe (`Frames 5400 - 7200` | `1:30 - 2:00`)
- **Frames 5400 - 6300 (The Great Cryogenic Exodus & Audio Drop)**:
  - At **Frame `5400`** (synced with the **100% total cut of thermal noise into pure vacuum silence**), the crimson heat haze vanishes instantly.
  - The camera shoots away from the glowing red Earth into the pitch-black, ice-cold shadow cone of **Sun-Earth Lagrange Point L2** (`AMBIENT TEMP: 2.725 K`).
  - In the equation $\Delta Q = k_B \cdot T \cdot \ln 2$ floating in the upper sky, watch the red symbol $T$ (`348 K`) shrink 120-fold into a tiny, serene ice-cyan crystal (`2.725 K`).
  - At the center of the void, unfold a breathtaking, mathematically exact **Murray's Law Fractal Radiator Wing** ($r_p^3 = r_1^3 + r_2^3$, 7 levels of recursive branching in cyan and gold) spanning across the starfield, freely venting faint infrared photons into the infinite $2.725\text{ K}$ cosmic sink with zero atmospheric reflection.
- **Frames 6300 - 6930 (The Fermi Paradox Revelation & Closing Title)**:
  - Camera slowly orbits the silent, majestic fractal superstructure floating in deep space, while distant stars twinkle like other hidden cryogenic minds across the galaxy.
  - Foreground quote: `"这或许就是宇宙如此寂静的原因：最高等的智慧从不喧哗，它们正躲在最寒冷的黑暗里静默思考。"`
  - Closing title card: `兰 道 尔 极 限` (`THE LANDAUER LIMIT`).
- **Frames 6930 - 7200 (EP.06 Cliffhanger — Sovereign Soul Crystal)**:
  - Cut from cosmic deep space directly into an intimate human neural waveform. A cyan SI prediction shadow traces the human's decision path `500 ms` *before* the amber human spark even fires (`[LIBET READINESS POTENTIAL LOCKED]`), until a golden cryptographic polyhedron snaps shut around the human core.
  - Subtitle: `下一次观测：主权心印 [EP.06 当算法比你更懂你]`.

---

# 5. Execution, Rendering & Acceptance QA Checklist
1. Synthesize or reuse cached narration segments using `tts_phonetic_text`, verify real PCM sample counts, and mix with procedural BGM + `sfx_events.json` (ensuring the rising thermal pink-noise floor from `1800f–5399f` cuts **100% cleanly to dead silence at Frame `5400`**) into the exact `120.00s` (`5,760,000` samples/ch @ 48kHz) stereo PCM master (`<= -1.0 dBTP`).
2. Run static typo scan on all HUD strings, equations, and subtitles (`LANDAUER`, `BOLTZMANN`, `RADIATIVE`, `ATMOSPHERE`, `BIOSPHERE`).
3. Render both final MP4s (`3840x2160` for Bilibili and `9:16` for Xiaohongshu) serially into the paths defined in `delivery.json`.
4. Run `python3 <skill_dir>/scripts/validate_delivery.py <work_dir>` (full strict decode), measure `ebur128=peak=true` LUFS/dBTP, extract representative frames + pair-frame delta comparisons (`t` vs `t+2.5s`) + `360px` mobile preview from the final encoded MP4s, and write the complete evidence report to `review/acceptance.md`.