#!/usr/bin/env python3
"""Validate technical media outputs and optional source checks in a delivery folder."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import struct
import subprocess
import sys
import unicodedata
from typing import Any


_VISUAL_QC_PATH = Path(__file__).resolve().with_name("visual_qc.py")
_VISUAL_QC_SPEC = importlib.util.spec_from_file_location("delivery_visual_qc", _VISUAL_QC_PATH)
if _VISUAL_QC_SPEC is None or _VISUAL_QC_SPEC.loader is None:
    raise ImportError(f"Cannot load visual QC helper: {_VISUAL_QC_PATH}")
_VISUAL_QC_MODULE = importlib.util.module_from_spec(_VISUAL_QC_SPEC)
_VISUAL_QC_SPEC.loader.exec_module(_VISUAL_QC_MODULE)
validate_visual_qc = _VISUAL_QC_MODULE.validate_visual_qc


FPS_CHOICES = (24, 25, 30, 50, 60)
OUTPUTS = {
    "bilibili": (3840, 2160),
    "xiaohongshu": (2160, 3840),
}
SUPPORTED_OUTPUTS = {
    "bilibili": {(3840, 2160)},
    "xiaohongshu": {(2160, 3840), (1080, 1920)},
}
AUDIO_MODES = {"narrated", "provided", "silent"}
DEFAULT_DURATION = 120
CONTAINER_TOLERANCE = Fraction(1, 20)
PRUNED_DIRECTORIES = {
    ".git", "node_modules", "out", "review", ".remotion", "dist", "build",
    "coverage", ".venv", "venv", ".cache", "__pycache__",
}
SOURCE_EXTENSIONS = {".ts", ".tsx", ".json"}
SOURCE_TYPO_PATTERNS = (
    (re.compile(r"\bCASUAL[\s_-]+(?:DEPTH|GRAPH|CHAIN|REASONING|INFERENCE|MODEL)\b", re.I),
     "CAUSAL DEPTH/GRAPH/CHAIN/REASONING/INFERENCE/MODEL"),
    (re.compile(r"\b(?:MANIFLOD|MANFIOLD|MANIFOD)\b", re.I), "MANIFOLD"),
    (re.compile(r"\bTELEMETERY\b", re.I), "TELEMETRY"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check technical media properties and write a fresh QA report."
    )
    parser.add_argument("film_dir", type=Path)
    parser.add_argument(
        "--scan-source",
        action="store_true",
        help="Scan source files for a short list of known token typos.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--source-only",
        action="store_true",
        help="Run only the source scan; media validation is not run.",
    )
    mode.add_argument(
        "--skip-decode",
        dest="skip_decode",
        action="store_true",
        help="Skip full FFmpeg decode; this always produces INCOMPLETE and exits nonzero.",
    )
    return parser.parse_args()


def plain_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def manifest_dimensions_valid(key: str, config: Any) -> bool:
    if not isinstance(config, dict):
        return False
    width = config.get("width")
    height = config.get("height")
    return (plain_int(width) and plain_int(height)
            and (width, height) in SUPPORTED_OUTPUTS[key])


def expected_dimensions(key: str, config: Any) -> tuple[int, int]:
    """Use a supported manifest pair, retaining the legacy XHS size explicitly."""
    if manifest_dimensions_valid(key, config):
        return config["width"], config["height"]
    return OUTPUTS[key]


def number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_check(
    checks: dict[str, str],
    failures: list[str],
    name: str,
    passed: bool,
    message: str,
) -> None:
    checks[name] = "PASS" if passed else "FAIL"
    if not passed:
        failures.append(message)


def resolve_relative(root: Path, raw_path: Any, label: str) -> tuple[Path | None, str | None]:
    if not isinstance(raw_path, str) or not raw_path or "\\" in raw_path:
        return None, f"{label} must be a non-empty relative POSIX path."
    posix = PurePosixPath(raw_path)
    windows = PureWindowsPath(raw_path)
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        return None, f"{label} must be relative to the delivery folder."
    if any(part in {".", ".."} for part in posix.parts):
        return None, f"{label} must not contain traversal components."
    candidate = (root / Path(*posix.parts)).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError:
        return None, f"{label} resolves outside the delivery folder."
    return candidate, None


def parse_rate(value: Any) -> Fraction | None:
    if not isinstance(value, str):
        return None
    try:
        rate = Fraction(value)
    except (ValueError, ZeroDivisionError):
        return None
    return rate if rate > 0 else None


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def inspect_mp4_atoms(path: Path) -> dict[str, Any]:
    """Check top-level ISO BMFF atom order without reading media payloads."""
    size = path.stat().st_size
    atoms: list[tuple[str, int]] = []
    offset = 0
    with path.open("rb") as stream:
        while offset < size:
            if size - offset < 8:
                raise ValueError(f"truncated atom header at byte {offset}")
            stream.seek(offset)
            atom_size, atom_type = struct.unpack(">I4s", stream.read(8))
            header_size = 8
            if atom_size == 1:
                extended = stream.read(8)
                if len(extended) != 8:
                    raise ValueError(f"truncated extended atom size at byte {offset}")
                atom_size = struct.unpack(">Q", extended)[0]
                header_size = 16
            elif atom_size == 0:
                atom_size = size - offset
            if atom_size < header_size or offset + atom_size > size:
                raise ValueError(f"invalid atom size at byte {offset}")
            atoms.append((atom_type.decode("ascii", errors="replace"), offset))
            offset += atom_size

    moov = next((pos for name, pos in atoms if name == "moov"), None)
    mdat = next((pos for name, pos in atoms if name == "mdat"), None)
    if moov is None or mdat is None:
        raise ValueError("top-level moov or mdat atom is missing")
    return {
        "atom_types": [name for name, _ in atoms],
        "moov_offset": moov,
        "mdat_offset": mdat,
        "moov_before_mdat": moov < mdat,
    }


def validate_manifest(
    root: Path, manifest: dict[str, Any], checks: dict[str, str], failures: list[str]
) -> tuple[int | None, int | None, str | None, Fraction | None, int | float | None]:
    version = manifest.get("schema_version")
    add_check(checks, failures, "schema_version", plain_int(version) and version == 1,
              "delivery.json schema_version must be 1")
    title = manifest.get("title")
    add_check(checks, failures, "title", isinstance(title, str) and bool(title.strip()),
              "delivery.json title must be non-empty text")
    duration_value = manifest.get("duration_seconds", DEFAULT_DURATION)
    duration_valid = (isinstance(duration_value, (int, float))
                      and not isinstance(duration_value, bool)
                      and (not isinstance(duration_value, float)
                           or math.isfinite(duration_value)))
    try:
        duration = Fraction(str(duration_value)) if duration_valid else None
    except (ValueError, ZeroDivisionError, OverflowError):
        duration = None
    duration_valid = duration is not None and duration > 0
    add_check(checks, failures, "duration_seconds", duration_valid,
              "delivery.json duration_seconds must be a finite positive JSON number"
              " (or be omitted to use 120 seconds)")

    slug = manifest.get("slug")
    safe_slug = isinstance(slug, str) and bool(slug) and slug not in {".", ".."}
    if safe_slug:
        safe_slug = ("/" not in slug and "\\" not in slug
                     and not PureWindowsPath(slug).drive
                     and not PureWindowsPath(slug).root
                     and not any(unicodedata.category(char) in {"Cc", "Cf"} for char in slug))
    add_check(checks, failures, "slug", safe_slug,
              "delivery.json slug must be one safe directory name")

    raw_fps = manifest.get("fps")
    fps = raw_fps if plain_int(raw_fps) and raw_fps in FPS_CHOICES else None
    add_check(checks, failures, "fps", fps is not None,
              "delivery.json fps must be one of 24, 25, 30, 50, or 60")
    frame_aligned = (duration is not None and fps is not None
                     and (duration * fps).denominator == 1)
    add_check(checks, failures, "duration_frame_alignment", frame_aligned,
              "delivery.json duration_seconds times fps must be an integer frame count"
              " and fps must be supported")
    sample_aligned = duration is not None and (duration * 48_000).denominator == 1
    add_check(checks, failures, "duration_sample_alignment", sample_aligned,
              "delivery.json duration_seconds times 48000 must be an integer sample count")
    expected_frames = int(duration * fps) if frame_aligned else None
    frames = manifest.get("total_frames")
    add_check(checks, failures, "total_frames",
              expected_frames is not None and plain_int(frames) and frames == expected_frames,
              "delivery.json total_frames must equal duration_seconds times its supported fps")

    audio = manifest.get("audio")
    audio_mode = audio.get("mode") if isinstance(audio, dict) else None
    valid_audio_mode = isinstance(audio_mode, str) and audio_mode in AUDIO_MODES
    add_check(checks, failures, "audio_mode", valid_audio_mode,
              "delivery.json audio.mode must be narrated, provided, or silent")
    if isinstance(audio, dict):
        add_check(checks, failures, "audio_master",
                  audio.get("master") == "project/public/audio/master.wav",
                  "delivery.json audio.master must be project/public/audio/master.wav")
    else:
        add_check(checks, failures, "audio_master", False,
                  "delivery.json audio entry must be an object")

    script = manifest.get("script")
    if not isinstance(script, dict):
        add_check(checks, failures, "script_path", False,
                  "delivery.json script entry must be an object")
        add_check(checks, failures, "script_hash", False,
                  "cannot verify source script without a script entry")
    else:
        script_path, path_error = resolve_relative(root, script.get("path"), "script.path")
        path_ok = path_error is None and script.get("path") == "source/script.md"
        add_check(checks, failures, "script_path", path_ok,
                  path_error or "delivery.json script.path must be source/script.md")
        expected_hash = script.get("sha256")
        hash_format_ok = (isinstance(expected_hash, str) and len(expected_hash) == 64
                          and all(char in "0123456789abcdef" for char in expected_hash))
        if not hash_format_ok:
            add_check(checks, failures, "script_hash", False,
                      "delivery.json script.sha256 must be lowercase SHA-256 hex")
        elif script_path is None or not script_path.is_file():
            add_check(checks, failures, "script_hash", False,
                      "source/script.md is missing")
        else:
            try:
                source = script_path.read_bytes()
                source_text = source.decode("utf-8", errors="strict")
                if not source or not source_text.strip():
                    raise ValueError("source/script.md must contain non-whitespace UTF-8 text")
                actual_hash = hashlib.sha256(source).hexdigest()
                add_check(checks, failures, "script_hash", actual_hash == expected_hash,
                          "source/script.md SHA-256 does not match delivery.json")
                checks["script_sha256"] = actual_hash
            except (OSError, UnicodeDecodeError, ValueError) as exc:
                add_check(checks, failures, "script_hash", False,
                          f"cannot read valid UTF-8 source/script.md: {exc}")

    output_config = manifest.get("outputs")
    if not isinstance(output_config, dict):
        add_check(checks, failures, "outputs", False,
                  "delivery.json outputs entry must be an object")
    else:
        for key in OUTPUTS:
            config = output_config.get(key)
            valid = manifest_dimensions_valid(key, config)
            add_check(checks, failures, f"{key}_manifest_dimensions", valid,
                      f"delivery.json outputs.{key} dimensions must be a supported integer pair")

    validated_duration = duration if duration_valid else None
    reported_duration = duration_value if duration_valid else None
    return fps, expected_frames, audio_mode if valid_audio_mode else None, validated_duration, reported_duration


def validate_media(
    key: str,
    config: Any,
    root: Path,
    fps: int | None,
    total_frames: int | None,
    target_duration: Fraction | None,
    target_duration_seconds: int | float | None,
    audio_mode: str | None,
    ffprobe: str | None,
    ffmpeg: str | None,
    skip_decode: bool,
) -> dict[str, Any]:
    width, height = expected_dimensions(key, config)
    checks: dict[str, str] = {}
    failures: list[str] = []
    result: dict[str, Any] = {
        "status": "PASS",
        "path": None,
        "sha256": None,
        "measurements": {},
        "checks": checks,
        "failures": failures,
    }

    def check(name: str, passed: bool, message: str) -> None:
        add_check(checks, failures, name, passed, message)

    duration_label = (f"{target_duration_seconds} seconds"
                      if target_duration_seconds is not None else "a valid target duration")

    if not isinstance(config, dict):
        check("manifest_entry", False, f"{key}: output entry must be an object")
        result["status"] = "FAIL"
        return result
    path, path_error = resolve_relative(root, config.get("path"), f"outputs.{key}.path")
    if path_error:
        check("relative_path", False, f"{key}: {path_error}")
        result["status"] = "FAIL"
        return result

    result["path"] = path.relative_to(root).as_posix()
    dimensions_valid = manifest_dimensions_valid(key, config)
    check("manifest_dimensions", dimensions_valid,
          f"{key}: manifest dimensions must be a supported integer pair")
    if not path.is_file():
        check("media_file", False, f"{key}: media file is missing: {result['path']}")
        if skip_decode:
            checks["strict_decode"] = "SKIPPED"
        else:
            check("strict_decode", False, f"{key}: missing media cannot be decoded")
        result["status"] = "FAIL"
        return result

    try:
        result["sha256"] = sha256_file(path)
        result["measurements"]["file_size_bytes"] = path.stat().st_size
        check("media_file", True, "")
    except OSError as exc:
        check("media_file", False, f"{key}: cannot read media file: {exc}")

    probe_data = None
    if not ffprobe:
        check("ffprobe", False, f"{key}: ffprobe was not found on PATH")
    else:
        try:
            probe = run_command([
                ffprobe, "-v", "error", "-count_frames", "-show_streams",
                "-show_format", "-of", "json", str(path),
            ])
            if probe.returncode != 0:
                check("ffprobe", False,
                      f"{key}: ffprobe failed: {probe.stderr.strip()[-2500:] or probe.returncode}")
            else:
                try:
                    probe_data = json.loads(probe.stdout)
                    if not isinstance(probe_data, dict):
                        raise ValueError("ffprobe JSON root must be an object")
                    check("ffprobe", True, "")
                except (json.JSONDecodeError, ValueError) as exc:
                    check("ffprobe", False, f"{key}: invalid ffprobe JSON: {exc}")
        except OSError as exc:
            check("ffprobe", False, f"{key}: cannot run ffprobe: {exc}")

    if probe_data is not None:
        streams = probe_data.get("streams")
        streams = streams if isinstance(streams, list) else []
        videos = [item for item in streams if isinstance(item, dict)
                  and item.get("codec_type") == "video"]
        audios = [item for item in streams if isinstance(item, dict)
                  and item.get("codec_type") == "audio"]
        check("video_stream_count", len(videos) == 1,
              f"{key}: expected one video stream, found {len(videos)}")
        if len(videos) == 1:
            video = videos[0]
            video_duration = number(video.get("duration"))
            video_info = {
                "codec": video.get("codec_name"),
                "pixel_format": video.get("pix_fmt"),
                "width": video.get("width"),
                "height": video.get("height"),
                "nominal_fps": video.get("r_frame_rate"),
                "average_fps": video.get("avg_frame_rate"),
                "counted_frames": video.get("nb_read_frames"),
                "duration_seconds": video_duration,
            }
            result["measurements"]["video"] = video_info
            check("dimensions", video.get("width") == width and video.get("height") == height,
                  f"{key}: expected {width}x{height}, got "
                  f"{video.get('width')}x{video.get('height')}")
            check("codec", video.get("codec_name") == "h264",
                  f"{key}: video codec must be H.264")
            check("pixel_format", video.get("pix_fmt") in {"yuv420p", "yuvj420p"},
                  f"{key}: pixel format must be yuv420p or yuvj420p")

            nominal = parse_rate(video.get("r_frame_rate"))
            average = parse_rate(video.get("avg_frame_rate"))
            check("nominal_fps", fps is not None and nominal == Fraction(fps, 1),
                  f"{key}: nominal frame rate must match supported manifest fps")
            check("average_fps", fps is not None and average == Fraction(fps, 1),
                  f"{key}: average frame rate must match supported manifest fps")
            try:
                counted_frames = int(video.get("nb_read_frames"))
            except (TypeError, ValueError, OverflowError):
                counted_frames = None
            check("counted_frames", total_frames is not None and counted_frames == total_frames,
                  f"{key}: counted frame count must equal duration_seconds times manifest fps")
            measured_video_duration = (Fraction(str(video_duration))
                                       if video_duration is not None else None)
            duration_ok = (fps is not None and target_duration is not None
                           and measured_video_duration is not None
                           and abs(measured_video_duration - target_duration)
                           <= Fraction(1, fps) + Fraction(1, 1_000_000_000))
            check("video_duration", duration_ok,
                  f"{key}: video duration must match {duration_label} within one frame")
        else:
            video_duration = None

        result["measurements"]["audio_stream_count"] = len(audios)
        if audio_mode == "silent":
            check("audio_stream_count", len(audios) == 0,
                  f"{key}: silent mode must not contain an audio stream")
        elif audio_mode in {"narrated", "provided"}:
            check("audio_stream_count", len(audios) == 1,
                  f"{key}: expected one audio stream, found {len(audios)}")
            if len(audios) == 1:
                audio = audios[0]
                audio_duration = number(audio.get("duration"))
                try:
                    sample_rate = int(audio.get("sample_rate"))
                except (TypeError, ValueError, OverflowError):
                    sample_rate = None
                audio_info = {
                    "codec": audio.get("codec_name"),
                    "sample_rate": sample_rate,
                    "channels": audio.get("channels"),
                    "duration_seconds": audio_duration,
                }
                result["measurements"]["audio"] = audio_info
                check("audio_codec", audio.get("codec_name") == "aac",
                      f"{key}: audio codec must be AAC")
                check("audio_sample_rate", sample_rate == 48_000,
                      f"{key}: audio sample rate must be 48 kHz")
                check("audio_channels", audio.get("channels") == 2,
                      f"{key}: audio must be stereo")
                measured_audio_duration = (Fraction(str(audio_duration))
                                           if audio_duration is not None else None)
                check("audio_duration", target_duration is not None
                      and measured_audio_duration is not None
                      and abs(measured_audio_duration - target_duration)
                      <= CONTAINER_TOLERANCE,
                      f"{key}: audio duration must be within 0.05 seconds"
                      f" of {duration_label}")
        else:
            check("audio_mode", False, f"{key}: manifest audio mode is invalid")

        format_info = probe_data.get("format")
        format_info = format_info if isinstance(format_info, dict) else {}
        container_duration = number(format_info.get("duration"))
        padding = (container_duration - video_duration
                   if container_duration is not None and video_duration is not None else None)
        result["measurements"]["container"] = {
            "duration_seconds": container_duration,
            "padding_vs_video_seconds": padding,
        }
        measured_container_duration = (Fraction(str(container_duration))
                                       if container_duration is not None else None)
        check("container_duration", target_duration is not None
              and measured_container_duration is not None
              and abs(measured_container_duration - target_duration) <= CONTAINER_TOLERANCE,
              f"{key}: container duration must be within 0.05 seconds"
              f" of {duration_label}")

    try:
        atoms = inspect_mp4_atoms(path)
        result["measurements"]["mp4_atoms"] = atoms
        check("moov_before_mdat", atoms["moov_before_mdat"],
              f"{key}: MP4 moov atom must precede mdat")
    except (OSError, ValueError) as exc:
        check("mp4_atom_layout", False, f"{key}: cannot verify MP4 atom order: {exc}")

    if skip_decode:
        checks["strict_decode"] = "SKIPPED"
    elif not ffmpeg:
        check("strict_decode", False, f"{key}: ffmpeg was not found on PATH")
    else:
        try:
            decoded = run_command([
                ffmpeg, "-v", "error", "-xerror", "-err_detect", "explode",
                "-i", str(path), "-map", "0:v:0", "-map", "0:a?", "-f", "null", "-",
            ])
            passed = decoded.returncode == 0
            check("strict_decode", passed,
                  "" if passed else f"{key}: strict decode failed: "
                  f"{decoded.stderr.strip()[-2500:] or decoded.returncode}")
        except OSError as exc:
            check("strict_decode", False, f"{key}: cannot run ffmpeg: {exc}")

    if failures:
        result["status"] = "FAIL"
    elif skip_decode:
        result["status"] = "INCOMPLETE"
    return result


def scan_source(root: Path) -> dict[str, Any]:
    """Read supported source files and report only matched tokens, never source lines."""
    resolved_root = root.resolve(strict=True)
    files_scanned = 0
    matches: list[dict[str, Any]] = []
    read_errors: list[dict[str, str]] = []

    def record_walk_error(exc: OSError) -> None:
        error_path = Path(exc.filename) if exc.filename else resolved_root
        try:
            relative = error_path.relative_to(resolved_root).as_posix() or "."
        except ValueError:
            relative = "."
        message = os.strerror(exc.errno) if exc.errno is not None else "directory read failed"
        read_errors.append({"file": relative, "error": message})

    for directory, directory_names, file_names in os.walk(
        resolved_root, topdown=True, followlinks=False, onerror=record_walk_error
    ):
        parent = Path(directory)
        directory_names[:] = [
            name for name in directory_names
            if name.lower() not in PRUNED_DIRECTORIES
            and not name.lower().startswith("bundle")
            and not (parent / name).is_symlink()
        ]
        for name in file_names:
            path = parent / name
            if path.suffix.lower() not in SOURCE_EXTENSIONS or path.is_symlink():
                continue
            try:
                resolved_path = path.resolve(strict=True)
                resolved_path.relative_to(resolved_root)
            except (OSError, RuntimeError, ValueError):
                continue

            relative = path.relative_to(resolved_root).as_posix()
            files_scanned += 1
            try:
                contents = path.read_text(encoding="utf-8", errors="strict")
            except UnicodeDecodeError:
                read_errors.append({"file": relative, "error": "invalid UTF-8"})
                continue
            except OSError as exc:
                message = os.strerror(exc.errno) if exc.errno is not None else "file read failed"
                read_errors.append({"file": relative, "error": message})
                continue

            for line_number, line in enumerate(contents.splitlines(), start=1):
                line_matches: list[tuple[int, dict[str, Any]]] = []
                for pattern, replacement in SOURCE_TYPO_PATTERNS:
                    for match in pattern.finditer(line):
                        token = match.group(0)
                        suggestion = replacement
                        if replacement.startswith("CAUSAL "):
                            suggestion = "CAUSAL" + token[6:]
                        line_matches.append((match.start(), {
                            "file": relative,
                            "line": line_number,
                            "matched_token": token,
                            "suggestion": suggestion,
                        }))
                matches.extend(item for _, item in sorted(line_matches, key=lambda value: value[0]))

    status = "FAIL" if matches else (
        "INCOMPLETE" if read_errors or files_scanned == 0 else "PASS"
    )
    result: dict[str, Any] = {
        "status": status,
        "files_scanned": files_scanned,
        "matches": matches,
        "read_errors": read_errors,
    }
    if files_scanned == 0:
        result["incomplete_reason"] = "no source files were found"
    return result


def read_manifest(root: Path) -> tuple[dict[str, Any] | None, str | None]:
    path = root / "delivery.json"
    if not path.is_file():
        return None, "delivery.json is missing or is not a regular file"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"cannot read valid UTF-8 delivery.json: {exc}"
    if not isinstance(manifest, dict):
        return None, "delivery.json root must be an object"
    return manifest, None


def save_report(root: Path, report: dict[str, Any]) -> Path:
    review = root / "review"
    if review.is_symlink():
        raise OSError("review directory must not be a symlink")
    review.mkdir(exist_ok=True)
    if not review.is_dir():
        raise OSError("review exists but is not a directory")
    for index in range(100):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        suffix = "" if index == 0 else f"-{index:02d}"
        path = review / f"media-validation-{stamp}{suffix}.json"
        try:
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(report, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            return path
        except FileExistsError:
            continue
    raise OSError("could not allocate a unique validation report filename")


def source_scan_failures(source_scan: dict[str, Any]) -> list[str]:
    return [
        f"source typo {item['matched_token']!r} in {item['file']}:{item['line']}; "
        f"suggestion: {item['suggestion']}"
        for item in source_scan["matches"]
    ]


def validate(
    film_dir: Path,
    skip_decode: bool,
    scan_source_enabled: bool = False,
    source_only: bool = False,
) -> int:
    try:
        root = film_dir.expanduser().resolve(strict=True)
    except OSError as exc:
        print(f"validate_delivery.py: error: cannot access film directory: {exc}", file=sys.stderr)
        return 2
    if not root.is_dir():
        print(f"validate_delivery.py: error: not a directory: {root}", file=sys.stderr)
        return 2

    if source_only:
        source_scan = scan_source(root)
        failures = source_scan_failures(source_scan)
        report = {
            "schema_version": 1,
            "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "scope": "source-only",
            "status": "INCOMPLETE",
            "media_validation": "NOT_RUN",
            "source_scan": source_scan,
            "checks": {},
            "outputs": {},
            "failures": failures,
        }
        try:
            report_path = save_report(root, report)
        except OSError as exc:
            print(f"validate_delivery.py: error: cannot write report: {exc}", file=sys.stderr)
            return 2
        print("Media validation: NOT RUN (source-only mode).")
        print(f"Source scan status: {source_scan['status']}")
        print("Validation status: INCOMPLETE")
        print(f"Report: {report_path.relative_to(root).as_posix()}")
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 0 if source_scan["status"] == "PASS" else 1

    checks: dict[str, str] = {}
    failures: list[str] = []
    output_reports: dict[str, Any] = {}
    manifest, manifest_error = read_manifest(root)
    add_check(checks, failures, "manifest", manifest is not None,
              manifest_error or "delivery.json is valid")
    manifest_hash = None
    if (root / "delivery.json").is_file():
        try:
            manifest_hash = sha256_file(root / "delivery.json")
        except OSError:
            pass

    target_duration: Fraction | None = None
    target_duration_seconds: int | float | None = None
    source_scan = scan_source(root) if scan_source_enabled else None
    if source_scan is not None:
        failures.extend(source_scan_failures(source_scan))

    if manifest is None:
        for key in OUTPUTS:
            output_reports[key] = {
                "status": "FAIL", "path": None, "sha256": None,
                "measurements": {}, "checks": {},
                "failures": ["cannot validate output without valid delivery.json"],
            }
            failures.append(f"{key}: cannot validate output without valid delivery.json")
    else:
        (fps, total_frames, audio_mode, target_duration,
         target_duration_seconds) = validate_manifest(root, manifest, checks, failures)
        output_entries = manifest.get("outputs")
        output_entries = output_entries if isinstance(output_entries, dict) else {}
        ffprobe = shutil.which("ffprobe")
        ffmpeg = shutil.which("ffmpeg")
        for key in OUTPUTS:
            output_reports[key] = validate_media(
                key, output_entries.get(key), root, fps, total_frames, target_duration,
                target_duration_seconds, audio_mode, ffprobe, ffmpeg, skip_decode,
            )
            failures.extend(output_reports[key]["failures"])

    qc_manifest = manifest if manifest is not None else {"visual_qc": None}
    output_hashes = {
        key: output_reports[key].get("sha256") for key in OUTPUTS
    }
    visual_qc = validate_visual_qc(root, qc_manifest, output_hashes, total_frames)
    non_visual_failures = bool(failures)
    checks["visual_qc"] = visual_qc["status"]
    failures.extend(visual_qc["failures"])

    scan_incomplete = source_scan is not None and source_scan["status"] == "INCOMPLETE"
    status = ("INCOMPLETE" if skip_decode else
              "FAIL" if non_visual_failures or visual_qc["status"] == "FAIL" else
              "INCOMPLETE" if visual_qc["status"] == "INCOMPLETE" or scan_incomplete else "PASS")
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": status,
        "target_duration_seconds": target_duration_seconds,
        "manifest_sha256": manifest_hash,
        "checks": checks,
        "outputs": output_reports,
        "visual_qc": visual_qc,
        "failures": failures,
        "human_review": {
            "representative_frames": "pending",
            "continuous_human_review": "pending",
            "target_device_playback": "pending",
        },
    }
    if source_scan is not None:
        report["source_scan"] = source_scan
    try:
        report_path = save_report(root, report)
    except OSError as exc:
        print(f"validate_delivery.py: error: cannot write report: {exc}", file=sys.stderr)
        return 2
    print(f"Validation status: {status}")
    print(f"Report: {report_path.relative_to(root).as_posix()}")
    if source_scan is not None:
        print(f"Source scan status: {source_scan['status']}")
    for failure in failures:
        print(f"- {failure}", file=sys.stderr)
    return 0 if status == "PASS" else 1


def main() -> int:
    args = parse_args()
    return validate(args.film_dir, args.skip_decode, args.scan_source, args.source_only)


if __name__ == "__main__":
    raise SystemExit(main())
