#!/usr/bin/env python3
"""Patch EP08's quote window from one contiguous numbered PNG sequence.

The quote PNGs are supplied to FFmpeg as one image2 sequence beginning at
absolute frame 5880. Their timestamps are shifted by 98 seconds before they
are overlaid, so the main video's zero-based frame indices 5880-6299 receive
the patch. This script writes a new MP4 and JSON evidence; it never edits the
input and refuses to replace existing output paths.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
import tempfile
import zlib
from typing import Any

import repair_frames as base


FPS = 60
DURATION_SECONDS = 120.0
EXPECTED_FRAMES = 7200
PATCH_START = 5880
PATCH_END = 6299
PATCH_COUNT = PATCH_END - PATCH_START + 1
PATCH_OFFSET_SECONDS = PATCH_START / FPS
FRAME_NAME = re.compile(r"^frame-(\d+)\.png$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Overlay EP08's quote-window PNG sequence into a new MP4.")
    parser.add_argument("--input", type=Path, help="Existing native 4K MP4; never modified.")
    parser.add_argument("--frames-dir", type=Path, help="Directory containing frame-5880.png through frame-6299.png and manifest.json.")
    parser.add_argument("--output", type=Path, help="New MP4 path; must not already exist.")
    parser.add_argument("--expected-frames", type=int, help="Expected input frame count; EP08 requires 7200.")
    parser.add_argument("--report", type=Path, help="New JSON evidence path; must not already exist.")
    parser.add_argument("--fixture-evidence", type=Path, help="Verified sequence-fixture JSON produced with --verify-sequence-fixture.")
    parser.add_argument(
        "--verify-sequence-fixture",
        action="store_true",
        help="Run the tiny five-frame/two-patch FFV1 sequence-offset fixture instead of a full repair.",
    )
    parser.add_argument("--fixture-report", type=Path, help="New JSON evidence path for --verify-sequence-fixture.")
    return parser.parse_args()


def discover_patch_sequence(directory: Path, dimensions: tuple[int, int]) -> list[dict[str, Any]]:
    if not directory.is_dir():
        raise base.RepairError(f"frames directory does not exist: {directory}")
    try:
        candidates = sorted(path for path in directory.iterdir() if path.suffix.lower() == ".png")
    except OSError as exc:
        raise base.RepairError(f"cannot list frames directory {directory}: {exc}") from None
    expected_ids = list(range(PATCH_START, PATCH_END + 1))
    by_id: dict[int, Path] = {}
    for path in candidates:
        match = FRAME_NAME.fullmatch(path.name)
        if match is None:
            raise base.RepairError(f"PNG filename must be frame-<id>.png with canonical decimal id: {path.name}")
        frame_id = int(match.group(1))
        if str(frame_id) != match.group(1):
            raise base.RepairError(f"PNG filename has a non-canonical frame id: {path.name}")
        if frame_id in by_id:
            raise base.RepairError(f"duplicate numeric frame id {frame_id}: {by_id[frame_id].name} and {path.name}")
        by_id[frame_id] = path
    actual_ids = sorted(by_id)
    if len(candidates) != PATCH_COUNT or actual_ids != expected_ids:
        raise base.RepairError(
            f"quote patch must contain exactly {PATCH_COUNT} contiguous PNGs for {PATCH_START}-{PATCH_END}; "
            f"found {len(candidates)} PNGs with ids {actual_ids[:3]}...{actual_ids[-3:] if actual_ids else []}"
        )
    frames: list[dict[str, Any]] = []
    for frame_id in expected_ids:
        path = by_id[frame_id]
        actual_dimensions = base.read_png_dimensions(path)
        if actual_dimensions != dimensions:
            raise base.RepairError(
                f"{path.name} is {actual_dimensions[0]}x{actual_dimensions[1]}; "
                f"expected {dimensions[0]}x{dimensions[1]}"
            )
        frames.append({"frame": frame_id, "path": path.resolve(), "sha256": base.sha256_file(path)})

    manifest_path = directory / "manifest.json"
    try:
        manifest_raw = manifest_path.read_bytes()
        manifest = json.loads(manifest_raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise base.RepairError(f"cannot read quote patch manifest {manifest_path}: {exc}") from None
    if not isinstance(manifest, dict):
        raise base.RepairError("quote patch manifest must be a JSON object")
    manifest_files = manifest.get("files")
    expected_manifest_files = [
        {"frame": item["frame"], "filename": item["path"].name, "sha256": item["sha256"]}
        for item in frames
    ]
    expected_dimensions = {"width": dimensions[0], "height": dimensions[1]}
    if (
        manifest.get("fps") != FPS
        or manifest.get("frame_range_inclusive") != [PATCH_START, PATCH_END]
        or manifest.get("frame_count") != PATCH_COUNT
        or manifest.get("dimensions") != expected_dimensions
        or manifest_files != expected_manifest_files
    ):
        raise base.RepairError("quote patch manifest does not match the contiguous PNG sequence, dimensions, or hashes")
    return frames


def sequence_ffmpeg_command(
    ffmpeg: str,
    source: Path,
    frames_dir: Path,
    expected_frames: int,
    temporary_output: Path,
) -> list[str]:
    sequence = frames_dir / "frame-%d.png"
    graph = (
        f"[1:v]setpts=PTS-STARTPTS+{PATCH_OFFSET_SECONDS:g}/TB[p];"
        f"[0:v][p]overlay=eof_action=pass:repeatlast=0:"
        f"enable='between(n,{PATCH_START},{PATCH_END})'[vout]"
    )
    return [
        ffmpeg, "-hide_banner", "-nostdin", "-y", "-filter_complex_threads", "2",
        "-threads", "2", "-i", str(source),
        "-threads", "2", "-framerate", str(FPS), "-start_number", str(PATCH_START), "-i", str(sequence),
        "-filter_complex", graph, "-map", "[vout]", "-map", "0:a?", "-map_metadata", "0",
        "-map_chapters", "0", "-fps_mode", "passthrough", "-frames:v", str(expected_frames),
        "-c:v", "libx264", "-preset", "fast", "-crf", "15", "-pix_fmt", "yuv420p",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
        "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709",
        "-threads", "4", "-c:a", "copy", "-movflags", "+faststart", str(temporary_output),
    ]


def load_fixture_evidence(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    fixture_path = path.expanduser().resolve(strict=True)
    try:
        evidence = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise base.RepairError(f"cannot read sequence fixture evidence {fixture_path}: {exc}") from None
    if (
        not isinstance(evidence, dict)
        or evidence.get("verified") is not True
        or evidence.get("main_codec") != "ffv1"
        or evidence.get("main_frames") != 5
        or evidence.get("sequence_start_number") != 2
        or evidence.get("sequence_frames") != 2
        or evidence.get("changed_output_indices") != [2, 3]
    ):
        raise base.RepairError(f"sequence fixture evidence is not a passing 5-frame [2,3] verification: {fixture_path}")
    return {"path": fixture_path, "sha256": base.sha256_file(fixture_path), "evidence": evidence}


def repair(args: argparse.Namespace) -> dict[str, Any]:
    if args.expected_frames != EXPECTED_FRAMES:
        raise base.RepairError(f"EP08 requires --expected-frames {EXPECTED_FRAMES}; got {args.expected_frames}")
    source = args.input.expanduser().resolve(strict=True)
    if not source.is_file() or source.suffix.lower() != ".mp4":
        raise base.RepairError(f"--input must be an existing MP4 file: {source}")
    output = base.canonical_new_path(args.output, "output")
    report = base.canonical_new_path(args.report, "report")
    if output.suffix.lower() != ".mp4":
        raise base.RepairError(f"--output must use an .mp4 extension: {output}")
    if output == source or report == source or output == report:
        raise base.RepairError("input, output, and report paths must be distinct")
    try:
        if os.path.samefile(source, output) or os.path.samefile(source, report):
            raise base.RepairError("input and output/report must not refer to the same file")
    except FileNotFoundError:
        pass

    ffmpeg = base.require_tool("ffmpeg")
    ffprobe = base.require_tool("ffprobe")
    input_probe = base.probe_media(ffprobe, source)
    input_timeline = base.validate_timeline(input_probe, args.expected_frames, "input")
    audio_count = sum(stream.get("codec_type") == "audio" for stream in input_probe["streams"])
    if audio_count < 1:
        raise base.RepairError("input MP4 must contain audio so copied audio payload can be verified")
    frames_dir = args.frames_dir.expanduser().resolve(strict=True)
    dimensions = (input_timeline["width"], input_timeline["height"])
    frames = discover_patch_sequence(frames_dir, dimensions)
    fixture = load_fixture_evidence(args.fixture_evidence)
    if fixture is None:
        raise base.RepairError("Passing --fixture-evidence is required before full repair")

    input_hash_before = base.sha256_file(source)
    audio_before = base.audio_packet_hashes(ffprobe, source, audio_count)
    manifest_hash = base.sha256_file(frames_dir / "manifest.json")
    temp_output = base.make_temp_file(output.parent, f".{output.stem}.quote-repair-", ".mp4")
    temp_report: Path | None = None
    published_output: tuple[int, int] | None = None
    try:
        command = sequence_ffmpeg_command(ffmpeg, source, frames_dir, args.expected_frames, temp_output)
        base.run_capture(command, "quote window sequence overlay encode", timeout=7200)

        if base.sha256_file(source) != input_hash_before:
            raise base.RepairError("input MP4 changed while quote-window repair was running")
        if base.sha256_file(frames_dir / "manifest.json") != manifest_hash:
            raise base.RepairError("quote patch manifest changed while repair was running")
        current_png_names = sorted(path.name for path in frames_dir.iterdir() if path.suffix.lower() == ".png")
        expected_png_names = [item["path"].name for item in frames]
        if current_png_names != expected_png_names:
            raise base.RepairError("quote patch PNG set changed while repair was running")
        for frame in frames:
            if base.sha256_file(frame["path"]) != frame["sha256"]:
                raise base.RepairError(f"overlay PNG changed while repair was running: {frame['path'].name}")

        output_probe = base.probe_media(ffprobe, temp_output)
        output_timeline = base.validate_timeline(output_probe, args.expected_frames, "output")
        output_video = base.selected_video(output_probe, "output")
        if output_video.get("codec_name") != "h264":
            raise base.RepairError(f"output video codec must be H.264; got {output_video.get('codec_name')!r}")
        if output_video.get("pix_fmt") != "yuv420p":
            raise base.RepairError(f"output pixel format must be yuv420p; got {output_video.get('pix_fmt')!r}")
        color_tags = {
            "color_primaries": output_video.get("color_primaries"),
            "color_transfer": output_video.get("color_transfer"),
            "color_space": output_video.get("color_space"),
        }
        expected_color = {"color_primaries": "bt709", "color_transfer": "bt709", "color_space": "bt709"}
        if color_tags != expected_color:
            raise base.RepairError(f"output must be tagged BT.709; got {color_tags}")
        output_audio_count = sum(stream.get("codec_type") == "audio" for stream in output_probe["streams"])
        if output_audio_count != audio_count:
            raise base.RepairError(f"audio stream count changed: input {audio_count}, output {output_audio_count}")
        audio_after = base.audio_packet_hashes(ffprobe, temp_output, output_audio_count)
        if audio_before != audio_after:
            raise base.RepairError("audio packet payload hashes differ; copied audio was not preserved byte-for-byte")
        if output_timeline != input_timeline:
            raise base.RepairError(f"video timeline changed: input {input_timeline}, output {output_timeline}")
        if not base.check_faststart(temp_output):
            raise base.RepairError("output MP4 does not place moov before mdat despite +faststart")

        evidence = {
            "schema_version": 1,
            "operation": "numbered_quote_window_sequence_overlay",
            "human_playback_verified": False,
            "input": {
                "path": str(source),
                "sha256": input_hash_before,
                "timeline": input_timeline,
                "ffprobe": input_probe,
                "audio_packet_hashes": audio_before,
            },
            "overlay_sequence": {
                "directory": str(frames_dir),
                "pattern": "frame-%d.png",
                "frame_range_inclusive": [PATCH_START, PATCH_END],
                "frame_count": PATCH_COUNT,
                "fps": FPS,
                "pts_offset_seconds": PATCH_OFFSET_SECONDS,
                "manifest_sha256": manifest_hash,
                "files": [
                    {"frame": item["frame"], "filename": item["path"].name, "sha256": item["sha256"]}
                    for item in frames
                ],
            },
            "ffmpeg_command": command,
            "output": {
                "path": str(output),
                "sha256": base.sha256_file(temp_output),
                "timeline": output_timeline,
                "ffprobe": output_probe,
                "audio_packet_hashes": audio_after,
                "audio_payloads_identical": True,
                "video_codec": "h264",
                "pixel_format": "yuv420p",
                "color_tags": color_tags,
                "crf": 15,
                "preset": "fast",
                "encoder_threads": 4,
                "faststart_verified": True,
            },
            "frame_indexing": {
                "basis": "absolute zero-based decoded main-video output frame n",
                "sequence_input": f"-framerate {FPS} -start_number {PATCH_START} frame-%d.png",
                "pts_offset_seconds": PATCH_OFFSET_SECONDS,
                "enable_expression": f"between(n,{PATCH_START},{PATCH_END})",
                "overlay_eof_behavior": "eof_action=pass:repeatlast=0",
                "fixture_verified": fixture is not None,
                "fixture_evidence": (
                    {"path": str(fixture["path"]), "sha256": fixture["sha256"], "changed_output_indices": [2, 3]}
                    if fixture is not None
                    else None
                ),
                "no_fps_conversion": True,
            },
        }
        temp_report = base.write_json_temp(report, evidence)
        published_output = base.publish_no_clobber(temp_output, output)
        try:
            base.publish_no_clobber(temp_report, report)
        except base.RepairError:
            base.remove_published_if_owned(output, published_output)
            published_output = None
            raise
        return evidence
    finally:
        for temporary in (temp_output, temp_report):
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def write_solid_png(path: Path, width: int, height: int, rgb: tuple[int, int, int]) -> None:
    row = b"\x00" + bytes(rgb) * width
    raw = row * height
    payload = b"\x89PNG\r\n\x1a\n"
    payload += _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    payload += _png_chunk(b"IDAT", zlib.compress(raw, level=1))
    payload += _png_chunk(b"IEND", b"")
    path.write_bytes(payload)


def decode_rgb_frames(ffmpeg: str, path: Path, width: int, height: int, expected: int) -> list[bytes]:
    result = base.run_capture(
        [ffmpeg, "-hide_banner", "-nostdin", "-v", "error", "-i", str(path), "-map", "0:v:0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        f"decode fixture frames from {path.name}",
    )
    frame_size = width * height * 3
    if len(result.stdout) != frame_size * expected:
        raise base.RepairError(f"fixture {path.name} decoded to {len(result.stdout)} bytes, expected {frame_size * expected}")
    return [result.stdout[index * frame_size : (index + 1) * frame_size] for index in range(expected)]


def verify_sequence_fixture(report_path: Path) -> dict[str, Any]:
    report = base.canonical_new_path(report_path, "fixture report")
    ffmpeg = base.require_tool("ffmpeg")
    ffprobe = base.require_tool("ffprobe")
    width = height = 32
    with tempfile.TemporaryDirectory(prefix="si-ep08-quote-fixture-") as temporary_dir:
        root = Path(temporary_dir)
        main = root / "main.mkv"
        patch_dir = root / "patch"
        patch_dir.mkdir()
        patched = root / "patched.mkv"
        base.run_capture(
            [
                ffmpeg, "-hide_banner", "-nostdin", "-y", "-f", "lavfi", "-i",
                f"color=c=black:s={width}x{height}:r={FPS}", "-frames:v", "5", "-an",
                "-c:v", "ffv1", "-level", "3", "-pix_fmt", "yuv420p", str(main),
            ],
            "create five-frame FFV1 fixture",
        )
        write_solid_png(patch_dir / "frame-2.png", width, height, (255, 0, 0))
        write_solid_png(patch_dir / "frame-3.png", width, height, (0, 255, 0))
        fixture_graph = (
            f"[1:v]setpts=PTS-STARTPTS+2/({FPS}*TB)[p];"
            "[0:v][p]overlay=eof_action=pass:repeatlast=0:enable='between(n,2,3)'[vout]"
        )
        fixture_command = [
            ffmpeg, "-hide_banner", "-nostdin", "-y", "-filter_complex_threads", "2",
            "-threads", "2", "-i", str(main),
            "-threads", "2", "-framerate", str(FPS), "-start_number", "2", "-i", str(patch_dir / "frame-%d.png"),
            "-filter_complex", fixture_graph, "-map", "[vout]", "-an", "-frames:v", "5",
            "-c:v", "ffv1", "-level", "3", "-pix_fmt", "yuv420p", str(patched),
        ]
        base.run_capture(fixture_command, "overlay numbered PNG sequence in FFV1 fixture")
        fixture_probe = base.probe_media(ffprobe, patched)
        video = base.selected_video(fixture_probe, "fixture output")
        if video.get("codec_name") != "ffv1" or int(video.get("nb_read_frames", -1)) != 5:
            raise base.RepairError(f"fixture output must be five-frame FFV1; got codec={video.get('codec_name')!r}, frames={video.get('nb_read_frames')!r}")
        before = decode_rgb_frames(ffmpeg, main, width, height, 5)
        after = decode_rgb_frames(ffmpeg, patched, width, height, 5)
        before_hashes = [hashlib.sha256(frame).hexdigest() for frame in before]
        after_hashes = [hashlib.sha256(frame).hexdigest() for frame in after]
        changed = [index for index, (left, right) in enumerate(zip(before, after)) if left != right]
        if changed != [2, 3]:
            raise base.RepairError(f"sequence fixture changed output indices {changed}; expected exactly [2, 3]")
        center = (height // 2 * width + width // 2) * 3
        red = tuple(after[2][center:center + 3])
        green = tuple(after[3][center:center + 3])
        if not (red[0] > 200 and red[1] < 80 and green[1] > 200 and green[0] < 80):
            raise base.RepairError(f"sequence frame order is wrong: expected red then green, got {red}, {green}")
        evidence = {
            "schema_version": 1,
            "purpose": "verify numbered image2 sequence start_number and PTS offset target only requested output frames",
            "verified": True,
            "main_codec": "ffv1",
            "main_frames": 5,
            "sequence_start_number": 2,
            "sequence_frames": 2,
            "fps": FPS,
            "pts_offset_seconds": 2 / FPS,
            "enable_expression": "between(n,2,3)",
            "changed_output_indices": changed,
            "patch_order_center_rgb": [red, green],
            "unchanged_output_indices": [index for index in range(5) if index not in changed],
            "input_frame_rgb_sha256": before_hashes,
            "output_frame_rgb_sha256": after_hashes,
            "ffmpeg_command": fixture_command,
            "output_video_sha256": base.sha256_file(patched),
        }
    temp_report = base.write_json_temp(report, evidence)
    try:
        base.publish_no_clobber(temp_report, report)
    finally:
        temp_report.unlink(missing_ok=True)
    return evidence


def main() -> int:
    args = parse_args()
    try:
        if args.verify_sequence_fixture:
            if args.fixture_report is None:
                raise base.RepairError("--fixture-report is required with --verify-sequence-fixture")
            if any(value is not None for value in (args.input, args.frames_dir, args.output, args.expected_frames, args.report, args.fixture_evidence)):
                raise base.RepairError("repair arguments cannot be combined with --verify-sequence-fixture")
            evidence = verify_sequence_fixture(args.fixture_report)
            print(json.dumps({"fixture_verified": evidence["verified"], "report": str(args.fixture_report.resolve())}))
            return 0
        if any(value is None for value in (args.input, args.frames_dir, args.output, args.expected_frames, args.report)):
            raise base.RepairError("repair mode requires --input, --frames-dir, --output, --expected-frames, and --report")
        evidence = repair(args)
    except base.RepairError as exc:
        print(f"[repair-quote-window] ERROR: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "output": evidence["output"]["path"],
                "report": str(args.report.resolve()),
                "frames": evidence["overlay_sequence"]["frame_count"],
                "audio_payloads_identical": True,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
