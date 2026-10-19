#!/usr/bin/env python3
"""Build the EP06 shared PCM score, SFX, narration, and master from local cues."""

from __future__ import annotations

import argparse
import array
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


PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT.parent
AUDIO = PROJECT / "public" / "audio"
CUES = AUDIO / "cues"
SEGMENTS_PATH = PROJECT / "segments.json"
EVENTS_PATH = PROJECT / "sfx_events.json"
PROVIDER_MANIFEST = AUDIO / "provider-manifest.json"
TIMING_PATH = PROJECT / "audio-timing.json"
SETTINGS_PATH = AUDIO / "mix-settings.json"
MANIFEST_PATH = AUDIO / "mix-manifest.json"

FPS = 60
SAMPLE_RATE = 48_000
SAMPLES_PER_FRAME = 800
DURATION_SECONDS = 120
TOTAL_FRAMES = 7_200
TOTAL_SAMPLES = 5_760_000
BLOCK_SAMPLES = 24_000
SILENCE_START_FRAME = 5_740
SILENCE_END_FRAME = 5_760
SILENCE_START_SAMPLE = SILENCE_START_FRAME * SAMPLES_PER_FRAME
SILENCE_END_SAMPLE = SILENCE_END_FRAME * SAMPLES_PER_FRAME

# Profiles contain sound character and duration only. Event IDs and anchors are
# always read from sfx_events.json, so the authored timeline has one source.
EVENT_PROFILES = {
    "cyan-pre-echo": ("cyan", 0.42),
    "human-heartbeat": ("heartbeat", 0.78),
    "rp-lock": ("lock", 0.72),
    "amber-awareness": ("amber", 1.25),
    "glass-window": ("glass40", 1.6),
    "data-convergence": ("converge", 2.0),
    "trajectory-lock": ("lock", 0.82),
    "reward-warp": ("magenta", 1.8),
    "gentle-prison": ("metalbox", 2.2),
    "absolute-silence": ("silence", 0.0),
    "vault-seal": ("vault", 1.7),
    "sovereign-chord": ("catharsis", 7.2),
    "final-heartbeat": ("warm_heartbeat", 2.0),
}


class AudioBuildError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_hash(value: Any) -> str:
    return sha256_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AudioBuildError(f"cannot read {path.name}: {exc}") from None
    if not isinstance(value, dict):
        raise AudioBuildError(f"{path.name} must contain a JSON object")
    return value


def load_segments() -> list[dict[str, Any]]:
    if not SEGMENTS_PATH.is_file():
        raise AudioBuildError("segments.json is missing; audio build remains pending")
    data = read_json(SEGMENTS_PATH)
    for field, expected in (("fps", FPS), ("duration_seconds", DURATION_SECONDS), ("sample_rate", SAMPLE_RATE)):
        if field in data and data[field] != expected:
            raise AudioBuildError(f"segments.json {field} must be {expected}")
    segments = data.get("segments")
    if not isinstance(segments, list) or [item.get("id") for item in segments] != [f"S{i:02d}" for i in range(1, 11)]:
        raise AudioBuildError("segments.json must contain S01 through S10 in order")
    previous_end = 0
    for item in segments:
        if not all(isinstance(item.get(field), str) and item[field].strip() for field in (
            "display_subtitle", "tts_phonetic_text"
        )):
            raise AudioBuildError(f"{item.get('id', 'segment')} needs display_subtitle and tts_phonetic_text")
        try:
            start, end = int(item["startFrame"]), int(item["endFrame"])
        except (KeyError, TypeError, ValueError):
            raise AudioBuildError(f"{item.get('id', 'segment')} needs integer startFrame/endFrame") from None
        if not 0 <= start < end <= TOTAL_FRAMES:
            raise AudioBuildError(f"{item['id']} has an invalid frame window")
        if start < previous_end:
            raise AudioBuildError(f"{item['id']} overlaps the preceding segment window")
        previous_end = end
    return segments


def load_events() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not EVENTS_PATH.is_file():
        raise AudioBuildError("sfx_events.json is missing; authored EP06 event anchors are required")
    authored = read_json(EVENTS_PATH)
    if (authored.get("fps"), authored.get("sampleRate"), authored.get("samplesPerFrame")) != (FPS, SAMPLE_RATE, SAMPLES_PER_FRAME):
        raise AudioBuildError("sfx_events.json must use 60 fps, 48 kHz, and 800 samples per frame")
    source_events = authored.get("events")
    if not isinstance(source_events, list) or not source_events:
        raise AudioBuildError("sfx_events.json must contain a non-empty events list")
    events: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    previous_frame = -1
    for source in source_events:
        if not isinstance(source, dict):
            raise AudioBuildError("every sfx event must be an object")
        event_id = source.get("id")
        frame = source.get("frame", source.get("startFrame"))
        if not isinstance(event_id, str) or not event_id or event_id in seen_ids:
            raise AudioBuildError("sfx event IDs must be non-empty and unique")
        if not isinstance(frame, int) or not 0 <= frame < TOTAL_FRAMES or frame <= previous_frame:
            raise AudioBuildError(f"{event_id} needs an in-range frame in authored timeline order")
        if "sampleIndex" in source and source["sampleIndex"] != frame * SAMPLES_PER_FRAME:
            raise AudioBuildError(f"{event_id} has an inconsistent sampleIndex")
        if event_id not in EVENT_PROFILES:
            raise AudioBuildError(f"NEEDS_SOL: no procedural sound profile is defined for authored event {event_id}")
        kind, duration = EVENT_PROFILES[event_id]
        if event_id == "absolute-silence":
            end_frame = source.get("endFrame")
            if (frame, end_frame) != (SILENCE_START_FRAME, SILENCE_END_FRAME):
                raise AudioBuildError("absolute-silence must author the exact [5740, 5760) frame window")
            if source.get("endSampleExclusive", SILENCE_END_SAMPLE) != SILENCE_END_SAMPLE:
                raise AudioBuildError("absolute-silence has an inconsistent exclusive end sample")
        elif "endFrame" in source or "endSampleExclusive" in source:
            raise AudioBuildError(f"only absolute-silence may define an event interval: {event_id}")
        event = {
            "id": event_id,
            "frame": frame,
            "sampleIndex": frame * SAMPLES_PER_FRAME,
            "kind": kind,
            "durationSeconds": duration,
            "description": source.get("description"),
        }
        events.append(event)
        seen_ids.add(event_id)
        previous_frame = frame
    if "absolute-silence" not in seen_ids:
        raise AudioBuildError("sfx_events.json must author the absolute-silence interval")
    if seen_ids != set(EVENT_PROFILES):
        missing = sorted(set(EVENT_PROFILES) - seen_ids)
        raise AudioBuildError(f"sfx_events.json is missing designed EP06 events: {missing}")
    return events, authored


def cue_path_for(segment_id: str) -> Path:
    if PROVIDER_MANIFEST.is_file():
        manifest = read_json(PROVIDER_MANIFEST)
        manifest_segments = manifest.get("segments")
        if not isinstance(manifest_segments, dict):
            raise AudioBuildError("provider-manifest.json must contain a segment map")
        entry = manifest_segments.get(segment_id)
        if not isinstance(entry, dict) or not isinstance(entry.get("cue_path"), str):
            raise AudioBuildError(f"provider-manifest.json has no cue_path entry for {segment_id}")
        candidate = (PROJECT / entry["cue_path"]).resolve()
        if candidate.is_relative_to(PROJECT.resolve()):
            return candidate
        raise AudioBuildError(f"provider manifest cue path escapes the EP06 project for {segment_id}")
    return CUES / f"{segment_id}.wav"


def wav_info(path: Path, *, stereo: bool | None = None) -> dict[str, Any]:
    try:
        with wave.open(str(path), "rb") as wav:
            params = wav.getparams()
            if params.comptype != "NONE" or params.sampwidth != 2 or params.framerate != SAMPLE_RATE:
                raise AudioBuildError(f"{path.name} must be uncompressed 48 kHz PCM16 WAV; got {params}")
            if stereo is True and params.nchannels != 2:
                raise AudioBuildError(f"{path.name} must be stereo; got {params.nchannels} channels")
            if stereo is False and params.nchannels != 1:
                raise AudioBuildError(f"{path.name} cue must be mono; got {params.nchannels} channels")
            raw = wav.readframes(params.nframes)
    except (OSError, wave.Error) as exc:
        raise AudioBuildError(f"cannot read WAV {path}: {exc}") from None
    if params.nframes <= 0 or len(raw) != params.nframes * params.nchannels * 2:
        raise AudioBuildError(f"{path.name} has an empty or physically incomplete PCM payload")
    return {
        "path": path,
        "samples": params.nframes,
        "channels": params.nchannels,
        "seconds": params.nframes / SAMPLE_RATE,
        "sha256": sha256_file(path),
        "pcmSha256": sha256_bytes(raw),
    }


def read_mono_cue(path: Path) -> tuple[array.array, dict[str, Any]]:
    info = wav_info(path, stereo=False)
    with wave.open(str(path), "rb") as wav:
        raw = wav.readframes(info["samples"])
    values = array.array("h")
    values.frombytes(raw)
    if sys.byteorder != "little":
        values.byteswap()
    if len(values) != info["samples"]:
        raise AudioBuildError(f"{path.name} sample count changed during read")
    return values, info


def active_bounds(samples: array.array) -> tuple[int, int, dict[str, Any]]:
    """Estimate measured PCM speech bounds with a sample-resolution sliding RMS."""
    if not samples:
        raise AudioBuildError("cue is empty")
    peak = max(abs(value) for value in samples)
    if peak == 0:
        raise AudioBuildError("cue is digital silence")
    threshold = max(48, round(peak * 0.004))
    window = 240  # 5 ms at 48 kHz; output onset/end remain measured in samples.
    if len(samples) < window:
        window = len(samples)
    power = sum(value * value for value in samples[:window])
    required = window * threshold * threshold
    first = None
    last = None
    for start in range(0, len(samples) - window + 1):
        if power >= required:
            if first is None:
                first = start
            last = start + window
        if start + window < len(samples):
            power += samples[start + window] * samples[start + window] - samples[start] * samples[start]
    if first is None or last is None:
        # Very short, quiet but nonzero cues still receive a PCM-derived bound.
        first = next((i for i, value in enumerate(samples) if abs(value) >= threshold), None)
        last_sample = next((i for i in range(len(samples) - 1, -1, -1) if abs(samples[i]) >= threshold), None)
        if first is None or last_sample is None:
            raise AudioBuildError("cue has no measurable activity above the PCM onset threshold")
        last = last_sample + 1
    return first, last, {"method": "5 ms sliding RMS; threshold=max(48 PCM16, 0.4% of cue peak)", "thresholdPcm16": threshold, "windowSamples": window}


def audit_cues(segments: list[dict[str, Any]] | None) -> int:
    if segments is None:
        print(json.dumps({"status": "pending_segments", "missing": [str(SEGMENTS_PATH.relative_to(WORK))]}, indent=2))
        return 0
    measured, missing = [], []
    for segment in segments:
        path = cue_path_for(segment["id"])
        if not path.is_file():
            missing.append(str(path.relative_to(WORK)))
            continue
        info = wav_info(path, stereo=False)
        with wave.open(str(path), "rb") as wav:
            raw = wav.readframes(info["samples"])
        values = array.array("h")
        values.frombytes(raw)
        if sys.byteorder != "little":
            values.byteswap()
        onset, end, onset_method = active_bounds(values)
        measured.append({
            "id": segment["id"],
            "file": str(path.relative_to(WORK)),
            "samplesAt48k": info["samples"],
            "durationSeconds": round(info["seconds"], 6),
            "estimatedVoiceOnsetOffsetSamples": onset,
            "estimatedVoiceEndOffsetSamplesExclusive": end,
            "onsetMeasurement": onset_method,
            "sha256": info["sha256"],
            "pcmSha256": info["pcmSha256"],
        })
    status = "pending_cues" if missing else "cues_measured"
    print(json.dumps({"status": status, "cueCountMeasured": len(measured), "cues": measured, "missing": missing}, ensure_ascii=False, indent=2))
    return 0


def write_stereo_wav(path: Path, blocks: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        for raw in blocks:
            wav.writeframesraw(raw)


def pcm16(value: float) -> int:
    return max(-32768, min(32767, round(value * 32767.0)))


def cue_timing(segments: list[dict[str, Any]], events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    spans = []
    timing = []
    for segment in segments:
        sid = segment["id"]
        cue_path = cue_path_for(sid)
        if not cue_path.is_file():
            raise AudioBuildError(f"missing local cue for {sid}: {cue_path.relative_to(WORK)}")
        cue, info = read_mono_cue(cue_path)
        onset, active_end, onset_method = active_bounds(cue)
        declared_start = int(segment["startFrame"])
        declared_end = int(segment["endFrame"])
        target_voice_sample = declared_start * SAMPLES_PER_FRAME
        cue_start = target_voice_sample - onset
        cue_end = cue_start + len(cue)
        window_start = declared_start * SAMPLES_PER_FRAME
        window_end = declared_end * SAMPLES_PER_FRAME
        if cue_start < 0:
            raise AudioBuildError(f"NEEDS_SOL: {sid} measured onset offset places its cue before sample zero")
        if cue_end > window_end:
            raise AudioBuildError(
                f"NEEDS_SOL: {sid} has {len(cue)} measured PCM samples; placement ends at sample {cue_end}, "
                f"past its window end {window_end}. No speed change, truncation, or shifted end was applied."
            )
        if cue_start < SILENCE_END_SAMPLE and cue_end > SILENCE_START_SAMPLE:
            raise AudioBuildError(
                f"NEEDS_SOL: {sid} cue PCM overlaps the authored total-master silence "
                f"[{SILENCE_START_SAMPLE}, {SILENCE_END_SAMPLE}); move the cue window or revise this cue"
            )
        active_start_sample = cue_start + onset
        active_end_sample = cue_start + active_end
        spans.append({"segmentId": sid, "startSample": cue_start, "cue": cue, "sampleCount": len(cue), "sourcePath": cue_path})
        timing.append({
            "id": sid,
            "declaredStartFrame": declared_start,
            "declaredEndFrame": declared_end,
            "voiceStartSample": active_start_sample,
            "voiceEndSampleExclusive": active_end_sample,
            "cueStartSample": cue_start,
            "cueEndSampleExclusive": cue_end,
            "cueSamplesAt48k": len(cue),
            "measuredActiveSamples": active_end - onset,
            "onsetOffsetSamplesInCue": onset,
            "activeEndOffsetSamplesInCueExclusive": active_end,
            "placement": "measured active PCM onset aligned to declared startFrame; source cue rate and samples preserved",
            "onsetMeasurement": onset_method,
            "cueFile": str(cue_path.relative_to(WORK)),
            "cueSha256": info["sha256"],
            "cuePcmSha256": info["pcmSha256"],
        })
    spans.sort(key=lambda item: item["startSample"])
    for previous, current in zip(spans, spans[1:]):
        if previous["startSample"] + previous["sampleCount"] > current["startSample"]:
            raise AudioBuildError(f"narration PCM spans overlap: {previous['segmentId']} and {current['segmentId']}")
    return spans, timing


def render_narration(path: Path, spans: list[dict[str, Any]]) -> dict[str, Any]:
    def blocks() -> Any:
        span_index = 0
        for block_start in range(0, TOTAL_SAMPLES, BLOCK_SAMPLES):
            count = min(BLOCK_SAMPLES, TOTAL_SAMPLES - block_start)
            block_end = block_start + count
            mono = array.array("h", [0]) * count
            while span_index < len(spans) and spans[span_index]["startSample"] + spans[span_index]["sampleCount"] <= block_start:
                span_index += 1
            cursor = span_index
            while cursor < len(spans) and spans[cursor]["startSample"] < block_end:
                span = spans[cursor]
                overlap_start = max(block_start, span["startSample"])
                overlap_end = min(block_end, span["startSample"] + span["sampleCount"])
                source_start = overlap_start - span["startSample"]
                target_start = overlap_start - block_start
                mono[target_start:target_start + overlap_end - overlap_start] = span["cue"][source_start:source_start + overlap_end - overlap_start]
                cursor += 1
            stereo = array.array("h", [0]) * (count * 2)
            stereo[0::2] = mono
            stereo[1::2] = mono
            if sys.byteorder != "little":
                stereo.byteswap()
            yield stereo.tobytes()
    write_stereo_wav(path, blocks())
    return validate_stem(path)


def validate_stem(path: Path) -> dict[str, Any]:
    try:
        with wave.open(str(path), "rb") as wav:
            params = wav.getparams()
            raw = wav.readframes(params.nframes)
    except (OSError, wave.Error) as exc:
        raise AudioBuildError(f"cannot read generated stem {path.name}: {exc}") from None
    expected = (SAMPLE_RATE, 2, 2, TOTAL_SAMPLES, "NONE")
    actual = (params.framerate, params.nchannels, params.sampwidth, params.nframes, params.comptype)
    if actual != expected or len(raw) != TOTAL_SAMPLES * 4:
        raise AudioBuildError(f"{path.name} must be exact 48 kHz stereo PCM16, {TOTAL_SAMPLES} samples/ch; got {actual}")
    return {
        "file": str(path.relative_to(WORK)),
        "sha256": sha256_file(path),
        "sampleRate": SAMPLE_RATE,
        "channels": 2,
        "sampleWidthBytes": 2,
        "samplesPerChannel": TOTAL_SAMPLES,
        "durationSeconds": TOTAL_SAMPLES / SAMPLE_RATE,
    }


def render_score(path: Path, events: list[dict[str, Any]]) -> dict[str, Any]:
    """Compose an intimate warm bed that turns threatening, then cathartic."""
    event_frames = {event["id"]: event["frame"] for event in events}
    required_anchors = ("rp-lock", "reward-warp", "gentle-prison", "vault-seal", "sovereign-chord")
    if any(event_id not in event_frames for event_id in required_anchors):
        raise AudioBuildError("sfx_events.json is missing an anchor needed by the EP06 score arc")

    def ramp(frame: float, start_id: str, end_id: str) -> float:
        start, end = event_frames[start_id], event_frames[end_id]
        return min(1.0, max(0.0, (frame - start) / max(1, end - start)))

    def blocks() -> Any:
        edge_fade_samples = round(0.015 * SAMPLE_RATE)
        for block_start in range(0, TOTAL_SAMPLES, BLOCK_SAMPLES):
            count = min(BLOCK_SAMPLES, TOTAL_SAMPLES - block_start)
            stereo = array.array("h")
            for offset in range(count):
                sample = block_start + offset
                t = sample / SAMPLE_RATE
                if SILENCE_START_SAMPLE <= sample < SILENCE_END_SAMPLE:
                    stereo.extend((0, 0))
                    continue
                frame = sample / SAMPLES_PER_FRAME
                threat = ramp(frame, "rp-lock", "reward-warp")
                magenta = ramp(frame, "reward-warp", "gentle-prison")
                catharsis = ramp(frame, "vault-seal", "sovereign-chord")
                breath = 0.88 + 0.12 * math.sin(2 * math.pi * 0.19 * t)
                intimate = (0.58 * math.cos(2 * math.pi * 55.0 * t)
                            + 0.26 * math.cos(2 * math.pi * 82.41 * t + 0.15)
                            + 0.16 * math.cos(2 * math.pi * 110.0 * t + 0.31))
                tension = (0.42 * math.cos(2 * math.pi * 55.0 * t)
                           + 0.25 * math.cos(2 * math.pi * 58.27 * t + 0.3)
                           + 0.19 * math.cos(2 * math.pi * 164.81 * t + 0.55)
                           + 0.14 * math.cos(2 * math.pi * 311.13 * t + 0.72))
                prism = (0.30 * math.cos(2 * math.pi * 220.0 * t)
                         + 0.28 * math.cos(2 * math.pi * 277.18 * t + 0.16)
                         + 0.20 * math.cos(2 * math.pi * 329.63 * t + 0.41)
                         + 0.12 * math.cos(2 * math.pi * 554.37 * t + 0.8))
                resolve = (0.42 * math.cos(2 * math.pi * 130.81 * t)
                           + 0.31 * math.cos(2 * math.pi * 196.0 * t + 0.12)
                           + 0.24 * math.cos(2 * math.pi * 261.63 * t + 0.25)
                           + 0.18 * math.cos(2 * math.pi * 329.63 * t + 0.42)
                           + 0.11 * math.cos(2 * math.pi * 392.0 * t + 0.6))
                bed = intimate * (1.0 - threat) + tension * threat
                bed = bed * (1.0 - magenta) + prism * magenta
                bed = bed * (1.0 - catharsis) + resolve * catharsis
                if SILENCE_START_SAMPLE - edge_fade_samples <= sample < SILENCE_START_SAMPLE:
                    bed *= (SILENCE_START_SAMPLE - sample) / edge_fade_samples
                elif SILENCE_END_SAMPLE <= sample < SILENCE_END_SAMPLE + edge_fade_samples:
                    bed *= (sample - SILENCE_END_SAMPLE) / edge_fade_samples
                left = bed * breath * 0.092
                right = bed * (0.94 + 0.06 * math.cos(2 * math.pi * 0.11 * t)) * 0.092
                stereo.extend((pcm16(left), pcm16(right)))
            if sys.byteorder != "little":
                stereo.byteswap()
            yield stereo.tobytes()
    write_stereo_wav(path, blocks())
    result = validate_stem(path)
    result["design"] = {
        "arc": "intimate heartbeat-colored warmth develops into a detuned predictive threat, opens into a magenta prism, then resolves to a major bowed/organ-like harmonic bed",
        "silenceWindowFrames": [SILENCE_START_FRAME, SILENCE_END_FRAME],
        "silenceWindowSamples": [SILENCE_START_SAMPLE, SILENCE_END_SAMPLE],
        "stereo": "subtle deterministic level motion; no platform-specific processing",
    }
    return result


def event_value(event: dict[str, Any], local_sample: int) -> tuple[float, float]:
    duration = event["durationSeconds"]
    t = local_sample / SAMPLE_RATE
    if t >= duration or event["kind"] == "silence":
        return 0.0, 0.0
    kind = event["kind"]
    attack = min(1.0, 0.15 + t / 0.025)
    release = min(1.0, max(0.0, (duration - t) / min(0.32, duration * 0.24)))
    env = attack * release
    if kind == "cyan":
        left = env * (0.16 * math.cos(2 * math.pi * 1_420.0 * t) + 0.07 * math.cos(2 * math.pi * 2_130.0 * t) + 0.05 * math.cos(2 * math.pi * 220.0 * t))
        right = env * (0.12 * math.cos(2 * math.pi * 1_420.0 * t + 0.4) + 0.08 * math.cos(2 * math.pi * 1_780.0 * t) + 0.04 * math.cos(2 * math.pi * 220.0 * t))
    elif kind in {"heartbeat", "warm_heartbeat"}:
        pulses = math.exp(-((t - 0.015) / 0.070) ** 2) + 0.72 * math.exp(-((t - 0.33) / 0.085) ** 2)
        warmth = 0.22 if kind == "heartbeat" else 0.26
        left = env * pulses * (warmth * math.cos(2 * math.pi * 62.0 * t) + 0.055 * math.cos(2 * math.pi * 132.0 * t))
        right = env * pulses * (warmth * math.cos(2 * math.pi * 62.0 * t + 0.15) + 0.045 * math.cos(2 * math.pi * 132.0 * t))
    elif kind == "lock":
        left = env * (0.17 * math.cos(2 * math.pi * 880.0 * t) + 0.11 * math.cos(2 * math.pi * 1_320.0 * t) + 0.06 * math.cos(2 * math.pi * 110.0 * t))
        right = env * (0.13 * math.cos(2 * math.pi * 880.0 * t + 0.22) + 0.12 * math.cos(2 * math.pi * 1_320.0 * t) + 0.05 * math.cos(2 * math.pi * 110.0 * t))
    elif kind == "amber":
        phase = 2 * math.pi * (180.0 * t + 0.5 * 240.0 * t * t / duration)
        left = env * (0.17 * math.cos(phase) + 0.08 * math.cos(2 * math.pi * 440.0 * t))
        right = env * (0.15 * math.cos(phase + 0.12) + 0.08 * math.cos(2 * math.pi * 554.37 * t))
    elif kind == "glass40":
        left = env * (0.22 * math.cos(2 * math.pi * 40.0 * t) + 0.10 * math.cos(2 * math.pi * 1_568.0 * t) * math.exp(-1.8 * t) + 0.05 * math.cos(2 * math.pi * 2_093.0 * t) * math.exp(-2.4 * t))
        right = env * (0.20 * math.cos(2 * math.pi * 40.0 * t + 0.1) + 0.08 * math.cos(2 * math.pi * 1_568.0 * t + 0.3) * math.exp(-1.8 * t) + 0.06 * math.cos(2 * math.pi * 2_093.0 * t) * math.exp(-2.4 * t))
    elif kind == "converge":
        growth = min(1.0, 0.15 + t / max(0.4, duration * 0.55))
        left = env * growth * (0.15 * math.cos(2 * math.pi * 110.0 * t) + 0.12 * math.cos(2 * math.pi * 220.0 * t) + 0.09 * math.cos(2 * math.pi * 330.0 * t))
        right = env * growth * (0.14 * math.cos(2 * math.pi * 110.0 * t + 0.1) + 0.12 * math.cos(2 * math.pi * 220.0 * t + 0.2) + 0.09 * math.cos(2 * math.pi * 330.0 * t + 0.3))
    elif kind == "magenta":
        phase = 2 * math.pi * (220.0 * t + 0.5 * 180.0 * t * t / duration)
        left = env * (0.14 * math.cos(phase) + 0.13 * math.cos(2 * math.pi * 277.18 * t) + 0.08 * math.cos(2 * math.pi * 554.37 * t))
        right = env * (0.13 * math.cos(phase + 0.5) + 0.15 * math.cos(2 * math.pi * 329.63 * t) + 0.09 * math.cos(2 * math.pi * 659.25 * t))
    elif kind == "metalbox":
        bell = (0.12 * math.cos(2 * math.pi * 440.0 * t) * math.exp(-1.3 * t)
                + 0.09 * math.cos(2 * math.pi * 659.25 * t) * math.exp(-1.8 * t)
                + 0.06 * math.cos(2 * math.pi * 987.77 * t) * math.exp(-2.4 * t))
        notes = (0.08 * math.cos(2 * math.pi * 523.25 * t) + 0.06 * math.cos(2 * math.pi * 783.99 * t + 0.2)) * (0.5 + 0.5 * math.cos(2 * math.pi * 1.2 * t))
        left = env * (bell + notes)
        right = env * (bell * 0.88 + notes * 1.08)
    elif kind == "vault":
        shock = 0.23 * math.cos(2 * math.pi * (68.0 - 20.0 * t / duration) * t) * math.exp(-2.0 * t)
        gold = 0.13 * math.cos(2 * math.pi * 523.25 * t) * math.exp(-1.0 * t) + 0.10 * math.cos(2 * math.pi * 783.99 * t) * math.exp(-1.4 * t)
        left, right = env * (shock + gold), env * (shock * 0.96 + gold * 1.06)
    elif kind == "catharsis":
        swell = min(1.0, 0.12 + t / 0.8) * min(1.0, max(0.0, (duration - t) / 0.7))
        chord = (0.20 * math.cos(2 * math.pi * 130.81 * t)
                 + 0.15 * math.cos(2 * math.pi * 196.0 * t + 0.12)
                 + 0.13 * math.cos(2 * math.pi * 261.63 * t + 0.26)
                 + 0.10 * math.cos(2 * math.pi * 329.63 * t + 0.4)
                 + 0.06 * math.cos(2 * math.pi * 523.25 * t + 0.7))
        left, right = swell * chord, swell * (0.94 * chord + 0.025 * math.cos(2 * math.pi * 392.0 * t))
    else:
        raise AudioBuildError(f"unknown EP06 event sound kind {kind}")
    return left, right


def render_sfx(path: Path, events: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    mapped = [{key: event[key] for key in ("id", "frame", "sampleIndex", "durationSeconds", "description")} | {
        "kind": event["kind"], "silentMarker": event["kind"] == "silence",
    } for event in events]
    def blocks() -> Any:
        event_index = 0
        for block_start in range(0, TOTAL_SAMPLES, BLOCK_SAMPLES):
            count = min(BLOCK_SAMPLES, TOTAL_SAMPLES - block_start)
            left = [0.0] * count
            right = [0.0] * count
            block_end = block_start + count
            while event_index < len(events) and events[event_index]["sampleIndex"] + round(events[event_index]["durationSeconds"] * SAMPLE_RATE) <= block_start:
                event_index += 1
            cursor = event_index
            while cursor < len(events) and events[cursor]["sampleIndex"] < block_end:
                event = events[cursor]
                if event["kind"] == "silence":
                    cursor += 1
                    continue
                event_start = event["sampleIndex"]
                event_end = event_start + round(event["durationSeconds"] * SAMPLE_RATE)
                if event_start < SILENCE_END_SAMPLE and event_end > SILENCE_START_SAMPLE:
                    raise AudioBuildError(f"{event['id']} procedural SFX overlaps authored total-master silence")
                overlap_start, overlap_end = max(block_start, event_start), min(block_end, event_end)
                for absolute in range(overlap_start, overlap_end):
                    offset = absolute - block_start
                    value_l, value_r = event_value(event, absolute - event_start)
                    left[offset] += value_l
                    right[offset] += value_r
                cursor += 1
            stereo = array.array("h")
            for index, (raw_l, raw_r) in enumerate(zip(left, right)):
                sample = block_start + index
                if SILENCE_START_SAMPLE <= sample < SILENCE_END_SAMPLE:
                    stereo.extend((0, 0))
                else:
                    stereo.extend((pcm16(raw_l), pcm16(raw_r)))
            if sys.byteorder != "little":
                stereo.byteswap()
            yield stereo.tobytes()
    write_stereo_wav(path, blocks())
    result = validate_stem(path)
    result["design"] = {
        "synthesis": "deterministic per-event procedural oscillators/noise-free envelopes; authored event anchors are read from sfx_events.json",
        "silenceWindowFrames": [SILENCE_START_FRAME, SILENCE_END_FRAME],
        "silenceWindowSamples": [SILENCE_START_SAMPLE, SILENCE_END_SAMPLE],
        "voiceBand": "crisp cyan/glass partials retained; master loudness/true-peak stage controls aggregate level",
    }
    return result, mapped


def verify_silence_window(path: Path) -> int:
    peak = 0
    with wave.open(str(path), "rb") as wav:
        if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getnframes()) != (SAMPLE_RATE, 2, 2, TOTAL_SAMPLES):
            raise AudioBuildError(f"{path.name} is not an exact-length stereo PCM16 stem")
        wav.setpos(SILENCE_START_SAMPLE)
        remaining = SILENCE_END_SAMPLE - SILENCE_START_SAMPLE
        while remaining:
            count = min(BLOCK_SAMPLES, remaining)
            raw = wav.readframes(count)
            if len(raw) != count * 4:
                raise AudioBuildError(f"{path.name} ended during the authored absolute-silence window")
            values = array.array("h")
            values.frombytes(raw)
            if sys.byteorder != "little":
                values.byteswap()
            peak = max(peak, max((abs(value) for value in values), default=0))
            remaining -= count
    if peak:
        raise AudioBuildError(f"{path.name} must be identically zero in [{SILENCE_START_SAMPLE}, {SILENCE_END_SAMPLE}); peak was {peak}")
    return peak


def run_ffmpeg(args: list[str], label: str) -> str:
    result = subprocess.run(args, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode:
        detail = (result.stderr or result.stdout or "").strip().splitlines()[-8:]
        raise AudioBuildError(f"{label} failed (exit {result.returncode}): {' | '.join(detail)}")
    return result.stderr or ""


def loudnorm_measurements(output: str) -> dict[str, Any]:
    matches = list(re.finditer(r"\{\s*\"input_i\"[\s\S]*?\}", output))
    if not matches:
        raise AudioBuildError("FFmpeg loudnorm returned no first-pass measurement JSON")
    try:
        value = json.loads(matches[-1].group(0))
    except json.JSONDecodeError:
        raise AudioBuildError("FFmpeg loudnorm returned malformed measurement JSON") from None
    needed = ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")
    if any(key not in value for key in needed):
        raise AudioBuildError("FFmpeg loudnorm measurement is incomplete")
    return value


def ebur128(path: Path) -> dict[str, float]:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise AudioBuildError("ffmpeg is required for loudness and true-peak verification")
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


def mix_master(path: Path, stem_paths: list[Path]) -> dict[str, Any]:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise AudioBuildError("ffmpeg is required to build the PCM master")
    audio_inputs = "".join(f"[{index}:a]" for index in range(len(stem_paths)))
    graph = (f"{audio_inputs}amix=inputs={len(stem_paths)}:duration=longest:dropout_transition=0:normalize=0,"
             f"aresample={SAMPLE_RATE},apad,atrim=end_sample={TOTAL_SAMPLES},asetpts=PTS-STARTPTS[mix]")
    args_in = [ffmpeg, "-hide_banner", "-nostats"]
    for stem in stem_paths:
        args_in.extend(("-i", str(stem)))
    first = run_ffmpeg(args_in + [
        "-filter_complex", graph + ";[mix]loudnorm=I=-17:TP=-1.5:LRA=11:print_format=json[out]",
        "-map", "[out]", "-ar", str(SAMPLE_RATE), "-ac", "2", "-f", "null", "-",
    ], "first-pass loudnorm analysis")
    measured = loudnorm_measurements(first)
    # Limit at 4x the delivery rate, then decimate with FFmpeg's compensated
    # resampler. The final PCM silence window is enforced after filtering so
    # interpolation tails cannot leak into the authored dramatic pause.
    second_filter = (graph + ";[mix]loudnorm=I=-17:TP=-1.5:LRA=11"
                     + f":measured_I={measured['input_i']}:measured_TP={measured['input_tp']}"
                     + f":measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}"
                     + f":offset={measured['target_offset']}:linear=true:print_format=json"
                     + f",aresample={SAMPLE_RATE * 4},alimiter=limit=0.841395:attack=5:release=80:level=false:latency=true"
                     + f",aresample={SAMPLE_RATE},apad,atrim=end_sample={TOTAL_SAMPLES},asetpts=PTS-STARTPTS[out]")
    args = list(args_in)
    args.extend(("-filter_complex", second_filter, "-map", "[out]", "-ar", str(SAMPLE_RATE), "-ac", "2",
                 "-c:a", "pcm_s16le", str(path)))
    second = run_ffmpeg(args, "second-pass loudnorm render")
    second_stats = loudnorm_measurements(second)
    enforce_silence_window(path)
    validate_stem(path)
    run_ffmpeg([ffmpeg, "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"], "strict master decode")
    loudness = ebur128(path)
    if not -18.0 <= loudness["integratedLUFS"] <= -16.0:
        raise AudioBuildError(f"master loudness {loudness['integratedLUFS']} LUFS is outside the -17 LUFS target tolerance")
    if loudness["truePeakDBTP"] > -1.2:
        raise AudioBuildError(f"master true peak {loudness['truePeakDBTP']} dBTP exceeds -1.2 dBTP")
    silence_peak = verify_silence_window(path)
    return {
        **validate_stem(path),
        "strictDecode": "passed",
        "loudnormFirstPass": measured,
        "loudnormSecondPass": second_stats,
        "ebur128Final": loudness,
        "loudnormTarget": {"integratedLUFS": -17.0, "truePeakDBTP": -1.5, "acceptanceLUFS": [-18.0, -16.0], "acceptanceTruePeakDBTP": -1.2, "passes": 2},
        "limiter": {"kind": "4x oversampled PCM-domain brickwall via 192 kHz resample + alimiter", "limitLinear": 0.841395, "targetDBTP": -1.5, "makeupLevel": False, "latencyCompensated": True},
        "silenceWindow": {"startSample": SILENCE_START_SAMPLE, "endSampleExclusive": SILENCE_END_SAMPLE, "peakPcm16": silence_peak, "exactZero": True},
        "latencyNote": "The limiter latency flag and compensated resampling preserve the source timeline; final output is trimmed to exactly 5,760,000 samples per channel.",
    }


def enforce_silence_window(path: Path) -> None:
    """Force the authored 20-frame master pause to exact PCM zero after DSP."""
    muted = path.with_name(path.stem + ".silence.tmp.wav")
    try:
        with wave.open(str(path), "rb") as src:
            params = src.getparams()
            if (params.framerate, params.nchannels, params.sampwidth, params.nframes, params.comptype) != (SAMPLE_RATE, 2, 2, TOTAL_SAMPLES, "NONE"):
                raise AudioBuildError("master before silence enforcement has an unexpected WAV format or length")
            raw = src.readframes(TOTAL_SAMPLES)
        if len(raw) != TOTAL_SAMPLES * 4:
            raise AudioBuildError("master PCM payload is incomplete before silence enforcement")
        start = SILENCE_START_SAMPLE * 4
        end = SILENCE_END_SAMPLE * 4
        with wave.open(str(muted), "wb") as dst:
            dst.setnchannels(2)
            dst.setsampwidth(2)
            dst.setframerate(SAMPLE_RATE)
            dst.writeframes(raw[:start] + bytes(end - start) + raw[end:])
        muted.replace(path)
    finally:
        muted.unlink(missing_ok=True)


def source_hashes(segments: list[dict[str, Any]], events: list[dict[str, Any]], event_data: dict[str, Any]) -> dict[str, Any]:
    cues = []
    for segment in segments:
        path = cue_path_for(segment["id"])
        if not path.is_file():
            raise AudioBuildError(f"missing local cue {path.relative_to(WORK)}")
        info = wav_info(path, stereo=False)
        cues.append({"id": segment["id"], "path": str(path.relative_to(WORK)), "sha256": info["sha256"], "samplesAt48k": info["samples"]})
    result = {
        "adaptedScriptMd": sha256_file(PROJECT / "adapted-script.md"),
        "segmentsJson": sha256_file(SEGMENTS_PATH),
        "eventsJson": sha256_file(EVENTS_PATH),
        "eventRenderProfiles": canonical_hash(EVENT_PROFILES),
        "normalizedEvents": canonical_hash(events),
        "providerManifest": sha256_file(PROVIDER_MANIFEST) if PROVIDER_MANIFEST.is_file() else None,
        "cueWavs": cues,
    }
    return result


def check_existing(inputs_hash: str) -> bool:
    output_paths = [AUDIO / f"{name}.wav" for name in ("narration", "score", "sfx", "master")]
    existing = [path for path in output_paths if path.exists()]
    if MANIFEST_PATH.is_file():
        old = read_json(MANIFEST_PATH)
        if old.get("inputSetSha256") != inputs_hash:
            raise AudioBuildError("existing EP06 mix is bound to different inputs; outputs preserved for review")
        outputs = old.get("outputs", {})
        for path in output_paths:
            record = outputs.get(path.stem, {})
            if not path.is_file() or record.get("sha256") != sha256_file(path):
                raise AudioBuildError(f"existing {path.name} differs from its manifest; preserved for review")
        print(json.dumps({"status": "verified_mix_cache_reused", "inputSetSha256": inputs_hash, "outputs": outputs}, ensure_ascii=False, indent=2))
        return True
    if existing:
        raise AudioBuildError("audio outputs exist without a matching mix-manifest.json; no files were overwritten")
    return False


def run_mix(segments: list[dict[str, Any]], events: list[dict[str, Any]], event_data: dict[str, Any]) -> int:
    if not (PROJECT / "adapted-script.md").is_file():
        raise AudioBuildError("project/adapted-script.md is missing")
    hashes = source_hashes(segments, events, event_data)
    input_set_hash = canonical_hash({
        "sourceHashes": hashes,
        "spec": {
            "fps": FPS, "sampleRate": SAMPLE_RATE, "totalSamples": TOTAL_SAMPLES,
            "silenceWindowSamples": [SILENCE_START_SAMPLE, SILENCE_END_SAMPLE],
            "normalization": {"integratedLUFS": -17.0, "maxTruePeakDBTP": -1.2, "limiterOversampling": 4},
        },
    })
    if check_existing(input_set_hash):
        return 0
    AUDIO.mkdir(parents=True, exist_ok=True)
    spans, segment_timing = cue_timing(segments, events)
    temporary = {name: AUDIO / f"{name}.render.tmp.wav" for name in ("narration", "score", "sfx", "master")}
    try:
        outputs: dict[str, Any] = {}
        outputs["narration"] = render_narration(temporary["narration"], spans)
        outputs["score"] = render_score(temporary["score"], events)
        outputs["sfx"], onset_map = render_sfx(temporary["sfx"], events)
        for name in ("narration", "score", "sfx"):
            peak = verify_silence_window(temporary[name])
            if peak:
                raise AudioBuildError(f"{name}.wav is not digitally silent during the authored pause")
        stem_paths = [temporary[name] for name in ("narration", "score", "sfx")]
        outputs["master"] = mix_master(temporary["master"], stem_paths)
        for name, path in temporary.items():
            final_path = AUDIO / f"{name}.wav"
            path.replace(final_path)
            outputs[name]["file"] = str(final_path.relative_to(WORK))
        timing = {
            "durationSeconds": DURATION_SECONDS,
            "fps": FPS,
            "sampleRate": SAMPLE_RATE,
            "samplesPerFrame": SAMPLES_PER_FRAME,
            "samplesPerChannel": TOTAL_SAMPLES,
            "segments": segment_timing,
            "captionTimingMethod": "Pending measured phrase allocation; no ASR or word alignment is used.",
            "sfxEvents": onset_map,
            "absoluteSilence": {
                "startFrame": SILENCE_START_FRAME, "endFrameExclusive": SILENCE_END_FRAME,
                "startSample": SILENCE_START_SAMPLE, "endSampleExclusive": SILENCE_END_SAMPLE,
                "samplesZeroInAllStemsAndMaster": True,
            },
            "sourceHashes": hashes,
        }
        settings = {
            "version": 1,
            "durationSeconds": DURATION_SECONDS,
            "fps": FPS,
            "sampleRate": SAMPLE_RATE,
            "samplesPerFrame": SAMPLES_PER_FRAME,
            "samplesPerChannel": TOTAL_SAMPLES,
            "channels": 2,
            "blockSamples": BLOCK_SAMPLES,
            "scoreDesign": outputs["score"]["design"],
            "sfxDesign": outputs["sfx"]["design"],
            "sfxOnsets": onset_map,
            "loudnormTarget": outputs["master"]["loudnormTarget"],
            "limiter": outputs["master"]["limiter"],
            "absoluteSilence": timing["absoluteSilence"],
            "sourceHashes": hashes,
            "outputs": outputs,
        }
        manifest = {
            "version": 1,
            "status": "built",
            "inputSetSha256": input_set_hash,
            "sourceHashes": hashes,
            "outputs": outputs,
            "eventOnsets": onset_map,
            "absoluteSilence": timing["absoluteSilence"],
            "mixSettings": str(SETTINGS_PATH.relative_to(WORK)),
            "audioTiming": str(TIMING_PATH.relative_to(WORK)),
        }
        write_json(TIMING_PATH, timing)
        write_json(SETTINGS_PATH, settings)
        write_json(MANIFEST_PATH, manifest)
        print(json.dumps({"status": "mix_complete", "master": outputs["master"], "eventOnsets": onset_map, "absoluteSilence": timing["absoluteSilence"]}, ensure_ascii=False, indent=2))
        return 0
    finally:
        for path in temporary.values():
            path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--mix", action="store_true", help="build stems and exact PCM master from local cue WAVs")
    mode.add_argument("--audit", action="store_true", help="read-only cue inventory and measured PCM sample counts")
    args = parser.parse_args()
    try:
        if not SEGMENTS_PATH.is_file() and args.audit:
            return audit_cues(None)
        segments = load_segments()
        events, event_data = load_events()
        if args.audit:
            return audit_cues(segments)
        return run_mix(segments, events, event_data)
    except (AudioBuildError, OSError, ValueError, wave.Error, OverflowError) as exc:
        print(f"build_audio.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
