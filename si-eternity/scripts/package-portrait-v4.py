#!/usr/bin/env python3
"""Package the portrait v4 source using the verified v3 packager."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PACKAGER_PATH = Path(__file__).resolve().with_name("package-v3.py")

PORTRAIT_V4_NOTES = [
    "This archive packages the native portrait v4 composition at 1080 x 1920, 180 seconds, 60 fps, and 10,800 frames.",
    "Portrait v4 reuses the exact v3 soundtrack, narration, all 22 v3 voice cue assets, and the existing v2 score and sound-design stems; no portrait-specific audio assets are added.",
    "Historical landscape exports, old full-film and preview MP4s, reference PNGs, previous project ZIPs, Remotion bundles, and node_modules are intentionally not packed.",
    "Full historical-validator checks requiring earlier MP4 exports and landscape reference PNGs require those original workspace files to remain available.",
    "Rendering and audio mixing can run offline from this archive after its declared dependencies and bundled audio assets are available.",
]


def main() -> None:
    if len(sys.argv) != 1:
        raise SystemExit("Usage: python3 scripts/package-portrait-v4.py")

    spec = importlib.util.spec_from_file_location("si_eternity_package_v3", PACKAGER_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load shared packager: {PACKAGER_PATH}")
    packager = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(packager)

    packager.PACKAGE_FORMAT = "si-eternity-portrait-v4-project-package"
    packager.ARCHIVE_NAME = "one-blink-ten-millennia-portrait-v4-project.zip"
    packager.EXTERNAL_MANIFEST_NAME = "package-portrait-v4-manifest.json"
    packager.ROOT_FILES = tuple(packager.ROOT_FILES) + ("PORTRAIT-V4.md",)
    packager.REPORT_FILES = tuple(packager.REPORT_FILES) + (
        "out/render-source-portrait-v4-sha256.json",
        "out/portrait-v4-validation.json",
    )
    packager.ARCHIVE_NOTES = PORTRAIT_V4_NOTES
    packager.main()


if __name__ == "__main__":
    main()
