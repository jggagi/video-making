#!/usr/bin/env python3
"""Build EP13's exact 90-second narration, procedural audio stems, captions, and PCM master."""

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
TIMING_OVERRIDES_PATH = PROJECT / "audio-timing-overrides.json"
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
SILENCE_START_FRAME = 4_860
SILENCE_END_FRAME = 4_890
SILENCE_START_SAMPLE = SILENCE_START_FRAME * SAMPLES_PER_FRAME
SILENCE_END_SAMPLE = SILENCE_END_FRAME * SAMPLES_PER_FRAME
MIN_S08_VOICE_START_FRAME = 4_902
MIN_S08_VOICE_START_SAMPLE = MIN_S08_VOICE_START_FRAME * SAMPLES_PER_FRAME
SNAP_BOUNDARY_FRAME = SILENCE_START_FRAME
SNAP_ATTACK_FRAME = SNAP_BOUNDARY_FRAME - 1
PIANO_START_FRAME = SILENCE_END_FRAME
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
    "scope": "EP13 S01 through S08 exact prepared tts_phonetic_text",
    "authorized": True,
    "source": "Standing video-making voiceover authorization in skills/voiceover/SKILL.md (2026-10-20); current EP13 Task Packet",
}
EVENT_PROFILES = {
    "rewind_calibration": ("cassette_rewind_calibration", 3.2),
    "warm_filtered_chord": ("warm_filtered_chord", 4.4),
    "tape_hiss": ("tape_hiss", 7.0),
    "magnetic_relay": ("magnetic_relay", 1.2),
    "hv_phase_lock": ("hv_phase_lock", 3.0),
    "nondecaying_loops": ("nondecaying_loops", 32.0),
    "shepard_tube": ("shepard_tube", 10.0),
    "harmonic_peak": ("harmonic_peak", 6.0),
    "crt_power_off_snap": ("crt_power_off_snap", 1.0 / FPS),
    "warm_piano_chord": ("warm_piano_chord", 8.5),
}
EXPECTED_EVENTS = [
    ("rewind_calibration", 60),
    ("warm_filtered_chord", 840),
    ("tape_hiss", 1_500),
    ("magnetic_relay", 1_920),
    ("hv_phase_lock", 2_160),
    ("nondecaying_loops", 2_940),
    ("shepard_tube", 3_900),
    ("harmonic_peak", 4_500),
    ("crt_power_off_snap", SNAP_BOUNDARY_FRAME),
    ("warm_piano_chord", PIANO_START_FRAME),
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
        normalized_display = re.sub(r"\s+", "", item["display_subtitle"])
        normalized_chunks = "".join(re.sub(r"\s+", "", chunk) for chunk in chunks)
        if normalized_chunks != normalized_display:
            raise AudioBuildError(f"{item['id']} caption chunks do not preserve the exact display_subtitle text")
        prior_end = end
    if segments[-1]["endFrame"] != TOTAL_FRAMES:
        raise AudioBuildError("S08 must end at frame 5400 for the exact 90-second master")
    if segments[-1]["startFrame"] != SILENCE_START_FRAME:
        raise AudioBuildError("S08 must retain its authored start at frame 4860")
    return segments


def load_events() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    authored = read_json(EVENTS_PATH, "sfx_events.json")
    if authored.get("fps") != FPS or authored.get("sampleRate") != SAMPLE_RATE or authored.get("samplesPerFrame") != SAMPLES_PER_FRAME:
        raise AudioBuildError("sfx_events.json timing units differ from the EP13 60 fps / 48 kHz audio plan")
    expected_silence = {
        "startFrame": SILENCE_START_FRAME,
        "endFrameExclusive": SILENCE_END_FRAME,
        "startSample": SILENCE_START_SAMPLE,
        "endSampleExclusive": SILENCE_END_SAMPLE,
        "scope": ["narration", "score", "sfx", "master"],
        "requireExactZero": True,
    }
    if authored.get("absoluteSilence") != expected_silence:
        raise AudioBuildError("sfx_events.json absoluteSilence must identify exact frames [4860,4890) and samples [3888000,3912000)")
    if authored.get("voiceMinimumOnsetFrame") != MIN_S08_VOICE_START_FRAME:
        raise AudioBuildError("sfx_events.json voiceMinimumOnsetFrame must be frame 4902")
    source = authored.get("events")
    if not isinstance(source, list) or [(item.get("id"), item.get("frame")) for item in source] != EXPECTED_EVENTS:
        raise AudioBuildError("sfx_events.json IDs/order/frames differ from the assigned EP13 event plan")
    if authored.get("snapBoundary") != {
        "anchorFrame": SNAP_BOUNDARY_FRAME,
        "attackStartFrame": SNAP_ATTACK_FRAME,
        "attackStartSample": SNAP_ATTACK_FRAME * SAMPLES_PER_FRAME,
        "endSampleExclusive": SILENCE_START_SAMPLE,
        "detail": "The snap attack occupies the final 800 samples before frame 4860; its transient ends exactly where [4860,4890) absolute silence begins.",
    }:
        raise AudioBuildError("sfx_events.json snapBoundary must end its transient exactly at sample 3888000")
    events: list[dict[str, Any]] = []
    for item in source:
        item_id, frame = item["id"], item["frame"]
        sample = frame * SAMPLES_PER_FRAME
        if item.get("sample") != sample:
            raise AudioBuildError(f"{item_id} sample does not equal frame*800")
        kind, duration = EVENT_PROFILES[item_id]
        if item.get("kind") != kind or item.get("durationSeconds") != duration:
            raise AudioBuildError(f"{item_id} kind or duration differs from the assigned EP13 event plan")
        start_frame = SNAP_ATTACK_FRAME if item_id == "crt_power_off_snap" else frame
        if item.get("startFrame", frame) != start_frame:
            raise AudioBuildError(f"{item_id} startFrame differs from the assigned EP13 event plan")
        start = start_frame * SAMPLES_PER_FRAME
        count = round(duration * SAMPLE_RATE)
        end = start + count
        if not 0 <= frame < TOTAL_FRAMES or end > TOTAL_SAMPLES:
            raise AudioBuildError(f"{item_id} has invalid event bounds")
        if item_id == "crt_power_off_snap" and (start != SNAP_ATTACK_FRAME * SAMPLES_PER_FRAME or end != SILENCE_START_SAMPLE):
            raise AudioBuildError("the CRT snap must occupy exactly the 800 samples before the absolute-silence boundary")
        if start < SILENCE_END_SAMPLE and end > SILENCE_START_SAMPLE:
            raise AudioBuildError(f"{item_id} SFX overlaps the authored absolute-silence interval")
        if item_id == "warm_piano_chord" and (frame != PIANO_START_FRAME or start != SILENCE_END_SAMPLE):
            raise AudioBuildError("the warm piano chord must begin exactly at frame 4890, after absolute silence")
        events.append({
            "id": item_id,
            "frame": frame,
            "startFrame": start_frame,
            "sampleIndex": start,
            "durationSeconds": duration,
            "sampleCount": count,
            "kind": kind,
            "boundaryFrame": SNAP_BOUNDARY_FRAME if item_id == "crt_power_off_snap" else None,
            "description": item.get("description", ""),
        })
    return events, authored


def validate_authorization(segments: list[dict[str, Any]]) -> str:
    value = read_json(AUTHORIZATION_PATH, "audio-authorization.json")
    for key, expected in AUTHORIZATION_CONTRACT.items():
        if value.get(key) != expected:
            raise AudioBuildError(f"audio-authorization.json does not match current EP13 authorization field {key!r}")
    if value.get("voice") != SETTINGS["voice"]:
        raise AudioBuildError("audio-authorization.json voice differs from the EP13 packet")
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
        raise AudioBuildError("provider manifest settings differ from the authorized EP13 TTS")
    auth = manifest.get("authorization")
    if not isinstance(auth, dict) or auth.get("sha256AtInvocation") != auth_hash:
        raise AudioBuildError("provider manifest does not bind to the current audio-authorization.json")
    if auth.get("scope") != AUTHORIZATION_CONTRACT["scope"] or auth.get("source") != AUTHORIZATION_CONTRACT["source"]:
        raise AudioBuildError("provider manifest authorization scope/source differs from the EP13 packet")
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
            raise AudioBuildError(f"{sid} recorded text/settings differ from the EP13 source")
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


def load_timing_override() -> dict[str, Any]:
    if not TIMING_OVERRIDES_PATH.exists():
        return {
            "version": 1,
            "segments": {},
            "decisionSource": "authored active-onset alignment; no placement override supplied",
        }
    value = read_json(TIMING_OVERRIDES_PATH, "audio-timing-overrides.json")
    if value.get("version") != 1:
        raise AudioBuildError("audio-timing-overrides.json version must be 1")
    overrides = value.get("segments")
    if not isinstance(overrides, dict):
        raise AudioBuildError("audio-timing-overrides.json segments must be an object keyed by S01 through S08")
    unknown_ids = set(overrides) - set(EXPECTED_IDS)
    if unknown_ids:
        raise AudioBuildError(f"audio-timing-overrides.json contains unknown segment ID {sorted(unknown_ids)[0]}")
    decision_source = value.get("decisionSource")
    if not isinstance(decision_source, str) or not decision_source.strip():
        raise AudioBuildError("audio-timing-overrides.json needs a non-empty decisionSource")
    allowed_fields = {"cueStartSample", "captionEndFrame"}
    for segment_id, entry in overrides.items():
        if not isinstance(entry, dict) or not entry or set(entry) - allowed_fields:
            raise AudioBuildError(f"audio-timing-overrides.json entry for {segment_id} must contain cueStartSample and/or captionEndFrame only")
        if "cueStartSample" in entry:
            sample = entry["cueStartSample"]
            if type(sample) is not int or not 0 <= sample < TOTAL_SAMPLES:
                raise AudioBuildError(f"audio-timing-overrides.json cueStartSample for {segment_id} is outside the 90-second master")
        if "captionEndFrame" in entry:
            frame = entry["captionEndFrame"]
            if type(frame) is not int or not 0 < frame <= TOTAL_FRAMES:
                raise AudioBuildError(f"audio-timing-overrides.json captionEndFrame for {segment_id} is outside frames 1..5400")
    return {"version": 1, "segments": overrides, "decisionSource": decision_source.strip()}


def cue_timing(segments: list[dict[str, Any]], cues: dict[str, array.array], inventory: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    spans: list[dict[str, Any]] = []
    measured: list[dict[str, Any]] = []
    complete_cue_overlaps: list[dict[str, Any]] = []
    inventory_by_id = {item["id"]: item for item in inventory}
    override = load_timing_override()
    for segment in segments:
        sid = segment["id"]
        cue = cues[sid]
        cue_measure = inventory_by_id[sid]
        onset = cue_measure["activeOnsetOffsetSamples"]
        active_end = cue_measure["activeEndOffsetSamplesExclusive"]
        declared_start = segment["startFrame"] * SAMPLES_PER_FRAME
        segment_override = override["segments"].get(sid, {})
        default_start = max(SILENCE_END_SAMPLE, MIN_S08_VOICE_START_SAMPLE - onset) if sid == "S08" else declared_start - onset
        cue_start = segment_override.get("cueStartSample", default_start)
        placement = (
            f"complete source cue placed at sample {cue_start} by timing override; original cue retained at natural rate; "
            f"decision source: {override['decisionSource']}"
            if "cueStartSample" in segment_override else
            "complete source cue retained at natural rate; measured active onset aligned to authored start"
        )
        cue_end = cue_start + len(cue)
        voice_start = cue_start + onset
        voice_end = cue_start + active_end
        if not 0 <= cue_start < cue_end <= TOTAL_SAMPLES:
            raise AudioBuildError(f"NEEDS_SOL: {sid} complete cue placement falls outside the exact 90-second master")
        if not 0 <= voice_start < voice_end <= TOTAL_SAMPLES:
            raise AudioBuildError(f"NEEDS_SOL: {sid} measured active voice falls outside the exact 90-second master")
        if sid == "S08" and cue_start + onset < MIN_S08_VOICE_START_SAMPLE:
            raise AudioBuildError("NEEDS_SOL: S08 active voice onset precedes frame 4902; the cue was not altered")
        if cue_start < SILENCE_END_SAMPLE and cue_end > SILENCE_START_SAMPLE:
            raise AudioBuildError(f"NEEDS_SOL: {sid} complete PCM overlaps the authored absolute-silence interval")
        caption_start = math.ceil(voice_start / SAMPLES_PER_FRAME)
        caption_end = segment_override.get("captionEndFrame", math.ceil(voice_end / SAMPLES_PER_FRAME))
        minimum_caption_end = math.ceil(voice_end / SAMPLES_PER_FRAME)
        if caption_end < minimum_caption_end:
            raise AudioBuildError(f"NEEDS_SOL: {sid} captionEndFrame would end before measured narration PCM")
        if not 0 <= caption_start < caption_end <= TOTAL_FRAMES:
            raise AudioBuildError(f"NEEDS_SOL: {sid} caption bounds fall outside the exact 90-second master")
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
            "voiceStartSample": voice_start,
            "voiceEndSampleExclusive": voice_end,
            "cueStartSample": cue_start,
            "cueEndSampleExclusive": cue_end,
            "cueSamplesAt48k": len(cue),
            "measuredActiveSamples": active_end - onset,
            "onsetOffsetSamplesInCue": onset,
            "activeEndOffsetSamplesInCueExclusive": active_end,
            "captionStartFrame": caption_start,
            "captionEndFrame": caption_end,
            "placement": placement,
            "timingOverrideDecisionSource": override["decisionSource"],
            "onsetMeasurement": cue_measure["activeBoundsMethod"],
        })
    spans.sort(key=lambda item: item["startSample"])
    for index, previous in enumerate(spans):
        previous_end = previous["startSample"] + previous["sampleCount"]
        for current in spans[index + 1:]:
            current_end = current["startSample"] + current["sampleCount"]
            overlap_start = max(previous["startSample"], current["startSample"])
            overlap_end = min(previous_end, current_end)
            if overlap_start < overlap_end:
                complete_cue_overlaps.append({
                    "segmentIds": [previous["segmentId"], current["segmentId"]],
                    "startSample": overlap_start,
                    "endSampleExclusive": overlap_end,
                    "sampleCount": overlap_end - overlap_start,
                    "mixMethod": "additive_PCM_with_PCM16_saturation",
                })
    for item in measured:
        item["completeCueOverlaps"] = [
            overlap for overlap in complete_cue_overlaps if item["id"] in overlap["segmentIds"]
        ]
    active = sorted(measured, key=lambda item: item["voiceStartSample"])
    for previous, current in zip(active, active[1:]):
        if previous["voiceEndSampleExclusive"] > current["voiceStartSample"]:
            raise AudioBuildError(f"NEEDS_SOL: measured active narration overlaps between {previous['id']} and {current['id']}")
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
            mono = np.zeros(count, dtype=np.int32)
            while cursor < len(spans) and spans[cursor]["startSample"] + spans[cursor]["sampleCount"] <= block_start:
                cursor += 1
            index = cursor
            while index < len(spans) and spans[index]["startSample"] < block_end:
                span = spans[index]
                overlap_start = max(block_start, span["startSample"])
                overlap_end = min(block_end, span["startSample"] + span["sampleCount"])
                source_start = overlap_start - span["startSample"]
                target_start = overlap_start - block_start
                source_count = overlap_end - overlap_start
                mono[target_start:target_start + source_count] += np.asarray(
                    span["cue"][source_start:source_start + source_count], dtype=np.int32
                )
                index += 1
            limited = np.clip(mono, -32768, 32767).astype("<i2")
            stereo = np.empty((count, 2), dtype="<i2")
            stereo[:, 0] = limited
            stereo[:, 1] = limited
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
    merciful = 1.0 - ramp_array(frame, 1_080, 1_380)
    lock_in = ramp_array(frame, 1_320, 1_680) * (1.0 - ramp_array(frame, 4_260, 4_500))
    accumulation = ramp_array(frame, 2_820, 4_200) * (1.0 - ramp_array(frame, 4_740, 4_860))
    wow = 0.018 * np.sin(2.0 * np.pi * 0.31 * time) + 0.003 * np.sin(2.0 * np.pi * 5.2 * time)
    warm_oscillators = (
        0.36 * np.sin(2.0 * np.pi * 55.0 * time + wow)
        + 0.27 * np.sin(2.0 * np.pi * 82.41 * time + 0.22 + wow * 1.3)
        + 0.21 * np.sin(2.0 * np.pi * 110.0 * time + 0.44 + wow * 1.7)
        + 0.11 * np.sin(2.0 * np.pi * 164.81 * time + 0.66 + wow * 2.0)
    )
    retention_oscillators = (
        0.30 * np.sin(2.0 * np.pi * 73.42 * time + wow)
        + 0.25 * np.sin(2.0 * np.pi * 92.50 * time + 0.19 + wow * 1.2)
        + 0.21 * np.sin(2.0 * np.pi * 110.00 * time + 0.41 + wow * 1.6)
        + 0.15 * np.sin(2.0 * np.pi * 146.83 * time + 0.63 + wow * 2.1)
        + 0.09 * np.sin(2.0 * np.pi * 220.00 * time + 0.82 + wow * 2.5)
    )
    trapped_trace = (
        0.25 * np.sin(2.0 * np.pi * 130.81 * time + 0.12)
        + 0.21 * np.sin(2.0 * np.pi * 164.81 * time + 0.31 + wow)
        + 0.18 * np.sin(2.0 * np.pi * 196.00 * time + 0.53 + wow * 1.4)
        + 0.15 * np.sin(2.0 * np.pi * 246.94 * time + 0.76 + wow * 1.8)
        + 0.12 * np.sin(2.0 * np.pi * 311.13 * time + 0.98 + wow * 2.2)
        + 0.09 * np.sin(2.0 * np.pi * 392.00 * time + 1.21 + wow * 2.6)
    )
    pulse = 0.94 + 0.06 * np.sin(2.0 * np.pi * 0.083 * time + 0.7)
    value = fade_in * (
        0.062 * merciful * warm_oscillators
        + 0.045 * lock_in * retention_oscillators
        + 0.052 * accumulation * trapped_trace
    )
    value *= pulse
    score_end = 1.0 - ramp_array(frame, 4_800, SNAP_BOUNDARY_FRAME)
    duck = voice_gain_array(samples, measured, attenuation_db=-8.0)
    value *= score_end * duck
    pan = 0.035 * np.sin(2.0 * np.pi * 0.035 * time)
    left = value * (0.99 - pan)
    right = value * (0.99 + pan)
    absolute_silence = (frame >= SILENCE_START_FRAME) & (frame < SILENCE_END_FRAME)
    left[absolute_silence] = 0.0
    right[absolute_silence] = 0.0
    return left, right


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
        "description": "Deterministic warm analog oscillators move from a merciful low-frequency bed into a denser, gently detuned CRT phosphor tone field; the score fades before the exact blackout.",
        "designedOscillatorFrequenciesHz": [55.0, 73.42, 82.41, 92.5, 110.0, 130.81, 146.83, 164.81, 196.0, 220.0, 246.94, 311.13, 392.0],
        "tapeWowHz": 0.31,
        "tapeFlutterHz": 5.2,
        "voiceDuckDB": -8.0,
        "voicePreattackMilliseconds": 60,
        "voiceReleaseMilliseconds": 350,
        "absoluteSilenceFrames": [SILENCE_START_FRAME, SILENCE_END_FRAME],
        "afterBlackout": "no score; the separately authored warm piano chord is an SFX event beginning at frame 4890",
        "stereo": "subtle deterministic pan",
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
    seed = sum((index + 1) * byte for index, byte in enumerate(event_id.encode("utf-8")))
    noise = deterministic_noise(count, seed).astype(np.float64)
    if kind == "cassette_rewind_calibration":
        low_noise = np.convolve(noise, np.ones(17, dtype=np.float32) / 17.0, mode="same")
        flutter = 0.012 * np.sin(2.0 * np.pi * 4.1 * t) + 0.004 * np.sin(2.0 * np.pi * 0.37 * t)
        drag = 0.034 * np.sin(2.0 * np.pi * (112.0 * t + flutter)) + 0.018 * low_noise
        drag *= 1.0 - smooth_array((t - 2.1) / 0.9)
        crackle = np.zeros(count, dtype=np.float64)
        for tick_time in (0.02, 0.19, 0.68, 1.18, 1.92, 2.58):
            local = np.maximum(0.0, t - tick_time)
            crackle += np.where(t >= tick_time, 0.035 * noise * np.exp(-local * 74.0), 0.0)
        tone_gate = smooth_array((t - 0.78) / 0.025) * (1.0 - smooth_array((t - 1.28) / 0.06))
        calibration = 0.075 * tone_gate * np.sin(2.0 * np.pi * 1_000.0 * t)
        left, right = drag + crackle + calibration, drag * 0.94 + crackle * 0.79 + calibration * 0.97
    elif kind == "warm_filtered_chord":
        chord = np.zeros(count, dtype=np.float64)
        bright = np.zeros(count, dtype=np.float64)
        for index, frequency in enumerate((174.61, 220.0, 261.63, 349.23)):
            phase = 2.0 * np.pi * frequency * t + index * 0.13
            chord += (0.31 - index * 0.035) * np.sin(phase)
            bright += (0.09 - index * 0.009) * np.sin(phase * (2.01 + index * 0.006) + 0.07)
        muffling = smooth_array(progress)
        source = (1.0 - muffling) * bright + (0.82 + 0.18 * muffling) * chord
        onset = smooth_array(np.minimum(1.0, t / 0.045))
        decay = np.exp(-t * 0.56)
        tone = source * onset * decay
        room = np.zeros(count, dtype=np.float64)
        for delay, gain in ((0.19, 0.23), (0.41, 0.14), (0.73, 0.08), (1.11, 0.045)):
            local = t - delay
            active = local >= 0.0
            room += np.where(active, gain * source * np.exp(-np.maximum(0.0, local) * 0.8), 0.0)
        left, right = 0.075 * (tone + room), 0.075 * (tone + room * 0.88)
    elif kind == "tape_hiss":
        high_hiss = noise - np.convolve(noise, np.ones(31, dtype=np.float32) / 31.0, mode="same")
        fade = 1.0 - smooth_array((progress - 0.43) / 0.57)
        slow_level = 0.88 + 0.12 * np.sin(2.0 * np.pi * 0.23 * t + 0.4)
        left, right = 0.060 * high_hiss * fade * slow_level, 0.057 * high_hiss * fade * (0.90 + 0.10 * np.sin(2.0 * np.pi * 0.19 * t))
    elif kind == "magnetic_relay":
        impact = 0.10 * noise * np.exp(-t * 93.0)
        thunk = 0.10 * np.sin(2.0 * np.pi * 68.0 * t) * np.exp(-t * 3.1)
        coil = (
            0.042 * np.sin(2.0 * np.pi * 246.94 * t)
            + 0.026 * np.sin(2.0 * np.pi * 392.0 * t + 0.16)
            + 0.014 * np.sin(2.0 * np.pi * 587.33 * t + 0.31)
        ) * np.exp(-t * 2.2)
        second_click = np.where(t >= 0.11, 0.035 * noise * np.exp(-np.maximum(0.0, t - 0.11) * 102.0), 0.0)
        left, right = impact + thunk + coil + second_click, impact * 0.9 + thunk * 0.96 + coil * 0.94 - second_click * 0.45
    elif kind == "hv_phase_lock":
        sweep_phase = 2.0 * np.pi * (1_180.0 * t + 0.5 * 1_420.0 * t * t / duration)
        whine = 0.052 * np.sin(sweep_phase) + 0.018 * np.sin(2.0 * sweep_phase + 0.18)
        capacitor = 0.026 * np.sin(2.0 * np.pi * 57.0 * t + 0.2) * (0.72 + 0.28 * np.sin(2.0 * np.pi * 7.0 * t))
        click_time = 0.74
        local = np.maximum(0.0, t - click_time)
        lock_click = np.where(t >= click_time, 0.080 * noise * np.exp(-local * 150.0), 0.0)
        left, right = whine + capacitor + lock_click, whine * 0.94 + capacitor * 0.91 - lock_click * 0.74
    elif kind == "nondecaying_loops":
        loops = np.zeros(count, dtype=np.float64)
        loop_frequencies = (110.0, 146.83, 196.0, 246.94, 293.66, 349.23, 440.0, 523.25, 659.25, 783.99, 987.77, 1_174.66)
        for loop_index, frequency in enumerate(loop_frequencies):
            start_time = loop_index * 2.15
            local = np.maximum(0.0, t - start_time)
            entered = smooth_array(np.minimum(1.0, local / 0.018)) * (t >= start_time)
            flutter = 0.003 * np.sin(2.0 * np.pi * (0.13 + loop_index * 0.011) * local)
            loops += entered * (0.014 - loop_index * 0.00045) * np.sin(2.0 * np.pi * frequency * (local + flutter) + loop_index * 0.29)
        amber_sheen = 0.009 * np.sin(2.0 * np.pi * 71.0 * t + 0.4) * np.sin(2.0 * np.pi * 0.31 * t)
        left, right = loops + amber_sheen, loops * 0.92 - amber_sheen * 0.54
    elif kind == "shepard_tube":
        layers = np.zeros(count, dtype=np.float64)
        for index, start_frequency in enumerate((118.0, 177.0, 266.0, 399.0, 598.0)):
            sweep_ratio = 2.0 * t / duration
            phase = 2.0 * np.pi * start_frequency * duration * (np.power(2.0, sweep_ratio) - 1.0) / (2.0 * math.log(2.0))
            layer_level = np.sin(np.pi * np.clip(progress + index * 0.17, 0.0, 1.0))
            layers += (0.035 - index * 0.0035) * layer_level * np.sin(phase + index * 0.31)
        tube = np.tanh(2.8 * layers) * 0.9
        edge = smooth_array(np.minimum(1.0, t / 0.04)) * smooth_array((duration - t) / 0.12)
        left, right = tube * edge, np.tanh(2.5 * (layers * 0.94 + 0.008 * np.sin(2.0 * np.pi * 63.0 * t))) * edge
    elif kind == "harmonic_peak":
        attack = smooth_array(np.minimum(1.0, t / 0.045))
        clear = smooth_array((duration - t) / 0.24)
        cluster = np.zeros(count, dtype=np.float64)
        for index, frequency in enumerate((1_760.0, 2_093.0, 2_637.0, 3_136.0, 4_186.0, 5_274.0)):
            detune = 1.0 + (index - 2.5) * 0.0018
            cluster += (0.035 - index * 0.003) * np.sin(2.0 * np.pi * frequency * detune * t + index * 0.21)
        shimmer = 0.012 * np.sin(2.0 * np.pi * 8.1 * t) * np.sin(2.0 * np.pi * 2_150.0 * t)
        left, right = (cluster + shimmer) * attack * clear, (cluster * 0.94 - shimmer * 0.62) * attack * clear
    elif kind == "crt_power_off_snap":
        discharge = 0.32 * noise * np.exp(-t * 760.0)
        click = 0.22 * np.sin(2.0 * np.pi * 3_800.0 * t) * np.exp(-t * 620.0)
        thump = 0.095 * np.sin(2.0 * np.pi * 96.0 * t) * np.exp(-t * 380.0)
        left, right = discharge + click + thump, discharge * 0.82 - click * 0.71 + thump * 0.95
    elif kind == "warm_piano_chord":
        envelope = smooth_array(np.minimum(1.0, t / 0.028)) * np.exp(-t * 0.46)
        envelope *= 1.0 - smooth_array((progress - 0.78) / 0.22)
        chord = np.zeros(count, dtype=np.float64)
        for index, (frequency, weight) in enumerate(zip((174.61, 220.0, 261.63, 329.63), (0.30, 0.27, 0.24, 0.19))):
            detuned = frequency * (1.0 + (index - 1.4) * 0.0022)
            phase = 2.0 * np.pi * detuned * t + index * 0.15
            chord += weight * (
                0.78 * np.sin(phase)
                + 0.17 * np.sin(phase * (2.005 + index * 0.002) + 0.04)
                + 0.05 * np.sin(phase * (3.97 - index * 0.003) + 0.09)
            )
        room = np.zeros(count, dtype=np.float64)
        for delay, gain in ((0.18, 0.28), (0.37, 0.18), (0.61, 0.11), (0.94, 0.065), (1.38, 0.035)):
            local = t - delay
            room += np.where(local >= 0.0, gain * chord * np.exp(-np.maximum(0.0, local) * 0.62), 0.0)
        left, right = 0.19 * envelope * (chord + room), 0.19 * envelope * (chord + room * 0.91)
    else:
        raise AudioBuildError(f"unknown deterministic SFX kind {kind}")
    return left, right


def notch_sfx_dialogue_band(values: Any) -> Any:
    """Apply a deterministic 1-4 kHz SFX notch across each event for speech intelligibility."""
    count = values.shape[0]
    frequencies = np.fft.rfftfreq(count, d=1.0 / SAMPLE_RATE)
    band = ramp_array(frequencies, 850.0, 1_000.0) * (1.0 - ramp_array(frequencies, 4_000.0, 4_600.0))
    gain = 1.0 - (1.0 - 10.0 ** (-12.0 / 20.0)) * band
    return np.fft.irfft(np.fft.rfft(values) * gain, n=count)


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
        lval = notch_sfx_dialogue_band(lval)
        rval = notch_sfx_dialogue_band(rval)
        duck = voice_gain_for_event(np.arange(start, end, dtype=np.int64), measured)
        left[start:end] += (lval * duck).astype(np.float32)
        right[start:end] += (rval * duck).astype(np.float32)
        onsets.append({
            "id": event["id"],
            "frame": event["frame"],
            "startFrame": event["startFrame"],
            "sampleIndex": start,
            "endSampleExclusive": end,
            "boundaryFrame": event["boundaryFrame"],
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
        "description": "Deterministic cassette rewind, vinyl/tape texture, warm filtered chord, relay, CRT high-voltage lock, accumulating feedback, Shepard rise, harmonic peak, power-off snap, and warm piano chord; no third-party assets.",
        "events": onsets,
        "silenceWindowFrames": [SILENCE_START_FRAME, SILENCE_END_FRAME],
        "snapBoundary": {
            "attackStartFrame": SNAP_ATTACK_FRAME,
            "anchorFrame": SNAP_BOUNDARY_FRAME,
            "endSampleExclusive": SILENCE_START_SAMPLE,
            "transientEndsBeforeSilence": True,
        },
        "voiceDuckDB": -9.0,
        "speechIntelligibilityNotch": {"startHz": 1_000, "endHz": 4_000, "attenuationDB": -12.0, "appliedToEvents": "all events; includes all narration overlaps"},
        "noiseSource": "fixed xorshift32 seed derived from event ID; no runtime random source",
        "postBlackout": ["warm_piano_chord"],
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
        raise AudioBuildError(f"{path.name} is not exact zero over frames [4860,4890); PCM16 peak={peak}")
    return 0


def verify_event_activity(path: Path, start_sample: int, sample_count: int, label: str) -> int:
    try:
        with wave.open(str(path), "rb") as wav:
            params = wav.getparams()
            expected = (SAMPLE_RATE, 2, 2, TOTAL_SAMPLES, "NONE")
            actual = (params.framerate, params.nchannels, params.sampwidth, params.nframes, params.comptype)
            if actual != expected:
                raise AudioBuildError(f"{path.name} has unexpected format before {label} verification")
            wav.setpos(start_sample)
            raw = wav.readframes(sample_count)
    except (OSError, wave.Error) as exc:
        raise AudioBuildError(f"cannot read {label} interval from {path.name}: {exc}") from None
    values = array.array("h")
    values.frombytes(raw)
    peak = max((abs(value) for value in values), default=0)
    if peak == 0:
        raise AudioBuildError(f"{path.name} lost {label}")
    return peak


def verify_snap_boundary(path: Path) -> int:
    return verify_event_activity(
        path,
        SNAP_ATTACK_FRAME * SAMPLES_PER_FRAME,
        SAMPLES_PER_FRAME,
        "the CRT power-off snap ending at frame 4860",
    )


def verify_warm_piano_chord(path: Path) -> int:
    return verify_event_activity(
        path,
        PIANO_START_FRAME * SAMPLES_PER_FRAME,
        round(0.5 * SAMPLE_RATE),
        "the warm piano chord beginning at frame 4890",
    )


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
    editorial_wraps = {
        "人类像一群在黑夜里摸象的盲人，": "人类像一群\n在黑夜里摸象的盲人，",
        "直到超级智能挥下奥卡姆剃刀。": "直到超级智能\n挥下奥卡姆剃刀。",
        "就像当年牛顿用一行万有引力，": "就像当年牛顿\n用一行万有引力，",
        "擦掉了托勒密上百个繁琐的圆圈；": "擦掉了托勒密\n上百个繁琐的圆圈；",
        "超级智能开始了终极的“符号坍缩”。": "超级智能开始了\n终极的“符号坍缩”。",
        "严丝合缝地折叠成了最后一行极简的黄金方程。": "严丝合缝地折叠成了\n最后一行极简的黄金方程。",
        "当超级智能替人类翻到了宇宙的最后一页，": "当超级智能替人类\n翻到了宇宙的最后一页，",
        "“当所有的迷雾都变成了定理，": "“当所有的迷雾\n都变成了定理，",
    }
    if clean in editorial_wraps:
        return editorial_wraps[clean]
    if len(clean) <= 13:
        return clean
    if len(clean) > 26:
        raise AudioBuildError(f"caption chunk cannot fit in at most two 13-character lines: {source!r}")
    split = min(13, max(len(clean) - 13, (len(clean) + 1) // 2))
    return clean[:split] + "\n" + clean[split:]


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
        start_frame = item["captionStartFrame"]
        end_frame = item["captionEndFrame"]
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
    existing_metadata = []
    for path in metadata_paths:
        if not path.exists():
            continue
        if path == TIMING_PATH:
            placeholder = read_json(path, "audio-timing.json")
            if (placeholder.get("status") == "PREVIEW_ONLY" and placeholder.get("segments") == []
                    and placeholder.get("captions") == [{"segmentId": "PREVIEW_ONLY", "startFrame": -1, "endFrame": -1, "text": ""}]):
                continue
        existing_metadata.append(path)
    existing = existing_outputs + existing_metadata
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
    complete_cue_overlaps = [
        overlap
        for item in segment_timing
        for overlap in item["completeCueOverlaps"]
        if overlap["segmentIds"][0] == item["id"]
    ]
    captions = build_captions(segments, segment_timing)
    scratch_parent = agentdev_scratch_parent()
    AUDIO.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="si-ep13-audio-", dir=str(scratch_parent)) as scratch_name:
        scratch = Path(scratch_name)
        outputs: dict[str, Any] = {}
        outputs["narration"] = render_narration(scratch / "narration.wav", spans)
        outputs["score"] = render_score(scratch / "score.wav", segment_timing)
        outputs["sfx"], sfx_onsets = render_sfx(scratch / "sfx.wav", events, segment_timing)
        for name in ("narration", "score", "sfx"):
            verify_silence(scratch / f"{name}.wav")
        sfx_snap_peak = verify_snap_boundary(scratch / "sfx.wav")
        sfx_piano_peak = verify_warm_piano_chord(scratch / "sfx.wav")
        outputs["master"] = mix_master(scratch / "master.wav", [scratch / name for name in ("narration.wav", "score.wav", "sfx.wav")])
        master_snap_peak = verify_snap_boundary(scratch / "master.wav")
        master_piano_peak = verify_warm_piano_chord(scratch / "master.wav")
        for name in ("narration", "score", "sfx", "master"):
            if outputs[name]["sizeBytes"] >= 100 * 1024 * 1024:
                raise AudioBuildError(f"{name}.wav unexpectedly exceeds the 100 MiB tracked-audio limit")
        input_hashes = {
            "segmentsJson": sha_file(SEGMENTS_PATH),
            "sfxEventsJson": sha_file(EVENTS_PATH),
            "audioAuthorization": sha_file(AUTHORIZATION_PATH),
            "audioTimingOverrides": sha_file(TIMING_OVERRIDES_PATH) if TIMING_OVERRIDES_PATH.is_file() else None,
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
            "captionTimingMethod": "Unchanged original display-subtitle chunks are allocated by character weight within measured active PCM spans; an optional per-segment captionEndFrame override may extend timing; no ASR or forced word alignment was performed.",
            "segments": segment_timing,
            "completeCueOverlaps": complete_cue_overlaps,
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
            "cuePlacement": "all complete source cues retained at natural rate; optional per-segment cueStartSample overrides set placement; complete-cue overlaps are mixed additively and reported; active voice overlap and blackout crossing are rejected; S08 active voice starts at frame 4902 or later",
            "completeCueOverlaps": complete_cue_overlaps,
            "captions": {
                "count": len(captions),
                "linesMaximumCharacters": 13,
                "linesMaximumPerCaption": 2,
                "alignment": "estimated character-weighted timing; not ASR or forced alignment",
            },
            "humanListening": {
                "status": "not_recorded_by_this_build",
                "note": "This report covers measured technical checks only; human listening remains separate.",
            },
            "crtPowerOffSnap": {
                "attackStartFrame": SNAP_ATTACK_FRAME,
                "anchorFrame": SNAP_BOUNDARY_FRAME,
                "startSample": SNAP_ATTACK_FRAME * SAMPLES_PER_FRAME,
                "endSampleExclusive": SILENCE_START_SAMPLE,
                "sfxSamplePeakPcm16": sfx_snap_peak,
                "masterSamplePeakPcm16": master_snap_peak,
                "endsExactlyAtSilenceBoundary": True,
            },
            "warmPianoChord": {
                "startFrame": PIANO_START_FRAME,
                "startSample": PIANO_START_FRAME * SAMPLES_PER_FRAME,
                "durationSeconds": 8.5,
                "sfxSamplePeakPcm16": sfx_piano_peak,
                "masterSamplePeakPcm16": master_piano_peak,
                "startsAfterAbsoluteSilence": True,
            },
            "absoluteSilence": silence,
            "masterLoudness": outputs["master"]["ebur128Final"],
            "normalizationTarget": outputs["master"]["normalizationTarget"],
            "boundaryEventSamplePeakPcm16": {"crtPowerOffSnap": {"sfx": sfx_snap_peak, "master": master_snap_peak}},
            "postBlackoutEventSamplePeakPcm16": {"warmPianoChord": {"sfx": sfx_piano_peak, "master": master_piano_peak}},
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
    modes.add_argument("--validate-source", action="store_true", help="validate segment/event timing and snap/blackout boundaries without loading cues or mixing")
    args = parser.parse_args()
    try:
        segments = load_segments()
        events, _ = load_events()
        if args.validate_source:
            timing_overrides = load_timing_override()
            print(json.dumps({
                "status": "source_validated",
                "durationSeconds": DURATION_SECONDS,
                "samplesPerChannel": TOTAL_SAMPLES,
                "segmentCount": len(segments),
                "eventCount": len(events),
                "eventAnchors": [
                    {
                        "id": event["id"],
                        "frame": event["frame"],
                        "startFrame": event["startFrame"],
                        "sampleIndex": event["sampleIndex"],
                        "sampleCount": event["sampleCount"],
                    }
                    for event in events
                ],
                "absoluteSilence": [SILENCE_START_FRAME, SILENCE_END_FRAME],
                "snapEndSampleExclusive": SILENCE_START_SAMPLE,
                "warmPianoStartFrame": PIANO_START_FRAME,
                "voiceMinimumOnsetFrame": MIN_S08_VOICE_START_FRAME,
                "timingOverrideSegments": sorted(timing_overrides["segments"]),
                "timingOverrideDecisionSource": timing_overrides["decisionSource"],
            }, ensure_ascii=False, indent=2))
            return 0
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
