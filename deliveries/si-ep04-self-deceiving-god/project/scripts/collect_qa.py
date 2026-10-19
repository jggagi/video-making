#!/usr/bin/env python3
"""Collect compact, measured QA evidence from the two final EP04 MP4s.

The script deliberately does not perform the strict full-decode acceptance
check; the video skill validator owns that gate. Its single video pass per
output gathers representative frames and a small grayscale edge-motion sample.
"""

from __future__ import annotations

import argparse
import array
import hashlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
from fractions import Fraction
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DELIVERY_DIR = PROJECT_DIR.parent
REVIEW_DIR = DELIVERY_DIR / "review"
QA_DIR = REVIEW_DIR / "final-qa"
QA_PATH = REVIEW_DIR / "final-qa.json"
FRAME_COUNT = 7_200
FPS = 60
SAMPLE_RATE = 48_000
SAMPLES_PER_CHANNEL = 5_760_000
REPRESENTATIVE_FRAMES = [0, 120, 960, 1260, 1500, 2190, 3200, 3900, 4800, 5819, 5820, 5849, 5850, 5859, 5868, 6100, 6500, 7100, 7199]
DARK_NATIVE_FRAMES = {5819, 5820, 5849}
AUDIO_WINDOWS = [(4, 6), (60, 62), (97, 99), (117, 119)]
OUTPUTS = {
    "bilibili": {"dimensions": (3840, 2160), "roi": (0.13, 0.40, 0.52, 0.29)},
    "xiaohongshu": {"dimensions": (2160, 3840), "roi": (0.08, 0.24, 0.72, 0.20)},
}


class ToolFailure(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe and collect compact QA evidence for finished EP04 outputs.")
    parser.add_argument("--layout", choices=("both", *OUTPUTS), default="both")
    parser.add_argument("--no-write", action="store_true", help="Collect evidence in a temporary folder without saving review artifacts.")
    return parser.parse_args()


def run(command: list[str]) -> tuple[bytes, str]:
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    except FileNotFoundError as exc:
        raise ToolFailure(f"required tool is unavailable: {command[0]}") from exc
    stderr = result.stderr.decode("utf-8", errors="replace")
    if result.returncode != 0:
        tail = stderr[-2500:].strip()
        raise ToolFailure(f"command failed ({result.returncode}): {command[0]}\n{tail}")
    return result.stdout, stderr


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_delivery_path(value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    candidate = (DELIVERY_DIR / value).resolve()
    try:
        candidate.relative_to(DELIVERY_DIR.resolve())
    except ValueError:
        return None
    return candidate


def add_check(report: dict[str, Any], name: str, status: str, details: Any = None) -> None:
    item: dict[str, Any] = {"name": name, "status": status}
    if details is not None:
        item["details"] = details
    report["checks"].append(item)
    if status == "FAIL":
        report["failures"].append(name)
    elif status == "INCOMPLETE":
        report["incomplete"].append(name)


def load_manifest(report: dict[str, Any]) -> dict[str, Any] | None:
    path = DELIVERY_DIR / "delivery.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        add_check(report, "delivery.json is readable", "FAIL", str(exc))
        return None
    if not isinstance(value, dict):
        add_check(report, "delivery.json contains an object", "FAIL")
        return None
    add_check(report, "delivery.json is readable", "PASS")
    return value


def fraction(value: Any) -> float | None:
    try:
        return float(Fraction(str(value)))
    except (ValueError, ZeroDivisionError, TypeError):
        return None


def probe_video(path: Path, layout: str, expected: tuple[int, int], report: dict[str, Any]) -> dict[str, Any] | None:
    try:
        raw, _ = run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)])
        data = json.loads(raw)
    except ToolFailure as exc:
        add_check(report, f"{layout} ffprobe", "FAIL", str(exc))
        return None
    except json.JSONDecodeError as exc:
        add_check(report, f"{layout} ffprobe JSON", "FAIL", str(exc))
        return None
    streams = data.get("streams", []) if isinstance(data, dict) else []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not isinstance(video, dict):
        add_check(report, f"{layout} has a video stream", "FAIL")
        return None
    if not isinstance(audio, dict):
        add_check(report, f"{layout} has an audio stream", "FAIL")
        return None
    fmt = data.get("format", {})
    width, height = video.get("width"), video.get("height")
    avg_fps = fraction(video.get("avg_frame_rate"))
    duration = fraction(fmt.get("duration"))
    video_duration = fraction(video.get("duration"))
    audio_summary = {
        "codec": audio.get("codec_name"),
        "sample_rate": int(audio["sample_rate"]) if str(audio.get("sample_rate", "")).isdigit() else None,
        "channels": audio.get("channels"),
        "duration": audio.get("duration"),
    }
    colors = {key: video.get(key) for key in ("color_space", "color_transfer", "color_primaries", "color_range")}
    details = {
        "path": path.relative_to(DELIVERY_DIR).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "container": fmt.get("format_name"),
        "duration_seconds": duration,
        "video_duration_seconds": video_duration,
        "dimensions": [width, height],
        "average_fps": avg_fps,
        "reported_frames": video.get("nb_frames"),
        "pixel_format": video.get("pix_fmt"),
        "colors": colors,
        "audio": audio_summary,
    }
    add_check(report, f"{layout} MP4 dimensions", "PASS" if (width, height) == expected else "FAIL", details["dimensions"])
    add_check(report, f"{layout} MP4 frame rate", "PASS" if avg_fps == FPS else "FAIL", avg_fps)
    frames = video.get("nb_frames")
    if str(frames).isdigit():
        add_check(report, f"{layout} MP4 reports 7200 frames", "PASS" if int(frames) == FRAME_COUNT else "FAIL", int(frames))
    else:
        add_check(report, f"{layout} MP4 reports 7200 frames", "INCOMPLETE", frames)
    add_check(report, f"{layout} MP4 duration is 120 seconds", "PASS" if duration is not None and abs(duration - 120) <= 0.01 else "FAIL", duration)
    add_check(report, f"{layout} video stream duration is 120 seconds", "PASS" if video_duration is not None and abs(video_duration - 120) <= 0.01 else "FAIL", video_duration)
    add_check(report, f"{layout} MP4 has BT.709 color metadata", "PASS" if all(colors.get(k) == "bt709" for k in ("color_space", "color_transfer", "color_primaries")) else "FAIL", colors)
    add_check(report, f"{layout} AAC is 48-kHz stereo", "PASS" if (audio_summary["codec"], audio_summary["sample_rate"], audio_summary["channels"]) == ("aac", SAMPLE_RATE, 2) else "FAIL", audio_summary)
    audio_duration = fraction(audio_summary["duration"])
    add_check(report, f"{layout} AAC duration is 120 seconds", "PASS" if audio_duration is not None and abs(audio_duration - 120) <= 0.05 else "FAIL", audio_duration)
    return details


def measure_loudness(path: Path, layout: str, report: dict[str, Any]) -> dict[str, Any] | None:
    try:
        _, stderr = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-map", "0:a:0", "-af", "ebur128=peak=true", "-f", "null", "-"])
    except ToolFailure as exc:
        add_check(report, f"{layout} EBU R128 / true peak measurement", "FAIL", str(exc))
        return None
    integrated = re.findall(r"\bI:\s*(-?\d+(?:\.\d+)?)\s*LUFS", stderr)
    true_peak = re.findall(r"\bPeak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", stderr)
    result = {
        "integrated_lufs": float(integrated[-1]) if integrated else None,
        "true_peak_dBFS": float(true_peak[-1]) if true_peak else None,
        "filter": "ebur128=peak=true",
    }
    if result["integrated_lufs"] is None or result["true_peak_dBFS"] is None:
        add_check(report, f"{layout} EBU R128 / true peak measurement", "INCOMPLETE", result)
    else:
        add_check(report, f"{layout} EBU R128 / true peak measurement", "PASS", result)
        in_spec = -18 <= result["integrated_lufs"] <= -16 and result["true_peak_dBFS"] <= -1
        add_check(report, f"{layout} encoded loudness and true peak meet delivery target", "PASS" if in_spec else "FAIL", {**result, "target_lufs": [-18, -16], "maximum_true_peak_dbtp": -1})
    return result


def packet_hash(path: Path, layout: str, report: dict[str, Any]) -> str | None:
    try:
        raw, _ = run(["ffmpeg", "-hide_banner", "-v", "error", "-i", str(path), "-map", "0:a:0", "-c", "copy", "-f", "streamhash", "-hash", "sha256", "-"])
    except ToolFailure as exc:
        add_check(report, f"{layout} AAC packet SHA-256", "FAIL", str(exc))
        return None
    match = re.search(rb"SHA256=([0-9a-fA-F]{64})", raw)
    if not match:
        add_check(report, f"{layout} AAC packet SHA-256", "INCOMPLETE", raw.decode("utf-8", errors="replace")[-300:])
        return None
    value = match.group(1).decode("ascii").lower()
    add_check(report, f"{layout} AAC packet SHA-256", "PASS", value)
    return value


def motion_pairs() -> list[tuple[int, int, str]]:
    path = PROJECT_DIR / "timeline.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return []
    shots = data.get("shots") if isinstance(data, dict) else None
    if not isinstance(shots, list):
        return []
    pairs: list[tuple[int, int, str]] = []
    for index, shot in enumerate(shots, start=1):
        if not isinstance(shot, dict):
            continue
        start, end = shot.get("startFrame"), shot.get("endFrame")
        if type(start) is not int or type(end) is not int or end - start <= 300:
            continue
        label = str(shot.get("id", f"shot-{index}"))
        frame = start + 60
        while frame + 150 < end:
            pairs.append((frame, frame + 150, label))
            frame += 180
    return pairs


def crop_roi(width: int, height: int, fractions: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    x, y, w, h = fractions
    crop_w = max(2, int(width * w) & ~1)
    crop_h = max(2, int(height * h) & ~1)
    crop_x = int(width * x) & ~1
    crop_y = int(height * y) & ~1
    crop_w = min(crop_w, (width - crop_x) & ~1)
    crop_h = min(crop_h, (height - crop_y) & ~1)
    return crop_w, crop_h, crop_x, crop_y


def png_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        with path.open("rb") as stream:
            header = stream.read(24)
        if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
            return None
        return struct.unpack(">II", header[16:24])
    except OSError:
        return None


def edge_delta(raw: bytes, frame_bytes: int, first_index: int, second_index: int) -> dict[str, float]:
    a = memoryview(raw)[first_index * frame_bytes:(first_index + 1) * frame_bytes]
    b = memoryview(raw)[second_index * frame_bytes:(second_index + 1) * frame_bytes]
    if len(a) != frame_bytes or len(b) != frame_bytes or frame_bytes == 0:
        raise ValueError("motion ROI samples are incomplete")
    absolute = 0
    changed = 0
    for av, bv in zip(a, b):
        delta = abs(av - bv)
        absolute += delta
        changed += delta > 0
    return {"mean_absolute_edge_difference": absolute / frame_bytes, "changed_edge_pixel_fraction": changed / frame_bytes}


def extract_visual_evidence(
    path: Path,
    layout: str,
    expected: tuple[int, int],
    roi_fraction: tuple[float, float, float, float],
    pairs: list[tuple[int, int, str]],
    output_dir: Path,
    report: dict[str, Any],
    *,
    persist: bool,
) -> dict[str, Any] | None:
    try:
        with tempfile.TemporaryDirectory(prefix=f"ep04-{layout}-") as temp_name:
            temp = Path(temp_name)
            raw_pattern = temp / "all-%04d.png"
            rep_pattern = temp / "frame-%04d.png"
            crop_w, crop_h, crop_x, crop_y = crop_roi(*expected, roi_fraction)
            # After the collapse the subject moves to its reality anchor. Keep
            # the fixed-size ROI on that object instead of sampling empty sky.
            post = (0.42, 0.50) if layout == 'bilibili' else (0.08, 0.44)
            post_x, post_y = int(expected[0]*post[0]) & ~1, int(expected[1]*post[1]) & ~1
            crop_x_expr = f"'if(gte(t,97.8),{post_x},{crop_x})'"
            crop_y_expr = f"'if(gte(t,97.8),{post_y},{crop_y})'"
            if not pairs:
                add_check(report, "timeline supplies long-shot motion pairs", "INCOMPLETE")
            motion_frames = sorted({n for a, b, _ in pairs for n in (a, b)})
            all_frames = sorted(set(REPRESENTATIVE_FRAMES) | set(motion_frames))
            sample_expr = "+".join(f"eq(n\\,{n})" for n in all_frames)
            motion_expr = "+".join(f"eq(n\\,{n})" for n in motion_frames) or "eq(n\\,-1)"
            graph = (
                f"[0:v]split=2[samples][motion];"
                f"[samples]select='{sample_expr}',format=rgb24[sout];"
                f"[motion]select='{motion_expr}',crop={crop_w}:{crop_h}:{crop_x_expr}:{crop_y_expr},"
                "scale=192:-2:flags=area,edgedetect=low=0.1:high=0.2,format=gray[mout]"
            )
            command = [
                "ffmpeg", "-hide_banner", "-v", "error", "-i", str(path), "-filter_complex", graph,
                "-map", "[sout]", "-fps_mode:v:0", "passthrough", "-c:v:0", "png", "-f", "image2", "-start_number", "0", str(raw_pattern),
                "-map", "[mout]", "-fps_mode:v:0", "passthrough", "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1",
            ]
            raw, _ = run(command)
            for index, frame_number in enumerate(REPRESENTATIVE_FRAMES):
                os.link(temp / f"all-{all_frames.index(frame_number):04d}.png", temp / f"frame-{index:04d}.png")
            rep_files = [temp / f"frame-{index:04d}.png" for index in range(len(REPRESENTATIVE_FRAMES))]
            missing = [f for f in rep_files if not f.is_file()]
            wrong = {f.name: png_dimensions(f) for f in rep_files if f.is_file() and png_dimensions(f) != expected}
            if missing or wrong:
                raise ToolFailure(f"representative native PNG extraction mismatch; missing={len(missing)}, wrong={wrong}")

            scaled_height = max(2, int(192 * crop_h / crop_w) & ~1)
            frame_bytes = 192 * scaled_height
            if len(raw) != frame_bytes * len(motion_frames):
                raise ToolFailure(f"motion ROI byte count mismatch: expected {frame_bytes * len(motion_frames)}, got {len(raw)}")
            motion_index = {frame: index for index, frame in enumerate(motion_frames)}
            measured_pairs = []
            for first, second, shot in pairs:
                measured_pairs.append({
                    "shot": shot,
                    "frames": [first, second],
                    **edge_delta(raw, frame_bytes, motion_index[first], motion_index[second]),
                })

            persistent = output_dir / layout if persist else temp / "saved" / layout
            persistent.mkdir(parents=True, exist_ok=True)
            # Preserve actual t/t+2.5s pictures, not just the edge-delta numbers.
            pair_dir = persistent / "motion-pairs"
            pair_dir.mkdir(parents=True, exist_ok=True)
            if pairs:
                for index, (first, second, _) in enumerate(pairs):
                    for side, frame_number in enumerate((first, second)):
                        os.link(temp / f"all-{all_frames.index(frame_number):04d}.png", temp / f"pair-{index*2+side:04d}.png")
                run([
                    "ffmpeg", "-hide_banner", "-v", "error", "-framerate", "1", "-start_number", "0", "-i", str(temp / "pair-%04d.png"),
                    "-vf", f"scale={480 if layout == 'bilibili' else 360}:-2:flags=lanczos,tile=2x1:padding=6:margin=6:color=0x050811",
                    "-fps_mode", "passthrough", "-q:v", "4", "-y", "-start_number", "0", str(pair_dir / "pair-%03d.jpg"),
                ])
                for index, item in enumerate(measured_pairs):
                    picture = pair_dir / f"pair-{index:03d}.jpg"
                    if not picture.is_file():
                        raise ToolFailure(f"motion pair picture missing: {index}")
                    item["picture"] = picture.relative_to(DELIVERY_DIR).as_posix() if persist else picture.name
            # One JPEG contact sheet in frame-list order. The JSON stores that order explicitly.
            preview_width = 960 if layout == "bilibili" else 360
            filter_complex = f"scale={preview_width}:-2:flags=lanczos,tile=3x{math.ceil(len(REPRESENTATIVE_FRAMES)/3)}:padding=8:margin=8:color=0x050811"
            run([
                "ffmpeg", "-hide_banner", "-v", "error", "-framerate", "1", "-start_number", "0", "-i", str(rep_pattern),
                "-vf", filter_complex, "-frames:v", "1", "-q:v", "4", "-y", str(persistent / "contact.jpg"),
            ])
            # Individual compact portrait previews preserve the exact sample order.
            if layout == "xiaohongshu":
                previews = persistent / "previews"
                previews.mkdir(parents=True, exist_ok=True)
                preview_pattern = temp / "preview-%04d.jpg"
                run([
                    "ffmpeg", "-hide_banner", "-v", "error", "-framerate", "1", "-start_number", "0", "-i", str(rep_pattern),
                    "-vf", "scale=360:-2:flags=lanczos", "-q:v", "4", "-y", "-start_number", "0", str(preview_pattern),
                ])
                for index, frame_number in enumerate(REPRESENTATIVE_FRAMES):
                    source = temp / f"preview-{index:04d}.jpg"
                    if not source.is_file():
                        raise ToolFailure(f"portrait preview missing for representative frame {frame_number}")
                    shutil.copy2(source, previews / f"frame-{frame_number:04d}.jpg")
            native_saved: list[str] = []
            if persist:
                native_dir = persistent / "dark-native"
                native_dir.mkdir(parents=True, exist_ok=True)
                for frame_number in sorted(DARK_NATIVE_FRAMES):
                    index = REPRESENTATIVE_FRAMES.index(frame_number)
                    destination = native_dir / f"frame-{frame_number:04d}.png"
                    shutil.copy2(rep_files[index], destination)
                    native_saved.append(destination.relative_to(DELIVERY_DIR).as_posix())

            return {
                "representative_frames": REPRESENTATIVE_FRAMES,
                "representative_dimensions": list(expected),
                "contact_sheet": (persistent / "contact.jpg").relative_to(DELIVERY_DIR).as_posix() if persist else None,
                "portrait_previews": len(REPRESENTATIVE_FRAMES) if layout == "xiaohongshu" else 0,
                "dark_native_pngs": native_saved,
                "motion_roi_fraction": {"x": roi_fraction[0], "y": roi_fraction[1], "w": roi_fraction[2], "h": roi_fraction[3]},
                "motion_roi_after_97_8_seconds": {"x": post[0], "y": post[1], "w": roi_fraction[2], "h": roi_fraction[3]},
                "motion_roi_scaled_to": [192, scaled_height],
                "motion_pairs": measured_pairs,
                "motion_interpretation": "Grayscale edge-difference samples are a heuristic; they do not prove complete motion or human acceptance.",
                "strict_full_decode": "delegated to the video skill validator",
            }
    except ToolFailure as exc:
        add_check(report, f"{layout} representative frames and motion samples", "FAIL", str(exc))
        return None
    except (OSError, ValueError, IndexError) as exc:
        add_check(report, f"{layout} representative frames and motion samples", "FAIL", str(exc))
        return None


def wave_info(path: Path) -> tuple[dict[str, Any], int] | None:
    try:
        with wave.open(str(path), "rb") as stream:
            info = {
                "sample_rate": stream.getframerate(),
                "channels": stream.getnchannels(),
                "samples_per_channel": stream.getnframes(),
                "sample_width_bytes": stream.getsampwidth(),
                "compression": stream.getcomptype(),
            }
    except (OSError, wave.Error):
        return None
    return info, info["sample_width_bytes"]


def pcm_to_ints(raw: bytes, width: int) -> list[int]:
    if width == 2:
        values = array.array("h")
        values.frombytes(raw)
        if sys.byteorder != "little":
            values.byteswap()
        return list(values)
    if width == 3:
        result = []
        for index in range(0, len(raw), 3):
            value = int.from_bytes(raw[index:index + 3], "little", signed=False)
            result.append(value - 0x1000000 if value & 0x800000 else value)
        return result
    if width == 4:
        values = array.array("i")
        values.frombytes(raw)
        if sys.byteorder != "little":
            values.byteswap()
        return list(values)
    raise ValueError(f"unsupported PCM sample width: {width}")


def pearson(left: list[int], right: list[int]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    count = len(left)
    mean_left, mean_right = sum(left) / count, sum(right) / count
    covariance = variance_left = variance_right = 0.0
    for a, b in zip(left, right):
        da, db = a - mean_left, b - mean_right
        covariance += da * db
        variance_left += da * da
        variance_right += db * db
    if variance_left == 0 or variance_right == 0:
        return None
    return covariance / math.sqrt(variance_left * variance_right)


def compare_audio(master: Path | None, paths: dict[str, Path], packet_hashes: dict[str, str | None], report: dict[str, Any]) -> dict[str, Any]:
    if len(packet_hashes) == 2 and all(packet_hashes.values()):
        equal = len(set(packet_hashes.values())) == 1
        add_check(report, "both MP4s have identical encoded AAC packet SHA-256", "PASS" if equal else "FAIL", packet_hashes)
    else:
        add_check(report, "both MP4s have identical encoded AAC packet SHA-256", "INCOMPLETE", packet_hashes)
    if master is None or not master.is_file():
        add_check(report, "AAC correlation against shared PCM master", "INCOMPLETE", "shared PCM master is missing")
        return {"packet_hashes": packet_hashes, "pcm_correlations": None}
    info_result = wave_info(master)
    if info_result is None:
        add_check(report, "shared PCM master format", "FAIL", "unreadable WAV")
        return {"packet_hashes": packet_hashes, "pcm_correlations": None}
    info, sample_width = info_result
    if (info["sample_rate"], info["channels"], info["samples_per_channel"]) != (SAMPLE_RATE, 2, SAMPLES_PER_CHANNEL):
        add_check(report, "shared PCM master format", "FAIL", info)
        return {"packet_hashes": packet_hashes, "pcm_correlations": None}
    add_check(report, "shared PCM master format", "PASS", {**info, "sha256": sha256_file(master)})

    correlations: dict[str, Any] = {}
    for layout, path in paths.items():
        try:
            decoded, _ = run(["ffmpeg", "-hide_banner", "-v", "error", "-i", str(path), "-map", "0:a:0", "-vn", "-sn", "-dn", "-ac", "2", "-ar", str(SAMPLE_RATE), "-f", "s16le", "pipe:1"])
        except ToolFailure as exc:
            add_check(report, f"{layout} AAC decode for PCM correlation", "FAIL", str(exc))
            continue
        expected_bytes = SAMPLES_PER_CHANNEL * 2 * 2
        if len(decoded) != expected_bytes:
            add_check(report, f"{layout} AAC decoded sample count", "INCOMPLETE", {"expected_bytes": expected_bytes, "actual_bytes": len(decoded), "timestamp_alignment": "unaltered FFmpeg timestamps; no offset guessed"})
            continue
        output_windows: dict[str, Any] = {}
        try:
            with wave.open(str(master), "rb") as stream:
                for start, end in AUDIO_WINDOWS:
                    frames = (end - start) * SAMPLE_RATE
                    start_sample = start * SAMPLE_RATE
                    stream.setpos(start_sample)
                    master_raw = stream.readframes(frames)
                    byte_start = start_sample * 2 * 2
                    decoded_raw = decoded[byte_start:byte_start + frames * 2 * 2]
                    master_values = pcm_to_ints(master_raw, sample_width)
                    decoded_values = pcm_to_ints(decoded_raw, 2)
                    left = pearson(master_values[0::2], decoded_values[0::2])
                    right = pearson(master_values[1::2], decoded_values[1::2])
                    output_windows[f"{start}-{end}s"] = {"left": left, "right": right}
        except (OSError, wave.Error, ValueError) as exc:
            add_check(report, f"{layout} AAC correlation windows", "FAIL", str(exc))
            continue
        correlations[layout] = output_windows
        add_check(report, f"{layout} AAC correlation windows", "PASS", output_windows)
    return {
        "packet_hashes": packet_hashes,
        "pcm_correlations": correlations,
        "correlation_windows_seconds": AUDIO_WINDOWS,
        "correlation_note": "Pearson values are measured evidence without an imposed pass threshold; timestamps were not shifted or guessed.",
    }


def main() -> int:
    args = parse_args()
    report: dict[str, Any] = {
        "schema_version": 1,
        "status": "INCOMPLETE",
        "checks": [],
        "failures": [],
        "incomplete": [],
        "outputs": {},
        "audio_comparison": {},
        "acceptance_status": "NOT_EVALUATED",
        "scope": "final MP4 probes, one EBU R128 measurement per output, representative frames, motion heuristic, packet hashes and PCM correlation; strict full decode and human review remain separate",
    }
    manifest = load_manifest(report)
    if manifest is None:
        report["status"] = "FAIL"
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1
    if manifest.get("duration_seconds") != 120 or manifest.get("fps") != FPS or manifest.get("total_frames") != FRAME_COUNT:
        add_check(report, "delivery.json timing is 120s / 60fps / 7200 frames", "FAIL", {k: manifest.get(k) for k in ("duration_seconds", "fps", "total_frames")})
    else:
        add_check(report, "delivery.json timing is 120s / 60fps / 7200 frames", "PASS")
    layouts = list(OUTPUTS) if args.layout == "both" else [args.layout]
    output_specs = manifest.get("outputs", {})
    paths: dict[str, Path] = {}
    packet_hashes: dict[str, str | None] = {}
    master_value = manifest.get("audio", {}).get("master") if isinstance(manifest.get("audio"), dict) else None
    master = safe_delivery_path(master_value)
    if master is None:
        add_check(report, "delivery.json audio master path is safe", "FAIL")
    elif not master.is_file():
        add_check(report, "shared PCM master is available", "INCOMPLETE", str(master_value))
    else:
        add_check(report, "shared PCM master is available", "PASS", str(master_value))

    pairs = motion_pairs()
    for layout in layouts:
        config = OUTPUTS[layout]
        output = output_specs.get(layout) if isinstance(output_specs, dict) else None
        relpath = output.get("path") if isinstance(output, dict) else None
        declared = (output.get("width"), output.get("height")) if isinstance(output, dict) else None
        add_check(report, f"{layout} delivery.json dimensions match native target", "PASS" if declared == config["dimensions"] else "FAIL", declared)
        path = safe_delivery_path(relpath)
        if path is None:
            add_check(report, f"{layout} delivery path is safe", "FAIL", relpath)
            continue
        if not path.is_file():
            add_check(report, f"{layout} final MP4 is present", "INCOMPLETE", relpath)
            continue
        add_check(report, f"{layout} final MP4 is present", "PASS", {"path": relpath, "bytes": path.stat().st_size})
        paths[layout] = path
        details = probe_video(path, layout, config["dimensions"], report)
        if details:
            report["outputs"][layout] = details
        loudness = measure_loudness(path, layout, report)
        if loudness is not None:
            report["outputs"].setdefault(layout, {})["loudness"] = loudness
        packet_hashes[layout] = packet_hash(path, layout, report)

    if not args.no_write:
        output_dir = QA_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
    else:
        output_dir = Path(tempfile.mkdtemp(prefix="ep04-final-qa-"))
    for layout in layouts:
        if layout not in paths:
            continue
        config = OUTPUTS[layout]
        visual = extract_visual_evidence(
            paths[layout], layout, config["dimensions"], config["roi"], pairs, output_dir, report,
            persist=not args.no_write,
        )
        if visual is not None:
            report["outputs"].setdefault(layout, {})["visual_evidence"] = visual
    if args.no_write:
        shutil.rmtree(output_dir, ignore_errors=True)

    report["audio_comparison"] = compare_audio(master, paths, packet_hashes, report)
    if not pairs:
        add_check(report, "long-shot motion sample plan", "INCOMPLETE", "timeline.json is unavailable or has no shot longer than five seconds")
    report["status"] = "FAIL" if report["failures"] else "INCOMPLETE" if report["incomplete"] else "PASS"
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(encoded, end="")
    if not args.no_write:
        REVIEW_DIR.mkdir(parents=True, exist_ok=True)
        temporary = QA_PATH.with_suffix(".json.tmp")
        temporary.write_text(encoded, encoding="utf-8")
        os.replace(temporary, QA_PATH)
    return 1 if report["failures"] else 2 if report["incomplete"] else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ToolFailure as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(3)
