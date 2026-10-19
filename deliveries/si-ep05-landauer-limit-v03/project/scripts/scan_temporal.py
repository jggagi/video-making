#!/usr/bin/env python3
"""Stream an encoded MP4 and flag conservative static-region anomalies.

This is a diagnostic screen, not a perceptual quality gate. The watermark ROI
is compared with the first encoded frame, and the portrait's bottom safe strip
is checked for unusually bright pixels. Neither measurement can establish the
absence of every kind of flicker elsewhere in the picture.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont


SCALED_WIDTH = 360
LAYOUTS = {
    "portrait": {
        "logical_size": (1080, 1920),
        "watermark_xywh": (65, 316, 520, 36),
        "safe_strip_y": (1600, 1900),
    },
    "landscape": {
        "logical_size": (1920, 1080),
        "watermark_xywh": (72, 43, 650, 28),
        "safe_strip_y": None,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--media", required=True, type=Path)
    parser.add_argument("--layout", required=True, choices=tuple(LAYOUTS))
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--expected-frames", type=int, default=7200)
    return parser.parse_args()


def require_numpy_pillow() -> None:
    # Imports above deliberately fail early with the missing module's name.
    if np is None or Image is None:  # pragma: no cover - import failure occurs first
        raise RuntimeError("NumPy and Pillow are required")


def luma(rgb: np.ndarray) -> np.ndarray:
    values = rgb.astype(np.float32, copy=False)
    return values[..., 0] * 0.2126 + values[..., 1] * 0.7152 + values[..., 2] * 0.0722


def roi_bounds(frame: np.ndarray, layout: str) -> tuple[int, int, int, int]:
    logical_width, logical_height = LAYOUTS[layout]["logical_size"]
    x, y, width, height = LAYOUTS[layout]["watermark_xywh"]
    scale_x = frame.shape[1] / logical_width
    scale_y = frame.shape[0] / logical_height
    x0 = max(0, round(x * scale_x))
    y0 = max(0, round(y * scale_y))
    x1 = min(frame.shape[1], x0 + round(width * scale_x))
    y1 = min(frame.shape[0], y0 + round(height * scale_y))
    return x0, y0, x1, y1


def crop_watermark(frame: np.ndarray, layout: str) -> np.ndarray:
    x0, y0, x1, y1 = roi_bounds(frame, layout)
    return frame[y0:y1, x0:x1]


def correlation(left: np.ndarray, right: np.ndarray) -> float | None:
    a = luma(left).reshape(-1)
    b = luma(right).reshape(-1)
    a_std = float(a.std())
    b_std = float(b.std())
    if a_std < 1e-6 or b_std < 1e-6:
        return None
    value = float(np.mean((a - a.mean()) * (b - b.mean())) / (a_std * b_std))
    return max(-1.0, min(1.0, value))


def watermark_metrics(
    frame: np.ndarray,
    template: np.ndarray,
    previous: np.ndarray | None,
    layout: str,
) -> dict[str, float | int | None]:
    current = crop_watermark(frame, layout)
    delta = np.abs(current.astype(np.int16) - template.astype(np.int16))
    gray = luma(current)
    result: dict[str, float | int | None] = {
        "watermark_mae_rgb": float(delta.mean()),
        "watermark_mae_luma": float(np.abs(luma(current) - luma(template)).mean()),
        "watermark_correlation": 1.0 if np.array_equal(current, template) else correlation(current, template),
        "watermark_bright_pixels_gt160": int(np.count_nonzero(gray > 160.0)),
        "watermark_prev_mae_rgb": (
            None if previous is None
            else float(np.abs(current.astype(np.int16) - previous.astype(np.int16)).mean())
        ),
    }
    return result


def safe_strip_metrics(frame: np.ndarray, layout: str) -> dict[str, int | float | None]:
    strip = LAYOUTS[layout]["safe_strip_y"]
    if strip is None:
        return {"safe_strip_bright_pixels_gt100": 0, "safe_strip_bright_fraction": None}
    logical_height = LAYOUTS[layout]["logical_size"][1]
    y0 = max(0, math.floor(strip[0] * frame.shape[0] / logical_height))
    y1 = min(frame.shape[0], math.ceil(strip[1] * frame.shape[0] / logical_height))
    gray = luma(frame[y0:y1, :, :])
    bright = int(np.count_nonzero(gray > 100.0))
    return {
        "safe_strip_bright_pixels_gt100": bright,
        "safe_strip_bright_fraction": float(bright / gray.size) if gray.size else 0.0,
    }


def robust_upper(values: list[float], floor: float) -> dict[str, float]:
    finite = np.asarray([value for value in values if math.isfinite(value)], dtype=np.float64)
    if finite.size == 0:
        return {"median": 0.0, "mad": 0.0, "threshold": floor}
    median = float(np.median(finite))
    mad = float(np.median(np.abs(finite - median)))
    sigma = 1.4826 * mad
    return {"median": median, "mad": mad, "threshold": max(floor, median + 8.0 * sigma)}


def make_ffmpeg_command(ffmpeg: str, media: Path) -> list[str]:
    return [
        ffmpeg,
        "-hide_banner", "-loglevel", "error", "-nostdin",
        "-threads", "2", "-filter_threads", "2", "-noautorotate",
        "-i", str(media),
        "-map", "0:v:0", "-an", "-sn", "-dn",
        "-vf", f"scale={SCALED_WIDTH}:-2:flags=bilinear",
        "-vsync", "0", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1",
    ]


def read_frame(pipe: Any, frame_bytes: int) -> bytes:
    chunk = bytearray()
    while len(chunk) < frame_bytes:
        part = pipe.read(frame_bytes - len(chunk))
        if not part:
            break
        chunk.extend(part)
    return bytes(chunk)


def add_candidate(
    candidates: list[tuple[float, int, np.ndarray]],
    score: float,
    index: int,
    frame: np.ndarray,
    limit: int = 20,
) -> None:
    if len(candidates) == limit and score <= candidates[-1][0]:
        return
    candidates.append((score, index, frame.copy()))
    candidates.sort(key=lambda item: (item[0], -item[1]), reverse=True)
    del candidates[limit:]


def draw_contact_sheet(candidates: list[tuple[float, int, np.ndarray]], output: Path) -> None:
    selected = candidates[:10]
    if not selected:
        return
    cell_width = 360
    header_height = 28
    thumb_width = 180
    thumb_height = max(1, round(selected[0][2].shape[0] * thumb_width / selected[0][2].shape[1]))
    cell_height = header_height + thumb_height
    sheet = Image.new("RGB", (cell_width, cell_height * 10), (18, 20, 25))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Monaco.ttf", 13)
    except OSError:
        font = ImageFont.load_default()
    for position, (score, index, frame) in enumerate(selected):
        row = position
        y = row * cell_height
        draw.text((8, y + 6), f"frame {index} | {index / 60.0:.3f}s | score {score:.2f}", fill=(238, 240, 246), font=font)
        thumb = Image.fromarray(frame).resize((thumb_width, thumb_height), Image.Resampling.BILINEAR)
        sheet.paste(thumb, ((cell_width - thumb_width) // 2, y + header_height))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, format="JPEG", quality=92, optimize=True)


def main() -> int:
    args = parse_args()
    require_numpy_pillow()
    media = args.media.expanduser().resolve()
    if not media.is_file():
        print(f"scan_temporal: media file not found: {media}", file=sys.stderr)
        return 2
    if args.expected_frames <= 0:
        print("scan_temporal: --expected-frames must be positive", file=sys.stderr)
        return 2
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        print("scan_temporal: ffmpeg is not available on PATH", file=sys.stderr)
        return 2

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    media_stat = media.stat()
    command = make_ffmpeg_command(ffmpeg, media)
    stderr_file = tempfile.TemporaryFile()
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=stderr_file)
    except OSError as exc:
        stderr_file.close()
        print(f"scan_temporal: could not start ffmpeg: {exc}", file=sys.stderr)
        return 2

    records: list[dict[str, Any]] = []
    candidates: list[tuple[float, int, np.ndarray]] = []
    frame_index = 0
    frame_width = SCALED_WIDTH
    frame_height: int | None = None
    template: np.ndarray | None = None
    previous_watermark: np.ndarray | None = None
    try:
        assert process.stdout is not None
        while True:
            if frame_height is None:
                # Both supported canvases have known reduced dimensions. FFmpeg's
                # scale filter preserves the original display ratio and rounds to even.
                logical_width, logical_height = LAYOUTS[args.layout]["logical_size"]
                frame_height = max(2, round(SCALED_WIDTH * logical_height / logical_width))
                if frame_height % 2:
                    frame_height -= 1
            frame_bytes = frame_width * frame_height * 3
            payload = read_frame(process.stdout, frame_bytes)
            if not payload:
                break
            if len(payload) != frame_bytes:
                raise RuntimeError(f"truncated raw frame {frame_index}: {len(payload)} of {frame_bytes} bytes")
            frame = np.frombuffer(payload, dtype=np.uint8).reshape((frame_height, frame_width, 3))
            current_watermark = crop_watermark(frame, args.layout)
            if template is None:
                template = current_watermark.copy()
            wm = watermark_metrics(frame, template, previous_watermark, args.layout)
            safe = safe_strip_metrics(frame, args.layout)
            gray_mean = float(luma(frame).mean())
            previous_delta = wm["watermark_prev_mae_rgb"]
            corr = wm["watermark_correlation"]
            score = (
                float(wm["watermark_mae_rgb"]) / 15.0
                + (max(0.0, 0.5 - float(corr)) * 4.0 if corr is not None else 0.0)
                + (float(previous_delta) / 20.0 if previous_delta is not None else 0.0)
                + float(safe["safe_strip_bright_pixels_gt100"]) / 50.0
            )
            record: dict[str, Any] = {
                "frame": frame_index,
                "time_seconds": round(frame_index / 60.0, 6),
                "full_frame_luma_mean": round(gray_mean, 4),
                **{key: round(value, 5) if isinstance(value, float) else value for key, value in wm.items()},
                **{key: round(value, 6) if isinstance(value, float) else value for key, value in safe.items()},
                "suspicion_score": round(score, 5),
                "anomaly_flags": [],
            }
            records.append(record)
            add_candidate(candidates, score, frame_index, frame, limit=20)
            previous_watermark = current_watermark.copy()
            frame_index += 1
            if frame_index % 600 == 0:
                print(f"[scan-temporal] decoded {frame_index} frames", flush=True)
        process.stdout.close()
        returncode = process.wait()
        stderr_file.seek(0)
        ffmpeg_stderr = stderr_file.read().decode("utf-8", errors="replace").strip()
    except Exception:
        process.terminate()
        process.wait()
        raise
    finally:
        stderr_file.close()

    if returncode != 0:
        print(f"scan_temporal: ffmpeg exited {returncode}: {ffmpeg_stderr[-1600:]}", file=sys.stderr)
        return 1
    if frame_index == 0:
        print("scan_temporal: ffmpeg produced no video frames", file=sys.stderr)
        return 1

    wm_template = robust_upper([float(row["watermark_mae_rgb"]) for row in records], floor=8.0)
    wm_temporal = robust_upper(
        [float(row["watermark_prev_mae_rgb"]) for row in records if row["watermark_prev_mae_rgb"] is not None],
        floor=8.0,
    )
    safe_counts = [float(row["safe_strip_bright_pixels_gt100"]) for row in records]
    safe_threshold = robust_upper(safe_counts, floor=50.0) if args.layout == "portrait" else None
    for row in records:
        flags: list[str] = []
        if float(row["watermark_mae_rgb"]) > wm_template["threshold"]:
            flags.append("watermark_template_outlier")
        corr = row["watermark_correlation"]
        if corr is not None and float(corr) < 0.15 and float(row["watermark_mae_rgb"]) > 10.0:
            flags.append("watermark_low_correlation_and_changed")
        prev = row["watermark_prev_mae_rgb"]
        if prev is not None and float(prev) > wm_temporal["threshold"]:
            flags.append("watermark_temporal_jump")
        if safe_threshold is not None and float(row["safe_strip_bright_pixels_gt100"]) > safe_threshold["threshold"]:
            flags.append("portrait_safe_strip_bright_outlier")
        row["anomaly_flags"] = flags

    csv_path = output_dir / "temporal-scan.csv"
    json_path = output_dir / "temporal-scan.json"
    contact_path = output_dir / "suspicious-top10.jpg"
    fieldnames = list(records[0])
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in records:
            writer.writerow({
                key: ";".join(row[key]) if key == "anomaly_flags" else row[key]
                for key in fieldnames
            })
    draw_contact_sheet(candidates, contact_path)

    metrics = {
        "watermark_template_mae_rgb": wm_template,
        "watermark_consecutive_mae_rgb": wm_temporal,
        "portrait_safe_strip_bright_pixel_count_gt100": safe_threshold,
    }
    flagged = [row for row in records if row["anomaly_flags"]]
    top20 = sorted(records, key=lambda row: float(row["suspicion_score"]), reverse=True)[:20]
    report = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "media": str(media),
        "media_size_bytes": media_stat.st_size,
        "media_mtime_ns": media_stat.st_mtime_ns,
        "layout": args.layout,
        "decode": {
            "method": "continuous decode from file start; no seek; scaled RGB24 stream",
            "ffmpeg_command": command,
            "threads": 2,
            "scaled_size": [frame_width, frame_height],
            "decoded_frames": frame_index,
            "expected_frames": args.expected_frames,
            "frame_count_matches_expected": frame_index == args.expected_frames,
            "return_code": returncode,
        },
        "regions": {
            "watermark_logical_xywh": LAYOUTS[args.layout]["watermark_xywh"],
            "watermark_scaled_xyxy": list(roi_bounds(np.zeros((frame_height, frame_width, 3), dtype=np.uint8), args.layout)),
            "watermark_template": "first decoded frame ROI",
            "watermark_bright_luma_threshold_exclusive": 160,
            "portrait_safe_strip_logical_y_range": LAYOUTS[args.layout]["safe_strip_y"],
            "portrait_safe_strip_bright_luma_threshold_exclusive": 100,
        },
        "metric_summaries": metrics,
        "heuristic_thresholds": {
            "template_or_temporal_outlier": "median + 8 * (1.4826 * MAD), with minimum RGB MAE threshold 8",
            "low_correlation_and_changed": "correlation < 0.15 and template RGB MAE > 10",
            "portrait_safe_strip": "median + 8 * (1.4826 * MAD), with minimum bright-pixel count threshold 50",
            "scope_note": "conservative region-specific screening heuristics; not a whole-picture or perceptual pass",
        },
        "flagged_frame_count": len(flagged),
        "flagged_frames": [
            {"frame": row["frame"], "time_seconds": row["time_seconds"], "flags": row["anomaly_flags"]}
            for row in flagged
        ],
        "top20_suspicious_frames": [
            {
                "frame": row["frame"], "time_seconds": row["time_seconds"],
                "score": row["suspicion_score"], "flags": row["anomaly_flags"],
                "watermark_mae_rgb": row["watermark_mae_rgb"],
                "watermark_correlation": row["watermark_correlation"],
                "watermark_prev_mae_rgb": row["watermark_prev_mae_rgb"],
                "watermark_bright_pixels_gt160": row["watermark_bright_pixels_gt160"],
                "safe_strip_bright_pixels_gt100": row["safe_strip_bright_pixels_gt100"],
            }
            for row in top20
        ],
        "evidence_files": {
            "per_frame_csv": str(csv_path),
            "top10_contact_sheet": str(contact_path),
        },
        "interpretation_limit": "No flagged frames is not evidence that all flicker is absent. Motion outside the static watermark ROI and portrait bottom strip is not screened as a failure condition.",
    }
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "decoded_frames": frame_index,
        "expected_frames": args.expected_frames,
        "flagged_frames": len(flagged),
        "top_frames": [item["frame"] for item in report["top20_suspicious_frames"][:10]],
        "outputs": {"json": str(json_path), "csv": str(csv_path), "contact": str(contact_path)},
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("scan_temporal: interrupted", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"scan_temporal: {exc}", file=sys.stderr)
        raise SystemExit(1)
