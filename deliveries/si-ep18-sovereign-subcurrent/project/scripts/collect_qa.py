#!/usr/bin/env python3
"""Collect fresh encoded EP18 media metadata, cue frames, phone contact sheets, and motion heuristics."""

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

PROJECT_DIR = Path(__file__).resolve().parents[1]
DELIVERY_DIR = PROJECT_DIR.parent
DELIVERY_JSON = DELIVERY_DIR / "delivery.json"
REVIEW_DIR = DELIVERY_DIR / "review"
EXPECTED_FRAME_COUNT = 5_400
EXPECTED_WIDTH = 2_160
EXPECTED_HEIGHT = 3_840
EXPECTED_FPS = Fraction(60, 1)
NATIVE_REVIEW_FRAMES = {"S03-private-current": 1_650, "cover-B": 2_160, "S04-memory-boundary": 2_400, "cover-A": 3_960}
DARK_CROP_CUES = {"S03-private-current", "S04-memory-boundary"}
PHONE_SIZE = (360, 640)
PHONE_CROP = (40, 180, 292, 416)


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


def resolve_final_movie() -> Path:
    manifest = read_json(DELIVERY_JSON)
    outputs = manifest.get("outputs")
    entry = outputs.get("xiaohongshu") if isinstance(outputs, dict) else None
    relative_path = entry.get("path") if isinstance(entry, dict) else None
    if manifest.get("slug") != "si-ep18-sovereign-subcurrent" or manifest.get("platforms") != ["xiaohongshu"]:
        raise RuntimeError("EP18 delivery identity or platform set is not the expected Xiaohongshu-only work")
    if relative_path != "小红书/si-ep18-sovereign-subcurrent-xiaohongshu-90s-portrait.mp4":
        raise RuntimeError("delivery.json does not point to the exact EP18 final movie path")
    root = DELIVERY_DIR.resolve()
    movie = (DELIVERY_DIR / relative_path).resolve()
    if not movie.is_relative_to(root) or movie.suffix.lower() != ".mp4" or not movie.is_file():
        raise FileNotFoundError("The manifest-bound EP18 final MP4 is unavailable or outside the delivery")
    return movie


def read_cues() -> list[dict[str, Any]]:
    cues = read_json(PROJECT_DIR / "segments.json")
    expected_ids = ["S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08"]
    if not isinstance(cues, list) or [row.get("id") for row in cues if isinstance(row, dict)] != expected_ids:
        raise RuntimeError("Expected exactly EP18 segment cues S01-S08")
    for row in cues:
        if not isinstance(row.get("startFrame"), int) or not isinstance(row.get("endFrame"), int):
            raise RuntimeError("EP18 cue frame bounds must be integer values")
        if not (0 <= row["startFrame"] < row["endFrame"] <= EXPECTED_FRAME_COUNT):
            raise RuntimeError("EP18 cue bounds must fit within the native 5400-frame timeline")
    return cues


def probe_movie(ffprobe: str, movie: Path) -> dict[str, Any]:
    result = run([ffprobe, "-v", "error", "-threads", "2", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(movie)])
    return json.loads(result.stdout)


def check_video_stream(probe: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    streams = probe.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), {})
    avg_rate = parse_fraction(video.get("avg_frame_rate"))
    frame_count = None
    for field in ("nb_read_frames", "nb_frames"):
        try:
            if video.get(field) not in (None, "N/A"):
                frame_count = int(video[field])
                break
        except (TypeError, ValueError):
            pass
    stream_duration = parse_float(video.get("duration"))
    format_duration = parse_float((probe.get("format") or {}).get("duration"))
    actual = {
        "video": {
            "codecName": video.get("codec_name"),
            "width": video.get("width"),
            "height": video.get("height"),
            "pixelFormat": video.get("pix_fmt"),
            "avgFrameRate": video.get("avg_frame_rate"),
            "rFrameRate": video.get("r_frame_rate"),
            "countedFrames": frame_count,
            "streamDurationSeconds": stream_duration,
            "durationFromFramesSeconds": (frame_count / float(avg_rate)) if frame_count is not None and avg_rate else None,
        },
        "audio": {
            "codecName": audio.get("codec_name"),
            "sampleRateHz": int(audio["sample_rate"]) if str(audio.get("sample_rate", "")).isdigit() else None,
            "channels": audio.get("channels"),
            "channelLayout": audio.get("channel_layout"),
            "streamDurationSeconds": parse_float(audio.get("duration")),
        },
        "container": {
            "formatName": (probe.get("format") or {}).get("format_name"),
            "sizeBytes": int((probe.get("format") or {}).get("size", 0) or 0),
            "durationSeconds": format_duration,
        },
    }
    duration_ok = stream_duration is not None and abs(stream_duration - 90.0) <= (1 / 60) + 0.001
    format_duration_ok = format_duration is not None and abs(format_duration - 90.0) <= 0.05
    video_ok = (
        video.get("codec_name") == "h264" and video.get("pix_fmt") == "yuv420p"
        and video.get("width") == EXPECTED_WIDTH and video.get("height") == EXPECTED_HEIGHT
        and avg_rate == EXPECTED_FPS and frame_count == EXPECTED_FRAME_COUNT
        and duration_ok and format_duration_ok
        and audio.get("codec_name") == "aac"
        and str(audio.get("sample_rate")) == "48000" and audio.get("channels") == 2
    )
    return actual, [{
        "name": "encoded_native_media_spec",
        "status": "PASS" if video_ok else "FAIL",
        "details": {
            "expected": {"codec": "h264", "pixelFormat": "yuv420p", "width": EXPECTED_WIDTH, "height": EXPECTED_HEIGHT, "fps": "60/1", "frames": EXPECTED_FRAME_COUNT, "durationSeconds": 90, "audioCodec": "aac", "audioSampleRateHz": 48000, "audioChannels": 2},
            "measured": actual,
        },
    }]


def collect_ebur128(ffmpeg: str, movie: Path) -> dict[str, Any]:
    result = run([ffmpeg, "-hide_banner", "-nostats", "-i", str(movie), "-map", "0:a:0", "-af", "ebur128=peak=true", "-f", "null", "-"])
    stderr = result.stderr
    summary_at = stderr.rfind("Summary:")
    summary_tail = stderr[summary_at:] if summary_at >= 0 else stderr
    integrated = re.search(r"\bI:\s*(-?\d+(?:\.\d+)?)\s*LUFS", summary_tail)
    true_peak = re.search(r"\bPeak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", summary_tail)
    if integrated is None or true_peak is None:
        raise RuntimeError("ffmpeg ebur128 did not return final integrated-loudness and true-peak values")
    return {"integratedLoudnessLufs": float(integrated.group(1)), "truePeakDbfs": float(true_peak.group(1)), "summaryTail": "\n".join(summary_tail.splitlines()[-40:])}


def select_frames(cues: list[dict[str, Any]]) -> list[int]:
    frames = {0, 2160, 3960, 4859, 4860, 4889, 4890, EXPECTED_FRAME_COUNT - 1}
    for cue in cues:
        start, end = cue["startFrame"], cue["endFrame"]
        frames.update((min(end - 1, start + 30), min(end - 1, start + 180), (start + end - 1) // 2, max(start, end - 1)))
    return sorted(frame for frame in frames if 0 <= frame < EXPECTED_FRAME_COUNT)


def motion_pairs(cues: list[dict[str, Any]]) -> list[tuple[str, int, int]]:
    pairs = []
    for cue in cues:
        start, end = cue["startFrame"], cue["endFrame"]
        first = min(end - 2, start + 30)
        second = min(end - 1, start + 180)
        if second > first:
            pairs.append((cue["id"], first, second))
    return pairs


def extract_selected_frames(ffmpeg: str, movie: Path, frames: list[int], output_dir: Path, *, native: bool) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = "selected-native" if native else "selected-phone"
    pattern = output_dir / (prefix + "_%03d.png")
    expression = "select='" + "+".join("eq(n," + str(frame) + ")" for frame in frames) + "'"
    if not native:
        expression += ",scale=360:640:force_original_aspect_ratio=decrease:flags=lanczos,pad=360:640:(ow-iw)/2:(oh-ih)/2"
    run([ffmpeg, "-hide_banner", "-loglevel", "error", "-threads", "2", "-filter_threads", "2", "-i", str(movie), "-map", "0:v:0", "-vf", expression, "-fps_mode", "passthrough", "-start_number", "0", str(pattern)])
    selected = sorted(output_dir.glob(prefix + "_*.png"))
    if len(selected) != len(frames):
        raise RuntimeError("Expected " + str(len(frames)) + " extracted frames; received " + str(len(selected)))
    final_paths = []
    for frame, temporary_path in zip(frames, selected):
        final_path = output_dir / ("frame_" + str(frame).zfill(4) + ".png")
        temporary_path.rename(final_path)
        final_paths.append(final_path)
    return final_paths


def make_contact_sheets(thumb_paths: list[Path], frame_numbers: list[int], output_dir: Path) -> list[str]:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RuntimeError("Pillow is required for phone contact sheets; use the existing Python environment with Pillow") from exc
    try:
        font = ImageFont.load_default(size=18)
    except TypeError:
        font = ImageFont.load_default()
    paths = []
    for panel_number, offset in enumerate(range(0, len(thumb_paths), 9), start=1):
        panel = Image.new("RGB", (1080, 1920), "#09090B")
        draw = ImageDraw.Draw(panel)
        for local_index, (image_path, frame) in enumerate(zip(thumb_paths[offset:offset + 9], frame_numbers[offset:offset + 9])):
            with Image.open(image_path) as opened:
                image = opened.convert("RGB")
            if image.size != PHONE_SIZE:
                raise RuntimeError("Unexpected phone thumbnail size at frame " + str(frame) + ": " + str(image.size))
            column, row = local_index % 3, local_index // 3
            x, y = column * 360, row * 640
            panel.paste(image, (x, y))
            draw.rectangle((x, y, x + 135, y + 28), fill="#09090B")
            draw.text((x + 6, y + 4), "F" + str(frame).zfill(4), fill="#FAFAFA", font=font)
        filename = "phone-contact-" + str(panel_number).zfill(2) + ".jpg"
        panel.save(output_dir / filename, quality=92, optimize=True)
        paths.append(filename)
    return paths


def compute_motion_heuristics(thumb_dir: Path, pairs: list[tuple[str, int, int]]) -> list[dict[str, Any]]:
    try:
        import numpy as np
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("NumPy and Pillow are required for motion heuristics; use the existing bundled Python environment") from exc
    output = []
    for cue_id, start, end in pairs:
        images = []
        for frame in (start, end):
            with Image.open(thumb_dir / ("frame_" + str(frame).zfill(4) + ".png")) as image:
                images.append(np.asarray(image.convert("RGB").crop(PHONE_CROP), dtype=np.int16))
        difference = float(np.abs(images[0] - images[1]).mean())
        output.append({"cueId": cue_id, "frames": [start, end], "cropXyxyOn360x640PhoneFrame": list(PHONE_CROP), "meanAbsoluteRgbDifference0To255": round(difference, 6), "interpretation": "measurement only; not a visual pass or proof of meaningful motion"})
    return output


def make_native_inspection_crops(native_dir: Path, output_dir: Path) -> list[dict[str, Any]]:
    from PIL import Image
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for cue_id, frame in NATIVE_REVIEW_FRAMES.items():
        if cue_id not in DARK_CROP_CUES:
            continue
        source = native_dir / ("frame_" + str(frame).zfill(4) + ".png")
        with Image.open(source) as image:
            if image.size != (EXPECTED_WIDTH, EXPECTED_HEIGHT):
                raise RuntimeError("Native inspection frame is not 2160x3840: " + str(source.name))
            box = (240, 840, 1920, 3000)
            crop = image.crop(box)
            destination = output_dir / (cue_id.lower() + "-frame-" + str(frame).zfill(4) + "-native-pixels.png")
            crop.save(destination, optimize=True)
            results.append({"cueId": cue_id, "frame": frame, "sourceNativeFrame": "native/" + source.name, "cropFile": "native-crops/" + destination.name, "cropBoxXyxy2160x3840": list(box), "pixelDimensions": list(crop.size), "qualityStatus": "NOT_ASSESSED"})
    return results


def main() -> int:
    movie = resolve_final_movie()
    cues = read_cues()
    frame_numbers = select_frames(cues)
    pairs = motion_pairs(cues)
    native_frames = sorted(set(NATIVE_REVIEW_FRAMES.values()))
    try:
        import numpy  # noqa: F401
        from PIL import Image, ImageDraw, ImageFont  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("NumPy and Pillow are required for QA collection; use the existing bundled Python environment") from exc
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("ffmpeg and ffprobe must be available on PATH")
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    movie_hash_before = sha256_file(movie)
    final_dir = REVIEW_DIR / ("encoded-qa-" + movie_hash_before[:12])
    if final_dir.exists():
        raise FileExistsError("Refusing to overwrite existing encoded QA folder: " + str(final_dir))
    probe = probe_movie(ffprobe, movie)
    encoded_actual, checks = check_video_stream(probe)
    loudness = collect_ebur128(ffmpeg, movie)
    temp_dir = Path(tempfile.mkdtemp(prefix=".encoded-qa-" + movie_hash_before[:12] + "-", dir=REVIEW_DIR))
    phone_dir, native_dir = temp_dir / "phone", temp_dir / "native"
    phone_paths = extract_selected_frames(ffmpeg, movie, frame_numbers, phone_dir, native=False)
    native_paths = extract_selected_frames(ffmpeg, movie, native_frames, native_dir, native=True)
    contacts = make_contact_sheets(phone_paths, frame_numbers, temp_dir)
    motion = compute_motion_heuristics(phone_dir, pairs)
    crops = make_native_inspection_crops(native_dir, temp_dir / "native-crops")
    hash_after = sha256_file(movie)
    stable = movie_hash_before == hash_after
    checks.append({"name": "movie_unchanged_during_collection", "status": "PASS" if stable else "FAIL", "details": {"sha256Before": movie_hash_before, "sha256After": hash_after}})
    report = {
        "schemaVersion": 1,
        "createdAtUtc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "work": {"id": "si-ep18-sovereign-subcurrent", "title": "心印潜流", "cueIds": [row["id"] for row in cues]},
        "movie": {"manifestPath": str(movie.relative_to(DELIVERY_DIR)), "sha256": hash_after, "bytes": movie.stat().st_size},
        "ffprobe": encoded_actual,
        "ebuR128": loudness,
        "checks": checks,
        "frameCollection": {
            "status": "COLLECTED",
            "decodeMethod": "Sequential ffmpeg frame-select passes: phone-sized thumbnails for all cue windows and native 2160x3840 frames for named scene/covers.",
            "phoneThumbnailSize": list(PHONE_SIZE),
            "phoneFrameNumbers": frame_numbers,
            "nativeFrameNumbers2160x3840": native_frames,
            "nativeFrameFiles": ["native/" + path.name for path in native_paths],
            "nativeInspectionCrops": crops,
            "contactSheetGrid": [3, 3],
            "phoneContactSheets": contacts,
        },
        "motionHeuristics": {"status": "MEASURED_HEURISTIC_ONLY", "method": "Mean absolute RGB difference inside the same 252x236 central phone-frame crop for one pair in each of the eight EP18 cue windows.", "pairs": motion, "notAVisualPass": True},
        "visualObservations": "NOT_RUN",
        "humanAcceptance": {
            "representativeFrames": str((read_json(DELIVERY_JSON).get("qa") or {}).get("representative_frames", "pending")).upper(),
            "continuousHumanReview": str((read_json(DELIVERY_JSON).get("qa") or {}).get("continuous_human_review", "pending")).upper(),
            "targetDevicePlayback": str((read_json(DELIVERY_JSON).get("qa") or {}).get("target_device_playback", "pending")).upper(),
        },
    }
    (temp_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not stable:
        raise RuntimeError("Final MP4 changed during QA collection; partial evidence remains at " + str(temp_dir))
    os.rename(temp_dir, final_dir)
    print(json.dumps({"reportPath": str((final_dir / "report.json").relative_to(DELIVERY_DIR)), **report}, ensure_ascii=False, indent=2))
    return 0 if all(check["status"] == "PASS" for check in checks) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", None) or str(exc)
        print("collect_qa: " + str(detail), file=sys.stderr)
        raise SystemExit(2)
