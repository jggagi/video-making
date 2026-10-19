#!/usr/bin/env python3
"""Generate only explicitly authorized EP07 Bailian narration and preserve measured caches."""

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
WORK = PROJECT.parent
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
    "scope": "EP07 ten original tts_phonetic_text segments and Q98 quote only",
    "authorized": True,
    "source": "direct user reply in current chat",
    "settings": {
        "model_selection": "active profile default",
        "voice": "longtian_v3",
        "rate": 1.0,
    },
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
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def load_segments() -> list[dict[str, Any]]:
    try:
        data = json.loads(SEGMENTS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SynthesisError(f"cannot read segments.json: {exc}") from None
    segments = data.get("segments") if isinstance(data, dict) else None
    if not isinstance(segments, list) or [item.get("id") for item in segments] != [f"S{i:02d}" for i in range(1, 11)] + ["Q98"]:
        raise SynthesisError("segments.json must contain S01 through S10 then Q98 in source order")
    for segment in segments:
        if not isinstance(segment.get("tts_phonetic_text"), str) or not segment["tts_phonetic_text"].strip():
            raise SynthesisError(f"{segment.get('id', 'segment')} has no tts_phonetic_text")
        if not isinstance(segment.get("startFrame"), int) or not isinstance(segment.get("endFrame"), int) or segment["startFrame"] >= segment["endFrame"]:
            raise SynthesisError(f"{segment['id']} has an invalid frame window")
    return segments


def authorization_error() -> str | None:
    try:
        value = json.loads(AUTHORIZATION_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return "project/audio-authorization.json is missing; no provider call was attempted"
    except (OSError, json.JSONDecodeError) as exc:
        return f"project/audio-authorization.json cannot be read: {exc}; no provider call was attempted"
    if not isinstance(value, dict):
        return "audio-authorization.json must be an object; no provider call was attempted"
    for key, expected in AUTHORIZATION_CONTRACT.items():
        if value.get(key) != expected:
            return f"audio-authorization.json does not match the required current-EP07 authorization field {key!r}; no provider call was attempted"
    return None


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


def checked_cache(entry: dict[str, Any] | None, key: str) -> bool:
    if entry is None or entry.get("cache_key") != key:
        return False
    cue = PROJECT / entry.get("cue_path", "")
    raw = PROJECT / entry.get("raw_path", "")
    canonical = PROJECT / entry.get("canonical_path", "")
    if not all(path.is_file() for path in (cue, raw, canonical)):
        raise SynthesisError("matching TTS manifest entry has a missing cache file; preserved for review")
    expected = ((cue, "cue_sha256"), (raw, "raw_sha256"), (canonical, "canonical_sha256"))
    for path, field in expected:
        if entry.get(field) != sha_file(path):
            raise SynthesisError(f"matching TTS cache has a divergent {path.name}; preserved for review")
    return True


def parse_provider_wav(raw: bytes) -> tuple[bytes, dict[str, Any]]:
    """Accept PCM16 mono 24 kHz WAV; repair only a verified trailing data overflow."""
    if len(raw) < 12 or raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise SynthesisError("provider response is not a RIFF/WAVE file")
    riff_declared = struct.unpack_from("<I", raw, 4)[0]
    offset = 12
    fmt = None
    payload = None
    data_declared = None
    data_available = None
    data_start = None
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
            if chunk_size <= data_available:
                payload = raw[start:start + chunk_size]
            else:
                # A size overflow is repairable only when verified PCM16 data
                # occupies the physical tail of the raw response.
                payload = raw[start:]
            break
        next_offset = start + chunk_size + (chunk_size & 1)
        if next_offset > len(raw):
            raise SynthesisError("provider WAV has a truncated non-data chunk")
        offset = next_offset
    if fmt is None or payload is None or data_declared is None or data_start is None:
        raise SynthesisError("provider WAV is missing fmt or data")
    encoding, channels, rate, byte_rate, block_align, bits = fmt
    if (encoding, channels, rate, block_align, bits) != (1, 1, 24_000, 2, 16) or byte_rate != 48_000:
        raise SynthesisError(f"provider WAV must be mono PCM16 at 24 kHz; got fmt={fmt}")
    if len(payload) == 0 or len(payload) % 2:
        raise SynthesisError("verified provider PCM payload is empty or not 16-bit aligned")
    overflow = data_declared > data_available or riff_declared > len(raw) - 8
    if data_declared > data_available and data_start + data_available != len(raw):
        raise SynthesisError("provider data-size overflow is not a trailing PCM payload; raw preserved")
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


def effective_wav(raw_path: Path, canonical_path: Path) -> dict[str, Any]:
    raw = raw_path.read_bytes()
    payload, meta = parse_provider_wav(raw)
    with wave.open(str(canonical_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24_000)
        wav.writeframes(payload)
    return meta


def run_checked(command: list[str], label: str) -> None:
    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if process.returncode:
        raise SynthesisError(f"{label} failed with exit {process.returncode}; raw provider result is preserved")


def manifest_for_call(path: Path, auth_hash: str) -> dict[str, Any]:
    if path.is_file():
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SynthesisError(f"provider-manifest.json is unreadable: {exc}") from None
        if not isinstance(value, dict) or value.get("settings") != SETTINGS:
            raise SynthesisError("existing provider manifest settings differ; preserved")
        if not isinstance(value.get("segments"), dict):
            raise SynthesisError("existing provider manifest has no segment map; preserved")
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
            "note": "Current EP07 authorization only; no EP05 consent is inherited.",
        },
        "segments": {},
        "cacheHistory": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("segment", help="S01..S10, Q98, or all")
    parser.add_argument("--authorized", action="store_true", help="explicit execution acknowledgement; current authorization manifest is also required")
    parser.add_argument("--collect-unfitted", action="store_true", help="collect measured cues even if the draft window is too short; mixer fit checks remain mandatory")
    args = parser.parse_args()
    try:
        segments = load_segments()
        selection = segments if args.segment == "all" else [segment for segment in segments if segment["id"] == args.segment]
        if not selection:
            raise SynthesisError("unknown segment; use S01..S10, Q98, or all")
        manifest_path = AUDIO / "provider-manifest.json"
        if manifest_path.is_file():
            try:
                old_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise SynthesisError(f"provider-manifest.json is unreadable: {exc}") from None
            if not isinstance(old_manifest, dict) or old_manifest.get("settings") != SETTINGS:
                raise SynthesisError("existing provider manifest settings differ; preserved")
            old_entries = old_manifest.get("segments", {})
        else:
            old_manifest, old_entries = None, {}

        needed: list[tuple[dict[str, Any], str]] = []
        for segment in selection:
            key = cache_key(segment["tts_phonetic_text"])
            entry = old_entries.get(segment["id"]) if isinstance(old_entries, dict) else None
            if checked_cache(entry, key):
                print(f"{segment['id']}: verified matching cache reused")
            else:
                needed.append((segment, key))
        if not needed:
            print("No provider calls needed; all requested EP07 cues match verified caches.")
            return 0

        if not args.authorized:
            raise SynthesisError("--authorized is required before any provider call; no provider call was attempted")
        auth_error = authorization_error()
        if auth_error:
            raise SynthesisError(auth_error)
        if not BL.is_absolute() or not BL.is_file() or not os.access(BL, os.X_OK):
            raise SynthesisError(f"authorized CLI path is unavailable or not executable: {BL}")
        auth_hash = sha_file(AUTHORIZATION_PATH)
        manifest = manifest_for_call(manifest_path, auth_hash)
        for folder in ("raw", "canonical", "cues", "tts-input"):
            (AUDIO / folder).mkdir(parents=True, exist_ok=True)

        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            raise SynthesisError("ffmpeg is required for local PCM resampling; no provider call was attempted")

        for segment, key in needed:
            sid = segment["id"]
            suffix = key[:12]
            text_path = AUDIO / "tts-input" / f"{sid}-{suffix}.txt"
            raw_path = AUDIO / "raw" / f"{sid}-{suffix}.wav"
            canonical_path = AUDIO / "canonical" / f"{sid}-{suffix}.wav"
            cue_path = AUDIO / "cues" / f"{sid}-{suffix}.wav"
            paths = (text_path, raw_path, canonical_path, cue_path)
            if any(path.exists() for path in paths):
                raise SynthesisError(f"versioned cache path for {sid} already exists without a verified matching manifest; preserved")
            text_path.write_text(segment["tts_phonetic_text"], encoding="utf-8")
            process = subprocess.run([
                str(BL), "speech", "synthesize", "--text-file", str(text_path), "--voice", SETTINGS["voice"],
                "--rate", str(SETTINGS["rate"]), "--format", SETTINGS["format"], "--sample-rate", str(SETTINGS["sample_rate"]),
                "--out", str(raw_path), "--concurrent", "1", "--output", "json",
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            if process.returncode:
                raise SynthesisError(f"{sid}: Bailian synthesis failed with exit {process.returncode}; credential output not retained")
            try:
                response = json.loads(process.stdout)
            except json.JSONDecodeError:
                raise SynthesisError(f"{sid}: CLI response was not JSON; raw result preserved") from None
            models = recursive_values(response, {"model", "model_id", "resolved_model"})
            voices = recursive_values(response, {"voice", "voice_id", "resolved_voice"})
            if models != [SETTINGS["effective_model"]] or voices != [SETTINGS["voice"]]:
                raise SynthesisError(f"NEEDS_SOL: {sid} reported model/voice {models}/{voices}; raw result preserved, no fallback selected")
            pcm_meta = effective_wav(raw_path, canonical_path)
            temp_cue = cue_path.with_name(cue_path.stem + ".tmp.wav")
            run_checked([
                ffmpeg, "-v", "error", "-xerror", "-y", "-i", str(canonical_path), "-ar", "48000", "-ac", "1",
                "-c:a", "pcm_s16le", str(temp_cue),
            ], f"{sid} local 48 kHz conversion")
            try:
                with wave.open(str(temp_cue), "rb") as wav:
                    cue_params = wav.getparams()
                    cue_samples = cue_params.nframes
                    cue_payload = wav.readframes(cue_samples)
                if (cue_params.framerate, cue_params.nchannels, cue_params.sampwidth, cue_params.comptype) != (48_000, 1, 2, "NONE") or len(cue_payload) != cue_samples * 2:
                    raise SynthesisError(f"{sid}: converted cue is not complete 48 kHz mono PCM16")
                active = __import__("array").array("h")
                active.frombytes(cue_payload)
                peak = max((abs(value) for value in active), default=0)
                if peak == 0:
                    raise SynthesisError(f"{sid}: provider returned digital silence")
                temp_cue.replace(cue_path)
            except BaseException:
                temp_cue.unlink(missing_ok=True)
                raise
            window_samples = (segment["endFrame"] - segment["startFrame"]) * 800
            entry = {
                "cache_key": key,
                "tts_phonetic_text": segment["tts_phonetic_text"],
                "settings": SETTINGS,
                "actual_samples_24k": pcm_meta["actualSamples24k"],
                "actual_samples_48k": cue_samples,
                "duration_seconds": cue_samples / 48_000,
                "fitsDeclaredWindowBeforeOnsetAdjustment": cue_samples <= window_samples,
                "declaredWindowSamples": window_samples,
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
            prior = manifest["segments"].get(sid)
            if prior:
                manifest.setdefault("cacheHistory", []).append({"id": sid, **prior})
            manifest["segments"][sid] = entry
            manifest["authorization"] = {
                "manifest": "project/audio-authorization.json",
                "sha256AtInvocation": auth_hash,
                "scope": AUTHORIZATION_CONTRACT["scope"],
                "source": AUTHORIZATION_CONTRACT["source"],
                "note": "Current EP07 authorization only; no EP05 consent is inherited.",
            }
            write_json(manifest_path, manifest)
            print(json.dumps({
                "segment": sid,
                "durationSeconds": round(cue_samples / 48_000, 6),
                "windowSeconds": (segment["endFrame"] - segment["startFrame"]) / 60,
                "effectiveModel": models,
                "effectiveVoice": voices,
                "verifiedPcmOverflowRepair": pcm_meta["verifiedPcmOverflowRepair"],
            }, ensure_ascii=False))
            if cue_samples > window_samples and not args.collect_unfitted:
                raise SynthesisError(f"NEEDS_SOL: {sid} cue has {cue_samples} samples for a {window_samples}-sample window; verified cache metadata was retained, with no acceleration or truncation")
        return 0
    except (SynthesisError, OSError, ValueError, wave.Error, subprocess.SubprocessError) as exc:
        print(f"synthesize.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
