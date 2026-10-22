#!/usr/bin/env python3
"""Composite the validated EP16 hand redraw over its exact absolute frame range."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any


PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT.parent
REVIEW = WORK / "review"
ORIGINAL_POINTER = REVIEW / "render-staging.json"
PATCH_POINTER = REVIEW / "hand-redraw-staging.json"
PROVENANCE_PATH = REVIEW / "render-provenance.json"
REPORT_PATH = REVIEW / "hand-redraw-composite.json"
FIXTURE_DIR = REVIEW / "hand-redraw-fixture"
CANDIDATE_DIR = REVIEW / "candidate-01-rejected"
COMPOSITE_RANGE = (5580, 6359)
NATIVE_WIDTH = 2160
NATIVE_HEIGHT = 3840
FPS = 60
FRAME_COUNT = 7200
DURATION_SECONDS = 120
EXPECTED_MASTER = PROJECT / "public" / "audio" / "master.wav"


class CompositeError(RuntimeError):
    pass


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompositeError(f"cannot read {label}: {exc}") from None


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    if temporary.exists():
        raise CompositeError(f"metadata temporary already exists; preserved: {temporary}")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def command_output(command: list[str], label: str) -> str:
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if result.returncode:
        details = " | ".join((result.stderr or result.stdout or "").strip().splitlines()[-8:])
        raise CompositeError(f"{label} failed with exit {result.returncode}: {details}")
    return result.stdout


def ffmpeg_binary() -> str:
    binary = shutil.which("ffmpeg")
    if not binary:
        raise CompositeError("ffmpeg is unavailable")
    return binary


def ffprobe_binary() -> str:
    binary = shutil.which("ffprobe")
    if not binary:
        raise CompositeError("ffprobe is unavailable")
    return binary


def ensure_safe_source(pointer: dict[str, Any], label: str) -> tuple[Path, dict[str, Any]]:
    if pointer.get("status") != "READY":
        raise CompositeError(f"{label} staging pointer is not READY")
    raw_path = pointer.get("file")
    if not isinstance(raw_path, str):
        raise CompositeError(f"{label} staging pointer has no file path")
    path = Path(raw_path).resolve(strict=True)
    if not path.is_file():
        raise CompositeError(f"{label} staging path is not a file: {path}")
    actual_bytes = path.stat().st_size
    actual_hash = sha_file(path)
    if actual_hash != pointer.get("sha256") or actual_bytes != pointer.get("bytes"):
        raise CompositeError(f"{label} file hash/size does not match its READY pointer; source preserved")
    return path, {"path": str(path), "sha256": actual_hash, "bytes": actual_bytes}


def probe(path: Path) -> dict[str, Any]:
    payload = json.loads(command_output([
        ffprobe_binary(), "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(path),
    ], f"ffprobe {path.name}"))
    streams = payload.get("streams", [])
    video_streams = [item for item in streams if item.get("codec_type") == "video"]
    audio_streams = [item for item in streams if item.get("codec_type") == "audio"]
    if len(video_streams) != 1:
        raise CompositeError(f"{path.name} must contain exactly one video stream; found {len(video_streams)}")
    video = video_streams[0]
    frames_raw = video.get("nb_read_frames") or video.get("nb_frames")
    try:
        frames = int(frames_raw)
    except (TypeError, ValueError):
        raise CompositeError(f"{path.name} has no exact decoded frame count in ffprobe") from None
    duration = float(video.get("duration") or payload.get("format", {}).get("duration", 0.0))
    return {
        "file": str(path),
        "codec": video.get("codec_name"),
        "width": video.get("width"),
        "height": video.get("height"),
        "pixelFormat": video.get("pix_fmt"),
        "rFrameRate": video.get("r_frame_rate"),
        "avgFrameRate": video.get("avg_frame_rate"),
        "durationSeconds": duration,
        "frames": frames,
        "colorRange": video.get("color_range"),
        "colorSpace": video.get("color_space"),
        "colorTransfer": video.get("color_transfer"),
        "colorPrimaries": video.get("color_primaries"),
        "audioStreams": len(audio_streams),
        "allStreamTypes": [item.get("codec_type") for item in streams],
        "sizeBytes": path.stat().st_size,
    }


def assert_video_contract(metadata: dict[str, Any], *, frames: int, duration: int, label: str) -> None:
    if (metadata["width"], metadata["height"]) != (NATIVE_WIDTH, NATIVE_HEIGHT):
        raise CompositeError(f"{label} is {metadata['width']}x{metadata['height']}, expected {NATIVE_WIDTH}x{NATIVE_HEIGHT}")
    if metadata["frames"] != frames:
        raise CompositeError(f"{label} has {metadata['frames']} decoded frames, expected {frames}")
    if Fraction(metadata["rFrameRate"]) != Fraction(FPS, 1) or Fraction(metadata["avgFrameRate"]) != Fraction(FPS, 1):
        raise CompositeError(f"{label} frame rate is {metadata['rFrameRate']} / {metadata['avgFrameRate']}, expected {FPS}/1")
    if abs(float(metadata["durationSeconds"]) - duration) > 1.0 / FPS:
        raise CompositeError(f"{label} duration is {metadata['durationSeconds']}, expected {duration}s")
    if metadata["audioStreams"] != 0:
        raise CompositeError(f"{label} must remain video-only; found {metadata['audioStreams']} audio stream(s)")


def ppm_bytes(rgb: tuple[int, int, int]) -> bytes:
    return b"P6\n64 64\n255\n" + bytes(rgb) * (64 * 64)


def decode_fixture(path: Path) -> list[bytes]:
    raw = subprocess.run([
        ffmpeg_binary(), "-hide_banner", "-v", "error", "-xerror", "-i", str(path),
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-vsync", "0", "pipe:1",
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if raw.returncode:
        raise CompositeError("fixture RGB decode failed: " + raw.stderr.decode("utf-8", errors="replace")[-1000:])
    frame_bytes = 64 * 64 * 3
    if len(raw.stdout) != frame_bytes * 5:
        raise CompositeError(f"fixture decoded to {len(raw.stdout) // frame_bytes} complete frames, expected 5")
    return [raw.stdout[i * frame_bytes:(i + 1) * frame_bytes] for i in range(5)]


def max_rgb_delta(actual: bytes, expected: tuple[int, int, int]) -> int:
    return max(abs(value - expected[index % 3]) for index, value in enumerate(actual))


def verify_fixture_proof() -> dict[str, Any]:
    proof_path = FIXTURE_DIR / "fixture-proof.json"
    if not proof_path.is_file():
        raise CompositeError("isolated overlay fixture has not been run; run --fixture-only first")
    proof = read_json(proof_path, "fixture proof")
    if proof.get("status") != "PASSED" or proof.get("filter") != fixture_filter():
        raise CompositeError("saved isolated overlay fixture proof is missing or divergent")
    for filename, field in (("fixture-composite.mkv", "compositeSha256"), ("base_0.ppm", "baseFrame0Sha256"), ("patch_0.ppm", "patchFrame0Sha256")):
        path = FIXTURE_DIR / filename
        if not path.is_file() or sha_file(path) != proof.get(field):
            raise CompositeError(f"fixture artifact missing/divergent: {filename}")
    frames = decode_fixture(FIXTURE_DIR / "fixture-composite.mkv")
    expected = proof["expectedRgb"]
    deltas = [max_rgb_delta(frame, tuple(color)) for frame, color in zip(frames, expected)]
    if len(deltas) != 5 or max(deltas) > 3 or deltas != proof.get("maxPerFrameRgbDelta"):
        raise CompositeError(f"fixture proof no longer reproduces: RGB deltas {deltas}")
    if proof.get("replacedOutputFrames") != [2, 3] or proof.get("unchangedOutputFrames") != [0, 1, 4]:
        raise CompositeError("fixture proof does not establish the expected two-frame replacement range")
    return proof


def fixture_filter() -> str:
    return "[1:v]setpts=PTS+2/TB[p];[0:v][p]overlay=x=0:y=0:format=auto:eof_action=pass:repeatlast=0:enable='between(n,2,3)'[v]"


def run_fixture() -> dict[str, Any]:
    if FIXTURE_DIR.exists():
        raise CompositeError(f"fixture output directory already exists; preserving: {FIXTURE_DIR}")
    FIXTURE_DIR.mkdir(parents=True)
    base_colors = [(20, 30, 40), (50, 60, 70), (80, 90, 100), (110, 120, 130), (140, 150, 160)]
    patch_colors = [(201, 11, 21), (31, 211, 41)]
    for index, rgb in enumerate(base_colors):
        (FIXTURE_DIR / f"base_{index}.ppm").write_bytes(ppm_bytes(rgb))
    for index, rgb in enumerate(patch_colors):
        (FIXTURE_DIR / f"patch_{index}.ppm").write_bytes(ppm_bytes(rgb))
    base = FIXTURE_DIR / "base.mkv"
    patch = FIXTURE_DIR / "patch.mkv"
    composite = FIXTURE_DIR / "fixture-composite.mkv"
    common = ffmpeg_binary()
    command_output([common, "-hide_banner", "-v", "error", "-nostdin", "-n", "-framerate", "1", "-start_number", "0", "-i", str(FIXTURE_DIR / "base_%d.ppm"), "-frames:v", "5", "-c:v", "ffv1", "-level", "3", "-pix_fmt", "bgr0", str(base)], "FFV1 base fixture render")
    command_output([common, "-hide_banner", "-v", "error", "-nostdin", "-n", "-framerate", "1", "-start_number", "0", "-i", str(FIXTURE_DIR / "patch_%d.ppm"), "-frames:v", "2", "-c:v", "ffv1", "-level", "3", "-pix_fmt", "bgr0", str(patch)], "FFV1 patch fixture render")
    command_output([
        common, "-hide_banner", "-v", "error", "-nostdin", "-n", "-filter_complex_threads", "2",
        "-i", str(base), "-i", str(patch), "-filter_complex", fixture_filter(), "-map", "[v]", "-an",
        "-frames:v", "5", "-fps_mode", "passthrough", "-c:v", "ffv1", "-level", "3", "-pix_fmt", "bgr0", str(composite),
    ], "isolated 5-frame FFV1 overlay fixture")
    decoded = decode_fixture(composite)
    expected = [base_colors[0], base_colors[1], patch_colors[0], patch_colors[1], base_colors[4]]
    deltas = [max_rgb_delta(frame, color) for frame, color in zip(decoded, expected)]
    if max(deltas) > 3:
        raise CompositeError(f"isolated overlay fixture RGB mismatch: per-frame deltas {deltas}")
    base_probe = probe(base)
    patch_probe = probe(patch)
    composite_probe = probe(composite)
    if (base_probe["frames"], patch_probe["frames"], composite_probe["frames"]) != (5, 2, 5):
        raise CompositeError("FFV1 fixture frame-count probe did not return 5/2/5")
    proof = {
        "status": "PASSED",
        "filter": fixture_filter(),
        "frameRate": 1,
        "frameSize": [64, 64],
        "baseRgb": base_colors,
        "patchRgb": patch_colors,
        "expectedRgb": expected,
        "replacedOutputFrames": [2, 3],
        "unchangedOutputFrames": [0, 1, 4],
        "maxPerFrameRgbDelta": deltas,
        "rgbTolerance": 3,
        "baseFrame0Sha256": sha_file(FIXTURE_DIR / "base_0.ppm"),
        "patchFrame0Sha256": sha_file(FIXTURE_DIR / "patch_0.ppm"),
        "baseFfv1Sha256": sha_file(base),
        "patchFfv1Sha256": sha_file(patch),
        "compositeSha256": sha_file(composite),
        "probes": {"base": base_probe, "patch": patch_probe, "composite": composite_probe},
        "ffmpegVersion": command_output([common, "-version"], "ffmpeg version query").splitlines()[0],
    }
    write_json_atomic(FIXTURE_DIR / "fixture-proof.json", proof)
    print(json.dumps({"fixture": "PASSED", "outputFrameRGBMaxDeltas": deltas, "changedFrames": [2, 3], "unchangedFrames": [0, 1, 4], "sha256": proof["compositeSha256"]}, ensure_ascii=False))
    return proof


def preserve_candidate(original: Path, original_record: dict[str, Any], original_pointer_bytes: bytes) -> dict[str, Any]:
    CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)
    candidate_video = CANDIDATE_DIR / "original-video-only.mp4"
    if candidate_video.exists():
        if sha_file(candidate_video) != original_record["sha256"] or candidate_video.stat().st_size != original_record["bytes"]:
            raise CompositeError(f"candidate preservation video is divergent; preserved: {candidate_video}")
        copy_method = "matching retained copy reused"
    else:
        temporary = CANDIDATE_DIR / "original-video-only.mp4.tmp"
        if temporary.exists():
            raise CompositeError(f"candidate copy temporary already exists; preserved: {temporary}")
        clone = subprocess.run(["cp", "-c", str(original), str(temporary)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        copy_method = "APFS clone via cp -c"
        if clone.returncode != 0:
            temporary.unlink(missing_ok=True)
            shutil.copy2(original, temporary)
            copy_method = "verified byte copy; clone unavailable across source/destination filesystems"
        if not temporary.is_file() or temporary.stat().st_size != original_record["bytes"] or sha_file(temporary) != original_record["sha256"]:
            temporary.unlink(missing_ok=True)
            raise CompositeError("retained candidate copy failed size/hash verification")
        temporary.replace(candidate_video)
    pointer_copy = CANDIDATE_DIR / "original-render-staging.json"
    if pointer_copy.exists():
        if pointer_copy.read_bytes() != original_pointer_bytes:
            raise CompositeError(f"retained old render pointer is divergent; preserved: {pointer_copy}")
    else:
        pointer_temp = pointer_copy.with_name(pointer_copy.name + ".tmp")
        if pointer_temp.exists():
            raise CompositeError(f"old pointer temporary exists; preserved: {pointer_temp}")
        pointer_temp.write_bytes(original_pointer_bytes)
        if sha_file(pointer_temp) != sha_file(ORIGINAL_POINTER):
            pointer_temp.unlink(missing_ok=True)
            raise CompositeError("old render pointer copy failed hash verification")
        pointer_temp.replace(pointer_copy)
    return {
        "video": {"path": str(candidate_video.relative_to(WORK)), "sha256": sha_file(candidate_video), "bytes": candidate_video.stat().st_size, "copyMethod": copy_method},
        "oldRenderPointer": {"path": str(pointer_copy.relative_to(WORK)), "sha256": sha_file(pointer_copy), "bytes": pointer_copy.stat().st_size},
    }


def assert_agentdev_scratch(path: Path) -> None:
    root = Path("/Volumes/AgentDev").resolve(strict=True)
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise CompositeError(f"TMPDIR is not on verified AgentDev: {resolved}")
    if os.stat(resolved).st_dev == os.stat(PROJECT).st_dev:
        raise CompositeError("TMPDIR resolves to the internal project filesystem; refusing fallback")


def composite() -> dict[str, Any]:
    fixture = verify_fixture_proof()
    original_pointer_bytes = ORIGINAL_POINTER.read_bytes()
    original_pointer = json.loads(original_pointer_bytes)
    patch_pointer = read_json(PATCH_POINTER, "hand-redraw-staging.json")
    provenance = read_json(PROVENANCE_PATH, "render-provenance.json")
    original_path, original_record = ensure_safe_source(original_pointer, "original full render")
    patch_path, patch_record = ensure_safe_source(patch_pointer, "hand-redraw patch")
    if patch_pointer.get("absoluteRange") != list(COMPOSITE_RANGE):
        raise CompositeError(f"patch range {patch_pointer.get('absoluteRange')} differs from assigned {list(COMPOSITE_RANGE)}")
    original_probe = probe(original_path)
    patch_probe = probe(patch_path)
    assert_video_contract(original_probe, frames=FRAME_COUNT, duration=DURATION_SECONDS, label="original full video")
    assert_video_contract(patch_probe, frames=COMPOSITE_RANGE[1] - COMPOSITE_RANGE[0] + 1, duration=13, label="hand patch")

    master = EXPECTED_MASTER.resolve(strict=True)
    master_before = sha_file(master)
    if master_before != provenance.get("master_sha256"):
        raise CompositeError("current PCM master hash differs from the original render provenance")
    geometry_path = PROJECT / "src" / "Geometry.tsx"
    geometry_hash_before = sha_file(geometry_path)
    if REPORT_PATH.exists():
        raise CompositeError(f"composite report already exists; preserving: {REPORT_PATH}")

    old_candidate = preserve_candidate(original_path, original_record, original_pointer_bytes)
    scratch_parent = Path(tempfile.gettempdir())
    assert_agentdev_scratch(scratch_parent)
    output_dir = Path(tempfile.mkdtemp(prefix="si-ep16-hand-composite-", dir=str(scratch_parent)))
    output = output_dir / "video-only.mp4"
    filter_complex = (
        f"[1:v]setpts=PTS+{COMPOSITE_RANGE[0] / FPS:g}/TB[p];"
        f"[0:v][p]overlay=x=0:y=0:format=auto:eof_action=pass:repeatlast=0:enable='between(n,{COMPOSITE_RANGE[0]},{COMPOSITE_RANGE[1]})'[v]"
    )
    command = [
        ffmpeg_binary(), "-hide_banner", "-nostdin", "-n", "-filter_complex_threads", "2",
        "-i", str(original_path), "-i", str(patch_path),
        "-filter_complex", filter_complex,
        "-map", "[v]", "-an", "-map_metadata", "-1",
        "-frames:v", str(FRAME_COUNT), "-fps_mode", "passthrough",
        "-c:v", "libx264", "-crf", "15", "-preset", "fast", "-threads", "4",
        "-pix_fmt", "yuv420p", "-color_range", "tv", "-colorspace", "bt709",
        "-color_trc", "bt709", "-color_primaries", "bt709", "-movflags", "+faststart", str(output),
    ]
    command_output(command, "native full-video hand-redraw composite")
    if not output.is_file() or output.stat().st_size <= 0:
        raise CompositeError("FFmpeg did not produce a nonempty video-only composite")
    composite_probe = probe(output)
    assert_video_contract(composite_probe, frames=FRAME_COUNT, duration=DURATION_SECONDS, label="composite video")
    if composite_probe["pixelFormat"] != "yuv420p" or (composite_probe["colorSpace"], composite_probe["colorTransfer"], composite_probe["colorPrimaries"]) != ("bt709", "bt709", "bt709"):
        raise CompositeError(f"composite colorspace/pixel format differs from assigned BT.709 yuv420p: {composite_probe}")
    command_output([ffmpeg_binary(), "-hide_banner", "-v", "error", "-xerror", "-i", str(output), "-an", "-f", "null", "-"], "strict composite video decode")

    if sha_file(original_path) != original_record["sha256"] or original_path.stat().st_size != original_record["bytes"]:
        raise CompositeError("original full video changed during composition")
    if sha_file(patch_path) != patch_record["sha256"] or patch_path.stat().st_size != patch_record["bytes"]:
        raise CompositeError("hand patch changed during composition")
    master_after = sha_file(master)
    if master_after != master_before:
        raise CompositeError("PCM master changed during video-only composition")
    geometry_hash_after = sha_file(geometry_path)
    if geometry_hash_after != geometry_hash_before:
        raise CompositeError("Geometry.tsx changed during video-only composition")

    composite_record = {"path": str(output), "sha256": sha_file(output), "bytes": output.stat().st_size}
    report = {
        "status": "READY",
        "method": "Two-input full-frame patch overlay; no fps conversion; full stream re-encoded, so non-patch pixels are not claimed bit-identical.",
        "range": {"startFrameInclusive": COMPOSITE_RANGE[0], "endFrameInclusive": COMPOSITE_RANGE[1], "frameCount": COMPOSITE_RANGE[1] - COMPOSITE_RANGE[0] + 1, "seconds": [COMPOSITE_RANGE[0] / FPS, (COMPOSITE_RANGE[1] + 1) / FPS]},
        "filterComplex": filter_complex,
        "encoding": {"codec": "libx264", "crf": 15, "preset": "fast", "pixelFormat": "yuv420p", "colorRange": "tv", "colorSpace": "bt709", "colorTransfer": "bt709", "colorPrimaries": "bt709", "threads": 4, "filterComplexThreads": 2, "fpsConversion": False, "audio": "none"},
        "original": original_record | {"probe": original_probe},
        "patch": patch_record | {"range": patch_pointer["absoluteRange"], "probe": patch_probe},
        "composite": composite_record | {"probe": composite_probe, "strictDecode": "passed"},
        "candidate01Rejected": old_candidate,
        "fixture": {"proofPath": str((FIXTURE_DIR / "fixture-proof.json").relative_to(WORK)), "status": fixture["status"], "sha256": fixture["compositeSha256"], "replacedOutputFrames": fixture["replacedOutputFrames"], "unchangedOutputFrames": fixture["unchangedOutputFrames"], "maxPerFrameRgbDelta": fixture["maxPerFrameRgbDelta"], "rgbTolerance": fixture["rgbTolerance"]},
        "sourceGeometrySha256": geometry_hash_after,
        "audioMaster": {"path": str(master.relative_to(PROJECT)), "sha256Before": master_before, "sha256After": master_after, "matchesOriginalRenderProvenance": True},
        "provenanceSha256": sha_file(PROVENANCE_PATH),
        "stagingDirectoryRetained": str(output_dir),
    }
    # The previous full render pointer and bytes are already retained under candidate-01-rejected.
    updated_pointer = dict(original_pointer)
    updated_pointer["file"] = composite_record["path"]
    updated_pointer["sha256"] = composite_record["sha256"]
    updated_pointer["bytes"] = composite_record["bytes"]
    updated_pointer["composite"] = {
        "sourceRenderStagingSha256": sha_file(CANDIDATE_DIR / "original-render-staging.json"),
        "sourceHandPatchSha256": patch_record["sha256"],
        "report": str(REPORT_PATH.relative_to(WORK)),
        "range": list(COMPOSITE_RANGE),
        "videoOnly": True,
    }
    write_json_atomic(REPORT_PATH, report)
    write_json_atomic(ORIGINAL_POINTER, updated_pointer)
    print(json.dumps({"status": "READY", "composite": composite_record, "probe": composite_probe, "masterSha256": master_after, "fixture": report["fixture"], "candidate01Rejected": old_candidate}, ensure_ascii=False))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-only", action="store_true", help="run the isolated exact-frame FFV1 fixture")
    parser.add_argument("--compose", action="store_true", help="compose the full native video after validating the saved fixture")
    args = parser.parse_args()
    try:
        if args.fixture_only == args.compose:
            raise CompositeError("choose exactly one of --fixture-only or --compose")
        if args.fixture_only:
            run_fixture()
            return 0
        composite()
        return 0
    except (CompositeError, OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        print(f"composite_hand_redraw.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
