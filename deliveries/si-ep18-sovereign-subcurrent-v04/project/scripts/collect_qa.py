#!/usr/bin/env python3
"""Collect SHA-bound encoded-frame and measurement evidence for EP18 v04."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any


PROJECT = Path(__file__).resolve().parents[1]
DELIVERY = PROJECT.parent
REVIEW = DELIVERY / "review"
DELIVERY_JSON = DELIVERY / "delivery.json"
WORK_ID = "si-ep18-sovereign-subcurrent-v04"
RENDER_PLAN = json.loads((PROJECT / "render-plan.json").read_text(encoding="utf-8"))
WORK_TITLE = RENDER_PLAN["work"]["title"]
EXPECTED_WIDTH = RENDER_PLAN["composition"]["width"]
EXPECTED_HEIGHT = RENDER_PLAN["composition"]["height"]
EXPECTED_FPS = Fraction(RENDER_PLAN["composition"]["fps"], 1)
EXPECTED_FRAMES = RENDER_PLAN["composition"]["durationInFrames"]
PHONE_SIZE = (360, 640)
PHONE_FRAMES = tuple(RENDER_PLAN["frames"]["stillFrameNumbers"])
NATIVE_REVIEW_ENTRIES = tuple(RENDER_PLAN["frames"]["nativeReviewFrames"])
NATIVE_FRAMES = tuple(entry["frame"] for entry in NATIVE_REVIEW_ENTRIES)
COVER_FRAMES = dict(RENDER_PLAN["frames"]["coverFrames"])
STAGE_BOUNDS_LOGICAL = tuple(RENDER_PLAN["sceneContract"]["stageBoundsLogical"][axis][index]
                              for axis in ("x", "y") for index in (0, 1))
# The stage bounds are logical-canvas coordinates; contact sheets are 360x640.
MOTION_CROP = tuple(round(STAGE_BOUNDS_LOGICAL[index] / 3) for index in (0, 2, 1, 3))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, capture_output=True, text=True)


def parse_fraction(value: Any) -> Fraction | None:
    if not isinstance(value, str) or value in {"0/0", "N/A", ""}:
        return None
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError):
        return None


def parse_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def resolve_inside_delivery(relative: Any, label: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise RuntimeError(f"delivery.json has no valid {label} path")
    root = DELIVERY.resolve(strict=True)
    path = (DELIVERY / relative).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise RuntimeError(f"Manifest {label} path must resolve to a file inside this v04 delivery")
    return path


def current_movie() -> tuple[dict[str, Any], Path]:
    manifest = read_json(DELIVERY_JSON)
    if manifest.get("slug") != WORK_ID or manifest.get("title") != WORK_TITLE:
        raise RuntimeError("delivery.json is not the expected EP18 v04 manifest")
    if manifest.get("platforms") != ["xiaohongshu"]:
        raise RuntimeError("v04 QA is scoped to the Xiaohongshu output")
    if (manifest.get("duration_seconds"), manifest.get("fps"), manifest.get("total_frames")) != (90, 60, EXPECTED_FRAMES):
        raise RuntimeError("delivery.json does not match the 90-second, 60-fps, 5400-frame target")
    outputs = manifest.get("outputs")
    entry = outputs.get("xiaohongshu") if isinstance(outputs, dict) else None
    if not isinstance(entry, dict) or (entry.get("width"), entry.get("height")) != (EXPECTED_WIDTH, EXPECTED_HEIGHT):
        raise RuntimeError("delivery.json does not declare the native portrait output")
    movie = resolve_inside_delivery(entry.get("path"), "final MP4")
    expected_name = Path(RENDER_PLAN["output"]["path"]).name
    if movie.name != expected_name or movie.suffix.lower() != ".mp4":
        raise RuntimeError("delivery.json does not point to the exact v04 final MP4")
    return manifest, movie


def validate_segments() -> list[dict[str, Any]]:
    rows = read_json(PROJECT / "segments.json")
    expected_ids = [f"S{i:02d}" for i in range(1, 9)]
    if not isinstance(rows, list) or [row.get("id") for row in rows if isinstance(row, dict)] != expected_ids:
        raise RuntimeError("Expected exactly the eight v04 narration cues S01-S08")
    for row in rows:
        if not isinstance(row.get("startFrame"), int) or not isinstance(row.get("endFrame"), int):
            raise RuntimeError("v04 cue frame bounds must be integers")
        if not (0 <= row["startFrame"] < row["endFrame"] <= EXPECTED_FRAMES):
            raise RuntimeError("v04 cue frame bounds must fit the 5400-frame timeline")
        if not isinstance(row.get("display_subtitle"), str) or not isinstance(row.get("tts_phonetic_text"), str):
            raise RuntimeError("v04 cues must retain display_subtitle and tts_phonetic_text")
    return rows


def representative_pairs(rows: list[dict[str, Any]]) -> tuple[tuple[str, int, int], ...]:
    offset = RENDER_PLAN["frames"]["segmentRepresentativePairs"]["startOffsetFrames"]
    pairs = []
    for row in rows:
        start, end = row["startFrame"], row["endFrame"]
        first = start + offset
        second = first + RENDER_PLAN["frames"]["segmentRepresentativePairs"]["gapFrames"]
        if not start <= first < second < end:
            raise RuntimeError(f"Cue {row['id']} cannot contain its planned 2.5-second motion pair")
        pairs.append((f"{row['id']}-human-shadow-stage", first, second))
    return tuple(pairs)


def collected_phone_frames(rows: list[dict[str, Any]], pairs: tuple[tuple[str, int, int], ...]) -> tuple[int, ...]:
    anchors = RENDER_PLAN["frames"]["anchors"]
    anchor_frames = [anchors["confirm"], *anchors["silenceRangeHalfOpen"], anchors["doubleHeartbeat"]]
    return tuple(sorted(set(PHONE_FRAMES) | set(anchor_frames) | {frame for _, first, second in pairs for frame in (first, second)}))


def probe_movie(ffprobe: str, movie: Path) -> dict[str, Any]:
    result = run([ffprobe, "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(movie)])
    return json.loads(result.stdout)


def check_media_spec(probe: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    streams = probe.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
    audio = audio_streams[0] if len(audio_streams) == 1 else {}
    frame_rate = parse_fraction(video.get("avg_frame_rate"))
    frame_count = None
    for field in ("nb_read_frames", "nb_frames"):
        try:
            if video.get(field) not in (None, "N/A"):
                frame_count = int(video[field])
                break
        except (TypeError, ValueError):
            pass
    video_duration = parse_float(video.get("duration"))
    container_duration = parse_float((probe.get("format") or {}).get("duration"))
    measured = {
        "video": {
            "codec": video.get("codec_name"), "pixelFormat": video.get("pix_fmt"),
            "width": video.get("width"), "height": video.get("height"),
            "averageFrameRate": video.get("avg_frame_rate"), "countedFrames": frame_count,
            "durationSeconds": video_duration,
        },
        "audio": {
            "streamCount": len(audio_streams), "codec": audio.get("codec_name"),
            "sampleRateHz": int(audio["sample_rate"]) if str(audio.get("sample_rate", "")).isdigit() else None,
            "channels": audio.get("channels"), "durationSeconds": parse_float(audio.get("duration")),
        },
        "container": {
            "durationSeconds": container_duration,
            "sizeBytes": int((probe.get("format") or {}).get("size", 0) or 0),
        },
    }
    passed = (
        video.get("codec_name") == "h264" and video.get("pix_fmt") == "yuv420p"
        and video.get("width") == EXPECTED_WIDTH and video.get("height") == EXPECTED_HEIGHT
        and frame_rate == EXPECTED_FPS and frame_count == EXPECTED_FRAMES
        and video_duration is not None and abs(video_duration - 90.0) <= (1 / 60) + 0.001
        and container_duration is not None and abs(container_duration - 90.0) <= 0.05
        and len(audio_streams) == 1 and audio.get("codec_name") == "aac"
        and str(audio.get("sample_rate")) == "48000" and audio.get("channels") == 2
        and abs((parse_float(audio.get("duration")) or 0.0) - 90.0) <= 0.05
    )
    return measured, [{"name": "encoded_native_media_spec", "status": "PASS" if passed else "FAIL", "measured": measured}]


def collect_loudness(ffmpeg: str, movie: Path) -> dict[str, Any]:
    result = run([ffmpeg, "-hide_banner", "-nostats", "-i", str(movie), "-map", "0:a:0", "-af", "ebur128=peak=true", "-f", "null", "-"])
    summary = result.stderr
    summary_at = summary.rfind("Summary:")
    tail = summary[summary_at:] if summary_at >= 0 else summary
    integrated = re.search(r"\bI:\s*(-?\d+(?:\.\d+)?)\s*LUFS", tail)
    true_peak = re.search(r"\bPeak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", tail)
    if integrated is None or true_peak is None:
        raise RuntimeError("ffmpeg ebur128 did not return integrated loudness and true-peak measurements")
    return {"integratedLoudnessLufs": float(integrated.group(1)), "truePeakDbfs": float(true_peak.group(1)), "summaryTail": "\n".join(tail.splitlines()[-40:])}


def extract_frames(ffmpeg: str, movie: Path, frames: tuple[int, ...], destination: Path, *, native: bool) -> list[Path]:
    if tuple(sorted(set(frames))) != frames:
        raise RuntimeError('FFmpeg emits frames chronologically; requested labels must be sorted and unique')
    destination.mkdir(parents=True, exist_ok=False)
    prefix = "native" if native else "phone"
    pattern = destination / (prefix + "_%03d.png")
    expression = "select='" + "+".join(f"eq(n,{frame})" for frame in frames) + "'"
    if not native:
        expression += ",scale=360:640:flags=lanczos"
    run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-threads", "2", "-filter_threads", "2",
        "-i", str(movie), "-map", "0:v:0", "-vf", expression, "-fps_mode", "passthrough",
        "-start_number", "0", str(pattern),
    ])
    selected = sorted(destination.glob(prefix + "_*.png"))
    if len(selected) != len(frames):
        raise RuntimeError(f"Expected {len(frames)} {prefix} frames; extracted {len(selected)}")
    from PIL import Image
    final_paths: list[Path] = []
    expected_size = (EXPECTED_WIDTH, EXPECTED_HEIGHT) if native else PHONE_SIZE
    for frame, temp_path in zip(frames, selected):
        with Image.open(temp_path) as image:
            if image.size != expected_size:
                raise RuntimeError(f"Unexpected {prefix} frame size at {frame}: {image.size}")
        final_path = destination / f"frame_{frame:04d}.png"
        temp_path.rename(final_path)
        final_paths.append(final_path)
    return final_paths


def make_contact_sheets(paths: list[Path], frames: tuple[int, ...], output_dir: Path) -> list[str]:
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.load_default(size=18)
    except TypeError:
        font = ImageFont.load_default()
    outputs: list[str] = []
    for panel_number, offset in enumerate(range(0, len(paths), 9), start=1):
        panel = Image.new("RGB", (1080, 1920), "#09090B")
        draw = ImageDraw.Draw(panel)
        for index, (image_path, frame) in enumerate(zip(paths[offset:offset + 9], frames[offset:offset + 9])):
            with Image.open(image_path) as opened:
                image = opened.convert("RGB")
            col, row = index % 3, index // 3
            x, y = col * 360, row * 640
            panel.paste(image, (x, y))
            draw.rectangle((x, y, x + 116, y + 28), fill="#09090B")
            draw.text((x + 6, y + 4), f"F{frame:04d}", fill="#FAFAFA", font=font)
        name = f"phone-contact-{panel_number:02d}.jpg"
        panel.save(output_dir / name, quality=92, optimize=True)
        outputs.append(name)
    return outputs


def motion_measurements(phone_dir: Path, pairs: tuple[tuple[str, int, int], ...]) -> list[dict[str, Any]]:
    import numpy as np
    from PIL import Image
    results: list[dict[str, Any]] = []
    for label, first, second in pairs:
        crops = []
        for frame in (first, second):
            path = phone_dir / f"frame_{frame:04d}.png"
            with Image.open(path) as image:
                if image.size != PHONE_SIZE:
                    raise RuntimeError(f"Unexpected motion thumbnail size at frame {frame}")
                crops.append(np.asarray(image.convert("RGB").crop(MOTION_CROP), dtype=np.int16))
        difference = float(np.abs(crops[0] - crops[1]).mean())
        results.append({
            "act": label,
            "frames": [first, second],
            "cropXyxyOn360x640PhoneFrame": list(MOTION_CROP),
            "sourceCropXyxyOn1080x1920LogicalFrame": [STAGE_BOUNDS_LOGICAL[index] for index in (0, 2, 1, 3)],
            "meanAbsoluteRgbDifference0To255": round(difference, 6),
            "interpretation": "human-and-shadow stage measurement only; not a visual pass or proof of meaningful motion",
        })
    return results


def main() -> int:
    manifest, movie = current_movie()
    cues = validate_segments()
    pairs = representative_pairs(cues)
    collected_frames = collected_phone_frames(cues, pairs)
    native_entries = NATIVE_REVIEW_ENTRIES
    chronological_entries = tuple(sorted(native_entries, key=lambda entry: entry["frame"]))
    if tuple(sorted(set(NATIVE_FRAMES))) != NATIVE_FRAMES or native_entries != chronological_entries:
        raise RuntimeError("Native review frames must be unique and their labels must be in chronological order")
    if not {1800, 3820, 4920}.issubset(set(NATIVE_FRAMES)):
        raise RuntimeError("Native review frames must include the three declared v04 story moments")
    if any(frame < 0 or frame >= EXPECTED_FRAMES for frame in collected_frames + NATIVE_FRAMES):
        raise RuntimeError("Configured v04 QA frame is outside the 5400-frame timeline")
    try:
        import numpy  # noqa: F401
        from PIL import Image, ImageDraw, ImageFont  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("NumPy and Pillow are required for QA collection; use the existing project environment") from exc
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("ffmpeg and ffprobe must be available on PATH")
    REVIEW.mkdir(parents=True, exist_ok=True)
    movie_stat_before = movie.stat()
    movie_hash_before = sha256_file(movie)
    final_dir = REVIEW / ("encoded-qa-" + movie_hash_before[:12])
    if final_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing encoded QA folder: {final_dir.name}")
    temp_dir = Path(tempfile.mkdtemp(prefix=".encoded-qa-" + movie_hash_before[:12] + "-", dir=REVIEW))
    try:
        measured, checks = check_media_spec(probe_movie(ffprobe, movie))
        loudness = collect_loudness(ffmpeg, movie)
        phone_dir = temp_dir / "phone"
        native_dir = temp_dir / "native"
        phone_paths = extract_frames(ffmpeg, movie, collected_frames, phone_dir, native=False)
        native_paths = extract_frames(ffmpeg, movie, NATIVE_FRAMES, native_dir, native=True)
        contacts = make_contact_sheets(phone_paths, collected_frames, temp_dir)
        motion = motion_measurements(phone_dir, pairs)
        movie_hash_after = sha256_file(movie)
        movie_stat_after = movie.stat()
        stable = movie_hash_before == movie_hash_after and (movie_stat_before.st_size, movie_stat_before.st_mtime_ns) == (movie_stat_after.st_size, movie_stat_after.st_mtime_ns)
        checks.append({"name": "movie_unchanged_during_collection", "status": "PASS" if stable else "FAIL", "sha256Before": movie_hash_before, "sha256After": movie_hash_after})
        qa = manifest.get("qa") if isinstance(manifest.get("qa"), dict) else {}
        report = {
            "schemaVersion": 1,
            "createdAtUtc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "work": {"id": WORK_ID, "title": WORK_TITLE, "cueIds": [row["id"] for row in cues]},
            "movie": {"manifestPath": str(movie.relative_to(DELIVERY)), "sha256": movie_hash_after, "bytes": movie_stat_after.st_size},
            "encodedMediaMeasurements": measured,
            "ebuR128": loudness,
            "checks": checks,
            "frameCollection": {
                "status": "COLLECTED",
                "phoneThumbnailSize": list(PHONE_SIZE),
                "requiredPhoneFrameNumbers": list(PHONE_FRAMES),
                "phoneFrameNumbers": list(collected_frames),
                "phoneFrameFiles": ["phone/" + path.name for path in phone_paths],
                "nativeFrameNumbers2160x3840": list(NATIVE_FRAMES),
                "nativeFrameFiles": ["native/" + path.name for path in native_paths],
                "chronologicalNativeFrameLabels": [{"frame": entry["frame"], "label": entry["label"]} for entry in native_entries],
                "covers": {key: {"frame": frame, "nativeFrameFile": f"native/frame_{frame:04d}.png"} for key, frame in COVER_FRAMES.items()},
                "phoneContactSheets": contacts,
            },
            "motionHeuristics": {
                "status": "MEASURED_HEURISTIC_ONLY",
                "method": "Mean absolute RGB difference in the human-and-shadow stage crop (logical x=90..900, y=430..1290, mapped to 360x640 phone pixels).",
                "pairs": motion,
                "notAVisualPass": True,
            },
            "visualScan": {"status": "NOT_RUN_BY_THIS_COLLECTOR", "reportPath": "review/visual-qc-xiaohongshu/report.json"},
            "humanAcceptance": {
                "representativeFrames": str(qa.get("representative_frames", "pending")).upper(),
                "continuousHumanReview": str(qa.get("continuous_human_review", "pending")).upper(),
                "targetDevicePlayback": str(qa.get("target_device_playback", "pending")).upper(),
            },
        }
        if not stable:
            raise RuntimeError("Final MP4 changed during QA collection")
        (temp_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.rename(temp_dir, final_dir)
        print(json.dumps({"reportPath": str((final_dir / "report.json").relative_to(DELIVERY)), **report}, ensure_ascii=False, indent=2))
        return 0 if all(check["status"] == "PASS" for check in checks) else 1
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", None) or str(exc)
        print("collect_qa: " + str(detail), file=sys.stderr)
        raise SystemExit(2)
