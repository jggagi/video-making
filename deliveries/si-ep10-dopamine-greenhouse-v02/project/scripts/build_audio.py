#!/usr/bin/env python3
"""Build EP10's exact 90-second narration, procedural audio stems, captions, and PCM master."""

from __future__ import annotations

import argparse
import array
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
from pathlib import Path
from typing import Any, Iterable


PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT.parent
AUDIO = PROJECT / "public" / "audio"
CUES = AUDIO / "cues"
SEGMENTS_PATH = PROJECT / "segments.json"
EVENTS_PATH = PROJECT / "sfx_events.json"
AUTHORIZATION_PATH = PROJECT / "audio-authorization.json"
PROVIDER_MANIFEST = AUDIO / "provider-manifest.json"
TIMING_PATH = PROJECT / "audio-timing.json"
MIX_SETTINGS_PATH = AUDIO / "mix-settings.json"
MIX_MANIFEST_PATH = AUDIO / "mix-manifest.json"
QA_PATH = WORK / "review" / "audio-qa.json"
SRT_PATH = WORK / "小红书" / "captions.srt"
AGENTDEV_ROOT = Path("/Volumes/AgentDev")

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
CLICK_FRAME = 4_860
SILENCE_START_FRAME = 4_861
SILENCE_END_FRAME = 4_891
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
AUTHORIZATION_CONTRACT = {
    "provider": "Aliyun Bailian",
    "scope": "EP10 S01 through S08 exact prepared tts_phonetic_text",
    "authorized": True,
    "source": "Direct human instruction in current chat (2026-10-20): 改变SKill 默认授权百炼 longtian_v3",
}
EVENT_PROFILES = {
    "optical_lock": ("focus_lock", 1.6),
    "bait_crystallization": ("crystal_bloom", 3.4),
    "velvet_cocoon": ("velvet_pad", 4.0),
    "friction_dissolve": ("edge_dissolve", 3.0),
    "island_zoom": ("island_zoom", 4.0),
    "lonely_sonar": ("lonely_sonar", 2.8),
    "saturation_rise": ("saturation_rise", 5.0),
    "screen_lock": ("screen_click", 1.0 / FPS),
    "raw_breath": ("raw_breath", 1.0),
    "flint_strike": ("flint_strike", 0.48),
}
EXPECTED_EVENTS = [
    ("optical_lock", 60),
    ("bait_crystallization", 840),
    ("velvet_cocoon", 1_500),
    ("friction_dissolve", 2_300),
    ("island_zoom", 2_940),
    ("lonely_sonar", 3_900),
    ("saturation_rise", 4_500),
    ("screen_lock", CLICK_FRAME),
    ("raw_breath", SILENCE_END_FRAME),
    ("flint_strike", 4_900),
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
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha_bytes(data)


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    if temporary.exists():
        raise AudioBuildError(f"temporary metadata file already exists; preserved: {temporary}")
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


def mix_spec() -> dict[str, Any]:
    return {
        "fps": FPS,
        "sampleRate": SAMPLE_RATE,
        "samplesPerChannel": TOTAL_SAMPLES,
        "absoluteSilence": [SILENCE_START_SAMPLE, SILENCE_END_SAMPLE],
        "loudness": {
            "integratedLUFS": LUFS_TARGET,
            "truePeakNormalizationTargetDBTP": TRUE_PEAK_TARGET_DBTP,
            "truePeakAcceptanceDBTP": TRUE_PEAK_ACCEPTANCE_DBTP,
        },
        "scoreVoiceDuckDB": -8.0,
        "sfxVoiceDuckDB": -9.0,
    }


def mix_input_set_hash(input_hashes: dict[str, Any]) -> str:
    return canonical_hash({"inputs": input_hashes, "mix": mix_spec()})


def load_segments() -> list[dict[str, Any]]:
    try:
        segments = json.loads(SEGMENTS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AudioBuildError(f"cannot read segments.json: {exc}") from None
    if not isinstance(segments, list) or [item.get("id") for item in segments] != EXPECTED_IDS:
        raise AudioBuildError("segments.json must contain exactly S01 through S08 in source order")
    prior_end = 0
    for item in segments:
        if not isinstance(item, dict):
            raise AudioBuildError("each segments.json entry must be an object")
        for field in ("display_subtitle", "tts_phonetic_text"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise AudioBuildError(f"{item.get('id', 'segment')} needs non-empty {field}")
        start, end = item.get("startFrame"), item.get("endFrame")
        if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= TOTAL_FRAMES:
            raise AudioBuildError(f"{item['id']} has invalid frame bounds")
        if start < prior_end:
            raise AudioBuildError(f"{item['id']} overlaps the preceding declared segment window")
        chunks = item.get("chunks")
        if not isinstance(chunks, list) or not chunks or any(not isinstance(chunk, str) or not chunk.strip() for chunk in chunks):
            raise AudioBuildError(f"{item['id']} needs non-empty original caption chunks")
        if any(len(re.sub(r"\s+", "", chunk)) > 26 for chunk in chunks):
            raise AudioBuildError(f"{item['id']} has a caption chunk that cannot fit in two lines of at most 13 characters")
        prior_end = end
    if segments[-1]["endFrame"] != TOTAL_FRAMES:
        raise AudioBuildError("S08 must end at frame 5400 for the exact 90-second master")
    if segments[-1]["startFrame"] != CLICK_FRAME:
        raise AudioBuildError("S08 must retain its authored start at the frame-4860 screen lock")
    return segments


def load_events() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    authored = read_json(EVENTS_PATH, "sfx_events.json")
    if authored.get("fps") != FPS or authored.get("clickFrame") != CLICK_FRAME:
        raise AudioBuildError("sfx_events.json fps or clickFrame differs from the EP10 audio plan")
    if authored.get("absoluteSilence") != [SILENCE_START_FRAME, SILENCE_END_FRAME]:
        raise AudioBuildError("sfx_events.json absoluteSilence must be [4861,4891)")
    if authored.get("absoluteBlack") != [SILENCE_START_FRAME, SILENCE_END_FRAME]:
        raise AudioBuildError("sfx_events.json absoluteBlack must match the exact silent interval")
    source = authored.get("events")
    if not isinstance(source, list) or [(item.get("id"), item.get("frame")) for item in source] != EXPECTED_EVENTS:
        raise AudioBuildError("sfx_events.json IDs/order/frames differ from the assigned EP10 event plan")
    events: list[dict[str, Any]] = []
    for item in source:
        item_id, frame = item["id"], item["frame"]
        sample = frame * SAMPLES_PER_FRAME
        if item.get("sample") != sample:
            raise AudioBuildError(f"{item_id} sample does not equal frame*800")
        kind, duration = EVENT_PROFILES[item_id]
        start = sample
        count = round(duration * SAMPLE_RATE)
        end = start + count
        if not 0 <= frame < TOTAL_FRAMES or end > TOTAL_SAMPLES:
            raise AudioBuildError(f"{item_id} has invalid event bounds")
        if item_id == "screen_lock" and (frame != CLICK_FRAME or count != SAMPLES_PER_FRAME):
            raise AudioBuildError("screen_lock click must be confined to exactly one 60 fps frame")
        if start < SILENCE_END_SAMPLE and end > SILENCE_START_SAMPLE:
            raise AudioBuildError(f"{item_id} SFX overlaps the authored absolute-silence interval")
        events.append({
            "id": item_id,
            "frame": frame,
            "sampleIndex": start,
            "durationSeconds": duration,
            "sampleCount": count,
            "kind": kind,
            "description": item.get("description", ""),
        })
    return events, authored


def validate_authorization(segments: list[dict[str, Any]]) -> str:
    value = read_json(AUTHORIZATION_PATH, "audio-authorization.json")
    for key, expected in AUTHORIZATION_CONTRACT.items():
        if value.get(key) != expected:
            raise AudioBuildError(f"audio-authorization.json does not match current EP10 authorization field {key!r}")
    if value.get("voice") != SETTINGS["voice"]:
        raise AudioBuildError("audio-authorization.json voice differs from the EP10 packet")
    text_hash = sha_bytes(json.dumps(
        [item["tts_phonetic_text"] for item in segments], ensure_ascii=False
    ).encode("utf-8"))
    if value.get("text_sha256") != text_hash:
        raise AudioBuildError("audio-authorization.json text_sha256 does not match the exact ordered prepared texts")
    return sha_file(AUTHORIZATION_PATH)


def cache_key(text: str) -> str:
    payload = json.dumps({"text": text, "settings": SETTINGS}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha_bytes(payload.encode("utf-8"))


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
            raise AudioBuildError("cue has no measurable PCM activity above the onset threshold")
        last = last_index + 1
    return first, last, {
        "method": "5 ms sliding RMS; threshold=max(48 PCM16, 0.4% of cue peak)",
        "thresholdPcm16": threshold,
        "windowSamples": window,
    }


def read_cue(path: Path) -> tuple[array.array, dict[str, Any]]:
    try:
        with wave.open(str(path), "rb") as wav:
            params = wav.getparams()
            expected = (SAMPLE_RATE, 1, 2, "NONE")
            actual = (params.framerate, params.nchannels, params.sampwidth, params.comptype)
            if actual != expected:
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
    if not any(values):
        raise AudioBuildError(f"{path.name} is digital silence")
    return values, {
        "samples": params.nframes,
        "seconds": params.nframes / SAMPLE_RATE,
        "sha256": sha_file(path),
        "pcmSha256": sha_bytes(raw),
    }


def validate_provider_manifest(segments: list[dict[str, Any]]) -> dict[str, Any]:
    auth_hash = validate_authorization(segments)
    manifest = read_json(PROVIDER_MANIFEST, "provider-manifest.json")
    if manifest.get("settings") != SETTINGS or not isinstance(manifest.get("segments"), dict):
        raise AudioBuildError("provider manifest settings differ from the authorized EP10 TTS")
    auth = manifest.get("authorization")
    if not isinstance(auth, dict) or auth.get("sha256AtInvocation") != auth_hash:
        raise AudioBuildError("provider manifest does not bind to the current audio-authorization.json")
    if auth.get("scope") != AUTHORIZATION_CONTRACT["scope"] or auth.get("source") != AUTHORIZATION_CONTRACT["source"]:
        raise AudioBuildError("provider manifest authorization scope/source differs from the EP10 packet")
    return manifest


def cue_inventory(segments: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, array.array]]:
    manifest = validate_provider_manifest(segments)
    cues: dict[str, array.array] = {}
    inventory = []
    for segment in segments:
        sid = segment["id"]
        entry = manifest["segments"].get(sid)
        if not isinstance(entry, dict):
            raise AudioBuildError(f"provider manifest has no entry for {sid}")
        if entry.get("cache_key") != cache_key(segment["tts_phonetic_text"]):
            raise AudioBuildError(f"{sid} cache key does not match its exact prepared text")
        if entry.get("tts_phonetic_text") != segment["tts_phonetic_text"] or entry.get("settings") != SETTINGS:
            raise AudioBuildError(f"{sid} recorded text/settings differ from the EP10 source")
        if entry.get("effective_model") != [SETTINGS["effective_model"]] or entry.get("effective_voice") != [SETTINGS["voice"]]:
            raise AudioBuildError(f"NEEDS_SOL: {sid} recorded model or voice differs from the authorized selection")
        relative = entry.get("cue_path")
        if not isinstance(relative, str):
            raise AudioBuildError(f"{sid} has no cue path")
        cue_path = (PROJECT / relative).resolve()
        if not cue_path.is_relative_to(PROJECT.resolve()) or not cue_path.is_file():
            raise AudioBuildError(f"{sid} cue is missing or outside the project")
        if entry.get("cue_sha256") != sha_file(cue_path):
            raise AudioBuildError(f"{sid} cue SHA-256 differs from its provider manifest")
        cue, info = read_cue(cue_path)
        onset, active_end, measurement = active_bounds(cue)
        cues[sid] = cue
        inventory.append({
            "id": sid,
            "cueFile": str(cue_path.relative_to(WORK)),
            "cueSamplesAt48k": len(cue),
            "durationSeconds": round(len(cue) / SAMPLE_RATE, 6),
            "cueSha256": info["sha256"],
            "cuePcmSha256": info["pcmSha256"],
            "activeOnsetOffsetSamples": onset,
            "activeEndOffsetSamplesExclusive": active_end,
            "activeBoundsMethod": measurement,
        })
    return inventory, cues


def cue_timing(segments: list[dict[str, Any]], cues: dict[str, array.array], inventory: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    spans: list[dict[str, Any]] = []
    measured: list[dict[str, Any]] = []
    inventory_by_id = {item["id"]: item for item in inventory}
    for segment in segments:
        sid = segment["id"]
        cue = cues[sid]
        cue_measure = inventory_by_id[sid]
        onset = cue_measure["activeOnsetOffsetSamples"]
        active_end = cue_measure["activeEndOffsetSamplesExclusive"]
        declared_start = segment["startFrame"] * SAMPLES_PER_FRAME
        hard_end = segment["endFrame"] * SAMPLES_PER_FRAME
        if sid == "S08":
            # The complete source cue starts after the exact blackout; nothing is shifted into silence.
            cue_start = SILENCE_END_SAMPLE
            placement = "complete S08 source cue starts at frame 4891 after the exact-zero interval; source PCM preserved"
        else:
            cue_start = declared_start - onset
            placement = "measured active PCM onset aligned to the declared start frame; complete source cue preserved"
        cue_end = cue_start + len(cue)
        if cue_start < 0:
            raise AudioBuildError(f"NEEDS_SOL: {sid} measured onset would place complete cue before sample zero")
        if cue_end > hard_end:
            raise AudioBuildError(
                f"NEEDS_SOL: {sid} complete PCM ends at sample {cue_end}, beyond its declared end sample {hard_end}; "
                "the cue was not shifted, accelerated, truncated, or stretched"
            )
        if sid != "S08" and cue_start < SILENCE_END_SAMPLE and cue_end > SILENCE_START_SAMPLE:
            raise AudioBuildError(f"NEEDS_SOL: {sid} complete PCM overlaps the authored absolute-silence interval")
        spans.append({
            "segmentId": sid,
            "startSample": cue_start,
            "sampleCount": len(cue),
            "cue": cue,
            "cuePath": cue_measure["cueFile"],
        })
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
            "placement": placement,
            "onsetMeasurement": cue_measure["activeBoundsMethod"],
        })
    spans.sort(key=lambda item: item["startSample"])
    for previous, current in zip(spans, spans[1:]):
        if previous["startSample"] + previous["sampleCount"] > current["startSample"]:
            raise AudioBuildError(f"NEEDS_SOL: complete narration PCM overlaps between {previous['segmentId']} and {current['segmentId']}")
    return spans, measured


def write_stereo(path: Path, block_iter: Iterable[bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        for block in block_iter:
            wav.writeframesraw(block)


def render_narration(path: Path, spans: list[dict[str, Any]]) -> dict[str, Any]:
    def blocks() -> Iterable[bytes]:
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


def smooth_array(value: Any) -> Any:
    x = np.clip(value, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def ramp_array(frame: Any, start: int, end: int) -> Any:
    return smooth_array((frame - start) / max(1, end - start))


def voice_gain_array(samples: Any, measured: list[dict[str, Any]], attenuation_db: float = -8.0) -> Any:
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


def score_block(samples: Any, measured: list[dict[str, Any]]) -> tuple[Any, Any]:
    time = samples / SAMPLE_RATE
    frame = samples / SAMPLES_PER_FRAME
    fade_in = ramp_array(frame, 40, 240)
    sweet = ramp_array(frame, 720, 840) * (1.0 - ramp_array(frame, 3960, 4380))
    velvet = ramp_array(frame, 1500, 1740) * (1.0 - ramp_array(frame, 3960, 4380))
    rise = ramp_array(frame, 4140, 4500) * (1.0 - ramp_array(frame, 4740, 4860))
    vibrato = 0.012 * np.sin(2.0 * np.pi * 4.7 * time)
    low_pad = (
        0.40 * np.sin(2.0 * np.pi * 110.0 * time + vibrato)
        + 0.27 * np.sin(2.0 * np.pi * 164.81 * time + 1.4 * vibrato + 0.12)
        + 0.19 * np.sin(2.0 * np.pi * 220.0 * time + 2.0 * vibrato + 0.24)
        + 0.10 * np.sin(2.0 * np.pi * 329.63 * time + 2.8 * vibrato + 0.36)
    )
    bell_warmth = (
        0.50 * np.sin(2.0 * np.pi * 261.63 * time + 0.12)
        + 0.32 * np.sin(2.0 * np.pi * 392.0 * time + 0.31)
        + 0.18 * np.sin(2.0 * np.pi * 329.63 * time + 0.48)
    )
    cocoon = (
        0.52 * np.sin(2.0 * np.pi * 58.27 * time)
        + 0.29 * np.sin(2.0 * np.pi * 87.31 * time + 0.22)
        + 0.19 * np.sin(2.0 * np.pi * 116.54 * time + 0.47)
    )
    euphoric = (
        0.48 * np.sin(2.0 * np.pi * (110.0 * time + 8.0 * time * time))
        + 0.31 * np.sin(2.0 * np.pi * (164.81 * time + 10.5 * time * time) + 0.3)
        + 0.21 * np.sin(2.0 * np.pi * (220.0 * time + 12.0 * time * time) + 0.6)
    )
    pulse = 0.83 + 0.17 * np.sin(2.0 * np.pi * 0.12 * time + 0.7)
    value = fade_in * (0.048 * low_pad + 0.012 * sweet * bell_warmth + 0.022 * velvet * cocoon + 0.021 * rise * euphoric)
    value *= pulse
    score_end = np.clip((4860.0 - frame) / 120.0, 0.0, 1.0)
    duck = voice_gain_array(samples, measured, attenuation_db=-8.0)
    value *= score_end * duck
    # EP10 resolves to silence and raw post-blackout sounds; the lush score never resumes.
    value[frame >= 4860.0] = 0.0
    pan = 0.035 * np.sin(2.0 * np.pi * 0.035 * time)
    return value * (0.99 - pan), value * (0.99 + pan)


def render_score(path: Path, measured: list[dict[str, Any]]) -> dict[str, Any]:
    def blocks() -> Iterable[bytes]:
        for block_start in range(0, TOTAL_SAMPLES, BLOCK_SAMPLES):
            count = min(BLOCK_SAMPLES, TOTAL_SAMPLES - block_start)
            samples = np.arange(block_start, block_start + count, dtype=np.int64)
            left, right = score_block(samples, measured)
            stereo = np.column_stack((left, right))
            yield np.clip(np.rint(stereo * 32767.0), -32768, 32767).astype("<i2").tobytes()
    write_stereo(path, blocks())
    info = validate_wav(path, stereo=True)
    info["design"] = {
        "description": "Deterministic warm, low-passed harmonic pad and cocoon with a controlled rise; the seductive score fades to zero at the screen lock and never continues after blackout.",
        "maximumDesignedToneHz": 392.0,
        "voiceDuckDB": -8.0,
        "voicePreattackMilliseconds": 60,
        "voiceReleaseMilliseconds": 350,
        "afterBlackout": "digital silence; sparse raw breath and flint live in the separate SFX stem",
        "stereo": "subtle deterministic low-frequency pan",
    }
    return info


def deterministic_noise(count: int, seed: int) -> Any:
    state = seed & 0xFFFFFFFF or 1
    values = np.empty(count, dtype=np.float32)
    for index in range(count):
        state ^= (state << 13) & 0xFFFFFFFF
        state ^= state >> 17
        state ^= (state << 5) & 0xFFFFFFFF
        values[index] = ((state & 0xFFFF) / 32767.5) - 1.0
    return values


def event_value(kind: str, count: int, duration: float, event_id: str) -> tuple[Any, Any]:
    t = np.arange(count, dtype=np.float64) / SAMPLE_RATE
    progress = np.clip(t / max(duration, 1.0 / SAMPLE_RATE), 0.0, 1.0)
    if kind == "screen_click":
        seed = sum((i + 1) * byte for i, byte in enumerate(event_id.encode("utf-8")))
        noise = deterministic_noise(count, seed)
        envelope = np.exp(-t * 190.0)
        click = 0.040 * noise * envelope + 0.060 * np.sin(2.0 * np.pi * 1_180.0 * t) * np.exp(-t * 260.0)
        return click, click * 0.96
    if kind == "raw_breath":
        seed = sum((i + 1) * byte for i, byte in enumerate(event_id.encode("utf-8")))
        noise = deterministic_noise(count, seed)
        filtered = np.convolve(noise, np.ones(25, dtype=np.float32) / 25.0, mode="same")
        swell = np.sin(np.pi * np.clip(progress, 0.0, 1.0)) ** 1.3
        breath = swell * (0.030 * filtered + 0.009 * np.sin(2.0 * np.pi * 112.0 * t + 0.2))
        pan = 0.03 * np.sin(2.0 * np.pi * 0.8 * t)
        return breath * (0.97 - pan), breath * (0.97 + pan)
    if kind == "flint_strike":
        seed = sum((i + 1) * byte for i, byte in enumerate(event_id.encode("utf-8")))
        noise = deterministic_noise(count, seed)
        transient = np.exp(-t * 32.0)
        spark = 0.030 * noise * transient + 0.035 * np.sin(2.0 * np.pi * 1_040.0 * t) * np.exp(-t * 24.0)
        return spark, spark * 0.91

    attack = smooth_array(np.minimum(1.0, t / min(0.04, duration * 0.15)))
    release = np.clip((duration - t) / min(0.5, duration * 0.22), 0.0, 1.0)
    env = attack * release
    if kind == "focus_lock":
        sweep = np.sin(2.0 * np.pi * (220.0 * t + 38.0 * t * t / duration))
        tone = 0.65 * sweep + 0.35 * np.sin(2.0 * np.pi * 660.0 * t + 0.15)
        left, right = env * 0.065 * tone, env * 0.062 * (0.94 * tone + 0.06 * np.sin(2.0 * np.pi * 523.25 * t))
    elif kind == "crystal_bloom":
        bloom = (0.46 * np.sin(2.0 * np.pi * 196.0 * t)
                 + 0.31 * np.sin(2.0 * np.pi * 293.66 * t + 0.2)
                 + 0.23 * np.sin(2.0 * np.pi * 392.0 * t + 0.45))
        glint = np.sin(np.pi * progress) ** 1.4
        left, right = env * glint * 0.070 * bloom, env * glint * 0.067 * (0.96 * bloom + 0.04 * np.sin(2.0 * np.pi * 587.33 * t))
    elif kind == "velvet_pad":
        wave = (0.48 * np.sin(2.0 * np.pi * 110.0 * t)
                + 0.31 * np.sin(2.0 * np.pi * 164.81 * t + 0.14)
                + 0.21 * np.sin(2.0 * np.pi * 220.0 * t + 0.28))
        mod = 0.76 + 0.24 * np.sin(2.0 * np.pi * 0.18 * t + 0.5)
        left, right = env * mod * 0.068 * wave, env * mod * 0.066 * (wave + 0.025 * np.sin(2.0 * np.pi * 329.63 * t))
    elif kind == "edge_dissolve":
        edge = (0.47 * np.sin(2.0 * np.pi * 293.66 * t) * np.exp(-1.7 * t)
                + 0.32 * np.sin(2.0 * np.pi * 440.0 * t + 0.2) * np.exp(-2.4 * t)
                + 0.21 * np.sin(2.0 * np.pi * 587.33 * t + 0.48) * np.exp(-3.0 * t))
        left, right = env * 0.062 * edge, env * 0.060 * (0.94 * edge + 0.06 * np.sin(2.0 * np.pi * 392.0 * t))
    elif kind == "island_zoom":
        drone = (0.63 * np.sin(2.0 * np.pi * 55.0 * t)
                 + 0.25 * np.sin(2.0 * np.pi * 82.41 * t + 0.2)
                 + 0.12 * np.sin(2.0 * np.pi * 110.0 * t + 0.4))
        bubble = np.exp(-((t - 0.55) / 0.16) ** 2) + 0.62 * np.exp(-((t - 1.9) / 0.24) ** 2)
        left, right = env * 0.065 * (drone + 0.09 * bubble * np.sin(2.0 * np.pi * 261.63 * t)), env * 0.063 * (drone + 0.08 * bubble * np.sin(2.0 * np.pi * 233.08 * t + 0.2))
    elif kind == "lonely_sonar":
        sonar = (0.68 * np.sin(2.0 * np.pi * 174.61 * t) * np.exp(-1.35 * t)
                 + 0.32 * np.sin(2.0 * np.pi * 349.23 * t + 0.12) * np.exp(-2.1 * t))
        left, right = env * 0.070 * sonar, env * 0.066 * sonar
    elif kind == "saturation_rise":
        frequency = 65.0 + 330.0 * progress
        phase = 2.0 * np.pi * (65.0 * t + 0.5 * 330.0 * t * t / duration)
        rise = 0.68 * np.sin(phase) + 0.32 * np.sin(2.0 * phase + 0.3)
        left, right = env * (0.058 + 0.018 * progress) * rise, env * (0.056 + 0.017 * progress) * (0.95 * rise + 0.05 * np.sin(2.0 * np.pi * 261.63 * t))
    else:
        raise AudioBuildError(f"unknown deterministic SFX kind {kind}")
    return left, right


def voice_gain_for_event(sample_indices: Any, measured: list[dict[str, Any]]) -> Any:
    return voice_gain_array(sample_indices, measured, attenuation_db=-9.0)


def render_sfx(path: Path, events: list[dict[str, Any]], measured: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    left = np.zeros(TOTAL_SAMPLES, dtype=np.float32)
    right = np.zeros(TOTAL_SAMPLES, dtype=np.float32)
    onsets = []
    for event in events:
        start = event["sampleIndex"]
        count = event["sampleCount"]
        end = start + count
        if start < SILENCE_END_SAMPLE and end > SILENCE_START_SAMPLE:
            raise AudioBuildError(f"{event['id']} overlaps authored absolute silence")
        lval, rval = event_value(event["kind"], count, event["durationSeconds"], event["id"])
        duck = voice_gain_for_event(np.arange(start, end, dtype=np.int64), measured)
        left[start:end] += (lval * duck).astype(np.float32)
        right[start:end] += (rval * duck).astype(np.float32)
        onsets.append({
            "id": event["id"],
            "frame": event["frame"],
            "sampleIndex": start,
            "durationSeconds": event["durationSeconds"],
            "sampleCount": count,
            "kind": event["kind"],
            "description": event["description"],
        })

    def blocks() -> Iterable[bytes]:
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
        "description": "Deterministic, low-frequency focus, crystalline bait, velvet pad, edge dissolve, island drone, sonar, saturation rise, one-frame screen click, raw breath, and flint strike.",
        "events": onsets,
        "silenceWindowFrames": [SILENCE_START_FRAME, SILENCE_END_FRAME],
        "voiceDuckDB": -9.0,
        "noiseSource": "fixed xorshift32 seed derived from event ID; no runtime random source",
        "postBlackout": ["raw_breath", "flint_strike"],
    }
    return info, onsets


def validate_wav(path: Path, *, stereo: bool, logical_path: str | None = None) -> dict[str, Any]:
    try:
        with wave.open(str(path), "rb") as wav:
            params = wav.getparams()
            channels = 2 if stereo else 1
            expected = (SAMPLE_RATE, channels, 2, TOTAL_SAMPLES, "NONE")
            actual = (params.framerate, params.nchannels, params.sampwidth, params.nframes, params.comptype)
            if actual != expected:
                raise AudioBuildError(f"{path.name} must be {expected}; got {actual}")
            raw = wav.readframes(params.nframes)
    except (OSError, wave.Error) as exc:
        raise AudioBuildError(f"cannot read WAV {path}: {exc}") from None
    if len(raw) != TOTAL_SAMPLES * channels * 2:
        raise AudioBuildError(f"{path.name} PCM payload is incomplete")
    values = array.array("h")
    values.frombytes(raw)
    if sys.byteorder != "little":
        values.byteswap()
    peak = max((abs(value) for value in values), default=0)
    return {
        "file": logical_path or path.name,
        "sha256": sha_file(path),
        "pcmSha256": sha_bytes(raw),
        "sizeBytes": path.stat().st_size,
        "sampleRate": SAMPLE_RATE,
        "channels": channels,
        "sampleWidthBytes": 2,
        "samplesPerChannel": TOTAL_SAMPLES,
        "durationSeconds": TOTAL_SAMPLES / SAMPLE_RATE,
        "samplePeakPcm16": peak,
    }


def verify_silence(path: Path) -> int:
    try:
        with wave.open(str(path), "rb") as wav:
            params = wav.getparams()
            expected = (SAMPLE_RATE, 2, 2, TOTAL_SAMPLES, "NONE")
            actual = (params.framerate, params.nchannels, params.sampwidth, params.nframes, params.comptype)
            if actual != expected:
                raise AudioBuildError(f"{path.name} has unexpected format before silence verification")
            wav.setpos(SILENCE_START_SAMPLE)
            raw = wav.readframes(SILENCE_END_SAMPLE - SILENCE_START_SAMPLE)
    except (OSError, wave.Error) as exc:
        raise AudioBuildError(f"cannot read silence interval from {path.name}: {exc}") from None
    values = array.array("h")
    values.frombytes(raw)
    peak = max((abs(value) for value in values), default=0)
    if peak:
        raise AudioBuildError(f"{path.name} is not exact zero over frames [4861,4891); PCM16 peak={peak}")
    return 0


def verify_click(path: Path) -> int:
    try:
        with wave.open(str(path), "rb") as wav:
            params = wav.getparams()
            expected = (SAMPLE_RATE, 2, 2, TOTAL_SAMPLES, "NONE")
            actual = (params.framerate, params.nchannels, params.sampwidth, params.nframes, params.comptype)
            if actual != expected:
                raise AudioBuildError(f"{path.name} has unexpected format before screen-lock verification")
            wav.setpos(CLICK_FRAME * SAMPLES_PER_FRAME)
            raw = wav.readframes(SAMPLES_PER_FRAME)
    except (OSError, wave.Error) as exc:
        raise AudioBuildError(f"cannot read screen-lock frame from {path.name}: {exc}") from None
    values = array.array("h")
    values.frombytes(raw)
    peak = max((abs(value) for value in values), default=0)
    if peak == 0:
        raise AudioBuildError(f"{path.name} lost the screen-lock click in frame {CLICK_FRAME}")
    return peak


def enforce_master_silence(path: Path) -> None:
    replacement = path.with_name(path.stem + ".silence.tmp.wav")
    if replacement.exists():
        raise AudioBuildError(f"master silence temporary already exists; preserved: {replacement}")
    try:
        with wave.open(str(path), "rb") as src:
            params = src.getparams()
            expected = (SAMPLE_RATE, 2, 2, TOTAL_SAMPLES, "NONE")
            actual = (params.framerate, params.nchannels, params.sampwidth, params.nframes, params.comptype)
            if actual != expected:
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
    """Apply a scalar gain to the master only while preserving its exact-zero interval."""
    gain = 10.0 ** (gain_db / 20.0)
    if not math.isfinite(gain) or gain <= 0:
        raise AudioBuildError("master calibration gain is invalid")
    try:
        with wave.open(str(source), "rb") as wav:
            params = wav.getparams()
            expected = (SAMPLE_RATE, 2, 2, TOTAL_SAMPLES, "NONE")
            actual = (params.framerate, params.nchannels, params.sampwidth, params.nframes, params.comptype)
            if actual != expected:
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
    text = run_ffmpeg([
        ffmpeg, "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-",
    ], "EBU R128 verification")
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
    if calibrated_path.exists():
        raise AudioBuildError(f"master calibration temporary already exists; preserved: {calibrated_path}")
    try:
        calibration = calibrate_master_pcm(path, calibrated_path, LUFS_TARGET - before_calibration["integratedLUFS"])
        calibrated_path.replace(path)
    finally:
        calibrated_path.unlink(missing_ok=True)
    run_ffmpeg([ffmpeg, "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"], "strict PCM master decode")
    wav_info = validate_wav(path, stereo=True)
    loudness = ebur128(path)
    if not LUFS_TARGET - LUFS_TOLERANCE <= loudness["integratedLUFS"] <= LUFS_TARGET + LUFS_TOLERANCE:
        raise AudioBuildError(f"master loudness {loudness['integratedLUFS']} LUFS is outside -16 LUFS ±0.2")
    if loudness["truePeakDBTP"] > TRUE_PEAK_ACCEPTANCE_DBTP:
        raise AudioBuildError(f"master true peak {loudness['truePeakDBTP']} dBTP exceeds -1.0 dBTP")
    calibration.update({
        "measuredBefore": before_calibration,
        "measuredAfter": loudness,
        "method": "linear PCM gain by final measured LUFS difference",
        "targetIntegratedLUFS": LUFS_TARGET,
        "sampleCountPreserved": True,
        "stemsChanged": False,
    })
    return {
        **wav_info,
        "strictDecode": "passed",
        "loudnormFirstPass": measured,
        "loudnormSecondPass": second_measurement,
        "ebur128Final": loudness,
        "normalizationTarget": {
            "integratedLUFS": LUFS_TARGET,
            "truePeakDBTP": TRUE_PEAK_TARGET_DBTP,
            "acceptanceLUFS": [LUFS_TARGET - LUFS_TOLERANCE, LUFS_TARGET + LUFS_TOLERANCE],
            "acceptanceTruePeakDBTP": TRUE_PEAK_ACCEPTANCE_DBTP,
            "passes": 2,
        },
        "postLoudnormCalibration": calibration,
        "absoluteSilence": {
            "startSample": SILENCE_START_SAMPLE,
            "endSampleExclusive": SILENCE_END_SAMPLE,
            "peakPcm16": verify_silence(path),
            "exactZero": True,
        },
    }


def caption_lines(source: str) -> str:
    clean = re.sub(r"\s+", "", source)
    if not clean:
        return ""
    if len(clean) <= 13:
        return clean
    if len(clean) > 26:
        raise AudioBuildError(f"caption chunk cannot fit in at most two 13-character lines: {source!r}")
    return clean[:13] + "\n" + clean[13:]


def build_captions(segments: list[dict[str, Any]], measured: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {item["id"]: item for item in measured}
    result = []
    for segment in segments:
        item = by_id[segment["id"]]
        phrase_texts = [caption_lines(chunk) for chunk in segment["chunks"]]
        phrase_texts = [text for text in phrase_texts if text]
        if not phrase_texts:
            raise AudioBuildError(f"{segment['id']} produces no visible caption phrases")
        weights = [max(1, len(text.replace("\n", ""))) for text in phrase_texts]
        total_weight = sum(weights)
        start_frame = math.ceil(item["voiceStartSample"] / SAMPLES_PER_FRAME)
        end_frame = item["voiceEndSampleExclusive"] // SAMPLES_PER_FRAME
        span_frames = end_frame - start_frame
        if span_frames < len(phrase_texts):
            raise AudioBuildError(f"{segment['id']} active PCM has fewer frames than its caption chunks")
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
                raise AudioBuildError(f"caption line exceeds 13 characters or two lines: {text!r}")
            result.append({
                "segmentId": segment["id"],
                "startFrame": previous,
                "endFrame": current_end,
                "text": text,
                "alignment": "estimated_character_weighted_within_measured_pcm_span",
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


def render_srt(captions: list[dict[str, Any]]) -> str:
    rows = []
    for index, caption in enumerate(captions, 1):
        rows.extend((
            str(index),
            f"{frame_srt_time(caption['startFrame'])} --> {frame_srt_time(caption['endFrame'])}",
            caption["text"],
            "",
        ))
    return "\n".join(rows)


def ensure_no_outputs_without_manifest() -> None:
    output_paths = [AUDIO / f"{name}.wav" for name in ("narration", "score", "sfx", "master")]
    metadata_paths = [TIMING_PATH, MIX_SETTINGS_PATH, MIX_MANIFEST_PATH, QA_PATH, SRT_PATH]
    existing_outputs = [path for path in output_paths if path.exists()]
    if MIX_MANIFEST_PATH.exists():
        old = read_json(MIX_MANIFEST_PATH, "mix-manifest.json")
        if old.get("status") != "built":
            raise AudioBuildError("existing mix manifest is not verified as built; preserved")
        missing = [path for path in output_paths if not path.is_file()]
        if missing:
            raise AudioBuildError(f"existing mix manifest has a missing output; preserved: {missing[0]}")
        for path in existing_outputs:
            expected = old.get("outputs", {}).get(path.stem, {}).get("sha256")
            if expected != sha_file(path):
                raise AudioBuildError(f"existing {path.name} differs from its manifest; preserved")
        raise AudioBuildError("a verified audio mix already exists; no output was overwritten")
    existing = existing_outputs + [path for path in metadata_paths if path.exists()]
    if existing:
        raise AudioBuildError(f"audio output exists without a matching mix manifest; preserved: {existing[0]}")
    for name in ("narration", "score", "sfx", "master"):
        staged = AUDIO / f"{name}.publish.tmp.wav"
        if staged.exists():
            raise AudioBuildError(f"staged output exists without a completed publish manifest; preserved: {staged}")


def agentdev_scratch_parent() -> Path:
    value = os.environ.get("TMPDIR")
    if not value:
        raise AudioBuildError("TMPDIR is unset; run the audio build through agent-dev run so scratch files stay on AgentDev")
    temp = Path(value).resolve()
    root = AGENTDEV_ROOT.resolve()
    if not temp.is_relative_to(root) or not temp.is_dir():
        raise AudioBuildError("TMPDIR is not a mounted directory under /Volumes/AgentDev; no audio build started")
    return temp


def file_record(path: Path, logical_path: str, *, stereo: bool = True) -> dict[str, Any]:
    return validate_wav(path, stereo=stereo, logical_path=logical_path)


def publish_outputs(scratch: Path, output_infos: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    AUDIO.mkdir(parents=True, exist_ok=True)
    staged: dict[str, Path] = {}
    created: list[Path] = []
    targets = {name: AUDIO / f"{name}.wav" for name in output_infos}
    try:
        for name, target in targets.items():
            if target.exists():
                raise AudioBuildError(f"existing {target.name} would be overwritten; preserved")
            temporary = AUDIO / f"{name}.publish.tmp.wav"
            if temporary.exists():
                raise AudioBuildError(f"existing staged file would be overwritten; preserved: {temporary}")
            source = scratch / f"{name}.wav"
            with source.open("rb") as src:
                with temporary.open("xb") as dst:
                    created.append(temporary)
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
                    dst.flush()
                    os.fsync(dst.fileno())
            shutil.copystat(source, temporary)
            expected = output_infos[name]["sha256"]
            if sha_file(temporary) != expected:
                raise AudioBuildError(f"copied {name}.wav differs from the measured scratch output")
            validate_wav(temporary, stereo=True)
            staged[name] = temporary
        for name, target in targets.items():
            if target.exists():
                raise AudioBuildError(f"destination appeared during publish; preserved: {target}")
            staged[name].replace(target)
            output_infos[name]["file"] = str(target.relative_to(WORK))
            output_infos[name]["sizeBytes"] = target.stat().st_size
        return output_infos
    finally:
        for temporary in created:
            temporary.unlink(missing_ok=True)


def run_mix(segments: list[dict[str, Any]], events: list[dict[str, Any]]) -> int:
    ensure_no_outputs_without_manifest()
    inventory, cues = cue_inventory(segments)
    spans, segment_timing = cue_timing(segments, cues, inventory)
    captions = build_captions(segments, segment_timing)
    scratch_parent = agentdev_scratch_parent()
    AUDIO.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="si-ep10-audio-", dir=str(scratch_parent)) as scratch_name:
        scratch = Path(scratch_name)
        outputs: dict[str, Any] = {}
        outputs["narration"] = render_narration(scratch / "narration.wav", spans)
        outputs["score"] = render_score(scratch / "score.wav", segment_timing)
        outputs["sfx"], sfx_onsets = render_sfx(scratch / "sfx.wav", events, segment_timing)
        for name in ("narration", "score", "sfx"):
            verify_silence(scratch / f"{name}.wav")
        sfx_click_peak = verify_click(scratch / "sfx.wav")
        outputs["master"] = mix_master(scratch / "master.wav", [scratch / name for name in ("narration.wav", "score.wav", "sfx.wav")])
        master_click_peak = verify_click(scratch / "master.wav")
        for name in ("narration", "score", "sfx", "master"):
            if outputs[name]["sizeBytes"] >= 100 * 1024 * 1024:
                raise AudioBuildError(f"{name}.wav unexpectedly exceeds the 100 MiB tracked-audio limit")
        input_hashes = {
            "segmentsJson": sha_file(SEGMENTS_PATH),
            "sfxEventsJson": sha_file(EVENTS_PATH),
            "audioAuthorization": sha_file(AUTHORIZATION_PATH),
            "providerManifest": sha_file(PROVIDER_MANIFEST),
            "cueWavs": inventory,
            "eventProfiles": canonical_hash(EVENT_PROFILES),
        }
        input_set_hash = mix_input_set_hash(input_hashes)
        outputs = publish_outputs(scratch, outputs)
        silence = {
            "startFrame": SILENCE_START_FRAME,
            "endFrameExclusive": SILENCE_END_FRAME,
            "startSample": SILENCE_START_SAMPLE,
            "endSampleExclusive": SILENCE_END_SAMPLE,
            "samplesZeroInAllStemsAndMaster": True,
            "samplePeakPcm16": 0,
        }
        timing = {
            "durationSeconds": DURATION_SECONDS,
            "fps": FPS,
            "sampleRate": SAMPLE_RATE,
            "samplesPerFrame": SAMPLES_PER_FRAME,
            "samplesPerChannel": TOTAL_SAMPLES,
            "status": "measured_pcm_with_estimated_phrase_timing",
            "captionTimingMethod": "Original source chunks are allocated by character weight only within measured active PCM spans; no ASR or forced word alignment was performed.",
            "segments": segment_timing,
            "captions": captions,
            "sfxEvents": sfx_onsets,
            "absoluteSilence": silence,
            "sourceHashes": input_hashes,
            "mixInputSetSha256": input_set_hash,
            "master": outputs["master"],
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
            "absoluteSilence": silence,
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
            "absoluteSilence": silence,
            "audioTiming": str(TIMING_PATH.relative_to(WORK)),
            "authorization": str(AUTHORIZATION_PATH.relative_to(WORK)),
        }
        qa = {
            "status": "technical_audio_checks_passed",
            "durationSeconds": DURATION_SECONDS,
            "fps": FPS,
            "sampleRate": SAMPLE_RATE,
            "samplesPerChannel": TOTAL_SAMPLES,
            "completeCueCount": len(segment_timing),
            "cuePlacement": "all complete source cues retained; S01-S07 measured active onset aligned to declared start; S08 complete cue starts at frame 4891 after blackout",
            "captions": {
                "count": len(captions),
                "linesMaximumCharacters": 13,
                "linesMaximumPerCaption": 2,
                "alignment": "estimated character-weighted timing; not ASR or forced alignment",
            },
            "screenLock": {
                "startFrame": CLICK_FRAME,
                "startSample": CLICK_FRAME * SAMPLES_PER_FRAME,
                "sampleCount": SAMPLES_PER_FRAME,
                "endsAtFrame": SILENCE_START_FRAME,
                "sfxSamplePeakPcm16": sfx_click_peak,
                "masterSamplePeakPcm16": master_click_peak,
                "clickRetained": True,
            },
            "absoluteSilence": silence,
            "masterLoudness": outputs["master"]["ebur128Final"],
            "normalizationTarget": outputs["master"]["normalizationTarget"],
            "screenLockSamplePeakPcm16": {"sfx": sfx_click_peak, "master": master_click_peak},
            "outputs": outputs,
            "sourceHashes": input_hashes,
            "mixInputSetSha256": input_set_hash,
        }
        srt_text = render_srt(captions)
        srt_tmp = SRT_PATH.with_name(SRT_PATH.name + ".tmp")
        if SRT_PATH.exists() or srt_tmp.exists():
            raise AudioBuildError(f"existing subtitle output would be overwritten; preserved: {SRT_PATH}")
        srt_tmp.parent.mkdir(parents=True, exist_ok=True)
        srt_tmp.write_text(srt_text, encoding="utf-8")
        srt_tmp.replace(SRT_PATH)
        write_json(TIMING_PATH, timing)
        write_json(MIX_SETTINGS_PATH, mix_settings)
        write_json(MIX_MANIFEST_PATH, manifest)
        write_json(QA_PATH, qa)
        print(json.dumps({
            "status": "mix_complete",
            "durationSeconds": DURATION_SECONDS,
            "samplesPerChannel": TOTAL_SAMPLES,
            "cueCount": len(segment_timing),
            "captionCount": len(captions),
            "master": outputs["master"],
            "absoluteSilence": silence,
            "masterLoudness": outputs["master"]["ebur128Final"],
        }, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--mix", action="store_true", help="build the exact 90-second PCM stems/master from verified local cues")
    modes.add_argument("--audit-cues", action="store_true", help="read and report verified cue file measurements only")
    args = parser.parse_args()
    try:
        segments = load_segments()
        events, _ = load_events()
        if args.audit_cues:
            inventory, _ = cue_inventory(segments)
            print(json.dumps({"status": "cues_measured", "cueCount": len(inventory), "cues": inventory}, ensure_ascii=False, indent=2))
            return 0
        global np
        try:
            import numpy as np
        except ImportError as exc:
            raise AudioBuildError("NumPy is required for deterministic DSP; use the configured bundled Python runtime, do not install dependencies") from exc
        return run_mix(segments, events)
    except (AudioBuildError, OSError, ValueError, wave.Error, OverflowError, subprocess.SubprocessError) as exc:
        print(f"build_audio.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
