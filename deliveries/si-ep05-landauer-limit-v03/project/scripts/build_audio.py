#!/usr/bin/env python3
"""Build deterministic EP05 audio from local PCM cues; never contacts a provider."""

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
CACHE_MANIFEST = AUDIO / "cache-manifest.json"
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
THERMAL_CUT_FRAME = 5_400
THERMAL_CUT_SAMPLE = THERMAL_CUT_FRAME * SAMPLES_PER_FRAME
THERMAL_START_FRAME = 1_800
THERMAL_START_SAMPLE = THERMAL_START_FRAME * SAMPLES_PER_FRAME
THERMAL_FADE_SAMPLES = 240  # 5 ms fade reaches exact zero at sample 4,320,000.
CRYO_CHIME_FRAME = 5_425
CRYO_CHIME_SAMPLE = CRYO_CHIME_FRAME * SAMPLES_PER_FRAME
VACUUM_SILENCE_START_SAMPLE = THERMAL_CUT_SAMPLE
VACUUM_SILENCE_END_SAMPLE = CRYO_CHIME_SAMPLE
SCORE_DUCK_DB = -6.0
SCORE_DUCK_ATTACK_SECONDS = 0.060
SCORE_DUCK_RELEASE_SECONDS = 0.420
SCORE_DESIGN_VERSION = "ep05-procedural-ambient-v03"
SCORE_WARM_SLOT_SECONDS = 15.0
SCORE_WARM_CROSSFADE_SECONDS = 10.0
SCORE_COLD_START_SECONDS = CRYO_CHIME_SAMPLE / SAMPLE_RATE
SCORE_FINAL_TAIL_START_SECONDS = 115.5
SCORE_FINAL_TAIL_SECONDS = DURATION_SECONDS - SCORE_FINAL_TAIL_START_SECONDS
WALL_GLIDE_FRACTION = 20 / 21  # 400 of the event's 420 frames; brickwall lands at frame 2600.

# The ordered frames are fixed by the EP05 brief. Names and descriptions from
# sfx_events.json are carried into the manifest when that file is available.
EVENT_SPECS = [
    {"id": "thought_thermal_spark", "frame": 120, "kind": "tick", "durationSeconds": 0.9},
    {"id": "memory_erasure_heat", "frame": 900, "kind": "thud", "durationSeconds": 1.5},
    {"id": "thermodynamic_seal", "frame": 1_350, "kind": "seal", "durationSeconds": 1.8, "frequencyHz": 40.0},
    {"id": "compute_wall_approach", "frame": 2_200, "kind": "wall", "durationSeconds": 7.0},
    {"id": "irreversible_heat_accumulation", "frame": 3_000, "kind": "crackle", "durationSeconds": 2.5},
    {"id": "planetary_pressure", "frame": 3_780, "kind": "infrared", "durationSeconds": 1.8},
    {"id": "returning_heat_alarm", "frame": 4_800, "kind": "planck", "durationSeconds": 2.0},
    {"id": "deep_space_crystal_chime", "frame": 5_425, "kind": "cryo", "durationSeconds": 2.4},
    {"id": "silent_hypothesis_harmonic", "frame": 6_480, "kind": "organ", "durationSeconds": 5.5},
    {"id": "synthetic_pulse_precursor", "frame": 6_990, "kind": "precursor", "durationSeconds": 0.35},
    {"id": "human_heartbeat_key", "frame": 7_020, "kind": "heartbeat", "durationSeconds": 2.0},
]
EXPECTED_EVENT_FRAMES = [entry["frame"] for entry in EVENT_SPECS]


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
    authored: dict[str, Any]
    if EVENTS_PATH.is_file():
        authored = read_json(EVENTS_PATH)
        if (authored.get("fps"), authored.get("sampleRate"), authored.get("samplesPerFrame")) != (FPS, SAMPLE_RATE, SAMPLES_PER_FRAME):
            raise AudioBuildError("sfx_events.json must use 60 fps, 48 kHz, and 800 samples per frame")
        events = authored.get("events")
        if not isinstance(events, list):
            raise AudioBuildError("sfx_events.json has no events list")
        frames = []
        for event in events:
            frame = event.get("frame", event.get("startFrame"))
            if not isinstance(frame, int):
                raise AudioBuildError("every sfx event needs an integer frame")
            if "sampleIndex" in event and event["sampleIndex"] != frame * SAMPLES_PER_FRAME:
                raise AudioBuildError(f"event at frame {frame} has an inconsistent sampleIndex")
            frames.append(frame)
        if sorted(frames) != EXPECTED_EVENT_FRAMES or len(set(frames)) != len(EXPECTED_EVENT_FRAMES):
            raise AudioBuildError(f"sfx_events.json frames must be {EXPECTED_EVENT_FRAMES}")
        silence = authored.get("silence_intervals")
        has_vacuum = (
            isinstance(silence, list) and any(
                isinstance(interval, dict)
                and interval.get("startFrame") == THERMAL_CUT_FRAME
                and interval.get("endFrame") == CRYO_CHIME_FRAME
                for interval in silence
            )
        )
        if not has_vacuum:
            raise AudioBuildError("sfx_events.json must declare the 25-frame digital vacuum [5400, 5425)")
    else:
        authored = {
            "fps": FPS,
            "sampleRate": SAMPLE_RATE,
            "samplesPerFrame": SAMPLES_PER_FRAME,
            "events": [{"id": item["id"], "frame": item["frame"]} for item in EVENT_SPECS],
            "source": "EP05 Task Packet fixed event anchors",
        }
    by_frame = {event.get("frame", event.get("startFrame")): event for event in authored["events"]}
    merged = []
    for spec in EVENT_SPECS:
        event = dict(spec)
        source = by_frame[spec["frame"]]
        event["sampleIndex"] = spec["frame"] * SAMPLES_PER_FRAME
        event["authoredId"] = source.get("id", spec["id"])
        if isinstance(source.get("description"), str):
            event["description"] = source["description"]
        merged.append(event)
    return merged, authored


def cue_path_for(segment_id: str) -> Path:
    if CACHE_MANIFEST.is_file():
        manifest = read_json(CACHE_MANIFEST)
        entry = manifest.get("segments", {}).get(segment_id)
        if isinstance(entry, dict) and isinstance(entry.get("cue_path"), str):
            candidate = (PROJECT / entry["cue_path"]).resolve()
            if candidate.is_relative_to(PROJECT.resolve()):
                return candidate
            raise AudioBuildError(f"cache manifest cue path escapes the EP05 v02 project for {segment_id}")
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
    starts_by_frame = {event["frame"] for event in events}
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
        overlaps_at_open = any(declared_start <= frame < declared_start + 12 for frame in starts_by_frame)
        delay_frames = 12 if overlaps_at_open else 0
        target_voice_sample = (declared_start + delay_frames) * SAMPLES_PER_FRAME
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
        active_start_sample = cue_start + onset
        active_end_sample = cue_start + active_end
        spans.append({
            "segmentId": sid,
            "startSample": cue_start,
            "cue": cue,
            "sampleCount": len(cue),
            "voiceStartSample": active_start_sample,
            "voiceEndSampleExclusive": active_end_sample,
            "sourcePath": cue_path,
        })
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
            "delayFrames": delay_frames,
            "delayReason": "opening SFX shares segment onset" if delay_frames else None,
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


def render_score(path: Path, narration_spans: list[dict[str, Any]]) -> dict[str, Any]:
    """Render an original, evolving ambient score with smooth sample-accurate ducking."""
    voice_ranges = sorted(
        (int(span["voiceStartSample"]), int(span["voiceEndSampleExclusive"]))
        for span in narration_spans
    )
    duck_target = 10.0 ** (SCORE_DUCK_DB / 20.0)
    attack_alpha = 1.0 - math.exp(-1.0 / (SCORE_DUCK_ATTACK_SECONDS * SAMPLE_RATE))
    release_alpha = 1.0 - math.exp(-1.0 / (SCORE_DUCK_RELEASE_SECONDS * SAMPLE_RATE))
    range_index = 0
    duck_gain = 1.0

    # Additive sine voices keep the score deterministic and fully local. The
    # chord voicings intentionally place several fundamentals in the 220-880 Hz
    # range so the music remains audible on small speakers while staying below
    # the narration's most sensitive 1-4 kHz band.
    warm_chords = (
        ("Am(add9)", ((55.00, .35), (110.00, .36), (164.81, .50), (220.00, .78),
                       (261.63, .67), (329.63, .50), (440.00, .36), (493.88, .27),
                       (659.25, .21), (880.00, .12))),
        ("Fmaj7", ((43.65, .30), (87.31, .34), (130.81, .47), (174.61, .56),
                   (220.00, .75), (261.63, .64), (349.23, .49), (392.00, .29),
                   (329.63, .40), (440.00, .35), (698.46, .19), (880.00, .10))),
        ("Dm(add9)", ((36.71, .26), (73.42, .31), (110.00, .39), (146.83, .50),
                      (174.61, .56), (220.00, .74), (261.63, .47), (293.66, .34),
                      (329.63, .37), (440.00, .28), (587.33, .20), (880.00, .09))),
        ("Esus", ((41.20, .32), (82.41, .40), (123.47, .46), (164.81, .63),
                  (220.00, .49), (246.94, .57), (329.63, .46), (369.99, .35),
                  (493.88, .28), (659.25, .17), (880.00, .11))),
    )
    cold_chords = (
        ("Cmaj7 suspended", ((65.41, .26), (130.81, .45), (164.81, .27), (196.00, .42),
                             (261.63, .70), (329.63, .52), (392.00, .37), (493.88, .32),
                             (523.25, .35), (783.99, .15))),
        ("Fmaj7 suspended", ((43.65, .22), (87.31, .25), (130.81, .36), (174.61, .44),
                             (220.00, .42), (261.63, .61), (329.63, .38), (349.23, .65), (392.00, .31),
                             (440.00, .36), (523.25, .34), (698.46, .22), (880.00, .12))),
    )
    pressure_tones = ((55.00, .36), (82.41, .30), (110.00, .38), (164.81, .43),
                      (220.00, .52), (293.66, .32), (349.23, .24))
    pressure_notes = (
        (61.6, 293.66), (65.2, 392.00), (69.1, 349.23), (73.0, 523.25),
        (77.0, 440.00), (81.0, 659.25), (85.0, 493.88), (88.5, 783.99),
    )
    cold_bells = (
        (92.0, 392.00), (95.4, 587.33), (99.0, 493.88), (102.7, 659.25),
        (106.3, 523.25), (110.0, 698.46), (113.4, 587.33),
    )
    chord_totals = {name: sum(weight for _, weight in tones) for name, tones in (*warm_chords, *cold_chords)}
    pressure_total = sum(weight for _, weight in pressure_tones)

    def smoothstep(value: float) -> float:
        value = min(1.0, max(0.0, value))
        return value * value * (3.0 - 2.0 * value)

    def chord_weights(t: float, chords: tuple[Any, ...], slot_seconds: float,
                      crossfade_seconds: float, origin_seconds: float = 0.0) -> tuple[tuple[int, float], ...]:
        """Return one or two adjacent chord weights with a smooth linear-power fade."""
        local_t = max(0.0, t - origin_seconds)
        slot = min(len(chords) - 1, int(local_t / slot_seconds))
        within = local_t - slot * slot_seconds
        half_fade = crossfade_seconds * 0.5
        if slot > 0 and within < half_fade:
            mix = smoothstep((within + half_fade) / crossfade_seconds)
            return ((slot - 1, 1.0 - mix), (slot, mix))
        if slot < len(chords) - 1 and within > slot_seconds - half_fade:
            mix = smoothstep((within - (slot_seconds - half_fade)) / crossfade_seconds)
            return ((slot, 1.0 - mix), (slot + 1, mix))
        return ((slot, 1.0),)

    def chord_sample(chord: tuple[str, tuple[tuple[float, float], ...]], t: float,
                     tone_phase: float) -> tuple[float, float]:
        name, tones = chord
        left = right = 0.0
        for index, (frequency, weight) in enumerate(tones):
            phase = tone_phase + index * 0.61
            # Gentle deterministic per-note panning makes a stereo bed without
            # detuning, phasey chorus, or transient energy.
            pan = 1.0 + 0.09 * ((index % 3) - 1)
            wave = weight * math.sin(2.0 * math.pi * frequency * t + phase)
            left += wave * pan
            right += wave * (2.0 - pan)
        total = max(chord_totals[name], 1e-9)
        return left / total, right / total

    def note_envelope(age: float, duration: float, attack: float = 0.32, release: float = 1.15) -> float:
        if age < 0.0 or age >= duration:
            return 0.0
        return smoothstep(age / attack) * (1.0 - smoothstep((age - (duration - release)) / release))

    def sparse_note(t: float, notes: tuple[tuple[float, float], ...], duration: float,
                    side: int, phase_offset: float = 0.0) -> float:
        value = 0.0
        for index, (start, frequency) in enumerate(notes):
            age = t - start
            env = note_envelope(age, duration)
            if env:
                phase = phase_offset + index * 0.73
                fundamental = math.sin(2.0 * math.pi * frequency * age + phase)
                overtone = 0.0
                if frequency * 2.0 <= 1_200.0:
                    overtone = 0.22 * math.sin(2.0 * math.pi * frequency * 2.0 * age + phase + 0.4)
                pan = 0.86 + side * 0.07 * ((index % 3) - 1)
                value += env * pan * (fundamental + overtone)
        return value

    def blocks() -> Any:
        nonlocal range_index, duck_gain
        for block_start in range(0, TOTAL_SAMPLES, BLOCK_SAMPLES):
            count = min(BLOCK_SAMPLES, TOTAL_SAMPLES - block_start)
            stereo = array.array("h")
            for offset in range(count):
                sample = block_start + offset
                t = sample / SAMPLE_RATE
                while range_index < len(voice_ranges) and voice_ranges[range_index][1] <= sample:
                    range_index += 1
                speaking = (
                    range_index < len(voice_ranges)
                    and voice_ranges[range_index][0] <= sample < voice_ranges[range_index][1]
                )
                target = duck_target if speaking else 1.0
                alpha = attack_alpha if target < duck_gain else release_alpha
                duck_gain += alpha * (target - duck_gain)
                if VACUUM_SILENCE_START_SAMPLE <= sample < VACUUM_SILENCE_END_SAMPLE:
                    stereo.extend((0, 0))
                    continue
                left = right = 0.0

                # Warm suspended progression: four 15-second harmonic fields,
                # with adjacent chords crossfading over ten seconds.
                warm_gate = smoothstep(t / 1.6) * (1.0 - smoothstep((t - 58.0) / 5.0))
                if warm_gate:
                    for chord_index, weight in chord_weights(
                        t, warm_chords, SCORE_WARM_SLOT_SECONDS, SCORE_WARM_CROSSFADE_SECONDS
                    ):
                        chord_l, chord_r = chord_sample(warm_chords[chord_index], t, chord_index * 0.27)
                        left += weight * chord_l
                        right += weight * chord_r
                    breath = 0.90 + 0.10 * math.sin(2.0 * math.pi * 0.031 * t)
                    left *= 0.205 * warm_gate * breath
                    right *= 0.205 * warm_gate * breath

                # A rounded low-string pulse and sparse midrange notes build
                # pressure from 60-90 seconds without sharp percussion.
                pressure_gate = smoothstep((t - 60.0) / 3.0) * (1.0 - smoothstep((t - 87.0) / 3.0))
                if pressure_gate:
                    pulse = 0.79 + 0.21 * (0.5 + 0.5 * math.cos(2.0 * math.pi * (t - 60.0) / 3.6))
                    pressure_l = pressure_r = 0.0
                    for index, (frequency, weight) in enumerate(pressure_tones):
                        wave = math.sin(2.0 * math.pi * frequency * t + index * 0.53)
                        pan = 1.0 + 0.08 * ((index % 3) - 1)
                        pressure_l += weight * wave * pan
                        pressure_r += weight * wave * (2.0 - pan)
                    pressure_l /= pressure_total
                    pressure_r /= pressure_total
                    left += 0.17 * pressure_gate * pulse * pressure_l
                    right += 0.17 * pressure_gate * pulse * pressure_r
                    left += 0.035 * pressure_gate * sparse_note(t, pressure_notes, 2.45, -1, 0.1)
                    right += 0.035 * pressure_gate * sparse_note(t, pressure_notes, 2.45, 1, 0.1)

                # The score itself is silent for the entire authored vacuum.
                # Its post-cut pad fades in after frame 5425 and resolves to a
                # gentle tail beginning at 115.5 seconds.
                if t >= SCORE_COLD_START_SECONDS:
                    cold_gate = smoothstep((t - SCORE_COLD_START_SECONDS) / 1.8)
                    cold_gate *= 1.0 - smoothstep((t - SCORE_FINAL_TAIL_START_SECONDS) / SCORE_FINAL_TAIL_SECONDS)
                    if cold_gate:
                        cold_origin = SCORE_COLD_START_SECONDS
                        for chord_index, weight in chord_weights(t, cold_chords, 12.5, 8.0, cold_origin):
                            chord_l, chord_r = chord_sample(cold_chords[chord_index], t, 0.3 + chord_index * 0.41)
                            left += 0.17 * cold_gate * weight * chord_l
                            right += 0.17 * cold_gate * weight * chord_r
                        left += 0.024 * cold_gate * sparse_note(t, cold_bells, 2.25, -1, 0.4)
                        right += 0.024 * cold_gate * sparse_note(t, cold_bells, 2.25, 1, 0.4)

                left *= duck_gain
                right *= duck_gain
                stereo.extend((pcm16(left), pcm16(right)))
            if sys.byteorder != "little":
                stereo.byteswap()
            yield stereo.tobytes()
    write_stereo_wav(path, blocks())
    result = validate_stem(path)
    result["design"] = {
        "version": SCORE_DESIGN_VERSION,
        "description": "Original deterministic ambient score: Am(add9)-Fmaj7-Dm(add9)-Esus warm chord fields, pressing low strings and soft pulse, exact vacuum, then airy Cmaj7/Fmaj7 suspended pad and sparse bells.",
        "warmProgression": {"chords": [name for name, _ in warm_chords], "slotSeconds": SCORE_WARM_SLOT_SECONDS, "crossfadeSeconds": SCORE_WARM_CROSSFADE_SECONDS, "sectionSeconds": [0, 60]},
        "pressureSection": {"seconds": [60, 90], "pulsePeriodSeconds": 3.6, "sparseNoteFrequenciesHz": [frequency for _, frequency in pressure_notes], "smoothEnvelopes": True},
        "vacuum": {"startFrame": THERMAL_CUT_FRAME, "endFrameExclusive": CRYO_CHIME_FRAME, "exactZero": True},
        "coldSection": {"startFrame": CRYO_CHIME_FRAME, "startSeconds": SCORE_COLD_START_SECONDS, "chords": [name for name, _ in cold_chords], "crossfadeSeconds": 8.0, "sparseBellFrequenciesHz": [frequency for _, frequency in cold_bells], "tailStartSeconds": SCORE_FINAL_TAIL_START_SECONDS, "tailEndSeconds": DURATION_SECONDS},
        "audibleFrequencyDesignHz": {"fundamentalRange": [36.71, 880.0], "midrangeEmphasis": [220.0, 880.0], "bellOvertoneCeiling": 1200.0, "speechBandAvoidance": "No score fundamentals above 880 Hz; bell overtones above 1200 Hz are omitted."},
        "stereo": "Deterministic per-tone pan; no sampled stereo source.",
        "speechDuckTargetDb": SCORE_DUCK_DB,
        "attackSeconds": SCORE_DUCK_ATTACK_SECONDS,
        "releaseSeconds": SCORE_DUCK_RELEASE_SECONDS,
        "activePcmBounds": "measured narration active bounds with exponential attack/release",
    }
    return result


def enforce_exact_vacuum(path: Path) -> dict[str, Any]:
    """Re-zero the authored interval after mastering lookahead/limiting."""
    temporary = path.with_name(path.stem + ".vacuum.tmp.wav")
    try:
        with wave.open(str(path), "rb") as source:
            params = source.getparams()
            if (params.framerate, params.nchannels, params.sampwidth, params.nframes) != (
                SAMPLE_RATE, 2, 2, TOTAL_SAMPLES
            ):
                raise AudioBuildError("master must be exact-length 48 kHz stereo PCM16 before vacuum enforcement")
            with wave.open(str(temporary), "wb") as target:
                target.setnchannels(params.nchannels)
                target.setsampwidth(params.sampwidth)
                target.setframerate(params.framerate)
                cursor = 0
                while cursor < TOTAL_SAMPLES:
                    count = min(BLOCK_SAMPLES, TOTAL_SAMPLES - cursor)
                    raw = bytearray(source.readframes(count))
                    if len(raw) != count * 4:
                        raise AudioBuildError("master ended before exact-vacuum enforcement completed")
                    overlap_start = max(cursor, VACUUM_SILENCE_START_SAMPLE)
                    overlap_end = min(cursor + count, VACUUM_SILENCE_END_SAMPLE)
                    if overlap_start < overlap_end:
                        offset = (overlap_start - cursor) * 4
                        length = (overlap_end - overlap_start) * 4
                        raw[offset:offset + length] = b"\0" * length
                    target.writeframesraw(raw)
                    cursor += count
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "startFrame": THERMAL_CUT_FRAME,
        "endFrameExclusive": CRYO_CHIME_FRAME,
        "startSample": VACUUM_SILENCE_START_SAMPLE,
        "endSampleExclusive": VACUUM_SILENCE_END_SAMPLE,
        "postLoudnormPcmZeroEnforcement": True,
    }


def event_value(event: dict[str, Any], local_sample: int) -> tuple[float, float]:
    rate = SAMPLE_RATE
    duration = event["durationSeconds"]
    t = local_sample / rate
    if t >= duration:
        return 0.0, 0.0
    kind = event["kind"]
    if kind == "tick":
        value = 0.28 * math.cos(2 * math.pi * 760.0 * t) * math.exp(-24.0 * t)
    elif kind == "thud":
        body = 0.40 * math.cos(2 * math.pi * (72.0 - 24.0 * t / duration) * t) * math.exp(-2.5 * t)
        overtone = 0.10 * math.cos(2 * math.pi * 176.0 * t) * math.exp(-7.0 * t)
        value = body + overtone
    elif kind == "seal":
        seal = 0.36 * math.cos(2 * math.pi * event["frequencyHz"] * t) * math.exp(-1.2 * t)
        scan = 0.09 * math.cos(2 * math.pi * 720.0 * t) * math.exp(-7.0 * t)
        value = seal + scan
    elif kind == "wall":
        glide_duration = duration * WALL_GLIDE_FRACTION
        glide_seconds = min(t, glide_duration)
        glide_phase = 2 * math.pi * (110.0 * glide_seconds + 0.5 * (820.0 - 110.0) * glide_seconds * glide_seconds / glide_duration)
        attack = 0.08 + 0.92 * min(1.0, t / 0.16)
        glide = 0.17 * math.cos(glide_phase) * attack * math.exp(-0.40 * t)
        wall = 0.14 * math.cos(2 * math.pi * 740.0 * t) if t >= glide_duration else 0.0
        value = glide + wall
    elif kind == "crackle":
        grain = local_sample // 480
        phase = local_sample % 480
        code = ((grain + 0x9E3779B9) ^ (grain << 13) ^ (grain >> 7)) & 0xFFFFFFFF
        amp = ((code & 0xFFFF) / 32767.5 - 1.0) * 0.22
        pulse = max(0.0, 1.0 - phase / 228.0) ** 2
        bed = 0.12 * math.cos(2 * math.pi * 190.0 * t) * (0.7 + 0.3 * math.sin(2 * math.pi * 0.35 * t))
        value = amp * pulse + bed
    elif kind == "infrared":
        hum = 0.26 * math.cos(2 * math.pi * 58.0 * t) * (0.7 + 0.3 * math.cos(2 * math.pi * 1.3 * t))
        beep = 0.11 * math.cos(2 * math.pi * 760.0 * t) * math.exp(-0.35 * t)
        value = hum + beep
    elif kind == "planck":
        glide_phase = 2 * math.pi * (210.0 * t + 0.5 * (880.0 - 210.0) * t * t / duration)
        value = 0.22 * math.cos(glide_phase) * min(1.0, t / 0.28) + 0.09 * math.cos(2 * math.pi * 680.0 * t) * math.exp(-0.12 * t)
    elif kind == "cryo":
        value = (0.20 * math.cos(2 * math.pi * 523.25 * t) * math.exp(-1.25 * t)
                 + 0.16 * math.cos(2 * math.pi * 659.25 * t) * math.exp(-0.95 * t)
                 + 0.12 * math.cos(2 * math.pi * 783.99 * t) * math.exp(-0.72 * t))
    elif kind == "organ":
        attack = 0.08 + 0.92 * min(1.0, t / 0.35)
        release = min(1.0, max(0.0, (duration - t) / 0.8))
        envelope = attack * release
        value = envelope * (0.22 * math.cos(2 * math.pi * 110.0 * t)
                            + 0.15 * math.cos(2 * math.pi * 164.81 * t)
                            + 0.13 * math.cos(2 * math.pi * 220.0 * t)
                            + 0.10 * math.cos(2 * math.pi * 329.63 * t))
    elif kind == "heartbeat":
        first = math.exp(-((t - 0.10) / 0.085) ** 2)
        second = 0.72 * math.exp(-((t - 0.48) / 0.11) ** 2)
        pulse = first + second
        value = pulse * (0.28 * math.cos(2 * math.pi * 72.0 * t) + 0.09 * math.cos(2 * math.pi * 880.0 * t))
    elif kind == "precursor":
        attack = 0.18 + 0.82 * min(1.0, t / 0.012)
        value = attack * (0.20 * math.cos(2 * math.pi * 740.0 * t)
                          + 0.08 * math.cos(2 * math.pi * 392.0 * t)) * math.exp(-16.0 * t)
    else:
        raise AudioBuildError(f"unknown event kind {kind}")
    # Paired oscillators are deliberately kept below 900 Hz; a two-pole
    # 850 Hz low-pass is applied to the complete SFX stem after summing.
    return value, value * (0.92 + 0.08 * math.cos(2 * math.pi * 0.7 * t))


def render_sfx(path: Path, events: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    lowpass_alpha = 1.0 - math.exp(-2.0 * math.pi * 850.0 / SAMPLE_RATE)
    state_l1 = state_l2 = state_r1 = state_r2 = 0.0
    mapped = [{
        "id": event["id"], "authoredId": event["authoredId"], "frame": event["frame"],
        "sampleIndex": event["sampleIndex"], "durationSeconds": event["durationSeconds"],
        "frequencyHz": event.get("frequencyHz"),
        "description": event.get("description"), "spectralDesign": "two-pole 850 Hz low-pass; voice-critical 1-4 kHz band reduced",
    } for event in events]
    def blocks() -> Any:
        nonlocal state_l1, state_l2, state_r1, state_r2
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
                event_start = event["sampleIndex"]
                event_end = event_start + round(event["durationSeconds"] * SAMPLE_RATE)
                overlap_start, overlap_end = max(block_start, event_start), min(block_end, event_end)
                for absolute in range(overlap_start, overlap_end):
                    offset = absolute - block_start
                    value_l, value_r = event_value(event, absolute - event_start)
                    left[offset] += value_l
                    right[offset] += value_r
                cursor += 1
            stereo = array.array("h")
            for raw_l, raw_r in zip(left, right):
                state_l1 += lowpass_alpha * (raw_l - state_l1)
                state_l2 += lowpass_alpha * (state_l1 - state_l2)
                state_r1 += lowpass_alpha * (raw_r - state_r1)
                state_r2 += lowpass_alpha * (state_r1 - state_r2)
                stereo.extend((pcm16(state_l2), pcm16(state_r2)))
            if sys.byteorder != "little":
                stereo.byteswap()
            yield stereo.tobytes()
    write_stereo_wav(path, blocks())
    result = validate_stem(path)
    result["design"] = "Eleven fixed-frame cues; the 2200-frame compute-wall rise transitions to its brickwall at frame 2600 then rings for 20 frames; the 6990-frame synthetic precursor leads the 7020-frame heartbeat by 500 ms; two-pole 850 Hz low-pass reduces SFX energy in the 1-4 kHz speech band."
    return result, mapped


def render_thermal(path: Path) -> dict[str, Any]:
    def blocks() -> Any:
        state_l, state_r = 0x13579BDF, 0x2468ACE1
        fast_l = slow_l = fast_r = slow_r = 0.0
        for block_start in range(0, TOTAL_SAMPLES, BLOCK_SAMPLES):
            count = min(BLOCK_SAMPLES, TOTAL_SAMPLES - block_start)
            stereo = array.array("h")
            for offset in range(count):
                sample = block_start + offset
                if sample < THERMAL_START_SAMPLE or sample >= THERMAL_CUT_SAMPLE:
                    stereo.extend((0, 0))
                    continue
                state_l = (1664525 * state_l + 1013904223) & 0xFFFFFFFF
                state_r = (1664525 * state_r + 1013904223) & 0xFFFFFFFF
                white_l = state_l / 2147483647.5 - 1.0
                white_r = state_r / 2147483647.5 - 1.0
                fast_l = 0.965 * fast_l + 0.035 * white_l
                slow_l = 0.995 * slow_l + 0.005 * fast_l
                fast_r = 0.965 * fast_r + 0.035 * white_r
                slow_r = 0.995 * slow_r + 0.005 * fast_r
                progress = (sample - THERMAL_START_SAMPLE) / (THERMAL_CUT_SAMPLE - THERMAL_START_SAMPLE - 1)
                pressure = 0.10 + 0.90 * progress ** 1.6
                fade = min(1.0, max(0.0, (THERMAL_CUT_SAMPLE - sample) / THERMAL_FADE_SAMPLES))
                amplitude = 0.085 * pressure * fade
                stereo.extend((pcm16((0.72 * fast_l + 1.12 * slow_l) * amplitude),
                               pcm16((0.72 * fast_r + 1.12 * slow_r) * amplitude)))
            if sys.byteorder != "little":
                stereo.byteswap()
            yield stereo.tobytes()
    write_stereo_wav(path, blocks())
    result = validate_stem(path)
    envelope_windows = measure_thermal_envelope(path)
    if any(right["rms"] <= left["rms"] for left, right in zip(envelope_windows, envelope_windows[1:])):
        raise AudioBuildError("thermal.wav measured RMS did not rise across consecutive 10-second pressure windows")
    result["design"] = {
        "noise": "Seeded Brownian-style two-stage low-pass noise with a power-law rising amplitude envelope",
        "startFrame": THERMAL_START_FRAME,
        "startSample": THERMAL_START_SAMPLE,
        "cutFrame": THERMAL_CUT_FRAME,
        "cutSample": THERMAL_CUT_SAMPLE,
        "preCutFadeSamples": THERMAL_FADE_SAMPLES,
        "exactZeroFromSample": THERMAL_CUT_SAMPLE,
        "pressureEnvelope": "0.10 + 0.90 × progress^1.6, progress from frame 1800 to 5399",
        "measuredRmsWindows": envelope_windows,
    }
    return result


def measure_thermal_envelope(path: Path) -> list[dict[str, Any]]:
    windows = []
    window_frames = 600
    with wave.open(str(path), "rb") as wav:
        for start_frame in range(THERMAL_START_FRAME, THERMAL_CUT_FRAME, window_frames):
            end_frame = min(start_frame + window_frames, THERMAL_CUT_FRAME)
            start_sample = start_frame * SAMPLES_PER_FRAME
            sample_count = (end_frame - start_frame) * SAMPLES_PER_FRAME
            wav.setpos(start_sample)
            raw = wav.readframes(sample_count)
            values = array.array("h")
            values.frombytes(raw)
            if sys.byteorder != "little":
                values.byteswap()
            if len(values) != sample_count * 2:
                raise AudioBuildError("thermal RMS measurement encountered a truncated PCM window")
            rms = math.sqrt(sum(value * value for value in values) / len(values)) / 32768.0
            if rms <= 0:
                raise AudioBuildError(f"thermal.wav is silent in frame window [{start_frame}, {end_frame})")
            windows.append({
                "startFrame": start_frame,
                "endFrameExclusive": end_frame,
                "rms": rms,
                "rmsDbfs": 20.0 * math.log10(rms),
            })
    return windows


def verify_thermal_cut(path: Path) -> int:
    peak = 0
    with wave.open(str(path), "rb") as wav:
        if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getnframes()) != (SAMPLE_RATE, 2, 2, TOTAL_SAMPLES):
            raise AudioBuildError(f"{path.name} is not an exact-length stereo PCM16 stem")
        wav.setpos(THERMAL_CUT_SAMPLE)
        remaining = TOTAL_SAMPLES - THERMAL_CUT_SAMPLE
        while remaining:
            count = min(BLOCK_SAMPLES, remaining)
            raw = wav.readframes(count)
            if len(raw) != count * 4:
                raise AudioBuildError("thermal stem ended before the exact cut could be verified")
            values = array.array("h")
            values.frombytes(raw)
            if sys.byteorder != "little":
                values.byteswap()
            peak = max(peak, max((abs(value) for value in values), default=0))
            remaining -= count
    if peak:
        raise AudioBuildError(f"thermal.wav must be identically zero from sample {THERMAL_CUT_SAMPLE}; peak was {peak}")
    return peak


def verify_thermal_prestart(path: Path) -> int:
    peak = 0
    with wave.open(str(path), "rb") as wav:
        if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getnframes()) != (
            SAMPLE_RATE, 2, 2, TOTAL_SAMPLES
        ):
            raise AudioBuildError(f"{path.name} is not an exact-length stereo PCM16 stem")
        wav.setpos(0)
        remaining = THERMAL_START_SAMPLE
        while remaining:
            count = min(BLOCK_SAMPLES, remaining)
            raw = wav.readframes(count)
            if len(raw) != count * 4:
                raise AudioBuildError("thermal stem ended before its start silence could be verified")
            values = array.array("h")
            values.frombytes(raw)
            if sys.byteorder != "little":
                values.byteswap()
            peak = max(peak, max((abs(value) for value in values), default=0))
            remaining -= count
    if peak:
        raise AudioBuildError(f"thermal.wav must be identically zero before frame {THERMAL_START_FRAME}; peak was {peak}")
    return peak


def verify_digital_vacuum(path: Path) -> dict[str, int | bool]:
    """Require exact digital zero in a stem/master for frames [5400, 5425)."""
    peak = 0
    start = VACUUM_SILENCE_START_SAMPLE
    end = VACUUM_SILENCE_END_SAMPLE
    try:
        with wave.open(str(path), "rb") as wav:
            if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getnframes()) != (SAMPLE_RATE, 2, 2, TOTAL_SAMPLES):
                raise AudioBuildError(f"{path.name} is not an exact-length stereo PCM16 stem")
            wav.setpos(start)
            remaining = end - start
            while remaining:
                count = min(BLOCK_SAMPLES, remaining)
                raw = wav.readframes(count)
                if len(raw) != count * 4:
                    raise AudioBuildError("digital-vacuum interval ended before its exact boundary")
                values = array.array("h")
                values.frombytes(raw)
                if sys.byteorder != "little":
                    values.byteswap()
                peak = max(peak, max((abs(value) for value in values), default=0))
                remaining -= count
    except (OSError, wave.Error) as exc:
        raise AudioBuildError(f"cannot inspect digital-vacuum interval in {path.name}: {exc}") from None
    if peak:
        raise AudioBuildError(f"{path.name} must be identically zero in frames [5400, 5425); peak was {peak}")
    return {"startFrame": THERMAL_CUT_FRAME, "endFrameExclusive": CRYO_CHIME_FRAME,
            "startSample": start, "endSampleExclusive": end, "peakPcm16": peak, "exactZero": True}


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
        "-filter_complex", graph + ";[mix]loudnorm=I=-17:TP=-1.8:LRA=11:print_format=json[out]",
        "-map", "[out]", "-ar", str(SAMPLE_RATE), "-ac", "2", "-f", "null", "-",
    ], "first-pass loudnorm analysis")
    measured = loudnorm_measurements(first)
    second_filter = (graph + ";[mix]loudnorm=I=-17:TP=-1.8:LRA=11"
                     + f":measured_I={measured['input_i']}:measured_TP={measured['input_tp']}"
                     + f":measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}"
                     + f":offset={measured['target_offset']}:linear=true:print_format=json[out]")
    args = list(args_in)
    args.extend(("-filter_complex", second_filter, "-map", "[out]", "-ar", str(SAMPLE_RATE), "-ac", "2",
                 "-c:a", "pcm_s16le", str(path)))
    second = run_ffmpeg(args, "second-pass loudnorm render")
    second_stats = loudnorm_measurements(second)
    vacuum_mute = enforce_exact_vacuum(path)
    validate_stem(path)
    run_ffmpeg([ffmpeg, "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"], "strict master decode")
    loudness = ebur128(path)
    if not -18.0 <= loudness["integratedLUFS"] <= -16.0:
        raise AudioBuildError(f"master loudness {loudness['integratedLUFS']} LUFS is outside -18 to -16 LUFS")
    if loudness["truePeakDBTP"] > -1.0:
        raise AudioBuildError(f"master true peak {loudness['truePeakDBTP']} dBTP exceeds -1.0 dBTP")
    return {
        **validate_stem(path),
        "strictDecode": "passed",
        "loudnormFirstPass": measured,
        "loudnormSecondPass": second_stats,
        "ebur128Final": loudness,
        "loudnormTarget": {"integratedLUFS": -17.0, "truePeakDBTP": -1.8, "acceptanceLUFS": [-18.0, -16.0], "acceptanceTruePeakDBTP": -1.0, "passes": 2},
        "exactVacuum": vacuum_mute,
        "latencyNote": "FFmpeg loudnorm true-peak processing is delay compensated; output is trimmed to exactly 5,760,000 samples per channel.",
    }


def source_hashes(segments: list[dict[str, Any]], events: list[dict[str, Any]], event_data: dict[str, Any]) -> dict[str, Any]:
    cues = []
    for segment in segments:
        path = cue_path_for(segment["id"])
        if not path.is_file():
            raise AudioBuildError(f"missing local cue {path.relative_to(WORK)}")
        info = wav_info(path, stereo=False)
        cues.append({"id": segment["id"], "path": str(path.relative_to(WORK)), "sha256": info["sha256"], "samplesAt48k": info["samples"]})
    result = {
        "buildAudioPy": sha256_file(Path(__file__).resolve()),
        "scriptMd": sha256_file(WORK / "source" / "script.md"),
        "segmentsJson": sha256_file(SEGMENTS_PATH),
        "eventsJson": sha256_file(EVENTS_PATH) if EVENTS_PATH.is_file() else canonical_hash(event_data),
        "eventSpec": canonical_hash(events),
        "cacheManifest": sha256_file(CACHE_MANIFEST) if CACHE_MANIFEST.is_file() else None,
        "cueWavs": cues,
    }
    return result


def check_existing(inputs_hash: str) -> bool:
    output_paths = [AUDIO / f"{name}.wav" for name in ("narration", "score", "sfx", "thermal", "master")]
    existing = [path for path in output_paths if path.exists()]
    if MANIFEST_PATH.is_file():
        old = read_json(MANIFEST_PATH)
        if old.get("inputSetSha256") != inputs_hash:
            raise AudioBuildError("existing EP05 mix is bound to different inputs; outputs preserved for review")
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
    if not (WORK / "source" / "script.md").is_file():
        raise AudioBuildError("source/script.md is missing")
    hashes = source_hashes(segments, events, event_data)
    input_set_hash = canonical_hash({
        "sourceHashes": hashes,
        "spec": {
            "fps": FPS,
            "sampleRate": SAMPLE_RATE,
            "totalSamples": TOTAL_SAMPLES,
            "thermalStartSample": THERMAL_START_SAMPLE,
            "thermalCutSample": THERMAL_CUT_SAMPLE,
            "scoreDesignVersion": SCORE_DESIGN_VERSION,
            "scoreDuckDb": SCORE_DUCK_DB,
            "scoreDuckAttackSeconds": SCORE_DUCK_ATTACK_SECONDS,
            "scoreDuckReleaseSeconds": SCORE_DUCK_RELEASE_SECONDS,
            "scoreWarmSlotSeconds": SCORE_WARM_SLOT_SECONDS,
            "scoreWarmCrossfadeSeconds": SCORE_WARM_CROSSFADE_SECONDS,
            "scoreColdStartSample": CRYO_CHIME_SAMPLE,
            "scoreFinalTailStartSeconds": SCORE_FINAL_TAIL_START_SECONDS,
            "wallGlideFraction": WALL_GLIDE_FRACTION,
        },
    })
    if check_existing(input_set_hash):
        return 0
    AUDIO.mkdir(parents=True, exist_ok=True)
    spans, segment_timing = cue_timing(segments, events)
    temporary = {name: AUDIO / f"{name}.render.tmp.wav" for name in ("narration", "score", "sfx", "thermal", "master")}
    try:
        outputs: dict[str, Any] = {}
        outputs["narration"] = render_narration(temporary["narration"], spans)
        outputs["score"] = render_score(temporary["score"], spans)
        outputs["sfx"], onset_map = render_sfx(temporary["sfx"], events)
        outputs["thermal"] = render_thermal(temporary["thermal"])
        thermal_prestart_peak = verify_thermal_prestart(temporary["thermal"])
        thermal_peak = verify_thermal_cut(temporary["thermal"])
        stem_paths = [temporary[name] for name in ("narration", "score", "sfx", "thermal")]
        vacuum_stems = {name: verify_digital_vacuum(temporary[name]) for name in ("narration", "score", "sfx", "thermal")}
        outputs["master"] = mix_master(temporary["master"], stem_paths)
        vacuum_master = verify_digital_vacuum(temporary["master"])
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
            "status": "measured_pcm_pending_caption_alignment",
            "pcmMeasurement": {
                "masterFile": outputs["master"]["file"],
                "sha256": outputs["master"]["sha256"],
                "sampleRate": SAMPLE_RATE,
                "channels": 2,
                "samplesPerChannel": TOTAL_SAMPLES,
                "durationSeconds": DURATION_SECONDS,
                "integratedLUFS": outputs["master"]["ebur128Final"]["integratedLUFS"],
                "truePeakDBTP": outputs["master"]["ebur128Final"]["truePeakDBTP"],
                "strictDecode": outputs["master"]["strictDecode"],
            },
            "captionTimingMethod": "Measured active PCM bounds from each decoded cue; captions will be allocated proportionally and remain estimated phrase timing, not ASR or word alignment.",
            "sfxEvents": onset_map,
            "thermalNoise": {
                "startFrame": THERMAL_START_FRAME,
                "startSample": THERMAL_START_SAMPLE,
                "cutFrame": THERMAL_CUT_FRAME,
                "cutSample": THERMAL_CUT_SAMPLE,
                "preCutFadeSamples": THERMAL_FADE_SAMPLES,
                "samplesZeroBeforeStart": thermal_prestart_peak == 0,
                "samplesZeroFromCut": thermal_peak == 0,
                "measuredRmsWindows": outputs["thermal"]["design"]["measuredRmsWindows"],
            },
            "digitalVacuum": {"interval": vacuum_master, "stemChecks": vacuum_stems, "masterCheck": vacuum_master},
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
            "thermalNoise": outputs["thermal"]["design"],
            "loudnormTarget": outputs["master"]["loudnormTarget"],
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
            "thermalStartSample": THERMAL_START_SAMPLE,
            "thermalZeroFromSample": THERMAL_CUT_SAMPLE,
            "mixSettings": str(SETTINGS_PATH.relative_to(WORK)),
            "audioTiming": str(TIMING_PATH.relative_to(WORK)),
        }
        write_json(TIMING_PATH, timing)
        write_json(SETTINGS_PATH, settings)
        write_json(MANIFEST_PATH, manifest)
        print(json.dumps({"status": "mix_complete", "master": outputs["master"], "eventOnsets": onset_map, "thermalZeroFromSample": THERMAL_CUT_SAMPLE}, ensure_ascii=False, indent=2))
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
