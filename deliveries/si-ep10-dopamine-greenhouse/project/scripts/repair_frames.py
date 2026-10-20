#!/usr/bin/env python3
"""Replace two defective EP10 frames with their exact native renderStill PNGs.

The default mode checks the source files and prints a hash-pinned plan. Applying
the repair requires --apply plus the two PNG SHA-256 values from that plan. The
video-only encode and the full-AAC remux are deliberately separate so a frame
cap can never truncate copied AAC packets.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
from typing import Any
import uuid


PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT.parent
ORIGINAL = WORK / "review/iterations/initial-90s.mp4.failed"
SOURCE_1369 = WORK / "review/source-1369.png"
SOURCE_4043 = WORK / "review/source-4043.png"
OUTPUT = WORK / "小红书/si-ep10-dopamine-greenhouse-xiaohongshu-90s-portrait.mp4"
EVIDENCE = WORK / "review/frame-repair.json"
AGENTDEV = Path("/Volumes/AgentDev")

EXPECTED_ORIGINAL_SHA256 = "c081bd497fcb5a29df33b4b718911b111d1b5a9ac8bd9510bf7e749f1cd28fe6"

WIDTH = 2160
HEIGHT = 3840
FPS = 60
OUTPUT_FRAMES = 5400
AAC_PACKET_COUNT = 4221
FRAME_1369 = 1369
FRAME_4043 = 4043


class RepairError(RuntimeError):
    """An input, validation, or no-overwrite guard failed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_json(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RepairError(f"Command returned invalid JSON: {shlex.join(command)}") from exc


def probe(path: Path, *, count_frames: bool = False, count_packets: bool = False) -> dict[str, Any]:
    command = ["ffprobe", "-v", "error"]
    if count_frames:
        command.append("-count_frames")
    if count_packets:
        command.append("-count_packets")
    if count_frames or count_packets:
        command.extend(["-threads", "2"])
    command.extend(["-show_streams", "-show_format", "-of", "json", str(path)])
    try:
        return run_json(command)
    except (OSError, subprocess.CalledProcessError, RepairError) as exc:
        raise RepairError(f"ffprobe failed for {path}: {exc}") from exc


def stream_of_type(data: dict[str, Any], stream_type: str, path: Path) -> dict[str, Any]:
    matches = [stream for stream in data.get("streams", []) if stream.get("codec_type") == stream_type]
    if len(matches) != 1:
        raise RepairError(f"Expected one {stream_type} stream in {path}; found {len(matches)}")
    return matches[0]


def check_native_video(
    data: dict[str, Any],
    path: Path,
    expected_frames: int,
    *,
    allow_unspecified_sar: bool = False,
) -> dict[str, Any]:
    stream = stream_of_type(data, "video", path)
    expected = {
        "width": WIDTH,
        "height": HEIGHT,
        "pix_fmt": "yuv420p",
        "r_frame_rate": "60/1",
        "avg_frame_rate": "60/1",
    }
    mismatches = {
        key: {"expected": value, "actual": stream.get(key)}
        for key, value in expected.items()
        if stream.get(key) != value
    }
    sar = stream.get("sample_aspect_ratio")
    if sar in {"1:1", "1/1"}:
        source_sar = "1:1"
    elif sar in {None, "N/A"} and allow_unspecified_sar:
        source_sar = "unspecified"
    else:
        mismatches["sample_aspect_ratio"] = {"expected": "1:1", "actual": sar}
    actual_frames = stream.get("nb_read_frames") or stream.get("nb_frames")
    if actual_frames != str(expected_frames):
        mismatches["frame_count"] = {"expected": expected_frames, "actual": actual_frames}
    if mismatches:
        raise RepairError(f"Video stream does not match the native repair contract for {path}: {mismatches}")
    return {
        "codecName": stream.get("codec_name"),
        "width": stream.get("width"),
        "height": stream.get("height"),
        "pixelFormat": stream.get("pix_fmt"),
        "sampleAspectRatio": source_sar,
        "rFrameRate": stream.get("r_frame_rate"),
        "avgFrameRate": stream.get("avg_frame_rate"),
        "nbFrames": stream.get("nb_frames"),
        "nbReadFrames": stream.get("nb_read_frames"),
        "colorSpace": stream.get("color_space"),
        "colorTransfer": stream.get("color_transfer"),
        "colorPrimaries": stream.get("color_primaries"),
        "durationSeconds": stream.get("duration"),
    }


def check_png(path: Path) -> dict[str, Any]:
    data = probe(path)
    stream = stream_of_type(data, "video", path)
    width, height = stream.get("width"), stream.get("height")
    if width != WIDTH or height != HEIGHT:
        raise RepairError(
            f"Corrected frame must be native {WIDTH}x{HEIGHT}: {path} is {width}x{height}"
        )
    if any(candidate.get("codec_type") == "audio" for candidate in data.get("streams", [])):
        raise RepairError(f"Still image unexpectedly has an audio stream: {path}")
    sar = stream.get("sample_aspect_ratio")
    if sar not in {None, "N/A", "1:1", "1/1"}:
        raise RepairError(f"Corrected frame has a non-square source SAR {sar!r}: {path}")
    return {
        "codecName": stream.get("codec_name"),
        "width": width,
        "height": height,
        "pixelFormat": stream.get("pix_fmt"),
        "effectiveFrameRateWhenRead": "60/1 (ffmpeg image input -framerate 60)",
        "sourceSampleAspectRatioMetadata": "unspecified" if sar in {None, "N/A"} else "1:1",
        "filterOutputSampleAspectRatio": "1:1 (explicit setsar in filter graph)",
    }


def check_audio(data: dict[str, Any], path: Path) -> dict[str, Any]:
    stream = stream_of_type(data, "audio", path)
    expected = {"codec_name": "aac", "sample_rate": "48000", "channels": 2}
    mismatches = {
        key: {"expected": value, "actual": stream.get(key)}
        for key, value in expected.items()
        if stream.get(key) != value
    }
    packets = stream.get("nb_read_packets") or stream.get("nb_frames")
    if packets != str(AAC_PACKET_COUNT):
        mismatches["aac_packet_count"] = {"expected": AAC_PACKET_COUNT, "actual": packets}
    if mismatches:
        raise RepairError(f"AAC stream does not match the pinned source contract for {path}: {mismatches}")
    return {
        "codecName": stream.get("codec_name"),
        "sampleRateHz": int(stream.get("sample_rate")),
        "channels": int(stream.get("channels")),
        "packetCount": int(packets),
        "durationSeconds": stream.get("duration"),
    }


def source_metadata(data: dict[str, Any], path: Path) -> dict[str, str]:
    tags = data.get("format", {}).get("tags", {})
    lowered = {str(key).lower(): str(value) for key, value in tags.items()}
    title = lowered.get("title")
    comment = lowered.get("comment")
    if not title or not comment:
        raise RepairError(f"Source is missing title/comment metadata required for preservation: {path}")
    return {"title": title, "comment": comment}


def filter_graph() -> str:
    # Every range is half-open and expressed in decoded source frame indices.
    # The two PNG inputs are each explicitly trimmed to exactly one frame.
    return (
        "[0:v:0]split=3[origpre][origmid][origsuffix];"
        "[origpre]trim=start_frame=0:end_frame=1369,settb=expr=1/60,setpts=N,"
        "setsar=1/1,format=yuv420p[pre];"
        "[1:v:0]trim=start_frame=0:end_frame=1,settb=expr=1/60,setpts=N,"
        "scale=iw:ih:flags=lanczos:in_range=pc:out_range=tv:out_color_matrix=bt709,"
        "format=yuv420p,setsar=1/1[fix1369];"
        "[origmid]trim=start_frame=1370:end_frame=4043,settb=expr=1/60,setpts=N,"
        "setsar=1/1,format=yuv420p[middle];"
        "[2:v:0]trim=start_frame=0:end_frame=1,settb=expr=1/60,setpts=N,"
        "scale=iw:ih:flags=lanczos:in_range=pc:out_range=tv:out_color_matrix=bt709,"
        "format=yuv420p,setsar=1/1[fix4043];"
        "[origsuffix]trim=start_frame=4044:end_frame=5400,settb=expr=1/60,setpts=N,"
        "setsar=1/1,format=yuv420p[suffix];"
        "[pre][fix1369][middle][fix4043][suffix]concat=n=5:v=1:a=0,"
        "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709,"
        "format=yuv420p[vout]"
    )


def video_encode_command(destination: Path, metadata: dict[str, str]) -> list[str]:
    return [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-n",
        "-filter_complex_threads",
        "1",
        "-threads",
        "2",
        "-i",
        str(ORIGINAL),
        "-framerate",
        "60",
        "-i",
        str(SOURCE_1369),
        "-framerate",
        "60",
        "-i",
        str(SOURCE_4043),
        "-filter_complex",
        filter_graph(),
        "-map",
        "[vout]",
        "-map_metadata",
        "0",
        "-metadata",
        f"title={metadata['title']}",
        "-metadata",
        f"comment={metadata['comment']}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "16",
        "-threads:v",
        "2",
        "-an",
        "-pix_fmt",
        "yuv420p",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-colorspace",
        "bt709",
        "-r",
        "60",
        "-fps_mode",
        "cfr",
        "-frames:v",
        str(OUTPUT_FRAMES),
        "-movflags",
        "+faststart",
        "-progress",
        "pipe:1",
        "-nostats",
        str(destination),
    ]


def remux_command(video_source: Path, destination: Path, metadata: dict[str, str]) -> list[str]:
    """Copy the entire encoded video and original AAC streams without duration caps."""
    return [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-n",
        "-threads",
        "2",
        "-i",
        str(video_source),
        "-threads",
        "2",
        "-i",
        str(ORIGINAL),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-map_metadata",
        "1",
        "-metadata",
        f"title={metadata['title']}",
        "-metadata",
        f"comment={metadata['comment']}",
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        "-progress",
        "pipe:1",
        "-nostats",
        str(destination),
    ]


def extract_aac_adts(source: Path, destination: Path) -> list[str]:
    return [
        "ffmpeg",
        "-hide_banner",
        "-v",
        "error",
        "-nostdin",
        "-n",
        "-threads",
        "2",
        "-i",
        str(source),
        "-map",
        "0:a:0",
        "-c:a",
        "copy",
        "-f",
        "adts",
        str(destination),
    ]


def verify_aac_copy(original: Path, output: Path, scratch: Path) -> dict[str, Any]:
    original_adts = scratch / "original-audio.aac"
    output_adts = scratch / "repaired-audio.aac"
    for command in (extract_aac_adts(original, original_adts), extract_aac_adts(output, output_adts)):
        try:
            subprocess.run(command, check=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise RepairError(f"AAC packet extraction failed: {exc}") from exc
    original_hash = sha256_file(original_adts)
    output_hash = sha256_file(output_adts)
    if original_hash != output_hash:
        raise RepairError(
            "AAC payload changed: source and repaired ADTS SHA-256 differ "
            f"({original_hash} != {output_hash})"
        )
    return {
        "status": "PASS",
        "method": "extract both AAC streams as ADTS with ffmpeg stream copy, then compare SHA-256",
        "expectedPacketCount": AAC_PACKET_COUNT,
        "sourceAdtsSha256": original_hash,
        "outputAdtsSha256": output_hash,
        "identical": True,
    }


def ensure_file(path: Path) -> None:
    if not path.is_file():
        raise RepairError(f"Required input is missing: {path}")


def get_agentdev_tmpdir(*, required: bool) -> Path | None:
    raw = os.environ.get("TMPDIR")
    if not raw:
        if required:
            raise RepairError("--apply requires TMPDIR to point to an existing directory under /Volumes/AgentDev")
        return None
    candidate = Path(raw).expanduser().resolve()
    root = AGENTDEV.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        if required:
            raise RepairError(f"--apply requires TMPDIR under {root}; current TMPDIR is {candidate}")
        return None
    if not candidate.is_dir():
        if required:
            raise RepairError(f"--apply requires an existing AgentDev TMPDIR: {candidate}")
        return None
    return candidate


def ensure_no_existing_outputs() -> None:
    for path in (OUTPUT, EVIDENCE):
        if path.exists():
            raise RepairError(f"Refusing to overwrite existing output or evidence: {path}")
    if not OUTPUT.parent.is_dir() or not EVIDENCE.parent.is_dir():
        raise RepairError("The canonical output and evidence parent directories must already exist")
    stale_output_parts = list(OUTPUT.parent.glob(f".{OUTPUT.name}.*.partial.mp4"))
    stale_evidence_parts = list(EVIDENCE.parent.glob(f".{EVIDENCE.name}.*.partial"))
    if stale_output_parts or stale_evidence_parts:
        raise RepairError(
            "Refusing to continue while stale publication partials exist: "
            f"{[str(path) for path in stale_output_parts + stale_evidence_parts]}"
        )


def validate_source_bundle() -> tuple[str, str, str, dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str]]:
    for path in (ORIGINAL, SOURCE_1369, SOURCE_4043):
        ensure_file(path)
    ensure_no_existing_outputs()

    original_sha = sha256_file(ORIGINAL)
    png_1369_sha = sha256_file(SOURCE_1369)
    png_4043_sha = sha256_file(SOURCE_4043)
    if original_sha != EXPECTED_ORIGINAL_SHA256:
        raise RepairError(
            "Original render differs from the pinned failed source: "
            f"expected {EXPECTED_ORIGINAL_SHA256}, got {original_sha}"
        )

    original_probe = probe(ORIGINAL, count_frames=True, count_packets=True)
    original_video = check_native_video(
        original_probe, ORIGINAL, OUTPUT_FRAMES, allow_unspecified_sar=True
    )
    original_audio = check_audio(original_probe, ORIGINAL)
    metadata = source_metadata(original_probe, ORIGINAL)
    png_1369 = check_png(SOURCE_1369)
    png_4043 = check_png(SOURCE_4043)
    return original_sha, png_1369_sha, png_4043_sha, original_video, original_audio, {
        "source1369": png_1369,
        "source4043": png_4043,
    }, metadata


def validate_expected_hash(label: str, value: str | None, *, required: bool) -> None:
    if value is None:
        if required:
            raise RepairError(f"--apply requires --expected-{label}-sha256 copied from a checked dry-run")
        return
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise RepairError(f"--expected-{label}-sha256 must be 64 lowercase hexadecimal characters")


def staged_copy(source: Path, parent: Path, *, prefix: str, suffix: str) -> Path:
    destination = parent / f"{prefix}{uuid.uuid4().hex}{suffix}"
    digest = hashlib.sha256()
    try:
        with source.open("rb") as src, destination.open("xb") as dst:
            for block in iter(lambda: src.read(8 * 1024 * 1024), b""):
                digest.update(block)
                dst.write(block)
            dst.flush()
            os.fsync(dst.fileno())
    except Exception:
        try:
            destination.unlink()
        except FileNotFoundError:
            pass
        raise
    if digest.hexdigest() != sha256_file(source):
        destination.unlink(missing_ok=True)
        raise RepairError(f"Staged copy integrity check failed for {source}")
    return destination


def publish_pair_no_replace(staged_output: Path, staged_evidence: Path) -> None:
    output_linked = False
    evidence_linked = False
    try:
        os.link(staged_output, OUTPUT)
        output_linked = True
        os.link(staged_evidence, EVIDENCE)
        evidence_linked = True
    except FileExistsError as exc:
        if output_linked and not evidence_linked:
            try:
                if os.path.samefile(staged_output, OUTPUT):
                    OUTPUT.unlink()
            except FileNotFoundError:
                pass
        raise RepairError(f"Refusing to overwrite a concurrently created final or evidence file: {exc}") from exc
    except OSError:
        if output_linked and not evidence_linked:
            try:
                if os.path.samefile(staged_output, OUTPUT):
                    OUTPUT.unlink()
            except FileNotFoundError:
                pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="encode, verify, and publish; default mode only prints a checked plan",
    )
    parser.add_argument(
        "--expected-source-1369-sha256",
        help="frame 1369 PNG digest printed by dry-run; required with --apply",
    )
    parser.add_argument(
        "--expected-source-4043-sha256",
        help="frame 4043 PNG digest printed by dry-run; required with --apply",
    )
    args = parser.parse_args()

    validate_expected_hash("source-1369", args.expected_source_1369_sha256, required=args.apply)
    validate_expected_hash("source-4043", args.expected_source_4043_sha256, required=args.apply)
    if args.apply and (not args.expected_source_1369_sha256 or not args.expected_source_4043_sha256):
        raise RepairError("--apply requires both frame PNG SHA-256 pins from a checked dry-run")

    (
        original_sha,
        png_1369_sha,
        png_4043_sha,
        original_video,
        original_audio,
        png_info,
        metadata,
    ) = validate_source_bundle()

    if args.apply:
        if png_1369_sha != args.expected_source_1369_sha256:
            raise RepairError(
                "Frame 1369 source changed since dry-run: "
                f"expected {args.expected_source_1369_sha256}, got {png_1369_sha}"
            )
        if png_4043_sha != args.expected_source_4043_sha256:
            raise RepairError(
                "Frame 4043 source changed since dry-run: "
                f"expected {args.expected_source_4043_sha256}, got {png_4043_sha}"
            )

    scratch_root = get_agentdev_tmpdir(required=args.apply)
    if scratch_root is None:
        video_scratch = Path("/Volumes/AgentDev/<TMPDIR_REQUIRED>/ep10-video-only.mp4")
        remux_scratch = Path("/Volumes/AgentDev/<TMPDIR_REQUIRED>/ep10-remuxed.mp4")
    else:
        video_scratch = scratch_root / "ep10-frame-repair" / "ep10-video-only.mp4"
        remux_scratch = scratch_root / "ep10-frame-repair" / "ep10-remuxed.mp4"

    encode = video_encode_command(video_scratch, metadata)
    remux = remux_command(video_scratch, remux_scratch, metadata)
    plan: dict[str, Any] = {
        "mode": "apply" if args.apply else "dry-run",
        "inputSha256": {
            "failedOriginal": original_sha,
            "sourceFrame1369": png_1369_sha,
            "sourceFrame4043": png_4043_sha,
        },
        "sourceSha256RequiredForApply": {
            "frame1369": png_1369_sha,
            "frame4043": png_4043_sha,
        },
        "sourceVideo": original_video,
        "sourceAudio": original_audio,
        "correctedPngs": png_info,
        "repair": {
            "frameIndexesZeroBased": [FRAME_1369, FRAME_4043],
            "sourceFrame1369": str(SOURCE_1369),
            "sourceFrame4043": str(SOURCE_4043),
            "rangesHalfOpen": [
                {"source": "original", "frames": [0, 1369]},
                {"source": "source-1369.png", "frames": [1369, 1370]},
                {"source": "original", "frames": [1370, 4043]},
                {"source": "source-4043.png", "frames": [4043, 4044]},
                {"source": "original", "frames": [4044, 5400]},
            ],
            "outputFrames": OUTPUT_FRAMES,
            "framesPerSecond": FPS,
            "videoDurationSeconds": OUTPUT_FRAMES / FPS,
        },
        "metadataPreservedFromOriginal": metadata,
        "agentDevScratch": {
            "required": True,
            "currentTmpdirReady": scratch_root is not None,
            "scratchDirectory": str(scratch_root) if scratch_root else None,
        },
        "output": str(OUTPUT),
        "evidence": str(EVIDENCE),
        "plannedFfmpegCommands": [encode, remux],
        "shellDisplayOnly": [shlex.join(encode), shlex.join(remux)],
        "encoding": {
            "video": "Separate video-only libx264 veryfast CRF 16 encode, two encoder threads; exact frame cap 5400 applies only here.",
            "audio": "Separate full-stream AAC copy remux from the original; no frame cap, -shortest, or duration cap.",
            "aacProof": f"Require exactly {AAC_PACKET_COUNT} source/output AAC packets and identical extracted ADTS SHA-256.",
        },
        "noOverwrite": {
            "formalOutputAndEvidenceMustBeAbsent": True,
            "publish": "Copy to unique same-volume sibling partials, then hard-link exclusively to formal paths.",
        },
        "limits": [
            "The repaired video is a second-generation libx264 encode and can lose quality relative to the failed source.",
            "The original .failed input remains unchanged; this script does not clear failure flags or rename it.",
            "No continuous visual review, human acceptance, target-device playback, or listening is performed.",
        ],
    }

    if not args.apply:
        apply_args = [
            "python3",
            str(Path(__file__).resolve()),
            "--apply",
            "--expected-source-1369-sha256",
            png_1369_sha,
            "--expected-source-4043-sha256",
            png_4043_sha,
        ]
        plan["applyCommand"] = shlex.join(apply_args)
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    scratch_root = get_agentdev_tmpdir(required=True)
    assert scratch_root is not None
    original_sha_before = sha256_file(ORIGINAL)
    png_1369_before = sha256_file(SOURCE_1369)
    png_4043_before = sha256_file(SOURCE_4043)
    if (original_sha_before, png_1369_before, png_4043_before) != (original_sha, png_1369_sha, png_4043_sha):
        raise RepairError("One or more inputs changed after the checked preflight")

    with tempfile.TemporaryDirectory(prefix="ep10-frame-repair-", dir=scratch_root) as temp_dir:
        scratch = Path(temp_dir)
        video_source = scratch / "video-only.mp4"
        remuxed = scratch / "repaired-remux.mp4"
        actual_commands: list[list[str]] = []

        print("Encoding video-only stream; ffmpeg progress follows.", flush=True)
        print(shlex.join(video_encode_command(video_source, metadata)), flush=True)
        try:
            subprocess.run(video_encode_command(video_source, metadata), check=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise RepairError(f"ffmpeg video-only encode failed: {exc}") from exc
        actual_commands.append(video_encode_command(video_source, metadata))
        if not video_source.is_file():
            raise RepairError(f"ffmpeg reported success but produced no video-only stream: {video_source}")

        video_probe = probe(video_source, count_frames=True)
        encoded_video = check_native_video(video_probe, video_source, OUTPUT_FRAMES)
        if any(stream.get("codec_type") == "audio" for stream in video_probe.get("streams", [])):
            raise RepairError("Video-only intermediate unexpectedly contains audio")
        expected_colors = {"color_space": "bt709", "color_transfer": "bt709", "color_primaries": "bt709"}
        bad_colors = {key: {"expected": value, "actual": stream_value}
                      for key, value in expected_colors.items()
                      if (stream_value := stream_of_type(video_probe, "video", video_source).get(key)) != value}
        if bad_colors:
            raise RepairError(f"Encoded video color tags differ from bt709: {bad_colors}")

        print("Remuxing the complete video with source AAC; no frame or duration cap is used.", flush=True)
        command = remux_command(video_source, remuxed, metadata)
        print(shlex.join(command), flush=True)
        try:
            subprocess.run(command, check=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise RepairError(f"ffmpeg full-stream remux failed: {exc}") from exc
        actual_commands.append(command)
        if not remuxed.is_file():
            raise RepairError(f"ffmpeg reported success but produced no remuxed output: {remuxed}")

        final_probe = probe(remuxed, count_frames=True, count_packets=True)
        final_video = check_native_video(final_probe, remuxed, OUTPUT_FRAMES)
        final_audio = check_audio(final_probe, remuxed)
        final_metadata = source_metadata(final_probe, remuxed)
        if final_metadata != metadata:
            raise RepairError("Final title/comment metadata differs from the original")
        container_duration = float(final_probe.get("format", {}).get("duration", "nan"))
        if abs(container_duration - 90.005) > 0.05:
            raise RepairError(f"Expected a 90.005-second AAC-padded container within 0.05 s; got {container_duration}")
        if final_video.get("durationSeconds") and abs(float(final_video["durationSeconds"]) - 90.0) > 0.01:
            raise RepairError(f"Expected a 90.0-second video stream; got {final_video['durationSeconds']}")
        for key in ("color_space", "color_transfer", "color_primaries"):
            value = stream_of_type(final_probe, "video", remuxed).get(key)
            if value != "bt709":
                raise RepairError(f"Final video {key} tag is {value!r}, expected 'bt709'")

        audio_proof = verify_aac_copy(ORIGINAL, remuxed, scratch)
        remux_sha = sha256_file(remuxed)
        original_sha_after = sha256_file(ORIGINAL)
        png_1369_after = sha256_file(SOURCE_1369)
        png_4043_after = sha256_file(SOURCE_4043)
        if (original_sha_after, png_1369_after, png_4043_after) != (original_sha, png_1369_sha, png_4043_sha):
            raise RepairError("Original or corrected PNG input changed during processing; refusing publication")

        evidence = {
            "status": "PASS",
            "createdAtUtc": datetime.now(timezone.utc).isoformat(),
            "sourceSha256": {
                "failedOriginalBefore": original_sha_before,
                "failedOriginalAfter": original_sha_after,
                "sourceFrame1369": png_1369_sha,
                "sourceFrame4043": png_4043_sha,
            },
            "outputSha256": remux_sha,
            "outputBytes": remuxed.stat().st_size,
            "canonicalOutput": str(OUTPUT),
            "exactFrameRepair": {
                "changedFrameIndexesZeroBased": [FRAME_1369, FRAME_4043],
                "frames": [
                    {"frameIndex": FRAME_1369, "sourcePng": str(SOURCE_1369), "sourcePngSha256": png_1369_sha},
                    {"frameIndex": FRAME_4043, "sourcePng": str(SOURCE_4043), "sourcePngSha256": png_4043_sha},
                ],
                "rangesHalfOpen": [
                    {"source": "original", "frames": [0, 1369]},
                    {"source": "source-1369.png", "frames": [1369, 1370]},
                    {"source": "original", "frames": [1370, 4043]},
                    {"source": "source-4043.png", "frames": [4043, 4044]},
                    {"source": "original", "frames": [4044, 5400]},
                ],
                "resultFrameCount": OUTPUT_FRAMES,
            },
            "nativeVideoProof": {
                "videoOnlyIntermediate": encoded_video,
                "finalVideo": final_video,
                "containerDurationSeconds": container_duration,
                "target": {"width": WIDTH, "height": HEIGHT, "fps": FPS, "frames": OUTPUT_FRAMES,
                           "sar": "1:1", "pixelFormat": "yuv420p", "color": "bt709"},
                "metadataPreserved": final_metadata == metadata,
                "titleAndComment": final_metadata,
            },
            "audioCopyProof": {**audio_proof, "finalStream": final_audio},
            "actualFfmpegCommands": actual_commands,
            "publication": {
                "method": "same-volume unique partial copy followed by exclusive hard links; no overwrite",
                "originalFailedSourceRetained": True,
            },
            "limitations": [
                "The corrected video stream is re-encoded and may have second-generation video loss.",
                "The original .failed render is retained unchanged and remains marked failed.",
                "This technical report does not imply visual acceptance, human review, device playback, or listening.",
            ],
        }

        staged_output = staged_copy(
            remuxed, OUTPUT.parent, prefix=f".{OUTPUT.name}.", suffix=".partial.mp4"
        )
        evidence_temp = EVIDENCE.parent / f".{EVIDENCE.name}.{uuid.uuid4().hex}.partial"
        try:
            with evidence_temp.open("x", encoding="utf-8") as stream:
                json.dump(evidence, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            publish_pair_no_replace(staged_output, evidence_temp)
        except Exception:
            staged_output.unlink(missing_ok=True)
            evidence_temp.unlink(missing_ok=True)
            raise
        staged_output.unlink(missing_ok=True)
        evidence_temp.unlink(missing_ok=True)

        print(json.dumps({"status": "PASS", "output": str(OUTPUT), "evidence": str(EVIDENCE),
                          "outputSha256": remux_sha, "aacPackets": AAC_PACKET_COUNT},
                         ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RepairError as exc:
        print(f"repair_frames: error: {exc}", file=sys.stderr)
        raise SystemExit(2)
