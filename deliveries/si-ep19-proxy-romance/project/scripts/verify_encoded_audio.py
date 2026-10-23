#!/usr/bin/env python3
"""Verify the encoded EP19 delivery against its exact PCM master and stems.

This is an automated encoded-audio check only.  It does not replace listening
to the finished film or target-device playback.
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
import wave
from pathlib import Path
from typing import Any

import numpy as np


PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT.parent
DELIVERY_PATH = WORK / "delivery.json"
QA_PATH = WORK / "review" / "encoded-audio-qa.json"
EXPECTED_RATE = 48_000
EXPECTED_CHANNELS = 2
EXPECTED_FRAMES = 5_400
EXPECTED_VIDEO_SECONDS = 90.0
SAMPLES_PER_CHANNEL = EXPECTED_RATE * EXPECTED_FRAMES // 60
SILENCE_START = 3_888_000
SILENCE_END = 3_912_000
INTERIOR_START = round(81.05 * EXPECTED_RATE)
INTERIOR_END = round(81.45 * EXPECTED_RATE)
MAX_LAG = 2_048
CORRELATION_WINDOWS = ((2.0, 5.0), (40.0, 43.0), (82.0, 85.0))


class VerificationError(RuntimeError):
    """A required input or media measurement could not be verified."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while True:
            block = source.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise VerificationError(f"Required media tool is missing from PATH: {name}")
    return path


def run_process(command: list[str], *, binary_output: bool = False) -> tuple[bytes | str, str]:
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    result = subprocess.run(command, capture_output=True, check=False, env=env)
    stderr = result.stderr.decode("utf-8", errors="replace")
    if result.returncode != 0:
        raise VerificationError(f"Command failed ({result.returncode}): {' '.join(command[:5])}: {stderr[-1800:]}")
    if binary_output:
        return result.stdout, stderr
    return result.stdout.decode("utf-8", errors="replace"), stderr


def parse_rate(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value)
    if "/" in text:
        numerator, denominator = text.split("/", 1)
        try:
            denominator_value = float(denominator)
            if denominator_value == 0:
                return None
            return float(numerator) / denominator_value
        except ValueError:
            return None
    try:
        return float(text)
    except ValueError:
        return None


def read_delivery() -> tuple[dict[str, Any], Path, Path, str]:
    if not DELIVERY_PATH.is_file():
        raise VerificationError(f"Missing delivery manifest: {DELIVERY_PATH}")
    try:
        delivery_bytes = DELIVERY_PATH.read_bytes()
        delivery = json.loads(delivery_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"Cannot read delivery manifest {DELIVERY_PATH}: {exc}") from exc
    try:
        video_ref = delivery["outputs"]["xiaohongshu"]["path"]
        master_ref = delivery["audio"]["master"]
    except (KeyError, TypeError) as exc:
        raise VerificationError("delivery.json must specify outputs.xiaohongshu.path and audio.master.") from exc
    if not isinstance(video_ref, str) or not video_ref.strip() or not isinstance(master_ref, str) or not master_ref.strip():
        raise VerificationError("delivery.json video and master paths must be non-empty strings.")
    video_path = Path(video_ref)
    master_path = Path(master_ref)
    if not video_path.is_absolute():
        video_path = WORK / video_path
    if not master_path.is_absolute():
        master_path = WORK / master_path
    return delivery, video_path.resolve(), master_path.resolve(), hashlib.sha256(delivery_bytes).hexdigest()


def duration_seconds(stream: dict[str, Any], frame_count: int | None, fps: float | None) -> tuple[float | None, str]:
    raw = stream.get("duration")
    try:
        if raw not in (None, "N/A"):
            return float(raw), "stream.duration"
    except (TypeError, ValueError):
        pass
    try:
        duration_ts = float(stream["duration_ts"])
        time_base = parse_rate(stream.get("time_base"))
        if time_base and math.isfinite(duration_ts * time_base):
            return duration_ts * time_base, "stream.duration_ts*time_base"
    except (KeyError, TypeError, ValueError):
        pass
    if frame_count is not None and fps and fps > 0:
        return frame_count / fps, "frame_count/fps"
    return None, "unavailable"


def probe_video(path: Path) -> tuple[dict[str, Any], list[str]]:
    ffprobe = require_tool("ffprobe")
    output, _ = run_process([
        ffprobe, "-v", "error", "-count_frames", "-show_streams", "-show_format",
        "-of", "json", str(path),
    ])
    try:
        metadata = json.loads(str(output))
    except json.JSONDecodeError as exc:
        raise VerificationError(f"ffprobe returned invalid JSON for {path}: {exc}") from exc
    streams = metadata.get("streams", [])
    videos = [stream for stream in streams if stream.get("codec_type") == "video"]
    audios = [stream for stream in streams if stream.get("codec_type") == "audio"]
    if not videos or not audios:
        raise VerificationError("ffprobe did not find both video and audio streams.")
    video = videos[0]
    audio = audios[0]
    fps = parse_rate(video.get("avg_frame_rate"))
    nominal_fps = parse_rate(video.get("r_frame_rate"))
    count_raw = video.get("nb_read_frames")
    if count_raw in (None, "N/A"):
        count_raw = video.get("nb_frames")
    try:
        frame_count = int(count_raw) if count_raw not in (None, "N/A") else None
    except (TypeError, ValueError):
        frame_count = None
    video_duration, duration_source = duration_seconds(video, frame_count, fps or nominal_fps)
    report = {
        "video": {
            "codec": video.get("codec_name"),
            "width": video.get("width"),
            "height": video.get("height"),
            "avgFrameRate": video.get("avg_frame_rate"),
            "nominalFrameRate": video.get("r_frame_rate"),
            "frameCount": frame_count,
            "durationSeconds": video_duration,
            "durationSource": duration_source,
        },
        "audio": {
            "codec": audio.get("codec_name"),
            "sampleRate": audio.get("sample_rate"),
            "channels": audio.get("channels"),
            "channelLayout": audio.get("channel_layout"),
            "streamDurationSeconds": parse_rate(audio.get("duration")),
        },
        "containerDurationSeconds": parse_rate(metadata.get("format", {}).get("duration")),
        "videoStreamCount": len(videos),
        "audioStreamCount": len(audios),
    }
    errors: list[str] = []
    if len(videos) != 1:
        errors.append(f"Expected one video stream, found {len(videos)}.")
    if len(audios) != 1:
        errors.append(f"Expected one audio stream, found {len(audios)}.")
    if int(video.get("width") or 0) != 2_160 or int(video.get("height") or 0) != 3_840:
        errors.append(f"Video dimensions must be 2160x3840; found {video.get('width')}x{video.get('height')}.")
    if frame_count != EXPECTED_FRAMES:
        errors.append(f"Video must contain {EXPECTED_FRAMES} frames; ffprobe counted {frame_count}.")
    if fps is None or abs(fps - 60.0) > 1e-6 or nominal_fps is None or abs(nominal_fps - 60.0) > 1e-6:
        errors.append(f"Video frame rates must both be 60 fps; found avg={fps}, nominal={nominal_fps}.")
    if video_duration is None or abs(video_duration - EXPECTED_VIDEO_SECONDS) > 0.001:
        errors.append(f"Video stream duration must be 90.000s; found {video_duration}.")
    if audio.get("codec_name") != "aac":
        errors.append(f"Encoded audio codec must be AAC; found {audio.get('codec_name')}.")
    if str(audio.get("sample_rate")) != str(EXPECTED_RATE):
        errors.append(f"Encoded audio sample rate must be {EXPECTED_RATE} Hz; found {audio.get('sample_rate')}.")
    if int(audio.get("channels") or 0) != EXPECTED_CHANNELS:
        errors.append(f"Encoded audio must be stereo; found {audio.get('channels')} channels.")
    return report, errors


def read_pcm_wav(path: Path) -> tuple[np.ndarray, dict[str, Any]]:
    if not path.is_file():
        raise VerificationError(f"Missing PCM reference file: {path}")
    try:
        with wave.open(str(path), "rb") as source:
            channels = source.getnchannels()
            sample_width = source.getsampwidth()
            sample_rate = source.getframerate()
            frame_count = source.getnframes()
            compression = source.getcomptype()
            raw = source.readframes(frame_count)
    except (OSError, wave.Error) as exc:
        raise VerificationError(f"Cannot read PCM WAV {path}: {exc}") from exc
    if channels != EXPECTED_CHANNELS or sample_width != 2 or sample_rate != EXPECTED_RATE or compression != "NONE":
        raise VerificationError(
            f"{path.name} must be uncompressed PCM16 stereo at {EXPECTED_RATE} Hz; "
            f"found channels={channels}, width={sample_width}, rate={sample_rate}, compression={compression}."
        )
    expected_bytes = frame_count * EXPECTED_CHANNELS * 2
    if len(raw) != expected_bytes:
        raise VerificationError(f"{path.name} WAV data has {len(raw)} bytes; expected {expected_bytes}.")
    pcm = np.frombuffer(raw, dtype="<i2").reshape(frame_count, EXPECTED_CHANNELS).copy()
    return pcm, {
        "path": str(path),
        "sampleRate": sample_rate,
        "channels": channels,
        "sampleCountPerChannel": frame_count,
        "bytesOfPcmData": len(raw),
        "sha256": sha256_file(path),
    }


def window_metrics(pcm: np.ndarray, start: int, end: int) -> dict[str, Any]:
    total = int(len(pcm))
    bounded_start = max(0, min(total, start))
    bounded_end = max(bounded_start, min(total, end))
    piece = pcm[bounded_start:bounded_end]
    if piece.size == 0:
        return {
            "sampleStart": start,
            "sampleEndExclusive": end,
            "sampleFrames": 0,
            "scalarSamples": 0,
            "nonZeroScalarSamples": 0,
            "nonZeroFrames": 0,
            "maxAbsSample": None,
            "rmsLinear": None,
            "rmsDbfs": None,
            "digitalZero": None,
            "rangeComplete": False,
        }
    values = piece.astype(np.float64) / 32768.0
    rms = float(np.sqrt(np.mean(values * values)))
    max_abs = int(np.max(np.abs(piece.astype(np.int32))))
    return {
        "sampleStart": start,
        "sampleEndExclusive": end,
        "sampleFrames": int(len(piece)),
        "scalarSamples": int(piece.size),
        "nonZeroScalarSamples": int(np.count_nonzero(piece)),
        "nonZeroFrames": int(np.count_nonzero(np.any(piece != 0, axis=1))),
        "maxAbsSample": max_abs,
        "rmsLinear": rms,
        "rmsDbfs": 20.0 * math.log10(rms) if rms > 0 else None,
        "digitalZero": max_abs == 0,
        "rangeComplete": bounded_start == start and bounded_end == end,
    }


def check_pcm_reference(path: Path, expected_samples: int, label: str, errors: list[str]) -> tuple[np.ndarray | None, dict[str, Any]]:
    try:
        pcm, info = read_pcm_wav(path)
    except VerificationError as exc:
        errors.append(str(exc))
        return None, {"path": str(path), "error": str(exc)}
    exact_sample_count = info["sampleCountPerChannel"] == expected_samples
    if not exact_sample_count:
        errors.append(f"{label} must contain {expected_samples} samples/channel; found {info['sampleCountPerChannel']}.")
    silence = window_metrics(pcm, SILENCE_START, SILENCE_END)
    if not silence["rangeComplete"] or not silence["digitalZero"]:
        errors.append(f"{label} is not exact digital zero across samples [{SILENCE_START},{SILENCE_END}).")
    info["expectedSamplesPerChannel"] = expected_samples
    info["exactSampleCount"] = exact_sample_count
    info["absoluteSilence"] = silence
    info["passes"] = exact_sample_count and silence["rangeComplete"] and silence["digitalZero"]
    return pcm, info


def decode_encoded_audio(path: Path) -> tuple[np.ndarray, dict[str, Any]]:
    ffmpeg = require_tool("ffmpeg")
    stdout, stderr = run_process([
        ffmpeg, "-hide_banner", "-v", "error", "-nostdin", "-i", str(path),
        "-map", "0:a:0", "-vn", "-ac", str(EXPECTED_CHANNELS), "-ar", str(EXPECTED_RATE),
        "-acodec", "pcm_s16le", "-f", "s16le", "pipe:1",
    ], binary_output=True)
    raw = bytes(stdout)
    bytes_per_frame = EXPECTED_CHANNELS * 2
    if len(raw) == 0 or len(raw) % bytes_per_frame:
        raise VerificationError(f"ffmpeg decoded malformed PCM: {len(raw)} bytes for stereo PCM16.")
    count = len(raw) // bytes_per_frame
    pcm = np.frombuffer(raw, dtype="<i2").reshape(count, EXPECTED_CHANNELS).copy()
    return pcm, {
        "decodedFormat": "PCM16",
        "sampleRate": EXPECTED_RATE,
        "channels": EXPECTED_CHANNELS,
        "actualSampleCountPerChannel": count,
        "expectedSampleCountPerChannel": SAMPLES_PER_CHANNEL,
        "sampleCountDelta": count - SAMPLES_PER_CHANNEL,
        "durationSeconds": count / EXPECTED_RATE,
        "ffmpegDecodeLog": stderr[-1200:],
    }


def measure_encoded_loudness(path: Path) -> tuple[dict[str, float], str]:
    ffmpeg = require_tool("ffmpeg")
    _, stderr = run_process([
        ffmpeg, "-hide_banner", "-nostats", "-v", "info", "-nostdin", "-i", str(path),
        "-map", "0:a:0", "-vn", "-af", "ebur128=peak=true", "-f", "null", "-",
    ])
    integrated_matches = re.findall(r"\bI:\s*(-?(?:inf|nan|\d+(?:\.\d+)?))\s*LUFS", stderr, flags=re.IGNORECASE)
    lra_matches = re.findall(r"\bLRA:\s*(-?(?:inf|nan|\d+(?:\.\d+)?))\s*LU", stderr, flags=re.IGNORECASE)
    true_peak_section = stderr.rsplit("True peak:", 1)[-1]
    peak_matches = re.findall(r"\bPeak:\s*(-?(?:inf|nan|\d+(?:\.\d+)?))\s*dBFS", true_peak_section, flags=re.IGNORECASE)
    if not integrated_matches or not peak_matches:
        raise VerificationError(f"ffmpeg ebur128=peak=true did not report integrated LUFS and true peak: {stderr[-1800:]}")
    integrated = float(integrated_matches[-1])
    true_peak = float(peak_matches[-1])
    lra = float(lra_matches[-1]) if lra_matches else math.nan
    if not math.isfinite(integrated) or not math.isfinite(true_peak):
        raise VerificationError(f"Unusable encoded loudness results: I={integrated}, true peak={true_peak}.")
    return {"integratedLufs": integrated, "loudnessRangeLu": lra, "truePeakDbtp": true_peak}, stderr[-2200:]


def correlations_for_window(reference: np.ndarray, encoded: np.ndarray, start: int, end: int, max_lag: int) -> tuple[np.ndarray, np.ndarray]:
    if start < max_lag or end + max_lag > len(encoded) or end > len(reference):
        raise VerificationError(f"Cannot compare [{start},{end}) with ±{max_lag} sample lag; decoded audio is too short.")
    ref = reference[start:end].astype(np.float64)
    encoded_base = encoded[start - max_lag : end + max_lag].astype(np.float64)
    length = len(ref)
    lags = np.arange(-max_lag, max_lag + 1, dtype=np.int64)
    convolution_length = len(encoded_base) + length - 1
    fft_length = 1 << (convolution_length - 1).bit_length()
    spectrum = np.fft.rfft(encoded_base, fft_length) * np.fft.rfft(ref[::-1], fft_length)
    convolution = np.fft.irfft(spectrum, fft_length)[:convolution_length]
    products = convolution[length - 1 + max_lag + lags]
    offsets = max_lag + lags
    cumulative_energy = np.concatenate(([0.0], np.cumsum(encoded_base * encoded_base)))
    encoded_energy = cumulative_energy[offsets + length] - cumulative_energy[offsets]
    reference_energy = float(np.dot(ref, ref))
    denominator = np.sqrt(np.maximum(0.0, reference_energy * encoded_energy))
    correlations = np.zeros_like(products)
    valid = denominator > 0.0
    correlations[valid] = products[valid] / denominator[valid]
    return lags, np.clip(correlations, -1.0, 1.0)


def alignment_report(master: np.ndarray, encoded: np.ndarray) -> dict[str, Any]:
    master_mono = master.astype(np.float32).mean(axis=1) / 32768.0
    encoded_mono = encoded.astype(np.float32).mean(axis=1) / 32768.0
    windows = []
    all_correlations = []
    common_lags: np.ndarray | None = None
    for start_seconds, end_seconds in CORRELATION_WINDOWS:
        start = round(start_seconds * EXPECTED_RATE)
        end = round(end_seconds * EXPECTED_RATE)
        lags, correlations = correlations_for_window(master_mono, encoded_mono, start, end, MAX_LAG)
        common_lags = lags
        all_correlations.append(correlations)
        windows.append({
            "startSeconds": start_seconds,
            "endSeconds": end_seconds,
            "sampleStart": start,
            "sampleEndExclusive": end,
            "lags": lags,
            "correlations": correlations,
        })
    if common_lags is None:
        raise VerificationError("No correlation windows were configured.")
    global_scores = np.mean(np.stack(all_correlations, axis=0), axis=0)
    global_index = int(np.argmax(global_scores))
    global_lag = int(common_lags[global_index])
    output_windows = []
    for window in windows:
        start = int(window["sampleStart"])
        end = int(window["sampleEndExclusive"])
        reference_piece = master_mono[start:end].astype(np.float64)
        encoded_piece = encoded_mono[start + global_lag : end + global_lag].astype(np.float64)
        if len(encoded_piece) != len(reference_piece):
            raise VerificationError("Global lag alignment left an incomplete comparison window.")
        reference_rms = float(np.sqrt(np.mean(reference_piece * reference_piece)))
        encoded_rms = float(np.sqrt(np.mean(encoded_piece * encoded_piece)))
        corr_values = window["correlations"]
        local_index = int(np.argmax(corr_values))
        local_best_lag = int(common_lags[local_index])
        global_corr = float(corr_values[global_index])
        scale = encoded_rms / reference_rms if reference_rms > 0.0 else math.nan
        output_windows.append({
            "startSeconds": window["startSeconds"],
            "endSeconds": window["endSeconds"],
            "sampleStart": start,
            "sampleEndExclusive": end,
            "globalLagSamples": global_lag,
            "correlationAtGlobalLag": global_corr,
            "localBestLagSamples": local_best_lag,
            "localBestCorrelation": float(corr_values[local_index]),
            "masterRmsLinear": reference_rms,
            "encodedRmsLinear": encoded_rms,
            "rmsScaleLinear": scale,
            "rmsScaleDb": 20.0 * math.log10(scale) if scale > 0.0 else None,
        })
    return {
        "method": "mono_downmix_normalized_cross_correlation",
        "lagConvention": "positive means decoded AAC sample index is shifted later than the master index",
        "maxSearchLagSamples": MAX_LAG,
        "globalBestLagSamples": global_lag,
        "globalBestLagSeconds": global_lag / EXPECTED_RATE,
        "globalMeanCorrelation": float(global_scores[global_index]),
        "windows": output_windows,
    }


def encoded_window_metrics(pcm: np.ndarray) -> dict[str, Any]:
    return {
        "timelineSilence81to81_5Seconds": window_metrics(pcm, SILENCE_START, SILENCE_END),
        "interior81_05to81_45Seconds": window_metrics(pcm, INTERIOR_START, INTERIOR_END),
    }


def aligned_encoded_window_metrics(pcm: np.ndarray, global_lag: int) -> dict[str, Any]:
    return {
        "masterSilenceAlignedToDecodedSamples": window_metrics(pcm, SILENCE_START + global_lag, SILENCE_END + global_lag),
        "masterInteriorAlignedToDecodedSamples": window_metrics(pcm, INTERIOR_START + global_lag, INTERIOR_END + global_lag),
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_report(report: dict[str, Any]) -> None:
    QA_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = QA_PATH.with_name(f".{QA_PATH.name}.tmp")
    temporary.write_text(json.dumps(_json_safe(report), ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(QA_PATH)


def verify() -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    report: dict[str, Any] = {
        "status": "FAIL",
        "scope": {
            "verification": "automated_encoded_audio_only",
            "humanListeningPerformed": False,
            "humanAcceptance": "NOT_ASSESSED",
            "targetDevicePlaybackPerformed": False,
        },
        "deliveryManifest": {"path": str(DELIVERY_PATH)},
        "checks": {},
        "errors": errors,
    }

    delivery: dict[str, Any] | None = None
    video_path: Path | None = None
    master_path: Path | None = None
    try:
        delivery, video_path, master_path, delivery_hash = read_delivery()
        report["deliveryManifest"].update({
            "sha256": delivery_hash,
            "slug": delivery.get("slug"),
            "title": delivery.get("title"),
            "videoPath": str(video_path),
            "masterPath": str(master_path),
        })
    except VerificationError as exc:
        errors.append(str(exc))

    reference_pcm: np.ndarray | None = None
    reference_info: dict[str, Any] = {}
    if master_path is not None:
        reference_pcm, reference_info = check_pcm_reference(master_path, SAMPLES_PER_CHANNEL, "Master PCM", errors)
    else:
        errors.append("Cannot inspect master PCM because delivery.json did not provide a valid master path.")
    report["masterPcm"] = reference_info

    stem_reports: dict[str, Any] = {}
    if master_path is not None:
        for stem_name in ("narration", "score", "sfx"):
            stem_path = master_path.parent / f"{stem_name}.wav"
            _, stem_info = check_pcm_reference(stem_path, SAMPLES_PER_CHANNEL, f"{stem_name} stem", errors)
            stem_reports[stem_name] = stem_info
    report["stems"] = stem_reports

    encoded_pcm: np.ndarray | None = None
    if video_path is None:
        errors.append("Cannot inspect final MP4 because delivery.json did not provide a valid video path.")
    elif not video_path.is_file():
        errors.append(f"Final MP4 from delivery.json does not exist: {video_path}")
    else:
        try:
            report["videoFile"] = {
                "path": str(video_path),
                "bytes": video_path.stat().st_size,
                "sha256": sha256_file(video_path),
            }
        except OSError as exc:
            errors.append(f"Cannot hash final MP4 {video_path}: {exc}")
        try:
            probe_report, probe_errors = probe_video(video_path)
            report["ffprobe"] = probe_report
            report["checks"]["videoAndAudioStreamSpecs"] = not probe_errors
            errors.extend(probe_errors)
        except VerificationError as exc:
            errors.append(str(exc))
        try:
            encoded_pcm, decode_report = decode_encoded_audio(video_path)
            report["decodedAac"] = decode_report
            if len(encoded_pcm) < SILENCE_END:
                errors.append(f"Decoded AAC has {len(encoded_pcm)} samples/channel, too short to inspect the requested silence window.")
            report["encodedSilenceMetrics"] = encoded_window_metrics(encoded_pcm)
            if not report["encodedSilenceMetrics"]["timelineSilence81to81_5Seconds"]["rangeComplete"]:
                errors.append("Decoded AAC does not contain the complete [81.0s,81.5s) inspection window.")
            if not report["encodedSilenceMetrics"]["interior81_05to81_45Seconds"]["rangeComplete"]:
                errors.append("Decoded AAC does not contain the complete [81.05s,81.45s) interior inspection window.")
        except VerificationError as exc:
            errors.append(str(exc))
        try:
            loudness, ebur_report = measure_encoded_loudness(video_path)
            report["encodedLoudness"] = {**loudness, "ebur128Report": ebur_report}
            if abs(loudness["integratedLufs"] - (-16.0)) > 0.3:
                errors.append(f"Encoded integrated loudness must be -16.0±0.3 LUFS; measured {loudness['integratedLufs']:.2f} LUFS.")
            if loudness["truePeakDbtp"] > -1.0:
                errors.append(f"Encoded true peak must be ≤ -1.0 dBTP; measured {loudness['truePeakDbtp']:.2f} dBTP.")
        except VerificationError as exc:
            errors.append(str(exc))

    if reference_pcm is not None and encoded_pcm is not None:
        try:
            alignment = alignment_report(reference_pcm, encoded_pcm)
            report["masterComparison"] = alignment
            report["encodedSilenceMetricsAlignedToMaster"] = aligned_encoded_window_metrics(
                encoded_pcm, alignment["globalBestLagSamples"]
            )
            for window in alignment["windows"]:
                if window["correlationAtGlobalLag"] < 0.95:
                    errors.append(
                        f"Encoded/master correlation at {window['startSeconds']:.0f}-{window['endSeconds']:.0f}s "
                        f"is {window['correlationAtGlobalLag']:.4f}, below 0.95."
                    )
            report["checks"]["masterCorrelation"] = all(
                window["correlationAtGlobalLag"] >= 0.95 for window in alignment["windows"]
            )
        except VerificationError as exc:
            errors.append(str(exc))

    if "masterPcm" in report:
        report["checks"]["masterPcmLengthAndSilence"] = bool(report["masterPcm"].get("passes", False))
    if stem_reports:
        report["checks"]["stemLengthsAndSilence"] = all(info.get("passes", False) for info in stem_reports.values())
    if "encodedLoudness" in report:
        loudness = report["encodedLoudness"]
        report["checks"]["encodedLoudness"] = (
            abs(loudness["integratedLufs"] - (-16.0)) <= 0.3 and loudness["truePeakDbtp"] <= -1.0
        )
    report["status"] = "PASS" if not errors else "FAIL"
    return report, errors


def main() -> int:
    try:
        report, errors = verify()
    except Exception as exc:  # preserve a machine-readable failure report for unexpected verifier errors
        errors = [f"Verifier failed unexpectedly: {type(exc).__name__}: {exc}"]
        report = {
            "status": "FAIL",
            "scope": {"verification": "automated_encoded_audio_only", "humanListeningPerformed": False, "humanAcceptance": "NOT_ASSESSED"},
            "deliveryManifest": {"path": str(DELIVERY_PATH)},
            "checks": {},
            "errors": errors,
        }
    try:
        write_report(report)
    except OSError as exc:
        errors.append(f"Cannot write verification report {QA_PATH}: {exc}")
        report["status"] = "FAIL"
    if errors:
        print(f"FAIL encoded-audio QA: {len(errors)} issue(s)")
        for error in errors:
            print(f"- {error}")
        print(f"Report: {QA_PATH}")
        return 2
    loudness = report.get("encodedLoudness", {})
    alignment = report.get("masterComparison", {})
    print(
        "PASS encoded-audio QA: "
        f"samples={report.get('decodedAac', {}).get('actualSampleCountPerChannel')} "
        f"I={loudness.get('integratedLufs', float('nan')):.2f} LUFS "
        f"TP={loudness.get('truePeakDbtp', float('nan')):.2f} dBTP "
        f"lag={alignment.get('globalBestLagSamples')} samples "
        f"corr={alignment.get('globalMeanCorrelation', float('nan')):.4f}"
    )
    print(f"Report: {QA_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
