#!/usr/bin/env python3
"""Collect final-media measurements and compact visual evidence for EP07.

This script records encoded-file metadata, loudness, representative frames,
subject-region frame differences, and short AAC-to-PCM comparisons. It does
not judge visual quality, run full-frame visual QC, transcribe audio, or claim
human review or continuous listening.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DELIVERY_DIR = PROJECT_DIR.parent
MANIFEST_PATH = DELIVERY_DIR / "delivery.json"
AUDIO_TIMING_PATH = PROJECT_DIR / "audio-timing.json"
REVIEW_DIR = DELIVERY_DIR / "review"
EVIDENCE_DIR = REVIEW_DIR / "final-media-evidence"
REPORT_PATH = REVIEW_DIR / "final-media-evidence.json"
FPS = 60
DURATION_SECONDS = 120
TOTAL_FRAMES = 7200
SAMPLE_RATE = 48_000
AUDIO_WINDOW_SECONDS = 2
SAMPLE_FRAMES = (
    120, 360, 960, 1500, 2099, 2100, 2250, 3000, 3899, 3900,
    4800, 5879, 5880, 5909, 5910, 6000, 6600, 7100, 7199,
)
PAIR_START_SECONDS = (6, 12, 24, 32, 43, 51, 62, 73, 83, 92, 100, 108, 116)
PAIR_GAP_FRAMES = round(2.5 * FPS)
PAIR_FRAMES = tuple((seconds * FPS, seconds * FPS + PAIR_GAP_FRAMES) for seconds in PAIR_START_SECONDS)
LAYOUTS = {
    "landscape": {"manifest_key": "bilibili", "width": 3840, "height": 2160, "tile_width": 640},
    "portrait": {"manifest_key": "xiaohongshu", "width": 2160, "height": 3840, "tile_width": 360},
}


class CollectionError(RuntimeError):
    pass


class MissingTool(CollectionError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    return parser.parse_args()


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CollectionError(f"cannot read {label}: {exc}") from None
    if not isinstance(value, dict):
        raise CollectionError(f"{label} must contain a JSON object")
    return value


def contained_path(base: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise CollectionError(f"{label} path is missing")
    path = (base / value).resolve()
    try:
        path.relative_to(base.resolve())
    except ValueError:
        raise CollectionError(f"{label} path escapes its owning directory") from None
    return path


def relative_path(path: Path) -> str:
    return path.resolve().relative_to(DELIVERY_DIR.resolve()).as_posix()


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise MissingTool(f"required executable is unavailable on PATH: {name}")
    return path


def run_capture(argv: list[str], label: str, *, timeout: int = 1800) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(
            argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CollectionError(f"{label} could not complete: {exc}") from None
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()[-1600:]
        raise CollectionError(f"{label} failed ({result.returncode}): {detail or 'no diagnostics'}")
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    return {"path": relative_path(path), "size_bytes": path.stat().st_size, "sha256": sha256_file(path)}


def file_identity(path: Path) -> tuple[int, str]:
    return path.stat().st_size, sha256_file(path)


def ffprobe_media(ffprobe: str, media: Path) -> dict[str, Any]:
    result = run_capture(
        [ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(media)],
        f"ffprobe {media.name}", timeout=90,
    )
    try:
        probe = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise CollectionError(f"ffprobe returned invalid JSON for {media.name}") from None
    if not isinstance(probe, dict) or not isinstance(probe.get("streams"), list):
        raise CollectionError(f"ffprobe returned incomplete metadata for {media.name}")
    video = next((stream for stream in probe["streams"] if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in probe["streams"] if stream.get("codec_type") == "audio"), None)
    if video is None or audio is None:
        raise CollectionError(f"{media.name} must contain both video and audio streams")
    return probe


def measure_loudness(ffmpeg: str, media: Path) -> dict[str, Any]:
    result = run_capture(
        [ffmpeg, "-hide_banner", "-nostats", "-nostdin", "-i", str(media), "-map", "0:a:0",
         "-af", "ebur128=peak=true", "-f", "null", "-"],
        f"full-stream ebur128 measurement for {media.name}", timeout=1800,
    )
    output = result.stderr.decode("utf-8", errors="replace")
    integrated = re.search(r"(?m)^\s*I:\s*(-?\d+(?:\.\d+)?)\s+LUFS\s*$", output)
    true_peak = re.search(r"(?m)^\s*True peak:\s*(-?\d+(?:\.\d+)?)\s+dBTP\s*$", output)
    if true_peak is None:
        true_peak = re.search(r"True peak:\s*\n\s*Peak:\s*(-?\d+(?:\.\d+)?)\s+dBFS", output)
    if integrated is None or true_peak is None:
        raise CollectionError(f"ebur128 did not report integrated loudness and true peak for {media.name}")
    return {
        "method": "FFmpeg ebur128=peak=true over the complete encoded audio stream",
        "integrated_lufs": float(integrated.group(1)),
        "true_peak_dbTP": float(true_peak.group(1)),
    }


def decode_audio_window(ffmpeg: str, media: Path, start_seconds: int) -> bytes:
    result = run_capture(
        [ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error", "-i", str(media),
         "-ss", str(start_seconds), "-t", str(AUDIO_WINDOW_SECONDS), "-map", "0:a:0", "-vn",
         "-ar", str(SAMPLE_RATE), "-ac", "2", "-c:a", "pcm_f32le", "-f", "f32le", "pipe:1"],
        f"decode {start_seconds}s audio window from {media.name}", timeout=300,
    )
    if not result.stdout or len(result.stdout) % (2 * 4) != 0:
        raise CollectionError(f"FFmpeg returned an invalid float32 stereo window from {media.name} at {start_seconds}s")
    return result.stdout


def compare_audio_window(
    numpy: Any, ffmpeg: str, master: Path, encoded: Path, start_seconds: int,
) -> dict[str, Any]:
    master_bytes = decode_audio_window(ffmpeg, master, start_seconds)
    encoded_bytes = decode_audio_window(ffmpeg, encoded, start_seconds)
    master_samples = numpy.frombuffer(master_bytes, dtype="<f4").reshape((-1, 2))
    encoded_samples = numpy.frombuffer(encoded_bytes, dtype="<f4").reshape((-1, 2))
    common = min(len(master_samples), len(encoded_samples))
    if common == 0:
        raise CollectionError(f"empty decoded audio comparison at {start_seconds}s for {encoded.name}")
    pcm = master_samples[:common].astype(numpy.float64, copy=False)
    aac = encoded_samples[:common].astype(numpy.float64, copy=False)
    error = aac - pcm
    master_std = float(numpy.std(pcm))
    encoded_std = float(numpy.std(aac))
    if master_std <= 1e-12 or encoded_std <= 1e-12:
        correlation = None
        correlation_note = "undefined because at least one decoded window has zero variance"
    else:
        correlation = float(numpy.corrcoef(pcm.reshape(-1), aac.reshape(-1))[0, 1])
        correlation_note = None
        if not math.isfinite(correlation):
            correlation = None
            correlation_note = "undefined because the computed value was non-finite"
    return {
        "start_seconds": start_seconds,
        "duration_seconds": AUDIO_WINDOW_SECONDS,
        "sample_rate_hz": SAMPLE_RATE,
        "channels": 2,
        "master_sample_frames": len(master_samples),
        "aac_sample_frames": len(encoded_samples),
        "compared_sample_frames": common,
        "correlation": correlation,
        "correlation_note": correlation_note,
        "rmse_normalized_amplitude": float(numpy.sqrt(numpy.mean(error * error))),
        "comparison_note": "AAC-decoded float samples are lossy and are not expected to be byte-identical to the PCM master.",
    }


def image_modules() -> tuple[Any, Any, Any, Any]:
    try:
        import numpy
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise MissingTool(f"NumPy and Pillow must be available in the selected Python environment: {exc}") from None
    return numpy, Image, ImageDraw, ImageFont


def ffmpeg_select(frames: tuple[int, ...] | list[int]) -> str:
    return "+".join(f"eq(n\\,{frame})" for frame in frames)


def roi_pixels(layout: str) -> tuple[int, int, int, int]:
    width = LAYOUTS[layout]["width"]
    height = LAYOUTS[layout]["height"]
    x0 = round(width * (0.15 if layout == "portrait" else 0.20))
    x1 = int(width * (0.78 if layout == "portrait" else 0.80))
    y0 = round(height * (0.20 if layout == "portrait" else 0.20))
    y1 = int(height * (0.65 if layout == "portrait" else 0.80))
    # Even crop dimensions and origins keep the yuv420p source chroma-aligned.
    x0 -= x0 % 2
    y0 -= y0 % 2
    x1 -= x1 % 2
    y1 -= y1 % 2
    return x0, y0, x1 - x0, y1 - y0


def extract_frames(
    ffmpeg: str, media: Path, layout: str, stage: Path,
) -> tuple[dict[int, Path], dict[int, Path], dict[str, Any]]:
    tile_width = LAYOUTS[layout]["tile_width"]
    pair_indexes = tuple(sorted({frame for pair in PAIR_FRAMES for frame in pair}))
    x, y, roi_width, roi_height = roi_pixels(layout)
    graph = (
        "[0:v:0]split=2[representative_source][pair_source];"
        f"[representative_source]select='{ffmpeg_select(SAMPLE_FRAMES)}',"
        f"scale={tile_width}:-2:flags=lanczos[representatives];"
        f"[pair_source]select='{ffmpeg_select(pair_indexes)}',crop={roi_width}:{roi_height}:{x}:{y},"
        f"scale={tile_width}:-2:flags=lanczos[pairs]"
    )
    representative_pattern = stage / "representative-%04d.jpg"
    pair_pattern = stage / "roi-%04d.jpg"
    run_capture(
        [ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error", "-y", "-i", str(media),
         "-filter_complex", graph,
         "-map", "[representatives]", "-fps_mode:v:0", "passthrough", "-start_number", "0", "-q:v", "3", str(representative_pattern),
         "-map", "[pairs]", "-fps_mode:v:0", "passthrough", "-start_number", "0", "-q:v", "3", str(pair_pattern)],
        f"extract selected JPEG evidence frames from {media.name}", timeout=3600,
    )
    representative_files = sorted(stage.glob("representative-*.jpg"))
    pair_files = sorted(stage.glob("roi-*.jpg"))
    if len(representative_files) != len(SAMPLE_FRAMES):
        raise CollectionError(f"{layout} extraction returned {len(representative_files)} representative frames; expected {len(SAMPLE_FRAMES)}")
    if len(pair_files) != len(pair_indexes):
        raise CollectionError(f"{layout} extraction returned {len(pair_files)} ROI frames; expected {len(pair_indexes)}")
    representative_dir = stage / "frames"
    roi_dir = stage / "pair-roi"
    representative_dir.mkdir()
    roi_dir.mkdir()
    representatives: dict[int, Path] = {}
    pair_images: dict[int, Path] = {}
    for frame, source in zip(SAMPLE_FRAMES, representative_files, strict=True):
        target = representative_dir / f"frame-{frame:04d}.jpg"
        source.replace(target)
        representatives[frame] = target
    for frame, source in zip(pair_indexes, pair_files, strict=True):
        target = roi_dir / f"frame-{frame:04d}.jpg"
        source.replace(target)
        pair_images[frame] = target
    return representatives, pair_images, {
        "coordinate_fractions": {"portrait": {"x": [0.15, 0.78], "y": [0.20, 0.65]} if layout == "portrait" else None,
                                  "landscape": {"x": [0.20, 0.80], "y": [0.20, 0.80]} if layout == "landscape" else None},
        "pixel_crop_xywh": [x, y, roi_width, roi_height],
        "scaled_width_px": tile_width,
    }


def open_rgb(path: Path, image_module: Any) -> Any:
    try:
        with image_module.open(path) as image:
            return image.convert("RGB")
    except OSError as exc:
        raise CollectionError(f"cannot open extracted JPEG {path.name}: {exc}") from None


def image_record(path: Path) -> dict[str, Any]:
    return file_record(path)


def make_frame_contact_sheet(
    paths: dict[int, Path], *, layout: str, target: Path, modules: tuple[Any, Any, Any, Any],
) -> None:
    _, Image, ImageDraw, ImageFont = modules
    tile_width = LAYOUTS[layout]["tile_width"]
    columns = 3 if layout == "portrait" else 4
    first = open_rgb(paths[SAMPLE_FRAMES[0]], Image)
    tile_height = first.height
    card_height = tile_height + 28
    rows = math.ceil(len(SAMPLE_FRAMES) / columns)
    sheet = Image.new("RGB", (columns * tile_width, rows * card_height), (5, 8, 17))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for position, frame in enumerate(SAMPLE_FRAMES):
        x = position % columns * tile_width
        y = position // columns * card_height
        image = open_rgb(paths[frame], Image)
        sheet.paste(image, (x, y))
        draw.rectangle((x, y + tile_height, x + tile_width, y + card_height), fill=(0, 0, 0))
        draw.text((x + 6, y + tile_height + 6), f"frame {frame:04d} | {frame / FPS:.2f}s", fill=(255, 255, 255), font=font)
    sheet.save(target, format="JPEG", quality=87, optimize=True)


def normalized_rgb_mad(numpy: Any, before_path: Path, after_path: Path, image_module: Any) -> float:
    before = numpy.asarray(open_rgb(before_path, image_module), dtype=numpy.float32) / 255.0
    after = numpy.asarray(open_rgb(after_path, image_module), dtype=numpy.float32) / 255.0
    if before.shape != after.shape:
        raise CollectionError("paired subject ROI image dimensions differ")
    return float(numpy.mean(numpy.abs(after - before)))


def make_pair_contact_sheet(
    pair_images: dict[int, Path], pair_records: list[dict[str, Any]], *, layout: str,
    target: Path, modules: tuple[Any, Any, Any, Any],
) -> None:
    _, Image, ImageDraw, ImageFont = modules
    tile_width = LAYOUTS[layout]["tile_width"]
    columns = 2
    first = open_rgb(pair_images[PAIR_FRAMES[0][0]], Image)
    tile_height = first.height
    gap = 8
    card_width = tile_width * 2 + gap
    card_height = tile_height + 32
    rows = math.ceil(len(pair_records) / columns)
    sheet = Image.new("RGB", (columns * card_width, rows * card_height), (5, 8, 17))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for position, pair in enumerate(pair_records):
        x = position % columns * card_width
        y = position // columns * card_height
        before = open_rgb(pair_images[pair["start_frame"]], Image)
        after = open_rgb(pair_images[pair["end_frame"]], Image)
        sheet.paste(before, (x, y))
        sheet.paste(after, (x + tile_width + gap, y))
        draw.rectangle((x, y + tile_height, x + card_width, y + card_height), fill=(0, 0, 0))
        draw.text(
            (x + 6, y + tile_height + 6),
            f"{pair['start_seconds']}s -> {pair['end_seconds']}s | RGB MAD {pair['subject_roi_normalized_rgb_mad']:.5f}",
            fill=(255, 255, 255), font=font,
        )
    sheet.save(target, format="JPEG", quality=86, optimize=True)


def collect_layout(
    *, layout: str, media: Path, ffmpeg: str, ffprobe: str, master: Path,
    numpy: Any, modules: tuple[Any, Any, Any, Any], stage: Path,
) -> tuple[dict[str, Any], dict[int, Path]]:
    initial_identity = file_identity(media)
    probe = ffprobe_media(ffprobe, media)
    loudness = measure_loudness(ffmpeg, media)
    layout_stage = stage / layout
    layout_stage.mkdir()
    representatives, pair_images, roi = extract_frames(ffmpeg, media, layout, layout_stage)
    frame_contact = layout_stage / f"{layout}-contact-sheet.jpg"
    make_frame_contact_sheet(representatives, layout=layout, target=frame_contact, modules=modules)

    pair_records: list[dict[str, Any]] = []
    for start_frame, end_frame in PAIR_FRAMES:
        start_seconds = start_frame / FPS
        end_seconds = end_frame / FPS
        difference = normalized_rgb_mad(numpy, pair_images[start_frame], pair_images[end_frame], modules[1])
        pair_records.append({
            "start_frame": start_frame,
            "end_frame": end_frame,
            "start_seconds": start_seconds,
            "end_seconds": end_seconds,
            "gap_frames": end_frame - start_frame,
            "subject_roi_normalized_rgb_mad": difference,
            "interpretation": "measurement only; no motion pass threshold",
            "start_roi_jpeg": image_record(pair_images[start_frame]),
            "end_roi_jpeg": image_record(pair_images[end_frame]),
        })
    pair_contact = layout_stage / f"{layout}-pair-contact-sheet.jpg"
    make_pair_contact_sheet(pair_images, pair_records, layout=layout, target=pair_contact, modules=modules)

    frame_records = [
        {"frame": frame, "seconds": frame / FPS, **image_record(path)}
        for frame, path in representatives.items()
    ]
    final_identity = file_identity(media)
    if final_identity != initial_identity:
        raise CollectionError(f"{media.name} changed while evidence was being collected")
    report = {
        "layout": layout,
        "media": {**file_record(media), "ffprobe": probe, "ebur128": loudness},
        "subject_roi": roi,
        "representative_frames": frame_records,
        "contact_sheet": image_record(frame_contact),
        "paired_frame_measurements": pair_records,
        "pair_contact_sheet": image_record(pair_contact),
        "scope_note": "Encoded-frame and measurement evidence only; not a visual or listening acceptance result.",
    }
    return report, representatives


def inspect_master(master: Path) -> dict[str, Any]:
    try:
        with wave.open(str(master), "rb") as wav:
            metadata = {
                "sample_rate_hz": wav.getframerate(),
                "channels": wav.getnchannels(),
                "sample_frames_per_channel": wav.getnframes(),
                "sample_width_bytes": wav.getsampwidth(),
                "compression_type": wav.getcomptype(),
            }
    except (OSError, wave.Error) as exc:
        raise CollectionError(f"cannot inspect PCM master WAV: {exc}") from None
    return {**file_record(master), "wav": metadata}


def collect() -> dict[str, Any]:
    manifest = read_json(MANIFEST_PATH, "delivery.json")
    timing = read_json(AUDIO_TIMING_PATH, "project/audio-timing.json")
    outputs = manifest.get("outputs")
    audio = manifest.get("audio")
    if not isinstance(outputs, dict) or not isinstance(audio, dict):
        raise CollectionError("delivery.json must contain outputs and audio objects")
    master = contained_path(DELIVERY_DIR, audio.get("master"), "audio master")
    media_paths: dict[str, Path] = {}
    missing: list[str] = []
    if not master.is_file():
        missing.append(f"PCM master is missing: {relative_path(master)}")
    for layout, spec in LAYOUTS.items():
        key = spec["manifest_key"]
        output = outputs.get(key)
        if not isinstance(output, dict):
            missing.append(f"delivery.json outputs.{key} is missing")
            continue
        if (output.get("width"), output.get("height")) != (spec["width"], spec["height"]):
            raise CollectionError(f"delivery.json outputs.{key} must declare {spec['width']}x{spec['height']}")
        media = contained_path(DELIVERY_DIR, output.get("path"), f"outputs.{key}")
        media_paths[layout] = media
        if not media.is_file():
            missing.append(f"final {layout} MP4 is missing: {relative_path(media)}")
    if missing:
        raise CollectionError("required final-media inputs are missing; no evidence was collected: " + "; ".join(missing))
    if manifest.get("duration_seconds") != DURATION_SECONDS or manifest.get("fps") != FPS or manifest.get("total_frames") != TOTAL_FRAMES:
        raise CollectionError("delivery.json must declare 120 seconds, 60 fps, and 7200 frames")
    if any(end >= TOTAL_FRAMES for _, end in PAIR_FRAMES) or any(frame >= TOTAL_FRAMES for frame in SAMPLE_FRAMES):
        raise CollectionError("configured evidence frame index falls outside the declared video")

    ffmpeg = require_tool("ffmpeg")
    ffprobe = require_tool("ffprobe")
    numpy, Image, ImageDraw, ImageFont = image_modules()
    modules = (numpy, Image, ImageDraw, ImageFont)
    master_metadata = inspect_master(master)

    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".final-media-evidence-", dir=REVIEW_DIR) as temp_name:
        stage = Path(temp_name)
        layout_reports: dict[str, Any] = {}
        for layout, media in media_paths.items():
            report, _ = collect_layout(
                layout=layout, media=media, ffmpeg=ffmpeg, ffprobe=ffprobe,
                master=master, numpy=numpy, modules=modules, stage=stage,
            )
            layout_reports[layout] = report

        comparisons: list[dict[str, Any]] = []
        for layout, media in media_paths.items():
            for start_seconds in (2, 44, 98, 116):
                comparisons.append({
                    "layout": layout,
                    "encoded_media_path": relative_path(media),
                    **compare_audio_window(numpy, ffmpeg, master, media, start_seconds),
                })

        created_at = datetime.now(timezone.utc).isoformat()
        run_dir = EVIDENCE_DIR
        revision = 2
        while run_dir.exists():
            run_dir = EVIDENCE_DIR.with_name(f"{EVIDENCE_DIR.name}-r{revision:02d}")
            revision += 1

        # Rebase all staged paths to the final evidence directory before publication.
        for layout, report in layout_reports.items():
            staged_layout = stage / layout
            final_layout = run_dir / layout
            for collection in (report["representative_frames"], report["paired_frame_measurements"]):
                for item in collection:
                    for key in ("path",):
                        value = item.get(key)
                        if value and value.startswith(relative_path(staged_layout)):
                            item[key] = value.replace(relative_path(staged_layout), relative_path(final_layout), 1)
                    for key in ("start_roi_jpeg", "end_roi_jpeg"):
                        record = item.get(key)
                        if isinstance(record, dict):
                            record["path"] = record["path"].replace(relative_path(staged_layout), relative_path(final_layout), 1)
            for key in ("contact_sheet", "pair_contact_sheet"):
                record = report[key]
                record["path"] = record["path"].replace(relative_path(staged_layout), relative_path(final_layout), 1)

        result = {
            "schema_version": 1,
            "status": "evidence_collected",
            "created_at_utc": created_at,
            "delivery_manifest": {**file_record(MANIFEST_PATH), "slug": manifest.get("slug")},
            "audio_timing": {
                **file_record(AUDIO_TIMING_PATH),
                "status": timing.get("status"),
                "caption_count": len(timing.get("captions", [])) if isinstance(timing.get("captions"), list) else None,
            },
            "pcm_master": master_metadata,
            "layouts": layout_reports,
            "audio_window_comparisons": comparisons,
            "acceptance": {
                "human_visual_review": "not performed",
                "full_frame_visual_qc": "not performed; use the separate rootscan_visual_qc process",
                "continuous_listening": "not performed or claimed",
                "asr_or_cloud_transcription": "not used",
                "status": "measurements only; no acceptance decision",
            },
        }

        # Move only this run's compact JPEG assets into a fresh evidence folder.
        run_dir.mkdir(parents=True)
        for layout in layout_reports:
            os.replace(stage / layout, run_dir / layout)
        report_temp = stage / "final-media-evidence.json.tmp"
        report_temp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(report_temp, REPORT_PATH)
    return result


def main() -> int:
    parse_args()
    try:
        result = collect()
    except (CollectionError, OSError, wave.Error) as exc:
        print(f"[collect-qa] ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": result["status"], "report": relative_path(REPORT_PATH)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
