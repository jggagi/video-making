#!/usr/bin/env python3
"""Audit or deterministically mix EP07 audio from local PCM narration cues.

The script never contacts a speech provider. ``--audit`` is the default and
only reads the local segment, event, provider-manifest, and cue files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path
from typing import Any

try:
    import numpy as np
except ImportError as exc:  # pragma: no cover - environment diagnostic
    raise SystemExit(
        "build_audio.py requires numpy; use /opt/anaconda3/bin/python for this project"
    ) from exc


PROJECT = Path(__file__).resolve().parents[1]
AUDIO_DIR = PROJECT / "public" / "audio"
SEGMENTS_PATH = PROJECT / "segments.json"
EVENTS_PATH = PROJECT / "sfx_events.json"
PROVIDER_MANIFEST_PATH = AUDIO_DIR / "provider-manifest.json"
TIMING_PATH = PROJECT / "audio-timing.json"

FPS = 60
SAMPLE_RATE = 48_000
SAMPLES_PER_FRAME = 800
TOTAL_FRAMES = 7_200
TOTAL_SAMPLES = TOTAL_FRAMES * SAMPLES_PER_FRAME
CHANNELS = 2
BLOCK_SAMPLES = 24_000
POST_ACTIVITY_SILENCE_SAMPLES = round(0.150 * SAMPLE_RATE)
SILENCE_START_FRAME = 5_880
SILENCE_END_FRAME = 5_910
SILENCE_START_SAMPLE = SILENCE_START_FRAME * SAMPLES_PER_FRAME
SILENCE_END_SAMPLE = SILENCE_END_FRAME * SAMPLES_PER_FRAME
EXPECTED_EVENT_FRAMES = [120, 900, 1_350, 2_100, 2_760, 3_900, 4_680, 5_910, 6_480, 7_020]
TARGET_INTEGRATED_LUFS = -17.0
TARGET_TRUE_PEAK_DBTP = -1.5
TARGET_LRA = 11.0
NARRATION_GAIN = 0.88
PREMASTER_GAIN = 0.40
SCORE_VERSION = "ep07-deterministic-cosmic-score-v1"
SFX_VERSION = "ep07-frame-anchored-sfx-v1"


class AudioBuildError(RuntimeError):
    """A local input or fit failure with an actionable explanation."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AudioBuildError(f"cannot read {path.name}: {exc}") from None
    if not isinstance(value, dict):
        raise AudioBuildError(f"{path.name} must contain a JSON object")
    return value


def load_segments() -> list[dict[str, Any]]:
    data = read_json(SEGMENTS_PATH)
    for field, expected in (("fps", FPS), ("duration_seconds", 120), ("sample_rate", SAMPLE_RATE)):
        if field in data and data[field] != expected:
            raise AudioBuildError(f"segments.json {field} must be {expected}")
    segments = data.get("segments")
    if not isinstance(segments, list) or not segments:
        raise AudioBuildError("segments.json must contain a non-empty segments array")
    seen: set[str] = set()
    for segment in segments:
        if not isinstance(segment, dict):
            raise AudioBuildError("each segment must be a JSON object")
        sid = segment.get("id")
        if not isinstance(sid, str) or not sid.strip() or sid in seen:
            raise AudioBuildError(f"segment id is missing or duplicated: {sid!r}")
        seen.add(sid)
        for field in ("display_subtitle", "tts_phonetic_text"):
            if not isinstance(segment.get(field), str) or not segment[field]:
                raise AudioBuildError(f"{sid} needs non-empty {field}")
        start, end = segment.get("startFrame"), segment.get("endFrame")
        if (isinstance(start, bool) or not isinstance(start, int)
                or isinstance(end, bool) or not isinstance(end, int)
                or not 0 <= start < end <= TOTAL_FRAMES):
            raise AudioBuildError(f"{sid} has an invalid startFrame/endFrame window")
    return segments


def load_events() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    data = read_json(EVENTS_PATH)
    if (data.get("fps"), data.get("sampleRate"), data.get("samplesPerFrame")) != (
        FPS, SAMPLE_RATE, SAMPLES_PER_FRAME
    ):
        raise AudioBuildError("sfx_events.json must use 60 fps, 48 kHz, and 800 samples per frame")
    events = data.get("events")
    if not isinstance(events, list):
        raise AudioBuildError("sfx_events.json must contain an events array")
    silence_markers: list[dict[str, Any]] = []
    audible: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            raise AudioBuildError("each SFX event must be a JSON object")
        frame = event.get("frame", event.get("startFrame"))
        if isinstance(frame, bool) or not isinstance(frame, int):
            raise AudioBuildError("every SFX event needs an integer frame")
        if "sampleIndex" in event and event["sampleIndex"] != frame * SAMPLES_PER_FRAME:
            raise AudioBuildError(f"SFX event at frame {frame} has an inconsistent sampleIndex")
        is_silence = (
            event.get("id") == "absolute-silence"
            or event.get("kind") == "silence"
            or "endFrame" in event
        )
        if is_silence:
            silence_markers.append(event)
        else:
            audible.append(event)
    frames = [event.get("frame", event.get("startFrame")) for event in audible]
    if sorted(frames) != EXPECTED_EVENT_FRAMES or len(set(frames)) != len(EXPECTED_EVENT_FRAMES):
        raise AudioBuildError(f"SFX event frames must be {EXPECTED_EVENT_FRAMES}")
    if len(silence_markers) != 1:
        raise AudioBuildError("sfx_events.json must declare one absolute-silence marker at [5880,5910)")
    marker = silence_markers[0]
    marker_start = marker.get("frame", marker.get("startFrame"))
    marker_end = marker.get("endFrame")
    if (marker_start, marker_end) != (SILENCE_START_FRAME, SILENCE_END_FRAME):
        raise AudioBuildError("sfx_events.json absolute silence must be exactly [5880,5910)")
    by_frame = {event.get("frame", event.get("startFrame")): event for event in audible}
    ordered = []
    for frame in EXPECTED_EVENT_FRAMES:
        event = dict(by_frame[frame])
        event["frame"] = frame
        event["sampleIndex"] = frame * SAMPLES_PER_FRAME
        ordered.append(event)
    return ordered, data


def load_provider_manifest() -> dict[str, Any]:
    manifest = read_json(PROVIDER_MANIFEST_PATH)
    entries = manifest.get("segments")
    if not isinstance(entries, dict):
        raise AudioBuildError("provider-manifest.json must map segment ids in its segments object")
    return manifest


def cue_path_for(segment_id: str, manifest: dict[str, Any]) -> Path:
    entry = manifest["segments"].get(segment_id)
    if not isinstance(entry, dict) or not isinstance(entry.get("cue_path"), str):
        raise AudioBuildError(f"provider-manifest.json has no cue_path for {segment_id}")
    candidate = (PROJECT / entry["cue_path"]).resolve()
    try:
        candidate.relative_to(PROJECT.resolve())
    except ValueError:
        raise AudioBuildError(f"provider manifest cue path escapes project for {segment_id}") from None
    return candidate


def read_cue(path: Path, segment_id: str, manifest_entry: dict[str, Any]) -> tuple[np.ndarray, dict[str, Any]]:
    try:
        with wave.open(str(path), "rb") as wav:
            params = wav.getparams()
            payload = wav.readframes(params.nframes)
    except (OSError, wave.Error) as exc:
        raise AudioBuildError(f"cannot read local PCM cue for {segment_id}: {exc}") from None
    actual = (params.framerate, params.nchannels, params.sampwidth, params.comptype)
    expected = (SAMPLE_RATE, 1, 2, "NONE")
    if actual != expected or params.nframes <= 0 or len(payload) != params.nframes * 2:
        raise AudioBuildError(
            f"{segment_id} cue must be non-empty mono 48 kHz PCM16 WAV; observed {actual}, "
            f"{params.nframes} frames"
        )
    digest = sha256_file(path)
    declared_digest = manifest_entry.get("cue_sha256")
    if not isinstance(declared_digest, str) or declared_digest.lower() != digest:
        raise AudioBuildError(
            f"{segment_id} cue SHA-256 does not match provider-manifest.json "
            f"(declared {declared_digest!r}, measured {digest})"
        )
    manifest_text = manifest_entry.get("tts_phonetic_text")
    if manifest_text is not None and manifest_text != manifest_entry.get("_expected_tts_text"):
        raise AudioBuildError(f"{segment_id} provider manifest text does not match segments.json")
    samples = np.frombuffer(payload, dtype="<i2").copy()
    return samples, {
        "file": str(path.relative_to(PROJECT)),
        "sha256": digest,
        "pcmSha256": sha256_bytes(payload),
        "samplesAt48k": int(params.nframes),
        "sampleRate": SAMPLE_RATE,
        "channels": 1,
        "sampleWidthBytes": 2,
    }


def active_bounds(samples: np.ndarray) -> tuple[int, int, dict[str, Any]]:
    """Measure activity with a 5 ms rolling RMS and sample-resolution offsets."""
    if samples.size == 0:
        raise AudioBuildError("cue is empty")
    pcm = samples.astype(np.int32, copy=False)
    peak = int(np.max(np.abs(pcm)))
    if peak == 0:
        raise AudioBuildError("cue contains digital silence only")
    threshold = max(48, int(round(peak * 0.004)))
    window = min(240, int(samples.size))
    squared = pcm.astype(np.float64) ** 2
    cumulative = np.empty(squared.size + 1, dtype=np.float64)
    cumulative[0] = 0.0
    np.cumsum(squared, out=cumulative[1:])
    rolling_power = cumulative[window:] - cumulative[:-window]
    active_windows = np.flatnonzero(rolling_power >= window * threshold * threshold)
    if active_windows.size:
        start = int(active_windows[0])
        end = int(active_windows[-1]) + window
    else:
        # A short, quiet cue may never fill one full RMS window.
        active_samples = np.flatnonzero(np.abs(pcm) >= threshold)
        if active_samples.size == 0:
            raise AudioBuildError("cue has no measurable activity above the PCM onset threshold")
        start = int(active_samples[0])
        end = int(active_samples[-1]) + 1
    return start, end, {
        "method": "5 ms sliding RMS; threshold=max(48 PCM16, 0.4% of cue peak)",
        "thresholdPcm16": threshold,
        "windowSamples": window,
    }


def prepare_cue(segment: dict[str, Any], samples: np.ndarray, info: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    sid = segment["id"]
    start_frame = int(segment["startFrame"])
    end_frame = int(segment["endFrame"])
    active_start_in_source, active_end_in_source, method = active_bounds(samples)

    first_nonzero_values = np.flatnonzero(samples != 0)
    trim_start = int(first_nonzero_values[0]) if first_nonzero_values.size else 0
    active_start = active_start_in_source - trim_start
    active_end = active_end_in_source - trim_start
    trim_end = int(samples.size)
    wanted_end = active_end_in_source + POST_ACTIVITY_SILENCE_SAMPLES
    if wanted_end < samples.size and np.all(samples[wanted_end:] == 0):
        trim_end = wanted_end

    retained = samples[trim_start:trim_end]
    if retained.size == 0:
        raise AudioBuildError(f"{sid} has no retained cue samples after digital-silence trimming")
    declared_start_sample = start_frame * SAMPLES_PER_FRAME
    declared_end_sample = end_frame * SAMPLES_PER_FRAME
    cue_start = declared_start_sample - active_start
    voice_start = cue_start + active_start
    voice_end = cue_start + active_end
    cue_end = cue_start + int(retained.size)
    errors: list[str] = []
    if cue_start < 0:
        errors.append(
            f"{sid} measured onset offset {active_start} samples places the preserved cue before sample zero"
        )

    audio_limit = declared_end_sample
    if voice_start < SILENCE_START_SAMPLE < declared_end_sample:
        audio_limit = min(audio_limit, SILENCE_START_SAMPLE)
    if voice_start < SILENCE_END_SAMPLE and voice_end > SILENCE_START_SAMPLE:
        errors.append(
            f"{sid} measured active audio crosses exact silence [{SILENCE_START_FRAME},{SILENCE_END_FRAME})"
        )
    if voice_end + POST_ACTIVITY_SILENCE_SAMPLES > audio_limit:
        limit_frame = audio_limit // SAMPLES_PER_FRAME
        errors.append(
            f"{sid} active audio ends at sample {voice_end}; it needs 150 ms of room before "
            f"frame {limit_frame}, but its usable window ends at sample {audio_limit}"
        )
    if cue_end > declared_end_sample:
        errors.append(
            f"{sid} preserved cue ends at sample {cue_end}, past its declared window end {declared_end_sample}; "
            "only exact digital edge silence may be trimmed"
        )
    if cue_start < SILENCE_END_SAMPLE and cue_end > SILENCE_START_SAMPLE:
        overlap_start = max(SILENCE_START_SAMPLE, cue_start)
        overlap_end = min(SILENCE_END_SAMPLE, cue_end)
        source_start = trim_start + overlap_start - cue_start
        source_end = trim_start + overlap_end - cue_start
        if source_start < source_end and np.any(samples[source_start:source_end] != 0):
            errors.append(
                f"{sid} preserved nonzero cue samples would occupy exact silence "
                f"[{SILENCE_START_FRAME},{SILENCE_END_FRAME})"
            )

    prepared = {
        "segmentId": sid,
        "samples": retained,
        "cueStartSample": cue_start,
        "cueEndSampleExclusive": cue_end,
        "voiceStartSample": voice_start,
        "voiceEndSampleExclusive": voice_end,
        "sourcePath": info["file"],
        "sourceSamples": int(samples.size),
        "trimStartSample": trim_start,
        "trimEndSampleExclusive": trim_end,
        "activeStartOffsetInSourceSamples": active_start_in_source,
        "activeEndOffsetInSourceSamplesExclusive": active_end_in_source,
        "activeStartOffsetInRetainedCueSamples": active_start,
        "activeEndOffsetInRetainedCueSamplesExclusive": active_end,
        "onsetMeasurement": method,
        "cueSha256": info["sha256"],
        "cuePcmSha256": info["pcmSha256"],
        "sourceCueSampleRate": SAMPLE_RATE,
        "sourceCueChannels": 1,
        "sourceCueSampleWidthBytes": 2,
        "trimmedLeadingSamples": trim_start,
        "trimmedTrailingSamples": int(samples.size) - trim_end,
        "trimPolicy": "trim exact digital edge silence only; retain all speech and nonzero PCM",
        "declaredStartFrame": start_frame,
        "declaredEndFrame": end_frame,
        "measuredActiveSamples": active_end_in_source - active_start_in_source,
        "postActivitySilenceSamples": POST_ACTIVITY_SILENCE_SAMPLES,
        "postActivitySilenceMilliseconds": 150,
    }
    return prepared, errors


def audit_cues(segments: list[dict[str, Any]] | None = None) -> int:
    if segments is None:
        segments = load_segments()
    if not PROVIDER_MANIFEST_PATH.is_file():
        print(json.dumps({
            "status": "pending_provider_manifest",
            "missing": [str(PROVIDER_MANIFEST_PATH.relative_to(PROJECT))],
        }, ensure_ascii=False, indent=2))
        return 0
    manifest = load_provider_manifest()
    measured: list[dict[str, Any]] = []
    missing: list[str] = []
    failures: list[str] = []
    prepared_for_overlap: list[dict[str, Any]] = []
    for segment in segments:
        sid = segment["id"]
        try:
            path = cue_path_for(sid, manifest)
        except AudioBuildError as exc:
            failures.append(str(exc))
            continue
        if not path.is_file():
            missing.append(str(path.relative_to(PROJECT)))
            continue
        entry = dict(manifest["segments"][sid])
        if entry.get("tts_phonetic_text") is not None and entry["tts_phonetic_text"] != segment["tts_phonetic_text"]:
            failures.append(f"{sid} provider manifest tts_phonetic_text differs from segments.json")
            continue
        try:
            samples, info = read_cue(path, sid, {**entry, "_expected_tts_text": segment["tts_phonetic_text"]})
            prepared, errors = prepare_cue(segment, samples, info)
        except AudioBuildError as exc:
            failures.append(f"{sid}: {exc}")
            continue
        prepared_for_overlap.append(prepared)
        measured.append({
            key: value for key, value in prepared.items() if key != "samples"
        } | {"fit": "needs_sol" if errors else "fits", "fitErrors": errors})
    for previous, current in zip(sorted(prepared_for_overlap, key=lambda item: item["cueStartSample"]),
                                 sorted(prepared_for_overlap, key=lambda item: item["cueStartSample"])[1:]):
        if previous["cueEndSampleExclusive"] > current["cueStartSample"]:
            failures.append(
                f"preserved narration cues overlap: {previous['segmentId']} and {current['segmentId']}"
            )
    fit_errors = [error for item in measured for error in item.get("fitErrors", [])]
    failures.extend(fit_errors)
    status = "needs_sol" if failures else ("pending_cues" if missing else "cues_measured")
    report = {
        "status": status,
        "cueCountMeasured": len(measured),
        "cues": measured,
        "missing": missing,
        "failures": failures,
        "silenceWindow": {
            "startFrame": SILENCE_START_FRAME,
            "endFrameExclusive": SILENCE_END_FRAME,
            "startSample": SILENCE_START_SAMPLE,
            "endSampleExclusive": SILENCE_END_SAMPLE,
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if failures else 0


def fit_cues(segments: list[dict[str, Any]], manifest: dict[str, Any]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for segment in segments:
        sid = segment["id"]
        entry = manifest["segments"].get(sid)
        if not isinstance(entry, dict):
            raise AudioBuildError(f"provider-manifest.json has no entry for {sid}")
        path = cue_path_for(sid, manifest)
        if not path.is_file():
            raise AudioBuildError(f"missing local narration cue for {sid}: {path.relative_to(PROJECT)}")
        if entry.get("tts_phonetic_text") is not None and entry["tts_phonetic_text"] != segment["tts_phonetic_text"]:
            raise AudioBuildError(f"NEEDS_SOL: {sid} manifest text differs from the current tts_phonetic_text")
        samples, info = read_cue(path, sid, {**entry, "_expected_tts_text": segment["tts_phonetic_text"]})
        item, errors = prepare_cue(segment, samples, info)
        if errors:
            raise AudioBuildError("NEEDS_SOL: " + "; ".join(errors))
        prepared.append(item)
    ordered = sorted(prepared, key=lambda item: item["cueStartSample"])
    for previous, current in zip(ordered, ordered[1:]):
        if previous["cueEndSampleExclusive"] > current["cueStartSample"]:
            raise AudioBuildError(
                f"NEEDS_SOL: preserved narration cue spans overlap for {previous['segmentId']} and {current['segmentId']}"
            )
    return ordered


def pcm16_bytes(values: np.ndarray) -> bytes:
    clipped = np.clip(np.rint(values), -32768, 32767).astype("<i2", copy=False)
    return clipped.tobytes()


def write_stereo_wav(path: Path, blocks: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        for payload in blocks:
            wav.writeframesraw(payload)


def validate_wav(path: Path, *, channels: int = CHANNELS) -> dict[str, Any]:
    try:
        with wave.open(str(path), "rb") as wav:
            params = wav.getparams()
            payload = wav.readframes(params.nframes)
    except (OSError, wave.Error) as exc:
        raise AudioBuildError(f"cannot read generated WAV {path.name}: {exc}") from None
    expected = (SAMPLE_RATE, channels, 2, TOTAL_SAMPLES, "NONE")
    actual = (params.framerate, params.nchannels, params.sampwidth, params.nframes, params.comptype)
    if actual != expected or len(payload) != TOTAL_SAMPLES * channels * 2:
        raise AudioBuildError(f"{path.name} must be exact 48 kHz PCM16, {TOTAL_SAMPLES} samples/channel; got {actual}")
    return {
        "file": str(path.relative_to(PROJECT)),
        "sha256": sha256_file(path),
        "sampleRate": SAMPLE_RATE,
        "channels": channels,
        "sampleWidthBytes": 2,
        "samplesPerChannel": TOTAL_SAMPLES,
        "durationSeconds": 120.0,
    }


def zero_peak_in_interval(path: Path, start: int = SILENCE_START_SAMPLE,
                          end: int = SILENCE_END_SAMPLE) -> int:
    try:
        with wave.open(str(path), "rb") as wav:
            if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getnframes()) != (
                SAMPLE_RATE, CHANNELS, 2, TOTAL_SAMPLES
            ):
                raise AudioBuildError(f"{path.name} has the wrong PCM format or duration")
            wav.setpos(start)
            payload = wav.readframes(end - start)
    except (OSError, wave.Error) as exc:
        raise AudioBuildError(f"cannot inspect {path.name} silence window: {exc}") from None
    values = np.frombuffer(payload, dtype="<i2")
    return int(np.max(np.abs(values.astype(np.int32)))) if values.size else 0


def require_exact_silence(path: Path, label: str) -> dict[str, Any]:
    peak = zero_peak_in_interval(path)
    if peak != 0:
        raise AudioBuildError(
            f"NEEDS_SOL: {label} contains nonzero PCM in required silent samples "
            f"[{SILENCE_START_SAMPLE},{SILENCE_END_SAMPLE}) (peak {peak})"
        )
    return {
        "startFrame": SILENCE_START_FRAME,
        "endFrameExclusive": SILENCE_END_FRAME,
        "startSample": SILENCE_START_SAMPLE,
        "endSampleExclusive": SILENCE_END_SAMPLE,
        "peakPcm16": 0,
        "exactZero": True,
    }


def render_narration(path: Path, spans: list[dict[str, Any]]) -> dict[str, Any]:
    def blocks() -> Any:
        span_index = 0
        for block_start in range(0, TOTAL_SAMPLES, BLOCK_SAMPLES):
            count = min(BLOCK_SAMPLES, TOTAL_SAMPLES - block_start)
            block_end = block_start + count
            mono = np.zeros(count, dtype=np.float64)
            while span_index < len(spans) and spans[span_index]["cueEndSampleExclusive"] <= block_start:
                span_index += 1
            cursor = span_index
            while cursor < len(spans) and spans[cursor]["cueStartSample"] < block_end:
                span = spans[cursor]
                left = max(block_start, span["cueStartSample"])
                right = min(block_end, span["cueEndSampleExclusive"])
                if left < right:
                    source_start = left - span["cueStartSample"]
                    source_end = source_start + right - left
                    target_start = left - block_start
                    mono[target_start:target_start + right - left] = (
                        span["samples"][source_start:source_end].astype(np.float64) * NARRATION_GAIN
                    )
                cursor += 1
            stereo = np.column_stack((mono, mono))
            yield pcm16_bytes(stereo)
    write_stereo_wav(path, blocks())
    output = validate_wav(path)
    output["gainLinear"] = NARRATION_GAIN
    output["silenceWindow"] = require_exact_silence(path, "narration stem")
    return output


def smoothstep(value: np.ndarray | float) -> np.ndarray | float:
    clipped = np.clip(value, 0.0, 1.0)
    return clipped * clipped * (3.0 - 2.0 * clipped)


def voice_duck_gain(block_start: int, count: int, spans: list[dict[str, Any]]) -> np.ndarray:
    indices = block_start + np.arange(count, dtype=np.int64)
    gain = np.ones(count, dtype=np.float64)
    target = 10.0 ** (-7.0 / 20.0)
    attack = round(0.060 * SAMPLE_RATE)
    release = round(0.420 * SAMPLE_RATE)
    for span in spans:
        voice_start = span["voiceStartSample"]
        voice_end = span["voiceEndSampleExclusive"]
        local_start = voice_start - attack
        local_end = voice_end + release
        if local_end <= block_start or local_start >= block_start + count:
            continue
        ramp_in = (indices - local_start) / max(1, attack)
        ramp_out = (indices - voice_end) / max(1, release)
        local = np.where(
            indices < voice_start,
            1.0 + (target - 1.0) * smoothstep(ramp_in),
            np.where(indices < voice_end, target, target + (1.0 - target) * smoothstep(ramp_out)),
        )
        active = (indices >= local_start) & (indices < local_end)
        gain[active] = np.minimum(gain[active], local[active])
    return gain


def seeded_texture_parameters(seed: int, count: int, low_hz: float, high_hz: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.Generator(np.random.PCG64(seed))
    frequencies = rng.uniform(low_hz, high_hz, size=count)
    phases = rng.uniform(0.0, 2.0 * np.pi, size=count)
    weights = rng.uniform(0.25, 1.0, size=count)
    weights /= max(float(np.sum(weights)), 1e-9)
    return frequencies, phases, weights


TEXTURE_FREQUENCIES, TEXTURE_PHASES, TEXTURE_WEIGHTS = seeded_texture_parameters(
    0xE907B1A7, 14, 110.0, 880.0
)


def render_music(path: Path, spans: list[dict[str, Any]]) -> dict[str, Any]:
    def blocks() -> Any:
        for block_start in range(0, TOTAL_SAMPLES, BLOCK_SAMPLES):
            count = min(BLOCK_SAMPLES, TOTAL_SAMPLES - block_start)
            sample_ids = block_start + np.arange(count, dtype=np.int64)
            t = sample_ids.astype(np.float64) / SAMPLE_RATE
            score = np.zeros(count, dtype=np.float64)

            # Act I: warm, dark harmonics under 500 Hz gradually tighten into
            # a compressed, detuned pulse as the human language channel closes.
            warm_gate = smoothstep(t / 1.8) * (1.0 - smoothstep((t - 26.0) / 5.0))
            warm = np.zeros(count, dtype=np.float64)
            for index, (freq, weight) in enumerate(((55.0, .28), (82.41, .18), (110.0, .25),
                                                    (164.81, .22), (220.0, .18), (329.63, .09), (440.0, .04))):
                warm += weight * np.sin(2.0 * np.pi * freq * t + index * .43)
            warm *= 0.12 * (0.92 + 0.08 * np.sin(2.0 * np.pi * 0.045 * t))
            score += warm_gate * warm

            tension_gate = smoothstep((t - 16.0) / 5.0) * (1.0 - smoothstep((t - 31.0) / 4.0))
            tension_phase = 2.0 * np.pi * (72.0 * t + 2.5 * np.sin(2.0 * np.pi * 0.13 * t))
            tension = 0.10 * np.sin(tension_phase) + 0.035 * np.sin(2.0 * np.pi * 144.4 * t)
            compressed = np.tanh(2.8 * tension) / 2.8
            score += tension_gate * compressed

            # Act II: an aurora of detuned, seeded, multi-octave partials.
            aurora_gate = smoothstep((t - 27.0) / 5.0) * (1.0 - smoothstep((t - 59.0) / 6.0))
            aurora = np.zeros(count, dtype=np.float64)
            for index, (freq, weight) in enumerate(((55.0, .18), (82.41, .12), (110.0, .16),
                                                    (164.81, .15), (220.0, .13), (329.63, .12),
                                                    (440.0, .10), (659.25, .075), (880.0, .055))):
                lfo = 0.72 + 0.28 * np.sin(2.0 * np.pi * (0.035 + index * .002) * t + index)
                base = np.sin(2.0 * np.pi * freq * t + index * .31)
                shimmer = 0.28 * np.sin(2.0 * np.pi * (freq + 0.31 + index * .025) * t + index * .79)
                aurora += weight * lfo * (base + shimmer)
            texture = np.zeros(count, dtype=np.float64)
            for freq, phase, weight in zip(TEXTURE_FREQUENCIES, TEXTURE_PHASES, TEXTURE_WEIGHTS):
                texture += weight * np.sin(2.0 * np.pi * freq * t + phase)
            score += aurora_gate * (0.16 * aurora + 0.008 * texture)

            # Act III: ominous, slowly beating alien-organ fundamentals.
            organ_gate = smoothstep((t - 56.0) / 6.0) * (1.0 - smoothstep((t - 90.0) / 7.0))
            organ = np.zeros(count, dtype=np.float64)
            for index, (freq, weight) in enumerate(((41.2, .12), (55.0, .20), (82.41, .18),
                                                    (110.0, .20), (116.54, .11), (164.81, .14),
                                                    (220.0, .11), (246.94, .08), (329.63, .05))):
                mod = 0.42 * np.sin(2.0 * np.pi * (0.018 + index * .001) * t + index * .54)
                organ += weight * np.sin(2.0 * np.pi * freq * t + mod + index * .21)
            score += organ_gate * 0.18 * organ

            # Act IV: a melancholy cello-like line with slow glissandi and
            # restrained vibrato; all fundamentals remain below 500 Hz.
            closing_gate = smoothstep((t - 86.0) / 7.0) * (1.0 - smoothstep((t - 118.5) / 1.5))
            closing = np.zeros(count, dtype=np.float64)
            close_t = np.maximum(0.0, t - 90.0)
            for index, (freq, weight, bend) in enumerate(((65.41, .23, -1.5), (98.0, .18, 1.0),
                                                          (130.81, .17, -1.0), (196.0, .12, .7),
                                                          (261.63, .07, -0.5), (392.0, .035, .25))):
                vibrato = 0.55 * np.sin(2.0 * np.pi * 0.23 * close_t + index * .5)
                phase = 2.0 * np.pi * (freq * close_t + 0.5 * bend * close_t * close_t / 30.0)
                closing += weight * np.sin(phase + vibrato + index * .33)
            score += closing_gate * 0.19 * closing

            # Protect both sides of the authored vacuum; the new score waits
            # until after frame 5910 so the chime has an uncluttered onset.
            pre_fade_start = SILENCE_START_SAMPLE - round(0.180 * SAMPLE_RATE)
            fade_out = 1.0 - smoothstep((sample_ids - pre_fade_start) / max(1, SILENCE_START_SAMPLE - pre_fade_start))
            fade_in = smoothstep((sample_ids - SILENCE_END_SAMPLE) / round(0.650 * SAMPLE_RATE))
            score *= np.where(sample_ids < SILENCE_START_SAMPLE, fade_out, fade_in)
            duck = voice_duck_gain(block_start, count, spans)
            score *= duck
            silent = (sample_ids >= SILENCE_START_SAMPLE) & (sample_ids < SILENCE_END_SAMPLE)
            score[silent] = 0.0
            stereo = np.column_stack((score * 0.97, score * 1.03)) * 32767.0
            yield pcm16_bytes(stereo)
    write_stereo_wav(path, blocks())
    output = validate_wav(path)
    output["design"] = {
        "version": SCORE_VERSION,
        "arc": "warm low-passed opening, compressed tension, shimmering multi-octave aurora, ominous alien organ, melancholy cello-like close",
        "speechDuck": {"targetDb": -7.0, "attackSeconds": 0.060, "releaseSeconds": 0.420},
        "spectralCeilingHz": 880,
        "seededTexture": {"seed": "0xE907B1A7", "partials": int(TEXTURE_FREQUENCIES.size), "frequencyRangeHz": [110, 880]},
        "silenceWindow": [SILENCE_START_FRAME, SILENCE_END_FRAME],
    }
    output["silenceWindow"] = require_exact_silence(path, "music stem")
    return output


def event_duration_seconds(frame: int) -> float:
    return {
        120: 0.90,
        900: 1.55,
        1_350: 1.70,
        2_100: 0.95,
        2_760: 2.80,
        3_900: 0.90,
        4_680: 3.20,
        5_910: 2.80,
        6_480: 4.40,
        7_020: 1.70,
    }[frame]


def event_seed(event: dict[str, Any]) -> int:
    material = f"EP07:{event.get('id', 'event')}:{event['frame']}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "little")


def lowband_texture(count: int, seed: int) -> np.ndarray:
    rng = np.random.Generator(np.random.PCG64(seed))
    frequencies = rng.uniform(90.0, 880.0, size=8)
    phases = rng.uniform(0.0, 2.0 * np.pi, size=8)
    weights = rng.uniform(0.2, 1.0, size=8)
    weights /= max(float(np.sum(weights)), 1e-9)
    t = np.arange(count, dtype=np.float64) / SAMPLE_RATE
    texture = np.zeros(count, dtype=np.float64)
    for freq, phase, weight in zip(frequencies, phases, weights):
        texture += weight * np.sin(2.0 * np.pi * freq * t + phase)
    return texture


def synthesize_event(event: dict[str, Any]) -> tuple[np.ndarray, dict[str, Any]]:
    frame = event["frame"]
    duration = event_duration_seconds(frame)
    count = round(duration * SAMPLE_RATE)
    age = np.arange(count, dtype=np.float64) / SAMPLE_RATE
    seed = event_seed(event)
    kind_by_frame = {
        120: "curious-tilt", 900: "compression", 1_350: "dual-sonar", 2_100: "protocol-switch",
        2_760: "aurora", 3_900: "decoder-short", 4_680: "alien-choir", 5_910: "gentle-chime",
        6_480: "cosmic-cello", 7_020: "folding-matter",
    }
    kind = kind_by_frame[frame]
    signal = np.zeros(count, dtype=np.float64)
    if kind == "curious-tilt":
        phase = 2.0 * np.pi * (220.0 * age + 0.5 * 75.0 * age * age)
        signal = 0.11 * np.sin(phase) + 0.035 * np.sin(2.0 * np.pi * 440.0 * age)
    elif kind == "compression":
        frequency = 360.0 * np.exp(-1.6 * age) + 58.0
        phase = 2.0 * np.pi * np.cumsum(frequency) / SAMPLE_RATE
        pulse = 0.70 + 0.30 * np.sin(2.0 * np.pi * 2.2 * age)
        signal = 0.15 * pulse * np.sin(phase) + 0.035 * lowband_texture(count, seed)
    elif kind == "dual-sonar":
        first = np.exp(-((age - 0.12) / 0.10) ** 2)
        second = 0.82 * np.exp(-((age - 0.62) / 0.13) ** 2)
        signal = (first + second) * (0.16 * np.sin(2.0 * np.pi * 420.0 * age)
                                     + 0.07 * np.sin(2.0 * np.pi * 630.0 * age))
    elif kind == "protocol-switch":
        frequency = 720.0 * np.exp(-2.4 * age) + 82.0
        phase = 2.0 * np.pi * np.cumsum(frequency) / SAMPLE_RATE
        signal = 0.18 * np.sin(phase) * np.exp(-2.8 * age)
    elif kind == "aurora":
        for index, (frequency, weight) in enumerate(((55.0, .13), (110.0, .12), (164.81, .11),
                                                    (220.0, .10), (329.63, .09), (440.0, .075),
                                                    (659.25, .055), (880.0, .035))):
            tremolo = 0.78 + 0.22 * np.sin(2.0 * np.pi * (0.4 + index * .03) * age + index)
            signal += weight * tremolo * np.sin(2.0 * np.pi * frequency * age + index * .4)
    elif kind == "decoder-short":
        gate = np.sin(2.0 * np.pi * 3.0 * age) > 0.25
        signal = gate.astype(np.float64) * 0.12 * np.sin(2.0 * np.pi * 790.0 * age)
        signal += 0.025 * lowband_texture(count, seed)
    elif kind == "alien-choir":
        for index, (frequency, weight) in enumerate(((55.0, .17), (82.41, .16), (110.0, .15),
                                                    (116.54, .12), (164.81, .12), (220.0, .09),
                                                    (246.94, .07), (329.63, .035))):
            vibrato = 0.45 * np.sin(2.0 * np.pi * (0.22 + index * .018) * age + index)
            signal += weight * np.sin(2.0 * np.pi * frequency * age + vibrato + index * .47)
    elif kind == "gentle-chime":
        for index, (frequency, weight, decay) in enumerate(((523.25, .16, 1.25), (659.25, .12, .95),
                                                           (783.99, .08, .72), (392.0, .045, 1.6))):
            signal += weight * np.sin(2.0 * np.pi * frequency * age + index * .2) * np.exp(-decay * age)
    elif kind == "cosmic-cello":
        bend = 14.0 * np.sin(2.0 * np.pi * 0.11 * age)
        phase = 2.0 * np.pi * np.cumsum(110.0 + bend) / SAMPLE_RATE
        vibrato = 0.35 * np.sin(2.0 * np.pi * 0.24 * age)
        signal = 0.16 * np.sin(phase + vibrato) + 0.055 * np.sin(2.0 * phase + 0.2)
    elif kind == "folding-matter":
        frequency = 420.0 * np.exp(-2.0 * age) + 55.0
        phase = 2.0 * np.pi * np.cumsum(frequency) / SAMPLE_RATE
        signal = 0.13 * np.sin(phase) * np.exp(-1.5 * age)

    attack = smoothstep(age / 0.015)
    release = 1.0 - smoothstep((age - (duration - 0.240)) / 0.240)
    signal *= attack * release
    if kind == "gentle-chime":
        # The chime begins at the first sample after the authored vacuum.
        signal[0] = 0.0
    return signal, {
        "id": event.get("id", kind),
        "kind": kind,
        "frame": frame,
        "sampleIndex": event["sampleIndex"],
        "durationSeconds": duration,
        "seed": seed,
        "spectralCeilingHz": 880,
        "voiceBandDesign": "synthesized partials and seeded texture remain below 1 kHz",
    }


def render_sfx(path: Path, events: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    synthesized = []
    onset_map = []
    for event in events:
        signal, mapped = synthesize_event(event)
        if event["frame"] == 5_910:
            mapped["startsAtSilenceEnd"] = True
        synthesized.append({"start": event["sampleIndex"], "signal": signal, "id": mapped["id"]})
        onset_map.append(mapped)

    def blocks() -> Any:
        event_index = 0
        for block_start in range(0, TOTAL_SAMPLES, BLOCK_SAMPLES):
            count = min(BLOCK_SAMPLES, TOTAL_SAMPLES - block_start)
            block_end = block_start + count
            stereo = np.zeros((count, 2), dtype=np.float64)
            while event_index < len(synthesized) and (
                synthesized[event_index]["start"] + synthesized[event_index]["signal"].size <= block_start
            ):
                event_index += 1
            cursor = event_index
            while cursor < len(synthesized) and synthesized[cursor]["start"] < block_end:
                item = synthesized[cursor]
                start = max(block_start, item["start"])
                end = min(block_end, item["start"] + item["signal"].size)
                if start < end:
                    source_start = start - item["start"]
                    source_end = source_start + end - start
                    signal = item["signal"][source_start:source_end]
                    t = (np.arange(start, end, dtype=np.float64) - item["start"]) / SAMPLE_RATE
                    stereo[start - block_start:end - block_start, 0] += signal * (0.98 + 0.02 * np.sin(2.0 * np.pi * .31 * t))
                    stereo[start - block_start:end - block_start, 1] += signal * (0.98 - 0.02 * np.sin(2.0 * np.pi * .31 * t))
                cursor += 1
            sample_ids = block_start + np.arange(count, dtype=np.int64)
            silent = (sample_ids >= SILENCE_START_SAMPLE) & (sample_ids < SILENCE_END_SAMPLE)
            stereo[silent, :] = 0.0
            yield pcm16_bytes(stereo * 32767.0)
    write_stereo_wav(path, blocks())
    output = validate_wav(path)
    output["design"] = {
        "version": SFX_VERSION,
        "synthesis": "frame-anchored deterministic sine/FM plus event-seeded low-band texture",
        "spectralCeilingHz": 880,
        "events": onset_map,
    }
    output["silenceWindow"] = require_exact_silence(path, "SFX stem")
    return output, onset_map


def render_premaster(path: Path, stem_paths: list[Path]) -> dict[str, Any]:
    with wave.open(str(stem_paths[0]), "rb") as stem:
        params = stem.getparams()
    expected = (SAMPLE_RATE, CHANNELS, 2, TOTAL_SAMPLES, "NONE")
    if (params.framerate, params.nchannels, params.sampwidth, params.nframes, params.comptype) != expected:
        raise AudioBuildError("stem format changed before premaster render")
    arrays: list[np.ndarray] = []
    for stem_path in stem_paths:
        with wave.open(str(stem_path), "rb") as wav:
            payload = wav.readframes(TOTAL_SAMPLES)
        values = np.frombuffer(payload, dtype="<i2")
        if values.size != TOTAL_SAMPLES * CHANNELS:
            raise AudioBuildError(f"{stem_path.name} ended before the full premaster duration")
        arrays.append(values.reshape((-1, CHANNELS)).astype(np.float64))

    def blocks() -> Any:
        for start in range(0, TOTAL_SAMPLES, BLOCK_SAMPLES):
            end = min(TOTAL_SAMPLES, start + BLOCK_SAMPLES)
            mixed = arrays[0][start:end].copy()
            for values in arrays[1:]:
                mixed += values[start:end]
            # Fixed headroom prevents PCM16 clipping before FFmpeg's measured
            # loudnorm pass can apply the requested integrated/true-peak target.
            yield pcm16_bytes(mixed * PREMASTER_GAIN)
    write_stereo_wav(path, blocks())
    output = validate_wav(path)
    output["inputs"] = [str(item.relative_to(PROJECT)) for item in stem_paths]
    output["gainLinear"] = PREMASTER_GAIN
    output["headroomDb"] = round(20.0 * math.log10(PREMASTER_GAIN), 3)
    output["silenceWindow"] = require_exact_silence(path, "premaster")
    return output


def run_ffmpeg(args: list[str], label: str) -> str:
    try:
        result = subprocess.run(args, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except OSError as exc:
        raise AudioBuildError(f"cannot run FFmpeg for {label}: {exc}") from None
    if result.returncode:
        detail = (result.stderr or result.stdout or "").strip().splitlines()[-8:]
        raise AudioBuildError(f"{label} failed (exit {result.returncode}): {' | '.join(detail)}")
    return result.stderr or ""


def loudnorm_measurements(output: str) -> dict[str, Any]:
    matches = list(re.finditer(r"\{\s*\"input_i\"[\s\S]*?\}", output))
    if not matches:
        raise AudioBuildError("FFmpeg loudnorm returned no measured JSON")
    try:
        value = json.loads(matches[-1].group(0))
    except json.JSONDecodeError:
        raise AudioBuildError("FFmpeg loudnorm returned malformed measurement JSON") from None
    needed = ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")
    if any(key not in value for key in needed):
        raise AudioBuildError("FFmpeg loudnorm measurement is incomplete")
    return value


def measure_ebur128(path: Path) -> dict[str, float]:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise AudioBuildError("ffmpeg is required for two-pass loudnorm and true-peak verification")
    output = run_ffmpeg([
        ffmpeg, "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"
    ], "ebur128 measurement")
    integrated = re.search(r"^\s*I:\s*(-?\d+(?:\.\d+)?)\s+LUFS\s*$", output, re.MULTILINE)
    true_peak = re.search(r"^\s*True peak:\s*(-?\d+(?:\.\d+)?)\s+dBTP\s*$", output, re.MULTILINE)
    if true_peak is None:
        true_peak = re.search(r"True peak:\s*\n\s*Peak:\s*(-?\d+(?:\.\d+)?)\s+dBFS", output)
    if integrated is None or true_peak is None:
        raise AudioBuildError("FFmpeg ebur128 did not report integrated LUFS and true peak")
    return {"integratedLUFS": float(integrated.group(1)), "truePeakDBTP": float(true_peak.group(1))}


def rewrite_silence_exact(path: Path) -> dict[str, Any]:
    temporary = path.with_name(path.stem + ".silence.tmp.wav")
    try:
        with wave.open(str(path), "rb") as source:
            params = source.getparams()
            if (params.framerate, params.nchannels, params.sampwidth, params.nframes, params.comptype) != (
                SAMPLE_RATE, CHANNELS, 2, TOTAL_SAMPLES, "NONE"
            ):
                raise AudioBuildError("master must be exact-length stereo PCM16 before silence enforcement")
            with wave.open(str(temporary), "wb") as target:
                target.setnchannels(CHANNELS)
                target.setsampwidth(2)
                target.setframerate(SAMPLE_RATE)
                cursor = 0
                while cursor < TOTAL_SAMPLES:
                    count = min(BLOCK_SAMPLES, TOTAL_SAMPLES - cursor)
                    payload = bytearray(source.readframes(count))
                    if len(payload) != count * CHANNELS * 2:
                        raise AudioBuildError("master ended before exact-silence enforcement completed")
                    left = max(cursor, SILENCE_START_SAMPLE)
                    right = min(cursor + count, SILENCE_END_SAMPLE)
                    if left < right:
                        start_byte = (left - cursor) * CHANNELS * 2
                        end_byte = start_byte + (right - left) * CHANNELS * 2
                        payload[start_byte:end_byte] = b"\0" * (end_byte - start_byte)
                    target.writeframesraw(payload)
                    cursor += count
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return require_exact_silence(path, "master")


def apply_volume_adjustment(source: Path, target: Path, gain_db: float) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise AudioBuildError("ffmpeg is required for final loudness adjustment")
    gain = f"{gain_db:.6f}dB"
    filter_graph = (
        f"volume={gain},aresample={SAMPLE_RATE},apad=whole_len={TOTAL_SAMPLES},"
        f"atrim=end_sample={TOTAL_SAMPLES},asetpts=N/SR/TB"
    )
    run_ffmpeg([
        ffmpeg, "-hide_banner", "-nostats", "-y", "-i", str(source), "-af", filter_graph,
        "-ar", str(SAMPLE_RATE), "-ac", str(CHANNELS), "-c:a", "pcm_s16le", str(target),
    ], "final deterministic volume adjustment")


def mix_master(path: Path, premaster: Path) -> dict[str, Any]:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise AudioBuildError("ffmpeg is required for two-pass loudnorm and true-peak limiting")
    first_filter = f"loudnorm=I={TARGET_INTEGRATED_LUFS}:TP={TARGET_TRUE_PEAK_DBTP}:LRA={TARGET_LRA}:print_format=json"
    first = run_ffmpeg([
        ffmpeg, "-hide_banner", "-nostats", "-i", str(premaster), "-af", first_filter, "-f", "null", "-"
    ], "first-pass loudnorm analysis")
    measured = loudnorm_measurements(first)
    second_filter = (
        f"loudnorm=I={TARGET_INTEGRATED_LUFS}:TP={TARGET_TRUE_PEAK_DBTP}:LRA={TARGET_LRA}"
        f":measured_I={measured['input_i']}:measured_TP={measured['input_tp']}"
        f":measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}"
        f":offset={measured['target_offset']}:linear=false:print_format=json"
        f",aresample={SAMPLE_RATE},apad=whole_len={TOTAL_SAMPLES},atrim=end_sample={TOTAL_SAMPLES},asetpts=N/SR/TB"
    )
    second = run_ffmpeg([
        ffmpeg, "-hide_banner", "-nostats", "-y", "-i", str(premaster), "-af", second_filter,
        "-ar", str(SAMPLE_RATE), "-ac", str(CHANNELS), "-c:a", "pcm_s16le", str(path),
    ], "second-pass loudnorm render")
    second_stats = loudnorm_measurements(second)
    validate_wav(path)
    silence = rewrite_silence_exact(path)
    loudness = measure_ebur128(path)

    # A single deterministic gain correction aims back at -17 LUFS while
    # keeping margin below the measured true-peak ceiling. FFmpeg's loudnorm
    # remains the true-peak limiter; this correction only changes output gain.
    desired_gain = TARGET_INTEGRATED_LUFS - loudness["integratedLUFS"]
    safe_peak_gain = TARGET_TRUE_PEAK_DBTP - 0.06 - loudness["truePeakDBTP"]
    adjustment = min(desired_gain, safe_peak_gain)
    adjustment = max(-3.0, min(3.0, adjustment))
    if abs(adjustment) >= 0.05:
        adjusted = path.with_name(path.stem + ".gain.tmp.wav")
        try:
            apply_volume_adjustment(path, adjusted, adjustment)
            validate_wav(adjusted)
            adjusted.replace(path)
        finally:
            adjusted.unlink(missing_ok=True)
        silence = rewrite_silence_exact(path)
        loudness = measure_ebur128(path)

    run_ffmpeg([ffmpeg, "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"], "strict master decode")
    if not -18.0 <= loudness["integratedLUFS"] <= -16.0:
        raise AudioBuildError(f"master loudness {loudness['integratedLUFS']} LUFS is outside -18 to -16 LUFS")
    if loudness["truePeakDBTP"] > TARGET_TRUE_PEAK_DBTP:
        raise AudioBuildError(
            f"master true peak {loudness['truePeakDBTP']} dBTP exceeds {TARGET_TRUE_PEAK_DBTP} dBTP after correction"
        )
    result = validate_wav(path)
    result.update({
        "strictDecode": "passed",
        "loudnormFirstPass": measured,
        "loudnormSecondPass": second_stats,
        "ebur128Final": loudness,
        "loudnormTarget": {
            "integratedLUFS": TARGET_INTEGRATED_LUFS,
            "truePeakDBTP": TARGET_TRUE_PEAK_DBTP,
            "lra": TARGET_LRA,
            "acceptanceLUFS": [-18.0, -16.0],
            "passes": 2,
            "finalGainAdjustmentDb": round(adjustment, 6),
            "truePeakLimiter": "FFmpeg loudnorm with true-peak oversampling enabled",
        },
        "silenceWindow": silence,
    })
    return result


PUNCTUATION = set("，。！？；：、,.!?;:…—-)]}）】》」』”’\"'")


def caption_lines(text: str, maximum: int = 14) -> list[str]:
    flattened = text.replace("\r", "").replace("\n", "")
    if not flattened:
        raise AudioBuildError("display_subtitle becomes empty after removing line breaks")
    lines: list[str] = []
    offset = 0
    while offset < len(flattened):
        limit = min(len(flattened), offset + maximum)
        punctuation_ends = [index + 1 for index in range(offset, limit) if flattened[index] in PUNCTUATION]
        end = punctuation_ends[-1] if punctuation_ends else limit
        while end < len(flattened) and end - offset < maximum and flattened[end] in "”’\"'）)]】》」』":
            end += 1
        if end <= offset:
            end = limit
        lines.append(flattened[offset:end])
        offset = end
    return lines


def caption_records(segments: list[dict[str, Any]], spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {span["segmentId"]: span for span in spans}
    captions: list[dict[str, Any]] = []
    for segment in sorted(segments, key=lambda item: int(item["startFrame"])):
        span = by_id[segment["id"]]
        authored_groups = segment.get("caption_groups")
        if authored_groups:
            groups = [group.split("\n") for group in authored_groups]
            if any(len(group) > 2 for group in groups):
                raise AudioBuildError(f"caption group exceeds two lines for {segment['id']}")
        else:
            lines = caption_lines(segment["display_subtitle"])
            groups = [lines[index:index + 2] for index in range(0, len(lines), 2)]
        flattened = segment["display_subtitle"].replace("\r", "").replace("\n", "")
        if "".join("".join(group) for group in groups) != flattened:
            raise AudioBuildError(f"caption wrapping changed display text for {segment['id']}")
        if any(len(line) > 14 for group in groups for line in group):
            raise AudioBuildError(f"caption line exceeds 14 characters for {segment['id']}")
        text_units = [sum(len(line) for line in group) for group in groups]
        total_units = sum(text_units)
        active_start = span["voiceStartSample"]
        active_end = span["voiceEndSampleExclusive"]
        duration = active_end - active_start
        if len(groups) > duration // SAMPLES_PER_FRAME:
            raise AudioBuildError(f"NEEDS_SOL: {segment['id']} has too many caption groups for its measured speech duration")
        cumulative_units = 0
        previous_end = int(segment["startFrame"])
        for index, (group, units) in enumerate(zip(groups, text_units), start=1):
            sample_start = active_start + round(duration * cumulative_units / total_units)
            cumulative_units += units
            sample_end = active_end if index == len(groups) else active_start + round(duration * cumulative_units / total_units)
            start_frame = max(previous_end, int(round(sample_start / SAMPLES_PER_FRAME)))
            end_frame = int(round(sample_end / SAMPLES_PER_FRAME))
            declared_end = int(segment["endFrame"])
            end_frame = min(declared_end, max(start_frame + 1, end_frame))
            if end_frame <= start_frame:
                raise AudioBuildError(f"NEEDS_SOL: {segment['id']} cannot fit caption group {index} into whole frames")
            captions.append({
                "id": f"{segment['id']}-C{index:02d}",
                "segmentId": segment["id"],
                "startFrame": start_frame,
                "endFrame": end_frame,
                "text": "\n".join(group),
                "timingEstimate": "proportional to measured active PCM span; phrase estimate, not word alignment",
            })
            previous_end = end_frame
    return captions


def run_mix(segments: list[dict[str, Any]], events: list[dict[str, Any]], event_data: dict[str, Any]) -> int:
    if not PROVIDER_MANIFEST_PATH.is_file():
        raise AudioBuildError("provider-manifest.json is missing; local cue mixing remains pending")
    manifest = load_provider_manifest()
    spans = fit_cues(segments, manifest)
    captions = caption_records(segments, spans)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    temporary = {
        name: AUDIO_DIR / f"{name}.render.tmp.wav"
        for name in ("narration", "music", "sfx", "premaster", "master")
    }
    timing_temporary = TIMING_PATH.with_name(TIMING_PATH.name + ".tmp")
    try:
        outputs: dict[str, Any] = {}
        outputs["narration"] = render_narration(temporary["narration"], spans)
        outputs["music"] = render_music(temporary["music"], spans)
        outputs["sfx"], onset_map = render_sfx(temporary["sfx"], events)
        outputs["premaster"] = render_premaster(
            temporary["premaster"], [temporary["narration"], temporary["music"], temporary["sfx"]]
        )
        outputs["master"] = mix_master(temporary["master"], temporary["premaster"])
        for name in ("narration", "music", "sfx", "premaster", "master"):
            outputs[name]["file"] = str((AUDIO_DIR / f"{name}.wav").relative_to(PROJECT))

        sources = {
            "segmentsJsonSha256": sha256_file(SEGMENTS_PATH),
            "sfxEventsJsonSha256": sha256_file(EVENTS_PATH),
            "providerManifestSha256": sha256_file(PROVIDER_MANIFEST_PATH),
            "cues": [{
                "id": span["segmentId"],
                "file": span["sourcePath"],
                "sha256": span["cueSha256"],
                "pcmSha256": span["cuePcmSha256"],
                "sourceSamples": span["sourceSamples"],
            } for span in spans],
        }
        timing_segments = [{key: value for key, value in span.items() if key != "samples"} for span in spans]
        timing = {
            "status": "measured_pcm_with_estimated_caption_timing",
            "durationSeconds": 120,
            "fps": FPS,
            "sampleRate": SAMPLE_RATE,
            "samplesPerFrame": SAMPLES_PER_FRAME,
            "samplesPerChannel": TOTAL_SAMPLES,
            "channels": CHANNELS,
            "segments": timing_segments,
            "captions": captions,
            "captionTimingMethod": (
                "Caption groups are allocated proportionally by displayed Unicode codepoint count across each "
                "cue's measured active PCM span. This is an estimate, not ASR or word-accurate alignment."
            ),
            "sfxEvents": onset_map,
            "absoluteSilence": {
                "startFrame": SILENCE_START_FRAME,
                "endFrameExclusive": SILENCE_END_FRAME,
                "startSample": SILENCE_START_SAMPLE,
                "endSampleExclusive": SILENCE_END_SAMPLE,
                "allStemsAndMasterExactZero": True,
            },
            "master": {
                "file": outputs["master"]["file"],
                "sha256": outputs["master"]["sha256"],
                "integratedLUFS": outputs["master"]["ebur128Final"]["integratedLUFS"],
                "truePeakDBTP": outputs["master"]["ebur128Final"]["truePeakDBTP"],
                "strictDecode": outputs["master"]["strictDecode"],
            },
            "sourceHashes": sources,
            "outputs": outputs,
            "sfxSourceSha256": sha256_file(EVENTS_PATH),
            "eventSourceFrames": [event["frame"] for event in events],
            "unusedEventData": {key: event_data[key] for key in ("fps", "sampleRate", "samplesPerFrame") if key in event_data},
        }
        timing_temporary.write_text(json.dumps(timing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for name, path in temporary.items():
            path.replace(AUDIO_DIR / f"{name}.wav")
        timing_temporary.replace(TIMING_PATH)
        print(json.dumps({
            "status": "mix_complete",
            "master": outputs["master"],
            "segments": len(timing_segments),
            "captions": len(captions),
            "silenceWindow": timing["absoluteSilence"],
        }, ensure_ascii=False, indent=2))
        return 0
    finally:
        for path in temporary.values():
            path.unlink(missing_ok=True)
        timing_temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--audit", action="store_true", help="read-only cue inventory and measured active windows (default)")
    mode.add_argument("--mix", action="store_true", help="build local PCM stems, master, and estimated captions")
    args = parser.parse_args()
    try:
        segments = load_segments()
        events, event_data = load_events()
        if args.mix:
            return run_mix(segments, events, event_data)
        return audit_cues(segments)
    except (AudioBuildError, OSError, ValueError, wave.Error, OverflowError) as exc:
        print(f"build_audio.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
