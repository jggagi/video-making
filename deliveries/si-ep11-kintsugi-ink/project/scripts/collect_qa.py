#!/usr/bin/env python3
"""Collect hash-bound frame, loudness, and AAC comparison evidence from EP11's final MP4."""

from __future__ import annotations

from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import wave

import numpy as np
from PIL import Image, ImageDraw


PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT.parent
REVIEW = WORK / "review"
SAMPLE_RATE = 48_000
CHANNELS = 2
BYTES_PER_SAMPLE = 2
MOBILE_SIZE = (360, 640)
REPRESENTATIVE_FRAMES = [0, 120, 600, 960, 1560, 2280, 2940, 3540, 3900, 4500, 4859, 4860, 4889, 4890, 5040, 5160, 5399]
MOTION_PAIRS = [
    (120, 270),
    (960, 1110),
    (1560, 1710),
    (2280, 2430),
    (2940, 3090),
    (3900, 4050),
    (4500, 4650),
    (5040, 5190),
]
NATIVE_FRAMES = [2280, 3540, 5040]
SAMPLE_WINDOWS_SECONDS = [(1, 4), (47, 50), (86, 89)]
ALL_MOBILE_FRAMES = sorted(
    set(REPRESENTATIVE_FRAMES)
    | {frame for pair in MOTION_PAIRS for frame in pair}
    | set(NATIVE_FRAMES)
)


class QAError(RuntimeError):
    """The final media or an evidence collection step is unavailable."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str]):
    try:
        result = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as error:
        raise QAError(f"could not start {command[0]}: {error}") from None
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace")[-1600:]
        raise QAError(f"{command[0]} exited {result.returncode}: {detail}")
    return result


def ffprobe(media: Path) -> dict:
    result = run([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(media)
    ])
    try:
        return json.loads(result.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise QAError("ffprobe did not return valid JSON") from None


def stream_duration(stream: dict, container: dict) -> float | None:
    value = stream.get("duration")
    if value in (None, "N/A"):
        value = container.get("duration")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def rate(stream: dict) -> Fraction | None:
    for key in ("avg_frame_rate", "r_frame_rate"):
        value = stream.get(key)
        try:
            parsed = Fraction(value)
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if parsed > 0:
            return parsed
    return None


def selected_mobile_frames(media: Path) -> dict[int, bytes]:
    select = "+".join(f"eq(n\\,{frame})" for frame in ALL_MOBILE_FRAMES)
    scale = "scale=360:640:force_original_aspect_ratio=decrease,pad=360:640:(ow-iw)/2:(oh-ih)/2"
    result = run([
        "ffmpeg", "-v", "error", "-xerror", "-i", str(media), "-map", "0:v:0",
        "-vf", f"select={select},{scale}", "-vsync", "0",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ])
    frame_bytes = MOBILE_SIZE[0] * MOBILE_SIZE[1] * 3
    expected_bytes = len(ALL_MOBILE_FRAMES) * frame_bytes
    if len(result.stdout) != expected_bytes:
        raise QAError(
            f"exact frame selection returned {len(result.stdout) // frame_bytes} frames; "
            f"expected {len(ALL_MOBILE_FRAMES)}"
        )
    return {
        frame: result.stdout[index * frame_bytes:(index + 1) * frame_bytes]
        for index, frame in enumerate(ALL_MOBILE_FRAMES)
    }


def image_for(frame: int, frames: dict[int, bytes]) -> Image.Image:
    return Image.frombytes("RGB", MOBILE_SIZE, frames[frame])


def save_representative_sheet(frames: dict[int, bytes], path: Path) -> None:
    columns = 6
    cell_height = MOBILE_SIZE[1] + 28
    rows = math.ceil(len(REPRESENTATIVE_FRAMES) / columns)
    sheet = Image.new("RGB", (columns * MOBILE_SIZE[0], rows * cell_height), "#111820")
    draw = ImageDraw.Draw(sheet)
    for index, frame in enumerate(REPRESENTATIVE_FRAMES):
        x = (index % columns) * MOBILE_SIZE[0]
        y = (index // columns) * cell_height
        draw.text((x + 8, y + 6), f"frame {frame} / {frame / 60:.2f}s", fill="#d6e0e7")
        sheet.paste(image_for(frame, frames), (x, y + 28))
    sheet.save(path, format="JPEG", quality=90, optimize=True)


def save_motion_sheets(frames: dict[int, bytes], directory: Path) -> list[Path]:
    outputs: list[Path] = []
    pair_gap = 4
    label_height = 28
    panel_width = 2 * MOBILE_SIZE[0] + pair_gap
    panel_height = MOBILE_SIZE[1] + label_height
    outer_gap = 12
    for group_index in range(2):
        group = MOTION_PAIRS[group_index * 4:(group_index + 1) * 4]
        sheet = Image.new(
            "RGB",
            (2 * panel_width + 3 * outer_gap, 2 * panel_height + 3 * outer_gap),
            "#111820",
        )
        draw = ImageDraw.Draw(sheet)
        for index, (first, second) in enumerate(group):
            column, row = index % 2, index // 2
            x = outer_gap + column * (panel_width + outer_gap)
            y = outer_gap + row * (panel_height + outer_gap)
            draw.text(
                (x + 5, y + 5),
                f"{first} ({first / 60:.2f}s) -> {second} ({second / 60:.2f}s)",
                fill="#d6e0e7",
            )
            sheet.paste(image_for(first, frames), (x, y + label_height))
            sheet.paste(image_for(second, frames), (x + MOBILE_SIZE[0] + pair_gap, y + label_height))
        output = directory / f"motion-pairs-contact-{group_index + 1:02d}.jpg"
        sheet.save(output, format="JPEG", quality=90, optimize=True)
        outputs.append(output)
    return outputs


def save_native_frames(media: Path, directory: Path) -> list[Path]:
    select = "+".join(f"eq(n\\,{frame})" for frame in NATIVE_FRAMES)
    pattern = directory / "encoded-native-%02d.png"
    run([
        "ffmpeg", "-v", "error", "-xerror", "-i", str(media), "-map", "0:v:0",
        "-vf", f"select={select}", "-vsync", "0", "-frames:v", str(len(NATIVE_FRAMES)),
        str(pattern),
    ])
    outputs = [directory / f"encoded-native-{index:02d}.png" for index in range(1, len(NATIVE_FRAMES) + 1)]
    if not all(path.is_file() for path in outputs):
        raise QAError("native-resolution frame extraction did not produce all requested frames")
    return outputs


def measure_ebur128(media: Path) -> dict[str, float]:
    result = run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(media), "-map", "0:a:0",
        "-af", "ebur128=peak=true", "-f", "null", "-",
    ])
    text = result.stderr.decode("utf-8", errors="replace")
    integrated_values = re.findall(r"I:\s*(-?\d+(?:\.\d+)?)\s+LUFS", text)
    peak_match = re.search(r"True peak:\s*\n\s*Peak:\s*(-?\d+(?:\.\d+)?)\s+dBFS", text)
    if not integrated_values or not peak_match:
        raise QAError("FFmpeg ebur128 output did not contain integrated LUFS and true-peak values")
    return {
        "integrated_lufs": float(integrated_values[-1]),
        "true_peak_dbfs": float(peak_match.group(1)),
    }


def read_master(master: Path) -> tuple[np.ndarray, dict[str, int]]:
    try:
        with wave.open(str(master), "rb") as audio:
            fields = {
                "channels": audio.getnchannels(),
                "sample_rate": audio.getframerate(),
                "sample_width_bytes": audio.getsampwidth(),
                "samples_per_channel": audio.getnframes(),
            }
            if (fields["channels"], fields["sample_rate"], fields["sample_width_bytes"]) != (
                CHANNELS, SAMPLE_RATE, BYTES_PER_SAMPLE
            ):
                raise QAError("PCM master must be stereo, 48kHz, signed 16-bit WAV")
            data = audio.readframes(audio.getnframes())
    except (OSError, wave.Error) as error:
        raise QAError(f"could not read PCM master: {error}") from None
    samples = np.frombuffer(data, dtype="<i2").reshape(-1, CHANNELS)
    return samples, fields


def compare_audio(media: Path, master_path: Path, container: dict, audio_stream: dict) -> dict:
    master, master_info = read_master(master_path)
    result = run([
        "ffmpeg", "-v", "error", "-xerror", "-i", str(media), "-map", "0:a:0",
        "-ar", str(SAMPLE_RATE), "-ac", str(CHANNELS), "-f", "s16le", "-",
    ])
    if len(result.stdout) % (CHANNELS * BYTES_PER_SAMPLE):
        raise QAError("decoded AAC PCM byte count is not frame-aligned")
    decoded = np.frombuffer(result.stdout, dtype="<i2").reshape(-1, CHANNELS)
    correlations = []
    for start_seconds, end_seconds in SAMPLE_WINDOWS_SECONDS:
        start = start_seconds * SAMPLE_RATE
        end = end_seconds * SAMPLE_RATE
        if end > len(master) or end > len(decoded):
            correlation = None
            sample_count = max(0, min(len(master), len(decoded), end) - start)
        else:
            source = master[start:end].astype(np.float64).reshape(-1)
            encoded = decoded[start:end].astype(np.float64).reshape(-1)
            if np.std(source) == 0 or np.std(encoded) == 0:
                correlation = None
            else:
                correlation = float(np.corrcoef(source, encoded)[0, 1])
            sample_count = end - start
        correlations.append({
            "seconds": [start_seconds, end_seconds],
            "sample_range_per_channel": [start, end],
            "samples_per_channel_compared": sample_count,
            "waveform_correlation": correlation,
        })
    audio_duration = stream_duration(audio_stream, container)
    try:
        container_duration = float(container["duration"])
    except (KeyError, TypeError, ValueError):
        container_duration = None
    return {
        "master": {
            "path": str(master_path.relative_to(WORK)),
            "sha256": sha256_file(master_path),
            **master_info,
            "duration_seconds": master_info["samples_per_channel"] / SAMPLE_RATE,
        },
        "decoded_aac": {
            "samples_per_channel": len(decoded),
            "sample_rate": SAMPLE_RATE,
            "channels": CHANNELS,
            "duration_seconds": len(decoded) / SAMPLE_RATE,
            "audio_stream_duration_seconds": audio_duration,
            "container_duration_seconds": container_duration,
            "sample_count_difference_vs_master": len(decoded) - len(master),
            "correlation_windows": correlations,
            "padding_note": (
                "AAC priming or end padding may change decoded sample count. Correlations use the same "
                "presentation-time sample ranges without shifting either stream."
            ),
        },
    }


def checks_for_streams(video: dict, audio: dict, container: dict) -> tuple[dict[str, str], dict]:
    frame_rate = rate(video)
    duration = stream_duration(video, container)
    try:
        frame_count = int(video.get("nb_frames"))
    except (TypeError, ValueError):
        frame_count = round(duration * float(frame_rate)) if duration is not None and frame_rate else None
    values = {
        "codec_name": video.get("codec_name"),
        "width": video.get("width"),
        "height": video.get("height"),
        "avg_frame_rate": video.get("avg_frame_rate"),
        "r_frame_rate": video.get("r_frame_rate"),
        "nb_frames": video.get("nb_frames"),
        "duration_seconds": duration,
        "pix_fmt": video.get("pix_fmt"),
        "color_space": video.get("color_space"),
        "color_transfer": video.get("color_transfer"),
        "color_primaries": video.get("color_primaries"),
    }
    try:
        audio_rate = int(audio.get("sample_rate"))
    except (TypeError, ValueError):
        audio_rate = None
    checks = {
        "dimensions": "PASS" if (video.get("width"), video.get("height")) == (2160, 3840) else "FAIL",
        "frame_rate": "PASS" if frame_rate == Fraction(60, 1) else "FAIL",
        "frame_count": "PASS" if frame_count == 5400 else "FAIL",
        "video_duration": "PASS" if duration is not None and abs(duration - 90.0) <= 0.02 else "FAIL",
        "audio_codec": "PASS" if audio.get("codec_name") == "aac" else "FAIL",
        "audio_format": "PASS" if (audio_rate, audio.get("channels")) == (SAMPLE_RATE, CHANNELS) else "FAIL",
    }
    values["parsed_frame_rate"] = (
        {"numerator": frame_rate.numerator, "denominator": frame_rate.denominator}
        if frame_rate else None
    )
    values["parsed_frame_count"] = frame_count
    return checks, values


def artifact_record(path: Path, published_directory: Path, **extra: object) -> dict:
    published_path = published_directory / path.name
    return {
        "path": published_path.relative_to(WORK).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        **extra,
    }


def main() -> int:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise SystemExit("ffmpeg and ffprobe must be available on PATH")
    try:
        manifest = json.loads((WORK / "delivery.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot read delivery.json: {error}") from None
    media = WORK / manifest["outputs"]["xiaohongshu"]["path"]
    master = WORK / manifest["audio"]["master"]
    if not media.is_file():
        raise SystemExit(f"final encoded MP4 is missing: {media}")
    if not master.is_file():
        raise SystemExit(f"PCM master is missing: {master}")
    if not REVIEW.is_dir():
        raise SystemExit(f"review directory is missing: {REVIEW}")

    media_sha = sha256_file(media)
    final_dir = REVIEW / f"encoded-qa-{media_sha[:12]}"
    if final_dir.exists():
        raise SystemExit(f"hash-bound evidence already exists; preserving it: {final_dir}")
    probe = ffprobe(media)
    video_streams = [stream for stream in probe.get("streams", []) if stream.get("codec_type") == "video"]
    audio_streams = [stream for stream in probe.get("streams", []) if stream.get("codec_type") == "audio"]
    if not video_streams or not audio_streams:
        raise SystemExit("final MP4 must contain video and audio streams")
    container = probe.get("format", {})
    video_checks, video_info = checks_for_streams(video_streams[0], audio_streams[0], container)

    staging = Path(tempfile.mkdtemp(prefix=".encoded-qa-", dir=REVIEW))
    try:
        mobile_frames = selected_mobile_frames(media)
        representative_path = staging / "representative-contact.jpg"
        save_representative_sheet(mobile_frames, representative_path)
        pair_paths = save_motion_sheets(mobile_frames, staging)
        native_paths = save_native_frames(media, staging)
        loudness = measure_ebur128(media)
        audio = compare_audio(media, master, container, audio_streams[0])

        mobile_artifact = artifact_record(representative_path, final_dir)
        pair_artifacts = [
            artifact_record(path, final_dir, pair_index=path.stem[-2:])
            for path in pair_paths
        ]
        native_artifacts = [
            artifact_record(path, final_dir, frame=frame, width=Image.open(path).width, height=Image.open(path).height)
            for frame, path in zip(NATIVE_FRAMES, native_paths)
        ]
        failed_checks = [name for name, result in video_checks.items() if result != "PASS"]
        report = {
            "schema_version": 1,
            "status": "MEASURED_WITH_TECHNICAL_MISMATCH" if failed_checks else "MEASURED",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "scope": "Encoded-media measurements and frame extraction. No visual, listening, audience, or device acceptance is inferred.",
            "media": {
                "path": media.relative_to(WORK).as_posix(),
                "bytes": media.stat().st_size,
                "sha256": media_sha,
                "video": video_info,
                "audio": {
                    key: audio_streams[0].get(key)
                    for key in ("codec_name", "sample_rate", "channels", "channel_layout", "duration", "nb_frames")
                },
            },
            "technical_checks": video_checks,
            "representative_frames": [
                {"frame": frame, "seconds": frame / 60}
                for frame in REPRESENTATIVE_FRAMES
            ],
            "mobile_contact_sheet": mobile_artifact,
            "motion_pairs": [
                {"frames": [start, end], "seconds": [start / 60, end / 60]}
                for start, end in MOTION_PAIRS
            ],
            "motion_pair_contact_sheets": pair_artifacts,
            "native_inspection_frames": native_artifacts,
            "audio_measurements": {
                "ebur128": loudness,
                **audio,
            },
            "acceptance": {
                "representative_visual_observation": "NOT_RUN",
                "continuous_human_review": "NOT_RUN",
                "human_listening": "NOT_RUN",
                "target_device_playback": "NOT_RUN",
                "note": "Contact sheets and native frames are evidence for review, not an observation or approval.",
            },
        }
        (staging / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        staging.rename(final_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    failed_checks = [name for name, result in video_checks.items() if result != "PASS"]
    print(json.dumps({
        "status": "MEASURED_WITH_TECHNICAL_MISMATCH" if failed_checks else "MEASURED",
        "report": (final_dir / "report.json").relative_to(WORK).as_posix(),
        "movie_sha256": media_sha,
        "technical_mismatches": failed_checks,
        "human_and_device_acceptance": "NOT_RUN",
    }, ensure_ascii=False, indent=2))
    return 1 if failed_checks else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except QAError as error:
        raise SystemExit(f"collect_qa.py: {error}") from None
