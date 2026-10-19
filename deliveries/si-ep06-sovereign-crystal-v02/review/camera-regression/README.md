# Camera regression evidence

Contact sheets have three columns: initial full export, fixed sequential preview after the act cut, and freshly initialized native still downsampled to the preview size. All show global frame5760. The first column has the wrong camera pose; the second and third align geometrically.

The raw SSIM diagnostic compares different render resolutions and did not meet its proposed threshold. A blurred control reduces antialiasing differences and, together with visual inspection, establishes the camera-pose correction; it is not a human aesthetic score. Final same-resolution encoded-frame comparison is recorded separately. Lossless control PNGs are retained in Git; compact JPEG contact sheets are included in the editable project package.
