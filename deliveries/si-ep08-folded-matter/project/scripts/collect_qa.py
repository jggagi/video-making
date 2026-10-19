#!/usr/bin/env python3
"""Probe, fully decode, hash and optionally capture final encoded EP08 frames."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DELIVERY_DIR = PROJECT_DIR.parent
REVIEW_DIR = DELIVERY_DIR / "review"
FPS = 60
FRAME_COUNT = 7200
SAMPLE_RATE = 48_000
EXPECTED_FRAMES = (360, 960, 1500, 2190, 3120, 3900, 4800, 5879, 5880, 5910, 6500, 7100, 7199)
LAYOUTS = {
    "landscape": ("bilibili", 3840, 2160),
    "portrait": ("xiaohongshu", 2160, 3840),
}


class CollectionError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CollectionError(f"cannot read {label}: {exc}") from None
    if not isinstance(value, dict):
        raise CollectionError(f"{label} must contain an object")
    return value


def contained_path(base: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise CollectionError(f"{label} path is missing")
    result = (base / value).resolve()
    try:
        result.relative_to(base.resolve())
    except ValueError:
        raise CollectionError(f"{label} path escapes its owning directory") from None
    return result


def fresh_dir(base: Path) -> Path:
    if not base.exists():
        base.mkdir(parents=True)
        return base
    for revision in range(2, 10000):
        candidate = base.with_name(f"{base.name}-r{revision:02d}")
        try:
            candidate.mkdir(parents=True)
            return candidate
        except FileExistsError:
            continue
    raise CollectionError(f"no fresh evidence directory is available for {base}")


def run(argv: list[str], label: str, *, timeout: int = 1800) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CollectionError(f"{label} could not complete: {exc}") from None
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise CollectionError(f"{label} failed ({result.returncode}): {detail[-1800:] or 'no diagnostics'}")
    return result


def probe(ffprobe: str, media: Path) -> dict[str, Any]:
    result = run([ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(media)], f"ffprobe {media.name}", timeout=90)
    try:
        data = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise CollectionError(f"ffprobe returned invalid JSON for {media.name}") from None
    if not isinstance(data, dict) or not isinstance(data.get("streams"), list):
        raise CollectionError(f"ffprobe returned incomplete metadata for {media.name}")
    video = next((stream for stream in data["streams"] if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in data["streams"] if stream.get("codec_type") == "audio"), None)
    if video is None or audio is None:
        raise CollectionError(f"{media.name} must contain video and audio streams")
    return {"format": data.get("format", {}), "video": video, "audio": audio}


def number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def validate_media(layout: str, width: int, height: int, metadata: dict[str, Any]) -> dict[str, bool]:
    video, audio, container = metadata["video"], metadata["audio"], metadata["format"]
    video_duration = number(video.get("duration"))
    audio_duration = number(audio.get("duration"))
    container_duration = number(container.get("duration"))
    fps_ok = video.get("avg_frame_rate") == "60/1" or video.get("r_frame_rate") == "60/1"
    return {
        "dimensions": (video.get("width"), video.get("height")) == (width, height),
        "fps_60": fps_ok,
        "frames_7200": video.get("nb_frames") in (str(FRAME_COUNT), FRAME_COUNT),
        "video_h264": video.get("codec_name") == "h264",
        "pixel_format_yuv420p": video.get("pix_fmt") == "yuv420p",
        "bt709_color_metadata": all(video.get(key) == "bt709" for key in ("color_space", "color_primaries", "color_transfer")),
        "audio_aac_48k_stereo": audio.get("codec_name") == "aac" and audio.get("sample_rate") == str(SAMPLE_RATE) and audio.get("channels") == 2,
        "video_duration_120s": video_duration is not None and abs(video_duration - 120) <= 0.001,
        "audio_duration_within_50ms": audio_duration is not None and abs(audio_duration - 120) <= 0.05,
        "container_duration_within_50ms": container_duration is not None and abs(container_duration - 120) <= 0.05,
    }


def moov_before_mdat(path: Path) -> bool:
    boxes: list[str] = []
    try:
        with path.open("rb") as stream:
            file_size = path.stat().st_size
            offset = 0
            while offset + 8 <= file_size:
                stream.seek(offset)
                header = stream.read(8)
                if len(header) != 8:
                    break
                size, kind = struct.unpack(">I4s", header)
                header_size = 8
                if size == 1:
                    extended = stream.read(8)
                    if len(extended) != 8:
                        break
                    size = struct.unpack(">Q", extended)[0]
                    header_size = 16
                elif size == 0:
                    size = file_size - offset
                if size < header_size or offset + size > file_size:
                    break
                boxes.append(kind.decode("ascii", errors="replace"))
                offset += size
    except OSError:
        return False
    return "moov" in boxes and "mdat" in boxes and boxes.index("moov") < boxes.index("mdat")


def ffmpeg_select(frames: tuple[int, ...]) -> str:
    return "+".join(f"eq(n\\,{frame})" for frame in frames)


def capture_frames(ffmpeg: str, media: Path, layout: str, evidence_dir: Path) -> dict[str, Any]:
    native_dir = evidence_dir / "native"
    phone_dir = evidence_dir / "phone-360px"
    native_dir.mkdir(parents=True)
    phone_dir.mkdir(parents=True)
    selection = ffmpeg_select(EXPECTED_FRAMES)
    native_pattern = native_dir / "encoded-%02d.png"
    phone_pattern = phone_dir / "phone-%02d.jpg"
    run([
        ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error", "-i", str(media),
        "-vf", f"select='{selection}'", "-fps_mode", "passthrough", "-start_number", "0",
        "-compression_level", "6", str(native_pattern),
    ], f"native encoded frame extraction {layout}")
    scale_filter = f"select='{selection}',scale=360:-2:flags=lanczos"
    run([
        ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error", "-i", str(media),
        "-vf", scale_filter, "-fps_mode", "passthrough", "-start_number", "0", "-q:v", "2", str(phone_pattern),
    ], f"360px review frame extraction {layout}")
    native_files = sorted(native_dir.glob("encoded-*.png"))
    phone_files = sorted(phone_dir.glob("phone-*.jpg"))
    if len(native_files) != len(EXPECTED_FRAMES) or len(phone_files) != len(EXPECTED_FRAMES):
        raise CollectionError(f"frame extraction for {layout} returned {len(native_files)} native and {len(phone_files)} phone frames; expected {len(EXPECTED_FRAMES)} each")

    cols, rows = ((4, 4) if layout == "landscape" else (3, 5))
    contact_sheet = evidence_dir / f"{layout}-contact-sheet.jpg"
    tile_filter = f"select='{selection}',scale=360:-2:flags=lanczos,tile={cols}x{rows}:nb_frames={len(EXPECTED_FRAMES)}:padding=10:margin=10:color=white"
    run([
        ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error", "-i", str(media),
        "-vf", tile_filter, "-frames:v", "1", "-q:v", "2", str(contact_sheet),
    ], f"contact sheet generation {layout}")
    return {
        "frame_indexes": list(EXPECTED_FRAMES),
        "native_frames": [path.relative_to(DELIVERY_DIR).as_posix() for path in native_files],
        "phone_360px_frames": [path.relative_to(DELIVERY_DIR).as_posix() for path in phone_files],
        "contact_sheet": contact_sheet.relative_to(DELIVERY_DIR).as_posix(),
        "human_review_status": "pending",
    }


def report_path() -> Path:
    base = REVIEW_DIR / "encoded-qa-summary.json"
    if not base.exists():
        return base
    for revision in range(2, 10000):
        candidate = base.with_name(f"encoded-qa-summary-r{revision:02d}.json")
        if not candidate.exists():
            return candidate
    raise CollectionError("no unused encoded QA report name is available")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", choices=("landscape", "portrait", "both"), default="both")
    parser.add_argument("--capture", action="store_true", help="Extract native frames, 360px frames and contact sheets for human review.")
    parser.add_argument("--no-write", action="store_true", help="Print measurements without saving the summary report.")
    args = parser.parse_args()
    if args.capture and args.no_write:
        parser.error("--capture cannot be combined with --no-write because capture evidence needs an index report")
    try:
        manifest = read_json(DELIVERY_DIR / "delivery.json", "delivery.json")
        ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
        if not ffmpeg or not ffprobe:
            raise CollectionError("ffmpeg and ffprobe must already be available on PATH")
        requested = ("landscape", "portrait") if args.layout == "both" else (args.layout,)
        reports: list[dict[str, Any]] = []
        for layout in requested:
            key, width, height = LAYOUTS[layout]
            spec = manifest.get("outputs", {}).get(key, {})
            if (spec.get("width"), spec.get("height")) != (width, height):
                raise CollectionError(f"delivery.json declares the wrong {layout} output dimensions")
            media = contained_path(DELIVERY_DIR, spec.get("path"), f"{layout} MP4")
            if not media.is_file():
                raise CollectionError(f"final {layout} MP4 is missing: {media}")
            metadata = probe(ffprobe, media)
            checks = validate_media(layout, width, height, metadata)
            decode = run([ffmpeg, "-hide_banner", "-nostdin", "-v", "error", "-xerror", "-err_detect", "explode", "-i", str(media), "-f", "null", "-"], f"full decode {layout}", timeout=7200)
            atom_order = moov_before_mdat(media)
            report: dict[str, Any] = {
                "layout": layout,
                "path": media.relative_to(DELIVERY_DIR).as_posix(),
                "bytes": media.stat().st_size,
                "sha256": sha256_file(media),
                "ffprobe": metadata,
                "checks": checks,
                "strict_full_decode": {"pass": decode.returncode == 0, "method": "ffmpeg -xerror -err_detect explode full-file demux and audio/video decode to null"},
                "mp4_faststart": {"pass": atom_order, "method": "top-level MP4 moov atom precedes mdat"},
                "human_aesthetic_and_device_acceptance": "pending",
            }
            report["status"] = "PASS" if all(checks.values()) and atom_order else "FAIL"
            if args.capture:
                evidence_dir = fresh_dir(REVIEW_DIR / "encoded-frames" / layout)
                report["capture"] = capture_frames(ffmpeg, media, layout, evidence_dir)
            reports.append(report)
        overall = "PASS" if all(item["status"] == "PASS" for item in reports) else "FAIL"
        result = {
            "status": overall,
            "scope": "media metadata and strict full-file decode; human aesthetic, listening, phone and platform acceptance remain separate",
            "manifest_sha256": sha256_file(DELIVERY_DIR / "delivery.json"),
            "layouts": reports,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not args.no_write:
            REVIEW_DIR.mkdir(parents=True, exist_ok=True)
            target = report_path()
            temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
            temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, target)
            print(f"Report: {target}")
        return 0 if overall == "PASS" else 1
    except (CollectionError, OSError, KeyError, TypeError) as exc:
        print(f"[collect-qa] ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
