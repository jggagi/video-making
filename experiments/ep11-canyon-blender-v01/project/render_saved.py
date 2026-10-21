#!/usr/bin/env python3
"""Render frames from an existing EP11 study .blend without rebuilding it.

Example (run only after checking the AgentDev volume and creating an empty
output directory there)::

    blender --background --python render_saved.py -- \
      --blend /path/inside/video/repo/porcelain-canyon.blend \
      --out /Volumes/AgentDev/ep11-canyon-frames --frames 1-192

This runner deliberately keeps the saved scene's camera, animation, materials,
color management, motion blur, and lighting.  It only sets the requested output
dimensions, frame rate, Cycles engine/device, sample count, and PNG output.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import struct
import sys
import time
import uuid
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
AGENTDEV_MOUNT = Path("/Volumes/AgentDev")
REPORT_NAME = "render-report.json"
LOCK_NAME = ".render_saved.lock"
REPORT_SCHEMA = "ep11-blender-saved-render/v1"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class RenderRunnerError(RuntimeError):
    """A safe preflight, integrity, or render-output failure."""


def parse_frames(value: str) -> list[int]:
    """Parse an inclusive comma-separated frame list/range expression."""
    frames: list[int] = []
    for raw_part in value.split(","):
        part = raw_part.strip()
        if not part:
            raise argparse.ArgumentTypeError("--frames contains an empty item")
        if "-" in part:
            bounds = part.split("-")
            if len(bounds) != 2 or not all(piece.isdecimal() for piece in bounds):
                raise argparse.ArgumentTypeError(
                    f"invalid frame range {part!r}; use N-M or N"
                )
            first, last = map(int, bounds)
            if first > last:
                raise argparse.ArgumentTypeError(
                    f"descending frame range is not allowed: {part!r}"
                )
            frames.extend(range(first, last + 1))
        else:
            if not part.isdecimal():
                raise argparse.ArgumentTypeError(
                    f"invalid frame number {part!r}; use N-M or N"
                )
            frames.append(int(part))
    if not frames:
        raise argparse.ArgumentTypeError("--frames must select at least one frame")
    if any(frame < 1 or frame > 192 for frame in frames):
        raise argparse.ArgumentTypeError("frames must be within the study range 1-192")
    if len(set(frames)) != len(frames):
        raise argparse.ArgumentTypeError("--frames must not select a frame more than once")
    return frames


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render selected frames from a saved Blender 4.5 study scene."
    )
    parser.add_argument("--blend", required=True, help="existing .blend inside this repository")
    parser.add_argument("--out", required=True, help="existing empty/resumable directory on AgentDev")
    parser.add_argument("--frames", type=parse_frames, default=parse_frames("1-192"),
                        help="frames, such as 1-192 or 1,24,48-72 (default: 1-192)")
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--samples", type=int, default=48)
    parser.add_argument("--resume", action="store_true",
                        help="resume only when report and all existing frames verify exactly")
    return parser


def script_arguments(argv: list[str]) -> list[str]:
    """Strip Blender's own options when invoked as --python script.py -- ..."""
    if "--" in argv:
        return argv[argv.index("--") + 1 :]
    return argv[1:]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_blend_path(value: str) -> Path:
    requested = Path(value).expanduser()
    if requested.is_symlink():
        raise RenderRunnerError("--blend must not be a symlink")
    try:
        blend = requested.resolve(strict=True)
    except OSError as error:
        raise RenderRunnerError(f"Cannot resolve --blend: {error}") from error
    if not blend.is_file() or blend.suffix.lower() != ".blend":
        raise RenderRunnerError("--blend must name an existing regular .blend file")
    try:
        blend.relative_to(REPO_ROOT)
    except ValueError as error:
        raise RenderRunnerError("--blend must be inside the video repository") from error
    return blend


def safe_output_directory(value: str) -> Path:
    requested = Path(value).expanduser()
    if requested.is_symlink():
        raise RenderRunnerError("--out must not be a symlink")
    if not AGENTDEV_MOUNT.is_mount():
        raise RenderRunnerError(
            f"{AGENTDEV_MOUNT} is not mounted; verify the AgentDev volume before rendering"
        )
    try:
        mount = AGENTDEV_MOUNT.resolve(strict=True)
        output = requested.resolve(strict=True)
    except OSError as error:
        raise RenderRunnerError(f"Cannot resolve --out or AgentDev mount: {error}") from error
    if not output.is_dir():
        raise RenderRunnerError("--out must be an existing directory; this runner does not create it")
    try:
        relative = output.relative_to(mount)
    except ValueError as error:
        raise RenderRunnerError(f"--out must be beneath {mount}") from error
    if not relative.parts:
        raise RenderRunnerError("--out must be a dedicated child directory, not the AgentDev mount root")
    if os.stat(output).st_dev != os.stat(mount).st_dev:
        raise RenderRunnerError("--out resolves to a different filesystem than AgentDev")
    return output


def acquire_lock(output: Path) -> tuple[int, tuple[int, int]]:
    lock = output / LOCK_NAME
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise RenderRunnerError(
            f"Render lock already exists: {lock}; inspect the process before removing a stale lock"
        ) from error
    payload = json.dumps({"pid": os.getpid(), "started_at_utc": utc_now()}).encode("utf-8")
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
        info = os.fstat(descriptor)
        return descriptor, (info.st_dev, info.st_ino)
    except BaseException:
        os.close(descriptor)
        try:
            lock.unlink()
        except OSError:
            pass
        raise


def release_lock(output: Path, lock_info: tuple[int, int]) -> None:
    lock = output / LOCK_NAME
    try:
        current = lock.stat(follow_symlinks=False)
        if (current.st_dev, current.st_ino) == lock_info:
            lock.unlink()
    except FileNotFoundError:
        pass


def png_dimensions(path: Path) -> tuple[int, int]:
    if path.is_symlink() or not path.is_file():
        raise RenderRunnerError(f"Expected a regular, non-symlink PNG: {path.name}")
    try:
        with path.open("rb") as image:
            header = image.read(24)
    except OSError as error:
        raise RenderRunnerError(f"Cannot read {path.name}: {error}") from error
    if len(header) != 24 or header[:8] != PNG_SIGNATURE or header[12:16] != b"IHDR":
        raise RenderRunnerError(f"Invalid PNG signature/IHDR in {path.name}")
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def validate_frame_file(path: Path, expected_width: int, expected_height: int) -> dict[str, Any]:
    width, height = png_dimensions(path)
    if (width, height) != (expected_width, expected_height):
        raise RenderRunnerError(
            f"{path.name} dimensions {width}x{height} do not match "
            f"{expected_width}x{expected_height}"
        )
    info = path.stat()
    if info.st_size <= 0:
        raise RenderRunnerError(f"{path.name} is empty")
    return {"bytes": info.st_size, "sha256": sha256_file(path), "dimensions": [width, height]}


def atomic_write_json(path: Path, payload: dict[str, Any], *, create_only: bool = False,
                      expected_sha256: str | None = None) -> str:
    """Durably replace a report, or create it without clobbering an existing one."""
    temporary = path.parent / f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "wb") as target:
            target.write(encoded)
            target.flush()
            os.fsync(target.fileno())
        if create_only:
            try:
                os.link(temporary, path)
            except FileExistsError as error:
                raise RenderRunnerError(f"Refusing to replace existing report: {path}") from error
            temporary.unlink()
        else:
            if path.is_symlink() or not path.is_file():
                raise RenderRunnerError(f"Report is no longer a regular file: {path}")
            if expected_sha256 is not None and sha256_file(path) != expected_sha256:
                raise RenderRunnerError("render-report.json changed during this run; refusing to overwrite it")
            os.replace(temporary, path)
        return sha256_file(path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def runtime_metadata(bpy: Any) -> dict[str, Any]:
    return {
        "blender_version": bpy.app.version_string,
        "blender_version_tuple": list(bpy.app.version),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
    }


def blender_scene_settings(scene: Any) -> dict[str, Any]:
    camera = scene.camera
    view = scene.view_settings
    return {
        "camera": camera.name if camera else None,
        "motion_blur_enabled": bool(scene.render.use_motion_blur),
        "motion_blur_shutter": float(scene.render.motion_blur_shutter),
        "view_transform": str(view.view_transform),
        "view_look": str(view.look),
        "view_exposure": float(view.exposure),
        "view_gamma": float(view.gamma),
        "display_device": str(scene.display_settings.display_device),
        "scene_frame_range": [int(scene.frame_start), int(scene.frame_end)],
        "denoiser": str(scene.cycles.denoiser),
    }


def configure_metal_or_cpu(bpy: Any, scene: Any) -> dict[str, Any]:
    """Use Metal if detected; otherwise explicitly render on CPU, never another GPU API."""
    addon = bpy.context.preferences.addons.get("cycles")
    preferences = addon.preferences if addon is not None else None
    metal_devices: list[Any] = []
    device_names: list[str] = []
    detection_error: str | None = None
    if preferences is not None:
        try:
            preferences.compute_device_type = "METAL"
            refresh = getattr(preferences, "refresh_devices", None)
            if callable(refresh):
                refresh()
            else:
                get_devices = getattr(preferences, "get_devices", None)
                if callable(get_devices):
                    get_devices()
            devices = getattr(preferences, "devices", ())
            flattened: list[Any] = []
            pending = list(devices) if devices is not None else []
            while pending:
                device = pending.pop(0)
                if getattr(device, "type", None) is not None:
                    flattened.append(device)
                elif isinstance(device, (tuple, list)):
                    pending[0:0] = list(device)
            metal_devices = [device for device in flattened if getattr(device, "type", "") == "METAL"]
            device_names = [str(getattr(device, "name", "Metal GPU")) for device in metal_devices]
            for device in flattened:
                device_type = getattr(device, "type", "")
                device.use = (
                    device_type == "METAL" if metal_devices else device_type == "CPU"
                )
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            detection_error = f"{type(error).__name__}: {error}"
            metal_devices = []
            device_names = []

    if metal_devices:
        scene.cycles.device = "GPU"
        return {"cycles_device": "GPU", "gpu_backend": "METAL", "gpu_devices": device_names,
                "device_detection_error": None}

    scene.cycles.device = "CPU"
    return {"cycles_device": "CPU", "gpu_backend": None, "gpu_devices": [],
            "device_detection_error": detection_error}


def load_and_configure_scene(blend: Path, args: argparse.Namespace, bpy: Any) -> tuple[Any, dict[str, Any]]:
    version = tuple(bpy.app.version[:2])
    if version != (4, 5):
        raise RenderRunnerError(f"Blender 4.5 is required; found {bpy.app.version_string}")
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    scene = bpy.context.scene
    if scene is None or scene.camera is None:
        raise RenderRunnerError("Saved .blend has no active scene camera")
    if scene.frame_start > min(args.frames) or scene.frame_end < max(args.frames):
        raise RenderRunnerError(
            f"Saved scene range {scene.frame_start}-{scene.frame_end} does not include all requested frames"
        )

    # These are output/render-contract settings. Saved camera, materials,
    # animation, lighting, color management and motion blur remain untouched.
    scene.render.engine = "CYCLES"
    scene.render.resolution_x = args.width
    scene.render.resolution_y = args.height
    scene.render.resolution_percentage = 100
    scene.render.fps = 24
    scene.render.fps_base = 1.0
    scene.cycles.samples = args.samples
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.use_file_extension = False
    device = configure_metal_or_cpu(bpy, scene)
    return scene, device


def make_config(args: argparse.Namespace, device: dict[str, Any]) -> dict[str, Any]:
    return {
        "frames": args.frames,
        "width": args.width,
        "height": args.height,
        "fps": 24,
        "fps_base": 1.0,
        "samples": args.samples,
        "engine": "CYCLES",
        "cycles_device": device["cycles_device"],
        "gpu_backend": device["gpu_backend"],
        "gpu_devices": device["gpu_devices"],
        "output_format": "PNG RGB 8-bit",
    }


def new_report(blend: Path, blend_sha256: str, args: argparse.Namespace,
               runtime: dict[str, Any], scene_settings: dict[str, Any],
               device: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": REPORT_SCHEMA,
        "status": "IN_PROGRESS",
        "created_at_utc": utc_now(),
        "updated_at_utc": utc_now(),
        "completed_at_utc": None,
        "blend_path": str(blend),
        "blend_sha256": blend_sha256,
        "runtime": runtime,
        "config": make_config(args, device),
        "scene_settings_preserved": scene_settings,
        "device_selection": device,
        "frames": [],
        "requested_frame_count": len(args.frames),
        "normal_human_acceptance": "NOT_RUN",
        "device_acceptance": "NOT_RUN",
    }


def read_resume_report(report_path: Path, blend_sha256: str, expected_config: dict[str, Any],
                       requested_frames: list[int], width: int, height: int) -> tuple[dict[str, Any], str]:
    if report_path.is_symlink() or not report_path.is_file():
        raise RenderRunnerError("--resume requires an existing regular render-report.json")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RenderRunnerError(f"Cannot read resume report: {error}") from error
    if not isinstance(report, dict) or report.get("schema") != REPORT_SCHEMA:
        raise RenderRunnerError("Existing report has an unsupported schema")
    if report.get("blend_sha256") != blend_sha256:
        raise RenderRunnerError("Existing report was created from a different .blend SHA-256")
    if report.get("config") != expected_config:
        raise RenderRunnerError("Resume configuration differs from the existing render report")
    records = report.get("frames")
    if not isinstance(records, list):
        raise RenderRunnerError("Resume report has an invalid frames list")
    frame_records: dict[int, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("frame"), int):
            raise RenderRunnerError("Resume report contains a malformed frame record")
        frame = record["frame"]
        if frame not in requested_frames or frame in frame_records:
            raise RenderRunnerError(f"Resume report contains an unexpected or duplicate frame: {frame}")
        if record.get("filename") != f"{frame:04d}.png":
            raise RenderRunnerError(f"Resume report has an unexpected filename for frame {frame}")
        frame_records[frame] = record

    expected_names = {f"{frame:04d}.png" for frame in requested_frames}
    actual_pngs = {path.name for path in report_path.parent.glob("*.png")}
    extras = actual_pngs - expected_names
    if extras:
        raise RenderRunnerError(f"Unexpected PNG files in output directory: {sorted(extras)}")
    for frame, record in frame_records.items():
        path = report_path.parent / f"{frame:04d}.png"
        measured = validate_frame_file(path, width, height)
        if measured["bytes"] != record.get("bytes"):
            raise RenderRunnerError(f"Recorded byte count does not match {path.name}")
        if measured["sha256"] != record.get("sha256"):
            raise RenderRunnerError(f"Recorded SHA-256 does not match {path.name}")
        if measured["dimensions"] != record.get("dimensions"):
            raise RenderRunnerError(f"Recorded dimensions do not match {path.name}")
    for frame in requested_frames:
        frame_path = report_path.parent / f"{frame:04d}.png"
        if frame_path.exists() and frame not in frame_records:
            raise RenderRunnerError(
                f"Unrecorded frame already exists: {frame_path.name}; refusing to overwrite it"
            )
    return report, sha256_file(report_path)


def initial_output_check(output: Path, resume: bool) -> None:
    entries = [path for path in output.iterdir() if path.name != LOCK_NAME]
    if not resume and entries:
        names = sorted(path.name for path in entries)
        raise RenderRunnerError(
            f"Refusing to write into a non-empty output directory: {names[:8]}"
        )


def render(args: argparse.Namespace, bpy: Any) -> Path:
    blend = safe_blend_path(args.blend)
    output = safe_output_directory(args.out)
    lock_fd, lock_info = acquire_lock(output)
    os.close(lock_fd)
    report_path = output / REPORT_NAME
    try:
        initial_output_check(output, args.resume)
        blend_sha256 = sha256_file(blend)
        scene, device = load_and_configure_scene(blend, args, bpy)
        config = make_config(args, device)
        runtime = runtime_metadata(bpy)
        scene_settings = blender_scene_settings(scene)

        if args.resume:
            report, report_sha256 = read_resume_report(
                report_path, blend_sha256, config, args.frames, args.width, args.height
            )
            if report.get("runtime") != runtime:
                raise RenderRunnerError("Blender/runtime differs from the existing render report")
            if report.get("scene_settings_preserved") != scene_settings:
                raise RenderRunnerError("Saved scene camera/color/motion settings differ from the report")
        else:
            report = new_report(blend, blend_sha256, args, runtime, scene_settings, device)
            report_sha256 = atomic_write_json(report_path, report, create_only=True)

        recorded = {item["frame"]: item for item in report["frames"]}
        for frame in args.frames:
            if frame in recorded:
                print(f"skip {frame:04d}.png (verified)", flush=True)
                continue
            destination = output / f"{frame:04d}.png"
            if destination.exists():
                raise RenderRunnerError(f"Refusing to replace existing frame: {destination.name}")
            scene.frame_set(frame, subframe=0.0)
            scene.render.filepath = str(destination)
            started = time.monotonic()
            bpy.ops.render.render(write_still=True)
            elapsed = time.monotonic() - started
            measured = validate_frame_file(destination, args.width, args.height)
            record = {
                "frame": frame,
                "filename": destination.name,
                "bytes": measured["bytes"],
                "sha256": measured["sha256"],
                "dimensions": measured["dimensions"],
                "render_seconds": round(elapsed, 6),
            }
            report["frames"].append(record)
            report["frames"].sort(key=lambda item: item["frame"])
            report["updated_at_utc"] = utc_now()
            report["status"] = "IN_PROGRESS"
            report["completed_at_utc"] = None
            report_sha256 = atomic_write_json(
                report_path, report, expected_sha256=report_sha256
            )
            print(f"rendered {destination.name} in {elapsed:.2f}s", flush=True)

        report["status"] = "COMPLETE"
        report["updated_at_utc"] = utc_now()
        report["completed_at_utc"] = utc_now()
        report_sha256 = atomic_write_json(report_path, report, expected_sha256=report_sha256)
        print(f"render report: {report_path} ({len(report['frames'])} verified frames)", flush=True)
        return report_path
    finally:
        release_lock(output, lock_info)


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    if argv is None:
        cli_args = script_arguments(sys.argv)
    elif "--" in argv:
        cli_args = script_arguments(argv)
    else:
        cli_args = argv
    args = parser.parse_args(cli_args)
    if args.width <= 0 or args.height <= 0:
        parser.error("--width and --height must be positive integers")
    if args.samples <= 0:
        parser.error("--samples must be a positive integer")
    try:
        import bpy  # type: ignore[import-not-found]
    except ImportError as error:
        raise RenderRunnerError(
            "Run this script with Blender's bundled Python: blender --background --python render_saved.py -- ..."
        ) from error
    render(args, bpy)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RenderRunnerError as error:
        print(f"render_saved: {error}", file=sys.stderr)
        raise SystemExit(2)
