"""Render a saved EP11 v03 Blender scene into a resumable PNG sequence.

Launch through Blender with factory startup and auto-execution disabled, for
example::

    blender --background --factory-startup --disable-autoexec \
      --python render_saved.py -- --blend scene.blend --out /Volumes/AgentDev/Scratch/ep11-v03

The output directory must already exist below /Volumes/AgentDev/Scratch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import stat
import sys
import time
from pathlib import Path
from typing import Any


FRAME_START = 1
FRAME_END = 1525
SOURCE_FPS = 30
FILM_FPS = 60
FILM_FRAME_START = 550
OUTPUT_ROOT = Path("/Volumes/AgentDev/Scratch")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Render the exact saved Blender scene into resumable PNG frames.",
        epilog=(
            "Run with Blender --background --factory-startup --disable-autoexec; "
            "--out must be an existing dedicated directory below "
            "/Volumes/AgentDev/Scratch."
        ),
    )
    p.add_argument("--blend", required=True, help="Exact saved .blend file to open")
    p.add_argument("--out", required=True, help="Existing dedicated Scratch output directory")
    p.add_argument("--start", type=int, default=FRAME_START, help="First inclusive scene frame")
    p.add_argument("--end", type=int, default=FRAME_END, help="Last inclusive scene frame")
    p.add_argument("--width", type=int, default=2160)
    p.add_argument("--height", type=int, default=3840)
    p.add_argument("--samples", type=int, default=32)
    p.add_argument(
        "--engine",
        choices=("CYCLES", "BLENDER_EEVEE_NEXT"),
        default="BLENDER_EEVEE_NEXT",
    )
    p.add_argument(
        "--frames",
        help="Optional comma-separated frame subset for focused runs, e.g. 1,760,1525",
    )
    return p


def script_args(argv: list[str]) -> list[str]:
    """Return arguments after Blender's -- separator or normal Python argv."""
    if "--" in argv:
        return argv[argv.index("--") + 1 :]
    return argv[1:]


def selected_frames(args: argparse.Namespace, p: argparse.ArgumentParser) -> list[int]:
    if args.start < FRAME_START or args.end > FRAME_END or args.start > args.end:
        p.error(f"--start/--end must select frames inside {FRAME_START}..{FRAME_END}")
    if args.width <= 0 or args.height <= 0 or args.samples <= 0:
        p.error("--width, --height, and --samples must be positive integers")
    if not args.frames:
        return list(range(args.start, args.end + 1))
    try:
        frames = [int(value.strip()) for value in args.frames.split(",") if value.strip()]
    except ValueError:
        p.error("--frames must be a comma-separated list of integers")
    if not frames:
        p.error("--frames must contain at least one frame")
    if len(frames) != len(set(frames)):
        p.error("--frames must not contain duplicates")
    if any(frame < args.start or frame > args.end for frame in frames):
        p.error("every --frames value must fall within --start..--end")
    return sorted(frames)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def checked_output_dir(value: str) -> Path:
    root = OUTPUT_ROOT.resolve(strict=True)
    out = Path(value).expanduser().resolve(strict=True)
    try:
        relative = out.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"--out must be below {root}; got {out}") from exc
    if not relative.parts:
        raise ValueError(f"--out must be a dedicated child directory below {root}")
    if not out.is_dir():
        raise ValueError(f"--out must already exist as a directory: {out}")
    return out


def png_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size <= 24:
            return None
        with path.open("rb") as f:
            header = f.read(24)
            f.seek(-12, 2)
            if f.read(12) != b"\x00\x00\x00\x00IEND\xaeB\x60\x82":
                return None
        if (
            len(header) != 24
            or header[:8] != PNG_SIGNATURE
            or int.from_bytes(header[8:12], "big") != 13
            or header[12:16] != b"IHDR"
        ):
            return None
        width = int.from_bytes(header[16:20], "big")
        height = int.from_bytes(header[20:24], "big")
        if width <= 0 or height <= 0:
            return None
        return width, height
    except OSError:
        return None


def valid_frame(path: Path, width: int, height: int) -> bool:
    return png_dimensions(path) == (width, height)


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def configure_scene(
    bpy: Any, args: argparse.Namespace, blend: Path, saved_blend_sha256: str
) -> tuple[Any, dict[str, Any]]:
    if "--factory-startup" not in sys.argv or "--disable-autoexec" not in sys.argv:
        raise RuntimeError(
            "launch Blender with --factory-startup and --disable-autoexec before --python"
        )

    # The caller supplies these flags; opening this exact file retains its native animation.
    bpy.ops.wm.open_mainfile(filepath=str(blend), load_ui=False, use_scripts=False)
    if sha256_file(blend) != saved_blend_sha256:
        raise RuntimeError("saved .blend changed while it was being opened")
    scene = bpy.context.scene
    if scene is None:
        raise RuntimeError("the saved .blend did not provide an active scene")
    if scene.frame_start != FRAME_START or scene.frame_end != FRAME_END:
        raise RuntimeError(
            f"saved scene frame range must be {FRAME_START}..{FRAME_END}; "
            f"found {scene.frame_start}..{scene.frame_end}"
        )
    fps = float(scene.render.fps) / float(scene.render.fps_base)
    if not math.isclose(fps, SOURCE_FPS, rel_tol=0.0, abs_tol=1e-9):
        raise RuntimeError(f"saved scene must run at {SOURCE_FPS} fps; found {fps:g}")
    film_frame_start = int(scene.get("film_frame_start", -1))
    saved_source_fps = float(scene.get("source_fps", -1))
    if film_frame_start != FILM_FRAME_START or not math.isclose(
        saved_source_fps, SOURCE_FPS, rel_tol=0.0, abs_tol=1e-9
    ):
        raise RuntimeError(
            "saved scene film mapping must record film_frame_start=550 and source_fps=30"
        )

    render = scene.render
    render.engine = args.engine
    render.resolution_x = args.width
    render.resolution_y = args.height
    render.resolution_percentage = 100
    render.fps = SOURCE_FPS
    render.fps_base = 1.0
    render.threads_mode = "FIXED"
    render.threads = 4
    render.image_settings.file_format = "PNG"
    render.image_settings.color_mode = "RGB"
    render.image_settings.color_depth = "8"

    if args.engine == "CYCLES":
        cycles_addon = bpy.context.preferences.addons.get("cycles")
        if cycles_addon is None:
            raise RuntimeError("Cycles add-on is unavailable in this Blender build")
        preferences = cycles_addon.preferences
        preferences.compute_device_type = "METAL"
        preferences.get_devices()
        metal_devices = [device for device in preferences.devices if device.type == "METAL"]
        if not metal_devices:
            raise RuntimeError("Cycles Metal was requested but no Metal device is available")
        for device in preferences.devices:
            device.use = device.type == "METAL"
        if not any(device.use and device.type == "METAL" for device in preferences.devices):
            raise RuntimeError("Cycles Metal was requested but no Metal device became active")
        scene.cycles.device = "GPU"
        scene.cycles.samples = args.samples
    else:
        eevee = getattr(scene, "eevee", None)
        if eevee is None or not hasattr(eevee, "taa_render_samples"):
            raise RuntimeError("BLENDER_EEVEE_NEXT render sample API is unavailable")
        eevee.taa_render_samples = args.samples

    guard = {
        "schema_version": 1,
        "blend": {"path": str(blend), "sha256": saved_blend_sha256},
        "scene": {
            "frame_start": FRAME_START,
            "frame_end": FRAME_END,
            "fps": SOURCE_FPS,
            "fps_base": 1.0,
            "source_fps": SOURCE_FPS,
            "film_frame_start": FILM_FRAME_START,
            "film_fps": FILM_FPS,
            "film_frame_end_exclusive": FILM_FRAME_START + FRAME_END * (FILM_FPS // SOURCE_FPS),
        },
        "render": {
            "width": args.width,
            "height": args.height,
            "resolution_percentage": 100,
            "engine": args.engine,
            "samples": args.samples,
            "threads": 4,
            "image_format": "PNG",
            "color_mode": "RGB",
            "color_depth": "8",
        },
        "blender": {"version": bpy.app.version_string},
    }
    return scene, guard


def establish_guard(out: Path, guard: dict[str, Any]) -> None:
    guard_path = out / "render-guard.json"
    if guard_path.exists():
        try:
            existing = json.loads(guard_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"existing render guard is unreadable: {guard_path}: {exc}") from exc
        if existing != guard:
            raise RuntimeError(
                "render guard mismatch: saved scene, dimensions, frame rate, engine, samples, "
                "or Blender version changed; use a new empty output directory"
            )
        return
    existing_entries = list(out.iterdir())
    if existing_entries:
        names = ", ".join(entry.name for entry in existing_entries[:5])
        raise RuntimeError(
            f"output directory has content but no render-guard.json ({names}); "
            "use an empty dedicated directory"
        )
    atomic_json(guard_path, guard)


def append_timing(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as log:
        log.write(json.dumps(record, sort_keys=True) + "\n")
        log.flush()


def render_frames(bpy: Any, scene: Any, out: Path, frames: list[int], args: argparse.Namespace) -> None:
    log_path = out / "render-times.jsonl"
    for frame in frames:
        destination = out / f"frame-{frame:04d}.png"
        if valid_frame(destination, args.width, args.height):
            append_timing(
                log_path,
                {
                    "frame": frame,
                    "status": "skipped_valid_existing",
                    "seconds": 0.0,
                    "path": str(destination),
                },
            )
            print(f"frame {frame}: valid prior PNG; skipped", flush=True)
            continue

        if destination.exists() or destination.is_symlink():
            if destination.is_dir() and not destination.is_symlink():
                raise RuntimeError(f"frame destination is a directory: {destination}")
            destination.unlink()
        scene.frame_set(frame)
        scene.render.filepath = str(destination)
        started = time.monotonic()
        bpy.ops.render.render(write_still=True)
        elapsed = time.monotonic() - started
        if not valid_frame(destination, args.width, args.height):
            raise RuntimeError(f"Blender did not produce a valid {args.width}x{args.height} PNG: {destination}")
        append_timing(
            log_path,
            {
                "frame": frame,
                "status": "rendered",
                "seconds": round(elapsed, 6),
                "bytes": destination.stat().st_size,
                "path": str(destination),
            },
        )
        print(f"frame {frame}: rendered in {elapsed:.2f}s", flush=True)


def main() -> int:
    p = parser()
    args = p.parse_args(script_args(sys.argv))
    frames = selected_frames(args, p)
    try:
        blend = Path(args.blend).expanduser().resolve(strict=True)
        if not blend.is_file() or blend.suffix.lower() != ".blend":
            raise ValueError(f"--blend must name an existing .blend file: {blend}")
        saved_blend_sha256 = sha256_file(blend)
        out = checked_output_dir(args.out)
        import bpy  # Blender's bundled Python module is unavailable in normal Python.

        scene, guard = configure_scene(bpy, args, blend, saved_blend_sha256)
        establish_guard(out, guard)
        render_frames(bpy, scene, out, frames, args)
    except Exception as exc:
        print(f"render_saved.py: error: {exc}", file=sys.stderr, flush=True)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
