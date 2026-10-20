#!/usr/bin/env python3
"""Generate authorized EP10 narration cues and preserve hash-verified caches."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path
from typing import Any


PROJECT = Path(__file__).resolve().parents[1]
AUDIO = PROJECT / "public" / "audio"
AUTHORIZATION_PATH = PROJECT / "audio-authorization.json"
SEGMENTS_PATH = PROJECT / "segments.json"
BL = Path("/Users/guoq/.local/n/bin/bl")
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


class SynthesisError(RuntimeError):
    pass


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SynthesisError(f"cannot read {label}: {exc}") from None
    if not isinstance(value, dict):
        raise SynthesisError(f"{label} must contain a JSON object")
    return value


def load_segments() -> list[dict[str, Any]]:
    try:
        segments = json.loads(SEGMENTS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SynthesisError(f"cannot read segments.json: {exc}") from None
    expected = [f"S{i:02d}" for i in range(1, 9)]
    if not isinstance(segments, list) or [item.get("id") for item in segments] != expected:
        raise SynthesisError("segments.json must contain S01 through S08 in source order")
    for segment in segments:
        if not isinstance(segment.get("tts_phonetic_text"), str) or not segment["tts_phonetic_text"].strip():
            raise SynthesisError(f"{segment.get('id', 'segment')} has no tts_phonetic_text")
        if not isinstance(segment.get("startFrame"), int) or not isinstance(segment.get("endFrame"), int):
            raise SynthesisError(f"{segment['id']} needs integer startFrame/endFrame")
        if segment["startFrame"] >= segment["endFrame"]:
            raise SynthesisError(f"{segment['id']} has an invalid frame window")
    return segments


def validate_authorization(segments: list[dict[str, Any]]) -> str:
    value = read_json(AUTHORIZATION_PATH, "audio-authorization.json")
    for key, expected in AUTHORIZATION_CONTRACT.items():
        if value.get(key) != expected:
            raise SynthesisError(f"audio-authorization.json does not match current EP10 authorization field {key!r}; no provider call was attempted")
    if value.get("voice") != SETTINGS["voice"]:
            raise SynthesisError("audio-authorization.json voice differs from the packet; no provider call was attempted")
    expected_text_hash = sha_bytes(json.dumps(
        [segment["tts_phonetic_text"] for segment in segments], ensure_ascii=False
    ).encode("utf-8"))
    if value.get("text_sha256") != expected_text_hash:
            raise SynthesisError("audio-authorization.json text_sha256 does not match the exact ordered prepared texts; no provider call was attempted")
    return sha_file(AUTHORIZATION_PATH)


def recursive_values(obj: Any, key_names: set[str]) -> list[str]:
    values: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key.lower() in key_names and isinstance(value, str):
                values.append(value)
            elif isinstance(value, (dict, list)):
                values.extend(recursive_values(value, key_names))
    elif isinstance(obj, list):
        for value in obj:
            values.extend(recursive_values(value, key_names))
    return sorted(set(values))


def cache_key(text: str) -> str:
    payload = json.dumps({"text": text, "settings": SETTINGS}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verified_cache(entry: Any, key: str) -> bool:
    if not isinstance(entry, dict) or entry.get("cache_key") != key:
        return False
    for path_field, hash_field in (("raw_path", "raw_sha256"), ("canonical_path", "canonical_sha256"), ("cue_path", "cue_sha256")):
        relative = entry.get(path_field)
        if not isinstance(relative, str):
            return False
        path = (PROJECT / relative).resolve()
        if not path.is_relative_to(PROJECT.resolve()) or not path.is_file():
            raise SynthesisError("matching TTS manifest entry has a missing or out-of-project cache file; preserved")
        if entry.get(hash_field) != sha_file(path):
            raise SynthesisError(f"matching TTS cache has a divergent {path.name}; preserved")
    return True


def parse_provider_wav(raw: bytes) -> tuple[bytes, dict[str, Any]]:
    if len(raw) < 12 or raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise SynthesisError("provider output is not a RIFF/WAVE file")
    riff_declared = struct.unpack_from("<I", raw, 4)[0]
    offset = 12
    fmt = None
    payload = None
    data_declared = None
    data_start = None
    data_available = None
    while offset + 8 <= len(raw):
        chunk_id = raw[offset:offset + 4]
        chunk_size = struct.unpack_from("<I", raw, offset + 4)[0]
        start = offset + 8
        if chunk_id == b"fmt ":
            if chunk_size < 16 or start + 16 > len(raw):
                raise SynthesisError("provider WAV has a truncated fmt chunk")
            fmt = struct.unpack_from("<HHIIHH", raw, start)
        elif chunk_id == b"data":
            data_declared = chunk_size
            data_start = start
            data_available = len(raw) - start
            payload = raw[start:start + chunk_size] if chunk_size <= data_available else raw[start:]
            break
        next_offset = start + chunk_size + (chunk_size & 1)
        if next_offset > len(raw):
            raise SynthesisError("provider WAV has a truncated non-data chunk")
        offset = next_offset
    if fmt is None or payload is None or data_declared is None or data_start is None or data_available is None:
        raise SynthesisError("provider WAV is missing fmt or data")
    encoding, channels, rate, byte_rate, block_align, bits = fmt
    if (encoding, channels, rate, block_align, bits, byte_rate) != (1, 1, 24_000, 2, 16, 48_000):
        raise SynthesisError(f"provider WAV must be mono PCM16 at 24 kHz; received fmt={fmt}")
    if len(payload) == 0 or len(payload) % 2:
        raise SynthesisError("provider PCM payload is empty or not 16-bit aligned")
    overflow = data_declared > data_available or riff_declared > len(raw) - 8
    if data_declared > data_available and data_start + data_available != len(raw):
        raise SynthesisError("provider data-size overflow is not a trailing PCM payload; raw output preserved")
    return payload, {
        "actualSamples24k": len(payload) // 2,
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
        wav.setframerate(24_000)
        wav.writeframes(payload)


def manifest_for_call(path: Path, auth_hash: str) -> dict[str, Any]:
    if path.is_file():
        value = read_json(path, "provider-manifest.json")
        if value.get("settings") != SETTINGS or not isinstance(value.get("segments"), dict):
            raise SynthesisError("existing provider-manifest.json has different settings or no segment map; preserved")
        value.setdefault("cacheHistory", [])
        return value
    return {
        "version": 1,
        "settings": SETTINGS,
        "authorization": {
            "manifest": "project/audio-authorization.json",
            "sha256AtInvocation": auth_hash,
            "scope": AUTHORIZATION_CONTRACT["scope"],
            "source": AUTHORIZATION_CONTRACT["source"],
        },
        "segments": {},
        "cacheHistory": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("segment", nargs="?", help="S01..S08 or all")
    parser.add_argument("--authorized", action="store_true", help="require the packet's direct-human authorization record before any provider call")
    parser.add_argument("--only", choices=[f"S{i:02d}" for i in range(1, 9)], help="synthesize only this first-check cue")
    args = parser.parse_args()
    try:
        segments = load_segments()
        if args.segment and args.only:
            raise SynthesisError("choose either a positional segment or --only, not both")
        requested = args.only or args.segment
        if requested is None:
            raise SynthesisError("choose --only S01..S08 or the positional segment/all")
        selection = segments if requested == "all" else [item for item in segments if item["id"] == requested]
        if not selection:
            raise SynthesisError("unknown segment; use S01..S08 or all")
        manifest_path = AUDIO / "provider-manifest.json"
        old = read_json(manifest_path, "provider-manifest.json") if manifest_path.is_file() else None
        if old is not None and (old.get("settings") != SETTINGS or not isinstance(old.get("segments"), dict)):
            raise SynthesisError("existing provider manifest settings differ; preserved")
        entries = old.get("segments", {}) if old else {}
        needed = []
        cache_metadata_changed = False
        for segment in selection:
            key = cache_key(segment["tts_phonetic_text"])
            entry = entries.get(segment["id"]) if isinstance(entries, dict) else None
            if verified_cache(entry, key):
                print(f"{segment['id']}: verified matching hash cache reused")
                window_samples = (segment["endFrame"] - segment["startFrame"]) * 800
                current_metadata = {
                    "declared_start_frame": segment["startFrame"],
                    "declared_end_frame": segment["endFrame"],
                    "declared_window_samples": window_samples,
                    "fits_declared_window_before_onset_adjustment": entry.get("actual_samples_48k", 0) <= window_samples,
                }
                if any(entry.get(key) != value for key, value in current_metadata.items()):
                    entry.update(current_metadata)
                    cache_metadata_changed = True
            else:
                needed.append((segment, key))
        if not needed:
            if cache_metadata_changed and old is not None:
                write_json(manifest_path, old)
            print("All requested EP10 cues match verified caches; no provider calls needed.")
            return 0
        if not args.authorized:
            raise SynthesisError("--authorized is required before any provider call; no provider call was attempted")
        auth_hash = validate_authorization(segments)
        if not BL.is_absolute() or not BL.is_file() or not os.access(BL, os.X_OK):
            raise SynthesisError(f"authorized CLI path is unavailable or not executable: {BL}")
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            raise SynthesisError("ffmpeg is required for local PCM resampling; no provider call was attempted")
        if cache_metadata_changed and old is not None:
            write_json(manifest_path, old)
        AUDIO.mkdir(parents=True, exist_ok=True)
        for folder in ("raw", "canonical", "cues", "tts-input"):
            (AUDIO / folder).mkdir(parents=True, exist_ok=True)
        manifest = manifest_for_call(manifest_path, auth_hash)

        for segment, key in needed:
            sid = segment["id"]
            suffix = key[:12]
            text_path = AUDIO / "tts-input" / f"{sid}-{suffix}.txt"
            raw_path = AUDIO / "raw" / f"{sid}-{suffix}.wav"
            canonical_path = AUDIO / "canonical" / f"{sid}-{suffix}.wav"
            cue_path = AUDIO / "cues" / f"{sid}-{suffix}.wav"
            if any(path.exists() for path in (text_path, raw_path, canonical_path, cue_path)):
                raise SynthesisError(f"versioned path for {sid} exists without a verified matching manifest; preserved")
            text_path.write_text(segment["tts_phonetic_text"], encoding="utf-8")
            process = subprocess.run([
                str(BL), "speech", "synthesize", "--text-file", str(text_path), "--voice", SETTINGS["voice"],
                "--rate", str(SETTINGS["rate"]), "--format", SETTINGS["format"], "--sample-rate", str(SETTINGS["sample_rate"]),
                "--out", str(raw_path), "--concurrent", "1", "--output", "json",
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            if process.returncode:
                raise SynthesisError(f"{sid}: Bailian synthesis failed with exit {process.returncode}; response details were not retained")
            try:
                response = json.loads(process.stdout)
            except json.JSONDecodeError:
                raise SynthesisError(f"{sid}: CLI response was not JSON; raw audio remains preserved") from None
            models = recursive_values(response, {"model", "model_id", "resolved_model"})
            voices = recursive_values(response, {"voice", "voice_id", "resolved_voice"})
            if models != [SETTINGS["effective_model"]] or voices != [SETTINGS["voice"]]:
                raise SynthesisError(f"NEEDS_SOL: {sid} reported model/voice {models}/{voices}; raw audio preserved, no fallback selected")
            raw = raw_path.read_bytes()
            payload, pcm_meta = parse_provider_wav(raw)
            write_canonical_wav(canonical_path, payload)
            temp_cue = cue_path.with_name(cue_path.stem + ".tmp.wav")
            try:
                conversion = subprocess.run([
                    ffmpeg, "-v", "error", "-xerror", "-y", "-i", str(canonical_path), "-ar", "48000", "-ac", "1",
                    "-c:a", "pcm_s16le", str(temp_cue),
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                if conversion.returncode:
                    raise SynthesisError(f"{sid}: local 48 kHz conversion failed with exit {conversion.returncode}")
                with wave.open(str(temp_cue), "rb") as wav:
                    params = wav.getparams()
                    samples = params.nframes
                    cue_payload = wav.readframes(samples)
                if (params.framerate, params.nchannels, params.sampwidth, params.comptype) != (48_000, 1, 2, "NONE") or len(cue_payload) != samples * 2:
                    raise SynthesisError(f"{sid}: converted cue is not complete 48 kHz mono PCM16")
                if not any(cue_payload):
                    raise SynthesisError(f"{sid}: provider returned digital silence")
                temp_cue.replace(cue_path)
            finally:
                temp_cue.unlink(missing_ok=True)
            window_samples = (segment["endFrame"] - segment["startFrame"]) * 800
            entry = {
                "cache_key": key,
                "tts_phonetic_text": segment["tts_phonetic_text"],
                "settings": SETTINGS,
                "actual_samples_24k": pcm_meta["actualSamples24k"],
                "actual_samples_48k": samples,
                "duration_seconds": samples / 48_000,
                "declared_window_samples": window_samples,
                "fits_declared_window_before_onset_adjustment": samples <= window_samples,
                "pcm_sha256_24k": pcm_meta["pcmSha256"],
                "raw_header_matches_payload": pcm_meta["rawHeaderMatchesPayload"],
                "verified_pcm_overflow_repair": pcm_meta["verifiedPcmOverflowRepair"],
                "raw_path": str(raw_path.relative_to(PROJECT)),
                "raw_sha256": sha_file(raw_path),
                "canonical_path": str(canonical_path.relative_to(PROJECT)),
                "canonical_sha256": sha_file(canonical_path),
                "cue_path": str(cue_path.relative_to(PROJECT)),
                "cue_sha256": sha_file(cue_path),
                "effective_model": models,
                "effective_voice": voices,
                "identity_status": "reported by CLI response",
            }
            previous = manifest["segments"].get(sid)
            if previous:
                manifest.setdefault("cacheHistory", []).append({"id": sid, **previous})
            manifest["segments"][sid] = entry
            manifest["authorization"] = {
                "manifest": "project/audio-authorization.json",
                "sha256AtInvocation": auth_hash,
                "scope": AUTHORIZATION_CONTRACT["scope"],
                "source": AUTHORIZATION_CONTRACT["source"],
            }
            write_json(manifest_path, manifest)
            print(json.dumps({
                "segment": sid,
                "durationSeconds": round(samples / 48_000, 6),
                "windowSeconds": (segment["endFrame"] - segment["startFrame"]) / 60,
                "effectiveModel": models,
                "effectiveVoice": voices,
                "verifiedPcmOverflowRepair": pcm_meta["verifiedPcmOverflowRepair"],
            }, ensure_ascii=False))
            if samples > window_samples:
                raise SynthesisError(f"NEEDS_SOL: {sid} PCM has {samples} samples for a {window_samples}-sample window; complete cache retained, with no speed change or truncation")
        return 0
    except (SynthesisError, OSError, ValueError, wave.Error, subprocess.SubprocessError) as exc:
        print(f"synthesize.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
