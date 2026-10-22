#!/usr/bin/env python3
"""Synthesize authorized EP16 narration and measure complete PCM cues."""

from __future__ import annotations

import argparse
import array
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT.parent
AUDIO = PROJECT / "public" / "audio"
SEGMENTS_PATH = PROJECT / "segments.json"
AUTHORIZATION_PATH = PROJECT / "audio-authorization.json"
PREFLIGHT_PATH = WORK / "review" / "provider-preflight.json"
ENVIRONMENT_PREFLIGHT_PATH = WORK / "review" / "preflight.json"
MANIFEST_PATH = AUDIO / "provider-manifest.json"
SAMPLE_RATE_24K = 24_000
SAMPLE_RATE_48K = 48_000
FPS = 60
SETTINGS = {
    "provider": "Aliyun Bailian",
    "model_selection": "active profile default",
    "effective_model": "cosyvoice-v3-flash",
    "voice": "longtian_v3",
    "rate": 1.0,
    "format": "wav",
    "sample_rate": SAMPLE_RATE_24K,
}
AUTHORIZATION_CONTRACT = {
    "provider": "Aliyun Bailian",
    "scope": "EP16 S01 through S09 prepared tts_phonetic_text",
    "authorized": True,
    "source": "Direct user confirmation in this EP16 chat on 2026-10-22: 授权，沿用系列百炼配音",
    "voice": "longtian_v3",
}
EXPECTED_IDS = [f"S{i:02d}" for i in range(1, 10)]


class SynthesisError(RuntimeError):
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
        raise SynthesisError(f"temporary metadata file already exists; preserved: {temporary}")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SynthesisError(f"cannot read {label}: {exc}") from None


def load_segments() -> list[dict[str, Any]]:
    value = load_json(SEGMENTS_PATH, "segments.json")
    if not isinstance(value, list) or [item.get("id") for item in value] != EXPECTED_IDS:
        raise SynthesisError("segments.json must contain S01 through S09 in source order")
    for item in value:
        if not isinstance(item.get("tts_phonetic_text"), str) or not item["tts_phonetic_text"].strip():
            raise SynthesisError(f"{item.get('id', 'segment')} has no prepared TTS phonetic text")
        if not isinstance(item.get("startFrame"), int) or not isinstance(item.get("endFrame"), int):
            raise SynthesisError(f"{item['id']} needs integer startFrame/endFrame")
        if not 0 <= item["startFrame"] < item["endFrame"] <= 7200:
            raise SynthesisError(f"{item['id']} has invalid frame bounds outside the 120-second timeline")
    return value


def validate_authorization(segments: list[dict[str, Any]]) -> tuple[str, str]:
    value = load_json(AUTHORIZATION_PATH, "audio-authorization.json")
    for key, expected in AUTHORIZATION_CONTRACT.items():
        if value.get(key) != expected:
            raise SynthesisError(f"audio-authorization.json does not match current EP14 authorization field {key!r}")
    if value.get("voice") != SETTINGS["voice"]:
        raise SynthesisError("audio-authorization.json voice differs from the assigned voice")
    ordered_text_hash = sha_bytes(json.dumps(
        [item["tts_phonetic_text"] for item in segments], ensure_ascii=False
    ).encode("utf-8"))
    if value.get("text_sha256") != ordered_text_hash:
        raise SynthesisError("audio-authorization.json does not match the exact ordered prepared texts")
    return sha_file(AUTHORIZATION_PATH), ordered_text_hash


def cache_key(text: str) -> str:
    return canonical_hash({"text": text, "settings": SETTINGS})


def recursive_values(obj: Any, keys: set[str]) -> list[str]:
    values: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key.lower() in keys and isinstance(value, str):
                values.append(value)
            elif isinstance(value, (dict, list)):
                values.extend(recursive_values(value, keys))
    elif isinstance(obj, list):
        for value in obj:
            values.extend(recursive_values(value, keys))
    return sorted(set(values))


def parse_provider_wav(raw: bytes) -> tuple[bytes, dict[str, Any]]:
    if len(raw) < 12 or raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise SynthesisError("provider output is not a RIFF/WAVE file; raw output preserved")
    riff_declared = struct.unpack_from("<I", raw, 4)[0]
    offset = 12
    fmt = None
    payload = None
    data_declared = None
    data_start = None
    while offset + 8 <= len(raw):
        chunk_id = raw[offset:offset + 4]
        chunk_size = struct.unpack_from("<I", raw, offset + 4)[0]
        start = offset + 8
        if chunk_id == b"fmt ":
            if chunk_size < 16 or start + 16 > len(raw):
                raise SynthesisError("provider WAV has a truncated fmt chunk; raw output preserved")
            fmt = struct.unpack_from("<HHIIHH", raw, start)
        elif chunk_id == b"data":
            data_declared = chunk_size
            data_start = start
            available = len(raw) - start
            payload = raw[start:start + chunk_size] if chunk_size <= available else raw[start:]
            break
        next_offset = start + chunk_size + (chunk_size & 1)
        if next_offset > len(raw):
            raise SynthesisError("provider WAV has a truncated non-data chunk; raw output preserved")
        offset = next_offset
    if fmt is None or payload is None or data_declared is None or data_start is None:
        raise SynthesisError("provider WAV is missing fmt or data; raw output preserved")
    encoding, channels, rate, byte_rate, align, bits = fmt
    if (encoding, channels, rate, byte_rate, align, bits) != (1, 1, SAMPLE_RATE_24K, 48_000, 2, 16):
        raise SynthesisError(f"provider WAV must be mono PCM16 at 24 kHz; received fmt={fmt}; raw preserved")
    if not payload or len(payload) % 2:
        raise SynthesisError("provider PCM payload is empty or not 16-bit aligned; raw output preserved")
    available = len(raw) - data_start
    overflow = data_declared > available or riff_declared > len(raw) - 8
    if data_declared > available and data_start + available != len(raw):
        raise SynthesisError("provider data-size overflow is not a trailing PCM payload; raw output preserved")
    return payload, {
        "actualSamples24k": len(payload) // 2,
        "actualDurationSeconds": len(payload) / 2 / SAMPLE_RATE_24K,
        "pcmSha256": sha_bytes(payload),
        "rawHeaderMatchesPayload": riff_declared == len(raw) - 8 and data_declared == len(payload),
        "verifiedPcmOverflowRepair": bool(overflow),
        "declaredRiffBytesAfterHeader": riff_declared,
        "actualRiffBytesAfterHeader": len(raw) - 8,
        "declaredDataBytes": data_declared,
        "actualDataBytes": len(payload),
    }


def write_canonical_wav(path: Path, payload: bytes) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE_24K)
        wav.writeframes(payload)


def measure_active_bounds(payload: bytes) -> tuple[int, int, dict[str, Any]]:
    samples = array.array("h")
    samples.frombytes(payload)
    if sys.byteorder != "little":
        samples.byteswap()
    peak = max((abs(sample) for sample in samples), default=0)
    if peak == 0:
        raise SynthesisError("cue is digital silence")
    threshold = max(48, round(peak * 0.004))
    window = min(240, len(samples))
    required_power = window * threshold * threshold
    power = sum(sample * sample for sample in samples[:window])
    first = last = None
    for start in range(0, len(samples) - window + 1):
        if power >= required_power:
            if first is None:
                first = start
            last = start + window
        if start + window < len(samples):
            power += samples[start + window] ** 2 - samples[start] ** 2
    if first is None or last is None:
        raise SynthesisError("cue has no measurable PCM activity above the onset threshold")
    return first, last, {
        "method": "5 ms sliding RMS; threshold=max(48 PCM16, 0.4% of cue peak)",
        "thresholdPcm16": threshold,
        "windowSamples": window,
    }


def read_cue(path: Path) -> tuple[int, int, int, int, str, dict[str, Any]]:
    try:
        with wave.open(str(path), "rb") as wav:
            params = wav.getparams()
            payload = wav.readframes(params.nframes)
    except (OSError, wave.Error) as exc:
        raise SynthesisError(f"cannot decode {path.name}: {exc}") from None
    if (params.framerate, params.nchannels, params.sampwidth, params.comptype) != (SAMPLE_RATE_48K, 1, 2, "NONE"):
        raise SynthesisError(f"{path.name} is not mono 48 kHz PCM16")
    if len(payload) != params.nframes * 2 or not payload:
        raise SynthesisError(f"{path.name} has an incomplete payload")
    onset, end, method = measure_active_bounds(payload)
    return params.nframes, onset, end, max(abs(sample) for sample in array.array("h", payload)), sha_bytes(payload), method


def write_or_verify_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise SynthesisError(f"versioned TTS input is divergent and was preserved: {path}")
        return
    path.write_text(text, encoding="utf-8")


def base_preflight(auth_hash: str, text_hash: str) -> dict[str, Any]:
    if PREFLIGHT_PATH.exists():
        value = load_json(PREFLIGHT_PATH, "provider-preflight.json")
        if value.get("authorization", {}).get("sha256") != auth_hash or value.get("orderedTextSha256") != text_hash:
            raise SynthesisError("existing provider-preflight.json belongs to different authorization/text; preserved")
        if value.get("settings") != SETTINGS or not isinstance(value.get("calls"), list):
            raise SynthesisError("existing provider-preflight.json settings differ; preserved")
        return value
    environment = load_json(ENVIRONMENT_PREFLIGHT_PATH, "review/preflight.json")
    if (environment.get("blCLI"), environment.get("blSkill"), environment.get("npmLatest")) != ("2.5.0", "2.5.0", "2.5.0"):
        raise SynthesisError("review/preflight.json does not prove aligned CLI, skill, and npm versions")
    if environment.get("authenticated") is not True or environment.get("credentialsRecorded") is not False:
        raise SynthesisError("review/preflight.json does not prove authenticated status without recorded secrets")
    bl = shutil.which("bl", path="/Users/guoq/.local/n/bin:" + os.environ.get("PATH", ""))
    return {
        "version": 1,
        "project": "si-ep16-frictionless-world",
        "cli": {"binary": bl, "version": f"bl {environment['blCLI']}", "skillVersion": environment["blSkill"], "npmLatest": environment["npmLatest"]},
        "authStatus": {"authenticated": True, "evidence": "review/preflight.json", "secretsRecorded": False},
        "settings": SETTINGS,
        "orderedTextSha256": text_hash,
        "authorization": {"file": "project/audio-authorization.json", "sha256": auth_hash, "scope": AUTHORIZATION_CONTRACT["scope"]},
        "calls": [],
    }


def update_preflight(call: dict[str, Any], auth_hash: str, text_hash: str) -> dict[str, Any]:
    value = base_preflight(auth_hash, text_hash)
    for index, prior in enumerate(value["calls"]):
        if prior.get("segmentId") == call.get("segmentId") and prior.get("cacheKey") == call.get("cacheKey"):
            if prior != call:
                raise SynthesisError(f"existing preflight call for {call.get('segmentId')} is divergent; preserved")
            return value
    value["calls"].append(call)
    write_json(PREFLIGHT_PATH, value)
    return value


def find_preflight_call(value: dict[str, Any], sid: str, key: str) -> dict[str, Any] | None:
    return next((item for item in value.get("calls", []) if item.get("segmentId") == sid and item.get("cacheKey") == key), None)


def verified_manifest_entry(entry: Any, key: str) -> bool:
    if not isinstance(entry, dict) or entry.get("cacheKey") != key:
        return False
    for path_field, hash_field in (("rawPath", "rawSha256"), ("canonicalPath", "canonicalSha256"), ("cuePath", "cueSha256")):
        relative = entry.get(path_field)
        if not isinstance(relative, str):
            return False
        path = (PROJECT / relative).resolve()
        if not path.is_relative_to(PROJECT.resolve()) or not path.is_file():
            raise SynthesisError(f"matching cache has missing/out-of-project file {relative}; preserved")
        if entry.get(hash_field) != sha_file(path):
            raise SynthesisError(f"matching cache file is divergent: {relative}; preserved")
    return True


def get_or_create_manifest(auth_hash: str) -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        return {"version": 1, "settings": SETTINGS, "authorization": {"file": "project/audio-authorization.json", "sha256": auth_hash}, "segments": {}}
    value = load_json(MANIFEST_PATH, "provider-manifest.json")
    if value.get("settings") != SETTINGS or not isinstance(value.get("segments"), dict):
        raise SynthesisError("existing provider-manifest.json has different settings; preserved")
    if value.get("authorization", {}).get("sha256") != auth_hash:
        raise SynthesisError("existing provider-manifest.json has a different authorization hash; preserved")
    return value


def convert_to_cue(canonical: Path, cue: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise SynthesisError("ffmpeg is required for local 48 kHz PCM conversion")
    cue.parent.mkdir(parents=True, exist_ok=True)
    temporary = cue.with_name(cue.stem + ".tmp.wav")
    if cue.exists() or temporary.exists():
        raise SynthesisError(f"canonical cue output collision; preserved: {cue if cue.exists() else temporary}")
    process = subprocess.run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-xerror", "-nostdin", "-n", "-i", str(canonical),
        "-map_metadata", "-1", "-ac", "1", "-ar", str(SAMPLE_RATE_48K), "-c:a", "pcm_s16le",
        "-af", "aresample=48000:resampler=swr:dither_method=none", str(temporary),
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if process.returncode:
        temporary.unlink(missing_ok=True)
        raise SynthesisError(f"ffmpeg conversion failed with exit {process.returncode}; cue was not published")
    temporary.replace(cue)


def invoke_provider(segment: dict[str, Any], key: str, raw_path: Path, text_path: Path, auth_hash: str, text_hash: str) -> tuple[list[str], list[str]]:
    executable = shutil.which("bl", path="/Users/guoq/.local/n/bin:" + os.environ.get("PATH", ""))
    if not executable:
        raise SynthesisError("verified bl CLI is unavailable")
    if raw_path.exists():
        raise SynthesisError(f"versioned raw path already exists without a verified cache; preserved: {raw_path}")
    env = os.environ.copy()
    env["PATH"] = "/Users/guoq/.local/n/bin:" + env.get("PATH", "")
    process = subprocess.run([
        executable, "speech", "synthesize", "--text-file", str(text_path), "--voice", SETTINGS["voice"],
        "--rate", str(SETTINGS["rate"]), "--format", SETTINGS["format"], "--sample-rate", str(SETTINGS["sample_rate"]),
        "--out", str(raw_path), "--concurrent", "1", "--output", "json",
    ], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if process.returncode:
        value = base_preflight(auth_hash, text_hash)
        value["calls"].append({
            "segmentId": segment["id"], "cacheKey": key, "status": "failed", "returnCode": process.returncode,
            "rawFilePreserved": raw_path.is_file(), "secretsRecorded": False,
        })
        write_json(PREFLIGHT_PATH, value)
        raise SynthesisError(f"{segment['id']}: bl speech synthesize failed with exit {process.returncode}; no automatic retry")
    try:
        response = json.loads(process.stdout)
    except json.JSONDecodeError:
        raise SynthesisError(f"{segment['id']}: provider response was not JSON; raw output preserved") from None
    models = recursive_values(response, {"model", "model_id", "resolved_model"})
    voices = recursive_values(response, {"voice", "voice_id", "resolved_voice"})
    if models != [SETTINGS["effective_model"]] or voices != [SETTINGS["voice"]]:
        raise SynthesisError(f"NEEDS_SOL: {segment['id']} reported model/voice {models}/{voices}; raw output preserved, no fallback selected")
    return models, voices


def process_segment(segment: dict[str, Any], manifest: dict[str, Any], preflight: dict[str, Any], auth_hash: str, text_hash: str, args: argparse.Namespace) -> dict[str, Any]:
    sid = segment["id"]
    text = segment["tts_phonetic_text"]
    key = cache_key(text)
    suffix = key[:12]
    input_path = AUDIO / "tts-input" / f"{sid}-{suffix}.txt"
    raw_path = AUDIO / "raw" / f"{sid}-{suffix}.wav"
    canonical_path = AUDIO / "canonical" / f"{sid}-{suffix}.wav"
    cue_path = AUDIO / "cues" / f"{sid}-{suffix}.wav"
    write_or_verify_text(input_path, text)

    entry = manifest["segments"].get(sid)
    if verified_manifest_entry(entry, key):
        with wave.open(str(cue_path), "rb") as cue:
            samples = cue.getnframes()
            payload = cue.readframes(samples)
        onset, active_end, bounds = measure_active_bounds(payload)
        print_measurement(segment, entry["rawSamples24k"], samples, onset, active_end, bounds, "verified cache")
        return entry

    preflight = base_preflight(auth_hash, text_hash)
    pre_call = find_preflight_call(preflight, sid, key)
    models: list[str]
    voices: list[str]
    if raw_path.exists():
        if not pre_call or pre_call.get("status") != "succeeded" or pre_call.get("rawSha256") != sha_file(raw_path):
            raise SynthesisError(f"raw path exists without matching successful preflight evidence; preserved: {raw_path}")
        if pre_call.get("reportedModels") != [SETTINGS["effective_model"]] or pre_call.get("reportedVoices") != [SETTINGS["voice"]]:
            raise SynthesisError(f"preflight identity does not match active model/voice for {sid}; preserved")
        models = pre_call["reportedModels"]
        voices = pre_call["reportedVoices"]
    else:
        if not args.authorized:
            raise SynthesisError("--authorized is required before an uncached provider call")
        models, voices = invoke_provider(segment, key, raw_path, input_path, auth_hash, text_hash)

    if canonical_path.exists() or cue_path.exists():
        raise SynthesisError(f"unmanifested canonical/cue path exists; preserved: {canonical_path if canonical_path.exists() else cue_path}")
    raw = raw_path.read_bytes()
    pcm24, raw_meta = parse_provider_wav(raw)
    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    write_canonical_wav(canonical_path, pcm24)
    convert_to_cue(canonical_path, cue_path)
    with wave.open(str(cue_path), "rb") as cue:
        cue_params = cue.getparams()
        payload48 = cue.readframes(cue_params.nframes)
    if (cue_params.framerate, cue_params.nchannels, cue_params.sampwidth, cue_params.comptype) != (SAMPLE_RATE_48K, 1, 2, "NONE"):
        raise SynthesisError(f"{sid}: converted cue is not mono 48 kHz PCM16")
    if len(payload48) != cue_params.nframes * 2 or not any(payload48):
        raise SynthesisError(f"{sid}: converted cue has incomplete or silent PCM")
    onset, active_end, bounds = measure_active_bounds(payload48)
    window_frames = segment["endFrame"] - segment["startFrame"]
    window_samples = window_frames * (SAMPLE_RATE_48K // FPS)
    cue_end_offset = cue_params.nframes
    record = {
        "cacheKey": key,
        "ttsPhoneticText": text,
        "settings": SETTINGS,
        "effectiveModel": models[0],
        "effectiveVoice": voices[0],
        "identityStatus": "reported by CLI response",
        "rawSamples24k": raw_meta["actualSamples24k"],
        "rawDurationSeconds": raw_meta["actualDurationSeconds"],
        "actualSamples48k": cue_params.nframes,
        "durationSeconds": cue_params.nframes / SAMPLE_RATE_48K,
        "declaredWindowFrames": window_frames,
        "declaredWindowSeconds": window_frames / FPS,
        "completeCueFitsDeclaredWindow": cue_end_offset <= window_samples,
        "completeCueOverrunSamples48k": max(0, cue_end_offset - window_samples),
        "activeOnsetOffsetSamples48k": onset,
        "activeEndOffsetSamples48kExclusive": active_end,
        "activeDurationSeconds": (active_end - onset) / SAMPLE_RATE_48K,
        "activeBoundsMethod": bounds,
        "providerPcmSha256": raw_meta["pcmSha256"],
        "rawHeaderMatchesPayload": raw_meta["rawHeaderMatchesPayload"],
        "verifiedPcmOverflowRepair": raw_meta["verifiedPcmOverflowRepair"],
        "riffHeader": {key: raw_meta[key] for key in ("declaredRiffBytesAfterHeader", "actualRiffBytesAfterHeader", "declaredDataBytes", "actualDataBytes")},
        "rawPath": str(raw_path.relative_to(PROJECT)),
        "rawSha256": sha_file(raw_path),
        "canonicalPath": str(canonical_path.relative_to(PROJECT)),
        "canonicalSha256": sha_file(canonical_path),
        "cuePath": str(cue_path.relative_to(PROJECT)),
        "cueSha256": sha_file(cue_path),
        "cuePcmSha256": sha_bytes(payload48),
    }
    if not pre_call:
        call_record = {
            "segmentId": sid, "cacheKey": key, "status": "succeeded", "reportedModels": models,
            "reportedVoices": voices, "rawPath": str(raw_path.relative_to(PROJECT)), "rawSha256": record["rawSha256"],
            "rawBytes": raw_path.stat().st_size, "pcmSha256": raw_meta["pcmSha256"],
            "actualSamples24k": raw_meta["actualSamples24k"], "actualDurationSeconds": raw_meta["actualDurationSeconds"],
            "rawHeaderMatchesPayload": raw_meta["rawHeaderMatchesPayload"],
            "verifiedPcmOverflowRepair": raw_meta["verifiedPcmOverflowRepair"], "secretsRecorded": False,
        }
        preflight = update_preflight(call_record, auth_hash, text_hash)
    manifest["segments"][sid] = record
    write_json(MANIFEST_PATH, manifest)
    print_measurement(segment, raw_meta["actualSamples24k"], cue_params.nframes, onset, active_end, bounds, "provider response")
    return record


def print_measurement(segment: dict[str, Any], samples24k: int, samples48k: int, onset: int, active_end: int, bounds: dict[str, Any], source: str) -> None:
    window = (segment["endFrame"] - segment["startFrame"]) / FPS
    duration = samples48k / SAMPLE_RATE_48K
    print(json.dumps({
        "segmentId": segment["id"], "source": source, "samples24k": samples24k,
        "samples48k": samples48k, "durationSeconds": round(duration, 6),
        "activeOnsetOffsetSamples48k": onset, "activeEndOffsetSamples48kExclusive": active_end,
        "activeDurationSeconds": round((active_end-onset)/SAMPLE_RATE_48K, 6),
        "windowSeconds": window, "completeCueFitsWindow": duration <= window,
        "overrunSeconds": round(max(0.0, duration-window), 6), "activeBoundsMethod": bounds,
    }, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("segment", nargs="?", choices=[*EXPECTED_IDS, "all"])
    parser.add_argument("--only", nargs="+", choices=EXPECTED_IDS, help="process these cues in source order")
    parser.add_argument("--authorized", action="store_true", help="require the current task authorization before any provider request")
    args = parser.parse_args()
    try:
        if args.segment and args.only:
            raise SynthesisError("choose either the positional segment/all or --only")
        if not args.segment and not args.only:
            raise SynthesisError("choose S01..S09, all, or --only with one or more segment IDs")
        segments = load_segments()
        auth_hash, text_hash = validate_authorization(segments)
        if args.only:
            requested = set(args.only)
            selection = [item for item in segments if item["id"] in requested]
        elif args.segment == "all":
            selection = segments
        else:
            selection = [item for item in segments if item["id"] == args.segment]
        AUDIO.mkdir(parents=True, exist_ok=True)
        manifest = get_or_create_manifest(auth_hash)
        preflight = base_preflight(auth_hash, text_hash)
        if not PREFLIGHT_PATH.exists():
            write_json(PREFLIGHT_PATH, preflight)
        for segment in selection:
            record = process_segment(segment, manifest, preflight, auth_hash, text_hash, args)
            next_segment = next((item for item in segments if item["startFrame"] > segment["startFrame"]), None)
            next_active_start = next_segment["startFrame"] if next_segment else 7200
            start_sample = segment["startFrame"] * (SAMPLE_RATE_48K // FPS)
            end_sample = start_sample + record["actualSamples48k"]
            active_end_sample = start_sample + record["activeEndOffsetSamples48kExclusive"]
            declared_end_sample = segment["endFrame"] * (SAMPLE_RATE_48K // FPS)
            next_active_start_sample = next_active_start * (SAMPLE_RATE_48K // FPS)
            record["placement"] = {
                "startFrame": segment["startFrame"],
                "declaredEndFrameExclusive": segment["endFrame"],
                "nextActiveStartFrame": next_active_start,
                "absoluteCueEndSampleExclusive": end_sample,
                "absoluteActiveEndSampleExclusive": active_end_sample,
                "cueEndsByDeclaredEndFrame": end_sample <= declared_end_sample,
                "activeSpeechEndsByDeclaredEndFrame": active_end_sample <= declared_end_sample,
                "cueAvoidsNextActiveRange": end_sample <= next_active_start_sample,
            }
            record["completeCueFitsDeclaredWindow"] = record["placement"]["cueEndsByDeclaredEndFrame"]
            manifest["segments"][segment["id"]] = record
            write_json(MANIFEST_PATH, manifest)
            if not record["placement"]["activeSpeechEndsByDeclaredEndFrame"] or not record["placement"]["cueAvoidsNextActiveRange"]:
                raise SynthesisError(
                    f"NEEDS_SOL: {segment['id']} complete cue {record['durationSeconds']:.3f}s, "
                    f"active speech {(record['activeEndOffsetSamples48kExclusive'] - record['activeOnsetOffsetSamples48k']) / SAMPLE_RATE_48K:.3f}s; "
                    f"active speech end frame {active_end_sample / (SAMPLE_RATE_48K // FPS):.2f}, "
                    f"declared end frame {segment['endFrame']}, next active start frame {next_active_start}; speech was not trimmed"
                )
        return 0
    except (SynthesisError, OSError, ValueError, wave.Error, subprocess.SubprocessError) as exc:
        print(f"synthesize.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
