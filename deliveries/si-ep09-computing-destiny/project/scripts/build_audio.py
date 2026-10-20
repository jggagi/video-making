#!/usr/bin/env python3
"""Build EP09 narration, procedural score/SFX, measured timing, and PCM master."""

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

import numpy as np


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
DURATION_SECONDS = 90
TOTAL_FRAMES = FPS * DURATION_SECONDS
TOTAL_SAMPLES = SAMPLE_RATE * DURATION_SECONDS
BLOCK_SAMPLES = 24_000
LUFS_TARGET = -16.0
LUFS_TOLERANCE = 0.2
TRUE_PEAK_TARGET_DBTP = -1.8
TRUE_PEAK_ACCEPTANCE_DBTP = -1.0
SILENCE_START_FRAME = 4_860
SILENCE_END_FRAME = 4_885
SILENCE_START_SAMPLE = SILENCE_START_FRAME * SAMPLES_PER_FRAME
SILENCE_END_SAMPLE = SILENCE_END_FRAME * SAMPLES_PER_FRAME
EXPECTED_IDS = [f"S{i:02d}" for i in range(1, 9)]

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
    "romantic_cello": ("warm_cello", 2.40),
    "cyan_scan": ("scan", 1.30),
    "double_heartbeat": ("double_heartbeat_mech", 1.25),
    "time_spiral": ("whoosh", 2.20),
    "day489_terminal": ("metal_terminal", 1.70),
    "rewind_38hz": ("rewind_38hz", 1.80),
    "nudge1": ("glass_chime", 2.50),
    "nudge2": ("glass_chime", 2.50),
    "nudge3": ("glass_chime", 2.50),
    "shepard_rise": ("shepard_sweep", 3.20),
    "defiant_piano_cello": ("warm_piano_cello", 4.00),
}
SCORE_SCENE_FRAMES = [60, 240, 720, 1380, 2340, 2700, 3360, 3600, 3840, 4380, 4885]
SFX_EVENT_DESCRIPTIONS = [
    "warm cello swell",
    "soft scanning texture",
    "double heartbeat with restrained mechanism",
    "rising filtered whoosh",
    "muted metal terminal resonance",
    "38 Hz rewind sweep",
    "first glass chime",
    "second glass chime",
    "third glass chime",
    "layered Shepard rise",
    "warm piano and cello resolution",
]


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


def mix_spec() -> dict[str, Any]:
    return {
        "fps": FPS,
        "sampleRate": SAMPLE_RATE,
        "samplesPerChannel": TOTAL_SAMPLES,
        "silence": [SILENCE_START_SAMPLE, SILENCE_END_SAMPLE],
        "loudness": {"integratedLUFS": LUFS_TARGET, "truePeakDBTP": TRUE_PEAK_TARGET_DBTP},
        "postLoudnormCalibration": {
            "method": "linear PCM gain by final measured LUFS difference",
            "targetIntegratedLUFS": LUFS_TARGET,
            "sampleCountPreserved": True,
            "stemsChanged": False,
        },
    }


def mix_input_set_hash(input_hashes: dict[str, Any]) -> str:
    return canonical_hash({"inputs": input_hashes, "mix": mix_spec()})


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
    try:
        segments = json.loads(SEGMENTS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AudioBuildError(f"cannot read segments.json: {exc}") from None
    if not isinstance(segments, list) or [item.get("id") for item in segments] != EXPECTED_IDS:
        raise AudioBuildError("segments.json must contain exactly S01 through S08 in order")
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
    if authored.get("fps") != FPS or authored.get("absoluteSilence") != [SILENCE_START_FRAME, SILENCE_END_FRAME]:
        raise AudioBuildError("sfx_events.json fps or absoluteSilence differs from the EP09 audio packet")
    source = authored.get("events")
    expected = [(event_id, frame) for (event_id, _), frame in zip(
        EVENT_PROFILES.items(), [60, 240, 720, 1380, 2340, 2700, 3360, 3600, 3840, 4380, 4885]
    )]
    expected_with_silence = expected[:-1] + [("silence_start", SILENCE_START_FRAME), expected[-1]]
    if not isinstance(source, list) or [(event.get("id"), event.get("frame")) for event in source] != expected_with_silence:
        raise AudioBuildError("sfx_events.json IDs/order/frames differ from the assigned EP09 scene events")
    events = []
    previous = -1
    descriptions = iter(SFX_EVENT_DESCRIPTIONS)
    for item in source:
        item_id = item["id"]
        frame = item["frame"]
        if item_id == "silence_start":
            previous = frame
            continue
        if not isinstance(frame, int) or not 0 <= frame < TOTAL_FRAMES or frame <= previous:
            raise AudioBuildError(f"{item_id} has an invalid or out-of-order frame")
        sample = frame * SAMPLES_PER_FRAME
        kind, duration = EVENT_PROFILES[item_id]
        if frame < SILENCE_END_FRAME and sample + round(duration * SAMPLE_RATE) > SILENCE_START_SAMPLE:
            raise AudioBuildError(f"{item_id} SFX would overlap the absolute silence interval")
        events.append({
            "id": item_id, "frame": frame, "sampleIndex": sample,
            "durationSeconds": duration, "kind": kind, "description": next(descriptions),
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
        raise AudioBuildError("provider manifest settings differ from authorized EP09 TTS")
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
    for index, segment in enumerate(segments):
        sid = segment["id"]
        cue = cues[sid]
        onset, active_end, method = active_bounds(cue)
        declared_voice_start = segment["startFrame"] * SAMPLES_PER_FRAME
        delayed_voice_start = SILENCE_END_SAMPLE if sid == "S08" else declared_voice_start
        voice_start = max(declared_voice_start, delayed_voice_start)
        cue_start = voice_start if sid == "S08" else voice_start - onset
        cue_end = cue_start + len(cue)
        normal_end = segment["endFrame"] * SAMPLES_PER_FRAME
        next_start = segments[index + 1]["startFrame"] * SAMPLES_PER_FRAME if index + 1 < len(segments) else normal_end
        hard_end = min(normal_end, next_start - round(0.1 * SAMPLE_RATE))
        if cue_start < 0:
            raise AudioBuildError(f"NEEDS_SOL: {sid} measured onset would place the complete cue before sample zero")
        if cue_end > hard_end:
            boundary = f"its declared end/reserved tail boundary at sample {hard_end}"
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
            "placement": (
                "complete S08 source cue placed at the first sample of frame 4885 after the exact-zero interval; source PCM preserved"
                if sid == "S08" else
                "measured active PCM onset aligned to the declared start frame; complete source cue preserved"
            ),
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


def smooth_array(value: np.ndarray) -> np.ndarray:
    x = np.clip(value, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def ramp_array(frame: np.ndarray, start: int, end: int) -> np.ndarray:
    return smooth_array((frame - start) / max(1, end - start))


def voice_gain_array(samples: np.ndarray, measured: list[dict[str, Any]], attenuation_db: float = -8.0) -> np.ndarray:
    duck = 10.0 ** (attenuation_db / 20.0)
    pre = round(0.060 * SAMPLE_RATE)
    release = round(0.350 * SAMPLE_RATE)
    gain = np.ones(samples.shape, dtype=np.float64)
    for span in measured:
        voice_start = span["voiceStartSample"]
        voice_end = span["voiceEndSampleExclusive"]
        pre_start = max(0, voice_start - pre)
        mask = (samples >= pre_start) & (samples < voice_start)
        if np.any(mask):
            progress = (samples[mask] - pre_start) / max(1, voice_start - pre_start)
            gain[mask] = np.minimum(gain[mask], 1.0 - (1.0 - duck) * smooth_array(progress))
        mask = (samples >= voice_start) & (samples < voice_end)
        gain[mask] = np.minimum(gain[mask], duck)
        release_end = min(TOTAL_SAMPLES, voice_end + release)
        mask = (samples >= voice_end) & (samples < release_end)
        if np.any(mask):
            progress = (samples[mask] - voice_end) / max(1, release_end - voice_end)
            gain[mask] = np.minimum(gain[mask], duck + (1.0 - duck) * smooth_array(progress))
    return gain


def score_block(samples: np.ndarray, measured: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    time = samples / SAMPLE_RATE
    frame = samples / SAMPLES_PER_FRAME
    warm_open = 1.0 - ramp_array(frame, 240, 2700)
    cold = ramp_array(frame, 720, 1800) * (1.0 - ramp_array(frame, 2700, 3960))
    warm_return = ramp_array(frame, 3360, 4885)
    tension = ramp_array(frame, 4140, 4380) * (1.0 - ramp_array(frame, 4770, 4885))

    vibrato = 0.016 * np.sin(2.0 * np.pi * 5.2 * time)
    cello = (
        0.42 * np.sin(2.0 * np.pi * 110.0 * time + vibrato)
        + 0.24 * np.sin(2.0 * np.pi * 164.81 * time + 1.5 * vibrato + 0.12)
        + 0.16 * np.sin(2.0 * np.pi * 220.0 * time + 2.0 * vibrato + 0.24)
        + 0.09 * np.sin(2.0 * np.pi * 330.0 * time + 3.0 * vibrato + 0.36)
    )
    cold_mod = 0.78 + 0.22 * np.sin(2.0 * np.pi * 0.17 * time + 0.3)
    cold_field = cold_mod * (
        0.34 * np.sin(2.0 * np.pi * 58.27 * time)
        + 0.26 * np.sin(2.0 * np.pi * 77.78 * time + 0.7)
        + 0.18 * np.sin(2.0 * np.pi * 116.54 * time + 1.2)
        + 0.12 * np.sin(2.0 * np.pi * 233.08 * time + 0.4)
        + 0.08 * np.sin(2.0 * np.pi * 311.13 * time + 2.1)
    )
    warm_chord = (
        0.34 * np.sin(2.0 * np.pi * 110.0 * time)
        + 0.25 * np.sin(2.0 * np.pi * 164.81 * time + 0.16)
        + 0.20 * np.sin(2.0 * np.pi * 220.0 * time + 0.31)
        + 0.13 * np.sin(2.0 * np.pi * 261.63 * time + 0.46)
        + 0.08 * np.sin(2.0 * np.pi * 329.63 * time + 0.63)
    )
    piano_pulse = np.maximum(0.0, np.sin(2.0 * np.pi * 0.23 * time + 0.8)) ** 2
    piano = piano_pulse * (
        0.40 * np.sin(2.0 * np.pi * 261.63 * time)
        + 0.24 * np.sin(2.0 * np.pi * 392.0 * time + 0.1)
        + 0.16 * np.sin(2.0 * np.pi * 523.25 * time + 0.25)
        + 0.08 * np.sin(2.0 * np.pi * 783.99 * time + 0.4)
    )
    rise = np.sin(2.0 * np.pi * (55.0 * time + 8.0 * time * time))
    bed = 0.11 * np.sin(2.0 * np.pi * 55.0 * time + 0.2)
    value = 0.031 * warm_open * cello + 0.018 * cold * cold_field
    value += warm_return * (0.025 * warm_chord + 0.012 * piano)
    value += 0.010 * tension * rise + 0.005 * bed
    fade_samples = round(0.800 * SAMPLE_RATE)
    endpoint_fade = np.clip((TOTAL_SAMPLES - samples) / fade_samples, 0.0, 1.0)
    silence_fade = np.ones(samples.shape, dtype=np.float64)
    fade = round(0.020 * SAMPLE_RATE)
    pre = (samples >= SILENCE_START_SAMPLE - fade) & (samples < SILENCE_START_SAMPLE)
    silence_fade[pre] = (SILENCE_START_SAMPLE - samples[pre]) / fade
    post = (samples >= SILENCE_END_SAMPLE) & (samples < SILENCE_END_SAMPLE + fade)
    silence_fade[post] = (samples[post] - SILENCE_END_SAMPLE) / fade
    silence_fade[(samples >= SILENCE_START_SAMPLE) & (samples < SILENCE_END_SAMPLE)] = 0.0
    duck = voice_gain_array(samples, measured)
    value *= endpoint_fade * silence_fade * duck
    pan = 0.045 * np.sin(2.0 * np.pi * 0.08 * time)
    left = value * (0.98 - pan)
    right = value * (0.98 + pan)
    if len(samples) and samples[-1] == TOTAL_SAMPLES - 1:
        left[-1] = right[-1] = 0.0
    return left, right


def render_score(path: Path, measured: list[dict[str, Any]]) -> dict[str, Any]:
    def blocks():
        for block_start in range(0, TOTAL_SAMPLES, BLOCK_SAMPLES):
            count = min(BLOCK_SAMPLES, TOTAL_SAMPLES - block_start)
            samples = np.arange(block_start, block_start + count, dtype=np.int64)
            left, right = score_block(samples, measured)
            stereo = np.column_stack((left, right))
            stereo = np.clip(np.rint(stereo * 32767.0), -32768, 32767).astype("<i2")
            yield stereo.tobytes()
    write_stereo(path, blocks())
    return validate_wav(path, stereo=True) | {
        "design": {
            "description": "Continuous deterministic cello-like harmonic bed moves from warm consonance into a restrained cold field, then returns to piano and cello warmth; no stock or cliché beep samples.",
            "sceneChangeFrames": SCORE_SCENE_FRAMES,
            "silenceWindowFrames": [SILENCE_START_FRAME, SILENCE_END_FRAME],
            "voiceDuckDB": -8.0,
            "voicePreattackMilliseconds": 60,
            "voiceReleaseMilliseconds": 350,
            "stereo": "deterministic subtle pan; same shared master for both platforms",
            "endpointFadeSeconds": 0.8,
        }
    }


def event_value(kind: str, times: np.ndarray, duration: float, event_id: str) -> tuple[np.ndarray, np.ndarray]:
    t = times
    progress = np.clip(t / duration, 0.0, 1.0)
    attack = smooth_array(np.minimum(1.0, t / min(0.045, duration * 0.15)))
    release = np.clip((duration - t) / min(0.48, duration * 0.22), 0.0, 1.0)
    env = attack * release
    if kind == "warm_cello":
        vibrato = 0.014 * np.sin(2.0 * np.pi * 4.9 * t)
        wave = (0.34 * np.sin(2.0 * np.pi * 110.0 * t + vibrato)
                + 0.18 * np.sin(2.0 * np.pi * 220.0 * t + 2.0 * vibrato + 0.2)
                + 0.10 * np.sin(2.0 * np.pi * 330.0 * t + 3.0 * vibrato + 0.4))
        left, right = env * 0.12 * wave, env * 0.115 * (wave + 0.025 * np.sin(2.0 * np.pi * 164.81 * t))
    elif kind == "scan":
        phase_a = 2.0 * np.pi * (280.0 * t + 46.0 * t * t / duration)
        phase_b = 2.0 * np.pi * (411.0 * t - 27.0 * t * t / duration + 0.23)
        scan = 0.55 * np.sin(phase_a) + 0.45 * np.sin(phase_b)
        left, right = env * 0.052 * scan, env * 0.049 * (0.8 * scan + 0.2 * np.sin(2.0 * np.pi * 557.0 * t))
    elif kind == "double_heartbeat_mech":
        pulse = np.exp(-((t - 0.20) / 0.12) ** 2) + 0.78 * np.exp(-((t - 0.56) / 0.14) ** 2)
        mech = 0.70 * np.sin(2.0 * np.pi * 53.0 * t) + 0.30 * np.sin(2.0 * np.pi * 106.0 * t + 0.3)
        left, right = env * 0.105 * pulse * mech, env * 0.10 * pulse * (0.9 * mech + 0.1 * np.sin(2.0 * np.pi * 78.0 * t))
    elif kind == "whoosh":
        phase_a = 2.0 * np.pi * (55.0 * t + 84.0 * t * t / duration)
        phase_b = 2.0 * np.pi * (93.0 * t + 51.0 * t * t / duration + 0.4)
        swell = np.sin(np.pi * progress) ** 1.4
        wave = 0.56 * np.sin(phase_a) + 0.31 * np.sin(phase_b) + 0.13 * np.sin(2.0 * np.pi * 238.0 * t + 0.6)
        left, right = env * swell * 0.09 * wave, env * swell * 0.087 * (0.94 * wave + 0.06 * np.sin(2.0 * np.pi * 311.0 * t))
    elif kind == "metal_terminal":
        ring = (0.46 * np.sin(2.0 * np.pi * 92.5 * t) * np.exp(-2.0 * t)
                + 0.30 * np.sin(2.0 * np.pi * 277.0 * t + 0.2) * np.exp(-2.8 * t)
                + 0.18 * np.sin(2.0 * np.pi * 369.5 * t + 0.55) * np.exp(-3.5 * t))
        left, right = env * 0.12 * ring, env * 0.115 * (0.96 * ring + 0.04 * np.sin(2.0 * np.pi * 554.0 * t))
    elif kind == "rewind_38hz":
        phase = 2.0 * np.pi * (210.0 * t - 86.0 * t * t / duration)
        low = np.sin(2.0 * np.pi * 38.0 * t)
        reverse = np.sin(phase) + 0.34 * np.sin(2.0 * phase + 0.2)
        left, right = env * 0.105 * (0.62 * low + 0.38 * reverse), env * 0.10 * (0.60 * low + 0.40 * np.sin(phase + 0.06))
    elif kind == "glass_chime":
        fundamental = {"nudge1": 659.25, "nudge2": 783.99, "nudge3": 987.77}.get(event_id, 659.25)
        bell = (0.52 * np.sin(2.0 * np.pi * fundamental * t) * np.exp(-2.2 * t)
                + 0.29 * np.sin(2.0 * np.pi * fundamental * 2.76 * t + 0.21) * np.exp(-3.0 * t)
                + 0.15 * np.sin(2.0 * np.pi * fundamental * 5.41 * t + 0.5) * np.exp(-4.1 * t))
        left, right = env * 0.072 * bell, env * 0.069 * (0.92 * bell + 0.08 * np.sin(2.0 * np.pi * fundamental * 1.51 * t))
    elif kind == "shepard_sweep":
        layers = np.zeros_like(t)
        for octave, phase_offset in ((55.0, 0.0), (110.0, 0.7), (220.0, 1.4), (440.0, 2.1)):
            local_progress = np.clip(progress + (phase_offset / (2.0 * np.pi)), 0.0, 1.0)
            frequency = octave * (2.0 ** (2.0 * local_progress))
            phase = 2.0 * np.pi * (octave * t + octave * (4.0 ** local_progress - 1.0) * duration / (4.0 * np.log(2.0)))
            layer_gain = np.sin(np.pi * local_progress) ** 1.2
            layers += 0.25 * layer_gain * np.sin(phase) * np.sqrt(110.0 / np.maximum(55.0, frequency))
        left, right = env * 0.11 * layers, env * 0.105 * (0.93 * layers + 0.07 * np.sin(2.0 * np.pi * 329.63 * t))
    elif kind == "warm_piano_cello":
        cello = 0.42 * np.sin(2.0 * np.pi * 110.0 * t) + 0.23 * np.sin(2.0 * np.pi * 164.81 * t + 0.16)
        piano = (0.31 * np.sin(2.0 * np.pi * 261.63 * t) * np.exp(-0.48 * t)
                 + 0.21 * np.sin(2.0 * np.pi * 392.0 * t + 0.18) * np.exp(-0.72 * t)
                 + 0.12 * np.sin(2.0 * np.pi * 523.25 * t + 0.34) * np.exp(-0.95 * t))
        left, right = env * 0.09 * (cello + piano), env * 0.087 * (0.96 * cello + piano)
    else:
        raise AudioBuildError(f"unknown procedural SFX kind {kind}")
    return left, right


def render_sfx(path: Path, events: list[dict[str, Any]], measured: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    left = np.zeros(TOTAL_SAMPLES, dtype=np.float32)
    right = np.zeros(TOTAL_SAMPLES, dtype=np.float32)
    onsets = []
    for event in events:
        start = event["sampleIndex"]
        count = min(round(event["durationSeconds"] * SAMPLE_RATE), TOTAL_SAMPLES - start)
        if start < SILENCE_END_SAMPLE and start + count > SILENCE_START_SAMPLE:
            raise AudioBuildError(f"{event['id']} overlaps authored silence")
        indices = np.arange(count, dtype=np.int64)
        times = indices / SAMPLE_RATE
        lval, rval = event_value(event["kind"], times, event["durationSeconds"], event["id"])
        duck = voice_gain_array(indices + start, measured, attenuation_db=-9.0)
        left[start:start + count] += (lval * duck).astype(np.float32)
        right[start:start + count] += (rval * duck).astype(np.float32)
        onsets.append({
            "id": event["id"], "frame": event["frame"], "sampleIndex": start,
            "durationSeconds": event["durationSeconds"], "kind": event["kind"],
            "description": event["description"],
        })
    def blocks():
        for start in range(0, TOTAL_SAMPLES, BLOCK_SAMPLES):
            end = min(TOTAL_SAMPLES, start + BLOCK_SAMPLES)
            lblock = left[start:end].copy()
            rblock = right[start:end].copy()
            silence_left = max(start, SILENCE_START_SAMPLE) - start
            silence_right = min(end, SILENCE_END_SAMPLE) - start
            if silence_right > silence_left:
                lblock[silence_left:silence_right] = 0.0
                rblock[silence_left:silence_right] = 0.0
            stereo = np.column_stack((lblock, rblock))
            yield np.clip(np.rint(stereo * 32767.0), -32768, 32767).astype("<i2").tobytes()
    write_stereo(path, blocks())
    info = validate_wav(path, stereo=True)
    info["design"] = {
        "description": "Deterministic local procedural warm cello, scan, double heartbeat/mechanism, whoosh, metal terminal, 38 Hz rewind, glass chimes, Shepard rise, and warm piano/cello.",
        "events": onsets,
        "silenceWindowFrames": [SILENCE_START_FRAME, SILENCE_END_FRAME],
        "voiceDuckDB": -9.0,
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
        raise AudioBuildError(f"{path.name} is not exact digital silence over [4860,4885); PCM16 peak={peak}")
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


def calibrate_master_pcm(source: Path, target: Path, gain_db: float) -> dict[str, Any]:
    """Apply one deterministic scalar gain to the master only, preserving exact zeros."""
    gain = 10.0 ** (gain_db / 20.0)
    if not math.isfinite(gain) or gain <= 0:
        raise AudioBuildError("master calibration gain is invalid")
    try:
        with wave.open(str(source), "rb") as wav:
            params = wav.getparams()
            if (params.framerate, params.nchannels, params.sampwidth, params.nframes, params.comptype) != (SAMPLE_RATE, 2, 2, TOTAL_SAMPLES, "NONE"):
                raise AudioBuildError("master calibration input has unexpected PCM format or duration")
            raw = wav.readframes(params.nframes)
    except (OSError, wave.Error) as exc:
        raise AudioBuildError(f"cannot read master for calibration: {exc}") from None
    values = np.frombuffer(raw, dtype="<i2").astype(np.float64)
    calibrated = np.rint(values * gain)
    peak = float(np.max(np.abs(calibrated))) if calibrated.size else 0.0
    if peak > 32767:
        raise AudioBuildError(f"master calibration would clip PCM16 (predicted peak {peak:.0f})")
    output = calibrated.astype("<i2").tobytes()
    start, end = SILENCE_START_SAMPLE * 4, SILENCE_END_SAMPLE * 4
    if any(output[start:end]):
        raise AudioBuildError("master calibration changed the authored exact-zero interval")
    try:
        with wave.open(str(target), "wb") as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(output)
    except (OSError, wave.Error) as exc:
        raise AudioBuildError(f"cannot write calibrated master: {exc}") from None
    return {"gainDB": round(gain_db, 6), "linearGain": gain, "samplePeakPcm16": int(peak)}


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
        "-filter_complex", graph + f";[mix]loudnorm=I={LUFS_TARGET}:TP={TRUE_PEAK_TARGET_DBTP}:LRA=11:print_format=json[out]",
        "-map", "[out]", "-ar", str(SAMPLE_RATE), "-ac", "2", "-f", "null", "-",
    ], "first-pass loudnorm analysis")
    measured = parse_loudnorm(first)
    second_graph = (graph + f";[mix]loudnorm=I={LUFS_TARGET}:TP={TRUE_PEAK_TARGET_DBTP}:LRA=11"
                    + f":measured_I={measured['input_i']}:measured_TP={measured['input_tp']}"
                    + f":measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}"
                    + f":offset={measured['target_offset']}:linear=true:print_format=json[out]")
    second = run_ffmpeg(ffmpeg_inputs + [
        "-filter_complex", second_graph, "-map", "[out]", "-ar", str(SAMPLE_RATE), "-ac", "2",
        "-c:a", "pcm_s16le", str(path),
    ], "second-pass loudnorm render")
    second_measurement = parse_loudnorm(second)
    enforce_master_silence(path)
    before_calibration = ebur128(path)
    calibrated_path = path.with_name(path.stem + ".calibrated.tmp.wav")
    try:
        calibration_gain_db = LUFS_TARGET - before_calibration["integratedLUFS"]
        calibration = calibrate_master_pcm(path, calibrated_path, calibration_gain_db)
        calibrated_path.replace(path)
    finally:
        calibrated_path.unlink(missing_ok=True)
    run_ffmpeg([ffmpeg, "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"], "strict PCM master decode")
    wav_info = validate_wav(path, stereo=True)
    loudness = ebur128(path)
    if not LUFS_TARGET - LUFS_TOLERANCE <= loudness["integratedLUFS"] <= LUFS_TARGET + LUFS_TOLERANCE:
        raise AudioBuildError(f"master loudness {loudness['integratedLUFS']} LUFS is outside the -16 LUFS ±0.2 acceptance")
    if loudness["truePeakDBTP"] > TRUE_PEAK_ACCEPTANCE_DBTP:
        raise AudioBuildError(f"master true peak {loudness['truePeakDBTP']} dBTP exceeds -1.0 dBTP acceptance")
    calibration.update({"measuredBefore": before_calibration, "measuredAfter": loudness,
                       "method": "linear PCM gain by final measured LUFS difference",
                       "targetIntegratedLUFS": LUFS_TARGET, "sampleCountPreserved": True,
                       "stemsChanged": False})
    return {
        **wav_info,
        "strictDecode": "passed",
        "loudnormFirstPass": measured,
        "loudnormSecondPass": second_measurement,
        "ebur128Final": loudness,
        "normalizationTarget": {"integratedLUFS": LUFS_TARGET, "truePeakDBTP": TRUE_PEAK_TARGET_DBTP,
                                "acceptanceLUFS": [LUFS_TARGET - LUFS_TOLERANCE, LUFS_TARGET + LUFS_TOLERANCE],
                                "acceptanceTruePeakDBTP": TRUE_PEAK_ACCEPTANCE_DBTP, "passes": 2},
        "postLoudnormCalibration": calibration,
        "absoluteSilence": {"startSample": SILENCE_START_SAMPLE, "endSampleExclusive": SILENCE_END_SAMPLE, "peakPcm16": verify_silence(path), "exactZero": True},
    }


def chunk_caption_text(source: str) -> list[str]:
    clean = re.sub(r"\s+", "", source)
    if not clean:
        return []
    pieces = [clean[start:start + 26] for start in range(0, len(clean), 26)]
    return ["\n".join(piece[i:i + 13] for i in range(0, len(piece), 13)) for piece in pieces]


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
        start_frame = math.ceil(item["voiceStartSample"] / SAMPLES_PER_FRAME)
        end_frame = item["voiceEndSampleExclusive"] // SAMPLES_PER_FRAME
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
            if not 1 <= len(lines) <= 2 or any(len(line) > 13 for line in lines):
                raise AudioBuildError(f"caption layout exceeds 13 characters per line or two lines: {text!r}")
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
        outputs["score"] = render_score(temporary["score"], segment_timing)
        outputs["sfx"], sfx_onsets = render_sfx(temporary["sfx"], events, segment_timing)
        for name in ("narration", "score", "sfx"):
            peak = verify_silence(temporary[name])
            if peak:
                raise AudioBuildError(f"{name} stem is not exact zero through the authored pause")
        outputs["master"] = mix_master(temporary["master"], [temporary[name] for name in ("narration", "score", "sfx")])
        captions = build_captions(segments, segment_timing)
        input_hashes = {
            "segmentsJson": sha_file(SEGMENTS_PATH),
            "sfxEventsJson": sha_file(EVENTS_PATH),
            "audioAuthorization": sha_file(PROJECT / "audio-authorization.json"),
            "providerManifest": sha_file(PROVIDER_MANIFEST),
            "cueWavs": inventory,
            "eventProfiles": canonical_hash(EVENT_PROFILES),
        }
        input_set_hash = mix_input_set_hash(input_hashes)
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
        write_srt(WORK / "小红书" / "captions.srt", captions)
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


def run_master_calibration(segments: list[dict[str, Any]], events: list[dict[str, Any]]) -> int:
    """Calibrate an existing verified mix without touching its narration or stems."""
    settings = read_json(MIX_SETTINGS_PATH, "mix-settings.json")
    manifest = read_json(MIX_MANIFEST_PATH, "mix-manifest.json")
    timing = read_json(TIMING_PATH, "audio-timing.json")
    if manifest.get("status") != "built":
        raise AudioBuildError("master calibration requires an existing built mix manifest")
    if settings.get("inputSetSha256") != manifest.get("inputSetSha256"):
        raise AudioBuildError("mix-settings and mix-manifest input hashes disagree; preserving outputs")
    if settings.get("sourceHashes") != manifest.get("sourceHashes") or timing.get("sourceHashes") != manifest.get("sourceHashes"):
        raise AudioBuildError("audio metadata source hashes disagree; preserving outputs")
    if "postLoudnormCalibration" in settings.get("outputs", {}).get("master", {}):
        raise AudioBuildError("master already has post-loudnorm calibration recorded; preserving outputs")

    current_inputs = {
        "segmentsJson": sha_file(SEGMENTS_PATH),
        "sfxEventsJson": sha_file(EVENTS_PATH),
        "audioAuthorization": sha_file(PROJECT / "audio-authorization.json"),
        "providerManifest": sha_file(PROVIDER_MANIFEST),
        "cueWavs": cue_inventory(segments)[0],
        "eventProfiles": canonical_hash(EVENT_PROFILES),
    }
    if current_inputs != manifest.get("sourceHashes"):
        raise AudioBuildError("source inputs differ from the built mix; preserving outputs")
    if [(event["id"], event["frame"]) for event in events] != [
        (entry["id"], entry["frame"]) for entry in manifest.get("eventOnsets", [])
    ]:
        raise AudioBuildError("SFX event positions differ from the built mix; preserving outputs")

    names = ("narration", "score", "sfx", "master")
    for name in names:
        path = AUDIO / f"{name}.wav"
        manifest_entry = manifest.get("outputs", {}).get(name)
        settings_entry = settings.get("outputs", {}).get(name)
        if not isinstance(manifest_entry, dict) or not isinstance(settings_entry, dict):
            raise AudioBuildError(f"{name} is missing output metadata; preserving outputs")
        if manifest_entry.get("sha256") != settings_entry.get("sha256") or manifest_entry.get("pcmSha256") != settings_entry.get("pcmSha256"):
            raise AudioBuildError(f"{name} metadata hashes disagree; preserving outputs")
        if not path.is_file() or sha_file(path) != manifest_entry.get("sha256"):
            raise AudioBuildError(f"existing {path.name} differs from its manifest; preserving outputs")
        validate_wav(path, stereo=True)
        verify_silence(path)

    master_path = AUDIO / "master.wav"
    master_entry = manifest["outputs"]["master"]
    before = ebur128(master_path)
    gain_db = LUFS_TARGET - before["integratedLUFS"]
    temporary = AUDIO / "master.calibration.tmp.wav"
    try:
        gain_info = calibrate_master_pcm(master_path, temporary, gain_db)
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise AudioBuildError("ffmpeg is required for final strict PCM master decode")
        run_ffmpeg([ffmpeg, "-v", "error", "-xerror", "-i", str(temporary), "-f", "null", "-"], "strict calibrated PCM master decode")
        calibrated_info = validate_wav(temporary, stereo=True)
        calibrated_loudness = ebur128(temporary)
        if not LUFS_TARGET - LUFS_TOLERANCE <= calibrated_loudness["integratedLUFS"] <= LUFS_TARGET + LUFS_TOLERANCE:
            raise AudioBuildError(f"calibrated master loudness {calibrated_loudness['integratedLUFS']} LUFS is outside the -16 LUFS ±0.2 acceptance")
        if calibrated_loudness["truePeakDBTP"] > TRUE_PEAK_ACCEPTANCE_DBTP:
            raise AudioBuildError(f"calibrated master true peak {calibrated_loudness['truePeakDBTP']} dBTP exceeds -1.0 dBTP acceptance")
        if verify_silence(temporary) != 0:
            raise AudioBuildError("calibrated master lost its exact-zero interval")

        calibration = {
            **gain_info,
            "measuredBefore": before,
            "measuredAfter": calibrated_loudness,
            "method": "linear PCM gain by final measured LUFS difference",
            "targetIntegratedLUFS": LUFS_TARGET,
            "sampleCountPreserved": True,
            "stemsChanged": False,
        }
        calibrated_info.update({
            "file": str(master_path.relative_to(WORK)),
            "strictDecode": "passed",
            "loudnormFirstPass": master_entry.get("loudnormFirstPass"),
            "loudnormSecondPass": master_entry.get("loudnormSecondPass"),
            "ebur128Final": calibrated_loudness,
            "normalizationTarget": master_entry.get("normalizationTarget"),
            "postLoudnormCalibration": calibration,
            "absoluteSilence": {"startSample": SILENCE_START_SAMPLE, "endSampleExclusive": SILENCE_END_SAMPLE,
                                "peakPcm16": 0, "exactZero": True},
        })
        temporary.replace(master_path)
    finally:
        temporary.unlink(missing_ok=True)

    new_inputs_hash = mix_input_set_hash(current_inputs)
    settings["inputSetSha256"] = new_inputs_hash
    settings["sourceHashes"] = current_inputs
    settings["postLoudnormCalibration"] = mix_spec()["postLoudnormCalibration"]
    settings["outputs"]["master"] = calibrated_info
    manifest["inputSetSha256"] = new_inputs_hash
    manifest["sourceHashes"] = current_inputs
    manifest["outputs"]["master"] = calibrated_info
    timing["sourceHashes"] = current_inputs
    timing["mixInputSetSha256"] = new_inputs_hash
    timing["master"] = calibrated_info
    write_json(TIMING_PATH, timing)
    write_json(MIX_SETTINGS_PATH, settings)
    write_json(MIX_MANIFEST_PATH, manifest)
    print(json.dumps({
        "status": "master_calibrated",
        "gainDB": calibration["gainDB"],
        "loudnessBefore": before,
        "loudnessAfter": calibrated_loudness,
        "masterSha256": calibrated_info["sha256"],
        "masterPcmSha256": calibrated_info["pcmSha256"],
        "samplesPerChannel": calibrated_info["samplesPerChannel"],
        "stemsPreserved": True,
        "absoluteSilence": calibrated_info["absoluteSilence"],
    }, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mix", action="store_true", help="build EP09's 90 second PCM audio set from verified local cues")
    parser.add_argument("--calibrate-master", action="store_true", help="apply measured post-loudnorm gain to an existing verified master only")
    parser.add_argument("--audit-cues", action="store_true", help="read and report cue file measurements only")
    args = parser.parse_args()
    if sum((args.mix, args.calibrate_master, args.audit_cues)) != 1:
        parser.error("choose exactly one of --mix, --calibrate-master, or --audit-cues")
    try:
        segments = load_segments()
        events, event_source = load_events()
        if args.audit_cues:
            inventory, _ = cue_inventory(segments)
            print(json.dumps({"status": "cues_measured", "cueCount": len(inventory), "cues": inventory}, ensure_ascii=False, indent=2))
            return 0
        if args.calibrate_master:
            return run_master_calibration(segments, events)
        return run_mix(segments, events, event_source)
    except (AudioBuildError, OSError, ValueError, wave.Error, OverflowError, subprocess.SubprocessError) as exc:
        print(f"build_audio.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
