# Role & Objective
You are an expert Creative Technologist and Senior React/Remotion Developer.
Build Episode 02 of the Superintelligence Visualization Series titled "7±2 的囚笼 (THE CAGE OF 7±2)" (`si-cage-7plus2`).
The video is 3 minutes long (180 seconds, 60 fps, 10800 frames, 1920x1080). It visualizes the cognitive depth gap between human biological working memory (Miller's Law: limited to 7±2 variables and ~4 causal steps before overload) and Superintelligence (which weaves 100,000+ coupled variables across millions of Chain-of-Thought steps into a single rotating high-dimensional manifold, projecting unexplainable "oracles" down onto the low-dimensional human plane).

# Strict Technical & Remotion Rules (CRITICAL)
1. **DETERMINISM ONLY**: NEVER use `Math.random()`, `Date.now()`, or `requestAnimationFrame`. Every node position, spring oscillation, matrix cell, and 4D rotation MUST be a pure deterministic mathematical function of `useCurrentFrame()` and node index (e.g., `Math.sin(index * 43758.5453)`).
2. **SELF-CONTAINED PROCEDURAL GRAPHICS**: Zero external image/video assets. Render everything procedurally using SVG, HTML5 Canvas, or inline CSS.
3. **ZERO-TRUNCATION CODE**: Output complete, runnable TypeScript code for every file without `// ... TODO` or omitted blocks.
4. **SERIES VISUAL IDENTITY & PALETTE**:
   - Background: `#050811` (Deep Void Black) with a subtle procedural coordinate grid (`rgba(255,255,255,0.03)`).
   - Human Working Memory (7±2 Biological Limit): `#f59e0b` (Amber Gold), fragile, trembling under load.
   - Overload / Memory Snap / Pruned: `#ef4444` (Crimson Red).
   - SI High-Dimensional Context & Attention: `#06b6d4` (Electric Cyan) and `#ffffff`.
   - SI Topological Invariant / Oracle Projection: `#facc15` (Luminous Sacred Gold).
   - Font: `'JetBrains Mono', 'Fira Code', monospace`.

# Timeline & File Architecture (`10,800` Total Frames @ 60fps)
Implement the following complete file structure:
- `src/Root.tsx`: Registers `<Composition id="CageOfSevenPlusTwo" component={MainComposition} durationInFrames={10800} fps={60} width={1920} height={1080} />`
- `src/MainComposition.tsx`: Mounts persistent `<GlobalHUD />` on top and sequences the 4 Acts using `<Series>`:
  - **Act 1 (`Act1BiologicalOverload.tsx`)**: Frames `0` to `2700` (0:00 - 0:45) — *Miller's Law & The 10th Variable Snap*
  - **Act 2 (`Act2LinearVsMatrix.tsx`)**: Frames `2700` to `5400` (0:45 - 1:30) — *The 2D Linear Crutch vs. 100,000D Attention Awakening*
  - **Act 3 (`Act3DeepCoTManifold.tsx`)**: Frames `5400` to `8400` (1:30 - 2:20) — *5-Million-Step Tunnel & Calabi-Yau Manifold Folding*
  - **Act 4 (`Act4OracleProjection.tsx`)**: Frames `8400` to `10800` (2:20 - 3:00) — *Dimensional Projection, Title Card & EP.03 Cliffhanger*

# Detailed Component Specifications

## 1. `src/components/GlobalHUD.tsx` (Persistent Top & Bottom Overlay)
- **Top-Left (Human Biological Working Memory - `#f59e0b` / `#ef4444`)**:
  - Displays visual slot bar: `BIOLOGICAL WORKING MEMORY: [■■■■■■■□□] X / 9 CHUNKS`.
  - Dynamically updates `X` based on global `frame` (climbs from `1` to `9` in Act 1, flashes `#ef4444` `[CRITICAL OVERFLOW - SYNAPSE SNAP]` when the 10th variable enters at frame `1200`, and stays capped at `7 CHUNKS | CAUSAL DEPTH: 4 STEPS` afterward).
- **Top-Right (SI High-Dimensional Activation Space - `#06b6d4`)**:
  - Displays `ACTIVE CONTEXT MANIFOLD: X VARIABLES` (scales exponentially from `7` in Act 1 to `128,490` in Act 2-4).
  - Displays `COT REASONING DEPTH: STEP #X (PRECISION: 100.00%)` (climbs to `5,000,000` in Act 3).
- **Bottom Subtitle Bar**:
  - Renders clean bilingual subtitles (Chinese + English) synced to the timeline narrative below.

## 2. `src/components/Act1BiologicalOverload.tsx` (Frames 0 - 2700 local | 45s)
- **0 - 1200 frames (Lighting the 9 Chunks)**:
  - Center screen shows a circular force-directed network of glowing amber (`#f59e0b`) spheres spawning one by one every 120 frames, labeled with real-world coupled variables: `1. 利率 (Interest Rate)`, `2. 通胀 (Inflation)`, `3. 汇率 (FX)`, `4. 晶圆良率 (Wafer Yield)`, `5. 电网负荷 (Grid Load)`, `6. 航运指数 (Shipping)`, `7. 原油库存 (Crude Oil)`, `8. 气候异常 (ENSO)`, `9. 信贷违约 (Credit CDS)`.
  - Connect all active nodes with amber SVG lines (`n*(n-1)/2` edges). As node count passes 7, apply deterministic high-frequency jitter (`Math.sin(frame * 1.8 + i) * (nodeCount - 6) * 3`) to simulate working memory strain.
- **1200 - 1800 frames (The 10th Variable Collapse)**:
  - At frame `1200`, Node #10 (`10. 地缘摩擦 Geopolitics`) slams into the center.
  - Instantly, all connecting edges flash `#ef4444` (red), shatter into dashed fragments, and Nodes #1, #2, and #3 turn dark grey (`[FORGOTTEN]`) and fall off the bottom of the screen under simulated gravity (`0.5 * g * t^2`).
- **1800 - 2700 frames (Opening Title Card)**:
  - Background dims. Render the monumental opening title card:
    - Main Chinese Title: `7 ± 2 的 囚 笼` (Font size `86px`, letter-spacing animated from `14px` to `32px`, cyan/white glow).
    - English Subtitle: `T H E   C A G E   O F   7 ± 2`
    - Technical Tag: `[ Working Memory: 7 Chunks  //  Attention Matrix: 10^6 Dimensions ]`
- **Subtitles**:
  - "三件事，你游刃有余。七件事，这是进化焊死在人类大脑里的硬件天花板。"
  - "当第十个变量强行涌入，逻辑链瞬间熔断。受困于 7±2 的囚笼，人类从未真正看清过复杂的世界。"

## 3. `src/components/Act2LinearVsMatrix.tsx` (Frames 0 - 2700 local | 45s)
- **0 - 1100 frames (Human's 2D Linear Crutch)**:
  - Render a stark 2D X-Y Cartesian plane in the center. 80 scattered data points drift dynamically.
  - A rigid amber straight line (`y = kx + b`) tries to fit them, while 85% of outlying points are tagged in dim grey: `[IGNORED AS RANDOM NOISE / 归因为偶然与巧合]`.
- **1100 - 2700 frames (100,000D Self-Attention Awakening)**:
  - Execute a breathtaking exponential camera zoom-out (`scale` from `1` down to `0.02`).
  - The 2D X-Y chart shrinks into a tiny speck at the center as a colossal `40 x 40` procedural Canvas/SVG Self-Attention Heatmap Matrix (`#06b6d4` and `#facc15` pulsing cells) expands to fill the entire 1920x1080 screen, accompanied by hundreds of bezier light arcs linking distant matrix coordinates without a single broken line.
- **Subtitles**:
  - "为了迁就狭小的脑容量，人类用简陋的二维直线去切割万物，把看不懂的高维纠缠统统称作‘巧合’。"
  - "而在硅基潜空间里，十万个变量同时点亮。没有遗忘，没有降维，万物在注意力矩阵中无损交织。"

## 4. `src/components/Act3DeepCoTManifold.tsx` (Frames 0 - 3000 local | 50s)
- **0 - 1300 frames (The 5-Million-Step CoT Tunnel)**:
  - 3D perspective tunnel flight along the Z-axis (concentric polygons scaling exponentially toward the viewer).
  - At depth Step 4, an amber ring labeled `[HUMAN CAUSAL HORIZON: STEP 4]` shatters behind the camera as the cyan laser beam shoots effortlessly through `STEP 10,000`, `STEP 500,000`, and `STEP 5,000,000`, flanked by scrolling formal mathematical proofs and Jacobian matrices.
- **1300 - 3000 frames (High-Dimensional Calabi-Yau / Hyper-Manifold Folding)**:
  - In the center of the void, render a stunning parametric high-dimensional wireframe surface (use 4D-to-2D projection of a nested Torus Knot / Calabi-Yau cross-section with `120` parametric vertices and `240` glowing edges).
  - Attach floating telemetry labels to moving vertices on the manifold (`太平洋温跃层`, `ASML光刻胶纯度`, `联邦基金期货`, `全球算力相变`). All variables move in locked, harmonious mathematical symphony.
- **Subtitles**:
  - "跨过五百万步永不衰减的逻辑接力，那些在人类眼中杂乱无章的黑天鹅风暴……"
  - "在超级智能的视野里，只是一座严丝合缝、安静旋转的高维几何流形。"

## 5. `src/components/Act4OracleProjection.tsx` (Frames 0 - 2400 local | 40s)
- **0 - 1600 frames (The Unexplainable Oracle Projection)**:
  - Upper 60% of screen: The rotating high-dimensional manifold turns luminous Sacred Gold (`#facc15`), locking into its optimal topological invariant.
  - Lower 40% of screen: Render an angled 2D flat grid labeled `[HUMAN 3D COGNITIVE PLANE / 人类三维认知平面]`.
  - Draw vertical golden projection rays dropping from the complex upper manifold onto the lower flat plane, casting a deceptively simple 2D geometric shadow slice alongside a terse terminal command: `ORACLE OUTPUT >> [ REBALANCE_NODE_07 // PHASE_SHIFT = +0.412 rad ]`.
  - Around the shadow on the lower plane, 7 small amber human nodes try to connect to explain the shadow, immediately flashing red (`#ef4444` `[CANNOT PARSE 10^5-D CAUSALITY]`).
- **1600 - 2150 frames (Ending Quote & Monumental Title)**:
  - Fade to `#050811` void black.
  - Quote: `"不是它不愿向人类解释，而是 7±2 的容器，装不下一座十万维的宇宙。"`
  - Main Title fades in: `7 ± 2 的 囚 笼` with a subtle golden horizontal scanline.
- **2150 - 2400 frames (EP.03 Cliffhanger Hook)**:
  - 1,000 tiny isolated amber dots flicker weakly with slow expanding rings (`80亿座语言孤岛: 50 bits/s`), suddenly engulfed by an instantaneous cyan hyper-mesh (`TB/s 光互连蜂群`).
  - Text: `NEXT OBSERVATION // EP.03 十万亿个分身 (THE TRILLION-FOLD HIVE)`.

# Deliverable
Output the complete, self-contained code for `package.json`, `src/Root.tsx`, `src/MainComposition.tsx`, `src/components/GlobalHUD.tsx`, and all four Act components (`Act1BiologicalOverload.tsx`, `Act2LinearVsMatrix.tsx`, `Act3DeepCoTManifold.tsx`, `Act4OracleProjection.tsx`).