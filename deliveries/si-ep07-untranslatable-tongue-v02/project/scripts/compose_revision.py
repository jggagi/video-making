#!/usr/bin/env python3
"""Compose the v02 master audio and subtitle-band patches over the v01 finals.

The base movies are SHA-256 pinned to the already-reviewed v01 files. Only the
manifest-selected v02 movie is published, and it is created through an owned
temporary file followed by a no-clobber atomic link.
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import wave
from typing import Any


DELIVERY_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = DELIVERY_DIR / "project"
PREVIOUS_DELIVERY_DIR = DELIVERY_DIR.parent / "si-ep07-untranslatable-tongue"
MANIFEST_PATH = DELIVERY_DIR / "delivery.json"
PREVIOUS_MANIFEST_PATH = PREVIOUS_DELIVERY_DIR / "delivery.json"
MASTER_PATH = PROJECT_DIR / "public/audio/master.wav"
EXPECTED_BASE_SHA256 = {
    "bilibili": "4ff0e36dbd83474ff8af2524d32d5ae9a7d2c4d4e0e8040282ee1cfdee52accb",
    "xiaohongshu": "8bf20c0583cc289fbb5f43391d6c9a0ebaa9e01b641d7b37b0df9e0e03708852",
}
SPECS = {
    "bilibili": {"width": 3840, "height": 2160, "patch_height": 360, "patch_y": 1800, "layout": "landscape"},
    "xiaohongshu": {"width": 2160, "height": 3840, "patch_height": 360, "patch_y": 2700, "layout": "portrait"},
}
FPS = 60
FRAMES = 7200
DURATION_SECONDS = 120
SAMPLE_RATE = 48_000
SAMPLE_FRAMES = DURATION_SECONDS * SAMPLE_RATE


class ComposeError(RuntimeError):
    """A supplied media identity or stream does not meet the compose contract."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", choices=("all", "portrait", "landscape"), default="all", help="compose both platforms serially, or one completed platform")
    parser.add_argument("--portrait-patch", type=Path, help="silent 2160x360, 7200-frame portrait patch MP4")
    parser.add_argument("--landscape-patch", type=Path, help="silent 3840x360, 7200-frame landscape patch MP4")
    parser.add_argument("--ffmpeg", help="FFmpeg executable (default: PATH lookup)")
    parser.add_argument("--ffprobe", help="FFprobe executable (default: PATH lookup)")
    return parser.parse_args()


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ComposeError(f"cannot read {label}: {exc}") from None
    if not isinstance(data, dict):
        raise ComposeError(f"{label} must be a JSON object")
    return data


def contained_file(base: Path, relative: Any, label: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ComposeError(f"{label} path is missing")
    base = base.resolve()
    candidate = (base / relative).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        raise ComposeError(f"{label} path escapes its delivery directory") from None
    require_regular_file(candidate, label)
    return candidate


def manifest_output_path(manifest: dict[str, Any], key: str) -> Path:
    outputs = manifest.get("outputs")
    spec = outputs.get(key) if isinstance(outputs, dict) else None
    value = spec.get("path") if isinstance(spec, dict) else None
    if not isinstance(value, str) or not value:
        raise ComposeError(f"v02 manifest outputs.{key}.path is missing")
    base = DELIVERY_DIR.resolve()
    path = (DELIVERY_DIR / value).resolve()
    try:
        path.relative_to(base)
    except ValueError:
        raise ComposeError(f"v02 manifest output for {key} escapes the delivery") from None
    if path.exists():
        require_regular_file(path, f"existing formal v02 {key} output")
    return path


def require_regular_file(path: Path, label: str) -> None:
    try:
        mode = path.lstat().st_mode
    except OSError as exc:
        raise ComposeError(f"cannot inspect {label} at {path}: {exc}") from None
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise ComposeError(f"{label} must be a regular non-symlink file: {path}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise ComposeError(f"cannot hash {path}: {exc}") from None
    return digest.hexdigest()


def file_identity(path: Path) -> tuple[int, str]:
    return path.stat().st_size, sha256_file(path)


def require_tool(explicit: str | None, name: str) -> str:
    executable = explicit or shutil.which(name)
    if not executable:
        raise ComposeError(f"required executable is unavailable: {name}")
    return executable


def run_capture(argv: list[str], label: str, timeout: int = 1800) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ComposeError(f"{label} could not complete: {exc}") from None
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()[-2000:]
        raise ComposeError(f"{label} failed ({result.returncode}): {detail or 'no diagnostics'}")
    return result


def probe(ffprobe: str, path: Path, label: str) -> dict[str, Any]:
    result = run_capture(
        [ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        f"ffprobe {label}", timeout=90,
    )
    try:
        info = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise ComposeError(f"ffprobe returned invalid JSON for {label}") from None
    if not isinstance(info, dict) or not isinstance(info.get("streams"), list):
        raise ComposeError(f"ffprobe returned incomplete metadata for {label}")
    return info


def video_stream(info: dict[str, Any], label: str) -> dict[str, Any]:
    stream = next((item for item in info["streams"] if item.get("codec_type") == "video"), None)
    if stream is None:
        raise ComposeError(f"{label} has no video stream")
    return stream


def rate(value: Any, label: str) -> Fraction:
    try:
        return Fraction(str(value))
    except (ValueError, ZeroDivisionError, TypeError):
        raise ComposeError(f"{label} has an invalid frame rate: {value!r}") from None


def check_video(
    info: dict[str, Any], *, label: str, width: int, height: int,
    expect_audio: bool, require_bt709: bool = False,
) -> dict[str, Any]:
    stream = video_stream(info, label)
    if (stream.get("width"), stream.get("height")) != (width, height):
        raise ComposeError(f"{label} dimensions are {stream.get('width')}x{stream.get('height')}; expected {width}x{height}")
    for key in ("avg_frame_rate", "r_frame_rate"):
        if rate(stream.get(key), f"{label} {key}") != FPS:
            raise ComposeError(f"{label} {key} must be {FPS}/1; got {stream.get(key)}")
    try:
        frame_count = int(stream.get("nb_frames", ""))
        duration = float(stream.get("duration", info.get("format", {}).get("duration", "nan")))
    except (TypeError, ValueError):
        raise ComposeError(f"{label} must expose frame count and duration in ffprobe metadata") from None
    if frame_count != FRAMES:
        raise ComposeError(f"{label} contains {frame_count} frames; expected {FRAMES}")
    if not math.isfinite(duration) or abs(duration - DURATION_SECONDS) > 1 / FPS:
        raise ComposeError(f"{label} duration is {duration}; expected {DURATION_SECONDS} seconds")
    audio_streams = [item for item in info["streams"] if item.get("codec_type") == "audio"]
    if expect_audio and not audio_streams:
        raise ComposeError(f"{label} has no audio stream")
    if not expect_audio and audio_streams:
        raise ComposeError(f"{label} must be silent; found {len(audio_streams)} audio stream(s)")
    if require_bt709:
        for field, expected in (("pix_fmt", "yuv420p"), ("color_primaries", "bt709"), ("color_transfer", "bt709"), ("color_space", "bt709"), ("color_range", "tv")):
            if stream.get(field) != expected:
                raise ComposeError(f"{label} {field} is {stream.get(field)!r}; expected {expected!r}")
    return stream


def inspect_master(path: Path) -> dict[str, Any]:
    try:
        with wave.open(str(path), "rb") as wav:
            details = {
                "sample_rate_hz": wav.getframerate(),
                "channels": wav.getnchannels(),
                "sample_frames_per_channel": wav.getnframes(),
                "sample_width_bytes": wav.getsampwidth(),
                "compression_type": wav.getcomptype(),
            }
    except (OSError, wave.Error) as exc:
        raise ComposeError(f"cannot inspect shared PCM master: {exc}") from None
    if details["sample_rate_hz"] != SAMPLE_RATE or details["channels"] != 2 or details["sample_frames_per_channel"] != SAMPLE_FRAMES or details["compression_type"] != "NONE":
        raise ComposeError(f"shared master must be 120s 48kHz stereo PCM: got {details}")
    return {**details, "size_bytes": path.stat().st_size, "sha256": sha256_file(path)}


def compose_one(
    *, key: str, base: Path, base_identity_expected: tuple[int, str], patch: Path,
    patch_identity_expected: tuple[int, str], master: Path, master_identity_expected: tuple[int, str], output: Path,
    ffmpeg: str, ffprobe: str, manifest: dict[str, Any],
) -> dict[str, Any]:
    spec = SPECS[key]
    output_spec = manifest.get("outputs", {}).get(key)
    if not isinstance(output_spec, dict) or (output_spec.get("width"), output_spec.get("height")) != (spec["width"], spec["height"]):
        raise ComposeError(f"v02 manifest outputs.{key} does not match the required native dimensions")
    try:
        output.relative_to(DELIVERY_DIR.resolve())
    except ValueError:
        raise ComposeError(f"manifest output for {key} escapes the v02 delivery") from None

    base_identity = file_identity(base)
    if base_identity != base_identity_expected or base_identity[1] != EXPECTED_BASE_SHA256[key]:
        raise ComposeError(f"pinned v01 {key} SHA-256 mismatch: {base_identity[1]}")
    base_info = probe(ffprobe, base, f"v01 {key} base")
    check_video(base_info, label=f"v01 {key} base", width=spec["width"], height=spec["height"], expect_audio=True)

    patch_identity = file_identity(patch)
    if patch_identity != patch_identity_expected:
        raise ComposeError(f"v02 {key} caption patch changed after preflight")
    master_identity = file_identity(master)
    if master_identity != master_identity_expected:
        raise ComposeError("v02 shared PCM master changed after preflight")
    patch_info = probe(ffprobe, patch, f"v02 {key} silent caption patch")
    check_video(patch_info, label=f"v02 {key} caption patch", width=spec["width"], height=spec["patch_height"], expect_audio=False)

    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{output.stem}.compose-", suffix=".partial.mp4", dir=output.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        filter_graph = f"[0:v:0][1:v:0]overlay=x=0:y={spec['patch_y']}:eval=init:shortest=1:repeatlast=0:format=auto[v]"
        argv = [
            ffmpeg, "-hide_banner", "-nostdin", "-y",
            "-i", str(base), "-i", str(patch), "-i", str(master),
            "-filter_complex", filter_graph,
            "-map", "[v]", "-map", "2:a:0",
            "-t", str(DURATION_SECONDS), "-frames:v", str(FRAMES), "-r", str(FPS), "-fps_mode", "cfr",
            "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-pix_fmt", "yuv420p",
            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv",
            "-c:a", "aac", "-b:a", "320k", "-ar", str(SAMPLE_RATE), "-ac", "2",
            "-movflags", "+faststart",
            "-metadata", f"title={manifest.get('title', 'EP07')}",
            "-metadata", "comment=v02 series-voice revision; image base is SHA-pinned v01; subtitle band replaced from measured timing; audio is v02 master PCM",
            str(temporary),
        ]
        run_capture(argv, f"compose v02 {key} final", timeout=7200)
        final_info = probe(ffprobe, temporary, f"composed v02 {key}")
        output_video = check_video(
            final_info, label=f"composed v02 {key}", width=spec["width"], height=spec["height"],
            expect_audio=True, require_bt709=True,
        )
        audio = next(item for item in final_info["streams"] if item.get("codec_type") == "audio")
        if str(audio.get("sample_rate")) != str(SAMPLE_RATE) or int(audio.get("channels", 0)) != 2:
            raise ComposeError(f"composed v02 {key} audio is not 48kHz stereo")
        if (base.stat().st_size, sha256_file(base)) != base_identity:
            raise ComposeError(f"pinned v01 {key} source changed while composing")
        if (patch.stat().st_size, sha256_file(patch)) != patch_identity:
            raise ComposeError(f"v02 {key} caption patch changed while composing")
        if file_identity(master) != master_identity:
            raise ComposeError("v02 shared PCM master changed while composing")

        output_hash = sha256_file(temporary)
        if output.exists():
            if not output.is_file() or output.is_symlink():
                raise ComposeError(f"formal v02 output path is not a regular file: {output}")
            existing_hash = sha256_file(output)
            if existing_hash != output_hash:
                raise ComposeError(f"refusing to replace divergent formal v02 file {output} (existing SHA-256 {existing_hash})")
            temporary.unlink()
            state = "existing identical formal file retained"
        else:
            try:
                os.link(temporary, output)
            except FileExistsError:
                existing_hash = sha256_file(output) if output.is_file() and not output.is_symlink() else "not-a-regular-file"
                if existing_hash != output_hash:
                    raise ComposeError(f"formal v02 output appeared during compose and differs: {output}") from None
                state = "concurrent identical formal file retained"
            else:
                state = "new formal file published atomically"
            temporary.unlink(missing_ok=True)

        # Re-probe the manifest-selected output after publication, and recheck its identity.
        published_info = probe(ffprobe, output, f"published v02 {key}")
        published_video = check_video(
            published_info, label=f"published v02 {key}", width=spec["width"], height=spec["height"],
            expect_audio=True, require_bt709=True,
        )
        published_hash = sha256_file(output)
        if published_hash != output_hash:
            raise ComposeError(f"published v02 {key} identity changed after compose")
        if published_video.get("nb_frames") != output_video.get("nb_frames"):
            raise ComposeError(f"published v02 {key} frame count changed after compose")
        return {
            "layout": spec["layout"],
            "output": str(output.relative_to(DELIVERY_DIR)),
            "state": state,
            "sha256": published_hash,
            "size_bytes": output.stat().st_size,
            "base_sha256": base_identity[1],
            "patch_sha256": patch_identity[1],
            "video": {
                "width": published_video["width"],
                "height": published_video["height"],
                "fps": published_video["avg_frame_rate"],
                "frames": int(published_video["nb_frames"]),
                "duration_seconds": float(published_video["duration"]),
                "pixel_format": published_video.get("pix_fmt"),
                "color_range": published_video.get("color_range"),
                "color_primaries": published_video.get("color_primaries"),
                "color_transfer": published_video.get("color_transfer"),
                "color_space": published_video.get("color_space"),
            },
            "audio": {"sample_rate_hz": int(audio["sample_rate"]), "channels": int(audio["channels"]), "codec": audio.get("codec_name"), "source": "v02 shared master.wav; v01 base audio is not mapped"},
        }
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    args = parse_args()
    try:
        selected_keys = tuple(key for key in ("xiaohongshu", "bilibili")
                              if args.layout == "all" or SPECS[key]["layout"] == args.layout)
        selected_specs = {key: SPECS[key] for key in selected_keys}
        manifest = read_json(MANIFEST_PATH, "v02 delivery.json")
        previous = read_json(PREVIOUS_MANIFEST_PATH, "v01 delivery.json")
        if manifest.get("duration_seconds") != DURATION_SECONDS or manifest.get("fps") != FPS or manifest.get("total_frames") != FRAMES:
            raise ComposeError("v02 manifest must declare 120 seconds, 60 fps, and 7200 frames")
        previous_outputs = previous.get("outputs")
        if not isinstance(previous_outputs, dict):
            raise ComposeError("v01 delivery manifest has no outputs object")
        bases = {
            key: contained_file(PREVIOUS_DELIVERY_DIR, previous_outputs.get(key, {}).get("path"), f"v01 {key} final")
            for key in selected_specs
        }
        base_identities = {}
        for key, base in bases.items():
            identity = file_identity(base)
            base_identities[key] = identity
            if identity[1] != EXPECTED_BASE_SHA256[key]:
                raise ComposeError(f"pinned v01 {key} SHA-256 mismatch: {identity[1]}")
        requested_patches = {"xiaohongshu": args.portrait_patch, "bilibili": args.landscape_patch}
        if any(requested_patches[key] is None for key in selected_keys):
            raise ComposeError("each selected platform requires its corresponding --portrait-patch/--landscape-patch")
        patches = {key: requested_patches[key].resolve() for key in selected_keys}
        for key, patch in patches.items():
            require_regular_file(patch, f"v02 {key} silent patch")
        patch_identities = {key: file_identity(patch) for key, patch in patches.items()}
        require_regular_file(MASTER_PATH, "v02 shared PCM master")
        master_metadata = inspect_master(MASTER_PATH)
        master_identity = (master_metadata["size_bytes"], master_metadata["sha256"])
        ffmpeg = require_tool(args.ffmpeg, "ffmpeg")
        ffprobe = require_tool(args.ffprobe, "ffprobe")

        output_paths = {key: manifest_output_path(manifest, key) for key in selected_specs}
        if len(set(output_paths.values())) != len(output_paths):
            raise ComposeError("v02 manifest platform outputs must resolve to distinct files")
        outputs = manifest.get("outputs")
        for key, spec in selected_specs.items():
            output_spec = outputs.get(key) if isinstance(outputs, dict) else None
            if not isinstance(output_spec, dict) or (output_spec.get("width"), output_spec.get("height")) != (spec["width"], spec["height"]):
                raise ComposeError(f"v02 manifest outputs.{key} must declare {spec['width']}x{spec['height']}")
        # Preflight all inputs for every selected platform before starting an encoder.
        for key, base in bases.items():
            spec = SPECS[key]
            base_info = probe(ffprobe, base, f"v01 {key} base")
            check_video(base_info, label=f"v01 {key} base", width=spec["width"], height=spec["height"], expect_audio=True)
            patch_info = probe(ffprobe, patches[key], f"v02 {key} silent caption patch")
            check_video(patch_info, label=f"v02 {key} caption patch", width=spec["width"], height=spec["patch_height"], expect_audio=False)
            if file_identity(patches[key]) != patch_identities[key]:
                raise ComposeError(f"v02 {key} caption patch changed during preflight")

        results = []
        for key in selected_keys:
            results.append(compose_one(
                key=key, base=bases[key], base_identity_expected=base_identities[key], patch=patches[key],
                patch_identity_expected=patch_identities[key], master=MASTER_PATH,
                master_identity_expected=master_identity, output=output_paths[key], ffmpeg=ffmpeg,
                ffprobe=ffprobe, manifest=manifest,
            ))
        print(json.dumps({"status": "composed", "master": {"path": str(MASTER_PATH.relative_to(DELIVERY_DIR)), **master_metadata}, "outputs": results}, ensure_ascii=False, indent=2))
        return 0
    except (ComposeError, OSError, ValueError, TypeError) as exc:
        print(f"[compose-revision] ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
