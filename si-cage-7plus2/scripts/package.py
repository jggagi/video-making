#!/usr/bin/env python3
"""Build a new, self-contained source package for the UHD v3 edition."""

import argparse
import hashlib
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "out/cage-of-seven-plus-two-uhd-v3-project.zip"
REPORT = ROOT / "out/uhd-v3-package-manifest.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def collect_files() -> list[Path]:
    files = {
        ROOT / name
        for name in [
            "package.json",
            "package-lock.json",
            "tsconfig.json",
            "timeline.json",
            "generate-audio-ep2.js",
            "README.md",
            "UHD-V3.md",
            "BRIEF.md",
            "VALIDATION.md",
            "VOICED-V2.md",
            ".gitignore",
        ]
    }
    for folder in [
        "src",
        "scripts",
        "public/audio",
        "audio-voiced-v2",
        "public/audio-voiced-v2",
    ]:
        files.update(
            path
            for path in (ROOT / folder).rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.name != ".DS_Store"
        )

    output_dir = ROOT / "out"
    for pattern in ["uhd-v3-*.json", "uhd-v3-*.png", "uhd-v3-*.mp4"]:
        files.update(path for path in output_dir.glob(pattern) if path.is_file())
    chinese_captions = output_dir / "cage-of-seven-plus-two-uhd-v3-zh.srt"
    if chinese_captions.is_file():
        files.add(chinese_captions)

    # These compact historical receipts are inputs to validate-uhd.py.
    for name in ["uhd-v3-source-before.zip", "voiced-v2-mix-manifest.json", "voiced-v2-validation.json"]:
        path = output_dir / name
        if path.is_file():
            files.add(path)

    excluded = {
        ARCHIVE.resolve(),
        REPORT.resolve(),
        (output_dir / "cage-of-seven-plus-two-uhd-v3-4k.mp4").resolve(),
        (output_dir / "cage-of-seven-plus-two-score-v3-4k.mp4").resolve(),
    }
    return sorted(
        path
        for path in files
        if path.is_file()
        and path.resolve() not in excluded
        and not path.name.endswith("package-manifest.json")
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create a new UHD v3 project ZIP. Historical v1/v2 archives are "
            "intentionally not writable by this script."
        )
    )
    parser.add_argument(
        "--uhd",
        action="store_true",
        help="package the current 4K UHD v3 source and cached local audio",
    )
    args = parser.parse_args()
    if not args.uhd:
        parser.error(
            "choose --uhd to create the separate UHD v3 archive; historical "
            "v1/v2 ZIPs are preserved and cannot be rebuilt from current sources"
        )

    if ARCHIVE.exists() or REPORT.exists():
        raise SystemExit(
            "Refusing to overwrite an existing UHD v3 archive or manifest: "
            f"{ARCHIVE if ARCHIVE.exists() else REPORT}"
        )

    required = [
        ROOT / "UHD-V3.md",
        ROOT / "public/audio-voiced-v2/soundtrack.wav",
        ROOT / "audio-voiced-v2/asr-status.json",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("Missing required UHD v3 package inputs: " + ", ".join(missing))

    files = collect_files()
    ledger = {
        str(path.relative_to(ROOT)): sha256(path.read_bytes())
        for path in files
    }
    archive_root = "si-cage-7plus2/"

    with zipfile.ZipFile(
        ARCHIVE,
        mode="x",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=5,
    ) as output:
        for path in files:
            output.write(path, archive_root + str(path.relative_to(ROOT)))
        output.writestr(
            archive_root + "source-file-hashes.json",
            json.dumps(ledger, indent=2, ensure_ascii=False) + "\n",
        )

    with zipfile.ZipFile(ARCHIVE) as source:
        if source.testzip() is not None:
            raise SystemExit("Archive CRC verification failed")
        for relative_path, digest in ledger.items():
            archived = source.read(archive_root + relative_path)
            if sha256(archived) != digest:
                raise SystemExit(f"Archive hash verification failed: {relative_path}")

    report = {
        "edition": "UHD v3",
        "archive": str(ARCHIVE),
        "files": len(ledger),
        "sha256": sha256(ARCHIVE.read_bytes()),
        "verifiedCrcAndAllFileHashes": True,
        "fullMoviesIncluded": False,
        "historicalArchivesModified": False,
    }
    with REPORT.open("x", encoding="utf-8") as output:
        json.dump(report, output, indent=2, ensure_ascii=False)
        output.write("\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
