#!/usr/bin/env python3
"""Build EP16's measured narration, procedural soundscape, captions, and PCM master."""

from __future__ import annotations

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
SEGMENTS_PATH = PROJECT / "segments.json"
TIMELINE_PATH = PROJECT / "timeline.json"
AUTHORIZATION_PATH = PROJECT / "audio-authorization.json"
PROVIDER_MANIFEST_PATH = AUDIO / "provider-manifest.json"
PREFLIGHT_PATH = WORK / "review" / "provider-preflight.json"
ENVIRONMENT_PREFLIGHT_PATH = WORK / "review" / "preflight.json"
TIMING_PATH = PROJECT / "audio-timing.json"
MIX_SETTINGS_PATH = PROJECT / "mix-settings.json"
QA_PATH = WORK / "review" / "audio-qa.json"
SRT_PATH = WORK / "小红书" / "captions.srt"
AGENTDEV_ROOT = Path("/Volumes/AgentDev")

FPS = 60
SAMPLE_RATE = 48_000
SAMPLES_PER_FRAME = SAMPLE_RATE // FPS
DURATION_SECONDS = 120
TOTAL_FRAMES = FPS * DURATION_SECONDS
TOTAL_SAMPLES = SAMPLE_RATE * DURATION_SECONDS
EXPECTED_IDS = [f"S{i:02d}" for i in range(1, 10)]
SETTINGS = {
    "provider": "Aliyun Bailian",
    "model_selection": "active profile default",
    "effective_model": "cosyvoice-v3-flash",
    "voice": "longtian_v3",
    "rate": 1.0,
    "format": "wav",
    "sample_rate": 24_000,
}
NARRATION_GAIN = 0.78
LUFS_TARGET = -16.0
LUFS_TOLERANCE = 0.1
LOUDNORM_TRUE_PEAK_TARGET = -1.5
TRUE_PEAK_ACCEPTANCE = -1.0
SCORE_END_SECONDS = 93.0
DROP_FRAME = 6401
DROP_START_SAMPLE = DROP_FRAME * SAMPLES_PER_FRAME
AIR_TAIL_END_SAMPLE = round(119.8 * SAMPLE_RATE)


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


def write_json_atomic(path: Path, value: Any) -> None:
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
        raise AudioBuildError("segments.json must contain S01 through S09 in source order")
    for item in segments:
        if not isinstance(item.get("display_subtitle"), str) or not item["display_subtitle"].strip():
            raise AudioBuildError(f"{item['id']} has no display_subtitle")
        if not isinstance(item.get("tts_phonetic_text"), str) or not item["tts_phonetic_text"].strip():
            raise AudioBuildError(f"{item['id']} has no prepared TTS text")
        start, end = item.get("startFrame"), item.get("endFrame")
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= TOTAL_FRAMES:
            raise AudioBuildError(f"{item['id']} has invalid frame bounds")
    return segments


def validate_timeline() -> dict[str, Any]:
    timeline = read_json(TIMELINE_PATH, "timeline.json")
    expected = (DURATION_SECONDS, FPS, TOTAL_FRAMES, SAMPLE_RATE, TOTAL_SAMPLES)
    actual = tuple(timeline.get(key) for key in ("duration_seconds", "fps", "total_frames", "sample_rate", "samples_per_channel"))
    if actual != expected:
        raise AudioBuildError(f"timeline.json timebase differs from the audio specification: {actual}")
    return timeline


def verify_provider_inputs(segments: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    authorization = read_json(AUTHORIZATION_PATH, "audio-authorization.json")
    if authorization.get("authorized") is not True or authorization.get("provider") != "Aliyun Bailian" or authorization.get("voice") != SETTINGS["voice"]:
        raise AudioBuildError("audio authorization does not match the assigned provider/voice")
    ordered_hash = sha_bytes(json.dumps([item["tts_phonetic_text"] for item in segments], ensure_ascii=False).encode("utf-8"))
    if authorization.get("text_sha256") != ordered_hash:
        raise AudioBuildError("audio authorization text hash differs from exact ordered prepared text")

    manifest = read_json(PROVIDER_MANIFEST_PATH, "provider-manifest.json")
    preflight = read_json(PREFLIGHT_PATH, "provider-preflight.json")
    environment = read_json(ENVIRONMENT_PREFLIGHT_PATH, "review/preflight.json")
    if manifest.get("settings") != SETTINGS or set(manifest.get("segments", {})) != set(EXPECTED_IDS):
        raise AudioBuildError("provider manifest settings or cue set differ from the assigned audio task")
    if preflight.get("settings") != SETTINGS or preflight.get("orderedTextSha256") != ordered_hash:
        raise AudioBuildError("provider preflight settings or ordered prepared text hash do not match")
    if preflight.get("authorization", {}).get("sha256") != sha_file(AUTHORIZATION_PATH):
        raise AudioBuildError("provider preflight authorization hash differs from the current authorization")
    if preflight.get("authStatus", {}).get("authenticated") is not True:
        raise AudioBuildError("provider preflight does not confirm authenticated CLI state")
    if (environment.get("blCLI"), environment.get("blSkill"), environment.get("npmLatest")) != ("2.5.0", "2.5.0", "2.5.0"):
        raise AudioBuildError("environment preflight does not prove aligned 2.5.0 CLI/skill/npm versions")
    if environment.get("authenticated") is not True or environment.get("credentialsRecorded") is not False:
        raise AudioBuildError("environment preflight authentication/secrets evidence is not acceptable")
    calls = preflight.get("calls")
    if not isinstance(calls, list) or len(calls) != len(EXPECTED_IDS) or {call.get("segmentId") for call in calls} != set(EXPECTED_IDS):
        raise AudioBuildError("provider preflight must contain exactly one successful identity record for each cue")
    for call in calls:
        if call.get("status") != "succeeded" or call.get("reportedModels") != [SETTINGS["effective_model"]] or call.get("reportedVoices") != [SETTINGS["voice"]]:
            raise AudioBuildError(f"provider preflight identity/status mismatch for {call.get('segmentId')}")

    for segment in segments:
        entry = manifest["segments"][segment["id"]]
        if entry.get("settings") != SETTINGS or entry.get("ttsPhoneticText") != segment["tts_phonetic_text"]:
            raise AudioBuildError(f"{segment['id']} provider manifest source/settings differ")
        if entry.get("effectiveModel") != SETTINGS["effective_model"] or entry.get("effectiveVoice") != SETTINGS["voice"]:
            raise AudioBuildError(f"{segment['id']} effective model/voice differs from the authorized request")
        for file_key, hash_key in (("rawPath", "rawSha256"), ("canonicalPath", "canonicalSha256"), ("cuePath", "cueSha256")):
            relative = entry.get(file_key)
            if not isinstance(relative, str):
                raise AudioBuildError(f"{segment['id']} is missing manifest path {file_key}")
            path = (PROJECT / relative).resolve()
            if not path.is_relative_to(PROJECT.resolve()) or not path.is_file():
                raise AudioBuildError(f"{segment['id']} has missing/out-of-project {file_key}")
            if sha_file(path) != entry.get(hash_key):
                raise AudioBuildError(f"{segment['id']} {file_key} hash differs from provider manifest")
    return manifest, preflight


def measure_active_bounds(pcm: np.ndarray) -> tuple[int, int, dict[str, Any]]:
    if pcm.ndim != 1 or not len(pcm):
        raise AudioBuildError("cue PCM must be a non-empty mono vector")
    sample_i32 = pcm.astype(np.int32)
    peak = int(np.max(np.abs(sample_i32)))
    if peak == 0:
        raise AudioBuildError("cue is digital silence")
    threshold = max(48, round(peak * 0.004))
    window = min(240, len(sample_i32))
    required_power = window * threshold * threshold
    squares = sample_i32.astype(np.int64) ** 2
    cumulative = np.empty(len(squares) + 1, dtype=np.int64)
    cumulative[0] = 0
    np.cumsum(squares, out=cumulative[1:])
    powers = cumulative[window:] - cumulative[:-window]
    active = np.flatnonzero(powers >= required_power)
    if not len(active):
        raise AudioBuildError("cue has no measurable PCM activity above onset threshold")
    first = int(active[0])
    last = int(active[-1]) + window
    return first, last, {
        "method": "5 ms sliding RMS; threshold=max(48 PCM16, 0.4% of cue peak)",
        "thresholdPcm16": threshold,
        "windowSamples": window,
    }


def load_cues(segments: list[dict[str, Any]], manifest: dict[str, Any]) -> tuple[dict[str, np.ndarray], list[dict[str, Any]]]:
    cues: dict[str, np.ndarray] = {}
    measured: list[dict[str, Any]] = []
    placements: list[tuple[str, int, int]] = []
    for index, segment in enumerate(segments):
        sid = segment["id"]
        entry = manifest["segments"][sid]
        path = PROJECT / entry["cuePath"]
        try:
            with wave.open(str(path), "rb") as wav:
                params = wav.getparams()
                payload = wav.readframes(params.nframes)
        except (OSError, wave.Error) as exc:
            raise AudioBuildError(f"cannot decode {sid} cue: {exc}") from None
        if (params.framerate, params.nchannels, params.sampwidth, params.comptype) != (SAMPLE_RATE, 1, 2, "NONE"):
            raise AudioBuildError(f"{sid} cue must be mono 48 kHz PCM16")
        if params.nframes != entry.get("actualSamples48k") or len(payload) != params.nframes * 2:
            raise AudioBuildError(f"{sid} cue sample count differs from its measured manifest")
        if sha_bytes(payload) != entry.get("cuePcmSha256"):
            raise AudioBuildError(f"{sid} cue PCM hash differs from its measured manifest")
        pcm = np.frombuffer(payload, dtype="<i2")
        onset, active_end, bounds = measure_active_bounds(pcm)
        if onset != entry.get("activeOnsetOffsetSamples48k") or active_end != entry.get("activeEndOffsetSamples48kExclusive"):
            raise AudioBuildError(f"{sid} recomputed active PCM bounds differ from its manifest")
        cues[sid] = pcm.astype(np.float32) / 32768.0

        start = segment["startFrame"] * SAMPLES_PER_FRAME
        cue_end = start + params.nframes
        declared_end = segment["endFrame"] * SAMPLES_PER_FRAME
        next_start = (segments[index + 1]["startFrame"] * SAMPLES_PER_FRAME) if index + 1 < len(segments) else TOTAL_SAMPLES
        active_start = start + onset
        active_end_absolute = start + active_end
        if cue_end > TOTAL_SAMPLES or active_end_absolute > declared_end:
            raise AudioBuildError(
                f"NEEDS_SOL: {sid} cue={params.nframes / SAMPLE_RATE:.3f}s; active ends at sample {active_end_absolute}, "
                f"declared end sample {declared_end}; speech remains untrimmed"
            )
        if cue_end > next_start:
            raise AudioBuildError(
                f"NEEDS_SOL: {sid} complete cue ends at sample {cue_end}, next cue starts at {next_start}; speech remains untrimmed"
            )
        placements.append((sid, active_start, active_end_absolute))
        measured.append({
            "id": sid,
            "startFrame": segment["startFrame"],
            "declaredEndFrameExclusive": segment["endFrame"],
            "cueStartSample": start,
            "cueEndSampleExclusive": cue_end,
            "completeCueSamples48k": params.nframes,
            "completeCueDurationSeconds": params.nframes / SAMPLE_RATE,
            "activeOnsetOffsetSamples48k": onset,
            "activeEndOffsetSamples48kExclusive": active_end,
            "activeStartSample": active_start,
            "activeEndSampleExclusive": active_end_absolute,
            "activeStartFrame": active_start / SAMPLES_PER_FRAME,
            "activeEndFrameExclusive": active_end_absolute / SAMPLES_PER_FRAME,
            "activeDurationSeconds": (active_end - onset) / SAMPLE_RATE,
            "activeBoundsMethod": bounds,
            "completeCueFitsDeclaredWindow": entry.get("completeCueFitsDeclaredWindow"),
            "activeSpeechEndsByDeclaredEndFrame": True,
            "cueAvoidsNextActiveRange": True,
            "effectiveModel": entry["effectiveModel"],
            "effectiveVoice": entry["effectiveVoice"],
            "rate": entry["settings"]["rate"],
            "cueSha256": entry["cueSha256"],
        })
    placements.sort(key=lambda item: item[1])
    for (prior_id, _, prior_end), (current_id, current_start, _) in zip(placements, placements[1:]):
        if prior_end > current_start:
            raise AudioBuildError(f"NEEDS_SOL: measured active speech overlaps between {prior_id} and {current_id}")
    return cues, measured


def smooth01(value: np.ndarray) -> np.ndarray:
    clipped = np.clip(value, 0.0, 1.0)
    return clipped * clipped * (3.0 - 2.0 * clipped)


def speech_duck(measured: list[dict[str, Any]], attenuation_db: float = -3.0) -> np.ndarray:
    envelope = np.zeros(TOTAL_SAMPLES, dtype=np.float32)
    pre = round(0.08 * SAMPLE_RATE)
    post = round(0.24 * SAMPLE_RATE)
    for segment in measured:
        start, end = segment["activeStartSample"], segment["activeEndSampleExclusive"]
        ramp_start = max(0, start - pre)
        if start > ramp_start:
            envelope[ramp_start:start] = smooth01(np.arange(start-ramp_start, dtype=np.float32) / max(1, start-ramp_start))
        envelope[start:end] = 1.0
        ramp_end = min(TOTAL_SAMPLES, end + post)
        if ramp_end > end:
            envelope[end:ramp_end] = 1.0 - smooth01(np.arange(ramp_end-end, dtype=np.float32) / max(1, ramp_end-end))
    ducked = 10.0 ** (attenuation_db / 20.0)
    return 1.0 - (1.0 - ducked) * envelope


def render_narration(cues: dict[str, np.ndarray], measured: list[dict[str, Any]]) -> np.ndarray:
    output = np.zeros((TOTAL_SAMPLES, 2), dtype=np.float32)
    by_id = {item["id"]: item for item in measured}
    for sid, cue in cues.items():
        start = by_id[sid]["cueStartSample"]
        end = start + len(cue)
        output[start:end, 0] += cue * NARRATION_GAIN
        output[start:end, 1] += cue * NARRATION_GAIN
    return output


def render_score(measured: list[dict[str, Any]]) -> tuple[np.ndarray, dict[str, Any]]:
    score = np.zeros((TOTAL_SAMPLES, 2), dtype=np.float32)
    count = round(SCORE_END_SECONDS * SAMPLE_RATE)
    time = np.arange(count, dtype=np.float64) / SAMPLE_RATE
    slow = 0.78 + 0.22 * np.sin(2.0 * np.pi * 0.071 * time + 0.2)
    drift = np.sin(2.0 * np.pi * 0.022 * time)
    drone = (0.0070 * np.sin(2.0 * np.pi * (47.0 + 0.22 * drift) * time)
             + 0.0024 * np.sin(2.0 * np.pi * 94.0 * time + 0.4)
             + 0.0010 * np.sin(2.0 * np.pi * 311.0 * time + 0.7)) * slow
    fade_in = smooth01(np.minimum(1.0, time / 1.4))
    fade_out = 1.0 - smooth01(np.clip((time - (SCORE_END_SECONDS - 2.0)) / 2.0, 0.0, 1.0))
    bed = drone * fade_in * fade_out
    score[:count, 0] = bed
    score[:count, 1] = bed * (0.94 + 0.025 * np.sin(2.0 * np.pi * 0.053 * time + 0.6))

    click_offsets = []
    click_count = round(0.055 * SAMPLE_RATE)
    local_t = np.arange(click_count, dtype=np.float64) / SAMPLE_RATE
    click_env = np.exp(-local_t * 78.0) * smooth01(np.minimum(1.0, local_t / 0.002))
    base_click = 0.0060 * click_env * (np.sin(2.0 * np.pi * 1780.0 * local_t) + 0.24 * np.sin(2.0 * np.pi * 760.0 * local_t + 0.3))
    for at in np.arange(0.8, SCORE_END_SECONDS - 0.4, 1.6):
        offset = round(float(at) * SAMPLE_RATE)
        end = min(count, offset + click_count)
        if end > offset:
            phase = len(click_offsets) % 2
            score[offset:end, 0] += base_click[:end-offset] * (1.0 if phase == 0 else 0.88)
            score[offset:end, 1] += base_click[:end-offset] * (0.88 if phase == 0 else 1.0)
            click_offsets.append(offset)

    duck = speech_duck(measured, -3.0)
    score *= duck[:, None]
    return score, {
        "kind": "procedural_clinical_drone_and_rigid_soft_clicks",
        "startSample": 0,
        "endSampleExclusive": count,
        "endSeconds": SCORE_END_SECONDS,
        "droneComponentsHz": [47.0, 94.0, 311.0],
        "clickCount": len(click_offsets),
        "clickPeriodSeconds": 1.6,
        "clickStartSamples": click_offsets,
        "speechDuckDB": -3.0,
        "suspension": {"scoreAndSfxAbsentFromSeconds": 93.0, "toDropFrame": DROP_FRAME, "choiceWindowSeconds": [103.0, 105.0]},
    }


def deterministic_noise(count: int, seed_text: str) -> np.ndarray:
    seed = int.from_bytes(hashlib.sha256(seed_text.encode("utf-8")).digest()[:8], "little")
    return np.random.default_rng(seed).standard_normal(count, dtype=np.float32)


def render_water_drop() -> tuple[np.ndarray, dict[str, Any]]:
    count = AIR_TAIL_END_SAMPLE - DROP_START_SAMPLE
    if count <= 0:
        raise AudioBuildError("water drop tail has invalid bounds")
    t = np.arange(count, dtype=np.float64) / SAMPLE_RATE
    duration = count / SAMPLE_RATE
    rng_noise = deterministic_noise(count, "si-ep16-water-drop-air-tail-v1").astype(np.float64)
    frequency = np.fft.rfftfreq(count, 1.0 / SAMPLE_RATE)
    lowpass = 1.0 / np.sqrt(1.0 + (frequency / 1150.0) ** 4)
    airy = np.fft.irfft(np.fft.rfft(rng_noise) * lowpass, n=count)
    rms = float(np.sqrt(np.mean(airy * airy)))
    if rms <= 1e-12:
        raise AudioBuildError("deterministic air tail unexpectedly has zero energy")
    airy /= rms

    attack = smooth01(np.minimum(1.0, t / 0.002))
    drop = (0.095 * np.sin(2.0 * np.pi * 380.0 * t + 0.08)
            + 0.060 * np.sin(2.0 * np.pi * 620.0 * t + 0.32)
            + 0.027 * np.sin(2.0 * np.pi * 1180.0 * t + 0.7))
    drop *= np.exp(-t * 4.1) * attack
    drop += 0.075 * np.sin(2.0 * np.pi * 1720.0 * t) * np.exp(-t * 52.0) * attack

    air_start = 0.17
    air_t = np.maximum(0.0, t - air_start)
    air_envelope = np.where(t >= air_start, 0.0045 * np.exp(-air_t / 6.0), 0.0)
    terminal_fade_start = duration - 0.45
    terminal_fade = 1.0 - smooth01(np.clip((t - terminal_fade_start) / 0.45, 0.0, 1.0))
    air = airy * air_envelope * terminal_fade
    shimmer = np.where(t >= air_start,
        0.0012 * np.sin(2.0 * np.pi * (1420.0 * t + 13.0 * t * t / max(duration, 1e-9))) * np.exp(-air_t / 4.7),
        0.0)
    mono = (drop + air + shimmer) * terminal_fade
    stereo = np.column_stack((mono, mono * (0.965 + 0.02 * np.sin(2.0 * np.pi * 0.19 * t)))).astype(np.float32)
    output = np.zeros((TOTAL_SAMPLES, 2), dtype=np.float32)
    output[DROP_START_SAMPLE:AIR_TAIL_END_SAMPLE] = stereo
    return output, {
        "eventId": "single-original-water-drop",
        "kind": "procedural_water_drop_with_airy_tail",
        "startFrame": DROP_FRAME,
        "startSample": DROP_START_SAMPLE,
        "startSeconds": DROP_START_SAMPLE / SAMPLE_RATE,
        "impactCount": 1,
        "tailEndSampleExclusive": AIR_TAIL_END_SAMPLE,
        "tailEndSeconds": AIR_TAIL_END_SAMPLE / SAMPLE_RATE,
        "terminalFadeSeconds": 0.45,
        "deterministicSeed": "si-ep16-water-drop-air-tail-v1",
    }


def write_pcm16(path: Path, stereo: np.ndarray) -> dict[str, Any]:
    if stereo.shape != (TOTAL_SAMPLES, 2):
        raise AudioBuildError(f"{path.name} has array shape {stereo.shape}, expected {(TOTAL_SAMPLES, 2)}")
    peak = float(np.max(np.abs(stereo)))
    if not math.isfinite(peak) or peak > 0.98:
        raise AudioBuildError(f"{path.name} pre-write peak {peak} exceeds safe PCM headroom")
    pcm = np.clip(np.rint(stereo * 32767.0), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm.tobytes())
    return validate_wav(path)


def validate_wav(path: Path) -> dict[str, Any]:
    try:
        with wave.open(str(path), "rb") as wav:
            params = wav.getparams()
            payload = wav.readframes(params.nframes)
    except (OSError, wave.Error) as exc:
        raise AudioBuildError(f"cannot decode {path}: {exc}") from None
    if (params.framerate, params.nchannels, params.sampwidth, params.comptype) != (SAMPLE_RATE, 2, 2, "NONE"):
        raise AudioBuildError(f"{path.name} must be 48 kHz stereo PCM16")
    if params.nframes != TOTAL_SAMPLES or len(payload) != TOTAL_SAMPLES * 4:
        raise AudioBuildError(f"{path.name} must contain exactly {TOTAL_SAMPLES} samples per channel")
    samples = np.frombuffer(payload, dtype="<i2").reshape(-1, 2)
    return {
        "file": str(path),
        "sha256": sha_file(path),
        "pcmSha256": sha_bytes(payload),
        "sizeBytes": path.stat().st_size,
        "sampleRate": SAMPLE_RATE,
        "channels": 2,
        "sampleWidthBytes": 2,
        "samplesPerChannel": TOTAL_SAMPLES,
        "durationSeconds": DURATION_SECONDS,
        "samplePeakPcm16": int(np.max(np.abs(samples.astype(np.int32)))),
        "terminalSamplePeakPcm16": int(np.max(np.abs(samples[-1].astype(np.int32)))),
        "final150msPeakPcm16": int(np.max(np.abs(samples[-round(0.15 * SAMPLE_RATE):].astype(np.int32)))),
    }


def run_ffmpeg(args: list[str], label: str) -> str:
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if proc.returncode:
        detail = " | ".join((proc.stderr or proc.stdout or "").strip().splitlines()[-8:])
        raise AudioBuildError(f"{label} failed with exit {proc.returncode}: {detail}")
    return proc.stderr or ""


def parse_loudnorm(text: str) -> dict[str, Any]:
    matches = list(re.finditer(r"\{\s*\"input_i\"[\s\S]*?\}", text))
    if not matches:
        raise AudioBuildError("FFmpeg loudnorm measurement JSON was not found")
    data = json.loads(matches[-1].group(0))
    required = ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")
    if any(key not in data for key in required):
        raise AudioBuildError("FFmpeg loudnorm measurement is incomplete")
    return data


def measure_ebur128(path: Path) -> dict[str, float]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise AudioBuildError("ffmpeg is required for LUFS and true-peak verification")
    text = run_ffmpeg([ffmpeg, "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"], "EBU R128 measurement")
    integrated = re.search(r"^\s*I:\s*(-?\d+(?:\.\d+)?)\s+LUFS\s*$", text, re.MULTILINE)
    peaks = list(re.finditer(r"^\s*True peak:\s*(-?\d+(?:\.\d+)?)\s+dBTP\s*$", text, re.MULTILINE))
    if not peaks:
        peaks = list(re.finditer(r"True peak:\s*\n\s*Peak:\s*(-?\d+(?:\.\d+)?)\s+dBFS", text))
    if integrated is None or not peaks:
        raise AudioBuildError("FFmpeg ebur128 did not report integrated LUFS and true peak")
    return {"integratedLUFS": float(integrated.group(1)), "truePeakDBTP": float(peaks[-1].group(1))}


def strict_decode(path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise AudioBuildError("ffmpeg is required for strict decode validation")
    run_ffmpeg([ffmpeg, "-hide_banner", "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"], "strict PCM master decode")


def normalize_master(premix: Path, output: Path) -> dict[str, Any]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise AudioBuildError("ffmpeg is required for master normalization")
    first_text = run_ffmpeg([
        ffmpeg, "-hide_banner", "-nostats", "-i", str(premix), "-af",
        f"loudnorm=I={LUFS_TARGET}:TP={LOUDNORM_TRUE_PEAK_TARGET}:LRA=11:print_format=json", "-f", "null", "-",
    ], "first-pass loudnorm analysis")
    first = parse_loudnorm(first_text)
    second_filter = (
        f"loudnorm=I={LUFS_TARGET}:TP={LOUDNORM_TRUE_PEAK_TARGET}:LRA=11"
        f":measured_I={first['input_i']}:measured_TP={first['input_tp']}:measured_LRA={first['input_lra']}"
        f":measured_thresh={first['input_thresh']}:offset={first['target_offset']}:linear=true:print_format=json"
    )
    normalized = output.with_name(output.stem + ".normalized.tmp.wav")
    limited = output.with_name(output.stem + ".limited.tmp.wav")
    if output.exists() or normalized.exists() or limited.exists():
        raise AudioBuildError("master output or normalization temporary already exists; preserved")
    second_text = run_ffmpeg([
        ffmpeg, "-hide_banner", "-nostats", "-i", str(premix), "-af", second_filter,
        "-ar", str(SAMPLE_RATE), "-ac", "2", "-c:a", "pcm_s16le", str(normalized),
    ], "second-pass loudnorm render")
    second = parse_loudnorm(second_text)
    ceiling = 10.0 ** (LOUDNORM_TRUE_PEAK_TARGET / 20.0)
    limiter = (
        "aresample=192000:resampler=swr,"
        f"alimiter=limit={ceiling:.12f}:attack=5:release=50:latency=1:level=disabled,"
        f"aresample={SAMPLE_RATE}:resampler=swr:dither_method=none,atrim=end_sample={TOTAL_SAMPLES},asetpts=PTS-STARTPTS"
    )
    run_ffmpeg([
        ffmpeg, "-hide_banner", "-nostats", "-i", str(normalized), "-af", limiter,
        "-ar", str(SAMPLE_RATE), "-ac", "2", "-c:a", "pcm_s16le", str(limited),
    ], "oversampled true-peak guard")
    normalized.unlink()
    limited.replace(output)
    stats = measure_ebur128(output)
    calibration: dict[str, Any] = {"appliedGainDB": 0.0, "method": "two-pass loudnorm plus oversampled limiter", "before": stats}
    gain_db = LUFS_TARGET - stats["integratedLUFS"]
    if abs(gain_db) > LUFS_TOLERANCE:
        gain = 10.0 ** (gain_db / 20.0)
        with wave.open(str(output), "rb") as wav:
            params = wav.getparams()
            payload = wav.readframes(params.nframes)
        values = np.frombuffer(payload, dtype="<i2").reshape(-1, 2).astype(np.float64)
        scaled = np.rint(values * gain)
        if float(np.max(np.abs(scaled))) > 32767.0:
            raise AudioBuildError("post-loudnorm calibration would clip PCM")
        calibration_path = output.with_name(output.stem + ".calibrated.tmp.wav")
        if calibration_path.exists():
            raise AudioBuildError("calibration temporary already exists; preserved")
        with wave.open(str(calibration_path), "wb") as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(scaled.astype("<i2").tobytes())
        after_calibration = measure_ebur128(calibration_path)
        if after_calibration["truePeakDBTP"] > TRUE_PEAK_ACCEPTANCE:
            calibration_path.unlink(missing_ok=True)
            raise AudioBuildError(f"-16 LUFS calibration would exceed true-peak acceptance: {after_calibration}")
        calibration_path.replace(output)
        calibration |= {"appliedGainDB": gain_db, "after": after_calibration, "method": "linear PCM correction after two-pass loudnorm and limiter"}
    strict_decode(output)
    final = measure_ebur128(output)
    info = validate_wav(output)
    if not LUFS_TARGET - LUFS_TOLERANCE <= final["integratedLUFS"] <= LUFS_TARGET + LUFS_TOLERANCE:
        raise AudioBuildError(f"final master loudness {final['integratedLUFS']} LUFS is outside -16.0 ±0.1")
    if final["truePeakDBTP"] > TRUE_PEAK_ACCEPTANCE:
        raise AudioBuildError(f"final master true peak {final['truePeakDBTP']} dBTP exceeds -1.0 dBTP")
    return info | {
        "strictDecode": "passed",
        "loudnormFirstPass": first,
        "loudnormSecondPass": second,
        "truePeakLimiter": {"oversampleFactor": 4, "processingSampleRate": 192_000, "ceilingDBTP": LOUDNORM_TRUE_PEAK_TARGET, "limitAmplitude": ceiling, "explicitlyApplied": True},
        "ebur128Final": final,
        "normalizationTarget": {"integratedLUFS": LUFS_TARGET, "toleranceLU": LUFS_TOLERANCE, "truePeakDBTPMaximum": TRUE_PEAK_ACCEPTANCE},
        "postLimiterCalibration": calibration,
    }


def caption_phrases(source: str) -> list[str]:
    text = re.sub(r"\s+", "", source)
    punctuation = set("，。！？；：、…,.!?;:")
    closing = set("”’」』）》】〕〉")
    phrases: list[str] = []
    current: list[str] = []
    index = 0
    while index < len(text):
        current.append(text[index])
        if text[index] in punctuation:
            while index + 1 < len(text) and text[index + 1] in punctuation:
                index += 1
                current.append(text[index])
            while index + 1 < len(text) and text[index + 1] in closing:
                index += 1
                current.append(text[index])
            phrases.append("".join(current))
            current = []
        index += 1
    if current:
        phrases.append("".join(current))

    expanded: list[str] = []
    for phrase in phrases:
        while len(phrase) > 26:
            cut = caption_breakpoint(phrase, 26)
            expanded.append(phrase[:cut])
            phrase = phrase[cut:]
        if phrase:
            expanded.append(phrase)
    if "".join(expanded) != text:
        raise AudioBuildError("caption phrase splitting changed source display text")
    return expanded


def caption_breakpoint(text: str, maximum: int) -> int:
    limit = min(maximum, len(text) - 1)
    after = set("，。！？；：、…,.!?;:")
    before = set("的了着过和与在把被就才还再只而但却又也更最是能可从向替")
    options: list[tuple[int, int]] = []
    for cut in range(max(1, limit - 11), limit + 1):
        score = abs(maximum - cut)
        if text[cut - 1] in after:
            score -= 8
        if text[cut] in before:
            score -= 6
        if text[cut - 1] in "”’」』）》】" or text[cut] in "“‘「『（《【":
            score += 4
        options.append((score, cut))
    return min(options)[1] if options else limit


def wrap_caption(phrase: str) -> str:
    if len(phrase) <= 13:
        return phrase
    if len(phrase) > 26:
        raise AudioBuildError("caption phrase exceeds the two-line 26-character maximum")
    cut = caption_breakpoint(phrase, 13)
    closing = set("”’」』）》】〕〉")
    while cut > 1 and phrase[cut] in closing:
        cut -= 1
    left, right = phrase[:cut], phrase[cut:]
    if not left or not right or len(left) > 13 or len(right) > 13:
        raise AudioBuildError(f"cannot wrap caption within two 13-character lines: {phrase!r}")
    return left + "\n" + right


def build_captions(segments: list[dict[str, Any]], measured: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {item["id"]: item for item in measured}
    captions: list[dict[str, Any]] = []
    for segment in segments:
        source = re.sub(r"\s+", "", segment["display_subtitle"])
        phrases = caption_phrases(segment["display_subtitle"])
        weights = [len(item) for item in phrases]
        total = sum(weights)
        start = math.ceil(by_id[segment["id"]]["activeStartSample"] / SAMPLES_PER_FRAME)
        end = math.ceil(by_id[segment["id"]]["activeEndSampleExclusive"] / SAMPLES_PER_FRAME)
        count = end - start
        if count < len(phrases):
            raise AudioBuildError(f"{segment['id']} has too few active frames for its caption phrases")
        cumulative = 0
        prior = start
        for index, (phrase, weight) in enumerate(zip(phrases, weights)):
            cumulative += weight
            if index == len(phrases) - 1:
                next_frame = end
            else:
                next_frame = start + round(count * cumulative / total)
                next_frame = min(end - (len(phrases) - index - 1), max(prior + 1, next_frame))
            wrapped = wrap_caption(phrase)
            lines = wrapped.split("\n")
            if len(lines) > 2 or any(len(line) > 13 for line in lines):
                raise AudioBuildError(f"caption exceeds two lines/13 chars: {wrapped!r}")
            captions.append({
                "segmentId": segment["id"],
                "startFrame": prior,
                "endFrame": next_frame,
                "text": wrapped,
                "alignment": "approximate_character_weighted_within_measured_active_PCM",
            })
            prior = next_frame
        if "".join(item["text"].replace("\n", "") for item in captions if item["segmentId"] == segment["id"]) != source:
            raise AudioBuildError(f"{segment['id']} caption source text is not preserved exactly")
    return captions


def frame_srt_time(frame: int) -> str:
    milliseconds = round(frame * 1000 / FPS)
    hours, rem = divmod(milliseconds, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def render_srt(captions: list[dict[str, Any]]) -> str:
    output: list[str] = []
    for index, caption in enumerate(captions, 1):
        output.extend((str(index), f"{frame_srt_time(caption['startFrame'])} --> {frame_srt_time(caption['endFrame'])}", caption["text"], ""))
    return "\n".join(output)


def copy_verified(source: Path, destination: Path) -> dict[str, Any]:
    digest = sha_file(source)
    if destination.exists():
        if sha_file(destination) != digest:
            raise AudioBuildError(f"existing output is divergent and was preserved: {destination}")
        return {"path": str(destination.relative_to(PROJECT)), "sha256": digest, "status": "matching output reused"}
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    if temporary.exists():
        raise AudioBuildError(f"output copy temporary already exists; preserved: {temporary}")
    shutil.copyfile(source, temporary)
    if sha_file(temporary) != digest:
        temporary.unlink(missing_ok=True)
        raise AudioBuildError(f"copied hash mismatch for {destination.name}")
    temporary.replace(destination)
    return {"path": str(destination.relative_to(PROJECT)), "sha256": digest, "status": "published from verified AgentDev scratch"}


def run_build() -> int:
    segments = load_segments()
    timeline = validate_timeline()
    manifest, preflight = verify_provider_inputs(segments)
    cues, measured = load_cues(segments, manifest)
    narration = render_narration(cues, measured)
    score, score_event = render_score(measured)
    sfx, drop_event = render_water_drop()
    outputs = [AUDIO / f"{name}.wav" for name in ("narration", "score", "sfx", "master")]
    write_targets = [*outputs, TIMING_PATH, MIX_SETTINGS_PATH, QA_PATH, SRT_PATH]
    existing = [path for path in write_targets if path.exists() and path not in (TIMING_PATH,)]
    if existing:
        raise AudioBuildError("audio outputs already exist; preserving: " + ", ".join(map(str, existing)))
    if TIMING_PATH.exists():
        existing_timing = read_json(TIMING_PATH, "existing audio-timing.json")
        if existing_timing.get("status") != "PREVIEW_ONLY":
            raise AudioBuildError("existing audio-timing.json is not PREVIEW_ONLY; preserving it")
        history_dir = AUDIO / "history"
        history_path = history_dir / "preview-timing.json"
        if history_path.exists() and history_path.read_bytes() != TIMING_PATH.read_bytes():
            raise AudioBuildError("existing archived preview timing is divergent; preserving it")

    voice_ranges = [{"id": item["id"], "startSample": item["activeStartSample"], "endSampleExclusive": item["activeEndSampleExclusive"]} for item in measured]
    captions = build_captions(segments, measured)
    timing = {
        "durationSeconds": DURATION_SECONDS,
        "fps": FPS,
        "sampleRate": SAMPLE_RATE,
        "samplesPerChannel": TOTAL_SAMPLES,
        "status": "MEASURED",
        "captionTimingMethod": "Approximate character-weighted phrase timing within measured active PCM. No ASR or forced word alignment was performed.",
        "activeBoundsMethod": "5 ms sliding RMS; threshold=max(48 PCM16, 0.4% of cue peak)",
        "segments": measured,
        "captions": [{key: item[key] for key in ("startFrame", "endFrame", "text")} | {"segmentId": item["segmentId"], "alignment": item["alignment"]} for item in captions],
    }
    srt = render_srt(captions)

    premix = narration + score + sfx
    if any(not np.all(np.isfinite(stem)) for stem in (narration, score, sfx, premix)):
        raise AudioBuildError("one or more audio stems contain non-finite samples")
    premix_peak = float(np.max(np.abs(premix)))
    if premix_peak > 0.98:
        raise AudioBuildError(f"premix peak {premix_peak} exceeds safe headroom before normalization")
    scratch_root = Path(tempfile.gettempdir())
    if not scratch_root.exists() or scratch_root.stat().st_dev == PROJECT.stat().st_dev:
        raise AudioBuildError("AgentDev wrapper did not provide external scratch; refusing internal fallback")
    with tempfile.TemporaryDirectory(prefix="si-ep16-audio-", dir=str(scratch_root)) as temporary:
        scratch = Path(temporary)
        stems = {
            "narration.wav": narration,
            "score.wav": score,
            "sfx.wav": sfx,
        }
        stem_info = {name: write_pcm16(scratch / name, data) for name, data in stems.items()}
        premix_path = scratch / "premix.wav"
        premix_info = write_pcm16(premix_path, premix)
        master_scratch = scratch / "master.wav"
        master_info = normalize_master(premix_path, master_scratch)
        audio_info = dict(stem_info)
        audio_info["master.wav"] = master_info
        published = {name: copy_verified(scratch / name, AUDIO / name) for name in stems}
        published["master.wav"] = copy_verified(master_scratch, AUDIO / "master.wav")
        published_info = {name: validate_wav(AUDIO / name) for name in audio_info}

        settings = {
            "version": 1,
            "episode": "EP16",
            "fps": FPS,
            "sampleRate": SAMPLE_RATE,
            "samplesPerChannel": TOTAL_SAMPLES,
            "durationSeconds": DURATION_SECONDS,
            "narrationGainDB": 20.0 * math.log10(NARRATION_GAIN),
            "score": score_event,
            "sfx": drop_event,
            "masterNormalization": {
                "method": "two-pass FFmpeg loudnorm, then 4x oversampled true-peak limiter",
                "targetLUFS": LUFS_TARGET,
                "loudnormTruePeakTargetDBTP": LOUDNORM_TRUE_PEAK_TARGET,
                "maximumTruePeakDBTP": TRUE_PEAK_ACCEPTANCE,
                "final": master_info["ebur128Final"],
            },
            "generativeAssets": "All score and SFX were synthesized deterministically from code; no external audio asset is claimed.",
        }
        mix_settings_hash = sha_bytes(json.dumps(settings, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        timing["mixSettingsSha256"] = mix_settings_hash
        qa = {
            "version": 1,
            "episode": "EP16",
            "status": "MEASURED_PCM_QA",
            "source": {
                "segmentsSha256": sha_file(SEGMENTS_PATH),
                "timelineSha256": sha_file(TIMELINE_PATH),
                "authorizationSha256": sha_file(AUTHORIZATION_PATH),
                "providerManifestSha256": sha_file(PROVIDER_MANIFEST_PATH),
                "providerPreflightSha256": sha_file(PREFLIGHT_PATH),
                "environmentPreflightSha256": sha_file(ENVIRONMENT_PREFLIGHT_PATH),
                "mixSettingsSha256": mix_settings_hash,
            },
            "provider": {
                "provider": SETTINGS["provider"],
                "modelSelection": SETTINGS["model_selection"],
                "effectiveModel": SETTINGS["effective_model"],
                "voice": SETTINGS["voice"],
                "rate": SETTINGS["rate"],
                "sampleRateHz": SETTINGS["sample_rate"],
                "callsRecorded": len(preflight["calls"]),
                "allIdentitiesMatched": True,
            },
            "speech": {
                "allNineCuesCompleteAndUntrimmed": True,
                "placement": "Each complete cue begins at its declared startFrame.",
                "allSpeechFitsDeclaredAndNextActiveRanges": True,
                "sampleRateHz": SAMPLE_RATE,
                "rate": SETTINGS["rate"],
                "activeRanges": voice_ranges,
            },
            "stems": {name: published_info[name] for name in ("narration.wav", "score.wav", "sfx.wav")},
            "master": published_info["master.wav"] | {"loudness": master_info["ebur128Final"], "limiter": master_info["truePeakLimiter"]},
            "soundDesign": {"score": score_event, "sfx": drop_event, "speechDuckDB": -3.0, "proceduralDeterministic": True},
            "captions": {
                "srt": "小红书/captions.srt",
                "timing": "project/audio-timing.json",
                "timingQuality": "approximate_character_weighted",
                "asrUsed": False,
                "allSourceDisplayTextPreserved": True,
                "maxLines": 2,
                "maxCharactersPerLine": 13,
            },
            "humanListening": {"status": "NOT_RUN", "claim": "No human listening review was performed by this build."},
            "scratch": {"volume": "AgentDev APFS", "temporaryFilesRemovedAfterSuccessfulPublication": True},
            "outputs": {name: published_info[name] for name in published_info},
            "premix": premix_info,
            "scratchPublication": published,
        }
        QA_PATH.parent.mkdir(parents=True, exist_ok=True)
        SRT_PATH.parent.mkdir(parents=True, exist_ok=True)
        if TIMING_PATH.exists():
            history_dir = AUDIO / "history"
            history_dir.mkdir(parents=True, exist_ok=True)
            history_path = history_dir / "preview-timing.json"
            if not history_path.exists():
                history_path.write_bytes(TIMING_PATH.read_bytes())
        write_json_atomic(TIMING_PATH, timing)
        write_json_atomic(MIX_SETTINGS_PATH, settings)
        write_json_atomic(QA_PATH, qa)
        srt_tmp = SRT_PATH.with_name(SRT_PATH.name + ".tmp")
        if srt_tmp.exists():
            raise AudioBuildError("SRT temporary already exists; preserved")
        srt_tmp.write_text(srt, encoding="utf-8")
        srt_tmp.replace(SRT_PATH)

    print(json.dumps({
        "status": "MEASURED_PCM_QA",
        "samplesPerChannel": TOTAL_SAMPLES,
        "master": published_info["master.wav"],
        "loudness": master_info["ebur128Final"],
        "cueCount": len(measured),
        "captionCount": len(captions),
        "dropFrame": DROP_FRAME,
        "humanListening": "NOT_RUN",
    }, ensure_ascii=False))
    return 0


def main() -> int:
    try:
        return run_build()
    except (AudioBuildError, OSError, ValueError, TypeError, wave.Error, subprocess.SubprocessError) as exc:
        print(f"build_audio.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
