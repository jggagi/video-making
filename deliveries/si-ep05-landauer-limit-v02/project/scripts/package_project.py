#!/usr/bin/env python3
"""Build a deterministic, self-contained editable-project ZIP for EP05.

The archive contains EP05 source, physics, timeline, narration caches, shared
audio, captions, and compact review evidence. It never uploads or installs anything.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
import wave
import zipfile
from typing import Any, BinaryIO, Iterable


WORK_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = WORK_DIR / "project"
OUTPUT_NAME = "si-ep05-landauer-limit-v02-editable-project.zip"
OUTPUT_PATH = WORK_DIR / OUTPUT_NAME
SIDECAR_PATH = PROJECT_DIR / "package-manifest.json"
INTERNAL_MANIFEST_NAME = "PACKAGE-MANIFEST.json"
ZIP_TIMESTAMP = (2026, 10, 18, 0, 0, 0)
CHUNK_BYTES = 1024 * 1024
FPS = 60
REVIEW_JPEG_LIMIT = 5 * 1024 * 1024
EXPECTED_LAYOUTS = {
    "bilibili": (3840, 2160),
    "xiaohongshu": (2160, 3840),
}
REQUIRED_ARCHIVE_PATHS = (
    "delivery.json",
    "source/script.md",
    "watch.html",
    "B站/captions.srt",
    "小红书/captions.srt",
    "project/brief.md",
    "project/adapted-script.md",
    "project/scientific-notes.md",
    "project/audio-timing.json",
    "project/segments.json",
    "project/timeline.json",
    "project/sfx_events.json",
    "project/src/physics.ts",
    "project/tsconfig.json",
    "project/package.json",
    "project/package-lock.json",
    "project/public/audio/master.wav",
    "project/public/audio/mix-manifest.json",
    "project/public/audio/cache-manifest.json",
    "review/audio-caption-alignment.json",
)
NARRATION_SEGMENTS = tuple(f"S{index:02d}" for index in range(1, 11))


class PackageError(RuntimeError):
    """A required input is invalid or a safe archive cannot be produced."""


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


def _stat_identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _relative_parts(relative: str) -> tuple[str, ...]:
    candidate = PurePosixPath(relative)
    if candidate.is_absolute() or not candidate.parts or any(part in ("", ".", "..") for part in candidate.parts):
        raise PackageError(f"unsafe archive path: {relative!r}")
    return candidate.parts


def _check_path(relative: str, *, required: bool) -> Path | None:
    """Return a contained regular file, rejecting symlink components."""
    parts = _relative_parts(relative)
    candidate = WORK_DIR.joinpath(*parts)
    current = WORK_DIR

    try:
        root_stat = WORK_DIR.lstat()
    except OSError as exc:
        raise PackageError(f"cannot inspect delivery root: {exc}") from None
    if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
        raise PackageError(f"delivery root is not a real directory: {WORK_DIR}")

    try:
        for part in parts[:-1]:
            current = current / part
            info = current.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                if required:
                    raise PackageError(f"required path has a symlink or non-directory parent: {relative}")
                return None

        info = candidate.lstat()
    except FileNotFoundError:
        if required:
            raise PackageError(f"required project file is missing: {relative}") from None
        return None
    except OSError as exc:
        if required:
            raise PackageError(f"cannot inspect required project file {relative}: {exc}") from None
        return None

    if stat.S_ISLNK(info.st_mode):
        if required:
            raise PackageError(f"required project file is a symlink: {relative}")
        return None
    if not stat.S_ISREG(info.st_mode):
        if required:
            raise PackageError(f"required project path is not a regular file: {relative}")
        return None

    try:
        resolved = candidate.resolve(strict=True)
        root_resolved = WORK_DIR.resolve(strict=True)
    except OSError as exc:
        if required:
            raise PackageError(f"cannot resolve project file {relative}: {exc}") from None
        return None
    if not _is_within(resolved, root_resolved):
        if required:
            raise PackageError(f"project file escapes delivery root: {relative}")
        return None
    return candidate


def _check_directory(relative: str, *, required: bool) -> Path | None:
    parts = _relative_parts(relative)
    candidate = WORK_DIR.joinpath(*parts)
    current = WORK_DIR
    try:
        root_stat = WORK_DIR.lstat()
        if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
            raise PackageError(f"delivery root is not a real directory: {WORK_DIR}")
        for part in parts:
            current = current / part
            info = current.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                if required:
                    raise PackageError(f"required directory has a symlink or non-directory component: {relative}")
                return None
        resolved = candidate.resolve(strict=True)
        root_resolved = WORK_DIR.resolve(strict=True)
    except FileNotFoundError:
        if required:
            raise PackageError(f"required project directory is missing: {relative}") from None
        return None
    except OSError as exc:
        if required:
            raise PackageError(f"cannot inspect project directory {relative}: {exc}") from None
        return None
    if not _is_within(resolved, root_resolved):
        if required:
            raise PackageError(f"project directory escapes delivery root: {relative}")
        return None
    return candidate


def _open_checked(path: Path, expected: os.stat_result | None = None) -> BinaryIO:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise PackageError(f"cannot safely open {path.relative_to(WORK_DIR)}: {exc}") from None

    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise PackageError(f"source changed to a non-regular file: {path.relative_to(WORK_DIR)}")
        if expected is not None and _stat_identity(opened) != _stat_identity(expected):
            raise PackageError(f"source changed while packaging: {path.relative_to(WORK_DIR)}")
        return os.fdopen(descriptor, "rb")
    except Exception:
        os.close(descriptor)
        raise


def _hash_file(path: Path, relative: str) -> tuple[str, int, os.stat_result]:
    checked = _check_path(relative, required=True)
    assert checked is not None
    before = checked.lstat()
    digest = hashlib.sha256()
    byte_count = 0
    with _open_checked(checked, before) as stream:
        while block := stream.read(CHUNK_BYTES):
            digest.update(block)
            byte_count += len(block)
        after_fd = os.fstat(stream.fileno())
    after_path = checked.lstat()
    if _stat_identity(before) != _stat_identity(after_fd) or _stat_identity(before) != _stat_identity(after_path):
        raise PackageError(f"source changed during hash pass: {relative}")
    if byte_count != before.st_size:
        raise PackageError(f"source size changed during hash pass: {relative}")
    return digest.hexdigest(), byte_count, before


def _read_safe_bytes(relative: str) -> bytes:
    path = _check_path(relative, required=True)
    assert path is not None
    before = path.lstat()
    with _open_checked(path, before) as stream:
        content = stream.read()
        after_fd = os.fstat(stream.fileno())
    after_path = path.lstat()
    if _stat_identity(before) != _stat_identity(after_fd) or _stat_identity(before) != _stat_identity(after_path):
        raise PackageError(f"source changed while reading: {relative}")
    if len(content) != before.st_size:
        raise PackageError(f"source size changed while reading: {relative}")
    return content


def _sensitive_or_transient(relative: str) -> bool:
    parts = _relative_parts(relative)
    lowered_parts = tuple(part.lower() for part in parts)
    name = lowered_parts[-1]

    excluded_dirs = {
        "node_modules", "out", "__pycache__", "credentials", "secrets",
        "agents", "uploads", "user-uploads", "user-media-uploads",
        "user-media", "media-uploads", "network", "networking", "deps", "dependencies",
        "config", "configs", "configuration",
    }
    if name.startswith("bundle") or name.startswith("scratch"):
        return True
    if any(part in excluded_dirs or part.startswith("bundle") or part.startswith("scratch") for part in lowered_parts[:-1]):
        return True
    if any(part.startswith(".") for part in lowered_parts):
        return True
    if name in {"archive.json", "package-manifest.json", "audio-authorization.json"}:
        return True
    if ".tmp" in name or name.endswith((".log", ".pyc", ".pyo")):
        return True
    if name in {"tsconfig.json"}:
        return False
    if any(word in name for word in ("credential", "secret", "token")):
        return True
    if name == ".env" or name.startswith(".env.") or name.endswith(".env"):
        return True
    if "config" in name or "configuration" in name:
        return True
    return False


def _walk_regular_files(relative_directory: str) -> Iterable[str]:
    directory = _check_directory(relative_directory, required=False)
    if directory is None:
        return ()
    found: list[str] = []
    for root, dirs, files in os.walk(directory, topdown=True, followlinks=False):
        root_path = Path(root)
        dirs[:] = sorted(
            name for name in dirs
            if not (root_path / name).is_symlink()
            and not _sensitive_or_transient((root_path / name).relative_to(WORK_DIR).as_posix() + "/placeholder")
        )
        for name in sorted(files):
            path = root_path / name
            if path.is_symlink():
                continue
            try:
                if not stat.S_ISREG(path.lstat().st_mode):
                    continue
            except OSError:
                continue
            found.append(path.relative_to(WORK_DIR).as_posix())
    return found


def _archive_candidates() -> list[str]:
    candidates: set[str] = set(REQUIRED_ARCHIVE_PATHS)

    project = _check_directory("project", required=True)
    assert project is not None
    for path in project.iterdir():
        if path.is_symlink() or not path.is_file():
            continue
        if path.name == "package-manifest.json":
            continue
        if path.suffix.lower() in {".json", ".md"} or path.name == "tsconfig.json":
            candidates.add(path.relative_to(WORK_DIR).as_posix())

    for relative_directory, suffixes in (
        ("project/src", {".ts", ".tsx"}),
        ("project/scripts", {".py", ".mjs"}),
    ):
        for relative in _walk_regular_files(relative_directory):
            if Path(relative).suffix.lower() in suffixes:
                candidates.add(relative)

    for relative in _walk_regular_files("project/public/audio"):
        parts = PurePosixPath(relative).parts
        suffix = Path(relative).suffix.lower()
        if parts[-2:-1] in (("cues",), ("raw",), ("canonical",)) and suffix == ".wav":
            candidates.add(relative)
        elif parts[-2:-1] == ("tts-input",) and suffix == ".txt":
            candidates.add(relative)
        elif len(parts) == 4 and parts[-1] == "master.wav":
            candidates.add(relative)
        elif len(parts) == 4 and suffix == ".json":
            candidates.add(relative)

    review = _check_directory("review", required=True)
    assert review is not None
    for path in review.iterdir():
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(WORK_DIR).as_posix()
        suffix = path.suffix.lower()
        if suffix in {".json", ".md"}:
            candidates.add(relative)
        elif suffix == ".jpg":
            try:
                if path.lstat().st_size <= REVIEW_JPEG_LIMIT:
                    candidates.add(relative)
            except OSError:
                continue

    filtered: list[str] = []
    for relative in candidates:
        if _sensitive_or_transient(relative):
            if relative in REQUIRED_ARCHIVE_PATHS:
                raise PackageError(f"required archive entry is blocked by a safety rule: {relative}")
            continue
        if relative == INTERNAL_MANIFEST_NAME:
            raise PackageError(f"source collides with reserved archive member {INTERNAL_MANIFEST_NAME}")
        checked = _check_path(relative, required=relative in REQUIRED_ARCHIVE_PATHS)
        if checked is not None:
            filtered.append(relative)

    return sorted(set(filtered))


def _read_json(relative: str) -> dict[str, Any]:
    try:
        data = json.loads(_read_safe_bytes(relative).decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PackageError(f"cannot read {relative}: {exc}") from None
    if not isinstance(data, dict):
        raise PackageError(f"{relative} must contain a JSON object")
    return data


def _srt_time_ms(value: str) -> int:
    match = re.fullmatch(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", value)
    if not match:
        raise PackageError(f"invalid SRT timestamp: {value!r}")
    hours, minutes, seconds, millis = (int(part) for part in match.groups())
    return (((hours * 60 + minutes) * 60 + seconds) * 1000) + millis


def _parse_srt(relative: str) -> list[tuple[int, int, str]]:
    try:
        content = _read_safe_bytes(relative).decode("utf-8").replace("\r\n", "\n").strip()
    except (OSError, UnicodeError) as exc:
        raise PackageError(f"cannot read {relative}: {exc}") from None
    cues: list[tuple[int, int, str]] = []
    for block in re.split(r"\n[ \t]*\n", content):
        lines = block.splitlines()
        if len(lines) < 3 or not lines[0].strip().isdigit():
            raise PackageError(f"malformed SRT cue in {relative}")
        match = re.fullmatch(r"(.+?) --> (.+?)", lines[1].strip())
        if not match:
            raise PackageError(f"malformed SRT timing line in {relative}")
        start_ms = _srt_time_ms(match.group(1))
        end_ms = _srt_time_ms(match.group(2))
        if start_ms >= end_ms:
            raise PackageError(f"non-positive SRT window in {relative}")
        cues.append((round(start_ms * 60 / 1000), round(end_ms * 60 / 1000), "\n".join(lines[2:])))
    return cues


def _validate_narration_cache_inventory() -> list[str]:
    """Require every EP05 segment's original, normalized, and canonical narration files."""
    required: list[str] = []
    directory_specs = (
        ("project/public/audio/cues", ".wav"),
        ("project/public/audio/raw", ".wav"),
        ("project/public/audio/canonical", ".wav"),
        ("project/public/audio/tts-input", ".txt"),
    )
    for directory, suffix in directory_specs:
        paths = list(_walk_regular_files(directory))
        matches: dict[str, list[str]] = {segment_id: [] for segment_id in NARRATION_SEGMENTS}
        for relative in paths:
            filename = Path(relative).name
            match = re.match(r"^(S\d{2})(?:[-_].*)?" + re.escape(suffix) + r"$", filename, re.IGNORECASE)
            if match and match.group(1).upper() in matches:
                matches[match.group(1).upper()].append(relative)
        missing = [segment_id for segment_id, files in matches.items() if not files]
        if missing:
            raise PackageError(
                f"{directory} is missing EP05 narration cache files for: {', '.join(missing)}"
            )
        required.extend(relative for files in matches.values() for relative in files)
    return sorted(set(required))


def _validate_inputs() -> tuple[dict[str, Any], dict[str, Any], int]:
    delivery = _read_json("delivery.json")
    slug = delivery.get("slug")
    if slug != WORK_DIR.name:
        raise PackageError(f"EP05 delivery slug must match work folder name ({WORK_DIR.name})")
    if (
        delivery.get("duration_seconds") != 120
        or delivery.get("fps") != 60
        or delivery.get("total_frames") != 7200
    ):
        raise PackageError("EP05 delivery.json must identify the 120-second, 60-fps, 7200-frame film")

    outputs = delivery.get("outputs")
    if not isinstance(outputs, dict):
        raise PackageError("delivery.json outputs must be an object")
    for key, expected in EXPECTED_LAYOUTS.items():
        output = outputs.get(key)
        if not isinstance(output, dict) or (output.get("width"), output.get("height")) != expected:
            raise PackageError(f"delivery.json outputs.{key} must be {expected[0]}x{expected[1]}")

    audio = delivery.get("audio")
    if not isinstance(audio, dict) or audio.get("master") != "project/public/audio/master.wav":
        raise PackageError("delivery.json must identify project/public/audio/master.wav as the shared master")

    source = _read_json("project/segments.json")
    authored_segments = source.get("segments")
    if (
        not isinstance(authored_segments, list)
        or len(authored_segments) != len(NARRATION_SEGMENTS)
        or any(not isinstance(item, dict) for item in authored_segments)
        or [item.get("id") for item in authored_segments] != list(NARRATION_SEGMENTS)
    ):
        raise PackageError("project/segments.json must contain EP05 segments S01 through S10 in order")

    timing = _read_json("project/audio-timing.json")
    if (
        timing.get("durationSeconds") != 120
        or timing.get("fps") != 60
        or timing.get("sampleRate") != 48000
        or timing.get("samplesPerChannel") != 5_760_000
    ):
        raise PackageError("audio-timing.json does not describe the exact measured EP05 PCM timeline")
    segments = timing.get("segments")
    if not isinstance(segments, list) or len(segments) != len(NARRATION_SEGMENTS):
        raise PackageError("audio-timing.json must contain ten measured EP05 narration windows")
    measured_by_id = {item.get("id"): item for item in segments if isinstance(item, dict)}
    if set(measured_by_id) != set(NARRATION_SEGMENTS):
        raise PackageError("audio-timing.json must identify every EP05 segment exactly once")

    for authored in authored_segments:
        segment_id = authored["id"]
        measured = measured_by_id[segment_id]
        declared_start = authored.get("startFrame")
        declared_end = authored.get("endFrame")
        if (
            not isinstance(declared_start, int)
            or not isinstance(declared_end, int)
            or not 0 <= declared_start < declared_end <= 7200
        ):
            raise PackageError(f"{segment_id} has an invalid requested EP05 frame window")
        if (
            measured.get("declaredStartFrame") != declared_start
            or measured.get("declaredEndFrame") != declared_end
        ):
            raise PackageError(f"{segment_id} measured timing does not retain its requested EP05 window")
        cue_samples = measured.get("cueSamplesAt48k")
        voice_start = measured.get("voiceStartSample")
        voice_end = measured.get("voiceEndSampleExclusive")
        cue_path = measured.get("cueFile")
        if (
            not isinstance(cue_samples, int)
            or cue_samples <= 0
            or not isinstance(voice_start, int)
            or not isinstance(voice_end, int)
            or not declared_start * 800 <= voice_start < voice_end <= declared_end * 800
        ):
            raise PackageError(f"{segment_id} has invalid measured voice or cue sample bounds")
        if not isinstance(cue_path, str) or not cue_path.startswith("project/public/audio/cues/"):
            raise PackageError(f"{segment_id} measured cue path is outside the EP05 cue cache")
        cue_digest, cue_size, _cue_stat = _hash_file(WORK_DIR / cue_path, cue_path)
        if measured.get("cueSha256") != cue_digest or cue_size < 44:
            raise PackageError(f"{segment_id} cue cache does not match its measured audio-timing hash")
        cue_file = _check_path(cue_path, required=True)
        assert cue_file is not None
        try:
            with wave.open(str(cue_file), "rb") as cue:
                cue_shape = (cue.getframerate(), cue.getnchannels(), cue.getsampwidth(), cue.getnframes(), cue.getcomptype())
        except (OSError, wave.Error) as exc:
            raise PackageError(f"cannot inspect measured EP05 narration cue for {segment_id}: {exc}") from None
        if cue_shape != (48000, 1, 2, cue_samples, "NONE"):
            raise PackageError(f"{segment_id} cue must be mono 48-kHz PCM16 with its measured sample count")

    alignment = _read_json("review/audio-caption-alignment.json")
    aligned_captions = alignment.get("captions")
    if alignment.get("status") != "measured_pcm_with_estimated_phrase_timing" or not isinstance(aligned_captions, list) or not aligned_captions:
        raise PackageError("review/audio-caption-alignment.json must contain the measured-PCM phrase alignment")
    expected_cues: list[tuple[int, int, str]] = []
    previous_caption_end = -1
    for item in aligned_captions:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("start"), str)
            or not isinstance(item.get("end"), str)
            or not isinstance(item.get("text"), str)
        ):
            raise PackageError("audio-caption-alignment.json has a malformed caption window")
        start_ms = _srt_time_ms(item["start"])
        end_ms = _srt_time_ms(item["end"])
        start_frame = round(start_ms * FPS / 1_000)
        end_frame = round(end_ms * FPS / 1_000)
        if not (0 <= start_frame < end_frame <= 7200):
            raise PackageError("audio-caption-alignment.json contains a caption outside the EP05 timeline")
        lines = item["text"].splitlines()
        if not 1 <= len(lines) <= 2 or any(
            sum("\u3400" <= character <= "\u9fff" for character in line) > 14 for line in lines
        ):
            raise PackageError("audio-caption-alignment.json contains a caption outside EP05 line limits")
        if start_frame < previous_caption_end:
            raise PackageError("audio-caption-alignment.json caption windows overlap")
        previous_caption_end = end_frame
        expected_cues.append((start_frame, end_frame, item["text"]))

    subtitle_sets = [
        _parse_srt("B站/captions.srt"),
        _parse_srt("小红书/captions.srt"),
    ]
    if any(len(cues) != len(expected_cues) for cues in subtitle_sets):
        raise PackageError("both platform SRT files must contain every EP05 aligned caption window")
    if subtitle_sets[0] != subtitle_sets[1]:
        raise PackageError("platform SRT files do not share identical caption windows")
    if subtitle_sets[0] != expected_cues:
        raise PackageError("platform SRT windows do not match the EP05 audio-caption alignment report")
    by_segment_text: dict[str, str] = {segment_id: "" for segment_id in NARRATION_SEGMENTS}
    for item in aligned_captions:
        segment_id = item.get("segmentId")
        if not isinstance(segment_id, str) or segment_id not in by_segment_text:
            raise PackageError("audio-caption-alignment.json references an unknown EP05 segment")
        by_segment_text[segment_id] += item["text"].replace("\n", "")
    for authored in authored_segments:
        joined = by_segment_text[authored["id"]]
        displayed = authored.get("display_subtitle")
        if not isinstance(displayed, str) or re.sub(r"\s+", "", joined) != re.sub(r"\s+", "", displayed):
            raise PackageError(f"EP05 caption text does not preserve all display subtitle text for {authored['id']}")

    master = _check_path("project/public/audio/master.wav", required=True)
    assert master is not None
    try:
        with wave.open(str(master), "rb") as source:
            audio_shape = (
                source.getframerate(),
                source.getnchannels(),
                source.getsampwidth(),
                source.getnframes(),
                source.getcomptype(),
            )
            sample_width_bytes = audio_shape[2]
    except (OSError, wave.Error) as exc:
        raise PackageError(f"cannot inspect shared PCM master: {exc}") from None
    if audio_shape != (48000, 2, 2, 5_760_000, "NONE"):
        raise PackageError("shared master must be stereo PCM16 at 48 kHz with 5,760,000 frames per channel")
    mix_manifest = _read_json("project/public/audio/mix-manifest.json")
    mix_outputs = mix_manifest.get("outputs")
    if not isinstance(mix_outputs, dict):
        raise PackageError("EP05 mix-manifest.json has no output records")
    master_record = mix_outputs.get("master")
    if not isinstance(master_record, dict):
        raise PackageError("EP05 mix-manifest.json has no master hash record")
    master_digest, _master_size, _master_stat = _hash_file(master, "project/public/audio/master.wav")
    if mix_manifest.get("status") != "built" or master_record.get("sha256") != master_digest:
        raise PackageError("EP05 master does not match a built audio mix manifest")

    source_hashes = timing.get("sourceHashes", {})
    if not isinstance(source_hashes, dict):
        raise PackageError("EP05 audio-timing.json has no source hash record")
    current_segments_hash, _segments_size, _segments_stat = _hash_file(PROJECT_DIR / "segments.json", "project/segments.json")
    current_events_hash, _events_size, _events_stat = _hash_file(PROJECT_DIR / "sfx_events.json", "project/sfx_events.json")
    if source_hashes.get("segmentsJson") != current_segments_hash or source_hashes.get("eventsJson") != current_events_hash:
        raise PackageError("EP05 PCM timing is stale against segments.json or sfx_events.json")

    project_identity = {
        "slug": slug,
        "title": delivery.get("title", ""),
        "duration_seconds": 120,
        "fps": 60,
        "total_frames": 7200,
        "layouts": {
            "bilibili": {"width": 3840, "height": 2160},
            "xiaohongshu": {"width": 2160, "height": 3840},
        },
        "shared_audio": {
            "sample_rate": 48000,
            "channels": 2,
            "sample_width_bytes": sample_width_bytes,
            "samples_per_channel": 5_760_000,
        },
        "measured_narration_segments": len(segments),
        "caption_windows_from_measured_segment_pcm": len(expected_cues),
    }
    return delivery, project_identity, sample_width_bytes


def _snapshot(relative: str) -> FileRecord:
    path = _check_path(relative, required=True)
    assert path is not None
    digest, size, info = _hash_file(path, relative)
    return FileRecord(
        archive_path=relative,
        source_path=path,
        size_bytes=size,
        sha256=digest,
        device=info.st_dev,
        inode=info.st_ino,
        mtime_ns=info.st_mtime_ns,
        ctime_ns=info.st_ctime_ns,
    )


def _assert_snapshot_current(record: FileRecord) -> None:
    path = _check_path(record.archive_path, required=True)
    assert path is not None
    if _stat_identity(path.lstat()) != _record_stat(record):
        raise PackageError(f"source changed after it was validated: {record.archive_path}")


def _record_stat(record: FileRecord) -> tuple[int, int, int, int, int]:
    return (record.device, record.inode, record.size_bytes, record.mtime_ns, record.ctime_ns)


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(filename=name, date_time=ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info._compresslevel = 6
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    info.extra = b""
    info.comment = b""
    return info


def _write_source_member(archive: zipfile.ZipFile, record: FileRecord) -> None:
    current = _check_path(record.archive_path, required=True)
    assert current is not None
    before = current.lstat()
    if _stat_identity(before) != _record_stat(record):
        raise PackageError(f"source changed after inventory: {record.archive_path}")

    digest = hashlib.sha256()
    byte_count = 0
    with _open_checked(current, before) as source, archive.open(
        _zip_info(record.archive_path), mode="w", force_zip64=True
    ) as target:
        while block := source.read(CHUNK_BYTES):
            digest.update(block)
            byte_count += len(block)
            target.write(block)
        after_fd = os.fstat(source.fileno())
    after_path = current.lstat()
    if _stat_identity(before) != _stat_identity(after_fd) or _stat_identity(before) != _stat_identity(after_path):
        raise PackageError(f"source changed during ZIP write: {record.archive_path}")
    if byte_count != record.size_bytes or digest.hexdigest() != record.sha256:
        raise PackageError(f"source hash changed during ZIP write: {record.archive_path}")


def _manifest_bytes(project_identity: dict[str, Any], records: list[FileRecord]) -> bytes:
    payload = {
        "schema_version": 1,
        "project": project_identity,
        "files": [
            {"path": record.archive_path, "size_bytes": record.size_bytes, "sha256": record.sha256}
            for record in records
        ],
        "notes": [
            "PingFang SC and Menlo are referenced native system fonts and are not embedded.",
            "project/package-lock.json is preserved for reproducible dependency installation.",
            "The exact PCM master and all S01-S10 cue, raw, and canonical narration caches are retained; reproducible mix stems are omitted.",
            "Audio authorization and local credential/configuration files are excluded.",
        ],
    }
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _verify_archive(path: Path, records: list[FileRecord], expected_manifest: bytes) -> None:
    expected_names = [record.archive_path for record in records] + [INTERNAL_MANIFEST_NAME]
    try:
        with zipfile.ZipFile(path, "r") as archive:
            if archive.namelist() != expected_names:
                raise PackageError("ZIP member list differs from the deterministic inventory")
            bad_member = archive.testzip()
            if bad_member is not None:
                raise PackageError(f"ZIP CRC check failed at {bad_member}")

            for record in records:
                digest = hashlib.sha256()
                byte_count = 0
                with archive.open(record.archive_path, "r") as source:
                    while block := source.read(CHUNK_BYTES):
                        digest.update(block)
                        byte_count += len(block)
                if byte_count != record.size_bytes or digest.hexdigest() != record.sha256:
                    raise PackageError(f"ZIP readback hash mismatch for {record.archive_path}")

            with archive.open(INTERNAL_MANIFEST_NAME, "r") as source:
                if source.read() != expected_manifest:
                    raise PackageError("embedded package manifest did not round-trip exactly")
    except (OSError, zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
        if isinstance(exc, PackageError):
            raise
        raise PackageError(f"cannot verify generated ZIP: {exc}") from None


def _hash_existing_archive(path: Path) -> tuple[int, str]:
    if path.is_symlink():
        raise PackageError(f"refusing to replace a symlink at {path}")
    try:
        info = path.lstat()
    except FileNotFoundError:
        raise
    if not stat.S_ISREG(info.st_mode):
        raise PackageError(f"refusing to replace a non-regular path at {path}")
    digest = hashlib.sha256()
    count = 0
    with _open_checked(path, info) as source:
        while block := source.read(CHUNK_BYTES):
            digest.update(block)
            count += len(block)
        after = os.fstat(source.fileno())
    if _stat_identity(info) != _stat_identity(after) or count != info.st_size:
        raise PackageError(f"existing ZIP changed while verifying: {path}")
    return count, digest.hexdigest()


@dataclass(frozen=True)
class ExistingState:
    output_exists: bool
    output_size: int | None
    output_sha256: str | None
    sidecar_exists: bool
    sidecar_sha256: str | None


def _existing_state() -> ExistingState:
    output_exists = OUTPUT_PATH.exists() or OUTPUT_PATH.is_symlink()
    sidecar_exists = SIDECAR_PATH.exists() or SIDECAR_PATH.is_symlink()
    if not output_exists and not sidecar_exists:
        return ExistingState(False, None, None, False, None)
    if not output_exists or not sidecar_exists:
        raise PackageError("an output ZIP or package-manifest.json exists alone; preserving it for review")

    if OUTPUT_PATH.is_symlink() or SIDECAR_PATH.is_symlink():
        raise PackageError("refusing to overwrite a symlinked ZIP or package manifest")
    output_size, output_digest = _hash_existing_archive(OUTPUT_PATH)
    sidecar_path = _check_path("project/package-manifest.json", required=True)
    assert sidecar_path is not None
    try:
        sidecar_bytes = _read_safe_bytes("project/package-manifest.json")
        sidecar = json.loads(sidecar_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PackageError(f"cannot read existing package-manifest.json: {exc}") from None

    archive_info = sidecar.get("archive") if isinstance(sidecar, dict) else None
    if (
        not isinstance(archive_info, dict)
        or archive_info.get("path") != OUTPUT_NAME
        or archive_info.get("size_bytes") != output_size
        or archive_info.get("sha256") != output_digest
        or archive_info.get("crc_status") != "PASS"
        or not isinstance(sidecar.get("project"), dict)
        or sidecar["project"].get("slug") != WORK_DIR.name
    ):
        raise PackageError("existing ZIP is unknown or divergent; preserving it and stopping")
    return ExistingState(
        True,
        output_size,
        output_digest,
        True,
        hashlib.sha256(sidecar_bytes).hexdigest(),
    )


def _assert_state_unchanged(expected: ExistingState) -> None:
    current = _existing_state()
    if current != expected:
        raise PackageError("existing package changed during build; preserving current files and stopping")


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _atomic_temporary(directory: Path, prefix: str, data: bytes | None = None) -> Path:
    try:
        descriptor, filename = tempfile.mkstemp(prefix=prefix, suffix=".tmp", dir=directory)
        path = Path(filename)
        if data is not None:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        else:
            os.close(descriptor)
        return path
    except OSError as exc:
        raise PackageError(f"cannot create temporary file in {directory}: {exc}") from None


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _acquire_lock() -> Path:
    lock_key = hashlib.sha256(str(WORK_DIR).encode("utf-8")).hexdigest()[:16]
    lock_path = Path(tempfile.gettempdir()) / f"ep05-project-package-{lock_key}.lock"
    try:
        descriptor = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(f"pid={os.getpid()}\n")
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        raise PackageError(f"another package operation or stale lock exists: {lock_path}") from None
    except OSError as exc:
        raise PackageError(f"cannot create package lock: {exc}") from None
    return lock_path


def build_package() -> None:
    lock_path = _acquire_lock()
    temp_zip: Path | None = None
    temp_sidecar: Path | None = None
    try:
        state = _existing_state()
        candidate_paths = _archive_candidates()
        narration_cache_paths = _validate_narration_cache_inventory()
        missing_cache_entries = sorted(set(narration_cache_paths) - set(candidate_paths))
        if missing_cache_entries:
            raise PackageError(
                "EP05 narration cache files were not admitted to the archive inventory: "
                + ", ".join(missing_cache_entries)
            )
        records = [_snapshot(relative) for relative in candidate_paths]
        records.sort(key=lambda record: record.archive_path)
        _delivery, project_identity, _sample_width = _validate_inputs()
        record_by_path = {record.archive_path: record for record in records}
        for relative in REQUIRED_ARCHIVE_PATHS:
            _assert_snapshot_current(record_by_path[relative])
        if any(record.archive_path == INTERNAL_MANIFEST_NAME for record in records):
            raise PackageError(f"source collides with reserved archive member {INTERNAL_MANIFEST_NAME}")

        embedded_manifest = _manifest_bytes(project_identity, records)
        temp_zip = _atomic_temporary(WORK_DIR, prefix=".editable-project-")
        with zipfile.ZipFile(
            temp_zip,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
            allowZip64=True,
        ) as archive:
            for record in records:
                _write_source_member(archive, record)
            archive.writestr(
                _zip_info(INTERNAL_MANIFEST_NAME),
                embedded_manifest,
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=6,
            )

        _verify_archive(temp_zip, records, embedded_manifest)
        zip_size, zip_digest = _hash_existing_archive(temp_zip)
        sidecar_payload = {
            "schema_version": 1,
            "project": project_identity,
            "files": [
                {"path": record.archive_path, "size_bytes": record.size_bytes, "sha256": record.sha256}
                for record in records
            ],
            "archive": {
                "path": OUTPUT_NAME,
                "size_bytes": zip_size,
                "sha256": zip_digest,
                "crc_status": "PASS",
                "member_count": len(records) + 1,
            },
            "notes": [
                "PingFang SC and Menlo are referenced native system fonts and are not embedded.",
                "project/package-lock.json is preserved for reproducible dependency installation.",
                "The exact PCM master and all S01-S10 cue, raw, and canonical narration caches are retained; reproducible mix stems are omitted.",
                "Audio authorization and local credential/configuration files are excluded.",
            ],
        }
        sidecar_bytes = _json_bytes(sidecar_payload)
        temp_sidecar = _atomic_temporary(PROJECT_DIR, prefix=".package-manifest-", data=sidecar_bytes)

        # Protect against a concurrent or unknown write during the potentially long ZIP pass.
        _assert_state_unchanged(state)
        if state.output_exists:
            os.replace(temp_zip, OUTPUT_PATH)
            temp_zip = None
        else:
            # Hard-link publication is atomic and refuses a newly appeared destination.
            os.link(temp_zip, OUTPUT_PATH)
            temp_zip.unlink()
            temp_zip = None
        _fsync_directory(WORK_DIR)

        try:
            if state.sidecar_exists:
                os.replace(temp_sidecar, SIDECAR_PATH)
            else:
                os.link(temp_sidecar, SIDECAR_PATH)
                temp_sidecar.unlink()
            temp_sidecar = None
            _fsync_directory(PROJECT_DIR)
        except OSError as exc:
            # Keep a first-run output from becoming an unindexed package if sidecar publication fails.
            if not state.output_exists:
                try:
                    size_now, digest_now = _hash_existing_archive(OUTPUT_PATH)
                    if size_now == zip_size and digest_now == zip_digest:
                        OUTPUT_PATH.unlink()
                        _fsync_directory(WORK_DIR)
                except (OSError, PackageError):
                    pass
            raise PackageError(f"ZIP is verified but package-manifest publication failed: {exc}") from None

        print(f"Package: {OUTPUT_PATH}")
        print(f"Entries: {len(records)} source files + {INTERNAL_MANIFEST_NAME}")
        print(f"ZIP size: {zip_size:,} bytes")
        print(f"ZIP SHA-256: {zip_digest}")
        print("CRC/readback: PASS")
        print("External manifest: project/package-manifest.json")
    finally:
        for temporary in (temp_zip, temp_sidecar):
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build and verify the deterministic EP05 editable-project ZIP in this delivery folder. "
            "The archive is limited to allowlisted source, PCM, narration-cache, caption, and compact QA files; "
            "no network access or dependency installation is used."
        )
    )
    parser.parse_args()
    try:
        build_package()
    except PackageError as exc:
        print(f"[package-project] ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
