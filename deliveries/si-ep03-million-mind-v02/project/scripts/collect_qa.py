#!/usr/bin/env python3
"""Collect compact, encoded-media review evidence for the EP03 v02 exports.

This is an evidence collector, not an acceptance validator. It reads the final
MP4s named by delivery.json and the shared PCM master, then writes measurements
and media-derived contact sheets under the delivery's review/ directory.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DELIVERY_DIR = PROJECT_DIR.parent
MANIFEST_PATH = DELIVERY_DIR / "delivery.json"
REVIEW_DIR = DELIVERY_DIR / "review"
MASTER_RELATIVE = "project/public/audio/master.wav"
SAMPLE_FRAMES = (
    0, 360, 1020, 1040, 1500, 1920, 2190, 2990, 3030,
    3900, 4560, 4567, 4575, 5790, 6000, 6020, 6500, 7100, 7199,
)
NATIVE_KEY_FRAMES = (0, 1020, 2190, 4567, 4575, 6020, 7199)
MOTION_BOUNDARIES = (0, 1200, 1800, 2640, 3600, 4440, 5400, 6000, 6300, 6930, 7200)
MOTION_PAIR_GAP = 150  # 2.5 seconds at 60 fps
MOTION_STEP = 300  # Sample a pair about every 5 seconds.
AUDIO_SAMPLE_RATE = 48_000
AUDIO_WINDOW_SECONDS = 0.5
AUDIO_MAX_SHIFT_SECONDS = 0.05
AUDIO_SAMPLE_TIMES = (3.0, 50.0, 80.0, 101.0, 117.0)


class CollectorError(RuntimeError):
    """A required media input or measurement could not be collected."""


def log(message: str) -> None:
    print(f"[collect-qa] {message}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect encoded-frame, motion, loudness, and audio-match evidence."
    )
    parser.add_argument(
        "--layout", choices=("landscape", "portrait", "both"), default="both",
        help="Which final delivery output(s) to inspect (default: both).",
    )
    return parser.parse_args()


def require_executable(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise CollectorError(f"required executable is unavailable: {name}")
    return path


def run_capture(argv: list[str], *, phase: str) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(
            argv, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise CollectorError(f"{phase}: could not start {Path(argv[0]).name}: {exc}") from None
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        detail = detail[-1200:] if detail else "no diagnostic output"
        raise CollectorError(
            f"{phase}: {Path(argv[0]).name} exited {result.returncode}: {detail}"
        )
    return result


def safe_delivery_path(relative: Any, label: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise CollectorError(f"delivery.json {label} path is missing")
    candidate = (DELIVERY_DIR / relative).resolve(strict=False)
    try:
        candidate.relative_to(DELIVERY_DIR.resolve())
    except ValueError:
        raise CollectorError(f"delivery.json {label} path escapes the delivery folder") from None
    return candidate


def load_inputs(layouts: list[str]) -> tuple[dict[str, dict[str, Any]], Path, dict[str, Any]]:
    if not MANIFEST_PATH.is_file():
        raise CollectorError(f"delivery manifest is missing: {MANIFEST_PATH}")
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CollectorError(f"cannot read delivery.json: {exc}") from None

    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        raise CollectorError("delivery.json outputs must be an object")
    layout_config: dict[str, dict[str, Any]] = {}
    output_keys = {"landscape": "bilibili", "portrait": "xiaohongshu"}
    for layout in layouts:
        key = output_keys[layout]
        output = outputs.get(key)
        if not isinstance(output, dict):
            raise CollectorError(f"delivery.json outputs.{key} is missing")
        media = safe_delivery_path(output.get("path"), f"outputs.{key}")
        if not media.is_file():
            raise CollectorError(f"final {layout} MP4 is missing: {media}")
        width, height = output.get("width"), output.get("height")
        if type(width) is not int or type(height) is not int:
            raise CollectorError(f"delivery.json outputs.{key} needs integer width and height")
        layout_config[layout] = {
            "manifest_key": key,
            "media": media,
            "width": width,
            "height": height,
        }

    audio = manifest.get("audio")
    if not isinstance(audio, dict):
        raise CollectorError("delivery.json audio must be an object")
    master = safe_delivery_path(audio.get("master"), "audio.master")
    if not master.is_file():
        raise CollectorError(f"shared PCM master is missing: {master}")

    fps = manifest.get("fps")
    duration = manifest.get("duration_seconds")
    total_frames = manifest.get("total_frames")
    if type(fps) is not int or type(duration) not in (int, float) or type(total_frames) is not int:
        raise CollectorError("delivery.json needs numeric fps/duration and integer total_frames")
    if not math.isfinite(float(duration)) or fps <= 0 or duration <= 0 or total_frames != duration * fps:
        raise CollectorError("delivery.json timing fields are inconsistent")
    if fps != 60:
        raise CollectorError(f"this collector's approved frame samples expect 60 fps, got {fps}")
    for frame in (*SAMPLE_FRAMES, *NATIVE_KEY_FRAMES):
        if frame >= total_frames:
            raise CollectorError(f"configured sample frame {frame} is outside total_frames={total_frames}")
    return layout_config, master, manifest


def ffprobe_media(ffprobe: str, media: Path) -> dict[str, Any]:
    log(f"ffprobe format and stream metadata: {media.name}")
    result = run_capture(
        [ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(media)],
        phase=f"ffprobe {media.name}",
    )
    try:
        data = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise CollectorError(f"ffprobe returned invalid JSON for {media.name}") from None
    if not isinstance(data, dict) or not isinstance(data.get("streams"), list):
        raise CollectorError(f"ffprobe returned incomplete metadata for {media.name}")
    if not any(stream.get("codec_type") == "video" for stream in data["streams"]):
        raise CollectorError(f"no video stream found in {media.name}")
    if not any(stream.get("codec_type") == "audio" for stream in data["streams"]):
        raise CollectorError(f"no audio stream found in {media.name}")
    return data


def extract_frames(ffmpeg: str, media: Path, indexes: tuple[int, ...], temp_dir: Path) -> dict[int, Path]:
    sorted_indexes = tuple(sorted(set(indexes)))
    expression = "select=" + "+".join(f"eq(n\\,{frame})" for frame in sorted_indexes)
    pattern = temp_dir / "frame-%03d.jpg"
    log(f"extract {len(sorted_indexes)} exact decoded frame indexes: {media.name}")
    run_capture(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-xerror", "-y",
            "-i", str(media), "-map", "0:v:0", "-an", "-vf", expression,
            "-fps_mode", "passthrough", "-q:v", "3", "-start_number", "0", str(pattern),
        ],
        phase=f"frame extraction {media.name}",
    )
    paths = sorted(temp_dir.glob("frame-*.jpg"))
    if len(paths) != len(sorted_indexes):
        raise CollectorError(
            f"frame extraction returned {len(paths)} images; expected {len(sorted_indexes)}"
        )
    return dict(zip(sorted_indexes, paths, strict=True))


def read_image(path: Path, image_module: Any) -> Any:
    try:
        with image_module.open(path) as image:
            return image.convert("RGB")
    except OSError as exc:
        raise CollectorError(f"cannot read extracted frame {path.name}: {exc}") from None


def draw_label(image: Any, text: str, image_draw: Any, image_font: Any) -> Any:
    draw = image_draw.Draw(image)
    band_height = 26
    y = image.height - band_height
    draw.rectangle((0, y, image.width, image.height), fill=(0, 0, 0))
    draw.text((6, y + 5), text, fill=(255, 255, 255), font=image_font.load_default())
    return image


def make_frame_contact_sheet(
    frame_paths: dict[int, Path], *, width: int, columns: int,
    target: Path, image_module: Any, image_draw: Any, image_font: Any,
    fps: int,
) -> None:
    first = read_image(frame_paths[min(frame_paths)], image_module)
    thumb_height = round(first.height * width / first.width)
    card_height = thumb_height + 26
    rows = math.ceil(len(frame_paths) / columns)
    sheet = image_module.new("RGB", (columns * width, rows * card_height), (15, 18, 27))
    for position, (frame, path) in enumerate(sorted(frame_paths.items())):
        image = read_image(path, image_module)
        thumb = image.resize((width, thumb_height), image_module.Resampling.LANCZOS)
        card = image_module.new("RGB", (width, card_height), (15, 18, 27))
        card.paste(thumb, (0, 0))
        draw_label(card, f"frame {frame}  |  {frame / fps:.2f}s", image_draw, image_font)
        x = (position % columns) * width
        y = (position // columns) * card_height
        sheet.paste(card, (x, y))
    sheet.save(target, format="JPEG", quality=88, optimize=False)


def make_pair_contact_sheet(
    pairs: list[dict[str, Any]], frame_paths: dict[int, Path], *,
    frame_width: int, columns: int, target: Path,
    image_module: Any, image_draw: Any, image_font: Any, fps: int,
) -> None:
    first = read_image(frame_paths[pairs[0]["start_frame"]], image_module)
    thumb_height = round(first.height * frame_width / first.width)
    card_width = frame_width * 2
    card_height = thumb_height + 27
    rows = math.ceil(len(pairs) / columns)
    sheet = image_module.new("RGB", (columns * card_width, rows * card_height), (15, 18, 27))
    for position, pair in enumerate(pairs):
        start = read_image(frame_paths[pair["start_frame"]], image_module)
        end = read_image(frame_paths[pair["end_frame"]], image_module)
        start = start.resize((frame_width, thumb_height), image_module.Resampling.LANCZOS)
        end = end.resize((frame_width, thumb_height), image_module.Resampling.LANCZOS)
        card = image_module.new("RGB", (card_width, card_height), (15, 18, 27))
        card.paste(start, (0, 0))
        card.paste(end, (frame_width, 0))
        delta = pair["edge_difference_mean"]
        label = (
            f"pair {position + 1:02d}  {pair['start_frame'] / fps:.1f}s"
            f" -> {pair['end_frame'] / fps:.1f}s  edge_d={delta:.2f}"
        )
        draw_label(card, label, image_draw, image_font)
        x = (position % columns) * card_width
        y = (position // columns) * card_height
        sheet.paste(card, (x, y))
    sheet.save(target, format="JPEG", quality=86, optimize=False)


def edge_difference(
    first_path: Path, second_path: Path, *, roi: tuple[float, float, float, float],
    image_module: Any, numpy: Any,
) -> float:
    def edge_field(path: Path) -> Any:
        image = read_image(path, image_module)
        left, top, right, bottom = roi
        box = (
            round(image.width * left), round(image.height * top),
            round(image.width * right), round(image.height * bottom),
        )
        gray = numpy.asarray(image.crop(box).convert("L"), dtype=numpy.float32)
        gx = numpy.zeros_like(gray)
        gy = numpy.zeros_like(gray)
        gx[:, :-1] = gray[:, 1:] - gray[:, :-1]
        gy[:-1, :] = gray[1:, :] - gray[:-1, :]
        return numpy.sqrt(gx * gx + gy * gy)

    before = edge_field(first_path)
    after = edge_field(second_path)
    return float(numpy.mean(numpy.abs(after - before), dtype=numpy.float64))


def motion_pairs(
    frame_paths: dict[int, Path], *, layout: str, fps: int,
    image_module: Any, numpy: Any,
) -> list[dict[str, Any]]:
    roi = (0.10, 0.30, 0.90, 0.72) if layout == "landscape" else (0.08, 0.24, 0.82, 0.65)
    pairs: list[dict[str, Any]] = []
    for segment_index, (start, end) in enumerate(zip(MOTION_BOUNDARIES, MOTION_BOUNDARIES[1:]), start=1):
        for frame in range(start, end - MOTION_PAIR_GAP + 1, MOTION_STEP):
            later = frame + MOTION_PAIR_GAP
            if frame not in frame_paths or later not in frame_paths:
                raise CollectorError(f"motion sample frames {frame}/{later} were not extracted")
            pairs.append({
                "segment_interval": segment_index,
                "start_frame": frame,
                "end_frame": later,
                "start_seconds": frame / fps,
                "end_seconds": later / fps,
                "edge_difference_mean": edge_difference(
                    frame_paths[frame], frame_paths[later], roi=roi,
                    image_module=image_module, numpy=numpy,
                ),
            })
    return pairs


def decode_stereo_48k(ffmpeg: str, path: Path, *, phase: str, numpy: Any) -> Any:
    log(phase)
    result = run_capture(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-xerror", "-i", str(path),
            "-map", "0:a:0", "-vn", "-ac", "2", "-ar", str(AUDIO_SAMPLE_RATE),
            "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1",
        ],
        phase=phase,
    )
    if len(result.stdout) == 0 or len(result.stdout) % 4 != 0:
        raise CollectorError(f"{phase}: decoded PCM has an empty or unaligned payload")
    return numpy.frombuffer(result.stdout, dtype="<i2").reshape((-1, 2)).astype(numpy.float64)


def validate_master(master_path: Path, *, manifest: dict[str, Any], wave_module: Any) -> dict[str, Any]:
    try:
        with wave_module.open(str(master_path), "rb") as wav:
            actual = {
                "sample_rate": wav.getframerate(),
                "channels": wav.getnchannels(),
                "sample_width_bytes": wav.getsampwidth(),
                "frames": wav.getnframes(),
            }
    except (OSError, wave_module.Error) as exc:
        raise CollectorError(f"cannot read shared WAV master: {exc}") from None
    expected_frames = int(manifest["duration_seconds"] * AUDIO_SAMPLE_RATE)
    if (actual["sample_rate"], actual["channels"], actual["frames"]) != (
        AUDIO_SAMPLE_RATE, 2, expected_frames
    ):
        raise CollectorError(
            f"shared master must be 48kHz stereo and exactly {expected_frames} frames; got {actual}"
        )
    return actual


def normalized_window_correlation(
    reference: Any, actual: Any, *, center_seconds: float, numpy: Any,
) -> dict[str, Any]:
    window_frames = round(AUDIO_WINDOW_SECONDS * AUDIO_SAMPLE_RATE)
    max_lag = round(AUDIO_MAX_SHIFT_SECONDS * AUDIO_SAMPLE_RATE)
    center = round(center_seconds * AUDIO_SAMPLE_RATE)
    start = center - window_frames // 2
    if start < 0 or start + window_frames > len(reference):
        raise CollectorError(f"audio comparison window around {center_seconds}s exceeds the master")
    if start - max_lag < 0 or start + window_frames + max_lag > len(actual):
        raise CollectorError(f"audio comparison window around {center_seconds}s exceeds encoded audio")

    ref = reference[start:start + window_frames, :]
    ref_centered = ref - numpy.mean(ref, axis=0, keepdims=True)
    ref_channel_energy = numpy.sum(ref_centered * ref_centered, axis=0)
    ref_energy = float(numpy.sum(ref_channel_energy))
    if ref_energy <= 0:
        return {
            "center_seconds": center_seconds,
            "window_seconds": AUDIO_WINDOW_SECONDS,
            "correlation": None,
            "best_lag_ms": None,
            "master_window_silent": True,
        }

    candidate = actual[start - max_lag:start + window_frames + max_lag, :]
    convolution_length = len(candidate) + window_frames - 1
    fft_length = 1 << (convolution_length - 1).bit_length()
    channel_dots = []
    for channel in range(2):
        conv = numpy.fft.irfft(
            numpy.fft.rfft(candidate[:, channel], fft_length)
            * numpy.fft.rfft(ref_centered[::-1, channel], fft_length),
            fft_length,
        )[:convolution_length]
        channel_dots.append(conv)
    positions = numpy.arange(2 * max_lag + 1, dtype=numpy.int64)
    channel_dots_at_lags = numpy.stack(
        [dots[positions + window_frames - 1] for dots in channel_dots], axis=1,
    )
    dots = numpy.sum(channel_dots_at_lags, axis=1)
    cumulative = numpy.vstack((numpy.zeros((1, 2)), numpy.cumsum(candidate, axis=0, dtype=numpy.float64)))
    cumulative_sq = numpy.vstack((numpy.zeros((1, 2)), numpy.cumsum(candidate * candidate, axis=0, dtype=numpy.float64)))
    sums = cumulative[positions + window_frames] - cumulative[positions]
    sums_sq = cumulative_sq[positions + window_frames] - cumulative_sq[positions]
    candidate_channel_energy = numpy.maximum(0.0, sums_sq - (sums * sums / window_frames))
    candidate_energy = numpy.sum(candidate_channel_energy, axis=1)
    denominator = numpy.sqrt(ref_energy * candidate_energy)
    correlations = numpy.divide(
        dots, denominator, out=numpy.full_like(dots, -1.0), where=denominator > 0,
    )
    best = int(numpy.argmax(correlations))
    channel_correlation = {}
    for channel, name in enumerate(("left", "right")):
        channel_denominator = math.sqrt(float(ref_channel_energy[channel] * candidate_channel_energy[best, channel]))
        value = (
            float(channel_dots_at_lags[best, channel] / channel_denominator)
            if channel_denominator > 0 else None
        )
        channel_correlation[name] = (
            float(numpy.clip(value, -1.0, 1.0)) if value is not None else None
        )
    return {
        "center_seconds": center_seconds,
        "window_seconds": AUDIO_WINDOW_SECONDS,
        "correlation": float(numpy.clip(correlations[best], -1.0, 1.0)),
        "channel_correlation_at_best_lag": channel_correlation,
        "best_lag_ms": round((best - max_lag) * 1000.0 / AUDIO_SAMPLE_RATE, 3),
        "max_alignment_search_ms": AUDIO_MAX_SHIFT_SECONDS * 1000,
        "master_window_rms_s16": round(math.sqrt(ref_energy / (window_frames * 2)), 3),
        "encoded_window_rms_s16": round(math.sqrt(float(candidate_energy[best]) / (window_frames * 2)), 3),
    }


def measure_loudness(ffmpeg: str, media: Path) -> dict[str, Any]:
    log(f"EBU R128 loudness and true peak: {media.name}")
    result = run_capture(
        [
            ffmpeg, "-hide_banner", "-nostats", "-i", str(media),
            "-map", "0:a:0", "-af", "ebur128=peak=true", "-f", "null", "-",
        ],
        phase=f"ebur128 {media.name}",
    )
    output = result.stderr.decode("utf-8", errors="replace")
    integrated = re.search(r"(?m)^\s*I:\s*(-?\d+(?:\.\d+)?)\s+LUFS\s*$", output)
    true_peak = re.search(r"(?m)^\s*True peak:\s*(-?\d+(?:\.\d+)?)\s+dBTP\s*$", output)
    if true_peak is None:
        true_peak = re.search(r"True peak:\s*\n\s*Peak:\s*(-?\d+(?:\.\d+)?)\s+dBFS", output)
    sample_peak = re.search(r"(?m)^\s*Sample peak:\s*(-?\d+(?:\.\d+)?)\s+dBFS\s*$", output)
    if integrated is None or true_peak is None:
        raise CollectorError(f"ebur128 did not report integrated loudness and true peak for {media.name}")
    return {
        "measurement": "FFmpeg ebur128=peak=true on the encoded MP4 audio stream",
        "integrated_lufs": float(integrated.group(1)),
        "true_peak_dbTP": float(true_peak.group(1)),
        "sample_peak_dbFS": float(sample_peak.group(1)) if sample_peak else None,
    }


def encoded_audio_stream_hash(ffmpeg: str, media: Path) -> dict[str, Any]:
    log(f"encoded audio packet stream hash: {media.name}")
    try:
        result = run_capture(
            [
                ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(media),
                "-map", "0:a:0", "-c", "copy", "-f", "streamhash", "-hash", "sha256", "-",
            ],
            phase=f"audio streamhash {media.name}",
        )
    except CollectorError as exc:
        return {"available": False, "reason": str(exc)}
    text = (result.stdout + result.stderr).decode("ascii", errors="replace")
    match = re.search(r"SHA256=([0-9a-fA-F]{64})", text)
    if match is None:
        return {"available": False, "reason": "FFmpeg streamhash returned no SHA-256 digest"}
    return {"available": True, "sha256": match.group(1).lower()}


def check_dimensions(frame_paths: dict[int, Path], *, expected: tuple[int, int], image_module: Any) -> None:
    for frame, path in frame_paths.items():
        with image_module.open(path) as image:
            if image.size != expected:
                raise CollectorError(
                    f"encoded frame {frame} is {image.width}x{image.height}; expected {expected[0]}x{expected[1]}"
                )


def layout_output_name(layout: str) -> str:
    return f"encoded-qa-{layout}.json"


def collect_layout(
    *, layout: str, config: dict[str, Any], manifest: dict[str, Any], master_path: Path,
    master_pcm: Any, ffmpeg: str, ffprobe: str, stage: Path,
    image_module: Any, image_draw: Any, image_font: Any, numpy: Any,
) -> dict[str, Any]:
    media: Path = config["media"]
    fps = manifest["fps"]
    total_frames = manifest["total_frames"]
    with tempfile.TemporaryDirectory(prefix=f"ep3-qa-{layout}-") as temp_name:
        temp_dir = Path(temp_name)
        requested_indexes = tuple(sorted(set(
            (*SAMPLE_FRAMES,
             *(frame for start, end in zip(MOTION_BOUNDARIES, MOTION_BOUNDARIES[1:])
               for frame in range(start, end - MOTION_PAIR_GAP + 1, MOTION_STEP)),
             *(frame + MOTION_PAIR_GAP
               for start, end in zip(MOTION_BOUNDARIES, MOTION_BOUNDARIES[1:])
               for frame in range(start, end - MOTION_PAIR_GAP + 1, MOTION_STEP)))
        )))
        if requested_indexes[-1] >= total_frames:
            raise CollectorError("configured encoded frame sample exceeds delivery total_frames")
        frame_paths = extract_frames(ffmpeg, media, requested_indexes, temp_dir)
        check_dimensions(
            frame_paths, expected=(config["width"], config["height"]), image_module=image_module,
        )
        pairs = motion_pairs(
            frame_paths, layout=layout, fps=fps, image_module=image_module, numpy=numpy,
        )

        width = 480 if layout == "landscape" else 360
        columns = 4 if layout == "landscape" else 3
        contact_name = f"encoded-{layout}-contact-sheet.jpg"
        pair_contact_name = f"encoded-{layout}-pair-contact-sheet.jpg"
        make_frame_contact_sheet(
            {frame: frame_paths[frame] for frame in SAMPLE_FRAMES},
            width=width, columns=columns, target=stage / contact_name,
            image_module=image_module, image_draw=image_draw, image_font=image_font, fps=fps,
        )
        make_pair_contact_sheet(
            pairs, frame_paths, frame_width=width // 2, columns=3,
            target=stage / pair_contact_name,
            image_module=image_module, image_draw=image_draw, image_font=image_font, fps=fps,
        )
        native_files: list[str] = []
        for frame in NATIVE_KEY_FRAMES:
            native_name = f"encoded-{layout}-native-frame-{frame:04d}.jpg"
            image = read_image(frame_paths[frame], image_module)
            image.save(stage / native_name, format="JPEG", quality=94, subsampling=0, optimize=False)
            native_files.append(native_name)

    probe = ffprobe_media(ffprobe, media)
    loudness = measure_loudness(ffmpeg, media)
    encoded_pcm = decode_stereo_48k(
        ffmpeg, media, phase=f"decode {layout} AAC as presented at 48kHz stereo", numpy=numpy,
    )
    audio_windows = [
        normalized_window_correlation(
            master_pcm, encoded_pcm, center_seconds=sample_time, numpy=numpy,
        )
        for sample_time in AUDIO_SAMPLE_TIMES
    ]
    packet_hash = encoded_audio_stream_hash(ffmpeg, media)
    expected_audio_frames = int(manifest["duration_seconds"] * AUDIO_SAMPLE_RATE)
    return {
        "schema_version": 1,
        "status": "evidence_collected",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "layout": layout,
        "media_path": media.relative_to(DELIVERY_DIR).as_posix(),
        "expected": {
            "width": config["width"],
            "height": config["height"],
            "fps": fps,
            "duration_seconds": manifest["duration_seconds"],
            "total_frames": total_frames,
        },
        "ffprobe": probe,
        "loudness": loudness,
        "representative_frames": {
            "method": "FFmpeg select=eq(n,index) over decoded final MP4 frames",
            "frame_indexes": list(SAMPLE_FRAMES),
            "contact_sheet_path": f"review/{contact_name}",
            "contact_tile_width_px": width,
            "native_keyframe_paths": [f"review/{name}" for name in native_files],
            "native_keyframe_indexes": list(NATIVE_KEY_FRAMES),
        },
        "motion_heuristic": {
            "method": "mean absolute difference between grayscale finite-difference edge-magnitude fields",
            "frame_source": "decoded final MP4 frames only",
            "roi_fraction_xyxy": [0.10, 0.30, 0.90, 0.72] if layout == "landscape" else [0.08, 0.24, 0.82, 0.65],
            "pair_gap_frames": MOTION_PAIR_GAP,
            "pair_gap_seconds": MOTION_PAIR_GAP / fps,
            "sample_step_frames": MOTION_STEP,
            "pair_contact_sheet_path": f"review/{pair_contact_name}",
            "samples": pairs,
            "limitation": (
                "Heuristic only, not proof of meaningful motion. The ROI avoids most HUD and subtitles, "
                "but overlays or scene cuts may still affect edge differences. Human review is separate."
            ),
        },
        "audio_comparison": {
            "master_path": master_path.relative_to(DELIVERY_DIR).as_posix(),
            "master_format": "48kHz stereo PCM WAV, decoded to s16le for comparison",
            "encoded_format": "FFmpeg-decoded MP4 audio, resampled to 48kHz stereo s16le",
            "master_decoded_frames": int(len(master_pcm)),
            "encoded_decoded_frames": int(len(encoded_pcm)),
            "encoded_minus_master_frames": int(len(encoded_pcm) - len(master_pcm)),
            "expected_frames_at_delivery_duration": expected_audio_frames,
            "windows": audio_windows,
            "encoded_audio_packet_sha256": packet_hash,
            "aac_note": (
                "AAC priming and tail padding can change container-presented duration and decoded sample count. "
                "Correlation allows a bounded +/-50ms alignment search; it is not a listening judgment."
            ),
        },
        "acceptance_limit": "Measurements and images are evidence only; this file makes no pass, listening, or human-acceptance claim.",
    }


def main() -> int:
    args = parse_args()
    layouts = ["landscape", "portrait"] if args.layout == "both" else [args.layout]
    try:
        ffmpeg = require_executable("ffmpeg")
        ffprobe = require_executable("ffprobe")
        configs, master_path, manifest = load_inputs(layouts)
        import numpy
        from PIL import Image, ImageDraw, ImageFont
        import wave

        master_info = validate_master(master_path, manifest=manifest, wave_module=wave)
        log(
            f"shared master {master_info['frames']} frames, {master_info['sample_rate']}Hz, "
            f"{master_info['channels']} channels"
        )
        master_pcm = decode_stereo_48k(
            ffmpeg, master_path, phase="decode shared PCM master at 48kHz stereo", numpy=numpy,
        )
        expected_master_frames = int(manifest["duration_seconds"] * AUDIO_SAMPLE_RATE)
        if len(master_pcm) != expected_master_frames:
            raise CollectorError(
                f"FFmpeg decoded {len(master_pcm)} master frames; expected {expected_master_frames}"
            )
        REVIEW_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".ep3-qa-stage-", dir=REVIEW_DIR) as stage_name:
            stage = Path(stage_name)
            results: dict[str, dict[str, Any]] = {}
            for layout in layouts:
                log(f"collecting {layout} evidence")
                results[layout] = collect_layout(
                    layout=layout, config=configs[layout], manifest=manifest,
                    master_path=master_path, master_pcm=master_pcm,
                    ffmpeg=ffmpeg, ffprobe=ffprobe, stage=stage,
                    image_module=Image, image_draw=ImageDraw, image_font=ImageFont, numpy=numpy,
                )
            if "landscape" in results and "portrait" in results:
                landscape_hash = results["landscape"]["audio_comparison"]["encoded_audio_packet_sha256"]
                portrait_hash = results["portrait"]["audio_comparison"]["encoded_audio_packet_sha256"]
                comparison = {
                    "same_encoded_audio_packets": (
                        landscape_hash.get("available") is True
                        and portrait_hash.get("available") is True
                        and landscape_hash.get("sha256") == portrait_hash.get("sha256")
                    ),
                    "landscape_sha256": landscape_hash.get("sha256"),
                    "portrait_sha256": portrait_hash.get("sha256"),
                }
                for result in results.values():
                    result["audio_comparison"]["cross_layout_packet_hash_comparison"] = comparison

            for layout, result in results.items():
                staged_json = stage / layout_output_name(layout)
                staged_json.write_text(
                    json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
                )
            publish_files = sorted(path for path in stage.iterdir() if path.is_file())
            for staged_file in publish_files:
                destination = REVIEW_DIR / staged_file.name
                os.replace(staged_file, destination)
                log(f"wrote {destination.relative_to(DELIVERY_DIR).as_posix()}")

        for layout in layouts:
            log(f"evidence collected for {layout}; review measurements without treating them as acceptance")
        return 0
    except (CollectorError, OSError, ValueError, ImportError) as exc:
        print(f"collect_qa.py: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
