#!/usr/bin/env python3
"""Collect encoded EP17 metadata, selected frames, loudness, and motion heuristics."""

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

FRAME_NUMBERS = [
    0, 60, 180, 210, 660, 720, 840, 870, 1319, 1320, 1500, 1650, 1980,
    2160, 2310, 2760, 2820, 2940, 3060, 3090, 3540, 3600, 3900, 3960,
    4110, 4380, 4500, 4650, 4859, 4860, 4889, 4890, 4902, 4950, 5100,
    5160, 5190, 5340, 5399,
]
NATIVE_FRAME_NUMBERS = [2160, 3960, 4890, 5399]
MOTION_PAIRS = [
    (60, 210), (720, 870), (1500, 1650), (2160, 2310), (2940, 3090),
    (3960, 4110), (4500, 4650), (4950, 5100), (5190, 5340),
]
EXPECTED_FRAME_COUNT = 5400
EXPECTED_WIDTH = 2160
EXPECTED_HEIGHT = 3840
EXPECTED_FPS = Fraction(60, 1)


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
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise RuntimeError("delivery.json has no outputs.xiaohongshu.path")
    movie = (DELIVERY_DIR / relative_path).resolve()
    if not movie.is_relative_to(DELIVERY_DIR.resolve()):
        raise RuntimeError("delivery.json final movie path escapes the delivery folder")
    if movie.suffix.lower() != ".mp4":
        raise RuntimeError(f"delivery.json final movie is not an MP4: {movie.name}")
    if not movie.is_file():
        raise FileNotFoundError(f"Final MP4 from delivery.json is unavailable: {movie}")
    return movie


def probe_movie(ffprobe: str, movie: Path) -> dict[str, Any]:
    result = run([
        ffprobe,
        "-v", "error",
        "-threads", "2",
        "-count_frames",
        "-show_streams",
        "-show_format",
        "-of", "json",
        str(movie),
    ])
    return json.loads(result.stdout)


def check_video_stream(probe: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    streams = probe.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), {})
    avg_rate = parse_fraction(video.get("avg_frame_rate"))
    real_rate = parse_fraction(video.get("r_frame_rate"))
    frame_count = None
    for field in ("nb_read_frames", "nb_frames"):
        value = video.get(field)
        try:
            if value not in (None, "N/A"):
                frame_count = int(value)
                break
        except (TypeError, ValueError):
            pass
    stream_duration = parse_float(video.get("duration"))
    format_duration = parse_float((probe.get("format") or {}).get("duration"))
    actual = {
        "video": {
            "codec_name": video.get("codec_name"),
            "width": video.get("width"),
            "height": video.get("height"),
            "pixel_format": video.get("pix_fmt"),
            "avg_frame_rate": video.get("avg_frame_rate"),
            "r_frame_rate": video.get("r_frame_rate"),
            "counted_frames": frame_count,
            "stream_duration_seconds": stream_duration,
            "duration_from_frames_seconds": (frame_count / float(avg_rate)) if frame_count and avg_rate else None,
        },
        "audio": {
            "codec_name": audio.get("codec_name"),
            "sample_rate_hz": int(audio["sample_rate"]) if str(audio.get("sample_rate", "")).isdigit() else None,
            "channels": audio.get("channels"),
            "channel_layout": audio.get("channel_layout"),
            "stream_duration_seconds": parse_float(audio.get("duration")),
        },
        "container": {
            "format_name": (probe.get("format") or {}).get("format_name"),
            "size_bytes": int((probe.get("format") or {}).get("size", 0) or 0),
            "duration_seconds": format_duration,
        },
    }
    duration_ok = (
        stream_duration is None
        or abs(stream_duration - 90.0) <= (1 / 60) + 0.001
    )
    video_ok = (
        video.get("width") == EXPECTED_WIDTH
        and video.get("height") == EXPECTED_HEIGHT
        and avg_rate == EXPECTED_FPS
        and frame_count == EXPECTED_FRAME_COUNT
        and duration_ok
        and bool(audio)
    )
    checks = [{
        "name": "encoded_video_spec",
        "status": "PASS" if video_ok else "FAIL",
        "details": {
            "expected": {
                "width": EXPECTED_WIDTH,
                "height": EXPECTED_HEIGHT,
                "fps": "60/1",
                "frames": EXPECTED_FRAME_COUNT,
                "duration_seconds": 90,
                "audio_stream_required": True,
            },
            "measured": actual,
        },
    }]
    return actual, checks


def collect_ebur128(ffmpeg: str, movie: Path) -> dict[str, Any]:
    result = run([
        ffmpeg,
        "-hide_banner",
        "-nostats",
        "-i", str(movie),
        "-map", "0:a:0",
        "-af", "ebur128=peak=true",
        "-f", "null", "-",
    ])
    stderr = result.stderr
    summary_at = stderr.rfind("Summary:")
    summary_tail = stderr[summary_at:] if summary_at >= 0 else stderr
    integrated = re.search(r"\bI:\s*(-?\d+(?:\.\d+)?)\s*LUFS", summary_tail)
    true_peak = re.search(r"\bPeak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", summary_tail)
    if integrated is None or true_peak is None:
        raise RuntimeError("ffmpeg ebur128 did not return final integrated-loudness and true-peak values")
    return {
        "integrated_loudness_lufs": float(integrated.group(1)),
        "true_peak_dbfs": float(true_peak.group(1)),
        "summary_tail": "\n".join(summary_tail.splitlines()[-40:]),
    }


def select_expression(frames: list[int]) -> str:
    # Quoting keeps expression commas inside eq() from being parsed as filter separators.
    return "select='" + "+".join(f"eq(n,{frame})" for frame in frames) + "'"


def extract_selected_frames(ffmpeg: str, movie: Path, frames: list[int], output_dir: Path, *, native: bool) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = "selected-native" if native else "selected-thumb"
    pattern = output_dir / f"{prefix}_%03d.png"
    video_filter = select_expression(frames)
    if not native:
        video_filter += ",scale=360:640:force_original_aspect_ratio=decrease:flags=lanczos,pad=360:640:(ow-iw)/2:(oh-ih)/2"
    run([
        ffmpeg,
        "-hide_banner",
        "-loglevel", "error",
        "-threads", "2", "-filter_threads", "2",
        "-i", str(movie),
        "-map", "0:v:0",
        "-vf", video_filter,
        "-fps_mode", "passthrough",
        "-start_number", "0",
        str(pattern),
    ])
    selected = sorted(output_dir.glob(f"{prefix}_*.png"))
    if len(selected) != len(frames):
        raise RuntimeError(f"Expected {len(frames)} selected frames, received {len(selected)}")
    final_paths: list[Path] = []
    for frame, temporary_path in zip(frames, selected):
        expected_name = f"frame_{frame:04d}.png"
        final_path = output_dir / expected_name
        temporary_path.rename(final_path)
        final_paths.append(final_path)
    return final_paths


def make_contact_sheets(thumb_paths: list[Path], frame_numbers: list[int], output_dir: Path) -> list[str]:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RuntimeError("Pillow is required for contact sheets; use the existing /opt/anaconda3/bin/python environment") from exc

    font = None
    try:
        font = ImageFont.load_default(size=18)
    except TypeError:
        font = ImageFont.load_default()
    panel_paths: list[str] = []
    for panel_number, offset in enumerate(range(0, len(thumb_paths), 9), start=1):
        panel = Image.new("RGB", (1080, 1920), "#09090B")
        draw = ImageDraw.Draw(panel)
        for local_index, (path, frame) in enumerate(zip(thumb_paths[offset:offset + 9], frame_numbers[offset:offset + 9])):
            with Image.open(path) as opened:
                image = opened.convert("RGB")
            if image.size != (360, 640):
                raise RuntimeError(f"Unexpected thumbnail size at frame {frame}: {image.size}")
            column, row = local_index % 3, local_index // 3
            x, y = column * 360, row * 640
            panel.paste(image, (x, y))
            draw.rectangle((x, y, x + 106, y + 28), fill="#09090B")
            draw.text((x + 6, y + 4), f"F{frame:04d}", fill="#FAFAFA", font=font)
        panel_path = output_dir / f"contact-{panel_number:02d}.jpg"
        panel.save(panel_path, quality=92, optimize=True)
        panel_paths.append(panel_path.name)
    return panel_paths


def compute_motion_heuristics(thumb_dir: Path) -> list[dict[str, Any]]:
    try:
        import numpy as np
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("NumPy and Pillow are required for crop-difference heuristics; use /opt/anaconda3/bin/python") from exc

    output = []
    for start, end in MOTION_PAIRS:
        images = []
        for frame in (start, end):
            with Image.open(thumb_dir / f"frame_{frame:04d}.png") as image:
                crop = image.convert("RGB").crop((40, 180, 292, 416))
                images.append(np.asarray(crop, dtype=np.int16))
        mean_abs_diff = float(np.abs(images[0] - images[1]).mean())
        output.append({
            "frames": [start, end],
            "crop_xyxy_on_360x640_thumb": [40, 180, 292, 416],
            "mean_absolute_rgb_difference_0_255": round(mean_abs_diff, 6),
            "interpretation": "heuristic only; not a visual pass or proof of meaningful motion",
        })
    return output


def main() -> int:
    movie = resolve_final_movie()
    try:
        import numpy  # noqa: F401
        from PIL import Image, ImageDraw, ImageFont  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("NumPy and Pillow are required for QA images; run with the existing /opt/anaconda3/bin/python") from exc
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("Both ffmpeg and ffprobe must be available on PATH")
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)

    movie_hash_before = sha256_file(movie)
    final_dir = REVIEW_DIR / f"encoded-qa-{movie_hash_before[:12]}"
    if final_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing QA output folder: {final_dir}")

    probe = probe_movie(ffprobe, movie)
    encoded_actual, checks = check_video_stream(probe)
    loudness = collect_ebur128(ffmpeg, movie)

    temp_dir = Path(tempfile.mkdtemp(prefix=f".encoded-qa-{movie_hash_before[:12]}-", dir=REVIEW_DIR))
    thumbs_dir = temp_dir / "thumbs"
    native_dir = temp_dir / "native"
    thumb_paths = extract_selected_frames(ffmpeg, movie, FRAME_NUMBERS, thumbs_dir, native=False)
    native_paths = extract_selected_frames(ffmpeg, movie, NATIVE_FRAME_NUMBERS, native_dir, native=True)
    contacts = make_contact_sheets(thumb_paths, FRAME_NUMBERS, temp_dir)
    motion = compute_motion_heuristics(thumbs_dir)

    movie_hash_after = sha256_file(movie)
    hash_stable = movie_hash_before == movie_hash_after
    checks.append({
        "name": "movie_unchanged_during_collection",
        "status": "PASS" if hash_stable else "FAIL",
        "details": {"sha256_before": movie_hash_before, "sha256_after": movie_hash_after},
    })
    report = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "movie": {
            "manifest_path": str(movie.relative_to(DELIVERY_DIR)),
            "sha256": movie_hash_after,
            "bytes": movie.stat().st_size,
        },
        "ffprobe": encoded_actual,
        "ebur128": loudness,
        "checks": checks,
        "frame_collection": {
            "status": "COLLECTED",
            "decode_method": "ffmpeg select=eq(n,frame) in one sequential pass for all 360x640 thumbnails; a second sequential pass extracts only the four requested native frames",
            "thumbnail_size": [360, 640],
            "thumbnail_frames": FRAME_NUMBERS,
            "native_frames_2160x3840": NATIVE_FRAME_NUMBERS,
            "native_frame_files": [f"native/{path.name}" for path in native_paths],
            "contact_sheets_max_grid": [3, 3],
            "contact_sheets": contacts,
        },
        "motion_heuristics": {
            "status": "MEASURED_HEURISTIC_ONLY",
            "method": "mean absolute RGB difference on 360x640 thumbnail crop x=40..292, y=180..416",
            "pairs": motion,
            "not_a_visual_pass": True,
        },
        "visual_observations": "NOT_RUN",
        "qa_statuses": {
            "model_visual_review": "PENDING",
            "human_visual_review": "PENDING",
            "device_playback": "NOT_RUN",
        },
    }
    (temp_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not hash_stable:
        raise RuntimeError(f"Final MP4 changed during collection; partial QA evidence kept at {temp_dir}")
    os.rename(temp_dir, final_dir)
    print(json.dumps({"report_path": str(final_dir.relative_to(DELIVERY_DIR) / "report.json"), **report}, ensure_ascii=False, indent=2))
    return 0 if all(check["status"] == "PASS" for check in checks) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", None) or str(exc)
        print(f"collect_qa: {detail}", file=sys.stderr)
        raise SystemExit(2)
