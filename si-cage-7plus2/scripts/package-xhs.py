#!/usr/bin/env python3
"""Create the separate EP02 Xiaohongshu v1 source and QA package."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
ARCHIVE = OUT / "cage-of-seven-plus-two-xhs-v1-project.zip"
REPORT = OUT / "xhs-v1-package-manifest.json"
LEDGER_NAME = "source-file-hashes.json"
ARCHIVE_ROOT = "si-cage-7plus2/"
PREVIEW_PATTERN = "*xhs-v1*preview*.mp4"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def required_project_files() -> list[Path]:
    files = {
        ROOT / name
        for name in [
            "package.json",
            "package-lock.json",
            "tsconfig.json",
            "timeline.json",
            "xhs-timeline.json",
            "generate-audio-ep2.js",
            "README.md",
            "UHD-V3.md",
            "VOICED-V2.md",
            "XHS-V1.md",
            ".gitignore",
            "out/voiced-v2-mix-manifest.json",
            "out/xhs-v1-before.json",
            "out/xhs-v1-audio-manifest.json",
            "out/xhs-v1-validation.json",
            "out/cage-of-seven-plus-two-xhs-v1-cover-3x4.jpg",
            "out/xhs-v1-cover-4k.png",
            "out/cage-of-seven-plus-two-xhs-v1-zh.srt",
            "public/audio-xhs-v1/soundtrack.wav",
        ]
    }
    for folder in [
        "src",
        "scripts",
        "public/audio",
        "audio-voiced-v2",
        "public/audio-voiced-v2",
        "public/audio-xhs-v1",
    ]:
        base = ROOT / folder
        if base.is_dir():
            files.update(path for path in base.rglob("*") if path.is_file())

    for pattern in ["xhs-v1-*.json", "xhs-v1-*.png", "xhs-v1-post.txt"]:
        files.update(path for path in OUT.glob(pattern) if path.is_file())
    files.update(path for path in OUT.glob(PREVIEW_PATTERN) if path.is_file())

    excluded_roots = {
        (ROOT / "node_modules").resolve(),
        (OUT / "bundle").resolve(),
        (OUT / "bundle-uhd-v3").resolve(),
    }
    excluded_paths = {
        ARCHIVE.resolve(),
        REPORT.resolve(),
        (OUT / "cage-of-seven-plus-two-xhs-v1-4k.mp4").resolve(),
        (OUT / "cage-of-seven-plus-two-xhs-v1-1080x1920.mp4").resolve(),
    }

    def should_include(path: Path) -> bool:
        resolved = path.resolve()
        if resolved in excluded_paths:
            return False
        if any(resolved == root or root in resolved.parents for root in excluded_roots):
            return False
        parts = {part.lower() for part in path.parts}
        name = path.name.lower()
        if "__pycache__" in parts or name == ".ds_store":
            return False
        if any(part in {".aws", "credentials", "secrets"} for part in parts):
            return False
        if name.startswith("credential") or name.startswith("secret"):
            return False
        if name.startswith(".env") or name.endswith((".pem", ".key", ".p12", ".pfx")):
            return False
        if name.endswith(".zip"):
            return False
        if "bundle" in parts or any(part.startswith("bundle-") for part in parts):
            return False
        if path.suffix.lower() in {".mp4", ".mov", ".m4v"} and not fnmatch.fnmatch(path.name, PREVIEW_PATTERN):
            # Full movies and unrelated historical previews stay outside the source package.
            return False
        return True

    return sorted((path for path in files if path.is_file() and should_include(path)),
                  key=lambda path: path.relative_to(ROOT).as_posix())


def check_validation_readiness() -> dict:
    validation_path = OUT / "xhs-v1-validation.json"
    if not validation_path.is_file():
        raise SystemExit("Missing local XHS v1 validation report; run scripts/validate-xhs.py first")
    report = json.loads(validation_path.read_text(encoding="utf-8"))
    if report.get("status") != "PASS":
        raise SystemExit("XHS v1 validation report is not PASS; refusing to package")
    results = report.get("results", {})
    required_results = [
        "sourceBaseline",
        "audioManifestAndClipTiming",
        "narrationUnityGainDualMono",
        "nineStageHarmonicStackAndHardGate",
        "overloadStemDigitalZeroAfterNoise",
        "pcmMasterLengthAndOpeningNoise",
        "digitalZeroFrames48To66",
        "masterProbe",
        "publishProbe",
        "strictFullDecodeBothMovies",
        "masterRepresentativeFramesInSameDecodePass",
        "masterEncodedAudioMatchesPcm",
        "publishEncodedAudioMatchesPcm",
        "aacPacketsIdenticalAcrossMovies",
        "coverDimensions",
        "captionsPresent",
    ]
    failures = [key for key in required_results if results.get(key) != "PASS"]
    if failures:
        raise SystemExit("XHS v1 validation report is missing required local PASS results: "
                         + ", ".join(failures))
    return {
        "automatedLocalChecks": "PASS",
        "humanListening": results.get("humanListening", "PENDING"),
        "continuousVisualReview": results.get("continuousVisualReview", "PENDING"),
        "actualPlatformUpload": results.get("actualPlatformUpload", "PENDING"),
        "asr": results.get("asr", "NOT_PERFORMED"),
        "cloudServices": results.get("cloudServices", "NOT_USED"),
    }


def validate_preview(path: Path) -> None:
    """Keep any optional packaged preview short enough to remain a compact QA sample."""
    import subprocess

    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise SystemExit(f"Cannot inspect optional XHS preview {path.name}: "
                         + result.stderr.decode(errors="replace")[-2000:])
    duration = float(json.loads(result.stdout)["format"]["duration"])
    if duration > 15.0:
        raise SystemExit(f"Optional XHS preview is not compact (over 15 s): {path.name}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a separate, hash-verified source/QA archive for the XHS v1 edition."
    )
    parser.add_argument("--xhs", action="store_true",
                        help="create the XHS v1 archive without including either full movie")
    args = parser.parse_args()
    if not args.xhs:
        parser.error("choose --xhs to create the separate Xiaohongshu v1 archive")

    if ARCHIVE.exists() or REPORT.exists():
        existing = ARCHIVE if ARCHIVE.exists() else REPORT
        raise SystemExit(f"Refusing to overwrite an existing XHS v1 archive or manifest: {existing}")

    acceptance = check_validation_readiness()
    required = [
        ROOT / "README.md",
        ROOT / "UHD-V3.md",
        ROOT / "VOICED-V2.md",
        ROOT / "XHS-V1.md",
        ROOT / "xhs-timeline.json",
        ROOT / "out/voiced-v2-mix-manifest.json",
        ROOT / "out/xhs-v1-audio-manifest.json",
        ROOT / "out/xhs-v1-validation.json",
        ROOT / "public/audio-xhs-v1/soundtrack.wav",
        ROOT / "public/audio-voiced-v2/soundtrack.wav",
    ]
    missing = [path.relative_to(ROOT).as_posix() for path in required if not path.is_file()]
    if missing:
        raise SystemExit("Missing required XHS v1 package inputs: " + ", ".join(missing))

    previews = [path for path in OUT.glob(PREVIEW_PATTERN) if path.is_file()]
    for path in previews:
        validate_preview(path)

    files = required_project_files()
    for path in required:
        if path not in files:
            raise SystemExit(f"Required package input would be excluded: {path.relative_to(ROOT)}")
    ledger = {
        path.relative_to(ROOT).as_posix(): sha256_file(path)
        for path in files
    }

    OUT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARCHIVE, mode="x", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=5) as output:
        for path in files:
            output.write(path, ARCHIVE_ROOT + path.relative_to(ROOT).as_posix())
        output.writestr(ARCHIVE_ROOT + LEDGER_NAME,
                        json.dumps(ledger, indent=2, ensure_ascii=False) + "\n")

    with zipfile.ZipFile(ARCHIVE) as package:
        bad_member = package.testzip()
        if bad_member is not None:
            raise SystemExit(f"Archive CRC verification failed: {bad_member}")
        expected_members = {ARCHIVE_ROOT + name for name in ledger}
        expected_members.add(ARCHIVE_ROOT + LEDGER_NAME)
        actual_members = set(package.namelist())
        if actual_members != expected_members:
            raise SystemExit("Archive member ledger mismatch; unexpected or missing files are present")
        for relative_path, digest in ledger.items():
            archived = package.read(ARCHIVE_ROOT + relative_path)
            if sha256_bytes(archived) != digest:
                raise SystemExit(f"Archive hash verification failed: {relative_path}")
        forbidden = [name for name in actual_members
                     if "/node_modules/" in name or "/bundle/" in name
                     or "/bundle-uhd-v3/" in name or name.endswith("package-manifest.json")]
        if forbidden:
            raise SystemExit("Archive contains excluded build or self-reference files: "
                             + ", ".join(sorted(forbidden)))

    report = {
        "edition": "EP02 Xiaohongshu portrait short v1",
        "archive": str(ARCHIVE),
        "files": len(ledger),
        "sha256": sha256_file(ARCHIVE),
        "archiveFileLedger": LEDGER_NAME,
        "verifiedCrcAndAllFileHashes": True,
        "fullMoviesIncluded": False,
        "compactPreviewFiles": [path.relative_to(ROOT).as_posix() for path in previews],
        "oldVoicedV2MasterIncludedForStudioCompositions": True,
        "humanAcceptance": acceptance,
        "historyArchivesIncluded": False,
        "credentialsIncluded": False,
    }
    with REPORT.open("x", encoding="utf-8") as output:
        json.dump(report, output, indent=2, ensure_ascii=False)
        output.write("\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
