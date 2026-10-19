# Native-render revisions

The initial native exports met dimensions and duration, but actual encoded-frame review found two issues. In landscape, the ivory hand passed behind white captions; a landscape-only bottom light falloff improves contrast. Comparing encoded crystal frames with fresh stills then exposed a more material camera discrepancy.

Local R3F9.4 source showed that Canvas camera options initialize a camera instance and do not update its position/FOV from later plain option objects. The first full exports could retain frame0 camera values while fresh stills initialized at the selected frame. CameraAim now applies full position, perspective FOV, target and projection in a layout effect before Remotion's manual frame advance. Both full editions therefore need a new export.

A ten-second preview in each layout crossed the choice→crystal scene cut. Subject geometry at global5760 was compared with a fresh still. Raw SSIM was affected by native4K-downsample versus lower-resolution WebGL antialiasing; this diagnostic failure was retained. A blurred grayscale control yielded0.9953 in both fixed previews versus0.5377/0.4705 in the first exports. Visual inspection confirmed matching position, facet orientation, scale and plinth ellipse. See camera-regression-controlled.json for hashes and scope. Final native encoded frames are checked again separately.

The initial exports remain under review/iterations/landscape-first-pass and portrait-first-pass as previews. They are excluded from the local final library and GitHub final backup. Script, captions, PCM and mathematical model remain unchanged. The final source snapshot is render-settings.json. The final exports use two frame workers inside one render job, with landscape and portrait processed serially after fresh storage checks.

Final paired360px review additionally found the coffee hand could graze the single-line qualifier at withdrawn poses. Its portrait Act0 position was moved fromy1274 toy1320; it ends aty1367.6, before the caption box aty1383. Native extrema0/330/840 were reviewed. The earlier camera-correct portrait is retained as a preview; landscape pixels are unaffected.
