#!/usr/bin/env python3
"""Build EP08 narration, procedural score/SFX, measured timing, and PCM master."""

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
MIX_SETTINGS_PATH = AUDIO / "mix-settings.json"
MIX_MANIFEST_PATH = AUDIO / "mix-manifest.json"

FPS = 60
SAMPLE_RATE = 48_000
SAMPLES_PER_FRAME = 800
DURATION_SECONDS = 120
TOTAL_FRAMES = FPS * DURATION_SECONDS
TOTAL_SAMPLES = SAMPLE_RATE * DURATION_SECONDS
BLOCK_SAMPLES = 24_000
SILENCE_START_FRAME = 5_880
SILENCE_END_FRAME = 5_910
SILENCE_START_SAMPLE = SILENCE_START_FRAME * SAMPLES_PER_FRAME
SILENCE_END_SAMPLE = SILENCE_END_FRAME * SAMPLES_PER_FRAME
EXPECTED_IDS = [f"S{i:02d}" for i in range(1, 11)]

SETTINGS = {
    "provider": "Aliyun Bailian",
    "model_selection": "active profile default",
    "effective_model": "cosyvoice-v3-flash",
    "voice": "longtian_v3",
    "rate": 1.0,
    "format": "wav",
    "sample_rate": 24_000,
}

EVENT_PROFILES = {
    "grid_snap": ("metal_snap", 0.62),
    "stamp": ("industrial_stamp", 0.58),
    "sub_sweep": ("sub_sweep_38hz", 1.70),
    "growth": ("fluid_growth", 2.60),
    "stress_sing": ("harmonic_stress", 1.75),
    "gold_lock": ("gold_lock", 0.96),
    "chord": ("folded_chord", 6.20),
    "titanium_drop": ("titanium_drop", 1.90),
    "ticker": ("metal_ticker", 3.20),
}
SCORE_SCENE_FRAMES = [120, 900, 1350, 2100, 2760, 3900, 4680, 5910, 6480]


class AudioBuildError(RuntimeError):
    pass


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha_bytes(encoded)


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AudioBuildError(f"cannot read {label}: {exc}") from None
    if not isinstance(value, dict):
        raise AudioBuildError(f"{label} must contain a JSON object")
    return value


def load_segments() -> list[dict[str, Any]]:
    data = read_json(SEGMENTS_PATH, "segments.json")
    if (data.get("fps"), data.get("duration_seconds"), data.get("sample_rate")) != (FPS, DURATION_SECONDS, SAMPLE_RATE):
        raise AudioBuildError("segments.json must declare 60 fps, 120 seconds, and 48 kHz")
    segments = data.get("segments")
    if not isinstance(segments, list) or [item.get("id") for item in segments] != EXPECTED_IDS:
        raise AudioBuildError("segments.json must contain exactly S01 through S10 in order")
    prior_end = 0
    for item in segments:
        for field in ("display_subtitle", "tts_phonetic_text"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise AudioBuildError(f"{item.get('id', 'segment')} needs {field}")
        start, end = item.get("startFrame"), item.get("endFrame")
        if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= TOTAL_FRAMES:
            raise AudioBuildError(f"{item['id']} has invalid frame bounds")
        if start < prior_end:
            raise AudioBuildError(f"{item['id']} overlaps the preceding declared segment window")
        if not isinstance(item.get("chunks"), list) or not item["chunks"] or any(not isinstance(chunk, str) or not chunk.strip() for chunk in item["chunks"]):
            raise AudioBuildError(f"{item['id']} needs non-empty original caption chunks")
        prior_end = end
    return segments


def load_events() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    authored = read_json(EVENTS_PATH, "sfx_events.json")
    if (authored.get("fps"), authored.get("sampleRate")) != (FPS, SAMPLE_RATE):
        raise AudioBuildError("sfx_events.json must use 60 fps and 48 kHz")
    if authored.get("absoluteSilence") != [SILENCE_START_FRAME, SILENCE_END_FRAME]:
        raise AudioBuildError("sfx_events.json absoluteSilence does not match the required [5880,5910) frames")
    source = authored.get("events")
    if not isinstance(source, list) or [event.get("id") for event in source] != list(EVENT_PROFILES):
        raise AudioBuildError("sfx_events.json event IDs/order differ from the authorized EP08 sound design")
    events = []
    previous = -1
    for item in source:
        frame = item.get("frame")
        if not isinstance(frame, int) or not 0 <= frame < TOTAL_FRAMES or frame <= previous:
            raise AudioBuildError(f"{item.get('id', 'event')} has an invalid or out-of-order frame")
        sample = frame * SAMPLES_PER_FRAME
        if item.get("sampleIndex") != sample:
            raise AudioBuildError(f"{item['id']} sampleIndex does not match its frame")
        if item["id"] not in EVENT_PROFILES:
            raise AudioBuildError(f"NEEDS_SOL: no procedural profile exists for {item['id']}")
        kind, duration = EVENT_PROFILES[item["id"]]
        if frame < SILENCE_END_FRAME and sample + round(duration * SAMPLE_RATE) > SILENCE_START_SAMPLE:
            raise AudioBuildError(f"{item['id']} SFX would overlap the absolute silence interval")
        events.append({
            "id": item["id"], "frame": frame, "sampleIndex": sample,
            "durationSeconds": duration, "kind": kind,
            "description": item.get("description"),
        })
        previous = frame
    return events, authored


def read_cue(path: Path) -> tuple[array.array, dict[str, Any]]:
    try:
        with wave.open(str(path), "rb") as wav:
            params = wav.getparams()
            if (params.framerate, params.nchannels, params.sampwidth, params.comptype) != (SAMPLE_RATE, 1, 2, "NONE"):
                raise AudioBuildError(f"{path.name} must be mono 48 kHz PCM16; got {params}")
            raw = wav.readframes(params.nframes)
    except (OSError, wave.Error) as exc:
        raise AudioBuildError(f"cannot read cue {path}: {exc}") from None
    if params.nframes <= 0 or len(raw) != params.nframes * 2:
        raise AudioBuildError(f"{path.name} has an empty or incomplete PCM payload")
    values = array.array("h")
    values.frombytes(raw)
    if sys.byteorder != "little":
        values.byteswap()
    return values, {"samples": params.nframes, "seconds": params.nframes / SAMPLE_RATE, "sha256": sha_file(path), "pcmSha256": sha_bytes(raw)}


def active_bounds(samples: array.array) -> tuple[int, int, dict[str, Any]]:
    peak = max((abs(value) for value in samples), default=0)
    if not peak:
        raise AudioBuildError("cue is digital silence")
    threshold = max(48, round(peak * 0.004))
    window = min(240, len(samples))
    required = window * threshold * threshold
    power = sum(value * value for value in samples[:window])
    first = last = None
    for start in range(0, len(samples) - window + 1):
        if power >= required:
            if first is None:
                first = start
            last = start + window
        if start + window < len(samples):
            power += samples[start + window] * samples[start + window] - samples[start] * samples[start]
    if first is None or last is None:
        first = next((i for i, value in enumerate(samples) if abs(value) >= threshold), None)
        last_index = next((i for i in range(len(samples) - 1, -1, -1) if abs(samples[i]) >= threshold), None)
        if first is None or last_index is None:
            raise AudioBuildError("cue has no measurable PCM activity above onset threshold")
        last = last_index + 1
    return first, last, {
        "method": "5 ms sliding RMS; threshold=max(48 PCM16, 0.4% of cue peak)",
        "thresholdPcm16": threshold, "windowSamples": window,
    }


def cue_inventory(segments: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, array.array]]:
    manifest = read_json(PROVIDER_MANIFEST, "provider-manifest.json")
    if manifest.get("settings") != SETTINGS or not isinstance(manifest.get("segments"), dict):
        raise AudioBuildError("provider manifest settings differ from authorized EP08 TTS")
    cues: dict[str, array.array] = {}
    inventory = []
    for segment in segments:
        sid = segment["id"]
        entry = manifest["segments"].get(sid)
        if not isinstance(entry, dict):
            raise AudioBuildError(f"provider manifest has no entry for {sid}")
        expected_key = hashlib.sha256(json.dumps({
            "text": segment["tts_phonetic_text"], "settings": SETTINGS,
        }, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
        if entry.get("cache_key") != expected_key or entry.get("settings") != SETTINGS:
            raise AudioBuildError(f"{sid} cue hash key/settings do not match the prepared text")
        if entry.get("effective_model") != [SETTINGS["effective_model"]] or entry.get("effective_voice") != [SETTINGS["voice"]]:
            raise AudioBuildError(f"NEEDS_SOL: {sid} recorded model or voice differs from the authorized selection")
        relative = entry.get("cue_path")
        if not isinstance(relative, str):
            raise AudioBuildError(f"{sid} has no cue path")
        cue_path = (PROJECT / relative).resolve()
        if not cue_path.is_relative_to(PROJECT.resolve()) or not cue_path.is_file():
            raise AudioBuildError(f"{sid} cue path is missing or outside the project")
        if entry.get("cue_sha256") != sha_file(cue_path):
            raise AudioBuildError(f"{sid} cue SHA-256 does not match its manifest")
        cue, info = read_cue(cue_path)
        onset, active_end, measure = active_bounds(cue)
        cues[sid] = cue
        inventory.append({
            "id": sid, "cueFile": str(cue_path.relative_to(WORK)),
            "cueSamplesAt48k": len(cue), "durationSeconds": round(len(cue) / SAMPLE_RATE, 6),
            "cueSha256": info["sha256"], "cuePcmSha256": info["pcmSha256"],
            "activeOnsetOffsetSamples": onset, "activeEndOffsetSamplesExclusive": active_end,
            "activeBoundsMethod": measure,
        })
    return inventory, cues


def cue_timing(segments: list[dict[str, Any]], cues: dict[str, array.array]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    spans = []
    measured = []
    for segment in segments:
        sid = segment["id"]
        cue = cues[sid]
        onset, active_end, method = active_bounds(cue)
        voice_start = segment["startFrame"] * SAMPLES_PER_FRAME
        cue_start = voice_start - onset
        cue_end = cue_start + len(cue)
        normal_end = segment["endFrame"] * SAMPLES_PER_FRAME
        hard_end = SILENCE_START_SAMPLE if sid == "S08" else normal_end
        if cue_start < 0:
            raise AudioBuildError(f"NEEDS_SOL: {sid} measured onset would place the complete cue before sample zero")
        if cue_end > hard_end:
            boundary = "the 98.0s absolute-silence boundary" if sid == "S08" else f"its declared end at sample {hard_end}"
            raise AudioBuildError(
                f"NEEDS_SOL: {sid} complete PCM ends at sample {cue_end}, beyond {boundary}; "
                "the cue was not shifted, accelerated, truncated, or stretched"
            )
        if cue_start < SILENCE_END_SAMPLE and cue_end > SILENCE_START_SAMPLE:
            raise AudioBuildError(f"NEEDS_SOL: {sid} complete PCM overlaps the authored absolute-silence interval")
        span = {
            "segmentId": sid, "startSample": cue_start, "cue": cue,
            "sampleCount": len(cue), "cuePath": inventory_path(sid),
        }
        spans.append(span)
        measured.append({
            "id": sid,
            "declaredStartFrame": segment["startFrame"],
            "declaredEndFrame": segment["endFrame"],
            "voiceStartSample": cue_start + onset,
            "voiceEndSampleExclusive": cue_start + active_end,
            "cueStartSample": cue_start,
            "cueEndSampleExclusive": cue_end,
            "cueSamplesAt48k": len(cue),
            "measuredActiveSamples": active_end - onset,
            "onsetOffsetSamplesInCue": onset,
            "activeEndOffsetSamplesInCueExclusive": active_end,
            "placement": "measured active PCM onset aligned to the declared start frame; complete source cue preserved",
            "onsetMeasurement": method,
        })
    spans.sort(key=lambda item: item["startSample"])
    for previous, current in zip(spans, spans[1:]):
        if previous["startSample"] + previous["sampleCount"] > current["startSample"]:
            raise AudioBuildError(f"NEEDS_SOL: complete narration PCM overlaps between {previous['segmentId']} and {current['segmentId']}")
    return spans, measured


def inventory_path(segment_id: str) -> str:
    manifest = read_json(PROVIDER_MANIFEST, "provider-manifest.json")
    return str(manifest["segments"][segment_id]["cue_path"])


def pcm16(value: float) -> int:
    return max(-32768, min(32767, round(value * 32767.0)))


def write_stereo(path: Path, block_iter: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        for block in block_iter:
            wav.writeframesraw(block)


def render_narration(path: Path, spans: list[dict[str, Any]]) -> dict[str, Any]:
    def blocks():
        cursor = 0
        for block_start in range(0, TOTAL_SAMPLES, BLOCK_SAMPLES):
            count = min(BLOCK_SAMPLES, TOTAL_SAMPLES - block_start)
            block_end = block_start + count
            mono = array.array("h", [0]) * count
            while cursor < len(spans) and spans[cursor]["startSample"] + spans[cursor]["sampleCount"] <= block_start:
                cursor += 1
            index = cursor
            while index < len(spans) and spans[index]["startSample"] < block_end:
                span = spans[index]
                overlap_start = max(block_start, span["startSample"])
                overlap_end = min(block_end, span["startSample"] + span["sampleCount"])
                source_start = overlap_start - span["startSample"]
                target_start = overlap_start - block_start
                mono[target_start:target_start + overlap_end - overlap_start] = span["cue"][source_start:source_start + overlap_end - overlap_start]
                index += 1
            stereo = array.array("h", [0]) * (count * 2)
            stereo[0::2] = mono
            stereo[1::2] = mono
            if sys.byteorder != "little":
                stereo.byteswap()
            yield stereo.tobytes()
    write_stereo(path, blocks())
    return validate_wav(path, stereo=True)


def smooth(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def ramp(frame: float, start: int, end: int) -> float:
    return smooth((frame - start) / max(1, end - start))


def score_value(sample: int) -> tuple[float, float]:
    frame = sample / SAMPLES_PER_FRAME
    time = sample / SAMPLE_RATE
    intro = 1.0 - ramp(frame, 900, 1350)
    sweep = ramp(frame, 1350, 2100) * (1.0 - ramp(frame, 2100, 2760))
    growth = ramp(frame, 2100, 3900) * (1.0 - 0.12 * ramp(frame, 4680, 5910))
    shimmer = ramp(frame, 2760, 3900)
    lock = ramp(frame, 3900, 4680) * (1.0 - ramp(frame, 5910, 6480))
    resolved = ramp(frame, 4680, 5910)
    after = ramp(frame, 5910, 6480)
    ticker = ramp(frame, 6480, 7200)
    drone = 0.36 * math.sin(2.0 * math.pi * 55.0 * time) + 0.18 * math.sin(2.0 * math.pi * 82.41 * time + 0.2)
    sweep_time = max(0.0, time - 1350 / FPS)
    sweep_duration = (2100 - 1350) / FPS
    sweep_phase = 2.0 * math.pi * (38.0 * time + (19.0 / sweep_duration) * min(sweep_time, sweep_duration) ** 2)
    rising = math.sin(sweep_phase) + 0.32 * math.sin(2.0 * sweep_phase + 0.16)
    fluid = (0.42 * math.sin(2.0 * math.pi * 110.0 * time)
             + 0.31 * math.sin(2.0 * math.pi * 164.81 * time + 0.28)
             + 0.22 * math.sin(2.0 * math.pi * (220.0 + 12.0 * math.sin(2.0 * math.pi * 0.07 * time)) * time + 0.5))
    metal = (0.35 * math.sin(2.0 * math.pi * 311.13 * time)
             + 0.25 * math.sin(2.0 * math.pi * 466.16 * time + 0.4)
             + 0.18 * math.sin(2.0 * math.pi * 622.25 * time + 0.8))
    lock_tone = (0.45 * math.sin(2.0 * math.pi * 196.0 * time)
                 + 0.30 * math.sin(2.0 * math.pi * 392.0 * time + 0.35)
                 + 0.18 * math.sin(2.0 * math.pi * 784.0 * time + 0.7))
    major = (0.38 * math.sin(2.0 * math.pi * 130.81 * time)
             + 0.28 * math.sin(2.0 * math.pi * 196.0 * time + 0.18)
             + 0.24 * math.sin(2.0 * math.pi * 261.63 * time + 0.31)
             + 0.18 * math.sin(2.0 * math.pi * 329.63 * time + 0.52)
             + 0.10 * math.sin(2.0 * math.pi * 523.25 * time + 0.78))
    after_tone = 0.42 * math.sin(2.0 * math.pi * 73.42 * time) + 0.24 * math.sin(2.0 * math.pi * 293.66 * time + 0.4)
    tick_bed = math.sin(2.0 * math.pi * 6.0 * time) * (0.65 + 0.35 * math.sin(2.0 * math.pi * 293.66 * time))
    value = 0.016 * intro * drone + 0.014 * sweep * rising + 0.026 * growth * fluid
    value += 0.010 * shimmer * metal + 0.012 * lock * lock_tone + 0.021 * resolved * major
    value += 0.009 * after * after_tone + 0.003 * ticker * tick_bed
    pan = 0.10 * math.sin(2.0 * math.pi * 0.09 * time)
    return value * (0.96 - pan), value * (0.96 + pan)


def render_score(path: Path) -> dict[str, Any]:
    fade_samples = round(0.015 * SAMPLE_RATE)
    def blocks():
        for block_start in range(0, TOTAL_SAMPLES, BLOCK_SAMPLES):
            count = min(BLOCK_SAMPLES, TOTAL_SAMPLES - block_start)
            stereo = array.array("h")
            for offset in range(count):
                sample = block_start + offset
                if SILENCE_START_SAMPLE <= sample < SILENCE_END_SAMPLE:
                    stereo.extend((0, 0))
                    continue
                gain = 1.0
                if SILENCE_START_SAMPLE - fade_samples <= sample < SILENCE_START_SAMPLE:
                    gain = (SILENCE_START_SAMPLE - sample) / fade_samples
                elif SILENCE_END_SAMPLE <= sample < SILENCE_END_SAMPLE + fade_samples:
                    gain = (sample - SILENCE_END_SAMPLE) / fade_samples
                left, right = score_value(sample)
                stereo.extend((pcm16(left * gain), pcm16(right * gain)))
            if sys.byteorder != "little":
                stereo.byteswap()
            yield stereo.tobytes()
    write_stereo(path, blocks())
    return validate_wav(path, stereo=True) | {
        "design": {
            "description": "Procedural atmospheric metallic score: sparse geometric opening, a 38 Hz sweep, fluid growth, harmonic stress, metallic lock, resolved chord, then titanium/ticker after the absolute pause.",
            "sceneChangeFrames": SCORE_SCENE_FRAMES,
            "silenceWindowFrames": [SILENCE_START_FRAME, SILENCE_END_FRAME],
            "stereo": "deterministic subtle pan; same shared master for both platforms",
        }
    }


def event_value(kind: str, t: float, duration: float) -> tuple[float, float]:
    progress = t / duration
    attack = smooth(min(1.0, t / min(0.035, duration * 0.15)))
    release = min(1.0, max(0.0, (duration - t) / min(0.35, duration * 0.25)))
    env = attack * release
    if kind == "metal_snap":
        body = 0.22 * math.sin(2 * math.pi * 128.0 * t) * math.exp(-6.0 * t)
        ring = 0.13 * math.sin(2 * math.pi * 1_780.0 * t) * math.exp(-5.2 * t) + 0.08 * math.sin(2 * math.pi * 2_730.0 * t) * math.exp(-7.0 * t)
        left, right = env * (body + ring), env * (body * 0.92 + ring * 0.9)
    elif kind == "industrial_stamp":
        thud = 0.25 * math.sin(2 * math.pi * (92.0 - 28.0 * progress) * t) * math.exp(-4.2 * t)
        clang = 0.11 * math.sin(2 * math.pi * 523.25 * t) * math.exp(-3.8 * t) + 0.07 * math.sin(2 * math.pi * 1_046.5 * t) * math.exp(-6.2 * t)
        left, right = env * (thud + clang), env * (thud * 0.96 + clang * 1.04)
    elif kind == "sub_sweep_38hz":
        phase = 2 * math.pi * (38.0 * t + 0.5 * 54.0 * t * t / duration)
        left = env * (0.21 * math.sin(phase) + 0.07 * math.sin(2 * phase + 0.12))
        right = env * (0.20 * math.sin(phase + 0.08) + 0.07 * math.sin(2 * phase + 0.34))
    elif kind == "fluid_growth":
        phase = 2 * math.pi * (92.0 * t + 0.5 * 250.0 * t * t / duration)
        wave = 0.15 * math.sin(phase) + 0.10 * math.sin(2 * math.pi * 220.0 * t + 0.3) + 0.07 * math.sin(2 * math.pi * 330.0 * t + 0.65)
        left, right = env * wave, env * (0.94 * wave + 0.025 * math.sin(2 * math.pi * 440.0 * t))
    elif kind == "harmonic_stress":
        beat = 0.5 + 0.5 * math.sin(2 * math.pi * 1.7 * t)
        wave = beat * (0.16 * math.sin(2 * math.pi * 220.0 * t) + 0.11 * math.sin(2 * math.pi * 329.63 * t + 0.2) + 0.08 * math.sin(2 * math.pi * 493.88 * t + 0.5))
        left, right = env * wave, env * (0.92 * wave + 0.025 * math.sin(2 * math.pi * 659.25 * t + 0.3))
    elif kind == "gold_lock":
        ring = (0.19 * math.sin(2 * math.pi * 440.0 * t) * math.exp(-2.2 * t)
                + 0.13 * math.sin(2 * math.pi * 659.25 * t + 0.25) * math.exp(-2.8 * t)
                + 0.09 * math.sin(2 * math.pi * 987.77 * t + 0.6) * math.exp(-3.4 * t))
        left, right = env * ring, env * (0.90 * ring + 0.025 * math.sin(2 * math.pi * 1_319.0 * t))
    elif kind == "folded_chord":
        swell = smooth(min(1.0, t / 0.9))
        chord = (0.17 * math.sin(2 * math.pi * 130.81 * t)
                 + 0.14 * math.sin(2 * math.pi * 196.0 * t + 0.15)
                 + 0.12 * math.sin(2 * math.pi * 261.63 * t + 0.28)
                 + 0.09 * math.sin(2 * math.pi * 329.63 * t + 0.42)
                 + 0.06 * math.sin(2 * math.pi * 523.25 * t + 0.68))
        left, right = env * swell * chord, env * swell * (0.92 * chord + 0.02 * math.sin(2 * math.pi * 392.0 * t))
    elif kind == "titanium_drop":
        phase = 2 * math.pi * (214.0 * t - 0.5 * 156.0 * t * t / duration)
        clang = 0.17 * math.sin(phase) * math.exp(-2.0 * t) + 0.11 * math.sin(2 * phase + 0.3) * math.exp(-3.1 * t)
        low = 0.19 * math.sin(2 * math.pi * (72.0 - 26.0 * progress) * t) * math.exp(-2.3 * t)
        left, right = env * (clang + low), env * (0.92 * clang + 1.04 * low)
    elif kind == "metal_ticker":
        phase = (t % 0.40)
        click = math.exp(-((phase - 0.018) / 0.012) ** 2) + 0.58 * math.exp(-((phase - 0.045) / 0.015) ** 2)
        tone = 0.12 * math.sin(2 * math.pi * 1_340.0 * t) + 0.07 * math.sin(2 * math.pi * 2_010.0 * t + 0.2)
        left, right = env * click * tone, env * click * (0.9 * tone + 0.025 * math.sin(2 * math.pi * 2_680.0 * t))
    else:
        raise AudioBuildError(f"unknown procedural SFX kind {kind}")
    return left, right


def render_sfx(path: Path, events: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    left = array.array("h", [0]) * TOTAL_SAMPLES
    right = array.array("h", [0]) * TOTAL_SAMPLES
    onsets = []
    for event in events:
        start = event["sampleIndex"]
        count = min(round(event["durationSeconds"] * SAMPLE_RATE), TOTAL_SAMPLES - start)
        if start < SILENCE_END_SAMPLE and start + count > SILENCE_START_SAMPLE:
            raise AudioBuildError(f"{event['id']} overlaps authored silence")
        for offset in range(count):
            lval, rval = event_value(event["kind"], offset / SAMPLE_RATE, event["durationSeconds"])
            li, ri = start + offset, start + offset
            left[li] = max(-32768, min(32767, left[li] + pcm16(lval)))
            right[ri] = max(-32768, min(32767, right[ri] + pcm16(rval)))
        onsets.append({
            "id": event["id"], "frame": event["frame"], "sampleIndex": start,
            "durationSeconds": event["durationSeconds"], "kind": event["kind"],
            "description": event["description"],
        })
    def blocks():
        for start in range(0, TOTAL_SAMPLES, BLOCK_SAMPLES):
            end = min(TOTAL_SAMPLES, start + BLOCK_SAMPLES)
            if start < SILENCE_END_SAMPLE and end > SILENCE_START_SAMPLE:
                # The interval is an authored all-track digital zero, regardless of other events.
                for sample in range(max(start, SILENCE_START_SAMPLE), min(end, SILENCE_END_SAMPLE)):
                    left[sample] = 0
                    right[sample] = 0
            stereo = array.array("h")
            for idx in range(start, end):
                stereo.extend((left[idx], right[idx]))
            if sys.byteorder != "little":
                stereo.byteswap()
            yield stereo.tobytes()
    write_stereo(path, blocks())
    info = validate_wav(path, stereo=True)
    info["design"] = {
        "description": "Procedural metallic grid/stamp, 38 Hz sub sweep, fluid growth, resonant harmonics, gold lock, resolved chord, titanium drop, and ticking transition.",
        "events": onsets,
        "silenceWindowFrames": [SILENCE_START_FRAME, SILENCE_END_FRAME],
    }
    return info, onsets


def validate_wav(path: Path, *, stereo: bool) -> dict[str, Any]:
    try:
        with wave.open(str(path), "rb") as wav:
            params = wav.getparams()
            expected_channels = 2 if stereo else 1
            actual = (params.framerate, params.nchannels, params.sampwidth, params.nframes, params.comptype)
            expected = (SAMPLE_RATE, expected_channels, 2, TOTAL_SAMPLES, "NONE")
            if actual != expected:
                raise AudioBuildError(f"{path.name} must be {expected}; got {actual}")
            raw = wav.readframes(params.nframes)
    except (OSError, wave.Error) as exc:
        raise AudioBuildError(f"cannot read WAV {path}: {exc}") from None
    if len(raw) != TOTAL_SAMPLES * expected_channels * 2:
        raise AudioBuildError(f"{path.name} PCM payload is incomplete")
    values = array.array("h")
    values.frombytes(raw)
    if sys.byteorder != "little":
        values.byteswap()
    peak = max((abs(value) for value in values), default=0)
    return {
        "file": str(path.relative_to(WORK)), "sha256": sha_file(path), "pcmSha256": sha_bytes(raw),
        "sampleRate": SAMPLE_RATE, "channels": expected_channels,
        "sampleWidthBytes": 2, "samplesPerChannel": TOTAL_SAMPLES,
        "durationSeconds": TOTAL_SAMPLES / SAMPLE_RATE, "samplePeakPcm16": peak,
    }


def verify_silence(path: Path) -> int:
    with wave.open(str(path), "rb") as wav:
        params = wav.getparams()
        if (params.framerate, params.nchannels, params.sampwidth, params.nframes, params.comptype) != (SAMPLE_RATE, 2, 2, TOTAL_SAMPLES, "NONE"):
            raise AudioBuildError(f"{path.name} has unexpected format before silence verification")
        wav.setpos(SILENCE_START_SAMPLE)
        raw = wav.readframes(SILENCE_END_SAMPLE - SILENCE_START_SAMPLE)
    values = array.array("h")
    values.frombytes(raw)
    peak = max((abs(value) for value in values), default=0)
    if peak:
        raise AudioBuildError(f"{path.name} is not exact digital silence over [5880,5910); PCM16 peak={peak}")
    return peak


def enforce_master_silence(path: Path) -> None:
    replacement = path.with_name(path.stem + ".silence.tmp.wav")
    try:
        with wave.open(str(path), "rb") as src:
            params = src.getparams()
            if (params.framerate, params.nchannels, params.sampwidth, params.nframes, params.comptype) != (SAMPLE_RATE, 2, 2, TOTAL_SAMPLES, "NONE"):
                raise AudioBuildError("normalized master has unexpected PCM format or duration")
            raw = src.readframes(TOTAL_SAMPLES)
        start, end = SILENCE_START_SAMPLE * 4, SILENCE_END_SAMPLE * 4
        with wave.open(str(replacement), "wb") as dst:
            dst.setnchannels(2)
            dst.setsampwidth(2)
            dst.setframerate(SAMPLE_RATE)
            dst.writeframes(raw[:start] + bytes(end - start) + raw[end:])
        replacement.replace(path)
    finally:
        replacement.unlink(missing_ok=True)


def run_ffmpeg(args: list[str], label: str) -> str:
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if result.returncode:
        detail = (result.stderr or result.stdout or "").strip().splitlines()[-8:]
        raise AudioBuildError(f"{label} failed (exit {result.returncode}): {' | '.join(detail)}")
    return result.stderr or ""


def parse_loudnorm(text: str) -> dict[str, Any]:
    matches = list(re.finditer(r"\{\s*\"input_i\"[\s\S]*?\}", text))
    if not matches:
        raise AudioBuildError("FFmpeg loudnorm did not return measurement JSON")
    try:
        value = json.loads(matches[-1].group(0))
    except json.JSONDecodeError:
        raise AudioBuildError("FFmpeg loudnorm returned malformed measurement JSON") from None
    required = ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")
    if any(key not in value for key in required):
        raise AudioBuildError("FFmpeg loudnorm measurement is incomplete")
    return value


def ebur128(path: Path) -> dict[str, float]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise AudioBuildError("ffmpeg is required for final LUFS/true-peak measurement")
    text = run_ffmpeg([ffmpeg, "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"], "EBU R128 verification")
    integrated = re.search(r"^\s*I:\s*(-?\d+(?:\.\d+)?)\s+LUFS\s*$", text, re.MULTILINE)
    true_peak = re.search(r"^\s*True peak:\s*(-?\d+(?:\.\d+)?)\s+dBTP\s*$", text, re.MULTILINE)
    if true_peak is None:
        true_peak = re.search(r"True peak:\s*\n\s*Peak:\s*(-?\d+(?:\.\d+)?)\s+dBFS", text)
    if integrated is None or true_peak is None:
        raise AudioBuildError("FFmpeg ebur128 did not report integrated LUFS and true peak")
    return {"integratedLUFS": float(integrated.group(1)), "truePeakDBTP": float(true_peak.group(1))}


def mix_master(path: Path, stems: list[Path]) -> dict[str, Any]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise AudioBuildError("ffmpeg is required to create the PCM master")
    inputs = "".join(f"[{i}:a]" for i in range(len(stems)))
    graph = f"{inputs}amix=inputs={len(stems)}:duration=longest:dropout_transition=0:normalize=0,aresample={SAMPLE_RATE},apad,atrim=end_sample={TOTAL_SAMPLES},asetpts=PTS-STARTPTS[mix]"
    ffmpeg_inputs = [ffmpeg, "-hide_banner", "-nostats"]
    for stem in stems:
        ffmpeg_inputs.extend(("-i", str(stem)))
    first = run_ffmpeg(ffmpeg_inputs + [
        "-filter_complex", graph + ";[mix]loudnorm=I=-17:TP=-1.8:LRA=11:print_format=json[out]",
        "-map", "[out]", "-ar", str(SAMPLE_RATE), "-ac", "2", "-f", "null", "-",
    ], "first-pass loudnorm analysis")
    measured = parse_loudnorm(first)
    second_graph = (graph + ";[mix]loudnorm=I=-17:TP=-1.8:LRA=11"
                    + f":measured_I={measured['input_i']}:measured_TP={measured['input_tp']}"
                    + f":measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}"
                    + f":offset={measured['target_offset']}:linear=true:print_format=json[out]")
    second = run_ffmpeg(ffmpeg_inputs + [
        "-filter_complex", second_graph, "-map", "[out]", "-ar", str(SAMPLE_RATE), "-ac", "2",
        "-c:a", "pcm_s16le", str(path),
    ], "second-pass loudnorm render")
    second_measurement = parse_loudnorm(second)
    enforce_master_silence(path)
    run_ffmpeg([ffmpeg, "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"], "strict PCM master decode")
    wav_info = validate_wav(path, stereo=True)
    loudness = ebur128(path)
    if not -18.0 <= loudness["integratedLUFS"] <= -16.0:
        raise AudioBuildError(f"master loudness {loudness['integratedLUFS']} LUFS is outside [-18,-16] around -17 LUFS target")
    if loudness["truePeakDBTP"] > -1.0:
        raise AudioBuildError(f"master true peak {loudness['truePeakDBTP']} dBTP exceeds -1.0 dBTP acceptance")
    return {
        **wav_info,
        "strictDecode": "passed",
        "loudnormFirstPass": measured,
        "loudnormSecondPass": second_measurement,
        "ebur128Final": loudness,
        "normalizationTarget": {"integratedLUFS": -17.0, "truePeakDBTP": -1.8, "acceptanceLUFS": [-18.0, -16.0], "acceptanceTruePeakDBTP": -1.0, "passes": 2},
        "absoluteSilence": {"startSample": SILENCE_START_SAMPLE, "endSampleExclusive": SILENCE_END_SAMPLE, "peakPcm16": verify_silence(path), "exactZero": True},
    }


def chunk_caption_text(source: str) -> list[str]:
    clean = re.sub(r"\s+", "", source)
    if not clean:
        return []
    pieces = [clean[start:start + 28] for start in range(0, len(clean), 28)]
    return ["\n".join(piece[i:i + 14] for i in range(0, len(piece), 14)) for piece in pieces]


def build_captions(segments: list[dict[str, Any]], measured: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {item["id"]: item for item in measured}
    result = []
    for segment in segments:
        item = by_id[segment["id"]]
        phrase_texts = [text for chunk in segment["chunks"] for text in chunk_caption_text(chunk)]
        if not phrase_texts:
            raise AudioBuildError(f"{segment['id']} produces no visible caption phrases")
        weights = [max(1, len(text.replace("\n", ""))) for text in phrase_texts]
        total_weight = sum(weights)
        start_frame = item["voiceStartSample"] // SAMPLES_PER_FRAME
        end_frame = (item["voiceEndSampleExclusive"] + SAMPLES_PER_FRAME - 1) // SAMPLES_PER_FRAME
        span_frames = end_frame - start_frame
        if span_frames < len(phrase_texts):
            raise AudioBuildError(f"{segment['id']} active voice span has fewer video frames than caption phrases")
        cumulative = 0
        previous = start_frame
        for index, (text, weight) in enumerate(zip(phrase_texts, weights)):
            cumulative += weight
            if index == len(phrase_texts) - 1:
                current_end = end_frame
            else:
                current_end = start_frame + round(span_frames * cumulative / total_weight)
                current_end = min(end_frame - (len(phrase_texts) - index - 1), max(previous + 1, current_end))
            lines = text.split("\n")
            if not 1 <= len(lines) <= 2 or any(len(line) > 14 for line in lines):
                raise AudioBuildError(f"caption layout exceeds 14 characters per line or two lines: {text!r}")
            result.append({
                "segmentId": segment["id"], "startFrame": previous, "endFrame": current_end,
                "text": text, "alignment": "estimated_character_weighted_within_measured_pcm_span",
            })
            previous = current_end
    if not result or any(item["startFrame"] >= item["endFrame"] for item in result):
        raise AudioBuildError("caption timing is empty or contains a zero-length phrase")
    return result


def frame_srt_time(frame: int) -> str:
    milliseconds = round(frame * 1000 / FPS)
    hours, remaining = divmod(milliseconds, 3_600_000)
    minutes, remaining = divmod(remaining, 60_000)
    seconds, millis = divmod(remaining, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def write_srt(path: Path, captions: list[dict[str, Any]]) -> None:
    rows = []
    for index, caption in enumerate(captions, 1):
        rows.extend((str(index), f"{frame_srt_time(caption['startFrame'])} --> {frame_srt_time(caption['endFrame'])}", caption["text"], ""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows), encoding="utf-8")


def ensure_no_outputs_without_manifest() -> None:
    output_names = ("narration.wav", "score.wav", "sfx.wav", "master.wav")
    existing = [AUDIO / name for name in output_names if (AUDIO / name).exists()]
    if MIX_MANIFEST_PATH.exists():
        old = read_json(MIX_MANIFEST_PATH, "mix-manifest.json")
        if old.get("status") != "built":
            raise AudioBuildError("existing mix manifest is not in a verified built state")
        for path in existing:
            expected = old.get("outputs", {}).get(path.stem, {}).get("sha256")
            if expected != sha_file(path):
                raise AudioBuildError(f"existing {path.name} differs from its manifest; preserved")
        raise AudioBuildError("a verified mix already exists; no audio output was overwritten")
    if existing:
        raise AudioBuildError("audio output exists without a matching mix-manifest.json; no files were overwritten")


def run_mix(segments: list[dict[str, Any]], events: list[dict[str, Any]], event_source: dict[str, Any]) -> int:
    ensure_no_outputs_without_manifest()
    inventory, cues = cue_inventory(segments)
    spans, segment_timing = cue_timing(segments, cues)
    outputs: dict[str, Any] = {}
    temporary = {name: AUDIO / f"{name}.render.tmp.wav" for name in ("narration", "score", "sfx", "master")}
    AUDIO.mkdir(parents=True, exist_ok=True)
    try:
        outputs["narration"] = render_narration(temporary["narration"], spans)
        outputs["score"] = render_score(temporary["score"])
        outputs["sfx"], sfx_onsets = render_sfx(temporary["sfx"], events)
        for name in ("narration", "score", "sfx"):
            peak = verify_silence(temporary[name])
            if peak:
                raise AudioBuildError(f"{name} stem is not exact zero through the authored pause")
        outputs["master"] = mix_master(temporary["master"], [temporary[name] for name in ("narration", "score", "sfx")])
        captions = build_captions(segments, segment_timing)
        input_hashes = {
            "segmentsJson": sha_file(SEGMENTS_PATH),
            "sfxEventsJson": sha_file(EVENTS_PATH),
            "providerManifest": sha_file(PROVIDER_MANIFEST),
            "cueWavs": inventory,
            "eventProfiles": canonical_hash(EVENT_PROFILES),
        }
        input_set_hash = canonical_hash({
            "inputs": input_hashes,
            "mix": {"fps": FPS, "sampleRate": SAMPLE_RATE, "samplesPerChannel": TOTAL_SAMPLES,
                    "silence": [SILENCE_START_SAMPLE, SILENCE_END_SAMPLE],
                    "loudness": {"integratedLUFS": -17.0, "truePeakDBTP": -1.8}},
        })
        for name, source in temporary.items():
            target = AUDIO / f"{name}.wav"
            source.replace(target)
            outputs[name]["file"] = str(target.relative_to(WORK))
        timing = {
            "durationSeconds": DURATION_SECONDS,
            "fps": FPS,
            "sampleRate": SAMPLE_RATE,
            "samplesPerFrame": SAMPLES_PER_FRAME,
            "samplesPerChannel": TOTAL_SAMPLES,
            "status": "measured_pcm_with_estimated_phrase_timing",
            "captionTimingMethod": "Original phrase chunks allocated by character weight only within measured active PCM spans; no ASR or forced word alignment.",
            "segments": segment_timing,
            "captions": captions,
            "sfxEvents": sfx_onsets,
            "absoluteSilence": {
                "startFrame": SILENCE_START_FRAME,
                "endFrameExclusive": SILENCE_END_FRAME,
                "startSample": SILENCE_START_SAMPLE,
                "endSampleExclusive": SILENCE_END_SAMPLE,
                "samplesZeroInAllStemsAndMaster": True,
            },
            "sourceHashes": input_hashes,
        }
        mix_settings = {
            "version": 1,
            "inputSetSha256": input_set_hash,
            "durationSeconds": DURATION_SECONDS,
            "fps": FPS,
            "sampleRate": SAMPLE_RATE,
            "samplesPerFrame": SAMPLES_PER_FRAME,
            "samplesPerChannel": TOTAL_SAMPLES,
            "channels": 2,
            "blockSamples": BLOCK_SAMPLES,
            "scoreDesign": outputs["score"]["design"],
            "sfxDesign": outputs["sfx"]["design"],
            "loudnormTarget": outputs["master"]["normalizationTarget"],
            "absoluteSilence": timing["absoluteSilence"],
            "sourceHashes": input_hashes,
            "outputs": outputs,
        }
        manifest = {
            "version": 1,
            "status": "built",
            "inputSetSha256": input_set_hash,
            "sourceHashes": input_hashes,
            "outputs": outputs,
            "eventOnsets": sfx_onsets,
            "absoluteSilence": timing["absoluteSilence"],
            "audioTiming": str(TIMING_PATH.relative_to(WORK)),
            "authorization": "project/audio-authorization.json",
        }
        write_json(TIMING_PATH, timing)
        write_json(MIX_SETTINGS_PATH, mix_settings)
        write_json(MIX_MANIFEST_PATH, manifest)
        for path in (WORK / "B站" / "captions.srt", WORK / "小红书" / "captions.srt"):
            write_srt(path, captions)
        print(json.dumps({
            "status": "mix_complete",
            "durationSeconds": DURATION_SECONDS,
            "samplesPerChannel": TOTAL_SAMPLES,
            "cueCount": len(segment_timing),
            "captionCount": len(captions),
            "master": outputs["master"],
            "absoluteSilence": timing["absoluteSilence"],
        }, ensure_ascii=False, indent=2))
        return 0
    finally:
        for path in temporary.values():
            path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mix", action="store_true", help="build all shared EP08 audio outputs from verified local cues")
    parser.add_argument("--audit-cues", action="store_true", help="read and report cue file measurements only")
    args = parser.parse_args()
    if args.mix == args.audit_cues:
        parser.error("choose exactly one of --mix or --audit-cues")
    try:
        segments = load_segments()
        events, event_source = load_events()
        if args.audit_cues:
            inventory, _ = cue_inventory(segments)
            print(json.dumps({"status": "cues_measured", "cueCount": len(inventory), "cues": inventory}, ensure_ascii=False, indent=2))
            return 0
        return run_mix(segments, events, event_source)
    except (AudioBuildError, OSError, ValueError, wave.Error, OverflowError, subprocess.SubprocessError) as exc:
        print(f"build_audio.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
