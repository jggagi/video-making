#!/usr/bin/env python3
"""Build EP14's measured narration, procedural stems, exact silence, captions, and PCM master."""

from __future__ import annotations

import array
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
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
OVERRIDES_PATH = PROJECT / "audio-timing-overrides.json"
PROVIDER_MANIFEST_PATH = AUDIO / "provider-manifest.json"
TIMING_PATH = PROJECT / "audio-timing.json"
TIMING_OVERRIDE_RECORD = "project/audio-timing-overrides.json"
QA_PATH = WORK / "review" / "audio-qa.json"
SRT_PATH = WORK / "小红书" / "captions.srt"
MIX_SETTINGS_PATH = AUDIO / "mix-settings.json"
MIX_MANIFEST_PATH = AUDIO / "mix-manifest.json"
AGENTDEV_ROOT = Path("/Volumes/AgentDev")

FPS = 60
SAMPLE_RATE = 48_000
SAMPLES_PER_FRAME = 800
DURATION_SECONDS = 90
TOTAL_FRAMES = FPS * DURATION_SECONDS
TOTAL_SAMPLES = SAMPLE_RATE * DURATION_SECONDS
BLOCK_SAMPLES = 24_000
SILENCE_START_FRAME = 4_860
SILENCE_END_FRAME = 4_890
SILENCE_START_SAMPLE = SILENCE_START_FRAME * SAMPLES_PER_FRAME
SILENCE_END_SAMPLE = SILENCE_END_FRAME * SAMPLES_PER_FRAME
MIN_S08_VOICE_START_FRAME = 4_902
MIN_S08_VOICE_START_SAMPLE = MIN_S08_VOICE_START_FRAME * SAMPLES_PER_FRAME
SNAP_ATTACK_START_FRAME = 4_859
SNAP_ATTACK_START_SAMPLE = SNAP_ATTACK_START_FRAME * SAMPLES_PER_FRAME
LUFS_TARGET = -16.0
LUFS_TOLERANCE = 0.1
LIMITER_TARGET_DBTP = -1.8
TRUE_PEAK_ACCEPTANCE_DBTP = -1.0
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
EVENT_ANCHORS = [
    ("ecg_message_chime", 60),
    ("warm_breath_granular", 840),
    ("indigo_membrane_seal", 1_500),
    ("gentle_harmony_60bpm", 2_220),
    ("low_cancellation_glass", 2_940),
    ("wet_cellular_engulf_tension", 3_900),
    ("trembling_sine_heartbeat", 4_500),
    ("bubble_pop_cut", 4_860),
    ("solitary_bowed_cello_harmonic", 4_890),
]


class AudioBuildError(RuntimeError):
    pass


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    return sha_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    if temporary.exists():
        raise AudioBuildError(f"temporary metadata file already exists; preserved: {temporary}")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AudioBuildError(f"cannot read {label}: {exc}") from None


def load_segments() -> list[dict[str, Any]]:
    segments = read_json(SEGMENTS_PATH, "segments.json")
    if not isinstance(segments, list) or [item.get("id") for item in segments] != EXPECTED_IDS:
        raise AudioBuildError("segments.json must contain S01 through S08 in source order")
    for item in segments:
        if not isinstance(item.get("display_subtitle"), str) or not item["display_subtitle"].strip():
            raise AudioBuildError(f"{item['id']} has no display_subtitle")
        start, end = item.get("startFrame"), item.get("endFrame")
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= TOTAL_FRAMES:
            raise AudioBuildError(f"{item['id']} has invalid authored frame bounds")
    return segments


def load_events() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    authored = read_json(EVENTS_PATH, "sfx_events.json")
    if (authored.get("fps"), authored.get("sampleRate"), authored.get("samplesPerFrame")) != (FPS, SAMPLE_RATE, SAMPLES_PER_FRAME):
        raise AudioBuildError("sfx_events.json units differ from 60 fps / 48 kHz")
    silence = authored.get("absoluteSilence")
    expected_silence = {
        "startFrame": SILENCE_START_FRAME,
        "endFrameExclusive": SILENCE_END_FRAME,
        "startSample": SILENCE_START_SAMPLE,
        "endSampleExclusive": SILENCE_END_SAMPLE,
        "scope": ["narration", "score", "sfx", "master"],
        "requireExactZero": True,
    }
    if silence != expected_silence or authored.get("voiceMinimumOnsetFrame") != MIN_S08_VOICE_START_FRAME:
        raise AudioBuildError("sfx_events.json does not preserve the assigned blackout or S08 voice minimum")
    events = authored.get("events")
    if not isinstance(events, list) or [(event.get("kind"), event.get("frame")) for event in events] != EVENT_ANCHORS:
        raise AudioBuildError("sfx_events.json event IDs/order/anchors differ from the assigned EP14 audio plan")
    dodge = authored.get("speechDodge")
    if not isinstance(dodge, dict) or dodge.get("enabled") is not True:
        raise AudioBuildError("sfx_events.json must enable voice-driven SFX/score ducking")
    for event in events:
        start, end = event.get("startFrame"), event.get("endFrameExclusive")
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= TOTAL_FRAMES:
            raise AudioBuildError(f"{event.get('id')} has invalid frame bounds")
        event["startSample"] = start * SAMPLES_PER_FRAME
        event["endSampleExclusive"] = end * SAMPLES_PER_FRAME
        event["sampleCount"] = (end - start) * SAMPLES_PER_FRAME
        event["durationSeconds"] = (end - start) / FPS
        event["bus"] = "score" if event["kind"] in {"gentle_harmony_60bpm", "solitary_bowed_cello_harmonic"} else "sfx"
    snap = authored.get("snapBoundary")
    if snap != {
        "anchorFrame": SILENCE_START_FRAME,
        "attackStartFrame": SNAP_ATTACK_START_FRAME,
        "attackStartSample": SNAP_ATTACK_START_SAMPLE,
        "endSampleExclusive": SILENCE_START_SAMPLE,
        "detail": "The one-frame bubble pop-cut attack ends exactly at sample 3888000, before the 30-frame absolute-silence interval.",
    }:
        raise AudioBuildError("sfx_events.json bubble pop-cut must stop exactly at the blackout boundary")
    return events, silence, dodge


def load_overrides() -> dict[str, Any]:
    value = read_json(OVERRIDES_PATH, "audio-timing-overrides.json")
    if value.get("version") != 1 or (value.get("fps"), value.get("sampleRate"), value.get("samplesPerFrame")) != (FPS, SAMPLE_RATE, SAMPLES_PER_FRAME):
        raise AudioBuildError("audio-timing-overrides.json has an unsupported version or time base")
    source = value.get("decisionSource")
    entries = value.get("segments")
    if not isinstance(source, str) or not source.strip() or not isinstance(entries, dict) or set(entries) != set(EXPECTED_IDS):
        raise AudioBuildError("audio-timing-overrides.json must contain a decisionSource and all eight segment placements")
    allowed = {"cueStartSample", "activeStartSample", "activeStartFrame", "omitTrailingZeroSamples", "terminalZeroEvidence", "reason"}
    for sid, entry in entries.items():
        if not isinstance(entry, dict) or set(entry) - allowed:
            raise AudioBuildError(f"invalid timing override fields for {sid}")
        if type(entry.get("cueStartSample")) is not int or type(entry.get("activeStartSample")) is not int:
            raise AudioBuildError(f"{sid} needs integer cueStartSample and activeStartSample")
        if not isinstance(entry.get("activeStartFrame"), (int, float)) or not isinstance(entry.get("reason"), str):
            raise AudioBuildError(f"{sid} needs activeStartFrame and a placement reason")
        omitted = entry.get("omitTrailingZeroSamples", 0)
        if type(omitted) is not int or omitted < 0:
            raise AudioBuildError(f"{sid} omitTrailingZeroSamples must be a non-negative integer")
    return value


def verify_provider_manifest(segments: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = read_json(PROVIDER_MANIFEST_PATH, "provider-manifest.json")
    if manifest.get("settings") != SETTINGS or not isinstance(manifest.get("segments"), dict):
        raise AudioBuildError("provider-manifest.json settings differ from this authorized audio task")
    if set(manifest["segments"]) != set(EXPECTED_IDS):
        raise AudioBuildError("provider-manifest.json does not contain every measured cue")
    preflight_path = WORK / "review" / "provider-preflight.json"
    preflight = read_json(preflight_path, "provider-preflight.json")
    auth = read_json(PROJECT / "audio-authorization.json", "audio-authorization.json")
    auth_hash = sha_file(PROJECT / "audio-authorization.json")
    if preflight.get("authorization", {}).get("sha256") != auth_hash:
        raise AudioBuildError("provider-preflight authorization hash differs from the current record")
    expected_text_hash = sha_bytes(json.dumps([s["tts_phonetic_text"] for s in segments], ensure_ascii=False).encode("utf-8"))
    if auth.get("text_sha256") != expected_text_hash or preflight.get("orderedTextSha256") != expected_text_hash:
        raise AudioBuildError("authorization/preflight text hash does not match the exact prepared source text")
    if preflight.get("authStatus", {}).get("authenticated") is not True:
        raise AudioBuildError("provider-preflight does not confirm authenticated CLI state")
    if preflight.get("settings") != SETTINGS:
        raise AudioBuildError("provider-preflight settings differ from the authorized audio task")
    calls = preflight.get("calls")
    if not isinstance(calls, list) or {call.get("segmentId") for call in calls} != set(EXPECTED_IDS):
        raise AudioBuildError("provider-preflight does not contain exactly one recorded call identity per cue")
    for call in calls:
        if call.get("status") != "succeeded" or call.get("reportedModels") != [SETTINGS["effective_model"]] or call.get("reportedVoices") != [SETTINGS["voice"]]:
            raise AudioBuildError(f"provider-preflight identity/status mismatch for {call.get('segmentId')}")
    for segment in segments:
        sid = segment["id"]
        entry = manifest["segments"][sid]
        if entry.get("settings") != SETTINGS or entry.get("ttsPhoneticText") != segment["tts_phonetic_text"]:
            raise AudioBuildError(f"{sid} manifest text or TTS settings differ from the authorized source")
        if entry.get("effectiveModel") != SETTINGS["effective_model"] or entry.get("effectiveVoice") != SETTINGS["voice"]:
            raise AudioBuildError(f"{sid} effective model/voice differs from the approved request")
        for file_key, hash_key in (("rawPath", "rawSha256"), ("canonicalPath", "canonicalSha256"), ("cuePath", "cueSha256")):
            path = (PROJECT / entry[file_key]).resolve()
            if not path.is_relative_to(PROJECT.resolve()) or not path.is_file():
                raise AudioBuildError(f"{sid} has a missing/out-of-project {file_key}")
            if sha_file(path) != entry[hash_key]:
                raise AudioBuildError(f"{sid} {file_key} hash differs from the manifest; preserved")
        if not isinstance(entry.get("completeCueFitsDeclaredWindow"), bool):
            raise AudioBuildError(f"{sid} fit measurement is missing")
    return manifest, preflight


def load_cues(segments: list[dict[str, Any]], manifest: dict[str, Any]) -> tuple[dict[str, np.ndarray], dict[str, dict[str, Any]]]:
    cues: dict[str, np.ndarray] = {}
    entries: dict[str, dict[str, Any]] = {}
    for segment in segments:
        sid = segment["id"]
        entry = manifest["segments"][sid]
        cue_path = PROJECT / entry["cuePath"]
        with wave.open(str(cue_path), "rb") as wav:
            params = wav.getparams()
            payload = wav.readframes(params.nframes)
        if (params.framerate, params.nchannels, params.sampwidth, params.comptype) != (SAMPLE_RATE, 1, 2, "NONE"):
            raise AudioBuildError(f"{sid} cue must be mono 48 kHz PCM16")
        if len(payload) != params.nframes * 2 or params.nframes != entry.get("actualSamples48k"):
            raise AudioBuildError(f"{sid} cue sample count differs from its measured manifest")
        samples = np.frombuffer(payload, dtype="<i2").astype(np.float32) / 32768.0
        cues[sid] = samples
        entries[sid] = entry
    return cues, entries


def cue_timing(segments: list[dict[str, Any]], cues: dict[str, np.ndarray], cue_entries: dict[str, dict[str, Any]], overrides: dict[str, Any]) -> tuple[list[dict[str, Any]], np.ndarray, list[dict[str, Any]]]:
    voice = np.zeros((TOTAL_SAMPLES, 2), dtype=np.float32)
    measured: list[dict[str, Any]] = []
    placed_ranges: list[tuple[str, int, int]] = []
    for segment in segments:
        sid = segment["id"]
        cue = cues[sid]
        entry = cue_entries[sid]
        override = overrides["segments"][sid]
        start = override["cueStartSample"]
        onset = entry["activeOnsetOffsetSamples48k"]
        active_end_offset = entry["activeEndOffsetSamples48kExclusive"]
        voice_start = start + onset
        voice_end = start + active_end_offset
        if override["activeStartSample"] != voice_start:
            raise AudioBuildError(f"NEEDS_SOL: {sid} override activeStartSample disagrees with measured onset")
        frame_position = voice_start / SAMPLES_PER_FRAME
        if abs(float(override["activeStartFrame"]) - frame_position) > 1e-8:
            raise AudioBuildError(f"NEEDS_SOL: {sid} override activeStartFrame disagrees with measured sample")
        omitted = override.get("omitTrailingZeroSamples", 0)
        if omitted:
            if sid != "S08" or omitted >= len(cue):
                raise AudioBuildError(f"NEEDS_SOL: only S08 may omit verified terminal zero padding")
            if np.any(cue[-omitted:] != 0.0):
                raise AudioBuildError("NEEDS_SOL: S08 terminal samples are not exact zero; no audio has been shortened")
            evidence = override.get("terminalZeroEvidence", {})
            if evidence.get("sampleRate") != SAMPLE_RATE or evidence.get("sampleCount") != omitted or evidence.get("exactDigitalZero") is not True or evidence.get("peakPcm16") != 0:
                raise AudioBuildError("NEEDS_SOL: S08 zero-tail omission lacks matching evidence")
        placement_count = len(cue) - omitted
        cue_end = start + placement_count
        if start < 0 or cue_end > TOTAL_SAMPLES or start >= cue_end:
            raise AudioBuildError(f"NEEDS_SOL: {sid} placement falls outside the exact 90-second master")
        if voice_start < 0 or voice_end > TOTAL_SAMPLES:
            raise AudioBuildError(f"NEEDS_SOL: {sid} measured speech falls outside the master")
        if sid == "S08":
            if start < SILENCE_END_SAMPLE or voice_start < MIN_S08_VOICE_START_SAMPLE:
                raise AudioBuildError("NEEDS_SOL: S08 placement overlaps blackout or starts before frame 4902")
        elif start < SILENCE_END_SAMPLE and cue_end > SILENCE_START_SAMPLE:
            raise AudioBuildError(f"NEEDS_SOL: {sid} cue overlaps the absolute-silence interval")
        if sid == "S07" and cue_end > SNAP_ATTACK_START_SAMPLE:
            raise AudioBuildError("NEEDS_SOL: S07 complete cue reaches the bubble pop-cut attack")
        mono = cue[:placement_count]
        voice[start:cue_end, 0] += mono * 0.78
        voice[start:cue_end, 1] += mono * 0.78
        placed_ranges.append((sid, voice_start, voice_end))
        measured.append({
            "id": sid,
            "declaredStartFrame": segment["startFrame"],
            "declaredEndFrame": segment["endFrame"],
            "cueStartSample": start,
            "cueEndSampleExclusive": cue_end,
            "sourceCueEndSampleExclusive": start + len(cue),
            "omittedVerifiedTrailingZeroSamples": omitted,
            "cueSamplesAt48k": len(cue),
            "placedSamples": placement_count,
            "voiceStartSample": voice_start,
            "voiceEndSampleExclusive": voice_end,
            "activeOnsetOffsetSamples": onset,
            "activeEndOffsetSamplesExclusive": active_end_offset,
            "activeDurationSeconds": (active_end_offset - onset) / SAMPLE_RATE,
            "completeCueDurationSeconds": len(cue) / SAMPLE_RATE,
            "activeBoundsMethod": entry["activeBoundsMethod"],
            "timingDecision": overrides["decisionSource"],
            "placementReason": override["reason"],
        })
    placed_ranges.sort(key=lambda item: item[1])
    for (prior_id, _, prior_end), (current_id, current_start, _) in zip(placed_ranges, placed_ranges[1:]):
        if prior_end > current_start:
            raise AudioBuildError(f"NEEDS_SOL: active narration overlaps between {prior_id} and {current_id}")
    tail_start=max(item[2] for item in placed_ranges)
    if tail_start>=TOTAL_SAMPLES:
        raise AudioBuildError("the final measured active voice span leaves no natural master-tail fade")
    tail_gain=np.linspace(1.0,0.0,TOTAL_SAMPLES-tail_start,dtype=np.float32)
    voice[tail_start:,0]*=tail_gain
    voice[tail_start:,1]*=tail_gain
    voice[SILENCE_START_SAMPLE:SILENCE_END_SAMPLE] = 0.0
    return measured, voice, placed_ranges


def smooth01(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def voice_duck_gain(measured: list[dict[str, Any]], dodge: dict[str, Any], bus: str) -> np.ndarray:
    pre = round(float(dodge["preAttackMilliseconds"]) * SAMPLE_RATE / 1000)
    release = round(float(dodge["releaseMilliseconds"]) * SAMPLE_RATE / 1000)
    attenuation = float(dodge["scoreAttenuationDB"] if bus == "score" else dodge["sfxAttenuationDB"])
    duck_value = 10.0 ** (attenuation / 20.0)
    envelope = np.zeros(TOTAL_SAMPLES, dtype=np.float32)
    for item in measured:
        start, end = item["voiceStartSample"], item["voiceEndSampleExclusive"]
        ramp_start = max(0, start - pre)
        if start > ramp_start:
            x = np.arange(start - ramp_start, dtype=np.float32) / max(1, start - ramp_start)
            envelope[ramp_start:start] = np.maximum(envelope[ramp_start:start], smooth01(x))
        envelope[start:end] = 1.0
        ramp_end = min(TOTAL_SAMPLES, end + release)
        if ramp_end > end:
            x = np.arange(ramp_end - end, dtype=np.float32) / max(1, ramp_end - end)
            envelope[end:ramp_end] = np.maximum(envelope[end:ramp_end], 1.0 - smooth01(x))
    return 1.0 - (1.0 - duck_value) * envelope


def seeded_noise(count: int, event_id: str) -> np.ndarray:
    seed = int.from_bytes(hashlib.sha256(event_id.encode("utf-8")).digest()[:8], "little")
    return np.random.default_rng(seed).standard_normal(count, dtype=np.float32)


def event_wave(kind: str, count: int, event_id: str) -> tuple[np.ndarray, np.ndarray]:
    t = np.arange(count, dtype=np.float64) / SAMPLE_RATE
    duration = count / SAMPLE_RATE
    u = np.clip(t / max(duration, 1.0 / SAMPLE_RATE), 0.0, 1.0)
    noise = seeded_noise(count, event_id).astype(np.float64)
    if kind == "ecg_message_chime":
        flat = 0.0035*np.sin(2*np.pi*880.0*t)*np.clip(1.0-t/0.2,0.0,1.0)
        chime = np.zeros(count, dtype=np.float64)
        for at, freq, amp in ((0.0, 784.0, 0.12), (0.24, 988.0, 0.105)):
            local = np.maximum(t-at, 0.0)
            vibrato_phase=2*np.pi*freq*local+0.7*np.sin(2*np.pi*4.2*local)
            note_fade=smooth01(np.clip(local/0.008,0.0,1.0))
            chime += np.where(t >= at, amp*np.sin(vibrato_phase)*np.exp(-local*3.2)*note_fade, 0.0)
        left, right = flat + chime, flat*0.96 + chime*0.86
    elif kind == "warm_breath_granular":
        breath = 0.035*np.sin(2*np.pi*103*t) + 0.025*np.sin(2*np.pi*157*t + 0.3)
        slow = (0.35 + 0.65*np.sin(np.pi*np.clip(t/6.0,0,1))**2) * (0.85+0.15*np.sin(2*np.pi*0.18*t))
        grains = np.zeros(count, dtype=np.float64)
        for at in np.arange(0.12, duration, 0.17):
            local = np.maximum(0.0, t-at)
            grains += np.where(t>=at, 0.007*noise*np.exp(-local*24.0), 0.0)
        emerald = 0.018*noise*np.sin(2*np.pi*(5.0+11.0*u)*t)
        morph = smooth01(u)
        value = (1-morph)*(breath*slow + grains) + morph*(0.55*breath*slow + emerald)
        left, right = value, value*0.91 + 0.004*np.sin(2*np.pi*1.5*t)
    elif kind == "indigo_membrane_seal":
        attack = smooth01(np.minimum(1.0, t/0.04))
        decay = np.exp(-t*(0.42+0.18*u))
        modes = (0.060*np.sin(2*np.pi*113*t) + 0.036*np.sin(2*np.pi*169*t+0.21)
                 + 0.024*np.sin(2*np.pi*242*t+0.43) + 0.014*np.sin(2*np.pi*331*t+0.68))
        seal = 0.055*noise*np.exp(-t*32.0)
        left, right = attack*decay*modes+seal, attack*decay*(modes*0.92)-seal*0.57
    elif kind == "gentle_harmony_60bpm":
        phase = np.mod(t,4.0)
        chord_a = (220.0, 277.18, 329.63)
        chord_b = (196.0, 246.94, 293.66)
        weight_b=np.zeros(count,dtype=np.float64)
        weight_b[(phase>=2.25)&(phase<3.75)]=1.0
        ab=(phase>=1.75)&(phase<2.25)
        weight_b[ab]=smooth01((phase[ab]-1.75)/0.5)
        ba=phase>=3.75
        weight_b[ba]=1.0-smooth01((phase[ba]-3.75)/0.5)
        value = np.zeros(count, dtype=np.float64)
        for idx, freq in enumerate(chord_a):
            value += (1.0-weight_b)*0.026/(idx+1)*np.sin(2*np.pi*freq*t+idx*0.13)
        for idx, freq in enumerate(chord_b):
            value += weight_b*0.024/(idx+1)*np.sin(2*np.pi*freq*t+idx*0.17)
        pulse = 0.65 + 0.35*np.sin(np.pi*np.mod(t, 1.0))**2
        value *= pulse * (0.8+0.2*smooth01(u))
        left, right = value, value*0.96 + 0.003*np.sin(2*np.pi*0.07*t)
    elif kind == "low_cancellation_glass":
        erase = 1.0-smooth01(u)
        low = erase*0.052*(np.sin(2*np.pi*54.0*t)-np.sin(2*np.pi*55.0*t))
        glass = 0.018*(0.3+0.7*smooth01(u))*np.sin(2*np.pi*1568.0*t+0.1*np.sin(2*np.pi*0.2*t))
        glass += 0.008*np.sin(2*np.pi*2093.0*t+0.3)
        left, right = low+glass, low*0.88+glass*0.78
    elif kind == "wet_cellular_engulf_tension":
        swell = smooth01(u)
        phase = 2*np.pi*(74*t + 13*t*t/max(duration,1e-6))
        bubbles = 0.028*np.sin(phase) + 0.021*np.sin(2.17*phase+0.4)
        wet = 0.015*noise*(0.3+0.7*swell)
        wet *= np.sin(2*np.pi*(1.8+0.8*u)*t)**2
        tension = 0.015*swell*np.sin(2*np.pi*(220+90*u)*t)
        left, right = bubbles+wet+tension, bubbles*0.93-wet*0.76+tension*0.88
    elif kind == "trembling_sine_heartbeat":
        tremble = 0.55+0.45*np.sin(2*np.pi*5.2*t)
        phase = 2*np.pi*(220*t + 1.7*np.sin(2*np.pi*0.8*t))
        heartbeat = np.zeros(count, dtype=np.float64)
        for at in np.arange(0.0, duration, 1.0):
            local = np.maximum(0.0, t-at)
            heartbeat += np.where(t>=at, 0.055*np.sin(2*np.pi*58*local)*np.exp(-local*13), 0.0)
        sine = 0.018*tremble*np.sin(phase)
        left, right = sine+heartbeat, sine*0.9+heartbeat*0.92
    elif kind == "bubble_pop_cut":
        envelope = np.exp(-t*420.0)
        click = 0.22*noise*envelope + 0.16*np.sin(2*np.pi*3200*t)*envelope
        bubble = 0.10*np.sin(2*np.pi*(330*t-28*t*t)) * np.exp(-t*260.0)
        left, right = click+bubble, click*0.73-bubble*0.82
    elif kind == "solitary_bowed_cello_harmonic":
        attack = smooth01(np.minimum(1.0, t/0.45))
        decay = np.exp(-t*0.27)
        bow = 0.004*noise*np.sin(2*np.pi*0.7*t)
        note = (0.072*np.sin(2*np.pi*196.0*t+0.12)
                + 0.018*np.sin(2*np.pi*392.0*t+0.27)
                + 0.006*np.sin(2*np.pi*588.0*t+0.4))
        left, right = attack*decay*(note+bow), attack*decay*(note*0.96-bow*0.7)
    else:
        raise AudioBuildError(f"unknown deterministic event kind {kind}")
    fade = np.ones(count, dtype=np.float64)
    fade[:min(count, 128)] *= np.linspace(0.0, 1.0, min(count, 128), endpoint=True)
    if kind not in {"bubble_pop_cut","solitary_bowed_cello_harmonic"}:
        fade_count=min(count,round(0.25*SAMPLE_RATE))
        fade[-fade_count:]*=1.0-smooth01(np.linspace(0.0,1.0,fade_count,endpoint=True))
    left *= fade
    right *= fade
    return left.astype(np.float32), right.astype(np.float32)


def notch_1_4khz(stereo: np.ndarray, attenuation_db: float) -> np.ndarray:
    if len(stereo) <= 1:
        return stereo
    count = stereo.shape[0]
    frequency = np.fft.rfftfreq(count, 1.0/SAMPLE_RATE)
    low = smooth01(np.clip((frequency-850.0)/150.0,0,1))
    high = 1.0-smooth01(np.clip((frequency-4_000.0)/600.0,0,1))
    band = low*high
    attenuation = 10.0**(attenuation_db/20.0)
    gain = 1.0-(1.0-attenuation)*band
    filtered = np.empty_like(stereo,dtype=np.float32)
    for channel in range(2):
        filtered[:,channel]=np.fft.irfft(np.fft.rfft(stereo[:,channel].astype(np.float64))*gain,n=count).astype(np.float32)
    return filtered


def render_event_stems(events: list[dict[str, Any]], measured: list[dict[str, Any]], dodge: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    sfx=np.zeros((TOTAL_SAMPLES,2),dtype=np.float32)
    score=np.zeros((TOTAL_SAMPLES,2),dtype=np.float32)
    sfx_gain=voice_duck_gain(measured,dodge,"sfx")
    score_gain=voice_duck_gain(measured,dodge,"score")
    metadata=[]
    notch=dodge.get("speechIntelligibilityNotch",{})
    for event in events:
        start,end=event["startSample"],event["endSampleExclusive"]
        if start < SILENCE_END_SAMPLE and end > SILENCE_START_SAMPLE:
            raise AudioBuildError(f"{event['id']} overlaps absolute silence")
        left,right=event_wave(event["kind"],event["sampleCount"],event["id"])
        stereo=np.column_stack((left,right))
        extra={}
        if event["bus"]=="sfx" and notch:
            stereo=notch_1_4khz(stereo,float(notch["attenuationDB"]))
            gain=sfx_gain[start:end]
            emitted=stereo*gain[:,None]
            sfx[start:end]+=emitted
        else:
            gain=score_gain[start:end]
            emitted=stereo*gain[:,None]
            score[start:end]+=emitted
        if event["kind"]=="ecg_message_chime":
            first_samples=round(0.05*SAMPLE_RATE)
            second_offset=round(0.24*SAMPLE_RATE)
            second_samples=round(0.05*SAMPLE_RATE)
            first_peak=float(np.max(np.abs(emitted[:first_samples])))
            second_peak=float(np.max(np.abs(emitted[second_offset:second_offset+second_samples])))
            if event["startFrame"]!=60 or event["startSample"]!=60*SAMPLES_PER_FRAME or first_peak<0.01 or second_peak<0.01:
                raise AudioBuildError("message chime must sound at frame 60 and again 240 ms later")
            extra={"audibleOnsets":[
                {"label":"first_note","offsetSample":0,"globalSample":start,"frame":event["startFrame"]},
                {"label":"second_note","offsetSample":second_offset,"globalSample":start+second_offset,"offsetSeconds":0.24},
            ],"postDuckNotchWindowPeak":[first_peak,second_peak]}
        metadata.append({k:event[k] for k in ("id","frame","startFrame","endFrameExclusive","startSample","endSampleExclusive","sampleCount","durationSeconds","kind","bus","description")} | extra)
    tail_start=max(item["voiceEndSampleExclusive"] for item in measured)
    tail_gain=np.linspace(1.0,0.0,TOTAL_SAMPLES-tail_start,dtype=np.float32)
    sfx[tail_start:,:]*=tail_gain[:,None]
    score[tail_start:,:]*=tail_gain[:,None]
    sfx[SILENCE_START_SAMPLE:SILENCE_END_SAMPLE]=0.0
    score[SILENCE_START_SAMPLE:SILENCE_END_SAMPLE]=0.0
    return sfx,score,metadata


def write_pcm16(path: Path, stereo: np.ndarray, *, refuse_existing: bool = True) -> dict[str, Any]:
    if stereo.shape != (TOTAL_SAMPLES,2):
        raise AudioBuildError(f"{path.name} array shape {stereo.shape} is not exactly 90 seconds stereo")
    if refuse_existing and path.exists():
        raise AudioBuildError(f"output already exists and will not be overwritten: {path}")
    peak=float(np.max(np.abs(stereo)))
    if not math.isfinite(peak) or peak > 0.999:
        raise AudioBuildError(f"{path.name} pre-write peak {peak} exceeds safe PCM headroom")
    path.parent.mkdir(parents=True,exist_ok=True)
    pcm=np.clip(np.rint(stereo*32767.0),-32768,32767).astype("<i2")
    with wave.open(str(path),"wb") as wav:
        wav.setnchannels(2); wav.setsampwidth(2); wav.setframerate(SAMPLE_RATE)
        for start in range(0,TOTAL_SAMPLES,BLOCK_SAMPLES):
            wav.writeframes(pcm[start:start+BLOCK_SAMPLES].tobytes())
    return validate_wav(path)


def validate_wav(path: Path) -> dict[str, Any]:
    try:
        with wave.open(str(path),"rb") as wav:
            params=wav.getparams()
            payload=wav.readframes(params.nframes)
    except (OSError,wave.Error) as exc:
        raise AudioBuildError(f"cannot decode {path}: {exc}") from None
    if (params.framerate,params.nchannels,params.sampwidth,params.comptype)!=(SAMPLE_RATE,2,2,"NONE"):
        raise AudioBuildError(f"{path.name} must be 48 kHz stereo PCM16")
    if params.nframes!=TOTAL_SAMPLES or len(payload)!=TOTAL_SAMPLES*4:
        raise AudioBuildError(f"{path.name} must contain exactly {TOTAL_SAMPLES} samples per channel")
    samples=np.frombuffer(payload,dtype="<i2").reshape(-1,2)
    silence_peak=int(np.max(np.abs(samples[SILENCE_START_SAMPLE:SILENCE_END_SAMPLE])))
    if silence_peak:
        raise AudioBuildError(f"{path.name} contains nonzero PCM in the absolute-silence interval")
    tail_start=TOTAL_SAMPLES-round(0.15*SAMPLE_RATE)
    return {
        "file":str(path),"sha256":sha_file(path),"pcmSha256":sha_bytes(payload),"sizeBytes":path.stat().st_size,
        "sampleRate":SAMPLE_RATE,"channels":2,"sampleWidthBytes":2,"samplesPerChannel":TOTAL_SAMPLES,
        "durationSeconds":DURATION_SECONDS,"samplePeakPcm16":int(np.max(np.abs(samples))),
        "terminalSamplePeakPcm16":int(np.max(np.abs(samples[-1]))),
        "final150msPeakPcm16":int(np.max(np.abs(samples[tail_start:]))),
        "absoluteSilence":{"startSample":SILENCE_START_SAMPLE,"endSampleExclusive":SILENCE_END_SAMPLE,"peakPcm16":silence_peak,"exactZero":True},
    }


def caption_phrases(source: str) -> list[str]:
    text=re.sub(r"\s+","",source)
    closing='”’」』）》】〕〉'
    punctuation=set("，。！？；：、…,.!?;:")
    phrases=[]; current=[]; index=0
    while index<len(text):
        current.append(text[index])
        if text[index] in punctuation:
            while index+1<len(text) and text[index+1] in punctuation:
                index+=1; current.append(text[index])
            while index+1<len(text) and text[index+1] in closing:
                index+=1; current.append(text[index])
            phrase="".join(current)
            if phrase: phrases.append(phrase)
            current=[]
        index+=1
    if current: phrases.append("".join(current))
    # Keep the source's explicit line boundaries as phrase boundaries when they remain meaningful.
    expanded=[]
    for phrase in phrases:
        while len(phrase)>26:
            cut=caption_breakpoint(phrase,26)
            expanded.append(phrase[:cut]); phrase=phrase[cut:]
        if phrase: expanded.append(phrase)
    if "".join(expanded)!=text:
        raise AudioBuildError("caption phrase splitting changed display_subtitle content")
    return expanded


def caption_breakpoint(text: str, maximum: int) -> int:
    limit=min(maximum,len(text)-1)
    preferred_after=set("，。！？；：、…：,;:")
    preferred_before=set("的了着过和与在把被就才还再只而但却又也更最是能可从向替")
    candidates=[]
    for cut in range(max(4,limit-10),limit+1):
        score=abs(maximum-cut)
        if text[cut-1] in preferred_after: score-=8
        if text[cut] in preferred_before: score-=6
        if text[cut-1] in "”’」』）》】" or text[cut] in "“‘「『（《【": score+=4
        candidates.append((score,cut))
    return min(candidates)[1] if candidates else limit


def wrap_caption(phrase: str) -> str:
    authored_breaks = {'他已经离开这个世界整整七年了。': '他已经离开这个世界\n整整七年了。', '偏爱的句尾语气词都分毫不差。': '偏爱的句尾语气词\n都分毫不差。', '超级智能只用他生前的五十万条聊天记录，': '超级智能只用他生前的\n五十万条聊天记录，', '你以为这是科技赐予思念的解药。': '你以为这是科技\n赐予思念的解药。', '甚至比生前更懂得接住你的情绪。': '甚至比生前更懂得\n接住你的情绪。', '那个百分之九十九点九相似的完美幽灵，': '那个百分之九十九点九\n相似的完美幽灵，', '把你脑海里仅存的那一点点真实血肉，': '把你脑海里仅存的\n那一点点真实血肉，', '屏幕那头再次弹出“我永远陪着你”，': '屏幕那头再次弹出\n“我永远陪着你”，', '它只是用一个永远不会离开的幻影，': '它只是用一个\n永远不会离开的幻影，'}
    if phrase in authored_breaks:
        return authored_breaks[phrase]
    if len(phrase)<=13:
        return phrase
    if len(phrase)>26:
        raise AudioBuildError("caption phrase is too long for two 13-character lines")
    cut=caption_breakpoint(phrase,13)
    punctuation=set("，。！？；：、…,.!?;:")
    closing=set("”’」』）》】〕〉")
    while cut > 4 and (phrase[cut] in punctuation or phrase[cut] in closing):
        cut-=1
    left,right=phrase[:cut],phrase[cut:]
    if len(left)>13 or len(right)>13 or not left or not right:
        raise AudioBuildError("caption line wrap exceeds 13 characters")
    return left+"\n"+right


def build_captions(segments: list[dict[str,Any]], measured: list[dict[str,Any]]) -> list[dict[str,Any]]:
    by_id={item["id"]:item for item in measured}
    result=[]
    for segment in segments:
        timing=by_id[segment["id"]]
        phrases=caption_phrases(segment["display_subtitle"])
        if not phrases: raise AudioBuildError(f"{segment['id']} has no caption phrases")
        if "".join(phrases)!=re.sub(r"\s+","",segment["display_subtitle"]):
            raise AudioBuildError(f"{segment['id']} captions do not preserve display text")
        weights=[len(text) for text in phrases]
        total=sum(weights)
        start=math.ceil(timing["voiceStartSample"]/SAMPLES_PER_FRAME)
        end=math.ceil(timing["voiceEndSampleExclusive"]/SAMPLES_PER_FRAME)
        frame_count=end-start
        if frame_count<len(phrases):
            raise AudioBuildError(f"{segment['id']} has too few active frames for its caption phrases")
        cumulative=0; prior=start
        for index,(phrase,weight) in enumerate(zip(phrases,weights)):
            cumulative+=weight
            if index==len(phrases)-1:
                next_frame=end
            else:
                next_frame=start+round(frame_count*cumulative/total)
                next_frame=min(end-(len(phrases)-index-1),max(prior+1,next_frame))
            text=wrap_caption(phrase)
            lines=text.split("\n")
            if len(lines)>2 or any(len(line)>13 for line in lines):
                raise AudioBuildError(f"caption exceeds two lines of 13 characters: {text!r}")
            result.append({"segmentId":segment["id"],"startFrame":prior,"endFrame":next_frame,"text":text,"alignment":"estimated_character_weighted_within_measured_active_PCM"})
            prior=next_frame
    for segment in segments:
        captions=[item for item in result if item["segmentId"]==segment["id"]]
        if "".join(item["text"].replace("\n","") for item in captions)!=re.sub(r"\s+","",segment["display_subtitle"]):
            raise AudioBuildError(f"{segment['id']} final caption text differs from display_subtitle")
    return result


def frame_srt_time(frame: int) -> str:
    milliseconds=round(frame*1000/FPS)
    hours,remaining=divmod(milliseconds,3_600_000)
    minutes,remaining=divmod(remaining,60_000)
    seconds,millis=divmod(remaining,1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def render_srt(captions: list[dict[str,Any]]) -> str:
    rows=[]
    for index,caption in enumerate(captions,1):
        rows.extend((str(index),f"{frame_srt_time(caption['startFrame'])} --> {frame_srt_time(caption['endFrame'])}",caption["text"],""))
    return "\n".join(rows)


def write_master_silence(path: Path) -> None:
    temporary=path.with_name(path.stem+".silence.tmp.wav")
    if temporary.exists(): raise AudioBuildError(f"silence-fix temporary exists; preserved: {temporary}")
    with wave.open(str(path),"rb") as wav:
        params=wav.getparams(); payload=wav.readframes(params.nframes)
    samples=np.frombuffer(payload,dtype="<i2").reshape(-1,2).copy()
    samples[SILENCE_START_SAMPLE:SILENCE_END_SAMPLE,:]=0
    with wave.open(str(temporary),"wb") as wav:
        wav.setnchannels(2); wav.setsampwidth(2); wav.setframerate(SAMPLE_RATE); wav.writeframes(samples.astype("<i2").tobytes())
    temporary.replace(path)


def run_ffmpeg(args: list[str], label: str) -> str:
    process=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,check=False)
    if process.returncode:
        lines=(process.stderr or process.stdout or "").strip().splitlines()[-6:]
        raise AudioBuildError(f"{label} failed with exit {process.returncode}: {' | '.join(lines)}")
    return process.stderr or ""


def parse_loudnorm(text: str) -> dict[str,Any]:
    matches=list(re.finditer(r"\{\s*\"input_i\"[\s\S]*?\}",text))
    if not matches: raise AudioBuildError("FFmpeg loudnorm measurement JSON was not found")
    value=json.loads(matches[-1].group(0))
    required=("input_i","input_tp","input_lra","input_thresh","target_offset")
    if any(key not in value for key in required): raise AudioBuildError("FFmpeg loudnorm measurement is incomplete")
    return value


def ebur128(path: Path) -> dict[str,float]:
    ffmpeg=shutil.which("ffmpeg")
    if not ffmpeg: raise AudioBuildError("ffmpeg is required for final loudness and true-peak verification")
    text=run_ffmpeg([ffmpeg,"-hide_banner","-nostats","-i",str(path),"-af","ebur128=peak=true","-f","null","-"],"EBU R128 measurement")
    integrated=re.search(r"^\s*I:\s*(-?\d+(?:\.\d+)?)\s+LUFS\s*$",text,re.MULTILINE)
    peak_matches=list(re.finditer(r"^\s*True peak:\s*(-?\d+(?:\.\d+)?)\s+dBTP\s*$",text,re.MULTILINE))
    if not peak_matches:
        peak_matches=list(re.finditer(r"True peak:\s*\n\s*Peak:\s*(-?\d+(?:\.\d+)?)\s+dBFS",text))
    if integrated is None or not peak_matches: raise AudioBuildError("FFmpeg ebur128 did not report LUFS and dBTP")
    peak=peak_matches[-1]
    return {"integratedLUFS":float(integrated.group(1)),"truePeakDBTP":float(peak.group(1))}


def calibrate_lufs(path: Path, measured: dict[str,float]) -> dict[str,Any]:
    gain_db=LUFS_TARGET-measured["integratedLUFS"]
    if abs(gain_db)<=LUFS_TOLERANCE:
        return {"appliedGainDB":0.0,"before":measured,"after":measured,"method":"no correction required"}
    temporary=path.with_name(path.stem+".gain.tmp.wav")
    if temporary.exists(): raise AudioBuildError(f"loudness-calibration temporary exists; preserved: {temporary}")
    gain=10.0**(gain_db/20.0)
    with wave.open(str(path),"rb") as wav:
        params=wav.getparams(); payload=wav.readframes(params.nframes)
    values=np.frombuffer(payload,dtype="<i2").reshape(-1,2).astype(np.float64)
    values[SILENCE_START_SAMPLE:SILENCE_END_SAMPLE,:]=0.0
    scaled=np.rint(values*gain)
    if float(np.max(np.abs(scaled)))>32767.0:
        raise AudioBuildError("LUFS correction would clip PCM; explicit limiter rerun is required")
    with wave.open(str(temporary),"wb") as wav:
        wav.setnchannels(2); wav.setsampwidth(2); wav.setframerate(SAMPLE_RATE); wav.writeframes(scaled.astype("<i2").tobytes())
    after=ebur128(temporary)
    if after["truePeakDBTP"]>TRUE_PEAK_ACCEPTANCE_DBTP:
        temporary.unlink(missing_ok=True)
        raise AudioBuildError(f"LUFS correction would exceed the -1 dBTP acceptance: {after}")
    temporary.replace(path)
    return {"appliedGainDB":gain_db,"before":measured,"after":after,"method":"linear PCM calibration after oversampled limiter; exact-zero interval preserved"}


def mix_master(premix: Path, output: Path) -> dict[str,Any]:
    ffmpeg=shutil.which("ffmpeg")
    if not ffmpeg: raise AudioBuildError("ffmpeg is required to create the PCM master")
    first=run_ffmpeg([
        ffmpeg,"-hide_banner","-nostats","-i",str(premix),"-af",
        f"loudnorm=I={LUFS_TARGET}:TP=-2.2:LRA=11:print_format=json","-f","null","-",
    ],"first-pass loudnorm analysis")
    first_measurement=parse_loudnorm(first)
    second_filter=(f"loudnorm=I={LUFS_TARGET}:TP=-2.2:LRA=11:measured_I={first_measurement['input_i']}"
        f":measured_TP={first_measurement['input_tp']}:measured_LRA={first_measurement['input_lra']}"
        f":measured_thresh={first_measurement['input_thresh']}:offset={first_measurement['target_offset']}"
        ":linear=true:print_format=json")
    normalized=output.with_name(output.stem+".normalized.tmp.wav")
    limited=output.with_name(output.stem+".limited.tmp.wav")
    if normalized.exists() or limited.exists() or output.exists():
        raise AudioBuildError("master output or temporary already exists; preserved")
    second=run_ffmpeg([
        ffmpeg,"-hide_banner","-nostats","-i",str(premix),"-af",second_filter,"-ar",str(SAMPLE_RATE),"-ac","2",
        "-c:a","pcm_s16le",str(normalized),
    ],"second-pass loudnorm render")
    second_measurement=parse_loudnorm(second)
    ceiling=10.0**(LIMITER_TARGET_DBTP/20.0)
    limiter_filter=(f"aresample=192000:resampler=swr,alimiter=limit={ceiling:.12f}:attack=5:release=50:latency=1:level=disabled,"
        f"aresample={SAMPLE_RATE}:resampler=swr:dither_method=none,atrim=end_sample={TOTAL_SAMPLES},asetpts=PTS-STARTPTS")
    run_ffmpeg([
        ffmpeg,"-hide_banner","-nostats","-i",str(normalized),"-af",limiter_filter,"-ar",str(SAMPLE_RATE),"-ac","2",
        "-c:a","pcm_s16le",str(limited),
    ],"4x oversampled true-peak limiter render")
    normalized.unlink(missing_ok=True)
    limited.replace(output)
    write_master_silence(output)
    before=ebur128(output)
    calibration=calibrate_lufs(output,before)
    write_master_silence(output)
    strict=run_ffmpeg([ffmpeg,"-hide_banner","-v","error","-xerror","-i",str(output),"-f","null","-"],"strict PCM master decode")
    final=ebur128(output)
    info=validate_wav(output)
    if not LUFS_TARGET-LUFS_TOLERANCE<=final["integratedLUFS"]<=LUFS_TARGET+LUFS_TOLERANCE:
        raise AudioBuildError(f"final master loudness {final['integratedLUFS']} LUFS is outside -16.0 ±0.1")
    if final["truePeakDBTP"]>TRUE_PEAK_ACCEPTANCE_DBTP:
        raise AudioBuildError(f"final master true peak {final['truePeakDBTP']} dBTP exceeds -1.0 dBTP")
    info.update({
        "strictDecode":"passed",
        "loudnormFirstPass":first_measurement,
        "loudnormSecondPass":second_measurement,
        "truePeakLimiter":{"oversampleFactor":4,"processingSampleRate":192000,"ceilingDBTP":LIMITER_TARGET_DBTP,"limitAmplitude":ceiling,"filter":"alimiter with latency compensation","explicitlyApplied":True},
        "ebur128Final":final,
        "normalizationTarget":{"integratedLUFS":LUFS_TARGET,"acceptanceLUFS":[LUFS_TARGET-LUFS_TOLERANCE,LUFS_TARGET+LUFS_TOLERANCE],"limiterTargetDBTP":LIMITER_TARGET_DBTP,"acceptanceTruePeakDBTP":TRUE_PEAK_ACCEPTANCE_DBTP},
        "postLimiterCalibration":calibration,
    })
    return info


def copy_verified(source: Path, destination: Path) -> dict[str,Any]:
    digest=sha_file(source)
    if destination.exists():
        if sha_file(destination)!=digest:
            raise AudioBuildError(f"existing output is divergent and was preserved: {destination}")
        return {"path":str(destination.relative_to(PROJECT)),"sha256":digest,"status":"matching output reused"}
    temporary=destination.with_name(destination.name+".tmp")
    if temporary.exists(): raise AudioBuildError(f"output copy temporary exists; preserved: {temporary}")
    shutil.copyfile(source,temporary)
    if sha_file(temporary)!=digest:
        temporary.unlink(missing_ok=True)
        raise AudioBuildError(f"scratch copy hash mismatch for {destination.name}")
    temporary.replace(destination)
    return {"path":str(destination.relative_to(PROJECT)),"sha256":digest,"status":"published from verified scratch"}


def build_timing(segments: list[dict[str,Any]], measured: list[dict[str,Any]]) -> tuple[dict[str,Any],str]:
    captions=build_captions(segments,measured)
    timing={
        "durationSeconds":DURATION_SECONDS,"fps":FPS,"sampleRate":SAMPLE_RATE,"samplesPerChannel":TOTAL_SAMPLES,
        "status":"MEASURED",
        "captionTimingMethod":"Estimated character-weighted phrase timing within measured active PCM. No ASR or forced word alignment was performed.",
        "segments":measured,
        "captions":[{k:item[k] for k in ("startFrame","endFrame","text")} | {"segmentId":item["segmentId"],"alignment":item["alignment"]} for item in captions],
        "timingOverride":"project/audio-timing-overrides.json",
    }
    return timing,render_srt(captions)


def ensure_output_absent(paths: list[Path]) -> None:
    existing=[str(path) for path in paths if path.exists()]
    if existing: raise AudioBuildError(f"audio build outputs already exist; preserving: {', '.join(existing[:4])}")


def preserve_preview_timing() -> None:
    if not TIMING_PATH.exists():
        return
    preview=read_json(TIMING_PATH,"existing audio-timing.json")
    if preview.get("status")!="PREVIEW_ONLY":
        raise AudioBuildError("existing audio-timing.json is not PREVIEW_ONLY; preserving it")
    destination=AUDIO/"history"/"preview-timing.json"
    raw=TIMING_PATH.read_bytes()
    if destination.exists():
        if destination.read_bytes()!=raw:
            raise AudioBuildError(f"existing preview archive is divergent and was preserved: {destination}")
        return
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=destination.with_name(destination.name+".tmp")
    if temporary.exists():
        raise AudioBuildError(f"preview archive temporary exists; preserved: {temporary}")
    temporary.write_bytes(raw)
    if sha_file(temporary)!=sha_bytes(raw):
        temporary.unlink(missing_ok=True)
        raise AudioBuildError("preview timing archive hash verification failed")
    temporary.replace(destination)


def run_build() -> int:
    segments=load_segments()
    events,silence,dodge=load_events()
    overrides=load_overrides()
    provider_manifest,preflight=verify_provider_manifest(segments)
    cues,cue_entries=load_cues(segments,provider_manifest)
    measured,narration,voice_ranges=cue_timing(segments,cues,cue_entries,overrides)
    sfx,score,event_records=render_event_stems(events,measured,dodge)
    output_targets = [
        *(AUDIO / name for name in ("narration.wav", "sfx.wav", "score.wav", "master.wav")),
        SRT_PATH, QA_PATH, MIX_SETTINGS_PATH, MIX_MANIFEST_PATH,
    ]
    ensure_output_absent(output_targets)
    if TIMING_PATH.exists() and read_json(TIMING_PATH,"existing audio-timing.json").get("status")!="PREVIEW_ONLY":
        raise AudioBuildError("existing audio-timing.json is not PREVIEW_ONLY; preserving it")
    if np.any(narration[SILENCE_START_SAMPLE:SILENCE_END_SAMPLE]) or np.any(sfx[SILENCE_START_SAMPLE:SILENCE_END_SAMPLE]) or np.any(score[SILENCE_START_SAMPLE:SILENCE_END_SAMPLE]):
        raise AudioBuildError("pre-mix blackout is not exact zero in all stems")
    for stem in (narration,sfx,score):
        if float(np.max(np.abs(stem)))>0.999:
            raise AudioBuildError("one or more pre-mix stems exceed safe PCM headroom")

    with tempfile.TemporaryDirectory(prefix="si-ep14-audio-",dir=str(AGENTDEV_ROOT)) as temp_dir:
        scratch=Path(temp_dir)
        narration_path=scratch/"narration.wav"
        sfx_path=scratch/"sfx.wav"
        score_path=scratch/"score.wav"
        premix_path=scratch/"premix.wav"
        master_path=scratch/"master.wav"
        narration_info=write_pcm16(narration_path,narration)
        sfx_info=write_pcm16(sfx_path,sfx)
        score_info=write_pcm16(score_path,score)
        premix=narration+sfx+score
        premix_peak=float(np.max(np.abs(premix)))
        if premix_peak>0.999:
            raise AudioBuildError(f"premix peak {premix_peak} would clip before loudness processing")
        premix_info=write_pcm16(premix_path,premix)
        master_info=mix_master(premix_path,master_path)
        output_map={
            "narration.wav":(narration_path,narration_info),
            "sfx.wav":(sfx_path,sfx_info),
            "score.wav":(score_path,score_info),
            "master.wav":(master_path,master_info),
        }
        target_paths=[AUDIO/name for name in output_map]
        ensure_output_absent(target_paths)
        published={name:copy_verified(source,AUDIO/name) for name,(source,_) in output_map.items()}
        # Validate published assets and exact blackout after the copy.
        published_info={name:validate_wav(AUDIO/name) for name in output_map}
        chime=next(item for item in event_records if item["kind"]=="ecg_message_chime")
        first_start=chime["startSample"]
        second_start=first_start+round(0.24*SAMPLE_RATE)
        window=round(0.05*SAMPLE_RATE)
        onset_peaks=[]
        for start in (first_start,second_start):
            peak=float(np.max(np.abs(sfx[start:start+window])))
            onset_peaks.append(peak)
        onset_peaks_pcm16=[int(round(peak*32767.0)) for peak in onset_peaks]
        if onset_peaks_pcm16[0]<300 or onset_peaks_pcm16[1]<300:
            raise AudioBuildError("the exported SFX stem does not preserve both audible message-chime notes")
        chime["postDuckNotchWindowPeak"]=onset_peaks
        chime["postDuckNotchWindowPeakPcm16"]=onset_peaks_pcm16
        timing,srt=build_timing(segments,measured)
        timing_path_tmp=TIMING_PATH.with_name(TIMING_PATH.name+".tmp")
        srt_tmp=SRT_PATH.with_name(SRT_PATH.name+".tmp")
        qa_tmp=QA_PATH.with_name(QA_PATH.name+".tmp")
        settings_tmp=MIX_SETTINGS_PATH.with_name(MIX_SETTINGS_PATH.name+".tmp")
        manifest_tmp=MIX_MANIFEST_PATH.with_name(MIX_MANIFEST_PATH.name+".tmp")
        targets=[SRT_PATH,QA_PATH,MIX_SETTINGS_PATH,MIX_MANIFEST_PATH]
        ensure_output_absent(targets+[timing_path_tmp,srt_tmp,qa_tmp,settings_tmp,manifest_tmp])
        QA_PATH.parent.mkdir(parents=True,exist_ok=True)
        SRT_PATH.parent.mkdir(parents=True,exist_ok=True)
        final_stats=master_info["ebur128Final"]
        qa={
            "version":1,"episode":"EP14","status":"MEASURED_PCM_QA",
            "source":{"segmentsSha256":sha_file(SEGMENTS_PATH),"authorizationSha256":sha_file(PROJECT/"audio-authorization.json"),"providerManifestSha256":sha_file(PROVIDER_MANIFEST_PATH),"providerPreflightSha256":sha_file(WORK/"review/provider-preflight.json"),"timingOverridesSha256":sha_file(OVERRIDES_PATH),"sfxEventsSha256":sha_file(EVENTS_PATH)},
            "provider":{"provider":"Aliyun Bailian","modelSelection":"active profile default","effectiveModel":SETTINGS["effective_model"],"voice":SETTINGS["voice"],"rate":SETTINGS["rate"],"callsRecorded":len(preflight["calls"]),"allIdentitiesMatched":True},
            "stems":{name:published_info[name] for name in ("narration.wav","sfx.wav","score.wav")},
            "master":published_info["master.wav"] | {"loudness":final_stats,"limiter":master_info["truePeakLimiter"]},
            "events":{"measured":event_records,"allAnchorsMatched":True,"snapAttackStartSample":SNAP_ATTACK_START_SAMPLE,"snapEndsAtSample":SILENCE_START_SAMPLE},
            "absoluteSilence":{"startFrame":SILENCE_START_FRAME,"endFrameExclusive":SILENCE_END_FRAME,"startSample":SILENCE_START_SAMPLE,"endSampleExclusive":SILENCE_END_SAMPLE,"exactZeroInNarrationScoreSfxMaster":True},
            "speech":{"allCuesCompleteExceptVerifiedTerminalZeroPadding":True,"sampleRate":SAMPLE_RATE,"rate":1.0,"activeRanges":[{"id":sid,"startSample":start,"endSampleExclusive":end} for sid,start,end in voice_ranges],
                "naturalTailFade":{"startSample":max(end for _,_,end in voice_ranges),"endSampleExclusive":TOTAL_SAMPLES,
                    "durationSeconds":(TOTAL_SAMPLES-max(end for _,_,end in voice_ranges))/SAMPLE_RATE,
                    "appliedAfterMeasuredActiveSpeechOnly":True,
                    "stemMeasurements":{name:{"final150msPeakPcm16":published_info[name]["final150msPeakPcm16"],"terminalSamplePeakPcm16":published_info[name]["terminalSamplePeakPcm16"]} for name in output_map}}},
            "captions":{"srt":str(SRT_PATH.relative_to(WORK)),"estimatedCharacterWeighted":True,"asrUsed":False,"allSourceDisplayTextPreserved":True,"maxLines":2,"maxCharactersPerLine":13,"orphanPunctuation":False},
            "scratch":{"volume":"AgentDev APFS","path":"verified by agent-dev run wrapper; scratch removed after successful publication"},
        }
        settings={
            "version":1,"fps":FPS,"sampleRate":SAMPLE_RATE,"samplesPerChannel":TOTAL_SAMPLES,"durationSeconds":DURATION_SECONDS,
            "narrationGainDB":20*math.log10(0.78),"scoreDuckDB":dodge["scoreAttenuationDB"],"sfxDuckDB":dodge["sfxAttenuationDB"],
            "duckPreAttackMilliseconds":dodge["preAttackMilliseconds"],"duckReleaseMilliseconds":dodge["releaseMilliseconds"],
            "speechIntelligibilityNotch":dodge["speechIntelligibilityNotch"],
            "masterNormalization":{"targetLUFS":LUFS_TARGET,"toleranceLU":LUFS_TOLERANCE,"firstAndSecondPassLoudnorm":True,"truePeakLimiter":master_info["truePeakLimiter"]},
            "absoluteSilence":{"startSample":SILENCE_START_SAMPLE,"endSampleExclusive":SILENCE_END_SAMPLE},
            "generativeAssets":"All score and SFX were synthesized deterministically from code; no external audio asset is claimed.",
        }
        mix_manifest={
            "version":1,"settings":settings,"inputSetSha256":canonical_hash({"segments":qa["source"],"settings":settings}),
            "providerManifest":"project/public/audio/provider-manifest.json","providerManifestSha256":qa["source"]["providerManifestSha256"],
            "outputs":{name:published_info[name] for name in output_map},"eventRecords":event_records,
            "premix":premix_info,"scratchPublication":published,
        }
        for path,value in ((timing_path_tmp,timing),(srt_tmp,None),(qa_tmp,qa),(settings_tmp,settings),(manifest_tmp,mix_manifest)):
            if value is not None: path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        srt_tmp.write_text(srt,encoding="utf-8")
        preserve_preview_timing()
        for temp,target in ((timing_path_tmp,TIMING_PATH),(srt_tmp,SRT_PATH),(qa_tmp,QA_PATH),(settings_tmp,MIX_SETTINGS_PATH),(manifest_tmp,MIX_MANIFEST_PATH)):
            temp.replace(target)
        print(json.dumps({"status":"MEASURED_PCM_QA","master":published_info["master.wav"],"loudness":final_stats,"captions":len(timing["captions"]),"absoluteSilence":qa["absoluteSilence"]},ensure_ascii=False))
    return 0


def main() -> int:
    try:
        return run_build()
    except (AudioBuildError,OSError,ValueError,TypeError,wave.Error,subprocess.SubprocessError) as exc:
        print(f"build_audio.py: {exc}",file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
