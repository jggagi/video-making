#!/usr/bin/env python3
"""Measure EP18 v04 final MP4 AAC timing against its current PCM master.

Lag convention: positive lag means the encoded AAC waveform is delayed relative
to the PCM master by that many samples. The report does not claim AAC silence
is bit-exact; only the source PCM silence window is checked for exact zeros.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


PROJECT_DIR = Path(__file__).resolve().parents[1]
DELIVERY_DIR = PROJECT_DIR.parent
REPORT_PATH = DELIVERY_DIR / "review" / "encoded-audio-sync.json"
WORK_ID = "si-ep18-sovereign-subcurrent-v04"
RENDER_PLAN = json.loads((PROJECT_DIR / "render-plan.json").read_text(encoding="utf-8"))
WORK_TITLE = RENDER_PLAN["work"]["title"]
SAMPLE_RATE = RENDER_PLAN["capture"]["audioSampleRateHz"]
FPS = RENDER_PLAN["composition"]["fps"]
SAMPLES_PER_FRAME = SAMPLE_RATE // FPS
TOTAL_FRAMES = RENDER_PLAN["composition"]["durationInFrames"]
TOTAL_SAMPLES = TOTAL_FRAMES * SAMPLES_PER_FRAME
SILENCE_START_FRAME, SILENCE_END_FRAME = RENDER_PLAN["frames"]["anchors"]["silenceRangeHalfOpen"]
SILENCE_START_SAMPLE = SILENCE_START_FRAME * SAMPLES_PER_FRAME
SILENCE_END_SAMPLE = SILENCE_END_FRAME * SAMPLES_PER_FRAME
WINDOW_SAMPLES = 2 * SAMPLE_RATE
MAX_LAG_SAMPLES = 2_400
MAX_ALLOWED_LAG_SAMPLES = SAMPLES_PER_FRAME
MIN_WINDOW_RMS = 1e-5
MIN_CENTERED_ENERGY = 1e-12
CORRELATION_THRESHOLD = 0.95
EXPECTED_CUE_COUNT = RENDER_PLAN["content"]["segmentCount"]


class ValidationError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stat_signature(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"Could not read valid JSON from {path.name}: {exc}") from exc


def resolve_delivery_file(relative: Any, label: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise ValidationError(f"Manifest has no valid {label} path")
    root = DELIVERY_DIR.resolve(strict=True)
    try:
        path = (DELIVERY_DIR / relative).resolve(strict=True)
    except OSError as exc:
        raise ValidationError(f"Manifest {label} file is unavailable: {relative}") from exc
    if not path.is_relative_to(root) or not path.is_file():
        raise ValidationError(f"Manifest {label} path is not a file inside this delivery")
    return path


def _fft_correlations(reference: np.ndarray, encoded_window: np.ndarray, max_lag: int) -> np.ndarray:
    """Return normalized correlation for shifts -max_lag..+max_lag via FFT.

    ``encoded_window`` contains ``max_lag`` samples of context on each side of
    the comparison window. Positive shift compares the reference to later
    encoded samples, so it means that AAC lags behind the master.
    """
    count = reference.size
    if count <= 2 * max_lag or encoded_window.size != count + 2 * max_lag:
        raise ValidationError("Correlation window is too short or lacks lag context")
    fft_size = 1 << (count + encoded_window.size - 2).bit_length()
    convolution = np.fft.irfft(
        np.fft.rfft(encoded_window, fft_size) * np.fft.rfft(reference[::-1], fft_size),
        fft_size,
    )[: reference.size + encoded_window.size - 1]
    shifts = np.arange(-max_lag, max_lag + 1, dtype=np.int64)
    # For an encoded window starting at -max_lag, the subwindow offset is lag+max_lag.
    subwindow_offsets = shifts + max_lag
    dot = convolution[count - 1 + subwindow_offsets]

    ref_sum = float(np.sum(reference, dtype=np.float64))
    ref_sq = float(np.sum(reference * reference, dtype=np.float64))
    enc_prefix = np.concatenate(([0.0], np.cumsum(encoded_window, dtype=np.float64)))
    enc_sq_prefix = np.concatenate(([0.0], np.cumsum(encoded_window * encoded_window, dtype=np.float64)))
    overlap = np.full(shifts.shape, count, dtype=np.int64)
    enc_start = subwindow_offsets
    enc_sum = enc_prefix[enc_start + overlap] - enc_prefix[enc_start]
    enc_sq = enc_sq_prefix[enc_start + overlap] - enc_sq_prefix[enc_start]
    covariance = dot - (ref_sum * enc_sum / overlap)
    ref_energy = ref_sq - (ref_sum * ref_sum / overlap)
    enc_energy = enc_sq - (enc_sum * enc_sum / overlap)
    denominator = np.sqrt(np.maximum(0.0, ref_energy) * np.maximum(0.0, enc_energy))
    correlations = np.full(shifts.shape, np.nan, dtype=np.float64)
    usable = denominator > MIN_CENTERED_ENERGY
    correlations[usable] = covariance[usable] / denominator[usable]
    return np.clip(correlations, -1.0, 1.0)


def analyze_window(
    master: np.ndarray,
    encoded: np.ndarray,
    frame: int,
    label: str,
    *,
    window_samples: int = WINDOW_SAMPLES,
    max_lag: int = MAX_LAG_SAMPLES,
) -> dict[str, Any]:
    center = frame * SAMPLES_PER_FRAME
    desired_start = center - window_samples // 2
    # Reserve lag context while keeping the first comparison anchored in the
    # opening narration instead of requesting nonexistent pre-roll samples.
    start = max(max_lag, desired_start)
    end = start + window_samples
    if start < 0 or end + max_lag > min(master.size, encoded.size):
        return {
            "id": label,
            "frame": frame,
            "status": "FAIL",
            "reason": "window_or_lag_context_out_of_bounds",
            "masterWindowRms": None,
            "encodedWindowRms": None,
            "bestLagSamples": None,
            "bestCorrelation": None,
        }
    reference = np.asarray(master[start:end], dtype=np.float64)
    encoded_context = np.asarray(encoded[start - max_lag:end + max_lag], dtype=np.float64)
    master_rms = float(np.sqrt(np.mean(reference * reference)))
    encoded_core = np.asarray(encoded[start:end], dtype=np.float64)
    encoded_rms = float(np.sqrt(np.mean(encoded_core * encoded_core)))
    result: dict[str, Any] = {
        "id": label,
        "frame": frame,
        "centerSample": center,
        "windowSamplesPerChannel": window_samples,
        "windowStartSample": start,
        "windowEndSampleExclusive": end,
        "windowCenterOffsetFromAnchorSamples": start + window_samples // 2 - center,
        "masterWindowRms": master_rms,
        "encodedWindowRms": encoded_rms,
        "maxLagSamples": max_lag,
        "maxLagMilliseconds": round(1000 * max_lag / SAMPLE_RATE, 3),
        "lagConvention": "positive means encoded AAC is delayed relative to PCM master",
        "requiredMaxAbsLagSamples": MAX_ALLOWED_LAG_SAMPLES,
        "requiredCorrelation": CORRELATION_THRESHOLD,
    }
    if master_rms < MIN_WINDOW_RMS:
        result.update({"status": "FAIL", "reason": "master_window_silent"})
        return result
    if encoded_rms < MIN_WINDOW_RMS:
        result.update({"status": "FAIL", "reason": "encoded_window_silent"})
        return result
    correlations = _fft_correlations(reference, encoded_context, max_lag)
    valid = np.isfinite(correlations)
    if not np.any(valid):
        result.update({"status": "FAIL", "reason": "unstable_or_zero_variance_window"})
        return result
    safe_correlations = np.where(valid, correlations, -np.inf)
    best_index = int(np.argmax(safe_correlations))
    best_lag = best_index - max_lag
    best_corr = float(correlations[best_index])
    lag_pass = abs(best_lag) <= MAX_ALLOWED_LAG_SAMPLES
    correlation_pass = best_corr >= CORRELATION_THRESHOLD
    result.update({
        "bestLagSamples": best_lag,
        "bestLagMilliseconds": round(1000 * best_lag / SAMPLE_RATE, 3),
        "bestCorrelation": best_corr,
        "lagPass": lag_pass,
        "correlationPass": correlation_pass,
        "status": "PASS" if lag_pass and correlation_pass else "FAIL",
    })
    if not lag_pass:
        result["reason"] = "best_lag_exceeds_one_frame"
    elif not correlation_pass:
        result["reason"] = "correlation_below_threshold"
    return result


def _master_pcm(path: Path) -> tuple[np.ndarray, dict[str, Any]]:
    before = stat_signature(path)
    digest = sha256_file(path)
    with wave.open(str(path), "rb") as stream:
        audio_format = {
            "sampleRateHz": stream.getframerate(),
            "channels": stream.getnchannels(),
            "sampleWidthBytes": stream.getsampwidth(),
            "compression": stream.getcomptype(),
            "sampleFramesPerChannel": stream.getnframes(),
        }
        raw = stream.readframes(stream.getnframes())
    after = stat_signature(path)
    stable = before == after
    channels = RENDER_PLAN["capture"]["audioChannels"]
    expected = (SAMPLE_RATE, channels, 2, "NONE", TOTAL_SAMPLES)
    actual = (
        audio_format["sampleRateHz"], audio_format["channels"], audio_format["sampleWidthBytes"],
        audio_format["compression"], audio_format["sampleFramesPerChannel"],
    )
    if actual != expected or len(raw) != TOTAL_SAMPLES * channels * 2:
        raise ValidationError(f"Accepted master must be stereo 48 kHz PCM16 with exactly {TOTAL_SAMPLES} samples per channel")
    interleaved = np.frombuffer(raw, dtype="<i2").reshape((-1, channels))
    silence = interleaved[SILENCE_START_SAMPLE:SILENCE_END_SAMPLE]
    exact_silence = bool(silence.size and np.count_nonzero(silence) == 0)
    mono = interleaved.astype(np.float32).mean(axis=1) / 32768.0
    return mono, {
        "sha256": digest,
        "bytes": path.stat().st_size,
        "format": audio_format,
        "stableDuringRead": stable,
        "silenceRangeSamplesPerChannel": [SILENCE_START_SAMPLE, SILENCE_END_SAMPLE],
        "silenceRangeExactZero": exact_silence,
        "silenceSamplesPerChannel": SILENCE_END_SAMPLE - SILENCE_START_SAMPLE,
    }


def _probe_movie(movie: Path) -> dict[str, Any]:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(movie)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        tail = proc.stderr[-800:].strip().replace("\n", " ")
        raise ValidationError(f"ffprobe failed (exit {proc.returncode}): {tail}")
    try:
        probe = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ValidationError("ffprobe did not return valid JSON") from exc
    audio_streams = [row for row in probe.get("streams", []) if row.get("codec_type") == "audio"]
    if len(audio_streams) != 1:
        raise ValidationError(f"Expected exactly one encoded audio stream, found {len(audio_streams)}")
    audio = audio_streams[0]
    allowlisted = (
        "codec_name", "sample_rate", "channels", "channel_layout", "start_time", "duration",
        "start_pts", "duration_ts", "time_base", "nb_frames", "bit_rate",
    )
    selected = {key: audio.get(key) for key in allowlisted}
    selected["formatDuration"] = (probe.get("format") or {}).get("duration")
    selected["formatStartTime"] = (probe.get("format") or {}).get("start_time")
    return selected


def _decode_movie_audio(movie: Path) -> tuple[np.ndarray, dict[str, Any]]:
    channels = RENDER_PLAN["capture"]["audioChannels"]
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-threads", "2", "-i", str(movie), "-map", "0:a:0", "-vn",
         "-ac", str(channels), "-ar", str(SAMPLE_RATE), "-c:a", "pcm_f32le", "-f", "f32le", "pipe:1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        tail = proc.stderr.decode("utf-8", errors="replace")[-800:].strip().replace("\n", " ")
        raise ValidationError(f"AAC decode failed (ffmpeg exit {proc.returncode}): {tail}")
    if len(proc.stdout) % (channels * 4):
        raise ValidationError("Decoded float PCM payload is not channel-aligned f32")
    decoded = np.frombuffer(proc.stdout, dtype="<f4").reshape((-1, channels))
    if decoded.size == 0 or not np.all(np.isfinite(decoded)):
        raise ValidationError("Decoded AAC produced no samples or non-finite PCM")
    mono = decoded.astype(np.float64).mean(axis=1)
    return mono, {
        "sampleRateHz": SAMPLE_RATE,
        "channelsDecoded": channels,
        "sampleFormat": "f32le",
        "decodedPayloadBytes": len(proc.stdout),
        "decodedSamplesPerChannel": int(decoded.shape[0]),
        "decodedDurationSeconds": decoded.shape[0] / SAMPLE_RATE,
        "monoRms": float(np.sqrt(np.mean(mono * mono))),
        "monoPeak": float(np.max(np.abs(mono))),
    }


def _atomic_report(report: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if REPORT_PATH.exists():
        raise ValidationError("Refusing to overwrite existing encoded-audio-sync.json")
    temp_path = REPORT_PATH.with_suffix(REPORT_PATH.suffix + ".tmp")
    temp_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(REPORT_PATH)


def validate_final() -> tuple[dict[str, Any], int]:
    delivery_path = DELIVERY_DIR / "delivery.json"
    delivery = read_json(delivery_path)
    if not isinstance(delivery, dict) or delivery.get("slug") != WORK_ID or delivery.get("title") != WORK_TITLE:
        raise ValidationError("delivery.json is not the expected EP18 v04 manifest")
    if delivery.get("platforms") != ["xiaohongshu"]:
        raise ValidationError("EP18 v04 audio validation is scoped to the Xiaohongshu output")
    if delivery.get("duration_seconds") != 90 or delivery.get("fps") != FPS or delivery.get("total_frames") != TOTAL_FRAMES:
        raise ValidationError("EP18 v04 manifest does not match the 90-second, 60-fps timeline")
    segment_rows = read_json(PROJECT_DIR / "segments.json")
    audio_plan = read_json(PROJECT_DIR / "audio-plan.json")
    synthesis_path = DELIVERY_DIR / "review" / "audio-synthesis.json"
    synthesis = read_json(synthesis_path)
    expected_ids = [f"S{i:02d}" for i in range(1, EXPECTED_CUE_COUNT + 1)]
    if not isinstance(segment_rows, list) or [row.get("id") for row in segment_rows if isinstance(row, dict)] != expected_ids:
        raise ValidationError("Current segments.json must contain the eight ordered EP18 v04 cues")
    synthesis_rows = synthesis.get("cues") if isinstance(synthesis, dict) else None
    cues = {row.get("id"): row for row in synthesis_rows if isinstance(row, dict)} if isinstance(synthesis_rows, list) else {}
    if set(cues) != set(expected_ids) or len(cues) != EXPECTED_CUE_COUNT:
        raise ValidationError("Fresh audio-synthesis.json must contain exactly the current eight cues")
    windows: list[tuple[str, int]] = []
    for segment in segment_rows:
        cue_id = segment["id"]
        cue = cues[cue_id]
        if cue.get("spokenText") != segment.get("tts_phonetic_text"):
            raise ValidationError(f"Synthesis text does not match the current v04 cue: {cue_id}")
        if cue.get("actualModel") != audio_plan.get("model") or cue.get("actualVoice") != audio_plan.get("voice"):
            raise ValidationError(f"Synthesis model or voice differs from the current audio plan: {cue_id}")
        if cue.get("rate") != audio_plan.get("rate") or audio_plan.get("rate") != 1.0:
            raise ValidationError(f"Synthesis rate differs from natural rate 1.0: {cue_id}")
        active_start = cue.get("activeStartFrame")
        active_end = cue.get("activeEndFrameExclusive")
        if not (isinstance(active_start, int) and isinstance(active_end, int)
                and segment["startFrame"] <= active_start < active_end <= segment["endFrame"]):
            raise ValidationError(f"Synthesis active PCM bounds do not fit the current cue: {cue_id}")
        if cue.get("sourceStartFrame") != segment["startFrame"] or cue.get("sourceEndFrame") != segment["endFrame"]:
            raise ValidationError(f"Synthesis window is stale for the current cue anchors: {cue_id}")
        center_frame = (active_start + active_end - 1) // 2
        windows.append((cue_id, center_frame))
    confirm_frame = RENDER_PLAN["frames"]["anchors"]["confirm"]
    s06 = cues.get("S06", {})
    if s06.get("activeEndFrameExclusive", TOTAL_FRAMES + 1) > confirm_frame:
        raise ValidationError("Measured S06 active narration extends past the confirmation frame")
    outputs = delivery.get("outputs") if isinstance(delivery, dict) else None
    xhs = outputs.get("xiaohongshu") if isinstance(outputs, dict) else None
    if not isinstance(xhs, dict) or xhs.get("path") != RENDER_PLAN["output"]["path"]:
        raise ValidationError("delivery.json output path differs from render-plan.json")
    movie = resolve_delivery_file(xhs.get("path") if isinstance(xhs, dict) else None, "final MP4")
    # A missing final movie must not produce an actual encoded-audio report.
    movie_sig_before = stat_signature(movie)
    movie_hash_before = sha256_file(movie)
    report: dict[str, Any] = {
        "schemaVersion": 1,
        "generatedAt": now_iso(),
        "work": {"id": WORK_ID, "title": WORK_TITLE},
        "status": "FAIL",
        "deliveryManifest": "delivery.json",
        "deliveryManifestSha256": sha256_file(delivery_path),
        "movie": {"path": str(movie.relative_to(DELIVERY_DIR)), "sha256": movie_hash_before, "bytes": movie_sig_before[0]},
        "master": {},
        "method": {
            "comparison": "mono average of accepted PCM master versus mono average of decoded final-MP4 AAC",
            "fftCorrelation": True,
            "lagSearchSamples": [-MAX_LAG_SAMPLES, MAX_LAG_SAMPLES],
            "lagConvention": "positive means encoded AAC is delayed relative to PCM master",
            "passCriteria": {
                "maxAbsoluteLagSamples": MAX_ALLOWED_LAG_SAMPLES,
                "minimumCorrelation": CORRELATION_THRESHOLD,
                "masterWindowMustHaveEnergy": True,
            },
            "windowLengthSamplesPerChannel": WINDOW_SAMPLES,
            "narrationWindowsFromMeasuredSynthesis": [{"id": label, "frame": frame} for label, frame in windows],
            "synthesisReportSha256": sha256_file(synthesis_path),
            "exactPcmSilenceFramesHalfOpen": [SILENCE_START_FRAME, SILENCE_END_FRAME],
            "exactPcmSilenceSamplesPerChannelHalfOpen": [SILENCE_START_SAMPLE, SILENCE_END_SAMPLE],
        },
        "checks": [],
        "windows": [],
    }
    checks: list[dict[str, Any]] = report["checks"]

    def record(name: str, passed: bool, details: Any) -> None:
        checks.append({"name": name, "status": "PASS" if passed else "FAIL", "details": details})

    try:
        mix_qa_path = DELIVERY_DIR / "review" / "audio-mix-qa.json"
        mix_qa = read_json(mix_qa_path)
        master_rel = (delivery.get("audio") or {}).get("master")
        master = resolve_delivery_file(master_rel, "PCM master")
        master_mono, master_info = _master_pcm(master)
        master_sha = master_info["sha256"]
        report["master"] = {
            "path": str(master.relative_to(DELIVERY_DIR)),
            "sha256": master_sha,
            "bytes": master_info["bytes"],
            "mixQaStatus": mix_qa.get("status"),
            "mixQaMasterSha256": mix_qa.get("masterSha256"),
            "mixQaReportSha256": sha256_file(mix_qa_path),
            "format": master_info["format"],
            "pcmSilence": {
                "rangeFramesHalfOpen": [SILENCE_START_FRAME, SILENCE_END_FRAME],
                "rangeSamplesPerChannel": master_info["silenceRangeSamplesPerChannel"],
                "samplesPerChannel": master_info["silenceSamplesPerChannel"],
                "exactZero": master_info["silenceRangeExactZero"],
            },
        }
        record("accepted_master_hash", mix_qa.get("status") == "pass" and mix_qa.get("masterSha256") == master_sha,
               {"mixQaStatus": mix_qa.get("status"), "mixQaShaMatches": mix_qa.get("masterSha256") == master_sha})
        record("master_pcm_format", master_info["format"] == {
            "sampleRateHz": SAMPLE_RATE, "channels": RENDER_PLAN["capture"]["audioChannels"], "sampleWidthBytes": 2,
            "compression": "NONE", "sampleFramesPerChannel": TOTAL_SAMPLES,
        }, master_info["format"])
        record("master_file_stable", master_info["stableDuringRead"], {"stableDuringRead": master_info["stableDuringRead"]})
        record("pcm_silence_exact_zero", master_info["silenceRangeExactZero"], report["master"]["pcmSilence"])
        lufs = mix_qa.get("measuredFinalIntegratedLufs")
        true_peak = mix_qa.get("measuredFinalTruePeakDbtp")
        accepted_mix_metrics = (
            isinstance(lufs, (int, float)) and abs(float(lufs) + 16.0) <= 0.15
            and isinstance(true_peak, (int, float)) and float(true_peak) <= -1.0
        )
        record("mix_qa_metrics_accepted", accepted_mix_metrics,
               {"measuredFinalIntegratedLufs": lufs, "measuredFinalTruePeakDbtp": true_peak})

        movie_meta = _probe_movie(movie)
        report["movie"]["audioMetadata"] = movie_meta
        expected_aac = movie_meta.get("codec_name") == "aac"
        expected_rate = movie_meta.get("sample_rate") == str(SAMPLE_RATE)
        expected_channels = movie_meta.get("channels") == RENDER_PLAN["capture"]["audioChannels"]
        record("final_movie_aac_stream", expected_aac and expected_rate and expected_channels,
               {"codec": movie_meta.get("codec_name"), "sampleRate": movie_meta.get("sample_rate"), "channels": movie_meta.get("channels")})

        encoded_mono, decode_info = _decode_movie_audio(movie)
        report["movie"]["decodedAudio"] = decode_info
        record("decoded_aac_samples", decode_info["decodedSamplesPerChannel"] >= SILENCE_END_SAMPLE,
               {"samplesPerChannel": decode_info["decodedSamplesPerChannel"], "decodedDurationSeconds": decode_info["decodedDurationSeconds"]})
        for label, frame in windows:
            report["windows"].append(analyze_window(master_mono, encoded_mono, frame, label))
        record("encoded_audio_eight_narration_windows_sync", len(report["windows"]) == EXPECTED_CUE_COUNT and all(row.get("status") == "PASS" for row in report["windows"]), report["windows"])

        if encoded_mono.size >= SILENCE_END_SAMPLE:
            encoded_silence = encoded_mono[SILENCE_START_SAMPLE:SILENCE_END_SAMPLE]
            silence_rms = float(np.sqrt(np.mean(encoded_silence * encoded_silence))) if encoded_silence.size else 0.0
            report["aacInteriorSilenceRms"] = {
                "rangeSamplesPerChannel": [SILENCE_START_SAMPLE, SILENCE_END_SAMPLE],
                "samplesPerChannel": int(encoded_silence.size),
                "rms": silence_rms,
                "rmsDbfs": None if silence_rms <= 0 else 20.0 * math.log10(silence_rms),
                "bitExactZeroClaimed": False,
            }
        else:
            report["aacInteriorSilenceRms"] = {
                "rangeSamplesPerChannel": [SILENCE_START_SAMPLE, SILENCE_END_SAMPLE],
                "samplesPerChannel": 0,
                "rms": None,
                "rmsDbfs": None,
                "bitExactZeroClaimed": False,
            }
        movie_hash_after = sha256_file(movie)
        movie_sig_after = stat_signature(movie)
        stable_movie = movie_hash_after == movie_hash_before and movie_sig_after == movie_sig_before
        record("movie_stable_during_validation", stable_movie,
               {"sha256Before": movie_hash_before, "sha256After": movie_hash_after, "stable": stable_movie})
        report["movie"]["stableDuringValidation"] = stable_movie
        report["master"]["stableDuringValidation"] = (
            master_info["stableDuringRead"] and sha256_file(master) == master_sha
        )
        record("master_stable_during_validation", report["master"]["stableDuringValidation"],
               {"stable": report["master"]["stableDuringValidation"]})
    except (ValidationError, OSError, wave.Error, ValueError) as exc:
        record("validation_execution", False, str(exc))

    report["status"] = "PASS" if checks and all(item["status"] == "PASS" for item in checks) else "FAIL"
    _atomic_report(report)
    return report, (0 if report["status"] == "PASS" else 1)


def self_test() -> dict[str, Any]:
    rng = np.random.default_rng(20261023)
    master = rng.normal(0.0, 0.2, 24_000).astype(np.float64)
    start, window, max_lag = 4_000, 12_000, 240
    delay = 137
    encoded_late = np.concatenate((np.zeros(delay), master[:-delay]))
    encoded_early = np.concatenate((master[delay:], np.zeros(delay)))
    # Use a safely interior window so both lag signs have complete context.
    def interior(signal: np.ndarray) -> dict[str, Any]:
        x = master[start:start + window]
        y = signal[start - max_lag:start + window + max_lag]
        corr = _fft_correlations(x, y, max_lag)
        best = int(np.argmax(np.where(np.isfinite(corr), corr, -np.inf))) - max_lag
        value = float(np.max(corr))
        return {"lagSamples": best, "correlation": value}

    positive = interior(encoded_late)
    negative = interior(encoded_early)
    silence = analyze_window(np.zeros_like(master), np.zeros_like(master), frame=0, label="silent", window_samples=window, max_lag=max_lag)
    unrelated = rng.normal(0.0, 0.2, master.size).astype(np.float64)
    weak = analyze_window(master, unrelated, frame=0, label="unrelated", window_samples=window, max_lag=max_lag)
    passed = (
        positive["lagSamples"] == delay
        and negative["lagSamples"] == -delay
        and positive["correlation"] >= 0.999
        and negative["correlation"] >= 0.999
        and silence.get("status") == "FAIL"
        and weak.get("status") == "FAIL"
        and weak.get("bestCorrelation", 1.0) < CORRELATION_THRESHOLD
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "positiveDelayExpectedSamples": delay,
        "positiveDelay": positive,
        "negativeAdvanceExpectedSamples": -delay,
        "negativeAdvance": negative,
        "silentWindow": {"status": silence.get("status"), "reason": silence.get("reason")},
        "unrelatedSignal": weak,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="test FFT lag sign and unstable-input rejection using synthetic signals")
    args = parser.parse_args()
    if args.self_test:
        result = self_test()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "PASS" else 1
    try:
        report, exit_code = validate_final()
    except (ValidationError, OSError, wave.Error) as exc:
        print(f"verify_encoded_audio: {exc}; no final report written", file=sys.stderr)
        return 2
    print(json.dumps({
        "status": report["status"],
        "report": str(REPORT_PATH.relative_to(DELIVERY_DIR)),
        "movieSha256": report.get("movie", {}).get("sha256"),
        "masterSha256": report.get("master", {}).get("sha256"),
        "windows": report.get("windows", []),
        "aacInteriorSilenceRms": report.get("aacInteriorSilenceRms"),
    }, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
