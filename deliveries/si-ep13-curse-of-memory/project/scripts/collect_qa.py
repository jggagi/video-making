#!/usr/bin/env python3
"""Collect hash-bound encoded-media evidence for EP13.

Frames and audio are read from the final MP4 named by delivery.json. Extracted
audio is kept only in a temporary directory. This tool writes evidence and
measurements; it does not judge visual quality, listen to the film, or write
the platform cover files.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from fractions import Fraction
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DELIVERY_DIR = PROJECT_DIR.parent
REVIEW_DIR = DELIVERY_DIR / "review"
EXPECTED_WIDTH = 2160
EXPECTED_HEIGHT = 3840
FPS = 60
TOTAL_FRAMES = 5400
SAMPLE_RATE = 48_000
CHANNELS = 2
SAMPLES_PER_FRAME = 800
SAMPLE_FRAMES = (0, 60, 900, 1320, 1500, 1680, 1920, 2160, 2820, 2940, 3900, 4020, 4500, 4859, 4860, 4890, 5040, 5160, 5399)
PAIR_FRAMES = ((180, 330), (780, 930), (1440, 1590), (2160, 2310),
               (2940, 3090), (3660, 3810), (4440, 4590), (4950, 5100))
ALL_FRAME_INDEXES = tuple(sorted(set(SAMPLE_FRAMES) | {frame for pair in PAIR_FRAMES for frame in pair}))
CORRELATION_WINDOWS = ((1, 8), (38, 43), (82, 89))
SILENCE_START_FRAME = 4860
SILENCE_END_FRAME = 4890
SILENCE_FIRST_BOUNDARY_SAMPLES = 25 * SAMPLE_RATE // 1000
CORRELATION_LAG_SAMPLES = 4096


class CollectionError(RuntimeError):
    pass


class MissingTool(CollectionError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_capture(argv: list[str], description: str, *, timeout: int | None = None) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(argv, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    except FileNotFoundError as exc:
        raise MissingTool(f"{description}: executable is unavailable: {exc.filename}") from None
    except subprocess.TimeoutExpired:
        raise CollectionError(f"{description}: command timed out") from None
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise CollectionError(f"{description} failed (exit {result.returncode}): {detail[-3000:]}")
    return result


def require_tool(name: str) -> str:
    result = shutil.which(name)
    if not result:
        raise MissingTool(f"{name} is not available on PATH")
    return result


def load_manifest() -> tuple[dict[str, Any], Path, Path]:
    manifest_path = DELIVERY_DIR / "delivery.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CollectionError(f"cannot read delivery.json: {exc}") from None
    outputs = manifest.get("outputs") if isinstance(manifest, dict) else None
    portrait = outputs.get("xiaohongshu") if isinstance(outputs, dict) else None
    relative = portrait.get("path") if isinstance(portrait, dict) else None
    if not isinstance(relative, str) or not relative:
        raise CollectionError("delivery.json outputs.xiaohongshu.path is missing")
    media = (DELIVERY_DIR / relative).resolve()
    try:
        media.relative_to(DELIVERY_DIR.resolve())
    except ValueError:
        raise CollectionError("final media path escapes the delivery directory") from None

    audio = manifest.get("audio")
    master_relative = audio.get("master") if isinstance(audio, dict) else None
    master: Path | None = None
    if isinstance(master_relative, str) and master_relative:
        master = (DELIVERY_DIR / master_relative).resolve()
        try:
            master.relative_to(DELIVERY_DIR.resolve())
        except ValueError:
            raise CollectionError("PCM master path escapes the delivery directory") from None
    return manifest, media, master


def rational(value: Any) -> float | None:
    if not isinstance(value, str) or not value or value == "0/0":
        return None
    try:
        return float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        return None


def probe_media(ffprobe: str, media: Path) -> dict[str, Any]:
    result = run_capture([
        ffprobe, "-v", "error", "-show_format", "-show_streams", "-show_entries",
        "format=format_name,duration:stream=codec_type,codec_name,width,height,avg_frame_rate,r_frame_rate,nb_frames,duration,pix_fmt,color_space,color_primaries,color_transfer,sample_rate,channels",
        "-of", "json", str(media),
    ], f"probe final media {media.name}")
    try:
        data = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CollectionError(f"ffprobe returned invalid JSON for {media.name}: {exc}") from None
    streams = data.get("streams") if isinstance(data, dict) else None
    if not isinstance(streams, list):
        raise CollectionError("ffprobe did not return streams")
    video = next((item for item in streams if isinstance(item, dict) and item.get("codec_type") == "video"), None)
    audio = next((item for item in streams if isinstance(item, dict) and item.get("codec_type") == "audio"), None)
    if not isinstance(video, dict):
        raise CollectionError("final media has no video stream")
    if not isinstance(audio, dict):
        raise CollectionError("final media has no audio stream")
    info = {
        "format_name": (data.get("format") or {}).get("format_name"),
        "container_duration_seconds": (data.get("format") or {}).get("duration"),
        "video": video,
        "audio": audio,
    }
    failures: list[str] = []
    if (video.get("width"), video.get("height")) != (EXPECTED_WIDTH, EXPECTED_HEIGHT):
        failures.append(f"video dimensions are {video.get('width')}x{video.get('height')}; expected {EXPECTED_WIDTH}x{EXPECTED_HEIGHT}")
    for field in ("avg_frame_rate", "r_frame_rate"):
        value = rational(video.get(field))
        if value is not None and abs(value - FPS) > 1e-9:
            failures.append(f"video {field} is {video.get(field)}; expected 60 fps")
    if rational(video.get("avg_frame_rate")) is None:
        failures.append("ffprobe did not provide a usable video average frame rate")
    nb_frames = video.get("nb_frames")
    if nb_frames is None or str(nb_frames) != str(TOTAL_FRAMES):
        failures.append(f"video nb_frames is {nb_frames!r}; expected {TOTAL_FRAMES}")
    video_duration = video.get("duration")
    if video_duration is not None:
        try:
            duration_number = float(video_duration)
        except (ValueError, TypeError):
            failures.append(f"video stream duration is not numeric: {video_duration!r}")
        else:
            if abs(duration_number - TOTAL_FRAMES / FPS) > 1e-6:
                failures.append(f"video stream duration is {duration_number}; expected 90 seconds")
    if failures:
        raise CollectionError("final media metadata mismatch: " + "; ".join(failures))
    return info


def timecode(frame: int) -> str:
    seconds, frame_remainder = divmod(frame, FPS)
    minutes, second_remainder = divmod(seconds, 60)
    return f"{minutes:02d}:{second_remainder:02d}:{frame_remainder:02d}"


def extract_frames(ffmpeg: str, media: Path, indexes: tuple[int, ...], output_dir: Path) -> dict[int, Path]:
    output_dir.mkdir(parents=True, exist_ok=False)
    select = "+".join(f"eq(n\\,{frame})" for frame in indexes)
    pattern = output_dir / "frame-%04d.png"
    run_capture([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-xerror", "-y", "-i", str(media),
        "-map", "0:v:0", "-an", "-vf", f"select={select}", "-fps_mode", "passthrough",
        "-start_number", "0", str(pattern),
    ], f"extract selected frames from final MP4 {media.name}")
    files = sorted(output_dir.glob("frame-*.png"))
    if len(files) != len(indexes):
        raise CollectionError(f"final MP4 frame extraction returned {len(files)} frames; expected {len(indexes)}")
    return dict(zip(indexes, files, strict=True))


def load_image_modules() -> tuple[Any, Any, Any]:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        raise MissingTool("Pillow is unavailable in this Python runtime") from None
    return Image, ImageDraw, ImageFont


def check_native_pngs(frame_paths: dict[int, Path], Image: Any) -> None:
    for frame, path in frame_paths.items():
        try:
            with Image.open(path) as image:
                if image.format != "PNG" or image.size != (EXPECTED_WIDTH, EXPECTED_HEIGHT):
                    raise CollectionError(
                        f"extracted frame {frame} is {image.format} {image.width}x{image.height}; expected native PNG {EXPECTED_WIDTH}x{EXPECTED_HEIGHT}"
                    )
                image.verify()
        except OSError as exc:
            raise CollectionError(f"cannot verify extracted PNG for frame {frame}: {exc}") from None


def make_contact_sheets(frame_paths: dict[int, Path], output_dir: Path, Image: Any, ImageDraw: Any, ImageFont: Any) -> dict[str, Any]:
    font = ImageFont.load_default()
    thumb_width = 360
    thumb_height = round(EXPECTED_HEIGHT * thumb_width / EXPECTED_WIDTH)
    label_height = 26
    columns = 3
    rows = math.ceil(len(SAMPLE_FRAMES) / columns)
    sheet = Image.new("RGB", (columns * thumb_width, rows * (thumb_height + label_height)), (18, 20, 24))
    draw = ImageDraw.Draw(sheet)
    for position, frame in enumerate(SAMPLE_FRAMES):
        with Image.open(frame_paths[frame]) as opened:
            thumbnail = opened.convert("RGB").resize((thumb_width, thumb_height), Image.Resampling.LANCZOS)
        x = (position % columns) * thumb_width
        y = (position // columns) * (thumb_height + label_height)
        sheet.paste(thumbnail, (x, y))
        draw.rectangle((x, y + thumb_height, x + thumb_width, y + thumb_height + label_height), fill=(0, 0, 0))
        draw.text((x + 6, y + thumb_height + 5), f"{timecode(frame)}  f{frame}", fill=(255, 255, 255), font=font)
    sample_path = output_dir / "contact-sheet-mobile-360px.jpg"
    sheet.save(sample_path, format="JPEG", quality=88, optimize=True)

    pair_width = 180
    pair_height = round(EXPECTED_HEIGHT * pair_width / EXPECTED_WIDTH)
    pair_label_height = 38
    pair_columns = 2
    pair_rows = math.ceil(len(PAIR_FRAMES) / pair_columns)
    pairs_sheet = Image.new(
        "RGB", (pair_columns * pair_width * 2, pair_rows * (pair_height + pair_label_height)), (18, 20, 24)
    )
    pair_draw = ImageDraw.Draw(pairs_sheet)
    for position, (start, end) in enumerate(PAIR_FRAMES):
        x = (position % pair_columns) * pair_width * 2
        y = (position // pair_columns) * (pair_height + pair_label_height)
        for offset, frame in ((0, start), (pair_width, end)):
            with Image.open(frame_paths[frame]) as opened:
                thumbnail = opened.convert("RGB").resize((pair_width, pair_height), Image.Resampling.LANCZOS)
            pairs_sheet.paste(thumbnail, (x + offset, y))
        pair_draw.rectangle((x, y + pair_height, x + pair_width * 2, y + pair_height + pair_label_height), fill=(0, 0, 0))
        pair_draw.text(
            (x + 5, y + pair_height + 5),
            f"{timecode(start)} f{start} -> {timecode(end)} f{end}",
            fill=(255, 255, 255), font=font,
        )
    pair_path = output_dir / "motion-pairs-mobile-360px.jpg"
    pairs_sheet.save(pair_path, format="JPEG", quality=88, optimize=True)
    return {
        "representative_contact_sheet": sample_path.name,
        "representative_tile_width_px": thumb_width,
        "representative_columns": columns,
        "motion_pair_sheet": pair_path.name,
        "motion_pair_tile_width_px": pair_width * 2,
        "motion_pair_comparison_width_px": pair_width,
    }


def dbfs(value: float) -> float | None:
    return 20.0 * math.log10(value) if value > 0 else None


def sample_metrics(samples: Any) -> dict[str, Any]:
    import numpy as np

    values = np.asarray(samples, dtype=np.float64)
    if values.size == 0:
        return {"sample_count_per_channel": 0, "rms_dbfs": None, "sample_peak_dbfs": None}
    rms = float(np.sqrt(np.mean(values * values)))
    peak = float(np.max(np.abs(values)))
    return {
        "sample_count_per_channel": int(values.shape[0]),
        "rms_dbfs": dbfs(rms),
        "sample_peak_dbfs": dbfs(peak),
    }


def decode_float_stereo(ffmpeg: str, input_path: Path, scratch_dir: Path, name: str) -> tuple[Path, int]:
    raw_path = scratch_dir / f"{name}.f32le"
    run_capture([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-xerror", "-i", str(input_path),
        "-map", "0:a:0", "-vn", "-c:a", "pcm_f32le", "-ar", str(SAMPLE_RATE), "-ac", str(CHANNELS),
        "-f", "f32le", "-y", str(raw_path),
    ], f"decode {name} audio to temporary float PCM")
    size = raw_path.stat().st_size
    if size % (4 * CHANNELS) != 0:
        raise CollectionError(f"decoded {name} audio byte count is not aligned to stereo float samples")
    return raw_path, size // (4 * CHANNELS)


def best_correlation(reference: Any, candidate: Any, max_lag: int) -> dict[str, Any]:
    import numpy as np

    if reference.ndim != 2 or candidate.ndim != 2 or reference.shape[1] != CHANNELS or candidate.shape[1] != CHANNELS:
        raise CollectionError("audio correlation expects two-channel float PCM arrays")
    sample_count = int(reference.shape[0])
    if sample_count < 2 or candidate.shape[0] < sample_count + 2 * max_lag:
        return {"status": "INCOMPLETE", "reason": "audio sample window is too short for the lag search"}
    centered_ref = reference.astype(np.float64, copy=False) - np.mean(reference, axis=0, keepdims=True)
    candidate64 = candidate.astype(np.float64, copy=False)
    offsets = 2 * max_lag + 1
    convolution_size = candidate64.shape[0] + sample_count - 1
    fft_size = 1 << (convolution_size - 1).bit_length()
    cross = np.zeros(offsets, dtype=np.float64)
    candidate_norm = np.zeros(offsets, dtype=np.float64)
    ref_norm = float(np.sum(centered_ref * centered_ref))

    for channel in range(CHANNELS):
        values = candidate64[:, channel]
        spectrum = np.fft.rfft(values, n=fft_size)
        ref_spectrum = np.fft.rfft(centered_ref[:, channel], n=fft_size)
        correlations = np.fft.irfft(spectrum * np.conjugate(ref_spectrum), n=fft_size)
        cross += correlations[:offsets]

        cumulative = np.concatenate(([0.0], np.cumsum(values, dtype=np.float64)))
        cumulative_sq = np.concatenate(([0.0], np.cumsum(values * values, dtype=np.float64)))
        sums = cumulative[sample_count:sample_count + offsets] - cumulative[:offsets]
        sums_sq = cumulative_sq[sample_count:sample_count + offsets] - cumulative_sq[:offsets]
        candidate_norm += np.maximum(0.0, sums_sq - (sums * sums) / sample_count)

    if ref_norm <= 1e-20:
        return {"status": "INCOMPLETE", "reason": "PCM master window has no measurable signal"}
    denominator = np.sqrt(ref_norm * candidate_norm)
    correlations = np.divide(cross, denominator, out=np.zeros_like(cross), where=denominator > 1e-20)
    best_offset = int(np.argmax(np.abs(correlations)))
    lag = best_offset - max_lag
    return {
        "status": "MEASURED",
        "best_lag_samples": lag,
        "best_lag_ms": lag * 1000.0 / SAMPLE_RATE,
        "normalized_correlation": float(correlations[best_offset]),
        "absolute_normalized_correlation": float(abs(correlations[best_offset])),
        "lag_search_samples_each_side": max_lag,
        "lag_search_ms_each_side": max_lag * 1000.0 / SAMPLE_RATE,
    }


def audio_correlation_and_silence(ffmpeg: str, media: Path, master: Path | None, scratch_dir: Path) -> dict[str, Any]:
    if master is None or not master.is_file():
        return {
            "status": "INCOMPLETE",
            "reason": "delivery.json PCM master is missing; no audio comparison was fabricated",
            "temporary_audio_retained": False,
        }
    try:
        with wave.open(str(master), "rb") as source:
            wav_info = {
                "sample_rate_hz": source.getframerate(),
                "channels": source.getnchannels(),
                "samples_per_channel": source.getnframes(),
                "sample_width_bytes": source.getsampwidth(),
            }
    except (OSError, wave.Error) as exc:
        raise CollectionError(f"cannot read PCM master WAV header: {exc}") from None
    if (wav_info["sample_rate_hz"], wav_info["channels"], wav_info["samples_per_channel"]) != (SAMPLE_RATE, CHANNELS, TOTAL_FRAMES * SAMPLES_PER_FRAME):
        raise CollectionError(f"PCM master must be 48kHz stereo with {TOTAL_FRAMES * SAMPLES_PER_FRAME} samples/channel, got {wav_info}")

    final_raw, final_count = decode_float_stereo(ffmpeg, media, scratch_dir, "encoded-final-audio")
    master_raw, master_count = decode_float_stereo(ffmpeg, master, scratch_dir, "source-pcm-master")
    if master_count != TOTAL_FRAMES * SAMPLES_PER_FRAME:
        raise CollectionError(f"decoded PCM master has {master_count} samples/channel; expected {TOTAL_FRAMES * SAMPLES_PER_FRAME}")
    if final_count < CORRELATION_WINDOWS[-1][1] * SAMPLE_RATE:
        raise CollectionError("decoded final audio is too short for the 82-89 second correlation window")

    try:
        import numpy as np
    except ImportError:
        raise MissingTool("NumPy is unavailable in this Python runtime") from None
    final_pcm = np.fromfile(final_raw, dtype="<f4").reshape((-1, CHANNELS))
    master_pcm = np.fromfile(master_raw, dtype="<f4").reshape((-1, CHANNELS))

    comparisons: list[dict[str, Any]] = []
    for start_seconds, end_seconds in CORRELATION_WINDOWS:
        start = start_seconds * SAMPLE_RATE
        end = end_seconds * SAMPLE_RATE
        margin = CORRELATION_LAG_SAMPLES
        candidate_start = max(0, start - margin)
        candidate_end = min(final_pcm.shape[0], end + margin)
        available_margin = min(start - candidate_start, candidate_end - end)
        comparison = best_correlation(
            master_pcm[start:end],
            final_pcm[candidate_start:candidate_end],
            min(margin, available_margin),
        )
        comparisons.append({
            "window_seconds_half_open": [start_seconds, end_seconds],
            "window_samples_per_channel": end - start,
            **comparison,
        })

    silence_start = SILENCE_START_FRAME * SAMPLES_PER_FRAME
    silence_end = SILENCE_END_FRAME * SAMPLES_PER_FRAME
    source_silence = master_pcm[silence_start:silence_end]
    final_silence = final_pcm[silence_start:silence_end]
    first_boundary_end = min(silence_start + SILENCE_FIRST_BOUNDARY_SAMPLES, silence_end)
    last_boundary_start = max(silence_end - SILENCE_FIRST_BOUNDARY_SAMPLES, first_boundary_end)
    audio_report = {
        "status": "MEASURED",
        "pcm_master": {"path": master.relative_to(DELIVERY_DIR).as_posix(), **wav_info},
        "decoded_final_audio": {
            "source": "final MP4 audio stream",
            "sample_rate_hz": SAMPLE_RATE,
            "channels": CHANNELS,
            "samples_per_channel": int(final_count),
            "temporary_audio_retained": False,
        },
        "correlation": {
            "method": "NumPy normalized cross-correlation over each stated window, allowing a local timing offset",
            "comparisons": comparisons,
            "acceptance_judgment": "NOT_RECORDED",
        },
        "absolute_silence_source_pcm": {
            "frame_interval_half_open": [SILENCE_START_FRAME, SILENCE_END_FRAME],
            "sample_interval_per_channel_half_open": [silence_start, silence_end],
            "source_is_exactly_zero": bool(np.count_nonzero(source_silence) == 0),
            "nonzero_float_samples": int(np.count_nonzero(source_silence)),
            "source_sample_metrics": sample_metrics(source_silence),
        },
        "encoded_aac_silence_window": {
            "frame_interval_half_open": [SILENCE_START_FRAME, SILENCE_END_FRAME],
            "leading_boundary_25ms": {
                "sample_interval_per_channel_half_open": [silence_start, first_boundary_end],
                **sample_metrics(final_pcm[silence_start:first_boundary_end]),
            },
            "interior_excluding_25ms_at_each_edge": {
                "sample_interval_per_channel_half_open": [first_boundary_end, last_boundary_start],
                **sample_metrics(final_pcm[first_boundary_end:last_boundary_start]),
            },
            "trailing_boundary_25ms": {
                "sample_interval_per_channel_half_open": [last_boundary_start, silence_end],
                **sample_metrics(final_pcm[last_boundary_start:silence_end]),
            },
            "measurement_scope": "Decoded AAC samples only; boundary leakage is reported separately from the interior and is not assigned an acceptance verdict.",
        },
    }
    return audio_report


def measure_loudness(ffmpeg: str, media: Path) -> dict[str, Any]:
    result = run_capture([
        ffmpeg, "-hide_banner", "-nostats", "-i", str(media), "-map", "0:a:0",
        "-af", "ebur128=peak=true", "-f", "null", "-",
    ], f"measure encoded audio loudness {media.name}")
    text = (result.stderr + result.stdout).decode("utf-8", errors="replace")
    integrated = re.search(r"(?m)^\s*I:\s*(-?\d+(?:\.\d+)?)\s+LUFS\s*$", text)
    true_peak = re.search(r"(?m)^\s*True peak:\s*(-?\d+(?:\.\d+)?)\s+dBTP\s*$", text)
    if true_peak is None:
        true_peak = re.search(r"True peak:\s*\n\s*Peak:\s*(-?\d+(?:\.\d+)?)\s+dBFS", text)
    if integrated is None or true_peak is None:
        raise CollectionError("FFmpeg ebur128=peak=true did not report both integrated LUFS and true peak")
    return {
        "measurement": "FFmpeg ebur128=peak=true on the final MP4 audio stream",
        "integrated_lufs": float(integrated.group(1)),
        "true_peak_dbTP": float(true_peak.group(1)),
        "acceptance_judgment": "NOT_RECORDED",
    }


def write_metadata(output_dir: Path, *, manifest: dict[str, Any], media: Path, media_hash: str,
                   probe: dict[str, Any], sheets: dict[str, Any], audio: dict[str, Any], loudness: dict[str, Any]) -> dict[str, Any]:
    all_timestamps = [
        {"frame": frame, "seconds": frame / FPS, "timecode": timecode(frame)}
        for frame in ALL_FRAME_INDEXES
    ]
    report = {
        "schema_version": 1,
        "collector": "EP13 encoded-media evidence collector",
        "evidence_only": True,
        "delivery_path": media.relative_to(DELIVERY_DIR).as_posix(),
        "media_sha256": media_hash,
        "native_dimensions": {"width": EXPECTED_WIDTH, "height": EXPECTED_HEIGHT},
        "video_timing": {"fps": FPS, "frames": TOTAL_FRAMES, "duration_seconds": TOTAL_FRAMES / FPS},
        "ffprobe": {
            "format_name": probe.get("format_name"),
            "container_duration_seconds": probe.get("container_duration_seconds"),
            "video": {key: probe["video"].get(key) for key in (
                "codec_name", "width", "height", "avg_frame_rate", "r_frame_rate", "nb_frames", "duration", "pix_fmt",
                "color_space", "color_primaries", "color_transfer",
            )},
            "audio": {key: probe["audio"].get(key) for key in ("codec_name", "sample_rate", "channels")},
        },
        "extraction": {
            "source": "final encoded MP4 only; no source-render PNGs or source project frames",
            "method": "FFmpeg decoded-frame select by absolute frame index, PNG output at native dimensions",
            "representative_frame_indexes": list(SAMPLE_FRAMES),
            "motion_pair_frame_indexes": [list(pair) for pair in PAIR_FRAMES],
            "all_extracted_frame_indexes": list(ALL_FRAME_INDEXES),
            "all_extracted_timestamps": all_timestamps,
            "native_frame_directory": "native-frames/",
            "covers": {
                "sampled_frames": {"A": 1680, "B": 4020},
                "platform_cover_files_written": False,
                "reason": "Cover image paths are owned by the render workflow; this collector preserves them.",
            },
            "contact_sheets": sheets,
        },
        "audio_measurements": {
            "encoded_loudness": loudness,
            "pcm_correlation_and_silence": audio,
            "scratch_policy": "Decoded audio is written only under the process TMPDIR and removed when collection exits.",
        },
        "scope": {
            "full_frame_visual_review_performed": False,
            "full_frame_decoder_scan_performed": False,
            "continuous_motion_compliance_verified": False,
            "human_listening_performed": False,
            "model_visual_observation_performed": False,
            "review_or_delivery_verdict": "NOT_RECORDED",
            "limitations": [
                "Native stills and sparse frame pairs are representative evidence; they do not establish full-frame quality or continuous motion compliance.",
                "Audio measurements and correlation are technical evidence; they do not establish intelligibility, emotion, or listening acceptance.",
                "The collector does not update delivery.json or any QA verdict file.",
            ],
        },
    }
    path = output_dir / "metadata.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return report


def incomplete_or_error(status: str, message: str, *, exit_code: int) -> int:
    print(json.dumps({"status": status, "message": message, "evidence_written": False}, ensure_ascii=False, indent=2))
    return exit_code


def main() -> int:
    try:
        manifest, media, master = load_manifest()
    except CollectionError as exc:
        return incomplete_or_error("FAIL", str(exc), exit_code=1)
    if not media.is_file():
        return incomplete_or_error("INCOMPLETE", f"final MP4 is not present: {media.relative_to(DELIVERY_DIR).as_posix()}", exit_code=2)
    if not master or not master.is_file():
        master = None

    try:
        ffmpeg = require_tool("ffmpeg")
        ffprobe = require_tool("ffprobe")
        Image, ImageDraw, ImageFont = load_image_modules()
        import numpy  # noqa: F401 - availability is needed for audio measurements below
    except MissingTool as exc:
        return incomplete_or_error("BLOCKED", str(exc), exit_code=1)
    except ImportError:
        return incomplete_or_error("BLOCKED", "NumPy is unavailable in this Python runtime", exit_code=1)

    try:
        initial_hash = sha256_file(media)
        probe = probe_media(ffprobe, media)
        REVIEW_DIR.mkdir(parents=True, exist_ok=True)
        output_dir = REVIEW_DIR / f"encoded-qa-{initial_hash[:12]}"
        if output_dir.exists():
            return incomplete_or_error("BLOCKED", f"refusing to overwrite existing evidence directory: {output_dir.relative_to(DELIVERY_DIR).as_posix()}", exit_code=1)

        stage = Path(tempfile.mkdtemp(prefix=".encoded-qa-stage-", dir=REVIEW_DIR))
        try:
            frames_dir = stage / "native-frames"
            frame_paths = extract_frames(ffmpeg, media, ALL_FRAME_INDEXES, frames_dir)
            check_native_pngs(frame_paths, Image)
            sheets = make_contact_sheets(frame_paths, stage, Image, ImageDraw, ImageFont)
            with tempfile.TemporaryDirectory(prefix="si-ep13-encoded-audio-") as scratch_name:
                scratch = Path(scratch_name)
                audio = audio_correlation_and_silence(ffmpeg, media, master, scratch)
            loudness = measure_loudness(ffmpeg, media)
            final_hash = sha256_file(media)
            if initial_hash != final_hash:
                raise CollectionError("final MP4 SHA-256 changed during evidence collection")
            report = write_metadata(
                stage, manifest=manifest, media=media, media_hash=final_hash,
                probe=probe, sheets=sheets, audio=audio, loudness=loudness,
            )
            stage.rename(output_dir)
        except BaseException:
            shutil.rmtree(stage, ignore_errors=True)
            raise
    except MissingTool as exc:
        return incomplete_or_error("BLOCKED", str(exc), exit_code=1)
    except (CollectionError, OSError) as exc:
        return incomplete_or_error("FAIL", str(exc), exit_code=1)

    print(json.dumps({
        "status": "EVIDENCE_COLLECTED",
        "metadata_path": (output_dir / "metadata.json").relative_to(DELIVERY_DIR).as_posix(),
        "media_sha256": report["media_sha256"],
        "native_dimensions": report["native_dimensions"],
        "extracted_frame_count": len(ALL_FRAME_INDEXES),
        "review_verdict": "NOT_RECORDED",
        "output_directory": output_dir.relative_to(DELIVERY_DIR).as_posix(),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
