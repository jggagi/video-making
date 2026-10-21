#!/usr/bin/env python3
"""Replace selected absolute frames in an existing EP12 MP4.

Each frame PNG is a one-frame input (the image demuxer is not looped).  The
overlay filter caches its last frame and is enabled only for the matching
zero-based main-video frame number.  A local five-frame FFV1 fixture verified
that enable='eq(n,2)' changes only frame index 2 with the FFmpeg overlay options
used below; n is therefore the absolute, zero-based output frame index.

This utility only publishes a new MP4 and a new JSON report.  It refuses to
replace existing paths, never edits its input, and records technical evidence;
it does not establish human playback acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from fractions import Fraction
from typing import Any


FPS = 60
DURATION_SECONDS = 90.0
NATIVE_DIMENSIONS = {(2160, 3840)}
FRAME_NAME = re.compile(r"^frame-(\d+)\.png$", re.IGNORECASE)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class RepairError(RuntimeError):
    """Expected validation or media-processing failure."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Overlay selected zero-based frames into a new native EP12 MP4."
    )
    parser.add_argument("--input", required=True, type=Path, help="Existing native 4K MP4; never modified.")
    parser.add_argument("--frames-dir", required=True, type=Path, help="Directory containing frame-<id>.png images.")
    parser.add_argument("--output", required=True, type=Path, help="New MP4 path; must not already exist.")
    parser.add_argument("--expected-frames", required=True, type=int, help="Expected absolute frame count (EP12: 5400).")
    parser.add_argument("--report", required=True, type=Path, help="New JSON evidence path; must not already exist.")
    return parser.parse_args()


def run_capture(argv: list[str], phase: str, *, timeout: int | None = None) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RepairError(f"{phase}: could not complete {Path(argv[0]).name}: {exc}") from None
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()[-2000:]
        raise RepairError(f"{phase}: {Path(argv[0]).name} exited {result.returncode}: {detail or 'no diagnostics'}")
    return result


def require_tool(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise RepairError(f"required executable is unavailable: {name}")
    return executable


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            for block in iter(lambda: source.read(4 * 1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise RepairError(f"cannot hash {path}: {exc}") from None
    return digest.hexdigest()


def probe_media(ffprobe: str, media: Path) -> dict[str, Any]:
    result = run_capture(
        [
            ffprobe, "-v", "error", "-count_frames", "-show_format", "-show_streams",
            "-of", "json", str(media),
        ],
        f"probe {media.name}",
        timeout=1800,
    )
    try:
        probe = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise RepairError(f"ffprobe returned invalid JSON for {media}") from None
    if not isinstance(probe, dict) or not isinstance(probe.get("streams"), list):
        raise RepairError(f"ffprobe returned incomplete metadata for {media}")
    return probe


def selected_video(probe: dict[str, Any], label: str) -> dict[str, Any]:
    videos = [stream for stream in probe["streams"] if stream.get("codec_type") == "video"]
    if len(videos) != 1:
        raise RepairError(f"{label} must contain exactly one video stream; found {len(videos)}")
    return videos[0]


def parse_rate(value: Any, label: str) -> Fraction:
    try:
        rate = Fraction(str(value))
    except (ValueError, ZeroDivisionError, TypeError):
        raise RepairError(f"{label} has an invalid frame rate: {value!r}") from None
    return rate


def validate_timeline(probe: dict[str, Any], expected_frames: int, label: str) -> dict[str, Any]:
    video = selected_video(probe, label)
    dimensions = (video.get("width"), video.get("height"))
    if dimensions not in NATIVE_DIMENSIONS:
        raise RepairError(f"{label} must be native 4K 3840x2160 or 2160x3840; got {dimensions}")
    rate = parse_rate(video.get("avg_frame_rate"), f"{label} average frame rate")
    if rate != FPS:
        raise RepairError(f"{label} must be {FPS} fps; got {rate}")
    frames_text = video.get("nb_read_frames")
    try:
        frames = int(frames_text)
    except (TypeError, ValueError):
        raise RepairError(f"ffprobe could not count decoded frames in {label}: {frames_text!r}") from None
    if frames != expected_frames:
        raise RepairError(f"{label} must contain {expected_frames} frames; ffprobe counted {frames}")
    try:
        duration = float(probe["format"]["duration"])
    except (KeyError, TypeError, ValueError):
        raise RepairError(f"ffprobe did not report a usable format duration for {label}") from None
    if abs(duration - DURATION_SECONDS) > 0.001:
        raise RepairError(f"{label} must be exactly 90 seconds (within 1 ms); got {duration:.6f}s")
    return {"width": dimensions[0], "height": dimensions[1], "fps": int(rate), "frames": frames, "duration_seconds": duration}


def read_png_dimensions(path: Path) -> tuple[int, int]:
    """Read PNG IHDR and reject APNG without loading a native 4K raster."""
    try:
        with path.open("rb") as png:
            if png.read(8) != PNG_SIGNATURE:
                raise RepairError(f"not a PNG image: {path.name}")
            length_bytes = png.read(4)
            chunk_type = png.read(4)
            if len(length_bytes) != 4 or chunk_type != b"IHDR" or struct.unpack(">I", length_bytes)[0] != 13:
                raise RepairError(f"invalid PNG IHDR: {path.name}")
            ihdr = png.read(13)
            crc = png.read(4)
            if len(ihdr) != 13 or len(crc) != 4:
                raise RepairError(f"truncated PNG header: {path.name}")
            width, height = struct.unpack(">II", ihdr[:8])
            # Scan chunk headers only; frame PNGs are expected to be static.
            while True:
                raw_length = png.read(4)
                if len(raw_length) != 4:
                    raise RepairError(f"truncated PNG chunks: {path.name}")
                length = struct.unpack(">I", raw_length)[0]
                kind = png.read(4)
                if len(kind) != 4:
                    raise RepairError(f"truncated PNG chunk type: {path.name}")
                if kind == b"acTL":
                    raise RepairError(f"animated PNG is not allowed as a single-frame overlay: {path.name}")
                if kind == b"IEND":
                    break
                png.seek(length + 4, os.SEEK_CUR)  # chunk payload and CRC
    except OSError as exc:
        raise RepairError(f"cannot read PNG {path}: {exc}") from None
    if width < 1 or height < 1:
        raise RepairError(f"invalid PNG dimensions in {path.name}: {width}x{height}")
    return width, height


def discover_frames(directory: Path, expected_frames: int, dimensions: tuple[int, int]) -> list[dict[str, Any]]:
    if not directory.is_dir():
        raise RepairError(f"frames directory does not exist: {directory}")
    frames: list[dict[str, Any]] = []
    seen: dict[int, str] = {}
    try:
        candidates = sorted(path for path in directory.iterdir() if path.suffix.lower() == ".png")
    except OSError as exc:
        raise RepairError(f"cannot list frames directory {directory}: {exc}") from None
    for path in candidates:
        match = FRAME_NAME.fullmatch(path.name)
        if match is None:
            raise RepairError(f"PNG filename must be frame-<zero-based-id>.png: {path.name}")
        frame_id = int(match.group(1))
        if frame_id in seen:
            raise RepairError(f"duplicate numeric frame id {frame_id}: {seen[frame_id]} and {path.name}")
        seen[frame_id] = path.name
        if frame_id < 0 or frame_id >= expected_frames:
            raise RepairError(f"frame id {frame_id} is outside [0, {expected_frames})")
        actual_dimensions = read_png_dimensions(path)
        if actual_dimensions != dimensions:
            raise RepairError(f"{path.name} is {actual_dimensions[0]}x{actual_dimensions[1]}; expected {dimensions[0]}x{dimensions[1]}")
        frames.append({"frame": frame_id, "path": path.resolve(), "sha256": sha256_file(path)})
    if not frames:
        raise RepairError(f"no frame-<id>.png overlays found in {directory}")
    return sorted(frames, key=lambda item: item["frame"])


def audio_packet_hashes(ffprobe: str, media: Path, audio_count: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for audio_index in range(audio_count):
        result = run_capture(
            [
                ffprobe, "-v", "error", "-select_streams", f"a:{audio_index}", "-show_packets",
                "-show_entries", "packet=data_hash", "-show_data_hash", "sha256", "-of", "json", str(media),
            ],
            f"hash audio packets a:{audio_index} in {media.name}",
            timeout=1800,
        )
        try:
            payload = json.loads(result.stdout.decode("utf-8"))
            packets = payload["packets"]
            hashes = [packet["data_hash"] for packet in packets]
        except (UnicodeError, json.JSONDecodeError, KeyError, TypeError):
            raise RepairError(f"could not read packet hashes for audio stream a:{audio_index} in {media}") from None
        if not hashes:
            raise RepairError(f"audio stream a:{audio_index} has no probeable packets in {media}")
        results.append({"stream": audio_index, "packet_count": len(hashes), "packet_sha256": hashes})
    return results


def check_faststart(path: Path) -> bool:
    """Return whether the top-level MP4 moov atom precedes mdat."""
    try:
        file_size = path.stat().st_size
        atoms: list[tuple[str, int]] = []
        with path.open("rb") as media:
            offset = 0
            while offset + 8 <= file_size:
                media.seek(offset)
                header = media.read(8)
                size, kind = struct.unpack(">I4s", header)
                header_size = 8
                if size == 1:
                    extended = media.read(8)
                    if len(extended) != 8:
                        return False
                    size = struct.unpack(">Q", extended)[0]
                    header_size = 16
                elif size == 0:
                    size = file_size - offset
                if size < header_size or offset + size > file_size:
                    return False
                atoms.append((kind.decode("latin-1"), offset))
                offset += size
        positions = {kind: offset for kind, offset in atoms}
        return "moov" in positions and "mdat" in positions and positions["moov"] < positions["mdat"]
    except OSError:
        return False


def canonical_new_path(value: Path, label: str) -> Path:
    candidate = value.expanduser().resolve(strict=False)
    if not candidate.parent.is_dir():
        raise RepairError(f"{label} parent directory must already exist: {candidate.parent}")
    if os.path.lexists(candidate):
        raise RepairError(f"{label} already exists; refusing to overwrite: {candidate}")
    return candidate


def make_temp_file(parent: Path, prefix: str, suffix: str) -> Path:
    try:
        fd, name = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=parent)
        os.close(fd)
    except OSError as exc:
        raise RepairError(f"cannot create temporary file in {parent}: {exc}") from None
    return Path(name)


def ffmpeg_command(
    ffmpeg: str,
    source: Path,
    frames: list[dict[str, Any]],
    expected_frames: int,
    temporary_output: Path,
) -> list[str]:
    argv = [
        ffmpeg, "-hide_banner", "-nostdin", "-y", "-filter_complex_threads", "2",
        "-threads", "2", "-i", str(source),
    ]
    for frame in frames:
        # One PNG input per target; intentionally no image2 -loop option.
        argv.extend(["-threads", "2", "-framerate", str(FPS), "-i", str(frame["path"])])
    chain: list[str] = []
    previous = "0:v"
    for input_index, frame in enumerate(frames, start=1):
        output_label = f"v{input_index}"
        chain.append(
            f"[{previous}][{input_index}:v]overlay=x=0:y=0:format=auto:"
            f"eof_action=repeat:repeatlast=1:shortest=0:enable='eq(n,{frame['frame']})'[{output_label}]"
        )
        previous = output_label
    graph = ";".join(chain) + f";[{previous}]null[vout]"
    argv.extend(
        [
            "-filter_complex", graph, "-map", "[vout]", "-map", "0:a?", "-map_metadata", "0",
            "-map_chapters", "0", "-fps_mode", "passthrough",
            "-c:v", "libx264", "-preset", "fast", "-crf", "15", "-pix_fmt", "yuv420p",
            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
            "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709",
            "-threads", "4", "-c:a", "copy", "-movflags", "+faststart", str(temporary_output),
        ]
    )
    return argv


def publish_no_clobber(temporary: Path, destination: Path) -> tuple[int, int]:
    """Atomically create destination without replacing a racing existing path."""
    try:
        os.link(temporary, destination)
        info = destination.stat()
        return info.st_dev, info.st_ino
    except FileExistsError:
        raise RepairError(f"destination appeared during processing; refusing to overwrite: {destination}") from None
    except OSError as exc:
        raise RepairError(f"cannot publish {destination} without replacement: {exc}") from None


def remove_published_if_owned(path: Path, identity: tuple[int, int] | None) -> None:
    if identity is None:
        return
    try:
        current = path.stat()
        if (current.st_dev, current.st_ino) == identity:
            path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass


def write_json_temp(path: Path, data: dict[str, Any]) -> Path:
    temporary = make_temp_file(path.parent, f".{path.name}.", ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise RepairError(f"cannot write temporary report: {exc}") from None
    return temporary


def repair(args: argparse.Namespace) -> dict[str, Any]:
    if args.expected_frames != 5400:
        raise RepairError(f"EP12 requires --expected-frames 5400; got {args.expected_frames}")
    source = args.input.expanduser().resolve(strict=True)
    if not source.is_file() or source.suffix.lower() != ".mp4":
        raise RepairError(f"--input must be an existing MP4 file: {source}")
    output = canonical_new_path(args.output, "output")
    report = canonical_new_path(args.report, "report")
    if output.suffix.lower() != ".mp4":
        raise RepairError(f"--output must use an .mp4 extension: {output}")
    if output == source or report == source or output == report:
        raise RepairError("input, output, and report paths must be distinct")
    try:
        if os.path.samefile(source, output) or os.path.samefile(source, report):
            raise RepairError("input and output/report must not refer to the same file")
    except FileNotFoundError:
        pass

    ffmpeg = require_tool("ffmpeg")
    ffprobe = require_tool("ffprobe")
    input_probe = probe_media(ffprobe, source)
    input_timeline = validate_timeline(input_probe, args.expected_frames, "input")
    source_video = selected_video(input_probe, "input")
    audio_count = sum(stream.get("codec_type") == "audio" for stream in input_probe["streams"])
    if audio_count < 1:
        raise RepairError("input MP4 must contain audio so copied audio payload can be verified")
    frames = discover_frames(args.frames_dir.expanduser().resolve(strict=True), args.expected_frames, (input_timeline["width"], input_timeline["height"]))

    input_hash_before = sha256_file(source)
    audio_before = audio_packet_hashes(ffprobe, source, audio_count)
    temp_output = make_temp_file(output.parent, f".{output.stem}.repair-", ".mp4")
    temp_report: Path | None = None
    published_output: tuple[int, int] | None = None
    published_report: tuple[int, int] | None = None
    try:
        command = ffmpeg_command(ffmpeg, source, frames, args.expected_frames, temp_output)
        run_capture(command, "frame overlay encode", timeout=5400)

        input_hash_after = sha256_file(source)
        if input_hash_after != input_hash_before:
            raise RepairError("input MP4 changed while repair was running")
        for frame in frames:
            if sha256_file(frame["path"]) != frame["sha256"]:
                raise RepairError(f"overlay PNG changed while repair was running: {frame['path'].name}")

        output_probe = probe_media(ffprobe, temp_output)
        output_timeline = validate_timeline(output_probe, args.expected_frames, "output")
        output_video = selected_video(output_probe, "output")
        if output_video.get("codec_name") != "h264":
            raise RepairError(f"output video codec must be H.264; got {output_video.get('codec_name')!r}")
        if output_video.get("pix_fmt") != "yuv420p":
            raise RepairError(f"output pixel format must be yuv420p; got {output_video.get('pix_fmt')!r}")
        color_tags = {
            "color_primaries": output_video.get("color_primaries"),
            "color_transfer": output_video.get("color_transfer"),
            "color_space": output_video.get("color_space"),
        }
        if color_tags != {"color_primaries": "bt709", "color_transfer": "bt709", "color_space": "bt709"}:
            raise RepairError(f"output must be tagged BT.709; got {color_tags}")
        output_audio_count = sum(stream.get("codec_type") == "audio" for stream in output_probe["streams"])
        if output_audio_count != audio_count:
            raise RepairError(f"audio stream count changed: input {audio_count}, output {output_audio_count}")
        audio_after = audio_packet_hashes(ffprobe, temp_output, output_audio_count)
        if audio_before != audio_after:
            raise RepairError("audio packet payload hashes differ; copied audio was not preserved byte-for-byte")
        if output_timeline != input_timeline:
            raise RepairError(f"video timeline changed: input {input_timeline}, output {output_timeline}")
        if not check_faststart(temp_output):
            raise RepairError("output MP4 does not place moov before mdat despite +faststart")

        evidence = {
            "schema_version": 1,
            "operation": "selected_absolute_frame_overlay",
            "human_playback_verified": False,
            "input": {
                "path": str(source),
                "sha256": input_hash_before,
                "timeline": input_timeline,
                "ffprobe": input_probe,
                "audio_packet_hashes": audio_before,
            },
            "overlays": [
                {"frame": item["frame"], "filename": item["path"].name, "sha256": item["sha256"]}
                for item in frames
            ],
            "ffmpeg_command": command,
            "output": {
                "path": str(output),
                "sha256": sha256_file(temp_output),
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
                "basis": "absolute zero-based decoded main-video frame n",
                "enable_expression_per_overlay": "eq(n,<frame-id>)",
                "fixture_verified": "five-frame FFV1 fixture: eq(n,2) changed only output frame index 2",
                "no_fps_conversion": True,
            },
        }
        temp_report = write_json_temp(report, evidence)
        published_output = publish_no_clobber(temp_output, output)
        try:
            published_report = publish_no_clobber(temp_report, report)
        except RepairError:
            remove_published_if_owned(output, published_output)
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
        # The report is published last; if an exception occurs after report
        # publication, preserve the complete evidence/output pair for review.


def main() -> int:
    args = parse_args()
    try:
        evidence = repair(args)
    except RepairError as exc:
        print(f"[repair-frames] ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"output": evidence["output"]["path"], "report": str(args.report.resolve()), "frames": len(evidence["overlays"]), "audio_payloads_identical": True}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
