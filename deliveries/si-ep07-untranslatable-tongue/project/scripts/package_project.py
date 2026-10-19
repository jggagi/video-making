#!/usr/bin/env python3
"""Create a reproducible, editable EP07 project ZIP without rendered movies.

Only local files are read. The ZIP contains source, project code and metadata,
shared PCM audio, publication copy, captions, a cover, and compact QA. Every
included file is hashed before and during packaging, and the finished archive
is read back and checked before publication.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import tempfile
import wave
import zipfile
from typing import Any, BinaryIO


WORK_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_DIR = WORK_DIR / "project"
REVIEW_DIR = WORK_DIR / "review"
OUTPUT_NAME = "si-ep07-untranslatable-tongue-project.zip"
OUTPUT_PATH = WORK_DIR / OUTPUT_NAME
SIDECAR_PATH = REVIEW_DIR / "package-manifest.json"
SIDECAR_RELATIVE = "review/package-manifest.json"
INTERNAL_MANIFEST_NAME = "PACKAGE-MANIFEST.json"
EXPECTED_SLUG = "si-ep07-untranslatable-tongue"
ZIP_TIMESTAMP = (2026, 1, 1, 0, 0, 0)
CHUNK_BYTES = 1024 * 1024
REVIEW_FILE_LIMIT = 2 * 1024 * 1024
REVIEW_IMAGE_LIMIT = 1024 * 1024
SOURCE_SUFFIXES = {
    ".py", ".mjs", ".js", ".ts", ".tsx", ".jsx", ".css", ".html",
    ".md", ".json", ".srt", ".txt", ".csv", ".svg",
}
FONT_SUFFIXES = {".ttf", ".otf", ".woff", ".woff2", ".ttc"}
MOVIE_SUFFIXES = {".mp4", ".mov", ".webm", ".mkv", ".m4v", ".avi"}
BLOCKED_DIRS = {
    ".git", ".remotion", "node_modules", "__pycache__", "bundles", "bundle",
    "logs", "credentials", "secrets", "deps", "dependencies", "uploads",
    "user-uploads", "user-media-uploads", "media-uploads",
}
REQUIRED_FILES = (
    "delivery.json",
    "source/script.md",
    "project/README.md",
    "project/adapted-script.md",
    "project/brief.md",
    "project/scientific-notes.md",
    "project/assets-manifest.json",
    "project/audio-timing.json",
    "project/segments.json",
    "project/sfx_events.json",
    "project/timeline.json",
    "project/layout-contract.json",
    "project/package.json",
    "project/package-lock.json",
    "project/src/CanvasWorld.tsx",
    "project/src/Film.tsx",
    "project/src/Root.tsx",
    "project/src/index.ts",
    "project/scripts/build_audio.py",
    "project/scripts/package_project.py",
    "project/scripts/render.mjs",
    "project/scripts/synthesize.py",
    "project/scripts/synthesize_local.py",
    "project/scripts/verify_project.py",
    "project/public/audio/provider-manifest.json",
    "project/public/audio/master.wav",
    "project/public/audio/music.wav",
    "project/public/audio/narration.wav",
    "project/public/audio/premaster.wav",
    "project/public/audio/sfx.wav",
    "B站/captions.srt",
    "小红书/captions.srt",
    "小红书/publication-content.json",
    "小红书/publication-copy.md",
    "小红书/cover-frame-99.5s.png",
)


class PackageError(RuntimeError):
    """A required input is invalid or a safe package cannot be produced."""


@dataclass(frozen=True)
class FileRecord:
    archive_path: str
    source_path: Path
    size_bytes: int
    sha256: str
    device: int
    inode: int
    mtime_ns: int
    ctime_ns: int


@dataclass(frozen=True)
class ExistingPackageState:
    present: bool
    zip_size_bytes: int | None = None
    zip_sha256: str | None = None
    manifest_sha256: str | None = None


def _identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _safe_relative(relative: str) -> tuple[str, ...]:
    candidate = PurePosixPath(relative)
    if candidate.is_absolute() or not candidate.parts or any(
        part in ("", ".", "..") for part in candidate.parts
    ):
        raise PackageError(f"unsafe delivery path: {relative!r}")
    return candidate.parts


def _check_path(relative: str, *, required: bool) -> Path | None:
    """Return a regular file inside the delivery, rejecting symlink components."""
    parts = _safe_relative(relative)
    root_info = WORK_DIR.lstat()
    if stat.S_ISLNK(root_info.st_mode) or not stat.S_ISDIR(root_info.st_mode):
        raise PackageError(f"delivery root is not a real directory: {WORK_DIR}")
    current = WORK_DIR
    try:
        for part in parts[:-1]:
            current = current / part
            info = current.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                if required:
                    raise PackageError(f"required path has a symlink or non-directory parent: {relative}")
                return None
        path = current / parts[-1]
        info = path.lstat()
    except FileNotFoundError:
        if required:
            raise PackageError(f"required project file is missing: {relative}") from None
        return None
    except OSError as exc:
        if required:
            raise PackageError(f"cannot inspect {relative}: {exc}") from None
        return None
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        if required:
            raise PackageError(f"required project path is not a regular file: {relative}")
        return None
    try:
        resolved = path.resolve(strict=True)
        resolved_root = WORK_DIR.resolve(strict=True)
    except OSError as exc:
        if required:
            raise PackageError(f"cannot resolve {relative}: {exc}") from None
        return None
    try:
        resolved.relative_to(resolved_root)
    except ValueError:
        if required:
            raise PackageError(f"project file escapes delivery root: {relative}") from None
        return None
    return path


def _open_checked(path: Path, expected: os.stat_result | None = None) -> BinaryIO:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise PackageError(f"cannot safely open {path.relative_to(WORK_DIR)}: {exc}") from None
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise PackageError(f"source changed to a non-file: {path.relative_to(WORK_DIR)}")
        if expected is not None and _identity(opened) != _identity(expected):
            raise PackageError(f"source changed while packaging: {path.relative_to(WORK_DIR)}")
        return os.fdopen(descriptor, "rb")
    except Exception:
        os.close(descriptor)
        raise


def _hash_file(relative: str) -> tuple[str, int, os.stat_result]:
    path = _check_path(relative, required=True)
    assert path is not None
    before = path.lstat()
    digest = hashlib.sha256()
    count = 0
    with _open_checked(path, before) as stream:
        while block := stream.read(CHUNK_BYTES):
            digest.update(block)
            count += len(block)
        after_fd = os.fstat(stream.fileno())
    after_path = path.lstat()
    if _identity(before) != _identity(after_fd) or _identity(before) != _identity(after_path):
        raise PackageError(f"source changed during hash pass: {relative}")
    if count != before.st_size:
        raise PackageError(f"source byte count changed during hash pass: {relative}")
    return digest.hexdigest(), count, before


def _read_bytes(relative: str) -> bytes:
    path = _check_path(relative, required=True)
    assert path is not None
    before = path.lstat()
    with _open_checked(path, before) as stream:
        data = stream.read()
        after_fd = os.fstat(stream.fileno())
    after_path = path.lstat()
    if _identity(before) != _identity(after_fd) or _identity(before) != _identity(after_path):
        raise PackageError(f"source changed while reading: {relative}")
    if len(data) != before.st_size:
        raise PackageError(f"source byte count changed while reading: {relative}")
    return data


def _json(relative: str) -> dict[str, Any]:
    try:
        data = json.loads(_read_bytes(relative).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PackageError(f"cannot parse {relative}: {exc}") from None
    if not isinstance(data, dict):
        raise PackageError(f"{relative} must contain a JSON object")
    return data


def _review_file_allowed(relative: str, size: int) -> tuple[bool, str]:
    lowered = relative.lower()
    name = Path(relative).name.lower()
    if relative == SIDECAR_RELATIVE:
        return False, "package_manifest_sidecar"
    if any(marker in lowered for marker in ("/failed", "/tmp", "/temp", "/scratch", "/bundle")):
        return False, "temporary_or_failed_qa"
    suffix = Path(relative).suffix.lower()
    if suffix in {".json", ".md", ".csv"}:
        if size <= REVIEW_FILE_LIMIT:
            return True, "compact_review"
        return False, "review_file_over_size_limit"
    if suffix in {".jpg", ".jpeg"}:
        if size <= REVIEW_IMAGE_LIMIT:
            return True, "compact_review_image"
        return False, "review_image_over_size_limit"
    if suffix in MOVIE_SUFFIXES:
        return False, "rendered_movie_or_video_evidence"
    if suffix in {".png", ".webp", ".tif", ".tiff"}:
        return False, "large_or_frame_qa_image"
    if suffix in {".log", ".pyc", ".pyo"} or name.startswith("."):
        return False, "transient_or_hidden"
    return False, "not_selected_for_compact_qa"


def _classify(relative: str, size: int) -> tuple[bool, str]:
    parts = _safe_relative(relative)
    lowered_parts = tuple(part.lower() for part in parts)
    name = lowered_parts[-1]
    suffix = Path(relative).suffix.lower()

    if relative in {OUTPUT_NAME, SIDECAR_RELATIVE}:
        return False, "package_output_control"
    if any(part in BLOCKED_DIRS or part.startswith("bundle") for part in lowered_parts[:-1]):
        return False, "dependency_runtime_or_transient_directory"
    if any(part.startswith(".") for part in lowered_parts):
        return False, "hidden_or_local_configuration"
    if name == ".env" or name.startswith(".env.") or name.endswith(".env"):
        return False, "environment_or_credentials"
    if any(token in name for token in ("credential", "secret", "token")):
        return False, "credential_or_secret_named_file"
    if suffix in MOVIE_SUFFIXES:
        return False, "rendered_movie"
    if suffix in {".log", ".pyc", ".pyo"} or name.endswith(".tmp") or ".tmp." in name:
        return False, "runtime_log_or_temporary_file"
    if name.startswith(("failed-", "tmp-", "temp-", "scratch-", "bundle")):
        return False, "failed_or_temporary_artifact"

    if parts[0] == "review":
        return _review_file_allowed(relative, size)
    if relative == "project/audio-authorization.json":
        return False, "local_authorization_record"
    if relative.startswith("project/public/audio/"):
        if name.startswith("local-preview"):
            return False, "local_speech_preview"
        if suffix == ".wav":
            return True, "shared_pcm_audio"
        if suffix == ".json" and name != "audio-authorization.json":
            return True, "audio_provenance_manifest"
        return False, "raw_preview_or_non_pcm_audio"
    if relative.startswith("project/public/fonts/"):
        if suffix in FONT_SUFFIXES:
            return True, "project_font_asset"
        if suffix in SOURCE_SUFFIXES:
            return True, "font_metadata"
        return False, "unselected_public_asset"
    if relative.startswith("project/src/") or relative.startswith("project/scripts/"):
        if suffix in SOURCE_SUFFIXES:
            return True, "editable_project_source"
        return False, "unselected_project_runtime_file"
    if relative.startswith("project/"):
        if suffix in SOURCE_SUFFIXES:
            return True, "editable_project_source_or_manifest"
        return False, "unselected_project_asset"
    if relative in REQUIRED_FILES:
        return True, "required_delivery_asset"
    if relative in {"小红书/publication-record.json"}:
        return False, "account_state_record"
    if relative in {"小红书/publication-content.json", "小红书/publication-copy.md"}:
        return True, "publication_copy"
    if relative == "小红书/cover-frame-99.5s.png":
        return True, "publication_cover"
    if relative in {"B站/captions.srt", "小红书/captions.srt"}:
        return True, "platform_caption"
    return False, "not_selected_delivery_file"


def _walk_delivery() -> tuple[list[str], list[dict[str, Any]]]:
    """Inventory this delivery without traversing any symlink or blocked tree."""
    selected: list[str] = []
    excluded: list[dict[str, Any]] = []
    stack = [WORK_DIR]
    while stack:
        directory = stack.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name, reverse=True)
        except OSError as exc:
            raise PackageError(f"cannot list {directory.relative_to(WORK_DIR) or '.'}: {exc}") from None
        for entry in entries:
            path = Path(entry.path)
            relative = path.relative_to(WORK_DIR).as_posix()
            try:
                info = entry.stat(follow_symlinks=False)
            except OSError as exc:
                excluded.append({"path": relative, "reason": f"unreadable_metadata: {exc.__class__.__name__}"})
                continue
            lowered_name = entry.name.lower()
            if stat.S_ISLNK(info.st_mode):
                excluded.append({"path": relative, "reason": "symlink_not_followed"})
                continue
            if stat.S_ISDIR(info.st_mode):
                if lowered_name in BLOCKED_DIRS or lowered_name.startswith("bundle"):
                    excluded.append({"path": relative, "reason": "dependency_runtime_or_transient_directory"})
                    continue
                if lowered_name.startswith("."):
                    excluded.append({"path": relative, "reason": "hidden_or_local_configuration_directory"})
                    continue
                stack.append(path)
                continue
            if not stat.S_ISREG(info.st_mode):
                excluded.append({"path": relative, "reason": "non_regular_file"})
                continue
            if relative in {OUTPUT_NAME, SIDECAR_RELATIVE}:
                # These two outputs are control files, not archive inputs or exclusions.
                continue
            include, reason = _classify(relative, info.st_size)
            if include:
                selected.append(relative)
            else:
                excluded.append({"path": relative, "reason": reason})
    return sorted(set(selected)), sorted(excluded, key=lambda item: item["path"])


def _validate_inputs(selected: list[str]) -> dict[str, Any]:
    for relative in REQUIRED_FILES:
        if relative not in selected:
            _check_path(relative, required=True)
            raise PackageError(f"required project file was not selected by package policy: {relative}")

    delivery = _json("delivery.json")
    if delivery.get("slug") != EXPECTED_SLUG or WORK_DIR.name != EXPECTED_SLUG:
        raise PackageError(f"delivery slug must be {EXPECTED_SLUG}")
    source_record = delivery.get("script")
    if not isinstance(source_record, dict) or source_record.get("path") != "source/script.md":
        raise PackageError("delivery.json must identify source/script.md as the original script")
    source_hash, source_size, _ = _hash_file("source/script.md")
    expected_hash = source_record.get("sha256")
    if expected_hash != source_hash:
        raise PackageError(
            f"original source hash mismatch: delivery.json says {expected_hash}, measured {source_hash}"
        )

    expected_audio = {
        "master.wav": (48_000, 2, 2, 5_760_000),
        "music.wav": (48_000, 2, 2, 5_760_000),
        "narration.wav": (48_000, 2, 2, 5_760_000),
        "premaster.wav": (48_000, 2, 2, 5_760_000),
        "sfx.wav": (48_000, 2, 2, 5_760_000),
    }
    audio_shapes: dict[str, dict[str, Any]] = {}
    for name, expected in expected_audio.items():
        relative = f"project/public/audio/{name}"
        try:
            with wave.open(str(WORK_DIR / relative), "rb") as wav:
                actual = (
                    wav.getframerate(), wav.getnchannels(), wav.getsampwidth(),
                    wav.getnframes(),
                )
                compression = wav.getcomptype()
        except (OSError, wave.Error) as exc:
            raise PackageError(f"cannot inspect PCM audio {relative}: {exc}") from None
        if actual != expected or compression != "NONE":
            raise PackageError(
                f"{relative} must be uncompressed 48 kHz stereo PCM16/5,760,000 samples; got {actual} {compression}"
            )
        audio_shapes[name] = {
            "sample_rate": actual[0], "channels": actual[1], "sample_width_bytes": actual[2],
            "samples_per_channel": actual[3], "compression_type": compression,
        }

    return {
        "slug": EXPECTED_SLUG,
        "title": delivery.get("title", ""),
        "source_script": {
            "path": "source/script.md", "size_bytes": source_size,
            "expected_sha256": expected_hash, "measured_sha256": source_hash, "matches": True,
        },
        "audio": audio_shapes,
        "duration_seconds": delivery.get("duration_seconds"),
        "fps": delivery.get("fps"),
        "total_frames": delivery.get("total_frames"),
    }


def _snapshot(relative: str) -> FileRecord:
    path = _check_path(relative, required=True)
    assert path is not None
    digest, size, info = _hash_file(relative)
    return FileRecord(relative, path, size, digest, info.st_dev, info.st_ino, info.st_mtime_ns, info.st_ctime_ns)


def _record_identity(record: FileRecord) -> tuple[int, int, int, int, int]:
    return record.device, record.inode, record.size_bytes, record.mtime_ns, record.ctime_ns


def _assert_record_current(record: FileRecord) -> None:
    path = _check_path(record.archive_path, required=True)
    assert path is not None
    if _identity(path.lstat()) != _record_identity(record):
        raise PackageError(f"source changed after inventory: {record.archive_path}")


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(filename=name, date_time=ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info._compresslevel = 6
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    info.extra = b""
    info.comment = b""
    return info


def _write_source(archive: zipfile.ZipFile, record: FileRecord) -> None:
    path = _check_path(record.archive_path, required=True)
    assert path is not None
    before = path.lstat()
    if _identity(before) != _record_identity(record):
        raise PackageError(f"source changed after inventory: {record.archive_path}")
    digest = hashlib.sha256()
    count = 0
    with _open_checked(path, before) as source, archive.open(
        _zip_info(record.archive_path), mode="w", force_zip64=True
    ) as target:
        while block := source.read(CHUNK_BYTES):
            digest.update(block)
            count += len(block)
            target.write(block)
        after_fd = os.fstat(source.fileno())
    after_path = path.lstat()
    if _identity(before) != _identity(after_fd) or _identity(before) != _identity(after_path):
        raise PackageError(f"source changed during ZIP write: {record.archive_path}")
    if count != record.size_bytes or digest.hexdigest() != record.sha256:
        raise PackageError(f"source hash changed during ZIP write: {record.archive_path}")


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _hash_path(path: Path) -> tuple[int, str]:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise PackageError(f"refusing to inspect non-file package output: {path}")
    digest = hashlib.sha256()
    count = 0
    with _open_checked(path, info) as stream:
        while block := stream.read(CHUNK_BYTES):
            digest.update(block)
            count += len(block)
        after = os.fstat(stream.fileno())
    if _identity(info) != _identity(after) or count != info.st_size:
        raise PackageError(f"package output changed while hashing: {path}")
    return count, digest.hexdigest()


def _existing_package_state() -> ExistingPackageState:
    zip_exists = OUTPUT_PATH.exists() or OUTPUT_PATH.is_symlink()
    manifest_exists = SIDECAR_PATH.exists() or SIDECAR_PATH.is_symlink()
    if not zip_exists and not manifest_exists:
        return ExistingPackageState(False)
    if not zip_exists or not manifest_exists:
        raise PackageError("an existing ZIP or package manifest exists alone; preserving it")
    if OUTPUT_PATH.is_symlink() or SIDECAR_PATH.is_symlink():
        raise PackageError("refusing to replace a symlinked ZIP or package manifest")

    zip_size, zip_hash = _hash_path(OUTPUT_PATH)
    manifest_bytes = _read_bytes(SIDECAR_RELATIVE)
    try:
        sidecar = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PackageError(f"cannot parse existing package manifest: {exc}") from None
    if not isinstance(sidecar, dict):
        raise PackageError("existing package manifest is not a JSON object; preserving both files")
    archive_record = sidecar.get("archive")
    files = sidecar.get("files")
    if (
        sidecar.get("schema_version") != 1
        or not isinstance(sidecar.get("project"), dict)
        or sidecar["project"].get("slug") != EXPECTED_SLUG
        or not isinstance(archive_record, dict)
        or archive_record.get("path") != OUTPUT_NAME
        or archive_record.get("size_bytes") != zip_size
        or archive_record.get("sha256") != zip_hash
        or archive_record.get("crc_status") != "PASS"
        or not isinstance(files, list)
        or archive_record.get("member_count") != len(files)
    ):
        raise PackageError("existing ZIP/manifest pair is unknown or divergent; preserving both")

    expected_names = [item.get("path") for item in files if isinstance(item, dict)]
    if (
        len(expected_names) != len(files)
        or any(not isinstance(name, str) for name in expected_names)
        or len(set(expected_names)) != len(expected_names)
        or INTERNAL_MANIFEST_NAME not in expected_names
    ):
        raise PackageError("existing package manifest member inventory is invalid; preserving both")
    try:
        with zipfile.ZipFile(OUTPUT_PATH, "r") as archive:
            if archive.namelist() != expected_names or archive.testzip() is not None:
                raise PackageError("existing ZIP member list or CRC is invalid; preserving both")
            for item in files:
                name = item.get("path")
                expected_size = item.get("size_bytes")
                expected_hash = item.get("sha256")
                if not isinstance(name, str) or not isinstance(expected_size, int) or not isinstance(expected_hash, str):
                    raise PackageError("existing package manifest contains an invalid member record")
                digest = hashlib.sha256()
                count = 0
                with archive.open(name, "r") as member:
                    while block := member.read(CHUNK_BYTES):
                        digest.update(block)
                        count += len(block)
                if count != expected_size or digest.hexdigest() != expected_hash:
                    raise PackageError(f"existing ZIP member hash is invalid: {name}")
            forbidden = [
                name for name in expected_names
                if any(part.lower() in BLOCKED_DIRS for part in PurePosixPath(name).parts)
                or Path(name).suffix.lower() in MOVIE_SUFFIXES
                or name.lower().endswith((".log", ".pyc", ".pyo", ".aiff"))
            ]
            if forbidden:
                raise PackageError(f"existing ZIP contains an excluded artifact: {forbidden[0]}")
    except (OSError, zipfile.BadZipFile, RuntimeError, KeyError) as exc:
        if isinstance(exc, PackageError):
            raise
        raise PackageError(f"cannot validate existing package: {exc}") from None
    return ExistingPackageState(
        True, zip_size, zip_hash, hashlib.sha256(manifest_bytes).hexdigest()
    )


def _assert_existing_unchanged(expected: ExistingPackageState) -> None:
    if _existing_package_state() != expected:
        raise PackageError("existing package changed during build; preserving current files")


def _verify_zip(path: Path, records: list[FileRecord], internal_manifest: bytes) -> None:
    expected_names = [record.archive_path for record in records] + [INTERNAL_MANIFEST_NAME]
    try:
        with zipfile.ZipFile(path, "r") as archive:
            if archive.namelist() != expected_names:
                raise PackageError("ZIP member list differs from deterministic inventory")
            bad = archive.testzip()
            if bad is not None:
                raise PackageError(f"ZIP CRC check failed at {bad}")
            for record in records:
                digest = hashlib.sha256()
                count = 0
                with archive.open(record.archive_path, "r") as member:
                    while block := member.read(CHUNK_BYTES):
                        digest.update(block)
                        count += len(block)
                if count != record.size_bytes or digest.hexdigest() != record.sha256:
                    raise PackageError(f"ZIP readback hash mismatch: {record.archive_path}")
            with archive.open(INTERNAL_MANIFEST_NAME, "r") as member:
                if member.read() != internal_manifest:
                    raise PackageError("embedded package manifest did not round-trip exactly")
            forbidden = [
                name for name in archive.namelist()
                if any(part.lower() in BLOCKED_DIRS for part in PurePosixPath(name).parts)
                or Path(name).suffix.lower() in MOVIE_SUFFIXES
                or name.lower().endswith((".log", ".pyc", ".pyo", ".aiff"))
            ]
            if forbidden:
                raise PackageError(f"excluded artifact found in ZIP: {forbidden[0]}")
    except (OSError, zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
        if isinstance(exc, PackageError):
            raise
        raise PackageError(f"cannot verify ZIP: {exc}") from None


def _make_temp(directory: Path, prefix: str, data: bytes | None = None) -> Path:
    try:
        descriptor, filename = tempfile.mkstemp(prefix=prefix, suffix=".tmp", dir=directory)
        path = Path(filename)
        if data is None:
            os.close(descriptor)
        else:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        return path
    except OSError as exc:
        raise PackageError(f"cannot create temporary output in {directory}: {exc}") from None


def _publish(
    zip_temp: Path,
    manifest_temp: Path,
    prior_state: ExistingPackageState,
) -> bool:
    _assert_existing_unchanged(prior_state)
    new_zip_size, new_zip_hash = _hash_path(zip_temp)
    _new_manifest_size, new_manifest_hash = _hash_path(manifest_temp)
    if prior_state.present and (
        prior_state.zip_size_bytes == new_zip_size
        and prior_state.zip_sha256 == new_zip_hash
        and prior_state.manifest_sha256 == new_manifest_hash
    ):
        return False

    backup_zip: Path | None = None
    backup_manifest: Path | None = None
    zip_published = False
    manifest_published = False
    try:
        if prior_state.present:
            # Retain hard-link recovery points until both atomic replacements finish.
            backup_zip = _make_temp(WORK_DIR, ".ep07-package-old-")
            backup_zip.unlink()
            os.link(OUTPUT_PATH, backup_zip)
            backup_manifest = _make_temp(REVIEW_DIR, ".package-manifest-old-")
            backup_manifest.unlink()
            os.link(SIDECAR_PATH, backup_manifest)
            os.replace(zip_temp, OUTPUT_PATH)
            zip_published = True
            os.replace(manifest_temp, SIDECAR_PATH)
            manifest_published = True
        else:
            os.link(zip_temp, OUTPUT_PATH)
            zip_published = True
            zip_temp.unlink()
            os.link(manifest_temp, SIDECAR_PATH)
            manifest_published = True
            manifest_temp.unlink()
        return True
    except OSError as exc:
        if prior_state.present:
            try:
                if backup_zip is not None and zip_published:
                    os.replace(backup_zip, OUTPUT_PATH)
                    backup_zip = None
                if backup_manifest is not None and manifest_published:
                    os.replace(backup_manifest, SIDECAR_PATH)
                    backup_manifest = None
            except OSError as rollback_exc:
                raise PackageError(
                    f"package update failed ({exc}); rollback also failed ({rollback_exc}); "
                    f"recovery files: {backup_zip}, {backup_manifest}"
                ) from None
        elif zip_published and not manifest_published:
            try:
                size, digest = _hash_path(OUTPUT_PATH)
                if size == new_zip_size and digest == new_zip_hash:
                    OUTPUT_PATH.unlink()
            except (OSError, PackageError):
                pass
        raise PackageError(f"cannot publish ZIP and manifest: {exc}") from None
    finally:
        for backup in (backup_zip, backup_manifest):
            if backup is not None:
                try:
                    backup.unlink(missing_ok=True)
                except OSError:
                    pass


def build_package() -> None:
    if WORK_DIR.name != EXPECTED_SLUG:
        raise PackageError(f"script must run from delivery folder {EXPECTED_SLUG}")
    if REVIEW_DIR.is_symlink() or not REVIEW_DIR.is_dir():
        raise PackageError("review directory is missing or is a symlink")

    prior_state = _existing_package_state()
    selected, exclusions = _walk_delivery()
    project_identity = _validate_inputs(selected)
    records = [_snapshot(relative) for relative in selected]
    records.sort(key=lambda record: record.archive_path)
    if any(record.archive_path == INTERNAL_MANIFEST_NAME for record in records):
        raise PackageError(f"source collides with reserved archive member {INTERNAL_MANIFEST_NAME}")

    entries = [
        {"path": record.archive_path, "size_bytes": record.size_bytes, "sha256": record.sha256}
        for record in records
    ]
    internal_payload = {
        "schema_version": 1,
        "project": project_identity,
        "files": entries,
        "notes": [
            "The original source-script hash was checked against delivery.json.",
            "The five shared 120-second PCM stems were shape-checked before packaging.",
            "Platform movies, dependency trees, runtime bundles, local speech previews, logs, and account state are excluded.",
            "Native PingFang SC is recorded by assets-manifest.json as a host prerequisite and is not redistributed.",
        ],
    }
    internal_manifest = _json_bytes(internal_payload)

    zip_temp: Path | None = None
    manifest_temp: Path | None = None
    try:
        zip_temp = _make_temp(WORK_DIR, ".ep07-project-")
        with zipfile.ZipFile(
            zip_temp, mode="w", compression=zipfile.ZIP_DEFLATED,
            compresslevel=6, allowZip64=True,
        ) as archive:
            for record in records:
                _write_source(archive, record)
            archive.writestr(
                _zip_info(INTERNAL_MANIFEST_NAME), internal_manifest,
                compress_type=zipfile.ZIP_DEFLATED, compresslevel=6,
            )

        _verify_zip(zip_temp, records, internal_manifest)
        zip_size, zip_hash = _hash_path(zip_temp)
        all_members = entries + [{
            "path": INTERNAL_MANIFEST_NAME,
            "size_bytes": len(internal_manifest),
            "sha256": hashlib.sha256(internal_manifest).hexdigest(),
        }]
        exclusion_counts: dict[str, int] = {}
        for item in exclusions:
            reason = item["reason"]
            exclusion_counts[reason] = exclusion_counts.get(reason, 0) + 1
        sidecar_payload = {
            "schema_version": 1,
            "project": project_identity,
            "archive": {
                "path": OUTPUT_NAME,
                "size_bytes": zip_size,
                "sha256": zip_hash,
                "crc_status": "PASS",
                "member_count": len(all_members),
            },
            "files": all_members,
            "exclusions": {
                "counts_by_reason": dict(sorted(exclusion_counts.items())),
                "items": exclusions,
                "rules": [
                    "Do not follow symlinks; exclude node_modules, .git, .remotion, bundles, logs, and hidden local configuration.",
                    "Exclude rendered movies and video evidence, local speech previews, Python caches, and runtime logs.",
                    "Include compact review JSON/Markdown/CSV up to 2 MiB and review JPEGs up to 1 MiB; omit frame PNGs and larger temporary QA.",
                    "Exclude the local account publication record and audio authorization record.",
                ],
            },
            "notes": [
                "Every listed archive member has a byte size and SHA-256; PACKAGE-MANIFEST.json is included in that list.",
                "The ZIP SHA-256 binds the entire compressed archive.",
                "This is an editable-source package; media rendering and publication acceptance are separate gates.",
            ],
        }
        sidecar_bytes = _json_bytes(sidecar_payload)
        manifest_temp = _make_temp(REVIEW_DIR, ".package-manifest-", sidecar_bytes)

        # Recheck every included input immediately before publishing. Excluded movie
        # files are never opened or copied; they may continue rendering independently.
        for record in records:
            _assert_record_current(record)
        published = _publish(zip_temp, manifest_temp, prior_state)
        print(f"Package: {OUTPUT_PATH}")
        print(f"Entries: {len(records)} source files + {INTERNAL_MANIFEST_NAME}")
        print(f"ZIP size: {zip_size:,} bytes")
        print(f"ZIP SHA-256: {zip_hash}")
        print("CRC/readback and member hashes: PASS")
        print(f"Original source SHA-256: {project_identity['source_script']['measured_sha256']} (matches delivery.json)")
        print(f"Excluded paths reported: {len(exclusions)}")
        print(f"External manifest: {SIDECAR_RELATIVE}")
        print("Publication: created" if published else "Publication: existing identical package")
    finally:
        for path in (zip_temp, manifest_temp):
            if path is not None:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a deterministic, locally verified editable EP07 project ZIP."
    )
    parser.parse_args()
    try:
        build_package()
    except (PackageError, OSError, zipfile.BadZipFile) as exc:
        print(f"[package-project] ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
