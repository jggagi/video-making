#!/usr/bin/env python3
"""Safely splice the native Act 2 revision into the 90-second portrait master.

Default mode validates the inputs and prints the exact plan. Publishing requires
--apply and the patch SHA-256 printed by the plan; an optional hash-pinned video
input allows a previously encoded native stream to be remuxed without re-encoding.
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


PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT.parent
ORIGINAL = WORK / "review/iterations/initial-90s.mp4"
PATCH = WORK / "review/motion-1200-2639.mp4"
OUTPUT = WORK / "小红书/si-ep09-computing-destiny-xiaohongshu-90s-portrait.mp4"
EVIDENCE = WORK / "review/phase-revision.json"
TEMP_OUTPUT = OUTPUT.with_name(f".{OUTPUT.name}.phase-splice.partial.mp4")
TEMP_VIDEO = OUTPUT.with_name(f".{OUTPUT.name}.phase-video.partial.mp4")

EXPECTED_ORIGINAL_SHA256 = "2ec6749477417216ec6837dd0a55eba28e50a243047bf5bdb066b372845a0f51"
EXPECTED_TITLE = "被算尽的心动"
EXPECTED_FICTION_COMMENT = (
    "Made with Remotion 4.0.534; Science-fiction thought experiment. All biometric values, "
    "forecasts, precision claims and engineered coincidences are fictional. Native portrait "
    "4K; 90 seconds; 5400 frames at 60fps."
)
WIDTH = 2160
HEIGHT = 3840
FPS = 60
OUTPUT_FRAMES = 5400
PREFIX_END = 1200
PATCH_START = 0
PATCH_END = 1440
SUFFIX_START = 2640
SUFFIX_END = 5400


class SpliceError(RuntimeError):
    """An input, validation, or no-overwrite guard failed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_json(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def probe(path: Path, *, count_frames: bool) -> dict[str, Any]:
    command = ["ffprobe", "-v", "error"]
    if count_frames:
        command.extend(["-count_frames", "-threads", "2"])
    command.extend(
        [
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ]
    )
    try:
        return run_json(command)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        raise SpliceError(f"ffprobe failed for {path}: {exc}") from exc


def video_stream(probe_data: dict[str, Any], path: Path) -> dict[str, Any]:
    videos = [s for s in probe_data.get("streams", []) if s.get("codec_type") == "video"]
    if len(videos) != 1:
        raise SpliceError(f"Expected one video stream in {path}; found {len(videos)}")
    return videos[0]


def audio_stream(probe_data: dict[str, Any], path: Path) -> dict[str, Any]:
    audios = [s for s in probe_data.get("streams", []) if s.get("codec_type") == "audio"]
    if len(audios) != 1:
        raise SpliceError(f"Expected one audio stream in {path}; found {len(audios)}")
    return audios[0]


def check_video(path: Path, data: dict[str, Any], expected_frames: int) -> dict[str, Any]:
    stream = video_stream(data, path)
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
    frame_count = stream.get("nb_read_frames") or stream.get("nb_frames")
    if frame_count != str(expected_frames):
        mismatches["frame_count"] = {"expected": expected_frames, "actual": frame_count}
    if mismatches:
        raise SpliceError(f"Video stream does not match the native splice contract for {path}: {mismatches}")
    return {
        "codec_name": stream.get("codec_name"),
        "width": stream.get("width"),
        "height": stream.get("height"),
        "pix_fmt": stream.get("pix_fmt"),
        "r_frame_rate": stream.get("r_frame_rate"),
        "avg_frame_rate": stream.get("avg_frame_rate"),
        "nb_frames": stream.get("nb_frames"),
        "nb_read_frames": stream.get("nb_read_frames"),
        "color_space": stream.get("color_space"),
        "color_transfer": stream.get("color_transfer"),
        "color_primaries": stream.get("color_primaries"),
        "duration": stream.get("duration"),
    }


def check_original_audio(data: dict[str, Any]) -> dict[str, Any]:
    stream = audio_stream(data, ORIGINAL)
    expected = {"codec_name": "aac", "sample_rate": "48000", "channels": 2}
    mismatches = {
        key: {"expected": value, "actual": stream.get(key)}
        for key, value in expected.items()
        if stream.get(key) != value
    }
    if mismatches:
        raise SpliceError(f"Original AAC stream differs from the approved source: {mismatches}")
    return {
        "codec_name": stream.get("codec_name"),
        "sample_rate": stream.get("sample_rate"),
        "channels": stream.get("channels"),
        "nb_frames": stream.get("nb_frames"),
        "duration": stream.get("duration"),
    }


def check_fiction_metadata(data: dict[str, Any], path: Path) -> dict[str, str]:
    tags = data.get("format", {}).get("tags", {})
    actual_title = tags.get("title")
    actual_comment = tags.get("comment")
    if actual_title != EXPECTED_TITLE or actual_comment != EXPECTED_FICTION_COMMENT:
        raise SpliceError(
            f"Fiction metadata differs from the approved source in {path}: "
            f"title={actual_title!r}, comment={actual_comment!r}"
        )
    return {"title": actual_title, "comment": actual_comment}


def filter_graph() -> str:
    return (
        "[0:v:0]split=2[origpre][origpost];"
        f"[origpre]trim=start_frame=0:end_frame={PREFIX_END},setpts=PTS-STARTPTS,"
        "setsar=1/1,format=yuv420p[pre];"
        f"[1:v:0]trim=start_frame={PATCH_START}:end_frame={PATCH_END},"
        "setpts=PTS-STARTPTS,setsar=1/1,format=yuv420p[patch];"
        f"[origpost]trim=start_frame={SUFFIX_START}:end_frame={SUFFIX_END},"
        "setpts=PTS-STARTPTS,setsar=1/1,format=yuv420p[post];"
        "[pre][patch][post]concat=n=3:v=1:a=0,"
        "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709,format=yuv420p[vout]"
    )


def video_encode_command(destination: Path) -> list[str]:
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
        "-threads",
        "2",
        "-i",
        str(PATCH),
        "-filter_complex",
        filter_graph(),
        "-map",
        "[vout]",
        "-map_metadata",
        "0",
        "-metadata",
        f"title={EXPECTED_TITLE}",
        "-metadata",
        f"comment={EXPECTED_FICTION_COMMENT}",
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


def remux_command(video_source: Path, destination: Path) -> list[str]:
    """Mux the complete encoded video stream with the untouched source AAC."""
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
        f"title={EXPECTED_TITLE}",
        "-metadata",
        f"comment={EXPECTED_FICTION_COMMENT}",
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


def verify_aac_copy(original: Path, output: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="ep09-aac-proof-", dir=WORK / "review") as temp_dir:
        original_adts = Path(temp_dir) / "original.aac"
        output_adts = Path(temp_dir) / "output.aac"
        for command in (
            extract_aac_adts(original, original_adts),
            extract_aac_adts(output, output_adts),
        ):
            subprocess.run(command, check=True)
        original_hash = sha256_file(original_adts)
        output_hash = sha256_file(output_adts)
        if original_hash != output_hash:
            raise SpliceError(
                "AAC payload changed: original and output ADTS SHA-256 digests differ "
                f"({original_hash} != {output_hash})"
            )
        return {
            "status": "PASS",
            "method": "ffmpeg -map 0:a:0 -c:a copy -f adts, then SHA-256",
            "original_aac_payload_sha256": original_hash,
            "output_aac_payload_sha256": output_hash,
            "identical": True,
        }


def ensure_available(path: Path) -> None:
    if not path.is_file():
        raise SpliceError(f"Required input is missing: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="encode, verify, and publish the splice; default mode only prints a checked plan",
    )
    parser.add_argument(
        "--expected-patch-sha256",
        help="patch digest printed by dry-run; required with --apply",
    )
    parser.add_argument(
        "--reuse-video",
        type=Path,
        help="reuse a previously encoded native 5400-frame video stream; its audio is ignored",
    )
    parser.add_argument(
        "--expected-reuse-video-sha256",
        help="required digest for --reuse-video, checked before and after remux",
    )
    args = parser.parse_args()

    if args.apply and not args.expected_patch_sha256:
        raise SpliceError("--apply requires --expected-patch-sha256 copied from a checked dry-run")
    if args.expected_patch_sha256 and not re.fullmatch(r"[0-9a-f]{64}", args.expected_patch_sha256):
        raise SpliceError("--expected-patch-sha256 must be 64 lowercase hexadecimal characters")
    if bool(args.reuse_video) != bool(args.expected_reuse_video_sha256):
        raise SpliceError("--reuse-video and --expected-reuse-video-sha256 must be supplied together")
    if args.expected_reuse_video_sha256 and not re.fullmatch(
        r"[0-9a-f]{64}", args.expected_reuse_video_sha256
    ):
        raise SpliceError("--expected-reuse-video-sha256 must be 64 lowercase hexadecimal characters")

    for path in (ORIGINAL, PATCH):
        ensure_available(path)
    for path in (OUTPUT, EVIDENCE, TEMP_OUTPUT, TEMP_VIDEO):
        if path.exists():
            raise SpliceError(f"Refusing to overwrite existing output or evidence: {path}")

    reuse_video = args.reuse_video.expanduser().resolve() if args.reuse_video else None
    if reuse_video is not None:
        ensure_available(reuse_video)
        if reuse_video in {ORIGINAL.resolve(), PATCH.resolve(), OUTPUT.resolve(), TEMP_OUTPUT.resolve(), TEMP_VIDEO.resolve()}:
            raise SpliceError(f"Refusing to use an input or output path as --reuse-video: {reuse_video}")

    original_sha = sha256_file(ORIGINAL)
    patch_sha = sha256_file(PATCH)
    if original_sha != EXPECTED_ORIGINAL_SHA256:
        raise SpliceError(
            f"Original differs from the QA-pinned source: expected {EXPECTED_ORIGINAL_SHA256}, got {original_sha}"
        )
    if args.apply and patch_sha != args.expected_patch_sha256:
        raise SpliceError(
            f"Patch differs from the checked dry-run: expected {args.expected_patch_sha256}, got {patch_sha}"
        )
    reuse_video_sha = sha256_file(reuse_video) if reuse_video is not None else None
    if reuse_video is not None and reuse_video_sha != args.expected_reuse_video_sha256:
        raise SpliceError(
            "Reused video differs from the checked digest: "
            f"expected {args.expected_reuse_video_sha256}, got {reuse_video_sha}"
        )

    original_probe = probe(ORIGINAL, count_frames=False)
    patch_probe = probe(PATCH, count_frames=False)
    original_video = check_video(ORIGINAL, original_probe, OUTPUT_FRAMES)
    original_audio = check_original_audio(original_probe)
    original_metadata = check_fiction_metadata(original_probe, ORIGINAL)
    patch_video = check_video(PATCH, patch_probe, PATCH_END - PATCH_START)

    video_source = reuse_video if reuse_video is not None else TEMP_VIDEO
    reuse_video_info = None
    if reuse_video is not None:
        reuse_probe = probe(reuse_video, count_frames=True)
        reuse_video_info = check_video(reuse_video, reuse_probe, OUTPUT_FRAMES)

    planned_commands = (
        [remux_command(video_source, TEMP_OUTPUT)]
        if reuse_video is not None
        else [video_encode_command(TEMP_VIDEO), remux_command(TEMP_VIDEO, TEMP_OUTPUT)]
    )

    plan = {
        "mode": "apply" if args.apply else "dry-run",
        "input_sha256": {"original": original_sha, "patch": patch_sha},
        "patch_sha256_required_for_apply": patch_sha,
        "splice": {
            "original_prefix_frames_half_open": [0, PREFIX_END],
            "patch_frames_half_open": [PATCH_START, PATCH_END],
            "original_suffix_frames_half_open": [SUFFIX_START, SUFFIX_END],
            "output_frames": OUTPUT_FRAMES,
            "frames_per_second": FPS,
            "duration_seconds": OUTPUT_FRAMES / FPS,
        },
        "act2_reveal_decision": {
            "frames": 240,
            "meaning": "Act 2 future is fully revealed over 4.0 seconds; preserve the final 24-second act range.",
        },
        "native_inputs": {"original_video": original_video, "patch_video": patch_video, "original_audio": original_audio},
        "video_source": {
            "kind": "reused" if reuse_video is not None else "to_be_encoded",
            "path": str(video_source),
            "sha256": reuse_video_sha,
            "reused_video_probe": reuse_video_info,
            "reused_video_audio": "ignored; only stream 0:v:0 is mapped" if reuse_video is not None else None,
        },
        "fiction_metadata": original_metadata,
        "output": str(OUTPUT),
        "evidence": str(EVIDENCE),
        "planned_ffmpeg_commands": planned_commands,
        "shell_display_only": [shlex.join(command) for command in planned_commands],
        "encoding": {
            "video": "libx264 veryfast CRF 16, two encoder threads; separate video-only encode"
            if reuse_video is None
            else "reuse hash-pinned native video stream",
            "audio": "full original AAC packet copy in a separate remux; no remux frame cap or duration cap",
        },
        "limits": [
            "Act 2 source frames replace only output frames 1200 through 2639.",
            "No ASR, visual acceptance, or human listening is performed by this script.",
            "The final video stream is either re-encoded or hash-pinned for reuse; source AAC packets are copied and compared byte-for-byte as ADTS payloads.",
        ],
    }

    if not args.apply:
        apply_args = [
            "python3",
            str(Path(__file__).resolve()),
            "--apply",
            "--expected-patch-sha256",
            patch_sha,
        ]
        if reuse_video is not None:
            apply_args.extend(
                ["--reuse-video", str(reuse_video), "--expected-reuse-video-sha256", reuse_video_sha]
            )
        plan["apply_command"] = shlex.join(apply_args)
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    actual_commands: list[list[str]] = []
    if reuse_video is None:
        encode_command = planned_commands[0]
        print("Encoding video-only splice; ffmpeg -progress output follows.", flush=True)
        print(shlex.join(encode_command), flush=True)
        try:
            subprocess.run(encode_command, check=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise SpliceError(f"ffmpeg video-only encode failed: {exc}") from exc
        actual_commands.append(encode_command)
        if not TEMP_VIDEO.is_file():
            raise SpliceError(f"ffmpeg reported success but produced no temporary video: {TEMP_VIDEO}")
        generated_probe = probe(TEMP_VIDEO, count_frames=True)
        generated_video = check_video(TEMP_VIDEO, generated_probe, OUTPUT_FRAMES)
        if any(s.get("codec_type") == "audio" for s in generated_probe.get("streams", [])):
            raise SpliceError("Video-only encode unexpectedly contains an audio stream")
        video_source_sha = sha256_file(TEMP_VIDEO)
        video_source_info = generated_video
    else:
        video_source_sha = reuse_video_sha
        video_source_info = reuse_video_info

    command = planned_commands[-1]
    print("Remuxing the complete video stream with the original AAC; ffmpeg -progress output follows.", flush=True)
    print(shlex.join(command), flush=True)
    try:
        subprocess.run(command, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SpliceError(f"ffmpeg full-stream remux failed: {exc}") from exc
    actual_commands.append(command)

    if not TEMP_OUTPUT.is_file():
        raise SpliceError(f"ffmpeg reported success but produced no temporary output: {TEMP_OUTPUT}")

    post_original_sha = sha256_file(ORIGINAL)
    post_patch_sha = sha256_file(PATCH)
    if (post_original_sha, post_patch_sha) != (original_sha, patch_sha):
        raise SpliceError("One or both splice inputs changed while processing; refusing to publish the result")
    post_video_source_sha = sha256_file(video_source)
    if post_video_source_sha != video_source_sha:
        raise SpliceError("Video source changed while remuxing; refusing to publish the result")

    output_probe = probe(TEMP_OUTPUT, count_frames=True)
    output_video = check_video(TEMP_OUTPUT, output_probe, OUTPUT_FRAMES)
    output_audio = check_original_audio(output_probe)
    output_metadata = check_fiction_metadata(output_probe, TEMP_OUTPUT)
    container_duration = float(output_probe.get("format", {}).get("duration", "nan"))
    if abs(container_duration - 90.005) > 0.01:
        raise SpliceError(f"Expected a 90.005-second AAC-padded container; got {container_duration}")
    if output_video.get("duration") and abs(float(output_video["duration"]) - 90.0) > 0.01:
        raise SpliceError(f"Expected a 90.0-second video stream; got {output_video['duration']}")
    if output_video.get("color_space") != "bt709" or output_video.get("color_transfer") != "bt709" or output_video.get("color_primaries") != "bt709":
        raise SpliceError("Output video color tags are not bt709")

    audio_proof = verify_aac_copy(ORIGINAL, TEMP_OUTPUT)
    output_sha = sha256_file(TEMP_OUTPUT)
    evidence = {
        "status": "PASS",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_sha256": {"original": original_sha, "patch": patch_sha},
        "output_sha256": output_sha,
        "act2_reveal_decision": {
            "frames": 240,
            "denominator_change": "Scenes.tsx uses 240 frames so the Act 2 future is fully revealed within its 24-second act.",
        },
        "exact_splice_ranges_half_open": {
            "original_prefix": [0, PREFIX_END],
            "patch_source": [PATCH_START, PATCH_END],
            "original_suffix": [SUFFIX_START, SUFFIX_END],
            "result_frame_count": OUTPUT_FRAMES,
        },
        "native_proof": {
            "status": "PASS",
            "original_video": original_video,
            "patch_video": patch_video,
            "output_video": output_video,
            "output_container_duration_seconds": container_duration,
            "fiction_metadata_preserved": output_metadata == original_metadata,
            "title_and_comment": output_metadata,
        },
        "video_source": {
            "kind": "reused" if reuse_video is not None else "generated",
            "path": str(video_source),
            "sha256_before_remux": video_source_sha,
            "sha256_after_remux": post_video_source_sha,
            "video_probe": video_source_info,
            "source_audio_ignored": reuse_video is not None,
        },
        "audio_copy_proof": audio_proof,
        "actual_ffmpeg_commands": actual_commands,
        "limitations": [
            "The splice re-encodes video and can introduce second-generation video loss.",
            "AAC payload identity proves the authored audio bitstream was copied; no ASR or perceptual listening was performed.",
            "No continuous visual review, target-device playback, or human acceptance is implied.",
        ],
    }

    # A hard link publishes only if the destination is still absent; it cannot
    # silently replace a concurrent or divergent final file.
    try:
        os.link(TEMP_OUTPUT, OUTPUT)
    except FileExistsError as exc:
        raise SpliceError(f"Refusing to overwrite output created concurrently: {OUTPUT}") from exc
    TEMP_OUTPUT.unlink()
    evidence_temp = EVIDENCE.with_name(f".{EVIDENCE.name}.partial")
    if evidence_temp.exists():
        raise SpliceError(f"Refusing to overwrite existing temporary evidence: {evidence_temp}")
    with evidence_temp.open("x", encoding="utf-8") as stream:
        json.dump(evidence, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    try:
        os.link(evidence_temp, EVIDENCE)
    except FileExistsError as exc:
        raise SpliceError(f"Refusing to overwrite evidence created concurrently: {EVIDENCE}") from exc
    evidence_temp.unlink()
    if reuse_video is None:
        TEMP_VIDEO.unlink()
    print(json.dumps({"status": "PASS", "output": str(OUTPUT), "evidence": str(EVIDENCE), "output_sha256": output_sha}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SpliceError as exc:
        print(f"splice_phase: error: {exc}", file=sys.stderr)
        raise SystemExit(2)
