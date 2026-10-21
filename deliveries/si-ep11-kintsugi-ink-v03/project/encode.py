"""Encode the complete native EP11 v03 Blender PNG sequence to H.264."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import uuid
from fractions import Fraction
from pathlib import Path
from typing import Any


FRAME_START = 1
FRAME_END = 1525
SOURCE_FPS = 30
FILM_FPS = 60
FILM_FRAME_START = 550
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
FRAME_NAME_RE = re.compile(r"^frame-(\d{4})\.png$")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Validate and encode the full 1525-frame Blender source sequence."
    )
    p.add_argument("--frames-dir", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path, help="New .mp4 output path")
    p.add_argument("--width", type=int, default=2160)
    p.add_argument("--height", type=int, default=3840)
    return p


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def png_dimensions(path: Path) -> tuple[int, int]:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size <= 24:
        raise ValueError(f"missing, empty, or non-file PNG: {path}")
    with path.open("rb") as f:
        header = f.read(24)
        f.seek(-12, 2)
        if f.read(12) != b"\x00\x00\x00\x00IEND\xaeB\x60\x82":
            raise ValueError(f"PNG has no complete IEND trailer: {path}")
    if (
        len(header) != 24
        or header[:8] != PNG_SIGNATURE
        or int.from_bytes(header[8:12], "big") != 13
        or header[12:16] != b"IHDR"
    ):
        raise ValueError(f"invalid PNG signature or IHDR: {path}")
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    if width <= 0 or height <= 0:
        raise ValueError(f"invalid PNG dimensions {width}x{height}: {path}")
    return width, height


def read_guard(frames_dir: Path) -> tuple[dict[str, Any], str]:
    guard_path = frames_dir / "render-guard.json"
    if not guard_path.is_file():
        raise ValueError(f"render guard is required: {guard_path}")
    raw = guard_path.read_bytes()
    try:
        guard = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid render guard JSON: {guard_path}: {exc}") from exc
    if not isinstance(guard, dict) or guard.get("schema_version") != 1:
        raise ValueError("unsupported render guard schema")
    scene = guard.get("scene", {})
    render = guard.get("render", {})
    expected_scene = {
        "frame_start": FRAME_START,
        "frame_end": FRAME_END,
        "fps": SOURCE_FPS,
        "fps_base": 1.0,
        "source_fps": SOURCE_FPS,
        "film_frame_start": FILM_FRAME_START,
        "film_fps": FILM_FPS,
        "film_frame_end_exclusive": FILM_FRAME_START + FRAME_END * (FILM_FPS // SOURCE_FPS),
    }
    for key, value in expected_scene.items():
        if scene.get(key) != value:
            raise ValueError(f"render guard scene.{key} must be {value}; found {scene.get(key)!r}")
    if render.get("resolution_percentage") != 100:
        raise ValueError("render guard resolution_percentage must be 100")
    if render.get("image_format") != "PNG" or render.get("color_mode") != "RGB":
        raise ValueError("render guard must describe PNG RGB source frames")
    if render.get("color_depth") != "8":
        raise ValueError("render guard must describe 8-bit source frames")
    if render.get("engine") not in ("CYCLES", "BLENDER_EEVEE_NEXT"):
        raise ValueError("render guard has an unsupported Blender engine")
    if int(render.get("samples", 0)) <= 0:
        raise ValueError("render guard must record a positive sample count")
    return guard, hashlib.sha256(raw).hexdigest()


def collect_frames(frames_dir: Path, width: int, height: int) -> tuple[list[dict[str, Any]], str]:
    actual: dict[int, Path] = {}
    unexpected: list[str] = []
    for path in frames_dir.iterdir():
        match = FRAME_NAME_RE.fullmatch(path.name)
        if match:
            frame = int(match.group(1))
            if frame in actual:
                raise ValueError(f"duplicate numbered frame: {path.name}")
            actual[frame] = path
        elif path.name.startswith("frame-") and path.suffix.lower() == ".png":
            unexpected.append(path.name)
    expected_numbers = set(range(FRAME_START, FRAME_END + 1))
    missing = sorted(expected_numbers - set(actual))
    extra = sorted(set(actual) - expected_numbers)
    if missing or extra or unexpected or len(actual) != FRAME_END:
        details = []
        if missing:
            details.append(f"missing {len(missing)} frames (first: {missing[:5]})")
        if extra:
            details.append(f"unexpected frame numbers: {extra[:5]}")
        if unexpected:
            details.append(f"unexpected PNG names: {unexpected[:5]}")
        raise ValueError("frame sequence must contain exactly frame-0001.png..frame-1525.png: " + "; ".join(details))

    files: list[dict[str, Any]] = []
    sequence_hash = hashlib.sha256()
    for frame in range(FRAME_START, FRAME_END + 1):
        path = actual[frame]
        dimensions = png_dimensions(path)
        if dimensions != (width, height):
            raise ValueError(f"{path.name} is {dimensions[0]}x{dimensions[1]}, expected {width}x{height}")
        digest = sha256_file(path)
        files.append(
            {
                "frame": frame,
                "path": path.name,
                "bytes": path.stat().st_size,
                "width": width,
                "height": height,
                "sha256": digest,
            }
        )
        sequence_hash.update(f"{frame:04d}\0{digest}\n".encode("ascii"))
    return files, sequence_hash.hexdigest()


def run_checked(command: list[str], label: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip() or f"exit status {result.returncode}"
        raise RuntimeError(f"{label} failed: {details[-6000:]}")
    return result


def ffprobe_movie(path: Path, ffprobe: str, width: int, height: int) -> dict[str, Any]:
    result = run_checked(
        [
            ffprobe,
            "-v",
            "error",
            "-count_frames",
            "-show_entries",
            "stream=codec_name,width,height,r_frame_rate,avg_frame_rate,nb_frames,nb_read_frames,pix_fmt,color_primaries,color_transfer,color_space",
            "-of",
            "json",
            str(path),
        ],
        "ffprobe",
    )
    try:
        streams = json.loads(result.stdout).get("streams", [])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"ffprobe returned invalid JSON: {exc}") from exc
    if len(streams) != 1:
        raise RuntimeError(f"expected one video stream, found {len(streams)}")
    stream = streams[0]
    required = {
        "codec_name": "h264",
        "width": width,
        "height": height,
        "pix_fmt": "yuv420p",
        "color_primaries": "bt709",
        "color_transfer": "bt709",
        "color_space": "bt709",
    }
    for key, value in required.items():
        if stream.get(key) != value:
            raise RuntimeError(f"encoded movie {key} must be {value!r}; found {stream.get(key)!r}")
    for key in ("r_frame_rate", "avg_frame_rate"):
        try:
            rate = Fraction(stream[key])
        except (KeyError, ValueError, ZeroDivisionError) as exc:
            raise RuntimeError(f"ffprobe did not report a valid {key}") from exc
        if rate != SOURCE_FPS:
            raise RuntimeError(f"encoded movie {key} must be {SOURCE_FPS}/1; found {stream[key]}")
    frame_count = stream.get("nb_read_frames")
    if frame_count is None or int(frame_count) != FRAME_END:
        raise RuntimeError(f"encoded movie must decode to {FRAME_END} frames; found {frame_count!r}")
    return stream


def strict_decode(path: Path, ffmpeg: str) -> None:
    run_checked(
        [ffmpeg, "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"],
        "strict ffmpeg decode",
    )


def expected_source_summary(guard: dict[str, Any], guard_sha: str, files: list[dict[str, Any]], sequence_sha: str, width: int, height: int) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source": {
            "render_guard_sha256": guard_sha,
            "blend_path": guard["blend"]["path"],
            "blend_sha256": guard["blend"]["sha256"],
            "frame_count": len(files),
            "sequence_sha256": sequence_sha,
            "width": width,
            "height": height,
            "fps": SOURCE_FPS,
            "frame_duration": "1/30",
            "files": files,
        },
        "frame_mapping": {
            "source_frame_start": FRAME_START,
            "source_frame_end": FRAME_END,
            "source_fps": SOURCE_FPS,
            "film_frame_start": FILM_FRAME_START,
            "film_fps": FILM_FPS,
            "film_frame_step": FILM_FPS // SOURCE_FPS,
            "film_frame_end_exclusive": FILM_FRAME_START + FRAME_END * (FILM_FPS // SOURCE_FPS),
        },
    }


def matching_existing_output(out: Path, sidecar: Path, source: dict[str, Any]) -> bool:
    if not out.exists():
        return False
    if not out.is_file() or not sidecar.is_file():
        return False
    try:
        existing = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if existing.get("source") != source.get("source") or existing.get("frame_mapping") != source.get("frame_mapping"):
        return False
    movie = existing.get("movie", {})
    return movie.get("path") == str(out) and movie.get("sha256") == sha256_file(out)


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    temp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def encode(args: argparse.Namespace) -> None:
    frames_dir = args.frames_dir.expanduser().resolve(strict=True)
    if not frames_dir.is_dir():
        raise ValueError(f"--frames-dir must be an existing directory: {frames_dir}")
    out = args.out.expanduser().absolute()
    if out.suffix.lower() != ".mp4":
        raise ValueError("--out must have an .mp4 extension")
    if not out.parent.is_dir():
        raise ValueError(f"movie output parent must already exist: {out.parent}")
    if args.width <= 0 or args.height <= 0:
        raise ValueError("--width and --height must be positive integers")

    guard, guard_sha = read_guard(frames_dir)
    render = guard["render"]
    if int(render.get("width", 0)) != args.width or int(render.get("height", 0)) != args.height:
        raise ValueError(
            f"requested output dimensions {args.width}x{args.height} must match the guarded "
            f"source dimensions {render.get('width')}x{render.get('height')}"
        )
    files, sequence_sha = collect_frames(frames_dir, args.width, args.height)
    source = expected_source_summary(guard, guard_sha, files, sequence_sha, args.width, args.height)
    sidecar = frames_dir / "source-footage.json"
    if out.exists():
        if matching_existing_output(out, sidecar, source):
            print(f"already verified: {out}")
            return
        raise FileExistsError(f"refusing to overwrite existing divergent movie: {out}")

    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("ffmpeg and ffprobe must both be available on PATH")
    temp = out.with_name(f".{out.stem}.{os.getpid()}.{uuid.uuid4().hex}.tmp.mp4")
    try:
        run_checked(
            [
                ffmpeg,
                "-hide_banner",
                "-nostdin",
                "-y",
                "-framerate",
                str(SOURCE_FPS),
                "-start_number",
                str(FRAME_START),
                "-i",
                str(frames_dir / "frame-%04d.png"),
                "-frames:v",
                str(FRAME_END),
                "-an",
                "-vf",
                "scale=iw:ih:out_color_matrix=bt709:out_range=tv,format=yuv420p,setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709",
                "-c:v",
                "libx264",
                "-crf",
                "16",
                "-preset",
                "slow",
                "-pix_fmt",
                "yuv420p",
                "-color_primaries",
                "bt709",
                "-color_trc",
                "bt709",
                "-colorspace",
                "bt709",
                "-fps_mode",
                "cfr",
                "-movflags",
                "+faststart",
                str(temp),
            ],
            "ffmpeg encode",
        )
        stream = ffprobe_movie(temp, ffprobe, args.width, args.height)
        strict_decode(temp, ffmpeg)
        movie_sha = sha256_file(temp)
        result = dict(source)
        result["movie"] = {
            "path": str(out),
            "sha256": movie_sha,
            "bytes": temp.stat().st_size,
            "codec": stream["codec_name"],
            "width": args.width,
            "height": args.height,
            "fps": SOURCE_FPS,
            "frame_count": FRAME_END,
            "pix_fmt": stream["pix_fmt"],
            "color_primaries": stream["color_primaries"],
            "color_transfer": stream["color_transfer"],
            "color_space": stream["color_space"],
        }
        # Publish only a fully probed and decoded movie, without clobbering a race-created file.
        if out.exists():
            raise FileExistsError(f"movie output appeared during encoding; refusing to replace: {out}")
        atomic_json(sidecar, result)
        try:
            os.link(temp, out)
        except FileExistsError as exc:
            raise FileExistsError(f"movie output appeared during encoding; refusing to replace: {out}") from exc
        else:
            temp.unlink()
        print(f"encoded and verified {FRAME_END} frames: {out}")
        print(f"source manifest: {sidecar}")
    finally:
        if temp.exists():
            temp.unlink()


def main() -> int:
    args = parser().parse_args()
    try:
        encode(args)
    except Exception as exc:
        print(f"encode.py: error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
