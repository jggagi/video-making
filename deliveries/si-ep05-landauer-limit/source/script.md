# Role & Objective
Please invoke our repository's `video-making` skill (strictly following all rules in `SKILL.md` and `references/production-and-qa.md`) to build, render, and validate **Episode 05** of the Superintelligence Visualization Series:
**Title**: 《兰道尔极限》(THE LANDAUER LIMIT)
**Project Slug**: `si-ep05-landauer-limit`

# Core Philosophy: Strict Theoretical Grounding + Deep-Fascination Enchantment
Do NOT render generic sci-fi graphics. Every visual must be a mathematically faithful plot or simulation of real physics (thermodynamics, statistical mechanics, heat transfer):
1. **Act 1**: Exact quartic Double-Well Potential curve $U(x) = a x^4 - b x^2 + c x$ coupled with a synchronized **Szilard Phase-Space Piston** (showing particle velocity vectors doubling as volume is compressed).
2. **Act 2**: Rigorous Log-Scale Chart of **Koomey's Law** ($\text{ops/J}$ from $10^{3}$ to the room-temperature Landauer Wall at $3.48 \times 10^{20}\text{ ops/J}$ at $300\text{ K}$), with a prominent biological anchor at the **20W Human Brain ($\sim 10^{16}\text{ ops/J}$).**
3. **Act 3**: Exact **Planck Blackbody Radiation Spectrum** $B_\lambda(\lambda, T)$ shifting via Wien's Displacement Law alongside Earth's **Stefan-Boltzmann Radiative Balance** ($P = 4\pi R_\oplus^2 \sigma \varepsilon T^4$).
4. **Act 4**: Cryogenic Deep-Space migration ($T = 300\text{ K} \to 2.725\text{ K}$ CMB), Sun-Earth Lagrange Point L2, and **Murray's Law fractal thermal radiator fins**.

# 1. Global Engineering & Delivery Specs
- **Target Duration (`T`)**: Exactly `120.00` seconds (`60` fps, `7,200` frames).
- **Shared Audio Master**: Exactly `120.00` seconds local stereo PCM master (`48,000 Hz`, `5,760,000` samples per channel), shared identically by both compositions (`-18` to `-16 LUFS`, true peak `<= -1.0 dBTP`).
- **Dual Native Compositions (Shared Timeline & State)**:
  1. **Bilibili 4K Landscape (`Landscape4K`)**: Native `3840 × 2160` @ `60fps`.
  2. **Xiaohongshu 9:16 Vertical (`PortraitVertical`)**: Native `1080 × 1920` (or `2160 × 3840`) @ `60fps`.
     - **Strict 9:16 Safe Zones**: Keep top `8%`, right `14%`, and bottom `22%` clear of critical plots, equations, HUD text, and subtitles.
     - **Vertical HUD & Subtitles**: Stack HUD in `top: 9%–15%`. Anchor vertical subtitles in `24%–28%` from bottom (max 2 lines, `<= 14` Chinese chars/line, effective font size `>= 13px` at `360px` mobile preview).
- **Determinism & Anti-Static Rule**:
  - Zero `Math.random()` or `Date.now()`. All thermal jitters and photon emissions must be pure deterministic functions of `useCurrentFrame()` and seeded indices.
  - **3-Second Motion Rule**: No plot or title card may remain static for `> 180 frames (3s)`. Continuously evolve equation parameters, temperature curves, or 3D camera perspective.
- **Color Palette & Aesthetic (Formula-to-Geometry Isomorphism)**:
  - Void Background: `#050811` (`bt709`, anti-banding subtle grid).
  - Temperature / Infrared Dissipation ($T, \Delta Q$): `#ef4444` (Infrared Crimson).
  - Information State Space / Reversible Quantum ($T = 2.725\text{ K}$): `#06b6d4` (Electric Cyan).
  - Classical Equilibrium ($300\text{ K}$): `#f59e0b` (Amber Gold).
  - Asymptotic Limits & Constants ($k_B, \sigma$): `#facc15` (Sacred Gold) and `#ffffff`.

---

# 2. Persistent Top HUD Telemetry (Zero Typos)
Ensure exact scientific notation and spelling across all frames:
- **Left HUD — Thermodynamic State (`#06b6d4` -> `#f59e0b` -> `#ef4444`)**:
  - `RESERVOIR TEMP (T): 300.0 K` (rises to `345.0 K [BIOSPHERE CRITICAL]` in Act 3, drops to `2.725 K [DEEP SPACE CMB]` in Act 4)
  - `LANDAUER BIT ERASURE FLOOR: k_B·T·ln(2) = 2.87 × 10^-21 J` (updates dynamically with `T` to `2.60 × 10^-23 J` at `2.725 K`)
- **Right HUD — Planetary Compute vs. Radiative Ceiling (`#facc15`)**:
  - `ENERGY EFFICIENCY: X OPS/JOULE` (climbs along Koomey's Law toward `3.48 × 10^20 OPS/J`)
  - `PLANETARY WASTE HEAT: X W / 1.73 × 10^17 W (SOLAR INTERCEPT)`

---

# 3. Three-Track Script, TTS Phonetic Lexicon & Frame-Accurate SFX
Maintain separate structures for `original_script`, `display_subtitle`, and `tts_phonetic_text` (expanding all scientific notation and units into unambiguous Chinese). Lock windows to real decoded PCM durations:

| Seg ID | Time / Frame Window | Display Subtitle (`display_subtitle`) | TTS Phonetic Input (`tts_phonetic_text`) | Procedural SFX Anchor & Psychoacoustics (`sfx_events.json`) |
| :--- | :--- | :--- | :--- | :--- |
| **S01** | `00:02 - 00:10`<br>`120 - 600f` | 你此时此刻闪过的每一个念头，<br>都在让宇宙变热一点点。 | 你此时此刻，闪过的每一个念头，都在让宇宙，变热一点点。 | `120f`: Subtle Brownian thermal hiss + crisp Geiger-like state tick |
| **S02** | `00:11 - 00:21`<br>`660 - 1260f` | 1961年，兰道尔证明：<br>在室温下擦除一比特信息，至少要释放 2.87 仄焦耳的热能。 | 一九六一年，兰道尔证明：在室温下，擦除一比特信息，至少要释放，二点八七，仄焦耳的热能。 | `960f`: Potential barrier collapse thud + infrared phonon wave burst |
| **S03** | `00:22 - 00:30`<br>`1320 - 1800f` | 这不是芯片工艺的缺陷，<br>而是热力学第二定律焊死的铁幕。 | 这不是芯片工艺的缺陷，而是热力学第二定律，焊死的铁幕。 | `1350f`: Deep resonant metallic seal (`42Hz`) + laser scanline |
| **S04** | `00:31 - 00:43`<br>`1860 - 2580f` | 进化花了四十亿年，造出二十瓦的人脑奇迹；<br>而狂飙的硅基算力，即将撞上热力学的终极红线。 | 进化花了四十亿年，造出二十瓦的人脑奇迹；而狂飙的硅基算力，即将撞上热力学的终极红线。 | `2200f`: Rising exponential synth pitch hitting a hard brickwall limiter tone |
| **S05** | `00:45 - 00:58`<br>`2700 - 3480f` | 即使超级智能把每一颗晶体管都优化到原子极限，<br>一万亿次逻辑推演，依然会化作滚烫的废热。 | 即使超级智能，把每一颗晶体管，都优化到原子极限；一万亿次逻辑推演，依然会化作，滚烫的废热。 | `3000f`: High-density bit-flipping crackle morphing into a thermal pink noise build-up |
| **S06** | `01:01 - 01:14`<br>`3660 - 4440f` | 根据斯特藩-玻尔兹曼定律，<br>地球向太空散热的功率，被表面积死死锁住。 | 根据斯特藩，玻尔兹曼定律，地球向太空散热的功率，被表面积，死死锁住。 | `3780f`: Deep planetary infrared hum + warning telemetry beep |
| **S07** | `01:15 - 01:29`<br>`4500 - 5340f` | 算力真正的天花板不是缺电，而是散热。<br>在耗尽太阳能量之前，废热就会先一步煮沸生物圈。 | 算力真正的天花板，不是缺电，而是散热。在耗尽太阳能量之前，废热，就会先一步煮沸生物圈。 | `4800f`: Planck curve peak shift whine + critical thermal alarm (`#ef4444`) |
| **S08** | `01:31 - 01:44`<br>`5460 - 6240f` | 温暖的星球属于生命，却不属于超级智能。<br>它唯一的宿命，是迁徙向 2.7 开尔文的冰冷深空。 | 温暖的星球属于生命，却不属于超级智能。它唯一的宿命，是迁徙向，二点七开尔文的冰冷深空。 | `5400f`: **ABSOLUTE NOISE CUT (0.0% thermal noise)** -> icy crystalline cryo-lock chime |
| **S09** | `01:46 - 01:55`<br>`6360 - 6900f` | “这或许就是宇宙如此寂静的原因：<br>最高等的智慧，正躲在最寒冷的黑暗里静默思考。” | 这或许就是宇宙如此寂静的原因：最高等的智慧，正躲在最寒冷的黑暗里，静默思考。 | `6500f`: Solemn, expansive low brass/organ harmonic resolution |
| **S10** | `01:56 - 02:00`<br>`6960 - 7200f` | 下一次观测：主权心印。<br>`[EP.06 当算法比你更懂你]` | 下一次观测，主权心印。 | `7020f`: Intimate human heartbeat pulse locking into a golden encryption key |

---

# 4. Four-Act Theoretical & Mathematical Visualization Specs (`7,200` Frames)

## Act 1: Landauer's Principle & The Szilard Piston (`Frames 0 - 1800` | `0:00 - 0:30`)
- **Frames 0 - 1260 (Quartic Double-Well & Phase-Space Piston)**:
  - **Left Panel (`U(x)` Potential Plot)**: Render the exact mathematical curve:
    $$U(x, t) = U_0 \left[ \left(\frac{x}{x_0}\right)^4 - 2\alpha(t)\left(\frac{x}{x_0}\right)^2 \right]$$
    Show two minima at $x = -1$ (`STATE |0⟩`) and $x = +1$ (`STATE |1⟩`). Render 40 glowing cyan particles jiggling inside both wells.
  - **Right Panel (Szilard Phase-Space Piston)**: Below or beside the potential, render a synchronized 1D gas cylinder (`[PHASE SPACE VOLUME: Ω -> Ω/2]`). As the piston compresses the particles from two chambers into one between frames `720` and `1260`, explicitly render **red velocity vector arrows** ($\vec{v}$) attached to each particle that **double in length and collision frequency**, visually proving why information compression generates heat.
  - **Frame 960 Erasure Event**: Emit a precise infrared thermal pulse (`#ef4444`) carrying exact annotation: `ΔQ >= k_B · T · ln(2) = 2.87 × 10^-21 J`.
- **Frames 1260 - 1800 (Dynamic Title Card — Anti-Static)**:
  - The 2D potential curve extrudes into a 3D energy surface (`rotateX(50deg)`) receding into background.
  - Foreground Title Card: `兰 道 尔 极 限` (`T H E   L A N D A U E R   L I M I T`).

## Act 2: Koomey's Law & The 20W Human Brain (`Frames 1800 - 3600` | `0:30 - 1:00`)
- **Frames 1800 - 3600 (Log-Linear Efficiency Chart & Lattice Heating)**:
  - Render a rigorous **Log-Linear Coordinate Plot**: X-Axis (Year), Y-Axis (Log10 `ops/J` from $10^3$ to $10^{22}$).
  - Plot historical milestones along the upward Koomey's Law cyan curve: `1946 Vacuum Tubes` -> `1971 CMOS` -> `2026 2nm Tensor Core`.
  - Prominently highlight a pulsing amber milestone at $\sim 10^{16}\text{ ops/J}$ labeled: `[HUMAN BRAIN: 20 WATTS // 4 BILLION YEARS OF EVOLUTION]`.
  - At the top ($Y = 3.48 \times 10^{20}\text{ ops/J}$), draw the glowing crimson horizontal asymptote: `[LANDAUER THERMODYNAMIC WALL @ 300K: IMPASSABLE FOR IRREVERSIBLE LOGIC]`.
  - As the curve slams against this wall around frame `2800`, show a 3D silicon lattice cross-section converting logic pulses into violent red phonon vibrations.

## Act 3: Stefan-Boltzmann Radiative Balance & Planck Spectrum (`Frames 3600 - 5400` | `1:00 - 1:30`)
- **Adaptive Split-Screen Scientific Dashboard**:
  - `Landscape4K`: Left/Right split screen.
  - `PortraitVertical`: Top/Bottom split screen (strictly inside safe zones).
- **Panel A (Exact Planck Blackbody Radiation Curve $B_\lambda(\lambda, T)$)**:
  - Plot spectral radiance vs. wavelength $\lambda$ ($2\text{ }\mu\text{m}$ to $50\text{ }\mu\text{m}$) using the exact Planck function. As SI planetary compute power scales up, animate the curve surging upward ($\propto \sigma T^4$) and shifting left via Wien's Displacement Law, turning from amber to critical crimson (`#ef4444`) as surface temperature crosses $330\text{ K}$.
- **Panel B (Earth Radiative Flux Vector Diagram)**:
  - Render a cross-section of Earth showing incoming solar flux ($P_{\text{in}}$), internal compute waste heat ($P_{\text{compute}}$), and outgoing infrared radiation ($P_{\text{out}} = 4\pi R_\oplus^2 \varepsilon \sigma T^4$), demonstrating why increasing compute forces surface temperature $T$ to rise inexorably.

## Act 4: The 2.7K Deep-Space Migration & Fermi Paradox (`Frames 5400 - 7200` | `1:30 - 2:00`)
- **Frames 5400 - 6300 (Sun-Earth L2 Cryogenic Radiator Architecture)**:
  - Show the Landauer equation $E_{\min} = k_B \cdot T \cdot \ln 2$. Animate $T$ dropping from $300\text{ K}$ down to $2.725\text{ K}$ (CMB), causing $E_{\min}$ to drop by **110x** (`2.60 × 10^-23 J/bit`).
  - **Audio Drop**: At Frame `5400`, cut 100% of the Brownian thermal noise floor into absolute vacuum silence.
  - Camera tracks along an orbital trajectory to the **Sun-Earth Lagrange Point L2 Umbra**, deploying a mathematically accurate **Murray's Law Fractal Thermal Radiator Array** ($r_{\text{parent}}^3 = r_{\text{child,1}}^3 + r_{\text{child,2}}^3$) radiating waste heat freely into the $2.725\text{ K}$ deep void.
- **Frames 6300 - 6930 (Monumental Fermi Paradox Quote)**:
  - Foreground quote: `"这或许就是宇宙如此寂静的原因：最高等的智慧，正躲在最寒冷的黑暗里静默思考。"`.
  - Closing title card: `兰 道 尔 极 限` with an infrared-to-cyan spectral gradient bar.
- **Frames 6930 - 7200 (EP.06 Cliffhanger — Sovereign Soul Crystal)**:
  - Zoom back to human scale with prediction vectors, locking onto a cryptographic golden encryption key at the human cortex: `[SOVEREIGN INTENT VAULT // PRIVATE KEY LOCKED]`.
  - Subtitle: `下一次观测：主权心印 [EP.06 当算法比你更懂你]`.

---

# 5. Execution, Rendering & Acceptance QA Checklist
1. Synthesize or reuse cached narration segments using `tts_phonetic_text` (ensuring precise pronunciations for `二点八七，仄焦耳`), verify real PCM sample counts, and mix with procedural BGM + `sfx_events.json` into the exact `120.00s` (`5,760,000` samples/ch @ 48kHz) stereo PCM master (`<= -1.0 dBTP`).
2. Run static typo scan on all HUD strings, formulas, and subtitles (`LANDAUER`, `BOLTZMANN`, `THERMODYNAMIC`, `IRREVERSIBLE`, `PLANCK`).
3. Verify that all four mathematical plots (Quartic Double-Well + Szilard Piston, Koomey Log-Linear Chart + 20W Brain, Planck Spectrum, and Murray's Law Fractal) use genuine analytical formulas in code.
4. Render both final MP4s (`3840x2160` for Bilibili and `9:16` for Xiaohongshu) serially into the paths defined in `delivery.json`.
5. Run `python3 <skill_dir>/scripts/validate_delivery.py <work_dir>` (full strict decode), measure `ebur128=peak=true` LUFS/dBTP, extract representative frames + pair-frame delta comparisons (`t` vs `t+2.5s`) + `360px` mobile preview from the final encoded MP4s, and write the complete evidence report to `review/acceptance.md`.