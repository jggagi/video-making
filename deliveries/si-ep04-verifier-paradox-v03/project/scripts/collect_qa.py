#!/usr/bin/env python3
"""Collect compact encoded-frame and audio evidence for the EP04 exports.

This collector records measurements and visual samples. It does not make a
human acceptance, listening, or full-motion claim.
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
SAMPLE_FRAMES = (360, 960, 1500, 2190, 3040, 3900, 4590, 5500, 5740, 5760, 5790, 6090, 6340, 6500, 6720, 6960, 7100, 7199)
FULL_NATIVE_FRAMES = (6500, 7100)
PAIR_GAP = 150
FPS = 60
SAMPLE_RATE = 48_000
EXPECTED_OUTPUTS = {
    "landscape": ("bilibili", 3840, 2160),
    "portrait": ("xiaohongshu", 2160, 3840),
}
# Coordinates are specified in the project's half-resolution logical canvas
# and scaled to its native 4K output. This keeps motion evidence in the drawn
# stage while omitting the overlay HUD and burned-in captions.
ROI_PIXELS = {
    "landscape": (200, 600, 3640, 1760),
    "portrait": (130, 880, 1830, 2580),
}


class CollectorError(RuntimeError):
    pass


class MissingTool(CollectorError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect encoded-frame, motion-heuristic, and audio evidence from EP04 MP4s."
    )
    parser.add_argument(
        "--layout", choices=("landscape", "portrait", "both"), default="both",
        help="Collect one output or both outputs (default: both).",
    )
    parser.add_argument(
        "--no-write", action="store_true",
        help="Print results without writing reports or image evidence.",
    )
    return parser.parse_args()


def log(message: str) -> None:
    print(f"[collect-qa] {message}", flush=True)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise MissingTool(f"required executable is unavailable: {name}")
    return path


def run_capture(argv: list[str], phase: str) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(argv, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        raise CollectorError(f"{phase}: could not start {Path(argv[0]).name}: {exc}") from None
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()[-1200:]
        raise CollectorError(
            f"{phase}: {Path(argv[0]).name} exited {result.returncode}: {detail or 'no diagnostics'}"
        )
    return result


def safe_path(relative: Any, label: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise CollectorError(f"delivery.json {label} path is missing")
    candidate = (DELIVERY_DIR / relative).resolve()
    try:
        candidate.relative_to(DELIVERY_DIR.resolve())
    except ValueError:
        raise CollectorError(f"delivery.json {label} path escapes the delivery folder") from None
    return candidate


def load_manifest(layouts: list[str]) -> tuple[dict[str, dict[str, Any]], dict[str, Any], list[str]]:
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise CollectorError(f"delivery manifest is missing: {MANIFEST_PATH}") from None
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CollectorError(f"cannot read delivery.json: {exc}") from None
    if not isinstance(manifest, dict):
        raise CollectorError("delivery.json must contain an object")
    if (manifest.get("duration_seconds"), manifest.get("fps"), manifest.get("total_frames")) != (120, 60, 7200):
        raise CollectorError("delivery.json timing must specify 120 seconds, 60 fps, and 7200 frames")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        raise CollectorError("delivery.json outputs must be an object")

    configs: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for layout in layouts:
        key, width, height = EXPECTED_OUTPUTS[layout]
        output = outputs.get(key)
        if not isinstance(output, dict):
            missing.append(f"delivery.json outputs.{key} is missing")
            continue
        media = safe_path(output.get("path"), f"outputs.{key}")
        if (output.get("width"), output.get("height")) != (width, height):
            raise CollectorError(f"delivery.json outputs.{key} must declare {width}x{height}")
        if not media.is_file():
            missing.append(f"final {layout} MP4 is missing: {media.relative_to(DELIVERY_DIR).as_posix()}")
            continue
        configs[layout] = {"media": media, "width": width, "height": height, "manifest_key": key}
    return configs, manifest, missing


def ffprobe_media(ffprobe: str, media: Path) -> dict[str, Any]:
    result = run_capture(
        [ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(media)],
        f"ffprobe {media.name}",
    )
    try:
        probe = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise CollectorError(f"ffprobe returned invalid JSON for {media.name}") from None
    if not isinstance(probe, dict) or not isinstance(probe.get("streams"), list):
        raise CollectorError(f"ffprobe returned incomplete metadata for {media.name}")
    video = next((stream for stream in probe["streams"] if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in probe["streams"] if stream.get("codec_type") == "audio"), None)
    if video is None or audio is None:
        raise CollectorError(f"{media.name} must contain both video and audio streams")
    return {"format": probe.get("format", {}), "video": video, "audio": audio}


def validate_probe(probe: dict[str, Any], *, layout: str, config: dict[str, Any]) -> list[str]:
    video = probe["video"]
    failures: list[str] = []
    checks = {
        "dimensions": (video.get("width"), video.get("height")) == (config["width"], config["height"]),
        "fps_60": video.get("avg_frame_rate") == "60/1" or video.get("r_frame_rate") == "60/1",
        "pixel_format_yuv420p": video.get("pix_fmt") == "yuv420p",
        "colorspace_bt709": video.get("color_space") == "bt709",
        "color_primaries_bt709": video.get("color_primaries") == "bt709",
        "color_transfer_bt709": video.get("color_transfer") == "bt709",
    }
    for key, passed in checks.items():
        if not passed:
            failures.append(f"{layout} ffprobe check failed: {key}")
    probe["expected_metadata_checks"] = checks
    return failures


def frame_indexes() -> tuple[tuple[int, ...], list[tuple[int, int, str]], str]:
    indexes = set(SAMPLE_FRAMES)
    timeline = PROJECT_DIR / "timeline.json"
    intervals: list[tuple[int, int, str]] = []
    source = "timeline.json"
    if timeline.is_file():
        try:
            data = json.loads(timeline.read_text(encoding="utf-8"))
            shots = data.get("shots") if isinstance(data, dict) else None
            if not isinstance(shots, list):
                raise CollectorError("timeline.json shots must be an array")
            for index, shot in enumerate(shots, start=1):
                if not isinstance(shot, dict):
                    raise CollectorError(f"timeline shot {index} must be an object")
                start, end = shot.get("startFrame"), shot.get("endFrame")
                if type(start) is not int or type(end) is not int or not 0 <= start < end <= 7200:
                    raise CollectorError(f"timeline shot {index} has invalid frame bounds")
                if end - start > 5 * FPS and start + PAIR_GAP < end:
                    intervals.append((start, end, str(shot.get("purpose", f"shot-{index}"))))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise CollectorError(f"cannot read timeline.json: {exc}") from None
    else:
        source = "segments.json fallback"
        segments_path = PROJECT_DIR / "segments.json"
        if segments_path.is_file():
            try:
                data = json.loads(segments_path.read_text(encoding="utf-8"))
                segments = data.get("segments") if isinstance(data, dict) else None
                if isinstance(segments, list):
                    for segment in segments:
                        if isinstance(segment, dict):
                            start, end = segment.get("startFrame"), segment.get("endFrame")
                            if type(start) is int and type(end) is int and end - start > 5 * FPS and start + PAIR_GAP < end:
                                intervals.append((start, end, str(segment.get("id", "segment"))))
            except (OSError, UnicodeError, json.JSONDecodeError):
                pass
    expanded: list[tuple[int, int, str]] = []
    for start, end, label in intervals:
        # Cover long holds internally as well as their entering state.
        pair_starts = set(range(start, end - PAIR_GAP, 300))
        pair_starts.add((start + end - PAIR_GAP) // 2)
        for at in sorted(pair_starts):
            expanded.append((at, end, label))
            indexes.add(at)
            indexes.add(at + PAIR_GAP)
    intervals = expanded
    if not intervals:
        raise CollectorError("no visual subscenes longer than 5 seconds are available for motion pairs")
    return tuple(sorted(indexes)), intervals, source


def extract_frames(ffmpeg: str, media: Path, indexes: tuple[int, ...], temp_dir: Path) -> dict[int, Path]:
    selection = "+".join(f"eq(n\\,{frame})" for frame in indexes)
    pattern = temp_dir / "frame-%03d.jpg"
    run_capture(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-xerror", "-y", "-i", str(media),
         "-map", "0:v:0", "-an", "-vf", f"select={selection}", "-fps_mode", "passthrough",
         "-q:v", "3", "-start_number", "0", str(pattern)],
        f"frame extraction {media.name}",
    )
    paths = sorted(temp_dir.glob("frame-*.jpg"))
    if len(paths) != len(indexes):
        raise CollectorError(f"frame extraction returned {len(paths)} frames; expected {len(indexes)}")
    return dict(zip(indexes, paths, strict=True))


def image_modules() -> tuple[Any, Any, Any, Any, Any]:
    try:
        from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageStat
    except ImportError:
        raise MissingTool("Pillow is unavailable; install no dependency here, use an existing Pillow environment") from None
    return Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageStat


def open_rgb(path: Path, image_module: Any) -> Any:
    try:
        with image_module.open(path) as image:
            return image.convert("RGB")
    except OSError as exc:
        raise CollectorError(f"cannot open extracted frame {path.name}: {exc}") from None


def frame_contact_sheet(
    paths: dict[int, Path], *, layout: str, target: Path,
    Image: Any, ImageDraw: Any, ImageFont: Any,
) -> None:
    width = 480 if layout == "landscape" else 360
    columns = 4 if layout == "landscape" else 3
    sample_paths = {frame: paths[frame] for frame in SAMPLE_FRAMES}
    first = open_rgb(sample_paths[SAMPLE_FRAMES[0]], Image)
    thumb_height = round(first.height * width / first.width)
    card_height = thumb_height + 28
    rows = math.ceil(len(sample_paths) / columns)
    sheet = Image.new("RGB", (columns * width, rows * card_height), (12, 15, 24))
    font = ImageFont.load_default()
    for position, (frame, path) in enumerate(sorted(sample_paths.items())):
        image = open_rgb(path, Image).resize((width, thumb_height), Image.Resampling.LANCZOS)
        x = (position % columns) * width
        y = (position // columns) * card_height
        sheet.paste(image, (x, y))
        draw = ImageDraw.Draw(sheet)
        draw.rectangle((x, y + thumb_height, x + width, y + card_height), fill=(0, 0, 0))
        draw.text((x + 5, y + thumb_height + 6), f"frame {frame} | {frame / FPS:.2f}s", fill=(255, 255, 255), font=font)
    sheet.save(target, format="JPEG", quality=86, optimize=True)


def pair_contact_sheet(
    pairs: list[dict[str, Any]], paths: dict[int, Path], *, layout: str, target: Path,
    Image: Any, ImageDraw: Any, ImageFont: Any,
) -> None:
    width = 240 if layout == "landscape" else 180
    first = open_rgb(paths[pairs[0]["start_frame"]], Image)
    height = round(first.height * width / first.width)
    card_width, card_height = width * 2, height + 28
    columns = 3
    sheet = Image.new("RGB", (columns * card_width, math.ceil(len(pairs) / columns) * card_height), (12, 15, 24))
    font = ImageFont.load_default()
    for position, pair in enumerate(pairs):
        y = (position // columns) * card_height
        x = (position % columns) * card_width
        for offset, frame in ((0, pair["start_frame"]), (width, pair["end_frame"])):
            image = open_rgb(paths[frame], Image).resize((width, height), Image.Resampling.LANCZOS)
            sheet.paste(image, (x + offset, y))
        draw = ImageDraw.Draw(sheet)
        draw.rectangle((x, y + height, x + card_width, y + card_height), fill=(0, 0, 0))
        draw.text(
            (x + 4, y + height + 6),
            f"{pair['start_frame']} -> {pair['end_frame']} edgeΔ={pair['edge_difference_mean']:.2f}",
            fill=(255, 255, 255), font=font,
        )
    sheet.save(target, format="JPEG", quality=84, optimize=True)


def edge_difference(
    before_path: Path, after_path: Path, *, layout: str,
    Image: Any, ImageChops: Any, ImageFilter: Any, ImageStat: Any,
) -> float:
    left, top, right, bottom = ROI_PIXELS[layout]

    def field(path: Path) -> Any:
        image = open_rgb(path, Image)
        if not (0 <= left < right <= image.width and 0 <= top < bottom <= image.height):
            raise CollectorError(f"{layout} stage ROI is outside the encoded frame")
        cropped = image.crop((left, top, right, bottom))
        cropped.thumbnail((640, 480), Image.Resampling.LANCZOS)
        return cropped.convert("L").filter(ImageFilter.FIND_EDGES)

    a, b = field(before_path), field(after_path)
    return float(ImageStat.Stat(ImageChops.difference(a, b)).mean[0])


def measure_loudness(ffmpeg: str, media: Path) -> dict[str, Any]:
    result = run_capture(
        [ffmpeg, "-hide_banner", "-nostats", "-i", str(media), "-map", "0:a:0",
         "-af", "ebur128=peak=true", "-f", "null", "-"],
        f"ebur128 {media.name}",
    )
    output = result.stderr.decode("utf-8", errors="replace")
    integrated = re.search(r"(?m)^\s*I:\s*(-?\d+(?:\.\d+)?)\s+LUFS\s*$", output)
    true_peak = re.search(r"(?m)^\s*True peak:\s*(-?\d+(?:\.\d+)?)\s+dBTP\s*$", output)
    if true_peak is None:
        true_peak = re.search(r"True peak:\s*\n\s*Peak:\s*(-?\d+(?:\.\d+)?)\s+dBFS", output)
    if integrated is None or true_peak is None:
        raise CollectorError(f"ebur128 did not report integrated loudness and true peak for {media.name}")
    return {
        "measurement": "FFmpeg ebur128=peak=true on the encoded MP4 audio stream",
        "integrated_lufs": float(integrated.group(1)),
        "true_peak_dbTP": float(true_peak.group(1)),
    }


def audio_packet_sha256(ffmpeg: str, media: Path) -> dict[str, Any]:
    result = run_capture(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(media), "-map", "0:a:0",
         "-c", "copy", "-f", "streamhash", "-hash", "sha256", "-"],
        f"audio packet SHA-256 {media.name}",
    )
    text = (result.stdout + result.stderr).decode("ascii", errors="replace")
    match = re.search(r"SHA256=([0-9a-fA-F]{64})", text)
    if match is None:
        raise CollectorError(f"FFmpeg did not return an audio packet SHA-256 for {media.name}")
    return {"algorithm": "sha256", "value": match.group(1).lower()}


def collect_layout(
    *, layout: str, config: dict[str, Any], manifest: dict[str, Any], ffmpeg: str, ffprobe: str,
    stage: Path, modules: tuple[Any, ...], indexes: tuple[int, ...], intervals: list[tuple[int, int, str]],
    interval_source: str,
) -> dict[str, Any]:
    Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageStat = modules
    media: Path = config["media"]
    log(f"collecting {layout}: {media.name}")
    probe = ffprobe_media(ffprobe, media)
    metadata_failures = validate_probe(probe, layout=layout, config=config)
    if metadata_failures:
        raise CollectorError("; ".join(metadata_failures))

    with tempfile.TemporaryDirectory(prefix=f"ep04-{layout}-frames-") as temp_name:
        frame_paths = extract_frames(ffmpeg, media, indexes, Path(temp_name))
        for frame, path in frame_paths.items():
            with Image.open(path) as image:
                if image.size != (config["width"], config["height"]):
                    raise CollectorError(f"frame {frame} has dimensions {image.width}x{image.height}")

        pairs: list[dict[str, Any]] = []
        for start, end, label in intervals:
            later = start + PAIR_GAP
            pairs.append({
                "subscene": label,
                "start_frame": start,
                "end_frame": later,
                "pair_gap_frames": PAIR_GAP,
                "edge_difference_mean": edge_difference(
                    frame_paths[start], frame_paths[later], layout=layout,
                    Image=Image, ImageChops=ImageChops, ImageFilter=ImageFilter, ImageStat=ImageStat,
                ),
            })

        contact_name = f"encoded-{layout}-contact-sheet.jpg"
        pair_name = f"encoded-{layout}-pair-contact-sheet.jpg"
        frame_contact_sheet(frame_paths, layout=layout, target=stage / contact_name,
                            Image=Image, ImageDraw=ImageDraw, ImageFont=ImageFont)
        pair_contact_sheet(pairs, frame_paths, layout=layout, target=stage / pair_name,
                           Image=Image, ImageDraw=ImageDraw, ImageFont=ImageFont)
        native_files: list[str] = []
        for frame in FULL_NATIVE_FRAMES:
            name = f"encoded-{layout}-native-frame-{frame:04d}.jpg"
            open_rgb(frame_paths[frame], Image).save(stage / name, format="JPEG", quality=92, optimize=True)
            native_files.append(name)

    loudness = measure_loudness(ffmpeg, media)
    packet_hash = audio_packet_sha256(ffmpeg, media)
    video = probe["video"]
    audio = probe["audio"]
    return {
        "schema_version": 1,
        "status": "evidence_collected",
        "layout": layout,
        "media_path": media.relative_to(DELIVERY_DIR).as_posix(),
        "expected": {
            "width": config["width"], "height": config["height"],
            "fps": FPS, "duration_seconds": manifest["duration_seconds"], "total_frames": manifest["total_frames"],
        },
        "ffprobe": {
            "format_name": probe["format"].get("format_name"),
            "duration_seconds": probe["format"].get("duration"),
            "video": {key: video.get(key) for key in (
                "codec_name", "width", "height", "avg_frame_rate", "r_frame_rate", "nb_frames",
                "pix_fmt", "color_space", "color_primaries", "color_transfer",
            )},
            "audio": {key: audio.get(key) for key in ("codec_name", "sample_rate", "channels", "channel_layout")},
            "metadata_checks": probe["expected_metadata_checks"],
        },
        "loudness": loudness,
        "audio_packet_sha256": packet_hash,
        "representative_frames": {
            "method": "FFmpeg select=eq(n,index) over decoded final MP4 frames",
            "frame_indexes": list(SAMPLE_FRAMES),
            "contact_sheet_path": f"review/{contact_name}",
            "contact_tile_width_px": 480 if layout == "landscape" else 360,
            "full_native_keyframe_paths": [f"review/{name}" for name in native_files],
            "full_native_keyframe_indexes": list(FULL_NATIVE_FRAMES),
        },
        "motion_heuristic": {
            "method": "mean absolute pixel difference between Pillow FIND_EDGES grayscale ROI images, resized to at most 640x480",
            "interval_source": interval_source,
            "roi_pixel_xyxy": list(ROI_PIXELS[layout]),
            "roi_fraction_xyxy": [
                ROI_PIXELS[layout][0] / config["width"],
                ROI_PIXELS[layout][1] / config["height"],
                ROI_PIXELS[layout][2] / config["width"],
                ROI_PIXELS[layout][3] / config["height"],
            ],
            "pairs": pairs,
            "pair_contact_sheet_path": f"review/{pair_name}",
            "content_scope": "Stage-only crop; excludes overlay HUD and captions, while semantic labels drawn inside the diagrams remain included.",
            "limitation": "Numeric edge differences are visual-change heuristics only; nonzero values do not prove meaningful semantic or continuous motion.",
        },
        "acceptance_status": "NOT_EVALUATED",
    }


def main() -> int:
    args = parse_args()
    layouts = ["landscape", "portrait"] if args.layout == "both" else [args.layout]
    try:
        configs, manifest, missing = load_manifest(layouts)
    except CollectorError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    if not args.no_write:
        REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    if not configs:
        report = {
            "schema_version": 1,
            "status": "INCOMPLETE",
            "requested_layouts": layouts,
            "collected_layouts": [],
            "incomplete": missing,
            "acceptance_status": "NOT_EVALUATED",
        }
        if not args.no_write:
            write_json(REVIEW_DIR / "encoded-qa-summary.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    try:
        ffmpeg = require_tool("ffmpeg")
        ffprobe = require_tool("ffprobe")
        modules = image_modules()
        indexes, intervals, interval_source = frame_indexes()
    except MissingTool as exc:
        report = {"schema_version": 1, "status": "BLOCKED", "reason": str(exc), "incomplete": missing}
        if not args.no_write:
            write_json(REVIEW_DIR / "encoded-qa-summary.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1
    except CollectorError as exc:
        report = {"schema_version": 1, "status": "FAIL", "error": str(exc), "incomplete": missing}
        if not args.no_write:
            write_json(REVIEW_DIR / "encoded-qa-summary.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    results: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    try:
        with tempfile.TemporaryDirectory(
            prefix=".ep04-qa-stage-", dir=None if args.no_write else REVIEW_DIR,
        ) as stage_name:
            stage = Path(stage_name)
            for layout in layouts:
                if layout not in configs:
                    continue
                try:
                    results[layout] = collect_layout(
                        layout=layout, config=configs[layout], manifest=manifest,
                        ffmpeg=ffmpeg, ffprobe=ffprobe, stage=stage, modules=modules,
                        indexes=indexes, intervals=intervals, interval_source=interval_source,
                    )
                except CollectorError as exc:
                    failures.append(f"{layout}: {exc}")

            if "landscape" in results and "portrait" in results:
                left = results["landscape"]["audio_packet_sha256"]["value"]
                right = results["portrait"]["audio_packet_sha256"]["value"]
                shared_audio = {"same_encoded_audio_packets": left == right, "landscape_sha256": left, "portrait_sha256": right}
                for result in results.values():
                    result["cross_layout_audio_packet_hash"] = shared_audio
                if left != right:
                    failures.append("encoded audio packet SHA-256 differs between landscape and portrait exports")

            for layout, result in results.items():
                (stage / f"encoded-qa-{layout}.json").write_text(
                    json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
                )
            if not args.no_write:
                for path in sorted(item for item in stage.iterdir() if item.is_file()):
                    os.replace(path, REVIEW_DIR / path.name)
    except OSError as exc:
        print(json.dumps({"status": "FAIL", "error": f"cannot publish review evidence: {exc}"}, ensure_ascii=False, indent=2))
        return 1

    status = "FAIL" if failures else "INCOMPLETE" if missing or len(results) != len(layouts) else "evidence_collected"
    summary = {
        "schema_version": 1,
        "status": status,
        "requested_layouts": layouts,
        "collected_layouts": sorted(results),
        "missing_media": missing,
        "failures": failures,
        "per_layout_reports": [f"review/encoded-qa-{layout}.json" for layout in sorted(results)],
        "acceptance_status": "NOT_EVALUATED",
        "limitations": [
            "Contact sheets and loudness/hash measurements are evidence, not delivery acceptance.",
            "Edge-geometry differences are heuristics; a nonzero value is not proof of meaningful motion.",
            "Human visual review, safe-zone review, and listening remain separate.",
        ],
    }
    if not args.no_write:
        write_json(REVIEW_DIR / "encoded-qa-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if failures else 2 if status == "INCOMPLETE" else 0


if __name__ == "__main__":
    raise SystemExit(main())
