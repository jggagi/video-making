#!/usr/bin/env python3
"""Create the self-contained v3 editable project archive after full QA is complete."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import BinaryIO


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_ROOT = "si-eternity"
OUT_DIR = PROJECT_ROOT / "out"
PACKAGE_FORMAT = "si-eternity-v3-project-package"
ARCHIVE_NAME = "one-blink-ten-millennia-v3-project.zip"
EXTERNAL_MANIFEST_NAME = "package-v3-manifest.json"
CONTENTS_MANIFEST_NAME = f"{ARCHIVE_ROOT}/PACKAGE-CONTENTS.json"
CHUNK_SIZE = 1024 * 1024

ROOT_FILES = (
    "package.json",
    "package-lock.json",
    "tsconfig.json",
    ".gitignore",
    "README.md",
    "BRIEF.md",
    "TITLE-V3.md",
    "AUDIO-V2.md",
    "VALIDATION.md",
)
V2_METADATA = (
    "audio-v2/voice-plan.json",
    "audio-v2/voice-manifest.json",
    "audio-v2/preflight.json",
)
V2_PUBLIC_STEMS = (
    "public/audio-v2/ambient-score.wav",
    "public/audio-v2/sound-design.wav",
)
V3_PUBLIC_ASSETS = (
    "public/audio-v3/soundtrack.wav",
    "public/audio-v3/narration.wav",
    "public/audio-v3/voice-review.wav",
    "public/audio-v3/mix-manifest.json",
    "public/audio-v3/raw/voice-01.wav",
    "public/audio-v3/raw/voice-21.wav",
)
REPORT_FILES = (
    "out/render-source-v3-sha256.json",
    "out/title-v3-validation.json",
    "out/artifact-sha256.json",
    "out/voiced-v2-validation.json",
)
OPTIONAL_SCORE_MANIFEST = "public/audio-v2/manifest.json"

ARCHIVE_NOTES = [
    "Historical full-film and preview MP4 exports, prior project ZIPs, Remotion bundles, and node_modules are intentionally not packed.",
    "Full historical-validator checks that compare against earlier workspace MP4s require those prior workspace files to remain available.",
    "Rendering and audio mixing can run offline from this archive after its declared dependencies and bundled audio assets are available.",
]


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _reject_symlink_components(path: Path, root: Path) -> None:
    """Reject a symlink at the path or anywhere between it and the project root."""
    if not _is_within(path, root):
        raise ValueError(f"Path is outside the project: {path}")
    current = path
    while current != root:
        if current.is_symlink():
            raise ValueError(f"Symlinks are not allowed in the package: {current}")
        current = current.parent


def _project_file(relative: str) -> Path:
    """Resolve and validate one project-relative regular file."""
    rel = PurePosixPath(relative)
    if rel.is_absolute() or not rel.parts or ".." in rel.parts or "\\" in relative:
        raise ValueError(f"Invalid project-relative path: {relative!r}")
    candidate = PROJECT_ROOT.joinpath(*rel.parts)
    _reject_symlink_components(candidate, PROJECT_ROOT)
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Required package input is missing: {relative}") from exc
    if not _is_within(resolved, PROJECT_ROOT):
        raise ValueError(f"Resolved path is outside the project: {relative}")
    if not stat.S_ISREG(resolved.stat().st_mode):
        raise ValueError(f"Package input is not a regular file: {relative}")
    return resolved


def _archive_path(relative: str) -> str:
    return f"{ARCHIVE_ROOT}/{PurePosixPath(relative).as_posix()}"


def _add_file(files: dict[str, Path], relative: str) -> None:
    source = _project_file(relative)
    archive_name = _archive_path(relative)
    previous = files.get(archive_name)
    if previous is not None and previous != source:
        raise ValueError(f"Two package inputs map to {archive_name}")
    files[archive_name] = source


def _load_voice_plan(files: dict[str, Path]) -> dict[str, object]:
    plan_path = _project_file("audio-v3/voice-plan.json")
    with plan_path.open("r", encoding="utf-8") as handle:
        plan = json.load(handle)
    cues = plan.get("cues") if isinstance(plan, dict) else None
    if not isinstance(cues, list) or len(cues) != 22:
        raise ValueError("audio-v3/voice-plan.json must contain exactly 22 cues")

    cue_files: list[str] = []
    cue_ids: set[str] = set()
    for cue in cues:
        if not isinstance(cue, dict):
            raise ValueError("Every v3 voice cue must be a JSON object")
        cue_id = cue.get("id")
        cue_file = cue.get("file")
        if not isinstance(cue_id, str) or cue_id in cue_ids:
            raise ValueError(f"Missing or duplicate v3 voice cue id: {cue_id!r}")
        if not isinstance(cue_file, str):
            raise ValueError(f"Cue {cue_id} does not name an audio file")
        cue_ids.add(cue_id)
        cue_files.append(cue_file)

    if len(set(cue_files)) != 22:
        raise ValueError("The v3 voice plan must reference 22 distinct cue files")
    for cue_file in cue_files:
        _add_file(files, cue_file)
    return plan


def _collect_files() -> tuple[dict[str, Path], dict[str, object]]:
    files: dict[str, Path] = {}

    for relative in ROOT_FILES:
        _add_file(files, relative)

    src_dir = PROJECT_ROOT / "src"
    _reject_symlink_components(src_dir, PROJECT_ROOT)
    if not src_dir.is_dir():
        raise FileNotFoundError("Required source directory is missing: src")
    for path in sorted(src_dir.rglob("*")):
        if path.suffix in {".ts", ".tsx"}:
            _add_file(files, path.relative_to(PROJECT_ROOT).as_posix())

    scripts_dir = PROJECT_ROOT / "scripts"
    _reject_symlink_components(scripts_dir, PROJECT_ROOT)
    if not scripts_dir.is_dir():
        raise FileNotFoundError("Required scripts directory is missing: scripts")
    for pattern in ("*.mjs", "*.py"):
        for path in sorted(scripts_dir.glob(pattern)):
            _add_file(files, path.relative_to(PROJECT_ROOT).as_posix())

    audio_v3_dir = PROJECT_ROOT / "audio-v3"
    _reject_symlink_components(audio_v3_dir, PROJECT_ROOT)
    if not audio_v3_dir.is_dir():
        raise FileNotFoundError("Required audio directory is missing: audio-v3")
    for path in sorted(audio_v3_dir.iterdir()):
        if path.suffix.lower() in {".json", ".txt"}:
            _add_file(files, path.relative_to(PROJECT_ROOT).as_posix())

    for relative in V2_METADATA + V3_PUBLIC_ASSETS + V2_PUBLIC_STEMS + REPORT_FILES:
        _add_file(files, relative)

    optional_score_manifest = PROJECT_ROOT / OPTIONAL_SCORE_MANIFEST
    if optional_score_manifest.is_symlink():
        raise ValueError(f"Symlinks are not allowed in the package: {OPTIONAL_SCORE_MANIFEST}")
    if optional_score_manifest.exists():
        _add_file(files, OPTIONAL_SCORE_MANIFEST)

    plan = _load_voice_plan(files)
    return dict(sorted(files.items())), plan


def _sha256_stream(stream: BinaryIO) -> str:
    digest = hashlib.sha256()
    while chunk := stream.read(CHUNK_SIZE):
        digest.update(chunk)
    return digest.hexdigest()


def _sha256_file(path: Path) -> tuple[str, int]:
    with path.open("rb") as handle:
        digest = hashlib.sha256()
        byte_count = 0
        while chunk := handle.read(CHUNK_SIZE):
            digest.update(chunk)
            byte_count += len(chunk)
    return digest.hexdigest(), byte_count


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _make_contents_manifest(files: dict[str, Path]) -> tuple[bytes, dict[str, str]]:
    hashes: dict[str, str] = {}
    for archive_name, source in files.items():
        hashes[archive_name] = _sha256_file(source)[0]
    manifest = {
        "format": PACKAGE_FORMAT,
        "manifestVersion": 1,
        "archiveRoot": f"{ARCHIVE_ROOT}/",
        "files": [
            {"path": archive_name, "sha256": hashes[archive_name]}
            for archive_name in sorted(hashes)
        ],
        "notes": ARCHIVE_NOTES,
        "selfHash": "Omitted because a file cannot contain its own SHA-256; the external package manifest records it.",
    }
    return _json_bytes(manifest), hashes


def _ensure_out_dir() -> None:
    _reject_symlink_components(OUT_DIR, PROJECT_ROOT)
    if not OUT_DIR.is_dir():
        raise FileNotFoundError("The project out/ directory must exist before packaging")


def _temp_file(directory: Path, prefix: str, suffix: str) -> Path:
    fd, name = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=directory)
    os.close(fd)
    return Path(name)


def _write_temp_bytes(path: Path, content: bytes) -> None:
    with path.open("wb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def _write_and_verify_archive(
    stage_path: Path,
    files: dict[str, Path],
    source_hashes: dict[str, str],
    contents_manifest: bytes,
) -> dict[str, str]:
    with zipfile.ZipFile(
        stage_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
        allowZip64=True,
    ) as archive:
        for archive_name, source in files.items():
            archive.write(
                source,
                arcname=archive_name,
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=6,
            )
        archive.writestr(
            CONTENTS_MANIFEST_NAME,
            contents_manifest,
            compress_type=zipfile.ZIP_DEFLATED,
            compresslevel=6,
        )

    expected_hashes = dict(source_hashes)
    expected_hashes[CONTENTS_MANIFEST_NAME] = hashlib.sha256(contents_manifest).hexdigest()
    archive_hashes: dict[str, str] = {}
    with zipfile.ZipFile(stage_path, mode="r", allowZip64=True) as archive:
        corrupt_entry = archive.testzip()
        if corrupt_entry is not None:
            raise ValueError(f"ZIP CRC verification failed for {corrupt_entry}")
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(names) != len(set(names)):
            raise ValueError("ZIP contains duplicate entry names")
        if set(names) != set(expected_hashes):
            missing = sorted(set(expected_hashes) - set(names))
            unexpected = sorted(set(names) - set(expected_hashes))
            raise ValueError(f"ZIP entry set mismatch; missing={missing}, unexpected={unexpected}")

        for entry in entries:
            with archive.open(entry, "r") as stream:
                actual_hash = _sha256_stream(stream)
            expected_hash = expected_hashes[entry.filename]
            if actual_hash != expected_hash:
                raise ValueError(f"ZIP stream hash mismatch for {entry.filename}")
            archive_hashes[entry.filename] = actual_hash
    return dict(sorted(archive_hashes.items()))


def main() -> None:
    if len(sys.argv) != 1:
        raise SystemExit("Usage: python3 scripts/package-v3.py")

    _ensure_out_dir()
    target_path = OUT_DIR / ARCHIVE_NAME
    external_manifest_path = OUT_DIR / EXTERNAL_MANIFEST_NAME
    if target_path.exists() or target_path.is_symlink():
        raise FileExistsError(f"Refusing to overwrite existing archive: {target_path}")
    if external_manifest_path.is_symlink():
        raise ValueError(f"Refusing to replace symlink: {external_manifest_path}")

    files, _plan = _collect_files()
    contents_manifest, source_hashes = _make_contents_manifest(files)
    stage_archive = _temp_file(OUT_DIR, ".one-blink-ten-millennia-v3-project.", ".tmp.zip")
    stage_manifest: Path | None = None
    archive_published = False
    try:
        archive_hashes = _write_and_verify_archive(
            stage_archive, files, source_hashes, contents_manifest
        )
        archive_sha256, archive_bytes = _sha256_file(stage_archive)
        external_manifest = {
            "format": PACKAGE_FORMAT,
            "manifestVersion": 1,
            "archive": ARCHIVE_NAME,
            "archiveBytes": archive_bytes,
            "archiveSha256": archive_sha256,
            "fileCount": len(archive_hashes),
            "fileHashes": archive_hashes,
            "contentsManifest": CONTENTS_MANIFEST_NAME,
            "notes": ARCHIVE_NOTES,
        }
        stage_manifest = _temp_file(OUT_DIR, ".package-v3-manifest.", ".tmp")
        _write_temp_bytes(stage_manifest, _json_bytes(external_manifest))

        if target_path.exists() or target_path.is_symlink():
            raise FileExistsError(f"Refusing to overwrite existing archive: {target_path}")
        os.replace(stage_archive, target_path)
        archive_published = True
        try:
            os.replace(stage_manifest, external_manifest_path)
            stage_manifest = None
        except OSError:
            if target_path.exists() and _sha256_file(target_path)[0] == archive_sha256:
                target_path.unlink()
                archive_published = False
            raise

        print(f"Created {target_path}")
        print(f"Archive SHA-256: {archive_sha256}")
        print(f"Archive bytes: {archive_bytes}")
        print(f"Files: {len(archive_hashes)} (including PACKAGE-CONTENTS.json)")
        print(f"Manifest: {external_manifest_path}")
    finally:
        if stage_archive.exists():
            stage_archive.unlink()
        if stage_manifest is not None and stage_manifest.exists():
            stage_manifest.unlink()
        # A failed external-manifest commit must not leave an untracked archive behind.
        if archive_published and not external_manifest_path.exists() and target_path.exists():
            target_path.unlink()


if __name__ == "__main__":
    main()
