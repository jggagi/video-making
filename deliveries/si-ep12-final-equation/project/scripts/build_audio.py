#!/usr/bin/env python3
"""Build EP12's exact 90-second narration, procedural audio stems, captions, and PCM master."""

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
PEN_TOUCH_FRAME = SILENCE_END_FRAME
MIN_S08_VOICE_START_FRAME = 4_902
MIN_S08_VOICE_START_SAMPLE = MIN_S08_VOICE_START_FRAME * SAMPLES_PER_FRAME
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
    "scope": "EP12 S01 through S08 exact prepared tts_phonetic_text",
    "authorized": True,
    "source": "Standing video-making voiceover authorization in skills/voiceover/SKILL.md (2026-10-20); current EP12 Task Packet",
}
EVENT_PROFILES = {
    "pencil_escapement": ("pencil_escapement", 2.4),
    "out_of_phase_gears": ("gears_errors", 3.6),
    "caliper_sweep": ("caliper_sweep", 2.6),
    "unlocking_rings": ("rings_to_sine", 2.8),
    "four_tones_unison": ("four_to_unison", 3.8),
    "precision_lock_resonance": ("lock_resonance", 2.6),
    "tuning_fork": ("tuning_fork", 5.0),
    "pen_touch": ("pen_touch", 0.16),
}
EXPECTED_EVENTS = [
    ("pencil_escapement", 60),
    ("out_of_phase_gears", 840),
    ("caliper_sweep", 1_440),
    ("unlocking_rings", 2_280),
    ("four_tones_unison", 2_940),
    ("precision_lock_resonance", 3_900),
    ("tuning_fork", 4_500),
    ("pen_touch", PEN_TOUCH_FRAME),
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
        raise AudioBuildError("sfx_events.json timing units differ from the EP12 60 fps / 48 kHz audio plan")
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
        raise AudioBuildError("sfx_events.json IDs/order/frames differ from the assigned EP12 event plan")
    events: list[dict[str, Any]] = []
    for item in source:
        item_id, frame = item["id"], item["frame"]
        sample = frame * SAMPLES_PER_FRAME
        if item.get("sample") != sample:
            raise AudioBuildError(f"{item_id} sample does not equal frame*800")
        kind, duration = EVENT_PROFILES[item_id]
        if item.get("kind") != kind or item.get("durationSeconds") != duration:
            raise AudioBuildError(f"{item_id} kind or duration differs from the assigned EP12 event plan")
        start = sample
        count = round(duration * SAMPLE_RATE)
        end = start + count
        if not 0 <= frame < TOTAL_FRAMES or end > TOTAL_SAMPLES:
            raise AudioBuildError(f"{item_id} has invalid event bounds")
        if start < SILENCE_END_SAMPLE and end > SILENCE_START_SAMPLE:
            raise AudioBuildError(f"{item_id} SFX overlaps the authored absolute-silence interval")
        if item_id == "pen_touch" and (frame != PEN_TOUCH_FRAME or end > MIN_S08_VOICE_START_SAMPLE):
            raise AudioBuildError("the pen touch must start at frame 4890 and end before the S08 voice-onset gate")
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
            raise AudioBuildError(f"audio-authorization.json does not match current EP12 authorization field {key!r}")
    if value.get("voice") != SETTINGS["voice"]:
        raise AudioBuildError("audio-authorization.json voice differs from the EP12 packet")
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
        raise AudioBuildError("provider manifest settings differ from the authorized EP12 TTS")
    auth = manifest.get("authorization")
    if not isinstance(auth, dict) or auth.get("sha256AtInvocation") != auth_hash:
        raise AudioBuildError("provider manifest does not bind to the current audio-authorization.json")
    if auth.get("scope") != AUTHORIZATION_CONTRACT["scope"] or auth.get("source") != AUTHORIZATION_CONTRACT["source"]:
        raise AudioBuildError("provider manifest authorization scope/source differs from the EP12 packet")
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
            raise AudioBuildError(f"{sid} recorded text/settings differ from the EP12 source")
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
    value = read_json(TIMING_OVERRIDES_PATH, "audio-timing-overrides.json")
    expected = {
        "version": 1,
        "segmentId": "S02",
        "preserveAuthoredStartFrame": 600,
        "preserveAuthoredEndFrame": 1260,
        "preserveTextAndRate": True,
        "approvedCompleteCueStartSample": 469951,
        "approvedCompleteCueEndSample": 1022911,
        "completeCueEndConvention": "exclusive",
        "approvedActiveVoiceStartSample": 480000,
        "approvedActiveVoiceEndSample": 1011046,
        "approvedCaptionEndFrame": 1264,
        "nextCueId": "S03",
        "nextCueStartSample": 1045756,
    }
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            raise AudioBuildError(f"audio-timing-overrides.json does not match the approved S02 placement field {key!r}")
    decision = value.get("decision")
    if not isinstance(decision, dict) or decision.get("authorized") is not True or decision.get("text") != "使用空隙，保留自然语速和完整原文（推荐）":
        raise AudioBuildError("audio-timing-overrides.json is missing the direct human S02 gap-use decision")
    if value.get("scope") != "S02 placement only; preserve authored source text, voice, rate, and segment start/end frames":
        raise AudioBuildError("audio-timing-overrides.json scope must remain limited to S02 placement")
    return value


def cue_timing(segments: list[dict[str, Any]], cues: dict[str, array.array], inventory: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    spans: list[dict[str, Any]] = []
    measured: list[dict[str, Any]] = []
    inventory_by_id = {item["id"]: item for item in inventory}
    override = load_timing_override()
    for segment in segments:
        sid = segment["id"]
        cue = cues[sid]
        cue_measure = inventory_by_id[sid]
        onset = cue_measure["activeOnsetOffsetSamples"]
        active_end = cue_measure["activeEndOffsetSamplesExclusive"]
        declared_start = segment["startFrame"] * SAMPLES_PER_FRAME
        hard_end = segment["endFrame"] * SAMPLES_PER_FRAME
        if sid == "S08":
            # Preserve the complete cue, place no source PCM in blackout, and gate active voice at/after frame 4902.
            cue_start = max(SILENCE_END_SAMPLE, MIN_S08_VOICE_START_SAMPLE - onset)
            placement = "complete S08 source cue starts at/after frame 4890; measured voice onset is gated to frame 4902 or later; source PCM preserved"
        else:
            cue_start = declared_start - onset
            placement = ("approved S02 complete cue preserved at natural rate; active onset aligned to frame 600 and complete cue ends in the approved reserved gap"
                         if sid == "S02" else
                         "measured active PCM onset aligned to the declared start frame; complete source cue preserved")
        cue_end = cue_start + len(cue)
        if cue_start < 0:
            raise AudioBuildError(f"NEEDS_SOL: {sid} measured onset would place complete cue before sample zero")
        if sid == "S02":
            voice_end = cue_start + active_end
            actual_s02 = {
                "cue_start": cue_start,
                "cue_end": cue_end,
                "voice_start": cue_start + onset,
                "voice_end": voice_end,
            }
            approved_s02 = {
                "cue_start": override["approvedCompleteCueStartSample"],
                "cue_end": override["approvedCompleteCueEndSample"],
                "voice_start": override["approvedActiveVoiceStartSample"],
                "voice_end": override["approvedActiveVoiceEndSample"],
            }
            if actual_s02 != approved_s02:
                raise AudioBuildError(f"NEEDS_SOL: S02 measured placement differs from the exact approved override: actual={actual_s02}, approved={approved_s02}")
            if segment["startFrame"] != override["preserveAuthoredStartFrame"] or segment["endFrame"] != override["preserveAuthoredEndFrame"]:
                raise AudioBuildError("NEEDS_SOL: S02 authored source frames changed; the approved placement override no longer applies")
        elif cue_end > hard_end:
            raise AudioBuildError(
                f"NEEDS_SOL: {sid} complete PCM ends at sample {cue_end}, beyond its declared end sample {hard_end}; "
                "the cue was not shifted, accelerated, truncated, or stretched"
            )
        if sid == "S08" and cue_start + onset < MIN_S08_VOICE_START_SAMPLE:
            raise AudioBuildError("NEEDS_SOL: S08 active voice onset precedes frame 4902; the cue was not shifted into silence or altered")
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
            "captionStartFrame": math.ceil((cue_start + onset) / SAMPLES_PER_FRAME),
            "captionEndFrame": (
                override["approvedCaptionEndFrame"] if sid == "S02" else
                math.ceil((cue_start + active_end) / SAMPLES_PER_FRAME)
            ),
            "placement": placement,
            "onsetMeasurement": cue_measure["activeBoundsMethod"],
        })
    spans.sort(key=lambda item: item["startSample"])
    for previous, current in zip(spans, spans[1:]):
        if previous["startSample"] + previous["sampleCount"] > current["startSample"]:
            raise AudioBuildError(f"NEEDS_SOL: complete narration PCM overlaps between {previous['segmentId']} and {current['segmentId']}")
    s02_span = next(item for item in spans if item["segmentId"] == "S02")
    s03_span = next(item for item in spans if item["segmentId"] == "S03")
    s02_end = s02_span["startSample"] + s02_span["sampleCount"]
    if s02_span["startSample"] + s02_span["sampleCount"] != override["approvedCompleteCueEndSample"]:
        raise AudioBuildError("NEEDS_SOL: complete S02 cue end differs from its approved sample")
    if s03_span["startSample"] != override["nextCueStartSample"]:
        raise AudioBuildError("NEEDS_SOL: measured S03 full-cue start differs from the approved no-overlap check")
    if s02_end > s03_span["startSample"]:
        raise AudioBuildError("NEEDS_SOL: approved S02 full cue overlaps the next S03 full cue")
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


NOSTALGIC_PIANO = [
    (4_900 + 34 * index, frequency)
    for index, frequency in enumerate((261.63, 392.00, 329.63, 523.25, 392.00, 329.63, 293.66, 440.00, 349.23, 587.33, 440.00, 392.00))
]


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

    # After the pen touch, a small deterministic felt-piano phrase returns under the final narration.
    piano = np.zeros(samples.shape, dtype=np.float64)
    piano_fade = 1.0 - ramp_array(frame, 5325, TOTAL_FRAMES)
    for note_index, (start_frame, frequency) in enumerate(NOSTALGIC_PIANO):
        start_sample = start_frame * SAMPLES_PER_FRAME
        duration_samples = round(1.15 * SAMPLE_RATE)
        note_time = np.maximum(0.0, (samples - start_sample) / SAMPLE_RATE)
        active = (samples >= start_sample) & (samples < start_sample + duration_samples)
        if not np.any(active):
            continue
        attack = smooth_array(note_time / 0.028)
        release = smooth_array((duration_samples / SAMPLE_RATE - note_time) / 0.16)
        envelope = attack * np.exp(-2.15 * note_time) * release
        tone = (
            0.60 * np.sin(2.0 * np.pi * frequency * note_time)
            + 0.25 * np.sin(2.0 * np.pi * frequency * 2.01 * note_time + 0.035)
            + 0.10 * np.sin(2.0 * np.pi * frequency * 3.98 * note_time + 0.11)
            + 0.05 * np.sin(2.0 * np.pi * frequency * 6.02 * note_time + 0.19)
        )
        piano += np.where(active, 0.115 * envelope * tone, 0.0)
    piano *= piano_fade * duck
    pan = 0.035 * np.sin(2.0 * np.pi * 0.035 * time)
    left = value * (0.99 - pan) + piano * (0.98 - pan)
    right = value * (0.99 + pan) + piano * (0.98 + pan)
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
        "description": "Deterministic harmonic pad resolves into an authored solo-piano phrase after the fountain-pen touch; both are silent throughout the exact 30-frame blackout.",
        "maximumDesignedToneHz": max(frequency for _, frequency in NOSTALGIC_PIANO),
        "maximumDesignedPartialHz": max(frequency for _, frequency in NOSTALGIC_PIANO) * 6.02,
        "postBlackoutPianoNotes": [{"startFrame": start, "frequencyHz": frequency} for start, frequency in NOSTALGIC_PIANO],
        "postBlackoutPianoTailEndsBeforeFrame": NOSTALGIC_PIANO[-1][0] + round(1.15 * FPS),
        "voiceDuckDB": -8.0,
        "voicePreattackMilliseconds": 60,
        "voiceReleaseMilliseconds": 350,
        "absoluteSilenceFrames": [SILENCE_START_FRAME, SILENCE_END_FRAME],
        "afterBlackout": "warm nostalgic procedural solo piano only; no score in frames [4860,4890)",
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
    seed = sum((index + 1) * byte for index, byte in enumerate(event_id.encode("utf-8")))
    noise = deterministic_noise(count, seed).astype(np.float64)
    attack = smooth_array(np.minimum(1.0, t / min(0.035, duration * 0.12)))
    release = smooth_array((duration - t) / min(0.40, duration * 0.24))
    env = attack * release

    if kind == "pencil_escapement":
        paper = np.convolve(noise, np.ones(31, dtype=np.float32) / 31.0, mode="same")
        scratch = (0.045 * paper + 0.018 * np.sin(2.0 * np.pi * 185.0 * t + 0.25)) * env
        ticks = np.zeros(count, dtype=np.float64)
        for tick_index in range(5):
            tick_time = 0.12 + tick_index * 0.48
            local = np.maximum(0.0, t - tick_time)
            ticks += np.where(t >= tick_time, 0.025 * np.sin(2.0 * np.pi * (1_420.0 + 25.0 * tick_index) * local) * np.exp(-local * 82.0), 0.0)
        left, right = scratch + ticks, scratch * 0.93 + ticks * 0.82
    elif kind == "gears_errors":
        drift = 0.5 * (1.0 + np.sin(2.0 * np.pi * 0.19 * t))
        gear_a = np.sin(2.0 * np.pi * (78.0 * t + 3.2 * t * t))
        gear_b = np.sin(2.0 * np.pi * (86.0 * t + 5.1 * t * t) + 0.5)
        grind = env * (0.045 * gear_a + (0.025 + 0.018 * drift) * gear_b + 0.008 * noise)
        errors = np.zeros(count, dtype=np.float64)
        for tick_time in (0.42, 1.14, 2.28, 3.02):
            local = np.maximum(0.0, t - tick_time)
            errors += np.where(t >= tick_time, 0.030 * np.sin(2.0 * np.pi * 1_760.0 * local) * np.exp(-local * 95.0), 0.0)
        left, right = grind + errors, grind * 0.95 - errors * 0.72
    elif kind == "caliper_sweep":
        phase = 2.0 * np.pi * (170.0 * t + 0.5 * 850.0 * t * t / duration)
        blade = env * (0.050 * np.sin(phase) + 0.018 * np.sin(phase * 2.01 + 0.15))
        pan = smooth_array(progress)
        left, right = blade * (1.0 - 0.72 * pan), blade * (0.28 + 0.72 * pan)
    elif kind == "rings_to_sine":
        rings = np.zeros(count, dtype=np.float64)
        for ring_index, ring_time in enumerate((0.05, 0.46, 0.89, 1.32)):
            local = np.maximum(0.0, t - ring_time)
            freq = (685.0, 823.0, 1_040.0, 1_304.0)[ring_index]
            rings += np.where(t >= ring_time, 0.060 * np.sin(2.0 * np.pi * freq * local) * np.exp(-local * (3.8 + ring_index * 0.5)), 0.0)
        blend = smooth_array((progress - 0.42) / 0.45)
        golden = 0.048 * np.sin(2.0 * np.pi * 392.0 * t + 0.1) * env
        tone = rings * (1.0 - blend) + golden * blend
        left, right = tone, tone * 0.94
    elif kind == "four_to_unison":
        initial = (196.00, 246.94, 293.66, 392.00)
        target = 261.63
        voices = []
        for voice_index, start_frequency in enumerate(initial):
            delta = target - start_frequency
            phase = 2.0 * np.pi * (start_frequency * t + delta * t * t / (2.0 * duration))
            voices.append(np.sin(phase + voice_index * 0.23))
        weights = (0.34, 0.28, 0.22, 0.16)
        left_voice = sum(weight * voice for weight, voice in zip(weights, voices))
        right_voice = sum(weight * voice for weight, voice in zip(weights, voices[::-1]))
        left, right = env * 0.075 * left_voice, env * 0.075 * right_voice
    elif kind == "lock_resonance":
        click = 0.050 * noise * np.exp(-t * 115.0)
        resonance = (
            0.045 * np.sin(2.0 * np.pi * 523.25 * t)
            + 0.025 * np.sin(2.0 * np.pi * 659.25 * t + 0.18)
            + 0.015 * np.sin(2.0 * np.pi * 1_046.5 * t + 0.32)
        ) * np.exp(-t * 1.4) * env
        left, right = click + resonance, click * 0.92 + resonance * 0.97
    elif kind == "tuning_fork":
        fade = 1.0 - smooth_array(progress)
        fork = fade * (0.060 * np.sin(2.0 * np.pi * 440.0 * t) + 0.018 * np.sin(2.0 * np.pi * 880.0 * t + 0.08))
        left, right = fork, fork * 0.97
    elif kind == "pen_touch":
        high_noise = noise - np.convolve(noise, np.ones(17, dtype=np.float32) / 17.0, mode="same")
        nib = (0.075 * high_noise + 0.030 * np.sin(2.0 * np.pi * 1_260.0 * t)) * np.exp(-t * 54.0)
        nib *= smooth_array(np.minimum(1.0, t / 0.0018))
        left, right = nib, nib * 0.90
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
        "description": "Deterministic authored pencil, escapement, gear, error, caliper, ring, unison, lock, tuning-fork, and fountain-pen sounds; no third-party assets.",
        "events": onsets,
        "silenceWindowFrames": [SILENCE_START_FRAME, SILENCE_END_FRAME],
        "voiceDuckDB": -9.0,
        "speechIntelligibilityNotch": {"startHz": 1_000, "endHz": 4_000, "attenuationDB": -12.0, "appliedToEvents": "all events; includes all narration overlaps"},
        "noiseSource": "fixed xorshift32 seed derived from event ID; no runtime random source",
        "postBlackout": ["pen_touch"],
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


def verify_pen_touch(path: Path) -> int:
    try:
        with wave.open(str(path), "rb") as wav:
            params = wav.getparams()
            expected = (SAMPLE_RATE, 2, 2, TOTAL_SAMPLES, "NONE")
            actual = (params.framerate, params.nchannels, params.sampwidth, params.nframes, params.comptype)
            if actual != expected:
                raise AudioBuildError(f"{path.name} has unexpected format before pen-touch verification")
            wav.setpos(PEN_TOUCH_FRAME * SAMPLES_PER_FRAME)
            raw = wav.readframes(round(0.16 * SAMPLE_RATE))
    except (OSError, wave.Error) as exc:
        raise AudioBuildError(f"cannot read pen-touch interval from {path.name}: {exc}") from None
    values = array.array("h")
    values.frombytes(raw)
    peak = max((abs(value) for value in values), default=0)
    if peak == 0:
        raise AudioBuildError(f"{path.name} lost the fountain-pen touch at frame {PEN_TOUCH_FRAME}")
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
    captions = build_captions(segments, segment_timing)
    scratch_parent = agentdev_scratch_parent()
    AUDIO.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="si-ep12-audio-", dir=str(scratch_parent)) as scratch_name:
        scratch = Path(scratch_name)
        outputs: dict[str, Any] = {}
        outputs["narration"] = render_narration(scratch / "narration.wav", spans)
        outputs["score"] = render_score(scratch / "score.wav", segment_timing)
        outputs["sfx"], sfx_onsets = render_sfx(scratch / "sfx.wav", events, segment_timing)
        for name in ("narration", "score", "sfx"):
            verify_silence(scratch / f"{name}.wav")
        sfx_pen_touch_peak = verify_pen_touch(scratch / "sfx.wav")
        outputs["master"] = mix_master(scratch / "master.wav", [scratch / name for name in ("narration.wav", "score.wav", "sfx.wav")])
        master_pen_touch_peak = verify_pen_touch(scratch / "master.wav")
        for name in ("narration", "score", "sfx", "master"):
            if outputs[name]["sizeBytes"] >= 100 * 1024 * 1024:
                raise AudioBuildError(f"{name}.wav unexpectedly exceeds the 100 MiB tracked-audio limit")
        input_hashes = {
            "segmentsJson": sha_file(SEGMENTS_PATH),
            "sfxEventsJson": sha_file(EVENTS_PATH),
            "audioAuthorization": sha_file(AUTHORIZATION_PATH),
            "audioTimingOverrides": sha_file(TIMING_OVERRIDES_PATH),
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
            "captionTimingMethod": "Unchanged original display-subtitle chunks are allocated by character weight within measured active PCM spans; S02 alone extends to approved frame 1264; no ASR or forced word alignment was performed.",
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
            "cuePlacement": "all complete source cues retained; S01-S07 active onset aligned to authored start, with only approved S02 complete-cue extension into the reserved gap; S08 complete cue starts 67 samples after frame 4890 and active voice starts at frame 4902",
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
            "penTouch": {
                "startFrame": PEN_TOUCH_FRAME,
                "startSample": PEN_TOUCH_FRAME * SAMPLES_PER_FRAME,
                "sampleCount": round(0.16 * SAMPLE_RATE),
                "endsBeforeFrame": MIN_S08_VOICE_START_FRAME,
                "sfxSamplePeakPcm16": sfx_pen_touch_peak,
                "masterSamplePeakPcm16": master_pen_touch_peak,
                "touchRetained": True,
            },
            "absoluteSilence": silence,
            "masterLoudness": outputs["master"]["ebur128Final"],
            "normalizationTarget": outputs["master"]["normalizationTarget"],
            "penTouchSamplePeakPcm16": {"sfx": sfx_pen_touch_peak, "master": master_pen_touch_peak},
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
