#!/usr/bin/env python3
"""Capture compact paired-frame evidence from the final encoded EP08 videos.

This helper records source hashes and frame/time mappings. Its edge-difference
numbers are only a lightweight review cue; they do not establish visual quality
or human/device acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
DELIVERY_DIR = SCRIPT_PATH.parents[2]
DEFAULT_DELIVERY = DELIVERY_DIR / "delivery.json"

PAIR_MAP: tuple[tuple[str, int, int], ...] = (
    ("rigid", 180, 330),
    ("rigid", 690, 840),
    ("rigid", 1020, 1170),
    ("title", 1350, 1500),
    ("erosion", 2010, 2160),
    ("erosion", 2370, 2520),
    ("erosion", 2820, 2970),
    ("erosion", 3270, 3420),
    ("artifact", 3780, 3930),
    ("artifact", 4200, 4350),
    ("artifact", 4590, 4740),
    ("artifact", 5100, 5250),
    ("city", 5460, 5610),
    ("city", 5820, 5970),
    ("city", 6090, 6240),
    ("nexus", 6390, 6540),
    ("nexus", 6660, 6810),
    ("finale", 6960, 7110),
)

LAYOUTS = (
    ("bilibili", "landscape", 4, 2),
    ("xiaohongshu", "portrait", 2, 4),
)


class CaptureError(RuntimeError):
    """Raised when media or tool preconditions are not met."""


def run_process(command: list[str], *, binary_output: bool = False) -> subprocess.CompletedProcess[Any]:
    try:
        return subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=not binary_output,
        )
    except FileNotFoundError:
        raise CaptureError(f"required executable is unavailable: {command[0]}") from None
    except OSError as exc:
        raise CaptureError(f"could not run {command[0]}: {exc}") from None


def require_success(result: subprocess.CompletedProcess[Any], action: str) -> None:
    if result.returncode == 0:
        return
    stderr = result.stderr
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", errors="replace")
    raise CaptureError(f"{action} failed: {str(stderr).strip()[-1800:] or result.returncode}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise CaptureError(f"cannot read source video {path}: {exc}") from None
    return digest.hexdigest()


def safe_delivery_path(delivery_dir: Path, relative: Any, name: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise CaptureError(f"delivery.json is missing outputs.{name}.path")
    root = delivery_dir.resolve()
    candidate = (delivery_dir / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise CaptureError(f"outputs.{name}.path must stay within the delivery directory") from None
    return candidate


def probe_video(ffprobe: str, path: Path, expected: dict[str, Any], declared_fps: Fraction, final_frame: int) -> dict[str, Any]:
    result = run_process(
        [
            ffprobe,
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,avg_frame_rate,duration",
            "-show_entries", "format=duration",
            "-of", "json",
            str(path),
        ]
    )
    require_success(result, f"ffprobe on {path.name}")
    try:
        data = json.loads(result.stdout)
        stream = data["streams"][0]
        width, height = int(stream["width"]), int(stream["height"])
        actual_fps = Fraction(stream["avg_frame_rate"])
    except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError, json.JSONDecodeError):
        raise CaptureError(f"ffprobe returned incomplete video metadata for {path.name}") from None

    if width != int(expected["width"]) or height != int(expected["height"]):
        raise CaptureError(
            f"{path.name} is {width}x{height}; delivery.json requires "
            f"{expected['width']}x{expected['height']}"
        )
    if actual_fps != declared_fps:
        raise CaptureError(f"{path.name} reports {actual_fps} fps; delivery.json declares {declared_fps} fps")

    duration = None
    for duration_value in (stream.get("duration"), data.get("format", {}).get("duration")):
        try:
            if duration_value is not None:
                duration = float(duration_value)
                break
        except (TypeError, ValueError):
            continue
    if duration is None:
        raise CaptureError(f"ffprobe returned no usable duration for {path.name}") from None
    if duration * float(actual_fps) < final_frame + 1:
        raise CaptureError(f"{path.name} ends before requested frame {final_frame}")

    return {
        "width": width,
        "height": height,
        "fps": str(actual_fps),
        "duration_seconds": duration,
    }


def extract_compact_frames(
    ffmpeg: str,
    source: Path,
    output_dir: Path,
    frames: list[int],
) -> dict[int, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    expression = "+".join(f"eq(n\\,{frame})" for frame in frames)
    video_filter = f"select='{expression}',scale=360:-2:flags=lanczos,format=yuvj420p"
    pattern = output_dir / "selected-%03d.jpg"
    result = run_process(
        [
            ffmpeg,
            "-hide_banner", "-nostdin", "-v", "error",
            "-i", str(source),
            "-map", "0:v:0", "-an", "-sn", "-dn",
            "-vf", video_filter,
            "-fps_mode", "vfr",
            "-frames:v", str(len(frames)),
            "-q:v", "2",
            str(pattern),
        ]
    )
    require_success(result, f"frame extraction for {source.name}")

    selected = sorted(output_dir.glob("selected-*.jpg"))
    if len(selected) != len(frames):
        raise CaptureError(
            f"{source.name} yielded {len(selected)} selected frames; expected {len(frames)}"
        )

    frame_paths: dict[int, Path] = {}
    for frame, selected_path in zip(frames, selected, strict=True):
        target = output_dir / f"frame-{frame:05d}.jpg"
        selected_path.replace(target)
        frame_paths[frame] = target
    return frame_paths


def contact_sheet(
    ffmpeg: str,
    frame_paths: list[tuple[int, Path]],
    output_path: Path,
    columns: int,
    rows: int,
    cell_height: int,
) -> list[dict[str, int]]:
    if not frame_paths or len(frame_paths) > columns * rows:
        raise CaptureError("contact sheet page must contain between 1 and 8 frames")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    inputs: list[str] = []
    labels: list[str] = []
    cells: list[dict[str, int]] = []
    for index, (frame, path) in enumerate(frame_paths):
        inputs.extend(["-i", str(path)])
        labels.append(f"[{index}:v]")
        cells.append({
            "cell": index + 1,
            "frame": frame,
            "column": index % columns + 1,
            "row": index // columns + 1,
        })
    layout = "|".join(
        f"{(index % columns) * 360}_{(index // columns) * cell_height}"
        for index in range(len(frame_paths))
    )
    graph = (
        f"{''.join(labels)}xstack=inputs={len(frame_paths)}:layout={layout}:fill=black,"
        "format=yuvj420p[out]"
    )
    result = run_process(
        [
            ffmpeg,
            "-hide_banner", "-nostdin", "-v", "error",
            *inputs,
            "-filter_complex", graph,
            "-map", "[out]", "-frames:v", "1", "-q:v", "3",
            str(output_path),
        ]
    )
    require_success(result, f"contact sheet {output_path.name}")
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise CaptureError(f"ffmpeg did not create {output_path.name}")
    return cells


def even_floor(value: float) -> int:
    return max(2, int(math.floor(value / 2) * 2))


def edge_difference_yavg(
    ffmpeg: str,
    first_image: Path,
    second_image: Path,
    compact_width: int,
    compact_height: int,
    roi: tuple[float, float, float, float],
) -> float:
    x0, y0, x1, y1 = roi
    crop_x = even_floor(compact_width * x0)
    crop_y = even_floor(compact_height * y0)
    crop_width = even_floor(compact_width * (x1 - x0))
    crop_height = even_floor(compact_height * (y1 - y0))
    if crop_x + crop_width > compact_width:
        crop_width = even_floor(compact_width - crop_x)
    if crop_y + crop_height > compact_height:
        crop_height = even_floor(compact_height - crop_y)
    crop = f"crop={crop_width}:{crop_height}:{crop_x}:{crop_y}"
    edge_pipeline = f"{crop},scale=160:-2:flags=area,format=yuv444p,edgedetect=low=0.1:high=0.2,format=gray"
    graph = (
        f"[0:v]{edge_pipeline}[first];[1:v]{edge_pipeline}[second];"
        "[first][second]blend=all_mode=difference,format=gray[out]"
    )
    result = run_process(
        [
            ffmpeg,
            "-hide_banner", "-nostdin", "-v", "error",
            "-i", str(first_image), "-i", str(second_image),
            "-filter_complex", graph,
            "-map", "[out]", "-frames:v", "1",
            "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1",
        ],
        binary_output=True,
    )
    require_success(result, "edge-difference estimate")
    pixels: bytes = result.stdout
    if not pixels:
        raise CaptureError("edge-difference filter produced no pixels")
    return sum(pixels) / len(pixels)


def versioned_output_dir(review_dir: Path, bilibili_hash: str, xiaohongshu_hash: str) -> Path:
    prefix = f"motion-evidence-b{bilibili_hash[:10]}-x{xiaohongshu_hash[:10]}"
    revision = 1
    while True:
        candidate = review_dir / f"{prefix}-r{revision:02d}"
        if not candidate.exists():
            return candidate
        revision += 1


def capture(delivery_path: Path) -> Path:
    try:
        delivery = json.loads(delivery_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise CaptureError(f"delivery manifest not found: {delivery_path}") from None
    except (OSError, json.JSONDecodeError) as exc:
        raise CaptureError(f"cannot read delivery manifest {delivery_path}: {exc}") from None

    delivery_dir = delivery_path.parent.resolve()
    outputs = delivery.get("outputs")
    if not isinstance(outputs, dict):
        raise CaptureError("delivery.json has no outputs object")

    source_paths: dict[str, Path] = {}
    for key, _, _, _ in LAYOUTS:
        spec = outputs.get(key)
        if not isinstance(spec, dict):
            raise CaptureError(f"delivery.json is missing outputs.{key}")
        source = safe_delivery_path(delivery_dir, spec.get("path"), key)
        if not source.is_file():
            raise CaptureError(f"final video is missing: {source}")
        source_paths[key] = source

    try:
        fps = Fraction(str(delivery["fps"]))
        total_frames = int(delivery["total_frames"])
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        raise CaptureError("delivery.json needs numeric fps and total_frames") from None
    selected_frames = sorted({frame for _, start, end in PAIR_MAP for frame in (start, end)})
    if not selected_frames or selected_frames[-1] >= total_frames:
        raise CaptureError("motion evidence frame map exceeds delivery.json total_frames")

    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        missing = " and ".join(tool for tool, path in (("ffmpeg", ffmpeg), ("ffprobe", ffprobe)) if not path)
        raise CaptureError(f"required tool unavailable: {missing}; no installation was attempted")

    source_hashes = {key: sha256_file(path) for key, path in source_paths.items()}
    probe_info: dict[str, dict[str, Any]] = {}
    for key, _, _, _ in LAYOUTS:
        probe_info[key] = probe_video(
            ffprobe,
            source_paths[key],
            outputs[key],
            fps,
            selected_frames[-1],
        )

    review_dir = delivery_dir / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    final_dir = versioned_output_dir(review_dir, source_hashes["bilibili"], source_hashes["xiaohongshu"])
    work_dir = Path(tempfile.mkdtemp(prefix=".motion-evidence-", dir=review_dir))

    try:
        layout_results: dict[str, dict[str, Any]] = {}
        compact_frames: dict[str, dict[int, Path]] = {}
        for key, layout_name, columns, rows in LAYOUTS:
            frame_dir = work_dir / layout_name / "frames"
            frame_paths = extract_compact_frames(
                ffmpeg,
                source_paths[key],
                frame_dir,
                selected_frames,
            )
            compact_frames[key] = frame_paths
            width = probe_info[key]["width"]
            height = probe_info[key]["height"]
            cell_height = even_floor(height * 360 / width)
            pages: list[dict[str, Any]] = []
            ordered_frames = list(frame_paths.items())
            page_size = columns * rows
            for page_index, start in enumerate(range(0, len(ordered_frames), page_size), start=1):
                page_items = ordered_frames[start:start + page_size]
                page_path = work_dir / layout_name / "contact-sheets" / f"page-{page_index:02d}.jpg"
                cells = contact_sheet(ffmpeg, page_items, page_path, columns, rows, cell_height)
                pages.append({
                    "path": page_path.relative_to(work_dir).as_posix(),
                    "columns": columns,
                    "rows": rows,
                    "cells": [
                        {
                            **cell,
                            "time_seconds": round(cell["frame"] / float(fps), 6),
                        }
                        for cell in cells
                    ],
                })

            frame_records = [
                {
                    "frame": frame,
                    "time_seconds": round(frame / float(fps), 6),
                    "path": path.relative_to(work_dir).as_posix(),
                    "source_path": source_paths[key].relative_to(delivery_dir).as_posix(),
                    "source_sha256": source_hashes[key],
                }
                for frame, path in ordered_frames
            ]
            layout_results[key] = {
                "layout": layout_name,
                "source_path": source_paths[key].relative_to(delivery_dir).as_posix(),
                "source_sha256": source_hashes[key],
                "video": probe_info[key],
                "compact_frame_width": 360,
                "frames": frame_records,
                "contact_sheets": pages,
            }

        pair_results: list[dict[str, Any]] = []
        for scene, first, second in PAIR_MAP:
            per_layout: dict[str, Any] = {}
            for key, layout_name, _, _ in LAYOUTS:
                width = probe_info[key]["width"]
                height = probe_info[key]["height"]
                if width > height:
                    roi = (0.50, 0.24, 0.95, 0.78)
                elif scene == "finale":
                    roi = (0.10, 0.23, 0.84, 0.61)
                else:
                    roi = (0.10, 0.23, 0.84, 0.61)
                compact_h = even_floor(height * 360 / width)
                first_image = compact_frames[key][first]
                second_image = compact_frames[key][second]
                try:
                    yavg = edge_difference_yavg(
                        ffmpeg,
                        first_image,
                        second_image,
                        360,
                        compact_h,
                        roi,
                    )
                    warning = "edge-difference YAVG is below 0.5" if yavg < 0.5 else None
                    per_layout[layout_name] = {
                        "roi_fraction": {"x0": roi[0], "y0": roi[1], "x1": roi[2], "y1": roi[3]},
                        "edge_difference_yavg": round(yavg, 4),
                        "warning": warning,
                    }
                except CaptureError as exc:
                    per_layout[layout_name] = {
                        "roi_fraction": {"x0": roi[0], "y0": roi[1], "x1": roi[2], "y1": roi[3]},
                        "edge_difference_yavg": None,
                        "warning": f"metric unavailable: {exc}",
                    }
            pair_results.append({
                "scene": scene,
                "start_frame": first,
                "end_frame": second,
                "start_time_seconds": round(first / float(fps), 6),
                "end_time_seconds": round(second / float(fps), 6),
                "layouts": per_layout,
            })

        report = {
            "schema_version": 1,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "delivery_manifest": delivery_path.resolve().relative_to(delivery_dir).as_posix(),
            "fps": str(fps),
            "total_frames": total_frames,
            "pair_map": [
                {"scene": scene, "start_frame": start, "end_frame": end}
                for scene, start, end in PAIR_MAP
            ],
            "layouts": layout_results,
            "pairs": pair_results,
            "interpretation": {
                "edge_difference": "Heuristic edge-map pixel difference at the listed ROI; YAVG is 0-255.",
                "threshold_warning": "Values below 0.5 are flagged for review, not treated as a motion pass/fail.",
                "disclaimer": "These are source-review aids only. Visual review, continuous human review, and target-device playback remain required.",
            },
        }
        (work_dir / "motion-evidence.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if final_dir.exists():
            raise CaptureError(f"evidence directory appeared during capture: {final_dir}")
        os.replace(work_dir, final_dir)
    except Exception:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise

    return final_dir


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Capture paired long-shot frames from both final encoded EP08 outputs, "
            "write compact contact sheets, and record heuristic edge differences."
        ),
        epilog="Evidence is a review aid and does not replace visual, continuous human, or device review.",
    )
    parser.add_argument(
        "--delivery",
        type=Path,
        default=DEFAULT_DELIVERY,
        help=f"delivery.json path (default: {DEFAULT_DELIVERY})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        output = capture(args.delivery.resolve())
    except CaptureError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
