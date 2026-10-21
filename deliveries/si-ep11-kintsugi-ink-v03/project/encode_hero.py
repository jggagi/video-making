"""Encode the corrected 231-frame native hero reassembly insert."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import sys
import uuid
from pathlib import Path
from typing import Any

import encode as encoder


SOURCE_FRAME_START = 1132
SOURCE_FRAME_END_INCLUSIVE = 1362
SOURCE_FRAME_END_EXCLUSIVE = SOURCE_FRAME_END_INCLUSIVE + 1
FRAME_COUNT = SOURCE_FRAME_END_EXCLUSIVE - SOURCE_FRAME_START
SOURCE_FPS = 30
FILM_FPS = 60
FILM_FRAME_START = 2812
FILM_FRAME_END_EXCLUSIVE = 3274
WIDTH = 2160
HEIGHT = 3840
FRAME_NAME_RE = re.compile(r"^frame-(\d{4})\.png$")
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
VIDEO_FILTER = (
    "scale=iw:ih:out_color_matrix=bt709:out_range=tv,format=yuv420p,"
    "setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709"
)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Validate and encode source frames 1132..1362 as the native 2160x3840, "
            "30 fps hero insert."
        )
    )
    p.add_argument(
        "--frames-dir",
        required=True,
        type=Path,
        help="Existing dedicated Blender render directory (with render-guard.json)",
    )
    p.add_argument("--out", required=True, type=Path, help="New .mp4 output path")
    return p


def validate_guard(frames_dir: Path) -> tuple[dict[str, Any], str, str, str]:
    guard, guard_sha = encoder.read_guard(frames_dir)
    render = guard["render"]
    if render.get("width") != WIDTH or render.get("height") != HEIGHT:
        raise ValueError(
            f"render guard must describe {WIDTH}x{HEIGHT} frames; found "
            f"{render.get('width')}x{render.get('height')}"
        )
    if render.get("engine") != "BLENDER_EEVEE_NEXT":
        raise ValueError(
            "render guard engine must be BLENDER_EEVEE_NEXT; "
            f"found {render.get('engine')!r}"
        )
    if render.get("samples") != 32:
        raise ValueError(f"render guard samples must be 32; found {render.get('samples')!r}")

    blend = guard.get("blend")
    if not isinstance(blend, dict):
        raise ValueError("render guard must identify its source Blender file")
    blend_path = blend.get("path")
    blend_sha = blend.get("sha256")
    if not isinstance(blend_path, str) or not blend_path:
        raise ValueError("render guard blend.path must be a non-empty path")
    if not isinstance(blend_sha, str) or SHA256_RE.fullmatch(blend_sha) is None:
        raise ValueError("render guard blend.sha256 must be a SHA-256 digest")
    source_blend = Path(blend_path).expanduser()
    if not source_blend.is_file():
        raise ValueError(f"guarded source Blender file is missing: {source_blend}")
    current_blend_sha = encoder.sha256_file(source_blend)
    if current_blend_sha.lower() != blend_sha.lower():
        raise ValueError(f"guarded source Blender file SHA-256 changed: {source_blend}")
    return guard, guard_sha, str(source_blend), current_blend_sha


def collect_hero_frames(frames_dir: Path) -> list[dict[str, Any]]:
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

    expected = set(range(SOURCE_FRAME_START, SOURCE_FRAME_END_EXCLUSIVE))
    missing = sorted(expected - set(actual))
    extra = sorted(set(actual) - expected)
    if missing or extra or unexpected or len(actual) != FRAME_COUNT:
        details = []
        if missing:
            details.append(f"missing {len(missing)} frames (first: {missing[:5]})")
        if extra:
            details.append(f"unexpected frame numbers: {extra[:5]}")
        if unexpected:
            details.append(f"unexpected frame names: {unexpected[:5]}")
        raise ValueError(
            "hero input must contain exactly frame-1132.png..frame-1362.png: "
            + "; ".join(details)
        )

    files: list[dict[str, Any]] = []
    for frame in range(SOURCE_FRAME_START, SOURCE_FRAME_END_EXCLUSIVE):
        path = actual[frame]
        if path.is_symlink():
            raise ValueError(f"symbolic-link PNG is not an accepted source frame: {path}")
        dimensions = encoder.png_dimensions(path)
        if dimensions != (WIDTH, HEIGHT):
            raise ValueError(
                f"{path.name} is {dimensions[0]}x{dimensions[1]}, expected {WIDTH}x{HEIGHT}"
            )
        files.append(
            {
                "frame": frame,
                "path": path.name,
                "bytes": path.stat().st_size,
                "width": WIDTH,
                "height": HEIGHT,
                "sha256": encoder.sha256_file(path),
            }
        )
    return files


def source_receipt(
    guard: dict[str, Any],
    guard_sha: str,
    blend_path: str,
    blend_sha: str,
    files: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source": {
            "render_guard_sha256": guard_sha,
            "blend_path": blend_path,
            "blend_sha256": blend_sha,
            "frame_count": len(files),
            "frame_start": SOURCE_FRAME_START,
            "frame_end_exclusive": SOURCE_FRAME_END_EXCLUSIVE,
            "width": WIDTH,
            "height": HEIGHT,
            "fps": SOURCE_FPS,
            "frame_duration": "1/30",
            "files": files,
        },
        "frame_mapping": {
            "source_frame_start": SOURCE_FRAME_START,
            "source_frame_end_inclusive": SOURCE_FRAME_END_INCLUSIVE,
            "source_frame_end_exclusive": SOURCE_FRAME_END_EXCLUSIVE,
            "source_fps": SOURCE_FPS,
            "film_frame_start": FILM_FRAME_START,
            "film_frame_end_exclusive": FILM_FRAME_END_EXCLUSIVE,
            "film_fps": FILM_FPS,
            "film_frame_step": FILM_FPS // SOURCE_FPS,
        },
    }


def is_regular_file(path: Path) -> bool:
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except FileNotFoundError:
        return False


def matching_existing_output(out: Path, sidecar: Path, source: dict[str, Any]) -> bool:
    if not is_regular_file(out) or not is_regular_file(sidecar):
        return False
    try:
        existing = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(existing, dict):
        return False
    if (
        existing.get("schema_version") != 1
        or existing.get("source") != source.get("source")
        or existing.get("frame_mapping") != source.get("frame_mapping")
    ):
        return False
    movie = existing.get("movie", {})
    expected_metadata = {
        "path": str(out),
        "bytes": out.stat().st_size,
        "codec": "h264",
        "width": WIDTH,
        "height": HEIGHT,
        "fps": SOURCE_FPS,
        "frame_count": FRAME_COUNT,
        "pix_fmt": "yuv420p",
        "color_primaries": "bt709",
        "color_transfer": "bt709",
        "color_space": "bt709",
    }
    if not isinstance(movie, dict) or any(movie.get(key) != value for key, value in expected_metadata.items()):
        return False
    digest = movie.get("sha256")
    if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None:
        return False
    try:
        return digest.lower() == encoder.sha256_file(out)
    except OSError:
        return False


def atomic_no_clobber_json(path: Path, value: dict[str, Any]) -> Path:
    temp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("x", encoding="utf-8") as output:
            output.write(json.dumps(value, indent=2, sort_keys=True) + "\n")
        return temp
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def encode_hero(args: argparse.Namespace) -> None:
    frames_dir = args.frames_dir.expanduser().resolve(strict=True)
    if not frames_dir.is_dir():
        raise ValueError(f"--frames-dir must be an existing directory: {frames_dir}")
    requested_out = args.out.expanduser()
    if not requested_out.is_absolute():
        requested_out = Path.cwd() / requested_out
    out = requested_out.parent.resolve(strict=True) / requested_out.name
    if out.suffix.lower() != ".mp4":
        raise ValueError("--out must have an .mp4 extension")
    if not out.parent.is_dir():
        raise ValueError(f"movie output parent must already exist: {out.parent}")

    guard, guard_sha, blend_path, blend_sha = validate_guard(frames_dir)
    files = collect_hero_frames(frames_dir)
    source = source_receipt(guard, guard_sha, blend_path, blend_sha, files)
    sidecar = frames_dir / "hero-footage.json"
    if out.exists() or out.is_symlink() or sidecar.exists() or sidecar.is_symlink():
        if matching_existing_output(out, sidecar, source):
            print(f"already verified: {out}")
            return
        raise FileExistsError(
            f"refusing to overwrite an existing movie or hero receipt: {out} / {sidecar}"
        )

    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("ffmpeg and ffprobe must both be available on PATH")
    temp_movie = out.with_name(f".{out.stem}.{os.getpid()}.{uuid.uuid4().hex}.tmp.mp4")
    temp_receipt: Path | None = None
    published_stat: os.stat_result | None = None
    try:
        encoder.run_checked(
            [
                ffmpeg,
                "-hide_banner",
                "-nostdin",
                "-y",
                "-framerate",
                str(SOURCE_FPS),
                "-start_number",
                str(SOURCE_FRAME_START),
                "-i",
                str(frames_dir / "frame-%04d.png"),
                "-frames:v",
                str(FRAME_COUNT),
                "-an",
                "-vf",
                VIDEO_FILTER,
                "-c:v",
                "libx264",
                "-threads",
                "4",
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
                str(temp_movie),
            ],
            "hero ffmpeg encode",
        )
        stream = encoder.ffprobe_movie(temp_movie, ffprobe, WIDTH, HEIGHT, expected_frames=FRAME_COUNT)
        encoder.strict_decode(temp_movie, ffmpeg)
        movie_sha = encoder.sha256_file(temp_movie)
        receipt = dict(source)
        receipt["movie"] = {
            "path": str(out),
            "sha256": movie_sha,
            "bytes": temp_movie.stat().st_size,
            "codec": stream["codec_name"],
            "width": WIDTH,
            "height": HEIGHT,
            "fps": SOURCE_FPS,
            "frame_count": FRAME_COUNT,
            "pix_fmt": stream["pix_fmt"],
            "color_primaries": stream["color_primaries"],
            "color_transfer": stream["color_transfer"],
            "color_space": stream["color_space"],
        }
        temp_receipt = atomic_no_clobber_json(sidecar, receipt)
        try:
            os.link(temp_movie, out)
            published_stat = out.lstat()
            os.link(temp_receipt, sidecar)
        except FileExistsError as exc:
            if published_stat is not None:
                try:
                    current = out.lstat()
                    if (current.st_dev, current.st_ino) == (published_stat.st_dev, published_stat.st_ino):
                        out.unlink()
                except FileNotFoundError:
                    pass
            raise FileExistsError(
                f"movie or hero receipt appeared during encoding; refusing to replace: {out} / {sidecar}"
            ) from exc
        except Exception:
            if published_stat is not None:
                try:
                    current = out.lstat()
                    if (current.st_dev, current.st_ino) == (published_stat.st_dev, published_stat.st_ino):
                        out.unlink()
                except FileNotFoundError:
                    pass
            raise
        else:
            temp_movie.unlink()
            print(f"encoded and verified {FRAME_COUNT} hero frames: {out}")
            print(f"source manifest: {sidecar}")
    finally:
        temp_movie.unlink(missing_ok=True)
        if temp_receipt is not None:
            temp_receipt.unlink(missing_ok=True)


def main() -> int:
    args = parser().parse_args()
    try:
        encode_hero(args)
    except Exception as exc:
        print(f"encode_hero.py: error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
