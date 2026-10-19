#!/usr/bin/env python3
"""Verify v02 proof media specs, hashes, and full MP4 decoding."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent.parent
REVIEW_DIR = PROJECT_DIR.parent / "review"
VIDEO = REVIEW_DIR / "crystal-proof-12s-1080p.mp4"
STILLS = {
    "coffee-4k.png": REVIEW_DIR / "coffee-4k.png",
    "choice-4k.png": REVIEW_DIR / "choice-4k.png",
    "crystal-4k.png": REVIEW_DIR / "crystal-4k.png",
}
REPORT = REVIEW_DIR / "media-check.json"
AAC_PADDING_TOLERANCE_SECONDS = 0.05


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, capture_output=True, text=True)


def ffprobe_json(ffprobe: str, media_path: Path, entries: str) -> dict[str, Any]:
    result = run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            entries,
            "-of",
            "json",
            str(media_path),
        ]
    )
    return json.loads(result.stdout)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def describe_error(error: Exception) -> str:
    if isinstance(error, subprocess.CalledProcessError) and error.stderr:
        return error.stderr.strip()
    return str(error)


def check_still(ffprobe: str | None, name: str, path: Path) -> tuple[dict[str, Any], list[str]]:
    result: dict[str, Any] = {"path": name, "pass": False}
    failures: list[str] = []
    if not path.is_file():
        failures.append(f"{name}: output is missing")
        result["error"] = "output is missing"
        return result, failures

    result["bytes"] = path.stat().st_size
    result["sha256"] = sha256(path)
    if not ffprobe:
        failures.append(f"{name}: ffprobe is not available")
        result["error"] = "ffprobe is not available"
        return result, failures

    try:
        metadata = ffprobe_json(ffprobe, path, "stream=codec_name,width,height")
        streams = metadata.get("streams", [])
        stream = streams[0] if len(streams) == 1 else {}
        spec = {
            "codec": stream.get("codec_name"),
            "width": to_int(stream.get("width")),
            "height": to_int(stream.get("height")),
        }
        result["spec"] = spec
        errors = []
        if len(streams) != 1:
            errors.append(f"expected one image stream, found {len(streams)}")
        for key, expected in (("codec", "png"), ("width", 3840), ("height", 2160)):
            if spec[key] != expected:
                errors.append(f"{key}: expected {expected}, got {spec[key]}")
        result["pass"] = not errors
        if errors:
            result["error"] = "; ".join(errors)
            failures.extend(f"{name}: {error}" for error in errors)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        message = describe_error(error)
        result["error"] = message
        failures.append(f"{name}: {message}")
    return result, failures


def check_video(ffprobe: str | None, ffmpeg: str | None) -> tuple[dict[str, Any], list[str]]:
    result: dict[str, Any] = {
        "path": VIDEO.name,
        "pass": False,
        "videoPass": False,
        "audioPass": False,
        "fullDecodePass": False,
    }
    failures: list[str] = []
    if not VIDEO.is_file():
        failures.append(f"{VIDEO.name}: output is missing")
        result["error"] = "output is missing"
        return result, failures

    result["bytes"] = VIDEO.stat().st_size
    result["sha256"] = sha256(VIDEO)
    video_errors: list[str] = []
    audio_errors: list[str] = []
    if not ffprobe:
        video_errors.append("ffprobe is not available")
        audio_errors.append("ffprobe is not available")
    else:
        try:
            metadata = ffprobe_json(
                ffprobe,
                VIDEO,
                "stream=codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,nb_frames,duration,sample_rate,channels,channel_layout:format=duration",
            )
        except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
            message = describe_error(error)
            video_errors.append(message)
            audio_errors.append(message)
        else:
            streams = metadata.get("streams", [])
            videos = [stream for stream in streams if stream.get("codec_type") == "video"]
            audios = [stream for stream in streams if stream.get("codec_type") == "audio"]
            video = videos[0] if len(videos) == 1 else {}
            audio = audios[0] if len(audios) == 1 else {}
            format_duration = to_float(metadata.get("format", {}).get("duration"))
            video_duration = to_float(video.get("duration"))
            audio_duration = to_float(audio.get("duration"))
            if video_duration is None:
                frame_count = to_int(video.get("nb_frames"))
                frame_rate = video.get("avg_frame_rate") or video.get("r_frame_rate")
                try:
                    video_fps = float(Fraction(frame_rate)) if frame_rate else 0
                except (ValueError, ZeroDivisionError):
                    video_fps = 0
                if frame_count is not None and video_fps > 0:
                    video_duration = frame_count / video_fps
            if format_duration is None:
                available_durations = [value for value in (video_duration, audio_duration) if value is not None]
                format_duration = max(available_durations) if available_durations else None
            if audio_duration is None:
                audio_duration = format_duration

            video_spec = {
                "codec": video.get("codec_name"),
                "width": to_int(video.get("width")),
                "height": to_int(video.get("height")),
                "frameRate": video.get("r_frame_rate"),
                "averageFrameRate": video.get("avg_frame_rate"),
                "frames": to_int(video.get("nb_frames")),
                "durationSeconds": video_duration,
            }
            audio_spec = {
                "codec": audio.get("codec_name"),
                "sampleRateHz": to_int(audio.get("sample_rate")),
                "channels": to_int(audio.get("channels")),
                "channelLayout": audio.get("channel_layout"),
                "durationSeconds": audio_duration,
            }
            result["spec"] = {
                "video": video_spec,
                "audio": audio_spec,
                "containerDurationSeconds": format_duration,
                "aacPaddingToleranceSeconds": AAC_PADDING_TOLERANCE_SECONDS,
            }

            if len(videos) != 1:
                video_errors.append(f"expected one video stream, found {len(videos)}")
            expected_video = {
                "codec": "h264",
                "width": 1920,
                "height": 1080,
                "frameRate": "60/1",
                "averageFrameRate": "60/1",
                "frames": 720,
            }
            for key, expected in expected_video.items():
                if video_spec[key] != expected:
                    video_errors.append(f"video {key}: expected {expected}, got {video_spec[key]}")
            if video_duration is None or abs(video_duration - 12.0) > 0.02:
                video_errors.append(f"video duration: expected 12.0s ±0.02s, got {video_duration}")

            if len(audios) != 1:
                audio_errors.append(f"expected one audio stream, found {len(audios)}")
            expected_audio = {
                "codec": "aac",
                "sampleRateHz": 48000,
                "channels": 2,
                "channelLayout": "stereo",
            }
            for key, expected in expected_audio.items():
                if audio_spec[key] != expected:
                    audio_errors.append(f"audio {key}: expected {expected}, got {audio_spec[key]}")
            if audio_duration is None or abs(audio_duration - 12.0) > AAC_PADDING_TOLERANCE_SECONDS:
                audio_errors.append(
                    f"audio duration: expected 12.0s ±{AAC_PADDING_TOLERANCE_SECONDS:.2f}s, got {audio_duration}"
                )
            if format_duration is None or abs(format_duration - 12.0) > AAC_PADDING_TOLERANCE_SECONDS:
                audio_errors.append(
                    f"container duration: expected 12.0s ±{AAC_PADDING_TOLERANCE_SECONDS:.2f}s, got {format_duration}"
                )

    result["videoPass"] = not video_errors
    result["audioPass"] = not audio_errors
    if video_errors:
        result["videoError"] = "; ".join(video_errors)
        failures.extend(f"{VIDEO.name}: {error}" for error in video_errors)
    if audio_errors:
        result["audioError"] = "; ".join(audio_errors)
        failures.extend(f"{VIDEO.name}: {error}" for error in audio_errors)

    decode_pass = False
    if not ffmpeg:
        decode_error = "ffmpeg is not available"
    else:
        try:
            run([ffmpeg, "-v", "error", "-xerror", "-i", str(VIDEO), "-f", "null", "-"])
            decode_pass = True
            decode_error = None
        except (OSError, subprocess.CalledProcessError) as error:
            decode_error = describe_error(error)
    result["fullDecodePass"] = decode_pass
    if decode_error:
        result["decodeError"] = decode_error
        failures.append(f"{VIDEO.name}: full decode failed: {decode_error}")

    result["pass"] = result["videoPass"] and result["audioPass"] and decode_pass
    return result, failures


def write_report(report: dict[str, Any]) -> None:
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    temporary = REPORT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(REPORT)


def main() -> int:
    ffprobe = shutil.which("ffprobe")
    ffmpeg = shutil.which("ffmpeg")
    files: dict[str, Any] = {}
    failures: list[str] = []

    for name, path in STILLS.items():
        files[name], asset_failures = check_still(ffprobe, name, path)
        failures.extend(asset_failures)
    files[VIDEO.name], video_failures = check_video(ffprobe, ffmpeg)
    failures.extend(video_failures)

    stills_pass = all(files[name]["pass"] for name in STILLS)
    video_pass = files[VIDEO.name]["videoPass"]
    audio_pass = files[VIDEO.name]["audioPass"]
    decode_pass = files[VIDEO.name]["fullDecodePass"]
    checks = {
        "allThreeStillSpecsPass": stills_pass,
        "videoSpecPass": video_pass,
        "audioSpecPass": audio_pass,
        "fullDecodePass": decode_pass,
    }
    report = {
        "schemaVersion": 1,
        "checkedAtUtc": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "files": files,
        "overallPass": all(checks.values()),
        "failures": failures,
    }
    write_report(report)

    if report["overallPass"]:
        print(f"PASS: all stills and 12-second video verified; full decode succeeded ({REPORT})")
        return 0
    print(f"FAIL: media checks failed; see {REPORT}", file=sys.stderr)
    for failure in failures:
        print(f"- {failure}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except OSError as error:
        print(f"FAIL: could not write media report: {error}", file=sys.stderr)
        raise SystemExit(1)
