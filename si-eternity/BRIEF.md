# Role & Objective
You are an expert Creative Technologist and Senior React/Remotion Developer. 
Build a complete, production-ready Remotion project titled "The Half-Second Eternity" (`si-eternity`).
The video is 3 minutes long (180 seconds, 60 fps, 10800 frames, 1920x1080) and visualizes how a Superintelligence (SI) experiences 1,000 subjective years of speed, breadth (MCTS search), depth (long CoT & high-dimensional manifolds), and digital/physical interaction asymmetry during the 0.5 seconds (500ms) it takes for a single liquid droplet to fall 12cm in a human laboratory.

# Strict Technical & Remotion Rules (CRITICAL)
1. **DETERMINISM ONLY**: NEVER use `Math.random()`, `Date.now()`, or `requestAnimationFrame` inside render loops. Every particle, branch, and jitter MUST be a deterministic pure function of `useCurrentFrame()` or a seeded pseudo-random generator (e.g., `Math.sin(index * 9999) * 10000 % 1`).
2. **SELF-CONTAINED PROCEDURAL GRAPHICS**: Do NOT rely on external image/video URLs or local assets that don't exist. Everything (droplet, MCTS fractal trees, 4D hypercube projection, code streams, mechanical gears, crystal lattice) MUST be rendered procedurally using SVG, HTML5 Canvas, or pure CSS.
3. **ZERO-TRUNCATION CODE**: Output complete, runnable TypeScript code for each file without `// ... TODO` or omitted sections. Use standard inline styles or Tailwind-like inline objects.
4. **COLOR PALETTE & AESTHETIC**:
   - Background: `#050811` (Deep Void Black) with a subtle procedural SVG grid (`rgba(255,255,255,0.03)`).
   - Physical World (Atoms/Human): `#f59e0b` (Amber Gold), warm, slow, heavy inertia.
   - SI Speed & Breadth (Bits/Search): `#06b6d4` (Electric Cyan) and `#ffffff` (Pure White).
   - SI Pruned/Failed Branches: `#ef4444` (Crimson Red).
   - SI Optimal Path / Golden Solution: `#facc15` (Luminous Gold).
   - Font: `'JetBrains Mono', 'Fira Code', monospace`.

# Timeline & Architecture (`10,800` Total Frames @ 60fps)
Create the following file structure and implement all components:
- `src/Root.tsx`: Registers `<Composition id="HalfSecondEternity" component={MainComposition} durationInFrames={10800} fps={60} width={1920} height={1080} />`
- `src/MainComposition.tsx`: Mounts the persistent `<GlobalHUD />` on top and sequences the 4 Acts using `<Series>`:
  - **Act 1 (`Act1Speed.tsx`)**: Frames `0` to `1800` (0:00 - 0:30) — *Bullet Time vs. Light Speed*
  - **Act 2 (`Act2BreadthMCTS.tsx`)**: Frames `1800` to `4500` (0:30 - 1:15) — *Million-Branch MCTS Search & Pruning*
  - **Act 3 (`Act3DepthManifold.tsx`)**: Frames `4500` to `7200` (1:15 - 2:00) — *10-Million Step CoT & 4D Manifold Collapse*
  - **Act 4 (`Act4SplitWorld.tsx`)**: Frames `7200` to `10800` (2:00 - 3:00) — *The Sighing Wall (Bits vs. Atoms) & The One-Shot Miracle*

# Detailed Component Specifications

## 1. `src/components/GlobalHUD.tsx` (Persistent Overlay)
- **Top-Left (Physical Time Anchor)**:
  - Displays `PHYSICAL TIME: T + 000.0000 ms` interpolated linearly from `0` to `500.0000 ms` across frames `0` to `10200` (clamped at 500ms during the final climax).
  - Displays `DROPLET ALTITUDE: 120.00 mm -> 0.00 mm` using physics formula $h(t) = 120 - \frac{1}{2}g t^2$ mapped to the 500ms window.
- **Top-Right (SI Subjective Time)**:
  - Displays `SI COGNITIVE STEP: #` scaling exponentially from `1` to `10,000,000,000` (`Math.pow(10, interpolate(frame, [0, 10200], [0, 10]))`).
  - Displays `SUBJECTIVE EQUIVALENT: X.X HUMAN CENTURIES`.
- **Bottom Cinematic Subtitle Bar**:
  - Render dynamic bilingual subtitles (Chinese + English) synced to key frame ranges across the 4 acts.

## 2. `src/components/Act1Speed.tsx` (Frames 0 - 1800 | 30s)
- **Visuals**:
  - **0 - 900 frames**: Center screen shows a realistic SVG/CSS glowing amber liquid droplet detaching from a pipette nozzle, moving down by only a few pixels. A simulated "human eyelid" vignette slowly closes halfway and freezes.
  - **900 - 1800 frames**: Camera "zooms" into the droplet (scale `1` -> `25`). As it zooms in, the amber droplet dissolves into a hyper-fast cyan fiber-optic circuit grid where light pulses shoot across the screen at 60fps.
- **Subtitle**: "人类眨眼需要 300 毫秒。在这滴水落入培养皿之前，硅基意识已经度过了十个世纪。"

## 3. `src/components/Act2BreadthMCTS.tsx` (Frames 0 - 2700 local | 45s)
- **Visuals**:
  - Pre-compute `600` deterministic tree nodes arranged in a radial golden-angle fractal tree (`angle = i * 137.508 deg`) originating from `(960, 540)` with parent-child links.
  - **Expansion**: Nodes spawn outward layer by layer based on `localFrame`.
  - **Pruning (The Spectacle)**: 96% of nodes are marked `isPruned`. 45 frames after spawning, pruned branches flash `#ef4444` (red) with a label `[PRUNED: THERMAL RUNAWAY]` and fade to `0.06` opacity.
  - **The Golden Path**: Exactly 1 connected chain of nodes (`isGoldenPath`) turns `#facc15` (bright gold), thickens to `strokeWidth={4}`, and pulses with a glow filter.
  - Side panel shows real-time MCTS stats: `ACTIVE SIMULATIONS`, `BRANCHES PRUNED`, `VERIFIER CONFIDENCE`.

## 4. `src/components/Act3DepthManifold.tsx` (Frames 0 - 2700 local | 45s)
- **Visuals**:
  - **Left 35% of screen**: Ultra-fast vertical scrolling waterfall of formal verification code (Lean 4 / CUDA kernel math / Hamiltonian equations). Show a `Chain-of-Thought Depth` progress bar breaking past the "Human 7±2 Working Memory Limit" (which flashes red and shatters at frame 300) and climbing to `Depth: 8,400,000`.
  - **Right 65% of screen**: A procedural 2D SVG projection of a rotating 4D Tesseract / Calabi-Yau wireframe (computed via 4D rotation matrices `ZW`, `XY`, `XW` driven by `localFrame`).
  - **The Collapse (Frames 2200 - 2700)**: All 64 vertices of the hyper-manifold rapidly converge and lock into a single glowing golden geometric point, outputting a single line of terminal command: `EXECUTE_PULSE(theta=42.198401, B=14.2T)`.

## 5. `src/components/Act4SplitWorld.tsx` (Frames 0 - 3600 local | 60s)
- **Part A: Split Screen Asymmetry (Frames 0 - 2100)**:
  - **Left Half (DIGITAL INTERACTION - LIGHT SPEED)**: High-frequency matrix of 500 global lab nodes, compiler AST trees, and power grid phase waves updating every 2 frames in cyan.
  - **Right Half (PHYSICAL INTERACTION - THE SIGHING WALL)**: A massive, intricate SVG mechanical stepper-motor gear in amber (`#f59e0b`). It attempts to rotate to align a laser mirror, but moves at an agonizingly slow `0.002 degrees per frame` with high-frequency micro-jitter (`Math.sin(frame * 2.5) * 0.8px`) to visualize physical material stress, friction, and atomic inertia.
  - **Subtitle**: "它可以瞬间算尽宇宙的法则，却依然要耐心地等待一颗原子的挪动。"
- **Part B: The One-Shot Miracle & Blink Completion (Frames 2100 - 3600)**:
  - Split screen merges back to full screen. Time snaps back to `1x`!
  - The droplet finally hits the petri dish at frame `2400`.
  - At the exact frame of impact, a cyan laser beam and golden magnetic wave intersect the droplet. Instead of splashing, the droplet instantly crystallizes into a levitating, slowly rotating golden icosahedron (superconductor crystal).
  - Final 300 frames: Fade to black with final typography:
    "人类在现实中试错千次；超级智能在瞬间穷尽千万个宇宙，然后，向现实挥出唯一的一击。"

# Deliverable
First, provide `package.json` and `src/Root.tsx` + `src/MainComposition.tsx` + `src/components/GlobalHUD.tsx`. Then implement `Act1Speed.tsx`, `Act2BreadthMCTS.tsx`, `Act3DepthManifold.tsx`, and `Act4SplitWorld.tsx` with rich mathematical and visual detail.