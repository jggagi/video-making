#!/usr/bin/env python3
"""Collect encoded-frame and audio evidence for the EP06 exports.

This script records measurements and images only. It does not run the skill's
strict full-file decode, and it never marks human review or device playback as
complete.
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


PROJECT_DIR = Path(__file__).resolve().parent.parent
DELIVERY_DIR = PROJECT_DIR.parent
MANIFEST_PATH = DELIVERY_DIR / "delivery.json"
TIMELINE_PATH = PROJECT_DIR / "timeline.json"
REVIEW_DIR = DELIVERY_DIR / "review"
FPS = 60
SAMPLE_RATE = 48_000
EXPECTED_DURATION = 120
EXPECTED_FRAMES = 7200
EXPECTED_SAMPLES_PER_CHANNEL = 5_760_000
SAMPLE_FRAMES = (0, 900, 1500, 2190, 3120, 3900, 4800, 5759, 5760, 5790, 6500, 7100, 7199)
PAIR_GAP = 150
PAIR_STRIDE = 180
PAIR_FRAMES: tuple[tuple[int, int], ...] = ()
EXPECTED_OUTPUTS = {
    "landscape": ("bilibili", 3840, 2160),
    "portrait": ("xiaohongshu", 2160, 3840),
}
LOGICAL_ROI = {
    "landscape": (74, 300, 1772, 550),
    "portrait": (64, 500, 838, 780),
}
LOGICAL_CANVAS_WIDTH = {"landscape": 1920, "portrait": 1080}


class CollectorError(RuntimeError):
    pass


class MissingTool(CollectorError):
    pass


def load_pair_frames() -> tuple[tuple[int, int], ...]:
    try:
        timeline = json.loads(TIMELINE_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CollectorError(f"cannot read project/timeline.json: {exc}") from None
    if not isinstance(timeline, dict) or timeline.get("fps") != FPS or timeline.get("total_frames") != EXPECTED_FRAMES:
        raise CollectorError("project/timeline.json must describe 60 fps and 7200 frames")
    scenes = timeline.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise CollectorError("project/timeline.json scenes must be a non-empty array")

    pairs: list[tuple[int, int]] = []
    cursor = 0
    for index, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            raise CollectorError(f"project/timeline.json scene {index} must be an object")
        start, end = scene.get("startFrame"), scene.get("endFrame")
        if (
            not isinstance(start, int) or isinstance(start, bool)
            or not isinstance(end, int) or isinstance(end, bool)
            or start != cursor or not start < end <= EXPECTED_FRAMES
        ):
            raise CollectorError(f"project/timeline.json scene {index} must continue contiguous frame coverage")
        pair_start = start + 60
        while pair_start + PAIR_GAP < end:
            pairs.append((pair_start, pair_start + PAIR_GAP))
            pair_start += PAIR_STRIDE
        cursor = end
    if cursor != EXPECTED_FRAMES or not pairs:
        raise CollectorError("project/timeline.json scenes must cover frames 0 through 7199 and contain motion pairs")
    return tuple(pairs)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect final-encoded frame, motion-heuristic, and audio evidence for EP06."
    )
    parser.add_argument(
        "--layout", choices=("landscape", "portrait", "both"), default="both",
        help="Collect one output or both outputs (default: both).",
    )
    parser.add_argument("--capture", action="store_true", help="Extract native PNG frames and contact sheets.")
    parser.add_argument("--metrics", action="store_true", help="Measure encoded audio and shared PCM metadata.")
    parser.add_argument("--no-write", action="store_true", help="Print reports without preserving review evidence.")
    return parser.parse_args()


def log(message: str) -> None:
    print(f"[collect-qa] {message}", flush=True)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise MissingTool(f"required executable is unavailable: {name}")
    return path


def run_capture(argv: list[str], phase: str, *, timeout: int | None = None) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(argv, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CollectorError(f"{phase}: could not complete {Path(argv[0]).name}: {exc}") from None
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()[-1200:]
        raise CollectorError(f"{phase}: {Path(argv[0]).name} exited {result.returncode}: {detail or 'no diagnostics'}")
    return result


def safe_path(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise CollectorError(f"delivery.json {label} path is missing")
    candidate = (DELIVERY_DIR / value).resolve()
    try:
        candidate.relative_to(DELIVERY_DIR.resolve())
    except ValueError:
        raise CollectorError(f"delivery.json {label} path escapes the delivery folder") from None
    return candidate


def safe_project_path(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise CollectorError(f"delivery.json {label} project path is missing")
    relative = value.removeprefix("project/")
    if relative.startswith("/") or any(part in ("", ".", "..") for part in Path(relative).parts):
        raise CollectorError(f"delivery.json {label} is not a safe project-relative path")
    candidate = (PROJECT_DIR / relative).resolve()
    try:
        candidate.relative_to(PROJECT_DIR.resolve())
    except ValueError:
        raise CollectorError(f"delivery.json {label} path escapes the project folder") from None
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
    if manifest.get("slug") != DELIVERY_DIR.name:
        raise CollectorError(f"delivery.json slug must match work folder name ({DELIVERY_DIR.name})")
    actual = (manifest.get("duration_seconds"), manifest.get("fps"), manifest.get("total_frames"))
    if actual != (EXPECTED_DURATION, FPS, EXPECTED_FRAMES):
        raise CollectorError(f"delivery.json timing must be 120 seconds, 60 fps and 7200 frames; got {actual}")
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
        configs[layout] = {
            "media": media, "width": width, "height": height, "manifest_key": key,
            "expected_frames": EXPECTED_FRAMES,
        }
    return configs, manifest, missing


def ffprobe_media(ffprobe: str, media: Path) -> dict[str, Any]:
    result = run_capture(
        [ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(media)],
        f"ffprobe {media.name}", timeout=60,
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


def validate_probe(probe: dict[str, Any], *, layout: str, config: dict[str, Any]) -> dict[str, bool]:
    video, audio = probe["video"], probe["audio"]
    video_duration = number_or_none(video.get("duration"))
    audio_duration = number_or_none(audio.get("duration"))
    container_duration = number_or_none(probe["format"].get("duration"))
    checks = {
        "dimensions": (video.get("width"), video.get("height")) == (config["width"], config["height"]),
        "fps_60": video.get("avg_frame_rate") == "60/1" or video.get("r_frame_rate") == "60/1",
        "frame_count_7200": video.get("nb_frames") in ("7200", 7200),
        "pixel_format_yuv420p": video.get("pix_fmt") == "yuv420p",
        "colorspace_bt709": video.get("color_space") == "bt709",
        "color_primaries_bt709": video.get("color_primaries") == "bt709",
        "color_transfer_bt709": video.get("color_transfer") == "bt709",
        "audio_aac": audio.get("codec_name") == "aac",
        "audio_48khz": audio.get("sample_rate") == str(SAMPLE_RATE),
        "audio_stereo": audio.get("channels") == 2,
        "video_duration_exact_120s": video_duration is not None and abs(video_duration - EXPECTED_DURATION) <= 0.001,
        "audio_duration_within_50ms_of_120s": audio_duration is not None and abs(audio_duration - EXPECTED_DURATION) <= 0.05,
        "container_duration_within_50ms_of_120s": container_duration is not None and abs(container_duration - EXPECTED_DURATION) <= 0.05,
    }
    if not all(checks.values()):
        failures = [f"{layout} ffprobe check failed: {name}" for name, passed in checks.items() if not passed]
        raise CollectorError("; ".join(failures))
    probe["metadata_checks"] = checks
    return checks


def number_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def image_modules() -> tuple[Any, ...]:
    try:
        from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageStat
    except ImportError:
        raise MissingTool("Pillow is unavailable; use an existing Pillow environment, do not install dependencies here") from None
    return Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageStat


def ffmpeg_selection(indexes: tuple[int, ...] | list[int]) -> str:
    return "+".join(f"eq(n\\,{index})" for index in indexes)


def unique_pair_frames() -> tuple[int, ...]:
    return tuple(sorted({frame for pair in PAIR_FRAMES for frame in pair}))


def roi_pixels(layout: str) -> tuple[int, int, int, int]:
    x, y, width, height = LOGICAL_ROI[layout]
    scale = EXPECTED_OUTPUTS[layout][1] / LOGICAL_CANVAS_WIDTH[layout]
    return tuple(round(value * scale) for value in (x, y, width, height))


def extract_evidence_frames(
    ffmpeg: str, media: Path, layout: str, temp_dir: Path,
) -> tuple[dict[int, Path], dict[int, Path]]:
    representative_selection = ffmpeg_selection(SAMPLE_FRAMES)
    pair_indexes = unique_pair_frames()
    pair_selection = ffmpeg_selection(pair_indexes)
    x, y, width, height = roi_pixels(layout)
    graph = (
        f"[0:v:0]split=2[representative_input][pair_input];"
        f"[representative_input]select={representative_selection},setpts=N/FRAME_RATE/TB[representatives];"
        f"[pair_input]select={pair_selection},crop={width}:{height}:{x}:{y},scale=640:-1[pairs]"
    )
    representative_pattern = temp_dir / "native-%04d.png"
    pair_pattern = temp_dir / "pair-%02d.jpg"
    run_capture(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(media),
         "-filter_complex", graph,
         "-map", "[representatives]", "-fps_mode:v:0", "passthrough", "-start_number", "0",
         "-compression_level", "6", str(representative_pattern),
         "-map", "[pairs]", "-fps_mode:v:0", "passthrough", "-start_number", "0",
         "-q:v", "3", str(pair_pattern)],
        f"representative frame capture {media.name}", timeout=1800,
    )
    native_paths = sorted(temp_dir.glob("native-*.png"))
    pair_paths = sorted(temp_dir.glob("pair-*.jpg"))
    if len(native_paths) != len(SAMPLE_FRAMES):
        raise CollectorError(f"frame extraction returned {len(native_paths)} native frames; expected {len(SAMPLE_FRAMES)}")
    if len(pair_paths) != len(pair_indexes):
        raise CollectorError(f"frame extraction returned {len(pair_paths)} pair frames; expected {len(pair_indexes)}")
    return dict(zip(SAMPLE_FRAMES, native_paths, strict=True)), dict(zip(pair_indexes, pair_paths, strict=True))


def open_rgb(path: Path, image_module: Any) -> Any:
    try:
        with image_module.open(path) as image:
            return image.convert("RGB")
    except OSError as exc:
        raise CollectorError(f"cannot open captured frame {path.name}: {exc}") from None


def frame_contact_sheet(
    paths: dict[int, Path], *, layout: str, target: Path, modules: tuple[Any, ...],
) -> None:
    Image, _, ImageDraw, _, ImageFont, _ = modules
    tile_width = 480 if layout == "landscape" else 360
    columns = 4 if layout == "landscape" else 3
    first = open_rgb(paths[SAMPLE_FRAMES[0]], Image)
    tile_height = round(first.height * tile_width / first.width)
    card_height = tile_height + 30
    rows = math.ceil(len(SAMPLE_FRAMES) / columns)
    sheet = Image.new("RGB", (columns * tile_width, rows * card_height), (12, 15, 24))
    font = ImageFont.load_default()
    for position, frame in enumerate(SAMPLE_FRAMES):
        x = position % columns * tile_width
        y = position // columns * card_height
        image = open_rgb(paths[frame], Image).resize((tile_width, tile_height), Image.Resampling.LANCZOS)
        sheet.paste(image, (x, y))
        draw = ImageDraw.Draw(sheet)
        draw.rectangle((x, y + tile_height, x + tile_width, y + card_height), fill=(0, 0, 0))
        draw.text((x + 5, y + tile_height + 6), f"frame {frame} | {frame / FPS:.2f}s", fill=(255, 255, 255), font=font)
    sheet.save(target, format="JPEG", quality=88, optimize=True)


def edge_difference(before_path: Path, after_path: Path, modules: tuple[Any, ...]) -> float:
    Image, ImageChops, _, ImageFilter, _, ImageStat = modules
    before = open_rgb(before_path, Image).convert("L").filter(ImageFilter.FIND_EDGES)
    after = open_rgb(after_path, Image).convert("L").filter(ImageFilter.FIND_EDGES)
    if before.size != after.size:
        raise CollectorError("motion-pair ROI dimensions differ")
    return float(ImageStat.Stat(ImageChops.difference(before, after)).mean[0])


def pair_contact_sheet(
    pair_paths: dict[int, Path], *, layout: str, target: Path, modules: tuple[Any, ...],
) -> list[dict[str, Any]]:
    Image, _, ImageDraw, _, ImageFont, _ = modules
    columns = 3
    first_frame = PAIR_FRAMES[0][0]
    first = open_rgb(pair_paths[first_frame], Image)
    tile_width, tile_height = first.size
    card_width, card_height = tile_width * 2, tile_height + 34
    rows = math.ceil(len(PAIR_FRAMES) / columns)
    sheet = Image.new("RGB", (columns * card_width, rows * card_height), (12, 15, 24))
    font = ImageFont.load_default()
    pairs: list[dict[str, Any]] = []
    for position, (start, end) in enumerate(PAIR_FRAMES):
        x = position % columns * card_width
        y = position // columns * card_height
        before = open_rgb(pair_paths[start], Image)
        after = open_rgb(pair_paths[end], Image)
        sheet.paste(before, (x, y))
        sheet.paste(after, (x + tile_width, y))
        delta = edge_difference(pair_paths[start], pair_paths[end], modules)
        pairs.append({
            "start_frame": start, "end_frame": end,
            "start_seconds": start / FPS, "end_seconds": end / FPS,
            "pair_gap_frames": end - start,
            "edge_difference_mean": delta,
        })
        draw = ImageDraw.Draw(sheet)
        draw.rectangle((x, y + tile_height, x + card_width, y + card_height), fill=(0, 0, 0))
        draw.text((x + 5, y + tile_height + 7),
                  f"{start / FPS:.1f}s -> {end / FPS:.1f}s | edgeΔ={delta:.2f}",
                  fill=(255, 255, 255), font=font)
    sheet.save(target, format="JPEG", quality=86, optimize=True)
    return pairs


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def measure_loudness(ffmpeg: str, media: Path) -> dict[str, Any]:
    result = run_capture(
        [ffmpeg, "-hide_banner", "-nostats", "-i", str(media), "-map", "0:a:0",
         "-af", "ebur128=peak=true", "-f", "null", "-"],
        f"ebur128 {media.name}", timeout=900,
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


def audio_packet_sha256(ffmpeg: str, media: Path) -> dict[str, str]:
    result = run_capture(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(media), "-map", "0:a:0",
         "-c", "copy", "-f", "streamhash", "-hash", "sha256", "-"],
        f"AAC packet SHA-256 {media.name}", timeout=180,
    )
    raw = (result.stdout + result.stderr).decode("ascii", errors="replace")
    match = re.search(r"SHA256=([0-9a-fA-F]{64})", raw)
    if match is None:
        raise CollectorError(f"FFmpeg did not return an AAC packet SHA-256 for {media.name}")
    return {"algorithm": "sha256", "value": match.group(1).lower()}


def inspect_pcm_master(manifest: dict[str, Any]) -> dict[str, Any]:
    audio = manifest.get("audio")
    master_value = audio.get("master") if isinstance(audio, dict) else None
    master = safe_project_path(master_value, "audio.master")
    if not master.is_file():
        raise CollectorError(f"shared PCM master is missing: {master.relative_to(DELIVERY_DIR).as_posix()}")
    try:
        with wave.open(str(master), "rb") as pcm:
            actual = (
                pcm.getframerate(), pcm.getnchannels(), pcm.getnframes(),
                pcm.getsampwidth(), pcm.getcomptype(),
            )
    except (OSError, wave.Error) as exc:
        raise CollectorError(f"cannot inspect shared PCM master: {exc}") from None
    digest = sha256_file(master)
    return {
        "path": master.relative_to(DELIVERY_DIR).as_posix(),
        "sample_rate": actual[0], "channels": actual[1], "samples_per_channel": actual[2],
        "sample_width_bytes": actual[3], "compression_type": actual[4], "sha256": digest,
        "expected": {"sample_rate": SAMPLE_RATE, "channels": 2,
                     "samples_per_channel": EXPECTED_SAMPLES_PER_CHANNEL,
                     "sample_width_bytes": 2, "compression_type": "NONE"},
        "metadata_matches_expected": actual == (SAMPLE_RATE, 2, EXPECTED_SAMPLES_PER_CHANNEL, 2, "NONE"),
    }


def collect_capture(
    *, layout: str, config: dict[str, Any], ffmpeg: str, ffprobe: str,
    stage: Path, modules: tuple[Any, ...], probe: dict[str, Any],
) -> dict[str, Any]:
    media: Path = config["media"]
    native_files: list[str] = []
    contact_name = f"encoded-{layout}-contact-sheet.jpg"
    pair_name = f"encoded-{layout}-pair-contact-sheet.jpg"
    with tempfile.TemporaryDirectory(prefix=f"ep06-{layout}-frames-") as temp_name:
        temp_dir = Path(temp_name)
        native, pair_images = extract_evidence_frames(ffmpeg, media, layout, temp_dir)
        for frame, path in native.items():
            with modules[0].open(path) as image:
                if image.size != (config["width"], config["height"]):
                    raise CollectorError(f"representative frame {frame} is {image.width}x{image.height}; expected native dimensions")
            name = f"encoded-{layout}-native-frame-{frame:04d}.png"
            shutil.copyfile(path, stage / name)
            native_files.append(name)
        frame_contact_sheet(native, layout=layout, target=stage / contact_name, modules=modules)
        pairs = pair_contact_sheet(pair_images, layout=layout, target=stage / pair_name, modules=modules)

    video = probe["video"]
    return {
        "representative_frames": {
            "method": "selected frames decoded from the final encoded MP4 with FFmpeg; lossless native-resolution PNGs",
            "frame_indexes": list(SAMPLE_FRAMES),
            "contact_sheet_path": f"review/{contact_name}",
            "contact_tile_width_px": 480 if layout == "landscape" else 360,
            "full_native_frame_paths": [f"review/{name}" for name in native_files],
        },
        "motion_heuristic": {
            "method": "mean absolute difference between Pillow FIND_EDGES grayscale crops from the final encoded MP4; pairs are sampled within every timeline scene, inset 60 frames and advanced by 180 frames, with the configured ROI omitting HUD/subtitle bands",
            "logical_roi_xywh": list(LOGICAL_ROI[layout]),
            "native_roi_xywh": list(roi_pixels(layout)),
            "pairs": pairs,
            "pair_contact_sheet_path": f"review/{pair_name}",
            "pair_gap_frames": PAIR_GAP,
            "timeline_coverage": {"scene_range_start_frame": 0, "scene_range_end_frame_exclusive": EXPECTED_FRAMES,
                                  "first_pair_start_frame": PAIR_FRAMES[0][0],
                                  "last_pair_end_frame": PAIR_FRAMES[-1][1],
                                  "pair_count": len(PAIR_FRAMES), "pair_gap_frames": PAIR_GAP,
                                  "pair_start_stride_frames": PAIR_STRIDE,
                                  "sampling": "for each timeline scene, start at scene.startFrame + 60 and advance 180 frames; keep pairs whose end frame is strictly before scene.endFrame"},
            "limitation": "Nonzero edge differences are a heuristic for pixel changes only; they do not prove meaningful motion, validate scene semantics, or satisfy human review.",
        },
        "native_frame_metadata": {"width": video.get("width"), "height": video.get("height"), "frame_count_reported": video.get("nb_frames")},
    }


def collect_metrics(*, layout: str, config: dict[str, Any], ffmpeg: str, probe: dict[str, Any]) -> dict[str, Any]:
    media: Path = config["media"]
    video, audio = probe["video"], probe["audio"]
    return {
        "ffprobe": {
            "format_name": probe["format"].get("format_name"),
            "container_duration_seconds": number_or_none(probe["format"].get("duration")),
            "video_duration_seconds": number_or_none(video.get("duration")),
            "audio_duration_seconds": number_or_none(audio.get("duration")),
            "video": {key: video.get(key) for key in (
                "codec_name", "width", "height", "avg_frame_rate", "r_frame_rate", "nb_frames",
                "pix_fmt", "color_space", "color_primaries", "color_transfer",
            )},
            "audio": {key: audio.get(key) for key in ("codec_name", "sample_rate", "channels", "channel_layout", "duration")},
            "metadata_checks": probe["metadata_checks"],
        },
        "encoded_audio_loudness": measure_loudness(ffmpeg, media),
        "aac_packet_sha256": audio_packet_sha256(ffmpeg, media),
    }


def main() -> int:
    args = parse_args()
    if not args.capture and not args.metrics:
        args.capture = True
        args.metrics = True
    layouts = ["landscape", "portrait"] if args.layout == "both" else [args.layout]
    global PAIR_FRAMES
    try:
        PAIR_FRAMES = load_pair_frames()
    except CollectorError as exc:
        report = {"schema_version": 1, "status": "FAIL", "error": str(exc), "acceptance_status": "NOT_EVALUATED"}
        if not args.no_write:
            write_json(REVIEW_DIR / "encoded-qa-summary.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1
    try:
        configs, manifest, missing = load_manifest(layouts)
    except CollectorError as exc:
        report = {"schema_version": 1, "status": "FAIL", "error": str(exc), "acceptance_status": "NOT_EVALUATED"}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    results: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    incomplete: list[str] = list(missing)
    ffmpeg: str | None = None
    ffprobe: str | None = None
    modules: tuple[Any, ...] | None = None
    if configs:
        try:
            ffmpeg = require_tool("ffmpeg")
            ffprobe = require_tool("ffprobe")
            if args.capture:
                modules = image_modules()
        except MissingTool as exc:
            report = {"schema_version": 1, "status": "BLOCKED", "reason": str(exc), "incomplete": incomplete,
                      "acceptance_status": "NOT_EVALUATED"}
            if not args.no_write:
                write_json(REVIEW_DIR / "encoded-qa-summary.json", report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 1

    pcm_master: dict[str, Any] | None = None
    if args.metrics:
        try:
            pcm_master = inspect_pcm_master(manifest)
            if not pcm_master["metadata_matches_expected"]:
                failures.append("shared PCM master metadata does not match exact 48kHz stereo 120s PCM requirements")
        except (CollectorError, OSError, wave.Error) as exc:
            incomplete.append(str(exc))

    stage_parent = None if args.no_write else REVIEW_DIR
    if not args.no_write:
        REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix=".ep06-qa-stage-", dir=stage_parent) as stage_name:
            stage = Path(stage_name)
            for layout, config in configs.items():
                try:
                    assert ffprobe is not None and ffmpeg is not None
                    probe = ffprobe_media(ffprobe, config["media"])
                    validate_probe(probe, layout=layout, config=config)
                    result: dict[str, Any] = {
                        "schema_version": 1,
                        "status": "evidence_collected",
                        "layout": layout,
                        "media_path": config["media"].relative_to(DELIVERY_DIR).as_posix(),
                        "expected": {
                            "width": config["width"], "height": config["height"],
                            "fps": FPS, "duration_seconds": EXPECTED_DURATION, "total_frames": EXPECTED_FRAMES,
                        },
                    }
                    if args.metrics:
                        result.update(collect_metrics(layout=layout, config=config, ffmpeg=ffmpeg, probe=probe))
                    if args.capture:
                        assert modules is not None
                        result.update(collect_capture(layout=layout, config=config, ffmpeg=ffmpeg, ffprobe=ffprobe,
                                                      stage=stage, modules=modules, probe=probe))
                    result["acceptance_status"] = "NOT_EVALUATED"
                    result["created_at_utc"] = datetime.now(timezone.utc).isoformat()
                    results[layout] = result
                except CollectorError as exc:
                    failures.append(f"{layout}: {exc}")

            if args.metrics and "landscape" in results and "portrait" in results:
                left = results["landscape"].get("aac_packet_sha256", {}).get("value")
                right = results["portrait"].get("aac_packet_sha256", {}).get("value")
                if left and right:
                    shared = {"same_aac_packet_sha256": left == right, "landscape_sha256": left, "portrait_sha256": right}
                    for result in results.values():
                        result["shared_aac_identity"] = shared
                    if left != right:
                        failures.append("encoded AAC packet SHA-256 differs between landscape and portrait exports")

            for layout, result in results.items():
                if pcm_master is not None:
                    result["shared_pcm_master"] = pcm_master
                (stage / f"encoded-qa-{layout}.json").write_text(
                    json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
                )
            if not args.no_write:
                for path in sorted(item for item in stage.iterdir() if item.is_file()):
                    os.replace(path, REVIEW_DIR / path.name)
    except OSError as exc:
        failures.append(f"cannot stage or publish review evidence: {exc}")

    if args.metrics and len(results) < len(layouts):
        add = "shared AAC packet identity requires both encoded output files"
        if add not in incomplete and not failures:
            incomplete.append(add)
    status = "FAIL" if failures else "INCOMPLETE" if incomplete or len(results) != len(layouts) else "evidence_collected"
    summary = {
        "schema_version": 1,
        "status": status,
        "requested_layouts": layouts,
        "collected_layouts": sorted(results),
        "missing_media": missing,
        "failures": failures,
        "incomplete": incomplete,
        "shared_pcm_master": pcm_master,
        "per_layout_reports": [f"review/encoded-qa-{layout}.json" for layout in sorted(results)],
        "acceptance_status": "NOT_EVALUATED",
        "limitations": [
            "AAC loudness and packet hashes are measurements; they do not prove PCM identity without the recorded master hash/sample count.",
            "Frame differences are visual heuristics and do not establish meaningful continuous motion.",
            "This script does not run strict full-file decode, human listening, human visual review, or target-device playback.",
        ],
    }
    if not args.no_write:
        write_json(REVIEW_DIR / "encoded-qa-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if failures else 2 if status == "INCOMPLETE" else 0


if __name__ == "__main__":
    raise SystemExit(main())
