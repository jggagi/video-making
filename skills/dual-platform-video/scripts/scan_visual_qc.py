#!/usr/bin/env python3
"""Screen every decoded frame for isolated flashes and optional ROI changes.

This is a scaled, conservative heuristic screen. It does not establish visual,
perceptual, listening, or device acceptance. Source cuts are preserved as
content and are not flagged by the isolated-frame heuristic.
"""

from __future__ import annotations

import argparse
import array
import csv
from datetime import datetime, timezone
import hashlib
import heapq
import io
import json
import math
import os
from pathlib import Path
import selectors
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterator

try:
    import numpy as np
except ImportError as exc:  # Keep --help and argument validation usable.
    np = None  # type: ignore[assignment]
    _NUMPY_IMPORT_ERROR = str(exc)
else:
    _NUMPY_IMPORT_ERROR = ""

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:  # Keep --help and argument validation usable.
    Image = ImageDraw = ImageFont = None  # type: ignore[assignment]
    _PIL_IMPORT_ERROR = str(exc)
else:
    _PIL_IMPORT_ERROR = ""


DEFAULT_WIDTH = 360
MIN_WIDTH = 90
MAX_WIDTH = 960
RGB_JUMP_FLOOR = 12.0
RGB_NEIGHBOR_LIMIT = 3.0
ROI_MAE_FLOOR = 8.0
DARK_BRIGHT_COUNT_FLOOR = 50.0
BRIGHT_LUMA_THRESHOLD = 100.0
RAW_READ_TIMEOUT_SECONDS = 60.0
FFPROBE_TIMEOUT_SECONDS = 30.0
FRAME_BYTES_PER_INDEX = 16

LIMITATIONS = [
    "Screening uses scaled RGB heuristics and does not replace full-resolution perceptual review.",
    "The scan does not establish human review, listening, or device playback acceptance.",
    "A frame with no heuristic flags may still contain visual defects outside these checks.",
]


def require_dependencies() -> None:
    missing: list[str] = []
    if np is None:
        missing.append(f"NumPy ({_NUMPY_IMPORT_ERROR})")
    if Image is None or ImageDraw is None or ImageFont is None:
        missing.append(f"Pillow ({_PIL_IMPORT_ERROR})")
    if missing:
        raise RuntimeError(
            "missing required bundled Python dependency: " + "; ".join(missing)
        )


def parse_roi(value: str) -> tuple[float, float, float, float]:
    """Parse normalized x,y,width,height coordinates contained in [0, 1]."""
    try:
        parts = tuple(float(part.strip()) for part in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("ROI must be four comma-separated numbers") from exc
    if len(parts) != 4 or not all(math.isfinite(part) for part in parts):
        raise argparse.ArgumentTypeError("ROI must be four finite comma-separated numbers")
    x, y, width, height = parts
    if width <= 0 or height <= 0 or x < 0 or y < 0 or x + width > 1 or y + height > 1:
        raise argparse.ArgumentTypeError("ROI must have positive size and fit within normalized 0..1 bounds")
    return x, y, width, height


def parse_width(value: str) -> int:
    try:
        width = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("width must be an integer") from exc
    if not MIN_WIDTH <= width <= MAX_WIDTH:
        raise argparse.ArgumentTypeError(f"width must be between {MIN_WIDTH} and {MAX_WIDTH}")
    return width


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--media", required=True, type=Path)
    parser.add_argument("--expected-frames", required=True, type=int)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--stable-roi", type=parse_roi, metavar="X,Y,W,H")
    parser.add_argument("--dark-roi", type=parse_roi, metavar="X,Y,W,H")
    parser.add_argument("--width", type=parse_width, default=DEFAULT_WIDTH)
    return parser.parse_args(argv)


def rgb_mae(left: Any, right: Any) -> float:
    """Mean absolute per-channel RGB difference for same-sized arrays."""
    assert np is not None
    delta = np.subtract(left, right, dtype=np.int16)
    return float(np.abs(delta).mean())


def isolated_full_frame_jump(
    previous_middle_mae: float,
    middle_next_mae: float,
    previous_next_mae: float,
) -> bool:
    """Return whether the center of a three-frame window is an isolated jump."""
    neighbor_limit = max(
        RGB_NEIGHBOR_LIMIT,
        0.35 * min(previous_middle_mae, middle_next_mae),
    )
    return (
        previous_middle_mae >= RGB_JUMP_FLOOR
        and middle_next_mae >= RGB_JUMP_FLOOR
        and previous_next_mae <= neighbor_limit
    )


def even_scaled_height(source_width: int, source_height: int, scaled_width: int) -> int:
    if source_width <= 0 or source_height <= 0:
        raise ValueError("FFprobe returned invalid video dimensions")
    height = max(2, int(round(scaled_width * source_height / source_width)))
    if height % 2:
        lower = max(2, height - 1)
        upper = height + 1
        height = lower if abs(lower - scaled_width * source_height / source_width) <= abs(
            upper - scaled_width * source_height / source_width
        ) else upper
    return height


def roi_pixels(frame: Any, roi: tuple[float, float, float, float]) -> Any:
    x, y, width, height = roi
    frame_height, frame_width = frame.shape[:2]
    x0 = min(frame_width - 1, max(0, math.floor(x * frame_width)))
    y0 = min(frame_height - 1, max(0, math.floor(y * frame_height)))
    x1 = min(frame_width, max(x0 + 1, math.ceil((x + width) * frame_width)))
    y1 = min(frame_height, max(y0 + 1, math.ceil((y + height) * frame_height)))
    return frame[y0:y1, x0:x1, :]


def luma(rgb: Any) -> Any:
    assert np is not None
    values = rgb.astype(np.float32, copy=False)
    return values[..., 0] * 0.2126 + values[..., 1] * 0.7152 + values[..., 2] * 0.0722


def robust_upper_from_sorted_median(median: float, mad: float, floor: float) -> dict[str, float]:
    return {
        "median": median,
        "mad": mad,
        "threshold": max(floor, median + 8.0 * 1.4826 * mad),
        "floor": floor,
    }


def _float_chunks_from_csv(path: Path, field: str, chunk_size: int) -> Iterator[list[float]]:
    values: list[float] = []
    with path.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            raw = row.get(field, "")
            if raw == "":
                continue
            values.append(float(raw))
            if len(values) >= chunk_size:
                yield values
                values = []
    if values:
        yield values


def _write_sorted_run(path: Path, values: list[float]) -> None:
    values.sort()
    with path.open("wb") as handle:
        array.array("d", values).tofile(handle)


def _run_values(path: Path, block_values: int = 4096) -> Iterator[float]:
    with path.open("rb") as handle:
        while True:
            block = array.array("d")
            try:
                block.fromfile(handle, block_values)
            except EOFError:
                pass
            if not block:
                break
            yield from block


def _merge_run_group(paths: list[Path], output: Path) -> None:
    with output.open("wb") as handle:
        merged = heapq.merge(*(_run_values(path) for path in paths))
        block = array.array("d")
        for value in merged:
            block.append(value)
            if len(block) == 8192:
                block.tofile(handle)
                block = array.array("d")
        if block:
            block.tofile(handle)


def _external_sorted_values(
    csv_path: Path,
    field: str,
    scratch: Path,
    *,
    offset: float | None = None,
    absolute: bool = False,
    chunk_size: int = 32768,
    merge_fan_in: int = 64,
) -> tuple[Path | None, int]:
    """External sort a CSV numeric column using bounded-size in-memory runs."""
    runs: list[Path] = []
    count = 0
    for values in _float_chunks_from_csv(csv_path, field, chunk_size):
        if offset is not None:
            values = [abs(value - offset) if absolute else value - offset for value in values]
        count += len(values)
        path = scratch / f"{field}-run-{len(runs):06d}.bin"
        _write_sorted_run(path, values)
        runs.append(path)
    if not runs:
        return None, 0

    generation = 0
    while len(runs) > 1:
        next_runs: list[Path] = []
        for start in range(0, len(runs), merge_fan_in):
            group = runs[start : start + merge_fan_in]
            merged_path = scratch / f"{field}-merge-{generation:03d}-{len(next_runs):06d}.bin"
            _merge_run_group(group, merged_path)
            next_runs.append(merged_path)
            for old_path in group:
                old_path.unlink()
        runs = next_runs
        generation += 1
    return runs[0], count


def _sorted_value_at(path: Path, index: int) -> float:
    with path.open("rb") as handle:
        handle.seek(index * 8)
        value = array.array("d")
        value.fromfile(handle, 1)
        if not value:
            raise ValueError("external sort produced an incomplete median file")
        return float(value[0])


def _median_of_sorted(path: Path, count: int) -> float:
    middle = count // 2
    if count % 2:
        return _sorted_value_at(path, middle)
    return (_sorted_value_at(path, middle - 1) + _sorted_value_at(path, middle)) / 2.0


def robust_upper_from_csv(
    csv_path: Path,
    field: str,
    floor: float,
    scratch: Path,
) -> dict[str, float] | None:
    sorted_values, count = _external_sorted_values(csv_path, field, scratch)
    if sorted_values is None or count == 0:
        return None
    median = _median_of_sorted(sorted_values, count)
    sorted_values.unlink()
    sorted_deviations, deviation_count = _external_sorted_values(
        csv_path, field, scratch, offset=median, absolute=True
    )
    if sorted_deviations is None or deviation_count != count:
        raise ValueError(f"could not compute robust MAD for {field}")
    mad = _median_of_sorted(sorted_deviations, deviation_count)
    sorted_deviations.unlink()
    return robust_upper_from_sorted_median(median, mad, floor)


def probe_media(ffprobe: str, media: Path) -> tuple[dict[str, Any], list[str]]:
    command = [
        ffprobe,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,avg_frame_rate,r_frame_rate,duration,nb_frames",
        "-show_entries", "format=duration",
        "-of", "json",
        str(media),
    ]
    try:
        result = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=FFPROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"ffprobe timed out after {FFPROBE_TIMEOUT_SECONDS:g}s") from exc
    except OSError as exc:
        raise RuntimeError(f"could not start ffprobe: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or "").strip()[-1600:]
        raise RuntimeError(f"ffprobe exited {result.returncode}: {detail}")
    try:
        payload = json.loads(result.stdout)
        streams = payload.get("streams", [])
        stream = streams[0] if streams else None
        if not stream:
            raise ValueError("no video stream")
        width = int(stream["width"])
        height = int(stream["height"])
        fps_text = stream.get("avg_frame_rate") or "0/0"
        fps = _parse_positive_fraction(fps_text)
        fps_source = "avg_frame_rate"
        if fps is None:
            fps_text = stream.get("r_frame_rate") or "0/0"
            fps = _parse_positive_fraction(fps_text)
            fps_source = "r_frame_rate"
        if fps is None:
            raise ValueError("ffprobe did not return a positive avg_frame_rate or r_frame_rate")
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise RuntimeError(f"invalid ffprobe video metadata: {exc}") from exc
    duration = stream.get("duration") or payload.get("format", {}).get("duration")
    return (
        {
            "codec_name": stream.get("codec_name"),
            "width": width,
            "height": height,
            "fps": {"numerator": fps.numerator, "denominator": fps.denominator, "decimal": float(fps)},
            "fps_source": fps_source,
            "duration_seconds": float(duration) if duration not in (None, "N/A") else None,
            "nb_frames": stream.get("nb_frames"),
            "geometry_basis": "FFprobe coded video dimensions; FFmpeg autorotation is disabled",
        },
        command,
    )


def _parse_positive_fraction(value: str) -> Any | None:
    from fractions import Fraction

    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError):
        return None
    return result if result > 0 else None


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def make_ffmpeg_command(
    ffmpeg: str,
    media: Path,
    width: int,
    height: int,
) -> list[str]:
    return [
        ffmpeg,
        "-hide_banner", "-loglevel", "error", "-nostdin",
        "-threads", "2", "-filter_threads", "2", "-noautorotate",
        "-i", str(media),
        "-map", "0:v:0", "-an", "-sn", "-dn",
        "-vf", f"scale={width}:{height}:flags=bilinear",
        "-vsync", "0", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1",
    ]


class StreamReadTimeout(TimeoutError):
    def __init__(self, partial: bytes):
        super().__init__(f"no decoded frame data arrived for {RAW_READ_TIMEOUT_SECONDS:g}s")
        self.partial = partial


def read_raw_frame(
    fd: int,
    frame_bytes: int,
    selector: selectors.BaseSelector,
) -> tuple[bytes, bool]:
    data = bytearray()
    deadline = time.monotonic() + RAW_READ_TIMEOUT_SECONDS
    while len(data) < frame_bytes:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not selector.select(remaining):
            raise StreamReadTimeout(bytes(data))
        try:
            part = os.read(fd, min(1024 * 1024, frame_bytes - len(data)))
        except BlockingIOError:
            continue
        if not part:
            return bytes(data), True
        data.extend(part)
        deadline = time.monotonic() + RAW_READ_TIMEOUT_SECONDS
    return bytes(data), False


def _terminate(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def _thumbnail_jpeg(frame: Any) -> bytes:
    assert Image is not None
    height, width = frame.shape[:2]
    thumb_width = min(240, width)
    thumb_height = max(1, round(height * thumb_width / width))
    image = Image.fromarray(frame).resize(
        (thumb_width, thumb_height), Image.Resampling.BILINEAR
    )
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=78, optimize=True)
    return buffer.getvalue()


def _row_template() -> dict[str, Any]:
    return {
        "frame": 0,
        "time_seconds": 0.0,
        "status": "decoded",
        "partial_bytes": 0,
        "full_frame_mae_prev_rgb": None,
        "full_frame_mae_next_rgb": None,
        "full_frame_mae_neighbors_rgb": None,
        "isolated_full_frame_jump": False,
        "stable_roi_template_mae_rgb": None,
        "stable_roi_consecutive_mae_rgb": None,
        "dark_roi_bright_pixels_gt100": None,
    }


def _write_spool_row(writer: csv.DictWriter, row: dict[str, Any]) -> None:
    writer.writerow(row)


def _spawn_ffmpeg(command: list[str], stderr_file: Any) -> subprocess.Popen[bytes]:
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=stderr_file,
            bufsize=0,
        )
    except OSError as exc:
        raise RuntimeError(f"could not start ffmpeg: {exc}") from exc
    if process.stdout is None:
        _terminate(process)
        raise RuntimeError("ffmpeg stdout pipe is unavailable")
    os.set_blocking(process.stdout.fileno(), False)
    return process


def scan_frames(
    *,
    command: list[str],
    width: int,
    height: int,
    fps: float,
    stable_roi: tuple[float, float, float, float] | None,
    dark_roi: tuple[float, float, float, float] | None,
    raw_csv_path: Path,
    thumbnail_path: Path,
    thumbnail_index_path: Path,
) -> dict[str, Any]:
    assert np is not None
    raw_fields = list(_row_template())
    stderr_file = tempfile.TemporaryFile()
    try:
        process = _spawn_ffmpeg(command, stderr_file)
    except BaseException:
        stderr_file.close()
        raise
    frame_bytes = width * height * 3
    frame_count = 0
    partial_frame_bytes = 0
    stream_error: str | None = None
    process_returncode: int | None = None
    window: list[dict[str, Any]] = []
    written_through = -1
    stable_template = None

    try:
        with (
            raw_csv_path.open("w", newline="", encoding="utf-8") as raw_handle,
            thumbnail_path.open("wb") as thumbnail_handle,
            thumbnail_index_path.open("wb") as thumbnail_index_handle,
            selectors.DefaultSelector() as selector,
        ):
            writer = csv.DictWriter(raw_handle, fieldnames=raw_fields, lineterminator="\n")
            writer.writeheader()
            assert process.stdout is not None
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                try:
                    payload, eof = read_raw_frame(
                        process.stdout.fileno(), frame_bytes, selector
                    )
                except StreamReadTimeout as exc:
                    partial_frame_bytes = len(exc.partial)
                    stream_error = str(exc)
                    _terminate(process)
                    break
                if not payload and eof:
                    break
                if len(payload) != frame_bytes:
                    partial_frame_bytes = len(payload)
                    stream_error = (
                        f"truncated raw frame {frame_count}: {len(payload)} of {frame_bytes} bytes"
                    )
                    break

                frame = np.frombuffer(payload, dtype=np.uint8).reshape((height, width, 3))
                row = _row_template()
                row["frame"] = frame_count
                row["time_seconds"] = round(frame_count / fps, 6)

                if window:
                    previous = window[-1]
                    difference = rgb_mae(previous["pixels"], frame)
                    row["full_frame_mae_prev_rgb"] = round(difference, 6)
                    previous["row"]["full_frame_mae_next_rgb"] = round(difference, 6)

                if stable_roi is not None:
                    current_stable = roi_pixels(frame, stable_roi)
                    if stable_template is None:
                        stable_template = current_stable.copy()
                    row["stable_roi_template_mae_rgb"] = round(
                        rgb_mae(current_stable, stable_template), 6
                    )
                    if window:
                        previous_stable = roi_pixels(window[-1]["pixels"], stable_roi)
                        row["stable_roi_consecutive_mae_rgb"] = round(
                            rgb_mae(current_stable, previous_stable), 6
                        )

                if dark_roi is not None:
                    gray = luma(roi_pixels(frame, dark_roi))
                    row["dark_roi_bright_pixels_gt100"] = int(
                        np.count_nonzero(gray > BRIGHT_LUMA_THRESHOLD)
                    )

                thumbnail = _thumbnail_jpeg(frame)
                thumbnail_offset = thumbnail_handle.tell()
                thumbnail_handle.write(thumbnail)
                thumbnail_index_handle.write(
                    struct.pack("!QQ", thumbnail_offset, len(thumbnail))
                )
                window.append({"pixels": frame, "row": row})
                frame_count += 1

                if len(window) == 3:
                    previous, middle, following = window
                    d_prev_mid = float(middle["row"]["full_frame_mae_prev_rgb"])
                    d_mid_next = float(following["row"]["full_frame_mae_prev_rgb"])
                    d_prev_next = rgb_mae(previous["pixels"], following["pixels"])
                    middle["row"]["full_frame_mae_neighbors_rgb"] = round(d_prev_next, 6)
                    middle["row"]["isolated_full_frame_jump"] = isolated_full_frame_jump(
                        d_prev_mid, d_mid_next, d_prev_next
                    )
                    for item in window[:2]:
                        item_frame = int(item["row"]["frame"])
                        if item_frame > written_through:
                            _write_spool_row(writer, item["row"])
                            written_through = item_frame
                    window.pop(0)

            for item in window:
                item_frame = int(item["row"]["frame"])
                if item_frame > written_through:
                    _write_spool_row(writer, item["row"])
                    written_through = item_frame
            if process.poll() is None:
                try:
                    process_returncode = process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    stream_error = stream_error or "ffmpeg did not exit after its output stream closed"
                    _terminate(process)
                    process_returncode = process.returncode
            else:
                process_returncode = process.returncode
            stderr_file.flush()
            stderr_file.seek(0, os.SEEK_END)
            stderr_size = stderr_file.tell()
            stderr_file.seek(max(0, stderr_size - 1600))
            stderr_tail = stderr_file.read().decode("utf-8", errors="replace").strip()
            if process_returncode != 0:
                detail = f"ffmpeg exited {process_returncode}"
                if stderr_tail:
                    detail += f": {stderr_tail}"
                stream_error = stream_error or detail
            elif stream_error is None and frame_count == 0:
                stream_error = "ffmpeg produced no complete video frames"
            if partial_frame_bytes or stream_error:
                partial_row = _row_template()
                partial_row["frame"] = frame_count
                partial_row["time_seconds"] = round(frame_count / fps, 6)
                partial_row["status"] = "partial" if partial_frame_bytes else "decode_error"
                partial_row["partial_bytes"] = partial_frame_bytes
                _write_spool_row(writer, partial_row)
            raw_handle.flush()
            os.fsync(raw_handle.fileno())
            thumbnail_handle.flush()
            os.fsync(thumbnail_handle.fileno())
            thumbnail_index_handle.flush()
            os.fsync(thumbnail_index_handle.fileno())

    except BaseException:
        _terminate(process)
        raise
    finally:
        if process.stdout is not None:
            process.stdout.close()
        stderr_file.flush()
        stderr_file.seek(0, os.SEEK_END)
        stderr_size = stderr_file.tell()
        stderr_file.seek(max(0, stderr_size - 1600))
        ffmpeg_stderr = stderr_file.read().decode("utf-8", errors="replace").strip()
        stderr_file.close()

    if process_returncode is None:
        process_returncode = process.returncode
    if process_returncode != 0 and stream_error is None:
        detail = f"ffmpeg exited {process_returncode}"
        if ffmpeg_stderr:
            detail += f": {ffmpeg_stderr}"
        stream_error = detail
    elif stream_error is None and frame_count == 0:
        stream_error = "ffmpeg produced no complete video frames"

    return {
        "decoded_frames": frame_count,
        "partial_frame_bytes": partial_frame_bytes,
        "return_code": process_returncode,
        "decode_error": stream_error,
        "stderr_tail": ffmpeg_stderr,
    }


def _metric_thresholds(
    raw_csv: Path,
    stable_roi: tuple[float, float, float, float] | None,
    dark_roi: tuple[float, float, float, float] | None,
    scratch: Path,
) -> dict[str, dict[str, float] | None]:
    return {
        "stable_roi_template_mae_rgb": (
            robust_upper_from_csv(raw_csv, "stable_roi_template_mae_rgb", ROI_MAE_FLOOR, scratch)
            if stable_roi is not None
            else None
        ),
        "stable_roi_consecutive_mae_rgb": (
            robust_upper_from_csv(raw_csv, "stable_roi_consecutive_mae_rgb", ROI_MAE_FLOOR, scratch)
            if stable_roi is not None
            else None
        ),
        "dark_roi_bright_pixels_gt100": (
            robust_upper_from_csv(
                raw_csv, "dark_roi_bright_pixels_gt100", DARK_BRIGHT_COUNT_FLOOR, scratch
            )
            if dark_roi is not None
            else None
        ),
    }


def _row_reasons(
    row: dict[str, str],
    thresholds: dict[str, dict[str, float] | None],
) -> list[str]:
    reasons: list[str] = []
    if row["status"] != "decoded":
        return reasons
    if row["isolated_full_frame_jump"] == "True":
        reasons.append("isolated_full_frame_jump")
    threshold = thresholds["stable_roi_template_mae_rgb"]
    value = row["stable_roi_template_mae_rgb"]
    if threshold is not None and value and float(value) > threshold["threshold"]:
        reasons.append("stable_roi_template_outlier")
    threshold = thresholds["stable_roi_consecutive_mae_rgb"]
    value = row["stable_roi_consecutive_mae_rgb"]
    if threshold is not None and value and float(value) > threshold["threshold"]:
        reasons.append("stable_roi_consecutive_outlier")
    threshold = thresholds["dark_roi_bright_pixels_gt100"]
    value = row["dark_roi_bright_pixels_gt100"]
    if threshold is not None and value and float(value) > threshold["threshold"]:
        reasons.append("dark_roi_bright_pixels_outlier")
    return reasons


def _suspicion_score(
    row: dict[str, str],
    reasons: list[str],
    thresholds: dict[str, dict[str, float] | None],
) -> float:
    scores: list[float] = []
    if "isolated_full_frame_jump" in reasons:
        prev_delta = float(row["full_frame_mae_prev_rgb"] or 0.0)
        next_delta = float(row["full_frame_mae_next_rgb"] or 0.0)
        scores.append(min(prev_delta, next_delta) / RGB_JUMP_FLOOR)
    for reason, field, threshold_key in (
        ("stable_roi_template_outlier", "stable_roi_template_mae_rgb", "stable_roi_template_mae_rgb"),
        ("stable_roi_consecutive_outlier", "stable_roi_consecutive_mae_rgb", "stable_roi_consecutive_mae_rgb"),
        ("dark_roi_bright_pixels_outlier", "dark_roi_bright_pixels_gt100", "dark_roi_bright_pixels_gt100"),
    ):
        threshold = thresholds[threshold_key]
        if reason in reasons and threshold is not None:
            scores.append(float(row[field]) / max(threshold["floor"], threshold["threshold"]))
    return max(scores, default=0.0)


def _contact_sheet(
    output_path: Path,
    selected: list[tuple[float, int, list[str]]],
    thumbnail_path: Path,
    thumbnail_index_path: Path,
    decoded_frames: int,
) -> None:
    assert Image is not None and ImageDraw is not None and ImageFont is not None
    cell_width = 360
    header_height = 38
    thumb_width = 180
    if selected:
        with thumbnail_path.open("rb") as thumbs, thumbnail_index_path.open("rb") as indices:
            first_frame = selected[0][1]
            indices.seek(first_frame * FRAME_BYTES_PER_INDEX)
            offset, length = struct.unpack("!QQ", indices.read(FRAME_BYTES_PER_INDEX))
            thumbs.seek(offset)
            with Image.open(io.BytesIO(thumbs.read(length))) as first_image:
                thumb_height = first_image.height
        cell_height = header_height + thumb_height + 8
        sheet = Image.new("RGB", (cell_width, cell_height * len(selected)), (18, 20, 25))
        draw = ImageDraw.Draw(sheet)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Monaco.ttf", 12)
        except OSError:
            font = ImageFont.load_default()
        with thumbnail_path.open("rb") as thumbs, thumbnail_index_path.open("rb") as indices:
            for row_index, (score, frame_index, reasons) in enumerate(selected):
                indices.seek(frame_index * FRAME_BYTES_PER_INDEX)
                offset, length = struct.unpack("!QQ", indices.read(FRAME_BYTES_PER_INDEX))
                thumbs.seek(offset)
                with Image.open(io.BytesIO(thumbs.read(length))) as image:
                    image.load()
                    thumb = image.convert("RGB")
                y = row_index * cell_height
                reason_text = ", ".join(reasons)
                draw.text(
                    (8, y + 5),
                    f"frame {frame_index} | score {score:.2f} | {reason_text[:42]}",
                    fill=(238, 240, 246),
                    font=font,
                )
                sheet.paste(thumb, ((cell_width - thumb.width) // 2, y + header_height))
    else:
        sheet = Image.new("RGB", (cell_width, 90), (18, 20, 25))
        draw = ImageDraw.Draw(sheet)
        draw.text((12, 24), "No visual heuristic flags", fill=(238, 240, 246))
        draw.text((12, 48), f"Complete frames scanned: {decoded_frames}", fill=(180, 185, 195))
    sheet.save(output_path, format="JPEG", quality=88, optimize=True)


def _atomic_publish(temp_path: Path, final_path: Path) -> None:
    try:
        os.link(temp_path, final_path)
    except FileExistsError as exc:
        raise RuntimeError(f"refusing to overwrite existing output: {final_path}") from exc
    temp_path.unlink()


def _atomic_json(report: dict[str, Any], output_path: Path) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=output_path.parent,
        prefix=".report-", suffix=".tmp", delete=False,
    ) as handle:
        temp_path = Path(handle.name)
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    _atomic_publish(temp_path, output_path)


def _acquire_output_dir(path: Path) -> tuple[Path, int]:
    if path.exists() and not path.is_dir():
        raise RuntimeError(f"--output-dir is not a directory: {path}")
    path.mkdir(parents=True, exist_ok=True)
    report_path = path / "report.json"
    if report_path.exists():
        raise RuntimeError(f"refusing to overwrite existing report: {report_path}")
    existing = list(path.iterdir())
    if existing:
        names = ", ".join(sorted(item.name for item in existing[:5]))
        raise RuntimeError(f"--output-dir must be fresh and empty; found: {names}")
    lock_path = path / ".scan_visual_qc.lock"
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RuntimeError(f"another scan is using output directory: {path}") from exc
    return lock_path, fd


def _publish_metrics(
    raw_csv: Path,
    metrics_path: Path,
    thresholds: dict[str, dict[str, float] | None],
) -> tuple[list[dict[str, Any]], list[tuple[float, int, list[str]]]]:
    fields = [
        "frame", "time_seconds", "status", "partial_bytes",
        "full_frame_mae_prev_rgb", "full_frame_mae_next_rgb",
        "full_frame_mae_neighbors_rgb", "isolated_full_frame_jump",
        "stable_roi_template_mae_rgb", "stable_roi_template_threshold",
        "stable_roi_consecutive_mae_rgb", "stable_roi_consecutive_threshold",
        "dark_roi_bright_pixels_gt100", "dark_roi_bright_pixels_threshold",
        "suspicion_score", "reasons",
    ]
    flagged: list[dict[str, Any]] = []
    top: list[tuple[float, int, list[str]]] = []
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="", dir=metrics_path.parent,
        prefix=".metrics-", suffix=".tmp", delete=False,
    ) as handle:
        temp_path = Path(handle.name)
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        with raw_csv.open("r", newline="", encoding="utf-8") as raw_handle:
            for row in csv.DictReader(raw_handle):
                reasons = _row_reasons(row, thresholds)
                score = _suspicion_score(row, reasons, thresholds)
                result = dict(row)
                result["stable_roi_template_threshold"] = (
                    thresholds["stable_roi_template_mae_rgb"]["threshold"]
                    if thresholds["stable_roi_template_mae_rgb"] is not None
                    else ""
                )
                result["stable_roi_consecutive_threshold"] = (
                    thresholds["stable_roi_consecutive_mae_rgb"]["threshold"]
                    if thresholds["stable_roi_consecutive_mae_rgb"] is not None
                    else ""
                )
                result["dark_roi_bright_pixels_threshold"] = (
                    thresholds["dark_roi_bright_pixels_gt100"]["threshold"]
                    if thresholds["dark_roi_bright_pixels_gt100"] is not None
                    else ""
                )
                result["suspicion_score"] = round(score, 6) if reasons else ""
                result["reasons"] = ";".join(reasons)
                writer.writerow(result)
                if reasons:
                    frame_index = int(row["frame"])
                    flagged.append({"frame": frame_index, "reasons": reasons})
                    top.append((score, frame_index, reasons))
                    top.sort(key=lambda item: (item[0], -item[1]), reverse=True)
                    del top[10:]
        handle.flush()
        os.fsync(handle.fileno())
    _atomic_publish(temp_path, metrics_path)
    return flagged, top


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.expected_frames <= 0:
        print("scan_visual_qc: --expected-frames must be positive", file=sys.stderr)
        return 2
    try:
        require_dependencies()
    except RuntimeError as exc:
        print(f"scan_visual_qc: {exc}", file=sys.stderr)
        return 2

    media = args.media.expanduser().resolve()
    if not media.is_file():
        print(f"scan_visual_qc: media file not found: {media}", file=sys.stderr)
        return 2
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        missing = ", ".join(name for name, path in (("ffmpeg", ffmpeg), ("ffprobe", ffprobe)) if path is None)
        print(f"scan_visual_qc: required executable is not on PATH: {missing}", file=sys.stderr)
        return 2

    output_dir = args.output_dir.expanduser().resolve()
    try:
        lock_path, lock_fd = _acquire_output_dir(output_dir)
    except (OSError, RuntimeError) as exc:
        print(f"scan_visual_qc: {exc}", file=sys.stderr)
        return 2

    try:
        try:
            media_sha_before = file_sha256(media)
            probe, ffprobe_command = probe_media(ffprobe, media)
        except (OSError, RuntimeError) as exc:
            print(f"scan_visual_qc: {exc}", file=sys.stderr)
            return 2

        scaled_width = args.width
        scaled_height = even_scaled_height(probe["width"], probe["height"], scaled_width)
        fps = float(probe["fps"]["decimal"])
        ffmpeg_command = make_ffmpeg_command(ffmpeg, media, scaled_width, scaled_height)

        with tempfile.TemporaryDirectory(prefix=".scan-visual-qc-", dir=output_dir) as scratch_name:
            scratch = Path(scratch_name)
            raw_csv = scratch / "metrics-raw.csv"
            thumbnails = scratch / "thumbnails.bin"
            thumbnail_index = scratch / "thumbnail-index.bin"
            try:
                scan = scan_frames(
                    command=ffmpeg_command,
                    width=scaled_width,
                    height=scaled_height,
                    fps=fps,
                    stable_roi=args.stable_roi,
                    dark_roi=args.dark_roi,
                    raw_csv_path=raw_csv,
                    thumbnail_path=thumbnails,
                    thumbnail_index_path=thumbnail_index,
                )
            except (OSError, RuntimeError, ValueError, TimeoutError) as exc:
                print(f"scan_visual_qc: scan failed: {exc}", file=sys.stderr)
                return 2

            try:
                media_sha_after = file_sha256(media)
                hash_matches = media_sha_before == media_sha_after
                if not hash_matches:
                    scan["decode_error"] = scan["decode_error"] or "source SHA-256 changed during scan"
            except OSError as exc:
                media_sha_after = None
                hash_matches = False
                scan["decode_error"] = scan["decode_error"] or f"could not hash media after scan: {exc}"

            try:
                thresholds = _metric_thresholds(
                    raw_csv, args.stable_roi, args.dark_roi, scratch
                )
                metrics_path = output_dir / "metrics.csv"
                flagged, top = _publish_metrics(
                    raw_csv,
                    metrics_path,
                    thresholds,
                )
                contact_path = output_dir / "suspicious-contact.jpg"
                contact_temp = scratch / "suspicious-contact.jpg"
                _contact_sheet(
                    contact_temp,
                    top,
                    thumbnails,
                    thumbnail_index,
                    scan["decoded_frames"],
                )
                _atomic_publish(contact_temp, contact_path)
            except (OSError, RuntimeError, ValueError) as exc:
                print(f"scan_visual_qc: could not write scan evidence: {exc}", file=sys.stderr)
                return 2

            frame_count_matches = scan["decoded_frames"] == args.expected_frames
            incomplete_reasons: list[str] = []
            if scan["return_code"] != 0:
                incomplete_reasons.append("ffmpeg_return_code_nonzero")
            if scan["partial_frame_bytes"]:
                incomplete_reasons.append("partial_raw_frame")
            if scan["decode_error"]:
                incomplete_reasons.append(scan["decode_error"])
            if not frame_count_matches:
                incomplete_reasons.append("decoded_frame_count_does_not_match_expected")
            if not hash_matches:
                incomplete_reasons.append("media_sha256_changed")
            complete = (
                scan["return_code"] == 0
                and scan["partial_frame_bytes"] == 0
                and scan["decode_error"] is None
                and frame_count_matches
                and hash_matches
            )
            analysis = ["isolated_full_frame_jump"]
            if args.stable_roi is not None:
                analysis.append("stable_roi")
            if args.dark_roi is not None:
                analysis.append("dark_roi")
            scan_report = {
                "mode": "continuous_from_start",
                "every_frame": True,
                "no_input_seek": True,
                "decoded_frames": scan["decoded_frames"],
                "expected_frames": args.expected_frames,
                "return_code": scan["return_code"],
                "analysis": analysis,
                "scaled_width": scaled_width,
                "scaled_height": scaled_height,
                "config": {
                    "width_requested": scaled_width,
                    "stable_roi_normalized_xywh": list(args.stable_roi) if args.stable_roi else None,
                    "dark_roi_normalized_xywh": list(args.dark_roi) if args.dark_roi else None,
                    "isolated_jump_mae_floor": RGB_JUMP_FLOOR,
                    "isolated_jump_neighbor_limit": "max(3, 0.35 * min(prev_middle_mae, middle_next_mae))",
                    "stable_roi_threshold": "median + 8 * (1.4826 * MAD), floor 8 RGB MAE",
                    "dark_roi_threshold": "median + 8 * (1.4826 * MAD), floor 50 pixels with luma > 100",
                    "dark_roi_bright_luma_threshold_exclusive": BRIGHT_LUMA_THRESHOLD,
                    "ffmpeg_threads": 2,
                    "ffmpeg_filter_threads": 2,
                    "pixel_format": "rgb24",
                    "autorotate": False,
                },
                "partial_frame_bytes": scan["partial_frame_bytes"],
                "frame_count_matches_expected": frame_count_matches,
                "media_sha256_after": media_sha_after,
                "media_sha256_matches": hash_matches,
                "complete": complete,
                "decode_error": scan["decode_error"],
                "incomplete_reasons": incomplete_reasons,
                "stderr_tail": scan["stderr_tail"],
            }
            report = {
                "schema_version": 1,
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "media_path": str(media),
                "media_sha256": media_sha_before,
                "probe": probe,
                "scan": scan_report,
                "roi_thresholds": thresholds,
                "flagged_frames": flagged,
                "flag_reviews": [],
                "limitations": LIMITATIONS,
                "evidence_files": {
                    "metrics_csv": "metrics.csv",
                    "suspicious_contact_jpeg": "suspicious-contact.jpg",
                },
                "commands": {"ffprobe": ffprobe_command, "ffmpeg": ffmpeg_command},
                "summary": {
                    "flagged_frame_count": len(flagged),
                    "contact_sheet_frame_numbers": [frame for _, frame, _ in top],
                },
            }
            try:
                _atomic_json(report, output_dir / "report.json")
            except (OSError, RuntimeError) as exc:
                print(f"scan_visual_qc: could not publish report: {exc}", file=sys.stderr)
                return 2

        print(
            json.dumps(
                {
                    "complete": complete,
                    "decoded_frames": scan["decoded_frames"],
                    "expected_frames": args.expected_frames,
                    "flagged_frames": len(flagged),
                    "incomplete_reasons": incomplete_reasons,
                    "outputs": {
                        "report": str(output_dir / "report.json"),
                        "metrics": str(output_dir / "metrics.csv"),
                        "contact": str(output_dir / "suspicious-contact.jpg"),
                    },
                },
                ensure_ascii=False,
            )
        )
        if not complete:
            return 2
        return 3 if flagged else 0
    finally:
        os.close(lock_fd)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("scan_visual_qc: interrupted", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"scan_visual_qc: {exc}", file=sys.stderr)
        raise SystemExit(2)
