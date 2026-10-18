#!/usr/bin/env python3
"""Create a fresh, editable dual-platform video delivery workspace."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import sys
import unicodedata


FPS_CHOICES = (24, 25, 30, 50, 60)
AUDIO_MODES = ("narrated", "provided", "silent")


class InputError(ValueError):
    """A user-provided argument or source file is invalid."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Initialize a fresh 120-second B站 and 小红书 delivery folder."
    )
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--script", required=True, type=Path)
    parser.add_argument("--fps", type=int, choices=FPS_CHOICES, default=60)
    parser.add_argument(
        "--audio-mode", choices=AUDIO_MODES, default="narrated"
    )
    return parser.parse_args()


def validate_slug(slug: str) -> None:
    if not slug or slug in {".", ".."}:
        raise InputError("--slug must be one non-empty directory name.")
    if "/" in slug or "\\" in slug:
        raise InputError("--slug must not contain a slash or backslash.")
    if PureWindowsPath(slug).drive or PureWindowsPath(slug).root:
        raise InputError("--slug must not be an absolute path or drive-qualified name.")
    if any(unicodedata.category(char) in {"Cc", "Cf"} for char in slug):
        raise InputError("--slug must not contain control or format characters.")


def read_script(path: Path) -> bytes:
    try:
        source_bytes = path.expanduser().read_bytes()
    except OSError as exc:
        raise InputError(f"Cannot read --script {path}: {exc}") from None
    if not source_bytes:
        raise InputError("--script must be a non-empty UTF-8 file.")
    try:
        source_text = source_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise InputError(f"--script is not valid UTF-8: {exc}") from None
    if not source_text.strip():
        raise InputError("--script must contain non-whitespace text.")
    return source_bytes


def build_manifest(
    *, slug: str, title: str, fps: int, audio_mode: str, script_bytes: bytes
) -> dict:
    return {
        "schema_version": 1,
        "title": title,
        "slug": slug,
        "duration_seconds": 120,
        "fps": fps,
        "total_frames": 120 * fps,
        "script": {
            "path": "source/script.md",
            "sha256": hashlib.sha256(script_bytes).hexdigest(),
        },
        "audio": {
            "mode": audio_mode,
            "master": "project/public/audio/master.wav",
        },
        "outputs": {
            "bilibili": {
                "path": f"B站/{slug}-bilibili-120s-4k.mp4",
                "width": 3840,
                "height": 2160,
            },
            "xiaohongshu": {
                "path": f"小红书/{slug}-xiaohongshu-120s-portrait.mp4",
                "width": 1080,
                "height": 1920,
            },
        },
        "qa": {
            "automated": "pending",
            "representative_frames": "pending",
            "continuous_human_review": "pending",
            "target_device_playback": "pending",
        },
    }


def remove_created_items(
    target: Path, created_files: list[Path], created_dirs: list[Path]
) -> None:
    """Best-effort rollback without recursively deleting unexpected contents."""
    for path in reversed(created_files):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
    for path in reversed(created_dirs):
        try:
            path.rmdir()
        except OSError:
            pass
    try:
        target.rmdir()
    except OSError:
        pass


def create_delivery(args: argparse.Namespace) -> Path:
    validate_slug(args.slug)
    if not args.title.strip():
        raise InputError("--title must contain non-whitespace text.")
    if args.fps not in FPS_CHOICES:
        raise InputError(f"--fps must be one of {', '.join(map(str, FPS_CHOICES))}.")
    if args.audio_mode not in AUDIO_MODES:
        raise InputError(f"--audio-mode must be one of {', '.join(AUDIO_MODES)}.")

    # Read and validate every user-controlled input before creating directories.
    script_bytes = read_script(args.script)
    manifest = build_manifest(
        slug=args.slug,
        title=args.title,
        fps=args.fps,
        audio_mode=args.audio_mode,
        script_bytes=script_bytes,
    )
    manifest_bytes = (
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")

    try:
        output_root = args.output_root.expanduser().resolve(strict=False)
    except OSError as exc:
        raise InputError(f"Cannot resolve --output-root: {exc}") from None
    target = output_root / args.slug

    # lexists also catches a dangling symlink at the requested target.
    if os.path.lexists(target):
        raise InputError(f"Target already exists; refusing to modify it: {target}")
    if output_root.exists() and not output_root.is_dir():
        raise InputError(f"--output-root is not a directory: {output_root}")

    created_dirs: list[Path] = []
    created_files: list[Path] = []
    target_created = False
    try:
        output_root.mkdir(parents=True, exist_ok=True)
        if os.path.lexists(target):
            raise InputError(f"Target already exists; refusing to modify it: {target}")
        target.mkdir(exist_ok=False)
        target_created = True

        for name in ("source", "B站", "小红书", "project", "review"):
            directory = target / name
            directory.mkdir()
            created_dirs.append(directory)

        script_destination = target / "source" / "script.md"
        with script_destination.open("xb") as stream:
            created_files.append(script_destination)
            stream.write(script_bytes)

        manifest_destination = target / "delivery.json"
        with manifest_destination.open("xb") as stream:
            created_files.append(manifest_destination)
            stream.write(manifest_bytes)
        return target
    except Exception:
        if target_created:
            remove_created_items(target, created_files, created_dirs)
        raise


def main() -> int:
    args = parse_args()
    try:
        target = create_delivery(args)
    except (InputError, OSError) as exc:
        print(f"init_delivery.py: error: {exc}", file=sys.stderr)
        return 2
    print(f"Initialized delivery: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
