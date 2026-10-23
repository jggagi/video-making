#!/usr/bin/env python3
"""EP18 v04 narration synthesis and deterministic 90-second audio assembly.

The synthesis path keeps provider WAVs immutable, verifies their PCM payload,
and writes a separate canonical mono 48 kHz cue.  ``mix`` verifies cue identity
against the current segment text before assembling the independent stems.
Adapted from the verified v03 implementation; synthesis settings, event mapping,
and sound design are read from this v04 project.
"""

from __future__ import annotations

import argparse
import array
import hashlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PROJECT = Path(__file__).resolve().parents[1]
DELIVERY = PROJECT.parent
REVIEW = DELIVERY / "review"
AUDIO = PROJECT / "public" / "audio"
BL = Path("/Users/guoq/.local/n/bin/bl")
EXPECTED_MODEL = "qwen-audio-3.0-tts-plus"
VOICE = "qwen-audio-3.0-tts-plus-longlangmoyue"
FPS = 60
SAMPLE_RATE = 48_000
SAMPLES_PER_FRAME = SAMPLE_RATE // FPS
TOTAL_FRAMES = 5_400
TOTAL_SAMPLES = TOTAL_FRAMES * SAMPLES_PER_FRAME
SILENCE_START_FRAME = 4_500
SILENCE_END_FRAME = 4_530
SILENCE_START_SAMPLE = SILENCE_START_FRAME * SAMPLES_PER_FRAME
SILENCE_END_SAMPLE = SILENCE_END_FRAME * SAMPLES_PER_FRAME
ACTIVE_THRESHOLD = 32  # PCM16 ~= -60 dBFS; used only to report active bounds.
LOUDNESS_TARGET_LUFS = -16.0
LOUDNESS_TOLERANCE_LU = 0.15
LOUDNESS_CORRECTION_MAX_PASSES = 2
LOUDNESS_CORRECTION_MAX_GAIN_DB = 2.0
CORRECTION_LIMIT_LINEAR = 10 ** (-1.4 / 20.0)

EXPECTED_EVENT_FRAMES = {
    "underwater-heart": 60,
    "delete-to-gold": 840,
    "phase-lock": 1500,
    "warm-unison": 2220,
    "crossroads-clock": 2940,
    "subcurrent-surge": 3660,
    "confirm-impact": 3900,
    "ice-glass": 4200,
    "absolute-silence": 4500,
    "double-heartbeat": 4530,
}


class PipelineError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_segments() -> list[dict[str, Any]]:
    name = "segments.json"
    path = PROJECT / name
    rows = read_json(path)
    if not isinstance(rows, list):
        raise PipelineError(f"{name} must contain a JSON array")
    seen: set[str] = set()
    for item in rows:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise PipelineError(f"Invalid segment entry in {name}")
        if item["id"] in seen:
            raise PipelineError(f"Duplicate segment id {item['id']} in {name}")
        seen.add(item["id"])
        for key in ("startFrame", "endFrame"):
            if not isinstance(item.get(key), int) or item[key] < 0:
                raise PipelineError(f"Invalid {key} for {item['id']}")
        if item["endFrame"] <= item["startFrame"]:
            raise PipelineError(f"Empty frame window for {item['id']}")
        if not isinstance(item.get("tts_phonetic_text"), str) or not item["tts_phonetic_text"].strip():
            raise PipelineError(f"Missing tts_phonetic_text for {item['id']}")
    return rows


def load_synthesis_settings() -> dict[str, Any]:
    plan = read_json(PROJECT / "audio-plan.json")
    if not isinstance(plan, dict):
        raise PipelineError("audio-plan.json must contain an object")
    if plan.get("model") != EXPECTED_MODEL or plan.get("voice") != VOICE:
        raise PipelineError("audio-plan.json model or voice differs from the authorized v04 selection")
    rate = plan.get("rate")
    instruction = plan.get("instruction")
    if not isinstance(rate, (int, float)) or isinstance(rate, bool) or not math.isfinite(rate) or rate <= 0:
        raise PipelineError("audio-plan.json rate must be a positive finite number")
    if not isinstance(instruction, str) or not instruction.strip():
        raise PipelineError("audio-plan.json instruction is missing")
    if plan.get("format") != "wav" or plan.get("sample_rate") != 24_000:
        raise PipelineError("audio-plan.json must request 24 kHz WAV")
    return {
        "provider": "Aliyun Bailian",
        "requestedModel": EXPECTED_MODEL,
        "expectedEffectiveModel": EXPECTED_MODEL,
        "voice": VOICE,
        "rate": float(rate),
        "instruction": instruction,
        "format": "wav",
        "sampleRate": 24_000,
        "language": "zh",
        "concurrent": 1,
    }


def required_tmp_dir() -> Path:
    value = os.environ.get("TMPDIR")
    if not value:
        raise PipelineError("TMPDIR must point to the agent-dev temporary directory for audio intermediates")
    path = Path(value)
    if not path.is_dir():
        raise PipelineError("TMPDIR is not an available directory; use agent-dev run for this audio job")
    return path


def _walk_key_values(value: Any, wanted: set[str], path: str = "$") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            child_path = f"{path}.{key}"
            if normalized in wanted and isinstance(child, str):
                found.append((child_path, child))
            found.extend(_walk_key_values(child, wanted, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_walk_key_values(child, wanted, f"{path}[{index}]"))
    return found


def extract_returned_identity(response: Any) -> tuple[str | None, str | None, dict[str, list[str]]]:
    model_keys = {"model", "modelid", "actualmodel", "actualmodelid", "effectivemodel", "effectivemodelid"}
    voice_keys = {"voice", "voiceid", "actualvoice", "actualvoiceid", "voiceidentity", "speakerid"}
    models = _walk_key_values(response, model_keys)
    voices = _walk_key_values(response, voice_keys)
    model_values = sorted({value for _, value in models})
    voice_values = sorted({value for _, value in voices})
    evidence = {
        "modelPaths": [path for path, _ in models],
        "voicePaths": [path for path, _ in voices],
    }
    return (model_values[0] if len(model_values) == 1 else None,
            voice_values[0] if len(voice_values) == 1 else None,
            evidence)


def provider_error_type(stdout: str) -> str | None:
    try:
        response = json.loads(stdout)
    except Exception:
        return None
    entries = _walk_key_values(response, {"type", "errortype", "code", "errorcode"})
    for _, value in entries:
        if re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", value):
            return value
    return None


def sanitized_network_summary(exit_code: int, stderr: str) -> tuple[str, str, str]:
    lower = stderr.lower()
    if exit_code == 6:
        if "eai_again" in lower or "enotfound" in lower or "getaddrinfo" in lower:
            message = "DNS resolution failed"
        elif "certificate" in lower or "tls" in lower or "ssl" in lower:
            message = "TLS connection failed"
        elif "proxy" in lower:
            message = "proxy or network route failed"
        elif "econnrefused" in lower or "connection refused" in lower:
            message = "connection was refused"
        elif "timeout" in lower or "timed out" in lower:
            message = "network request timed out"
        else:
            message = "network request failed; non-allowlisted detail withheld"
        return "NETWORK", message, f"exit={exit_code}; {message}"
    known = {
        2: ("USAGE", "provider command rejected its arguments"),
        3: ("AUTH", "provider authentication failed"),
        4: ("QUOTA", "provider quota or rate limit reported"),
        5: ("TIMEOUT", "network request timed out"),
        10: ("CONTENT_FILTER", "provider content filter blocked the request"),
    }
    error_type, message = known.get(exit_code, ("PROVIDER_FAILURE", "provider command failed; details withheld"))
    return error_type, message, f"exit={exit_code}; {message}"


def pcm_wav_payload(path: Path) -> dict[str, Any]:
    """Strictly inspect a RIFF PCM WAV and use only physically present, aligned bytes."""
    raw = path.read_bytes()
    if len(raw) < 12 or raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise PipelineError(f"{path.name}: not a little-endian RIFF/WAVE file")
    riff_declared = struct.unpack_from("<I", raw, 4)[0] + 8
    offset = 12
    fmt: dict[str, int] | None = None
    data_payload: bytes | None = None
    data_declared: int | None = None
    data_offset: int | None = None
    while offset + 8 <= len(raw):
        tag = raw[offset:offset + 4]
        chunk_size = struct.unpack_from("<I", raw, offset + 4)[0]
        start = offset + 8
        available = max(0, len(raw) - start)
        if tag == b"fmt ":
            if chunk_size > available or chunk_size < 16:
                raise PipelineError(f"{path.name}: invalid or incomplete fmt chunk")
            code, channels, rate, byte_rate, block_align, bits = struct.unpack_from("<HHIIHH", raw, start)
            fmt = {
                "formatCode": code,
                "channels": channels,
                "sampleRate": rate,
                "byteRate": byte_rate,
                "blockAlign": block_align,
                "bitsPerSample": bits,
            }
        elif tag == b"data":
            data_declared = chunk_size
            data_offset = start
            physical = min(chunk_size, available)
            data_payload = raw[start:start + physical]
            break
        else:
            if chunk_size > available:
                raise PipelineError(f"{path.name}: incomplete {tag!r} chunk before data")
        offset = start + chunk_size + (chunk_size & 1)
    if fmt is None or data_payload is None or data_declared is None or data_offset is None:
        raise PipelineError(f"{path.name}: missing fmt or data chunk")
    if fmt["formatCode"] != 1:
        raise PipelineError(f"{path.name}: expected integer PCM format code 1")
    if fmt["channels"] < 1 or fmt["sampleRate"] < 1 or fmt["bitsPerSample"] not in (8, 16, 24, 32):
        raise PipelineError(f"{path.name}: unsupported PCM channel/rate/bit-depth")
    sample_width = fmt["bitsPerSample"] // 8
    expected_align = fmt["channels"] * sample_width
    if fmt["blockAlign"] != expected_align or fmt["byteRate"] != fmt["sampleRate"] * expected_align:
        raise PipelineError(f"{path.name}: inconsistent PCM byteRate/blockAlign")
    if not data_payload or len(data_payload) % expected_align:
        raise PipelineError(f"{path.name}: physical PCM payload is empty or not byte-aligned")
    data_payload_end = data_offset + data_declared
    data_chunk_end = data_payload_end + (data_declared & 1)
    trailing_bytes = max(0, len(raw) - data_chunk_end)
    physical_payload_end = data_offset + len(data_payload)
    physical_chunk_end = physical_payload_end + (len(data_payload) & 1)
    header_mismatch = (riff_declared != len(raw) or data_declared != len(data_payload))
    streaming_header_repair_eligible = (
        riff_declared > len(raw)
        and data_declared > len(data_payload)
        and riff_declared == data_offset + data_declared
        and physical_chunk_end == len(raw)
        and len(data_payload) % expected_align == 0
    )
    return {
        **fmt,
        "sampleWidthBytes": sample_width,
        "payload": data_payload,
        "sampleFrames": len(data_payload) // expected_align,
        "physicalBytes": len(raw),
        "riffDeclaredBytes": riff_declared,
        "dataOffset": data_offset,
        "dataDeclaredBytes": data_declared,
        "dataPhysicalBytes": len(data_payload),
        "dataTrailingBytes": trailing_bytes,
        "physicalPayloadEnd": physical_payload_end,
        "payloadSha256": sha256_bytes(data_payload),
        "headerMismatch": header_mismatch,
        "streamingHeaderRepairEligible": streaming_header_repair_eligible,
    }


def write_pcm_wav(path: Path, payload: bytes, channels: int, rate: int, width: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(width)
        out.setframerate(rate)
        out.writeframes(payload)


def active_bounds(payload: bytes, sample_count: int) -> tuple[int | None, int | None]:
    samples = array.array("h")
    samples.frombytes(payload)
    if sys.byteorder != "little":
        samples.byteswap()
    active = [index for index, sample in enumerate(samples) if abs(sample) > ACTIVE_THRESHOLD]
    return (active[0], active[-1] + 1) if active else (None, None)


def stable_cache_key(text: str, settings: dict[str, Any]) -> str:
    material = {"spokenText": text, **settings}
    return sha256_bytes(json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def settings_sha256(settings: dict[str, Any]) -> str:
    return sha256_bytes(json.dumps(settings, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def identity_sidecar_path(raw_path: Path) -> Path:
    return raw_path.with_suffix(".identity.json")


def load_verified_identity_sidecar(sidecar_path: Path, raw_path: Path, cache_key: str,
                                   text_sha256: str, settings: dict[str, Any]) -> dict[str, str]:
    if not sidecar_path.is_file():
        raise PipelineError(f"Raw WAV exists without its verified identity sidecar: {raw_path.name}")
    sidecar = read_json(sidecar_path)
    expected_fields = {
        "schemaVersion", "cacheKey", "textSha256", "settingsSha256", "actualModel",
        "actualVoice", "rawSha256", "identityVerifiedAt",
    }
    if not isinstance(sidecar, dict) or set(sidecar) != expected_fields:
        raise PipelineError(f"Identity sidecar has an invalid allowlisted schema: {sidecar_path.name}")
    if (sidecar.get("schemaVersion") != 1
            or sidecar.get("cacheKey") != cache_key
            or sidecar.get("textSha256") != text_sha256
            or sidecar.get("settingsSha256") != settings_sha256(settings)
            or sidecar.get("actualModel") != EXPECTED_MODEL
            or sidecar.get("actualVoice") != VOICE):
        raise PipelineError(f"Identity sidecar does not match the current cue/settings: {sidecar_path.name}")
    if not raw_path.is_file() or sha256_file(raw_path) != sidecar.get("rawSha256"):
        raise PipelineError(f"Identity sidecar raw WAV hash mismatch: {raw_path.name}")
    return {"actualModel": EXPECTED_MODEL, "actualVoice": VOICE, "rawSha256": sidecar["rawSha256"]}


def manifest_path() -> Path:
    return REVIEW / "audio-synthesis.json"


def existing_manifest() -> dict[str, Any]:
    path = manifest_path()
    if not path.exists():
        return {"schemaVersion": 1, "source": "segments.json", "cues": []}
    doc = read_json(path)
    if not isinstance(doc, dict) or not isinstance(doc.get("cues"), list):
        raise PipelineError(f"Invalid existing manifest {path.name}")
    return doc


def find_cached_cue(cache_key: str, expected_text_sha256: str,
                    settings: dict[str, Any]) -> dict[str, Any] | None:
    path = manifest_path()
    if not path.exists():
        return None
    doc = read_json(path)
    for cue in doc.get("cues", []):
        if cue.get("cacheKey") != cache_key:
            continue
        if cue.get("actualModel") != EXPECTED_MODEL or cue.get("actualVoice") != VOICE:
            raise PipelineError("A matching cache key has a divergent provider identity; refusing reuse")
        if cue.get("textSha256") != expected_text_sha256:
            raise PipelineError("A matching cache key has a divergent spoken-text hash; refusing reuse")
        canonical = PROJECT / cue.get("canonicalAudioFile", "")
        raw = PROJECT / cue.get("rawAudioFile", "")
        identity_sidecar = PROJECT / cue.get("identitySidecarFile", "")
        if not canonical.is_file() or sha256_file(canonical) != cue.get("canonicalSha256"):
            raise PipelineError("A matching synthesis cache has a missing or divergent canonical WAV; refusing reuse")
        if not raw.is_file() or sha256_file(raw) != cue.get("rawSha256"):
            raise PipelineError("A matching synthesis cache has a missing or divergent provider WAV; refusing reuse")
        if not identity_sidecar.is_file() or sha256_file(identity_sidecar) != cue.get("identitySidecarSha256"):
            raise PipelineError("A matching synthesis cache has a missing or divergent identity sidecar; refusing reuse")
        load_verified_identity_sidecar(identity_sidecar, raw, cache_key, expected_text_sha256, settings)
        return cue
    return None


def run_provider_synthesis(text_file: Path, raw_path: Path, settings: dict[str, Any], cache_key: str,
                           text_sha256: str, verbose: bool = False) -> dict[str, str]:
    args = [
        str(BL), "speech", "synthesize",
        "--model", EXPECTED_MODEL,
        "--voice", VOICE,
        "--rate", str(settings["rate"]),
        "--instruction", settings["instruction"],
        "--language", "zh",
        "--format", "wav",
        "--sample-rate", "24000",
        "--concurrent", "1",
        "--text-file", str(text_file),
        "--out", str(raw_path),
        "--output", "json",
    ]
    if verbose:
        args.append("--verbose")
    if not BL.is_file():
        raise PipelineError(f"Configured Bailian CLI path is unavailable: {BL}")
    env = os.environ.copy()
    env.update({
        "BAILIAN_CALLER_TYPE": "agent",
        "BAILIAN_CALLER_NAME": "codex",
        "BAILIAN_SKILL_NAME": "bailian-gen",
        "BAILIAN_SKILL_VERSION": "2.5.1",
    })
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False, env=env)
    try:
        response = json.loads(proc.stdout)
    except Exception as exc:
        error_type, safe_message, safe_tail = sanitized_network_summary(proc.returncode, proc.stderr)
        raise PipelineError(
            f"Synthesis returned non-JSON output ({error_type}, {safe_message}; sanitized stderr tail: {safe_tail}); "
            "response was not retained"
        ) from exc
    if proc.returncode != 0:
        error_type = provider_error_type(proc.stdout)
        safe_type, safe_message, safe_tail = sanitized_network_summary(proc.returncode, proc.stderr)
        raise PipelineError(
            f"Synthesis failed (exit {proc.returncode}, provider error type {error_type or safe_type}: {safe_message}; "
            f"sanitized stderr tail: {safe_tail}); raw output was not retained"
        )
    model, voice, _evidence = extract_returned_identity(response)
    if model != EXPECTED_MODEL or voice != VOICE:
        safe_model = model if model and re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", model) else None
        safe_voice = voice if voice and re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", voice) else None
        raise PipelineError(
            "Returned provider identity did not verify; "
            f"actualModel={safe_model!r}, actualVoice={safe_voice!r}. "
            "Response was not retained and no canonical cue was written."
        )
    if not raw_path.is_file() or raw_path.stat().st_size == 0:
        raise PipelineError("Provider returned success without a non-empty WAV file")
    identity_path = identity_sidecar_path(raw_path)
    if identity_path.exists():
        raise PipelineError("Identity sidecar already exists without a matching verified cache; refusing overwrite")
    identity = {
        "schemaVersion": 1,
        "cacheKey": cache_key,
        "textSha256": text_sha256,
        "settingsSha256": settings_sha256(settings),
        "actualModel": model,
        "actualVoice": voice,
        "rawSha256": sha256_file(raw_path),
        "identityVerifiedAt": now_iso(),
    }
    # Persist only allowlisted identity and integrity fields before parsing the WAV.
    write_json(identity_path, identity)
    return {"actualModel": model, "actualVoice": voice, "rawSha256": identity["rawSha256"]}


def frame_for_sample_ceil(sample: int) -> int:
    return (sample * FPS + SAMPLE_RATE - 1) // SAMPLE_RATE


def cue_window_fields(segment: dict[str, Any], active_start: int | None, active_end: int | None,
                      canonical_sample_count: int | None = None) -> dict[str, Any]:
    anchor = segment["startFrame"]
    end = segment["endFrame"]
    start_frame = None if active_start is None else anchor + active_start * FPS // SAMPLE_RATE
    end_frame = None if active_end is None else anchor + frame_for_sample_ceil(active_end)
    window_samples = (end - anchor) * SAMPLES_PER_FRAME
    return {
        "placementStartFrameForFit": anchor,
        "windowEndFrame": end,
        "windowSeconds": (end - anchor) / FPS,
        "canonicalSampleCount": canonical_sample_count,
        "windowSampleCapacity": window_samples,
        "fitsFullCanonicalWindowWithoutTrimOrSpeedChange": (
            canonical_sample_count is None or canonical_sample_count <= window_samples
        ),
        "activeStartFrame": start_frame,
        "activeEndFrameExclusive": end_frame,
        "activeDurationSeconds": 0 if active_start is None or active_end is None else (active_end - active_start) / SAMPLE_RATE,
        "fitsOriginalWindowWithoutTrimOrSpeedChange": end_frame is None or end_frame <= end,
    }


def synthesize(ids: list[str], verbose: bool = False) -> list[dict[str, Any]]:
    settings = load_synthesis_settings()
    tmp_root = required_tmp_dir()
    rows = load_segments()
    by_id = {row["id"]: row for row in rows}
    missing = [segment_id for segment_id in ids if segment_id not in by_id]
    if missing:
        raise PipelineError(f"Unknown segment ids: {', '.join(missing)}")
    AUDIO.mkdir(parents=True, exist_ok=True)
    text_dir = AUDIO / "text"
    raw_dir = AUDIO / "history" / "raw"
    text_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    canonical_dir = AUDIO / "voice"
    canonical_dir.mkdir(parents=True, exist_ok=True)
    manifest = existing_manifest()
    results: list[dict[str, Any]] = []
    for segment_id in ids:
        segment = by_id[segment_id]
        text = segment["tts_phonetic_text"]
        text_sha256 = sha256_bytes(text.encode("utf-8"))
        cache_key = stable_cache_key(text, settings)
        cached = find_cached_cue(cache_key, text_sha256, settings)
        if cached:
            cue = dict(cached)
            cue["id"] = segment_id
            cue["cacheReuse"] = True
            cue["sourceSegmentFile"] = "segments.json"
            cue["sourceStartFrame"] = segment["startFrame"]
            cue["sourceEndFrame"] = segment["endFrame"]
            cue.update(cue_window_fields(segment, cue.get("activeStartSample"), cue.get("activeEndSampleExclusive"), cue.get("sampleCount")))
            manifest["cues"] = [c for c in manifest["cues"] if c.get("id") != segment_id]
            manifest["cues"].append(cue)
            manifest["settings"] = settings
            manifest["updatedAt"] = now_iso()
            write_json(manifest_path(), manifest)
            results.append(cue)
            continue
        text_path = text_dir / f"{segment_id}-{cache_key[:12]}.txt"
        if text_path.exists() and text_path.read_text(encoding="utf-8") != text:
            raise PipelineError(f"Refusing to overwrite divergent text file {text_path.name}")
        if not text_path.exists():
            text_path.write_text(text, encoding="utf-8")
        raw_path = raw_dir / f"{cache_key}.wav"
        identity_path = identity_sidecar_path(raw_path)
        if raw_path.exists():
            identity = load_verified_identity_sidecar(identity_path, raw_path, cache_key, text_sha256, settings)
        else:
            if identity_path.exists():
                raise PipelineError(f"Identity sidecar exists without its raw provider WAV: {identity_path.name}")
            identity = run_provider_synthesis(text_path, raw_path, settings, cache_key, text_sha256, verbose)
        raw_info = pcm_wav_payload(raw_path)
        if raw_info["sampleRate"] != 24_000 or raw_info["channels"] != 1:
            raise PipelineError(
                f"Provider WAV format mismatch: rate={raw_info['sampleRate']}, channels={raw_info['channels']}; raw WAV retained"
            )
        if raw_info["headerMismatch"] and not raw_info["streamingHeaderRepairEligible"]:
            raise PipelineError(
                "Provider WAV header mismatch is not the verified oversized streaming form; "
                f"raw WAV retained (riffDeclaredBytes={raw_info['riffDeclaredBytes']}, "
                f"dataOffset={raw_info['dataOffset']}, dataDeclaredBytes={raw_info['dataDeclaredBytes']}, "
                f"dataPhysicalBytes={raw_info['dataPhysicalBytes']}, physicalBytes={raw_info['physicalBytes']}, "
                f"dataTrailingBytes={raw_info['dataTrailingBytes']}, payloadSha256={raw_info['payloadSha256']})"
            )
        if raw_info["dataTrailingBytes"] != 0 or raw_info["physicalPayloadEnd"] + (raw_info["dataPhysicalBytes"] & 1) != raw_info["physicalBytes"]:
            raise PipelineError("Provider WAV contains ambiguous trailing bytes; raw WAV retained without header repair")
        repaired_temp: Path | None = None
        source_for_ffmpeg = raw_path
        if raw_info["headerMismatch"]:
            fd, temp_name = tempfile.mkstemp(prefix="si-ep18-sovereign-subcurrent-v04-repaired-", suffix=".wav", dir=tmp_root)
            os.close(fd)
            repaired_temp = Path(temp_name)
            write_pcm_wav(repaired_temp, raw_info["payload"], raw_info["channels"], raw_info["sampleRate"], raw_info["sampleWidthBytes"])
            checked = pcm_wav_payload(repaired_temp)
            if (checked["headerMismatch"] or checked["sampleFrames"] != raw_info["sampleFrames"]
                    or checked["payloadSha256"] != raw_info["payloadSha256"]):
                repaired_temp.unlink(missing_ok=True)
                raise PipelineError("Validated WAV header repair failed; original provider WAV was retained")
            source_for_ffmpeg = repaired_temp
        canonical_path = canonical_dir / f"{segment_id}-{cache_key[:12]}.wav"
        if canonical_path.exists():
            if repaired_temp:
                repaired_temp.unlink(missing_ok=True)
            raise PipelineError(f"Canonical output already exists without a matching cache record: {canonical_path.name}")
        fd, canonical_temp_name = tempfile.mkstemp(prefix=f"si-ep18-sovereign-subcurrent-v04-{segment_id}-", suffix=".wav", dir=tmp_root)
        os.close(fd)
        Path(canonical_temp_name).unlink(missing_ok=True)
        canonical_temp = Path(canonical_temp_name)
        publish_temp: Path | None = None
        try:
            proc = subprocess.run(
                ["/opt/homebrew/bin/ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-n", "-i", str(source_for_ffmpeg),
                 "-map", "0:a:0", "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(canonical_temp)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
            )
            if proc.returncode != 0 or not canonical_temp.is_file():
                raise PipelineError(f"Canonical resampling failed (ffmpeg exit {proc.returncode}); raw WAV retained")
            canonical_info = pcm_wav_payload(canonical_temp)
            if (canonical_info["sampleRate"], canonical_info["channels"], canonical_info["bitsPerSample"]) != (SAMPLE_RATE, 1, 16):
                raise PipelineError("Canonical WAV is not mono 48 kHz PCM16")
            active_start, active_end = active_bounds(canonical_info["payload"], canonical_info["sampleFrames"])
            fit_fields = cue_window_fields(segment, active_start, active_end, canonical_info["sampleFrames"])
            fd, publish_name = tempfile.mkstemp(prefix=f".{segment_id}-publish-", suffix=".wav", dir=canonical_dir)
            os.close(fd)
            publish_temp = Path(publish_name)
            shutil.copyfile(canonical_temp, publish_temp)
            published_info = pcm_wav_payload(publish_temp)
            if (published_info["sampleRate"], published_info["channels"], published_info["bitsPerSample"], published_info["sampleFrames"]) != (SAMPLE_RATE, 1, 16, canonical_info["sampleFrames"]):
                raise PipelineError("Canonical cue changed format or sample count while publishing")
            os.replace(publish_temp, canonical_path)
        finally:
            canonical_temp.unlink(missing_ok=True)
            if publish_temp:
                publish_temp.unlink(missing_ok=True)
            if repaired_temp:
                repaired_temp.unlink(missing_ok=True)
        cue = {
            "id": segment_id,
            "spokenText": text,
            "sourceSegmentFile": "segments.json",
            "sourceStartFrame": segment["startFrame"],
            "sourceEndFrame": segment["endFrame"],
            **fit_fields,
            "provider": settings["provider"],
            "settings": settings,
            "requestedModel": EXPECTED_MODEL,
            "actualModel": identity["actualModel"],
            "voice": VOICE,
            "actualVoice": identity["actualVoice"],
            "rate": settings["rate"],
            "formatRequested": "wav",
            "providerSampleRate": raw_info["sampleRate"],
            "providerChannels": raw_info["channels"],
            "providerBitsPerSample": raw_info["bitsPerSample"],
            "rawAudioFile": str(raw_path.relative_to(PROJECT)),
            "rawSha256": identity["rawSha256"],
            "rawSampleCount": raw_info["sampleFrames"],
            "rawDurationSeconds": raw_info["sampleFrames"] / raw_info["sampleRate"],
            "rawHeaderMismatchRepairedForCanonical": raw_info["headerMismatch"],
            "rawWavHeader": {
                "physicalBytes": raw_info["physicalBytes"],
                "riffDeclaredBytes": raw_info["riffDeclaredBytes"],
                "dataOffset": raw_info["dataOffset"],
                "dataDeclaredBytes": raw_info["dataDeclaredBytes"],
                "dataPhysicalBytes": raw_info["dataPhysicalBytes"],
                "dataTrailingBytes": raw_info["dataTrailingBytes"],
                "payloadSha256": raw_info["payloadSha256"],
                "headerMismatch": raw_info["headerMismatch"],
                "streamingHeaderRepairEligible": raw_info["streamingHeaderRepairEligible"],
            },
            "identitySidecarFile": str(identity_path.relative_to(PROJECT)),
            "identitySidecarSha256": sha256_file(identity_path),
            "canonicalAudioFile": str(canonical_path.relative_to(PROJECT)),
            "canonicalSha256": sha256_file(canonical_path),
            "sampleRate": canonical_info["sampleRate"],
            "channels": canonical_info["channels"],
            "bitsPerSample": canonical_info["bitsPerSample"],
            "sampleCount": canonical_info["sampleFrames"],
            "durationSeconds": canonical_info["sampleFrames"] / canonical_info["sampleRate"],
            "activeThresholdPcm16": ACTIVE_THRESHOLD,
            "activeStartSample": active_start,
            "activeEndSampleExclusive": active_end,
            "cacheKey": cache_key,
            "textFile": str(text_path.relative_to(PROJECT)),
            "textSha256": text_sha256,
            "cacheReuse": False,
            "generatedAt": now_iso(),
        }
        manifest["schemaVersion"] = 1
        manifest["source"] = "segments.json"
        manifest["settings"] = settings
        manifest["cues"] = [c for c in manifest["cues"] if c.get("id") != segment_id]
        manifest["cues"].append(cue)
        manifest["updatedAt"] = now_iso()
        write_json(manifest_path(), manifest)
        results.append(cue)
    return results


def _active_bounds_array(samples: array.array) -> tuple[int | None, int | None]:
    first: int | None = None
    last: int | None = None
    for index, sample in enumerate(samples):
        if abs(sample) > ACTIVE_THRESHOLD:
            if first is None:
                first = index
            last = index + 1
    return first, last


def _read_mono_pcm16(path: Path, expected_rate: int = SAMPLE_RATE) -> array.array:
    info = pcm_wav_payload(path)
    if (info["formatCode"], info["channels"], info["sampleRate"], info["bitsPerSample"]) != (1, 1, expected_rate, 16):
        raise PipelineError(f"{path.name} must be mono {expected_rate} Hz PCM16")
    samples = array.array("h")
    samples.frombytes(info["payload"])
    if sys.byteorder != "little":
        samples.byteswap()
    return samples


def _write_stereo_pcm16(path: Path, mono: array.array) -> None:
    stereo = array.array("h")
    stereo.extend(sample for value in mono for sample in (value, value))
    if sys.byteorder != "little":
        stereo.byteswap()
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        out.writeframes(stereo.tobytes())


def _add_tone(buffer: array.array, start: int, duration: float, frequency: float, amplitude: float,
              decay: float = 5.5, harmonics: tuple[tuple[int, float], ...] = ((1, 1.0), (2, 0.28), (3, 0.12)),
              sweep_hz_per_second: float = 0.0, attack: float = 0.02, release: float = 0.12) -> None:
    count = min(int(duration * SAMPLE_RATE), len(buffer) - start)
    if count <= 0:
        return
    tau = 2.0 * math.pi
    attack_samples = max(1, int(attack * SAMPLE_RATE))
    release_samples = max(1, int(release * SAMPLE_RATE))
    for offset in range(count):
        t = offset / SAMPLE_RATE
        attack_phase = min(1.0, offset / attack_samples)
        release_phase = min(1.0, (count - 1 - offset) / release_samples)
        attack_env = 0.5 - 0.5 * math.cos(math.pi * attack_phase)
        release_env = 0.5 - 0.5 * math.cos(math.pi * release_phase)
        envelope = attack_env * release_env * math.exp(-decay * t)
        phase_base = tau * (frequency * t + 0.5 * sweep_hz_per_second * t * t)
        value = 0.0
        for harmonic, weight in harmonics:
            value += weight * math.sin(phase_base * harmonic)
        buffer[start + offset] += amplitude * envelope * value


def _add_deterministic_transient(buffer: array.array, start: int, duration: float, amplitude: float,
                                frequencies: tuple[float, ...], decay: float = 12.0,
                                attack: float = 0.001, release: float = 0.08) -> None:
    """Create a repeatable, non-random inharmonic transient from fixed partials."""
    count = min(int(duration * SAMPLE_RATE), len(buffer) - start)
    if count <= 0:
        return
    attack_samples = max(1, int(attack * SAMPLE_RATE))
    release_samples = max(1, int(release * SAMPLE_RATE))
    normalizer = max(1, len(frequencies))
    for offset in range(count):
        t = offset / SAMPLE_RATE
        attack_phase = min(1.0, offset / attack_samples)
        release_phase = min(1.0, (count - 1 - offset) / release_samples)
        envelope = ((0.5 - 0.5 * math.cos(math.pi * attack_phase))
                    * (0.5 - 0.5 * math.cos(math.pi * release_phase))
                    * math.exp(-decay * t))
        value = sum(math.sin(2.0 * math.pi * frequency * t) for frequency in frequencies) / normalizer
        buffer[start + offset] += amplitude * envelope * value


def _load_sfx_event_map() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    document = read_json(PROJECT / "sfx_events.json")
    if (not isinstance(document, dict) or document.get("fps") != FPS
            or document.get("sampleRate") != SAMPLE_RATE
            or document.get("samplesPerFrame") != SAMPLES_PER_FRAME):
        raise PipelineError("sfx_events.json must declare 60 fps, 48 kHz, and 800 samples per frame")
    events = document.get("events")
    if not isinstance(events, list):
        raise PipelineError("sfx_events.json events must be an array")
    by_id = {event.get("id"): event for event in events if isinstance(event, dict)}
    if len(events) != len(EXPECTED_EVENT_FRAMES) or len(by_id) != len(events) or set(by_id) != set(EXPECTED_EVENT_FRAMES):
        raise PipelineError("sfx_events.json event IDs differ from the approved v04 event plan")
    for event_id, frame in EXPECTED_EVENT_FRAMES.items():
        event = by_id[event_id]
        if event.get("frame") != frame or event.get("sampleIndex") != frame * SAMPLES_PER_FRAME:
            raise PipelineError(f"sfx_events.json frame/sample mapping is invalid for {event_id}")
    if document.get("silenceRangeFrames") != [SILENCE_START_FRAME, SILENCE_END_FRAME]:
        raise PipelineError("sfx_events.json absolute-silence frame range is invalid")
    if document.get("silenceRangeSamples") != [SILENCE_START_SAMPLE, SILENCE_END_SAMPLE]:
        raise PipelineError("sfx_events.json absolute-silence sample range is invalid")
    return by_id, document


def _add_deterministic_noise(buffer: array.array, start: int, duration: float, amplitude: float,
                            seed: int, attack: float = 0.02, release: float = 0.2,
                            decay: float = 0.0) -> None:
    count = min(int(duration * SAMPLE_RATE), len(buffer) - start)
    if count <= 0:
        return
    attack_samples = max(1, int(attack * SAMPLE_RATE))
    release_samples = max(1, int(release * SAMPLE_RATE))
    state = seed & 0xFFFFFFFF or 1
    for offset in range(count):
        state ^= (state << 13) & 0xFFFFFFFF
        state ^= state >> 17
        state ^= (state << 5) & 0xFFFFFFFF
        noise = (state / 0xFFFFFFFF) * 2.0 - 1.0
        attack_phase = min(1.0, offset / attack_samples)
        release_phase = min(1.0, (count - 1 - offset) / release_samples)
        envelope = ((0.5 - 0.5 * math.cos(math.pi * attack_phase))
                    * (0.5 - 0.5 * math.cos(math.pi * release_phase))
                    * math.exp(-decay * (offset / SAMPLE_RATE)))
        buffer[start + offset] += amplitude * envelope * noise


def _make_score(segments: list[dict[str, Any]]) -> array.array:
    """Build an evolving four-act score bed with an exact silent relay gap."""
    score = array.array("f", [0.0]) * TOTAL_SAMPLES
    acts = (
        (60, 1500, ((43.65, 0.010), (65.41, 0.007), (98.00, 0.003)), 2.2, 1.5),
        (1500, 2940, ((65.41, 0.009), (98.00, 0.007), (130.81, 0.004)), 1.8, 1.7),
        (2940, 3900, ((48.99, 0.010), (73.42, 0.007), (110.00, 0.004)), 1.0, 1.0),
        (3900, SILENCE_START_FRAME, ((55.00, 0.008), (82.41, 0.006), (123.47, 0.004), (392.00, 0.0015)), 1.2, 2.0),
    )
    for start_frame, end_frame, notes, attack, release in acts:
        start = start_frame * SAMPLES_PER_FRAME
        duration = (end_frame - start_frame) / FPS
        for frequency, amplitude in notes:
            _add_tone(score, start, duration, frequency, amplitude, decay=0.0,
                      harmonics=((1, 1.0), (2, 0.14)), attack=attack, release=release)
    # A faint post-gap low tone gives the final question a cold, unresolved tail.
    final_segment = next((segment for segment in segments if segment["id"] == "S08"), None)
    if final_segment is None or final_segment["endFrame"] <= SILENCE_END_FRAME:
        raise PipelineError("segments.json must give S08 a window after the absolute-silence gap")
    tail = SILENCE_END_SAMPLE
    tail_duration = (final_segment["endFrame"] - SILENCE_END_FRAME) / FPS
    _add_tone(score, tail, tail_duration, 55.0, 0.0035, decay=0.12,
              harmonics=((1, 1.0), (2, 0.08)), attack=0.4, release=3.0)
    for index in range(SILENCE_START_SAMPLE, SILENCE_END_SAMPLE):
        score[index] = 0.0
    return score


def _make_sfx(event_map: dict[str, dict[str, Any]]) -> array.array:
    sfx = array.array("f", [0.0]) * TOTAL_SAMPLES
    at = lambda event_id: int(event_map[event_id]["sampleIndex"])

    # Act 1: a restrained 55 BPM pulse anchors the memory details.
    heart = at("underwater-heart")
    beat_period = SAMPLE_RATE * 60.0 / 55.0
    for beat in range(12):
        beat_start = heart + int(round(beat * beat_period))
        for delay, level in ((0.0, 0.022), (0.18, 0.014)):
            _add_tone(sfx, beat_start + int(delay * SAMPLE_RATE), 0.34, 55.0, level,
                      decay=4.2, harmonics=((1, 1.0), (2, 0.12)), attack=0.012, release=0.2)
        if beat % 2 == 0:
            _add_tone(sfx, beat_start + int(0.52 * SAMPLE_RATE), 0.9, 1244.51, 0.003,
                      decay=2.8, harmonics=((1, 1.0), (2, 0.15)), attack=0.004, release=0.7)

    # Act 2 opening: delete-key clicks sink into small, muted gold chimes.
    gold = at("delete-to-gold")
    for delay in (0.0, 0.52, 1.04):
        click = gold + int(delay * SAMPLE_RATE)
        _add_deterministic_noise(sfx, click, 0.035, 0.022, 8401 + int(delay * 100), attack=0.0005, release=0.025, decay=20.0)
        _add_tone(sfx, click, 0.8, 987.77, 0.006, decay=1.2,
                  harmonics=((1, 1.0), (2, 0.24), (3, 0.08)), attack=0.003, release=0.7)
        _add_tone(sfx, click + int(0.14 * SAMPLE_RATE), 1.4, 1479.98, 0.0035,
                  decay=1.1, harmonics=((1, 1.0), (2, 0.12)), attack=0.01, release=1.2)

    # Two synthetic sine resonances converge around 1.5 kHz; no recorded voice.
    phase = at("phase-lock")
    _add_tone(sfx, phase, 3.2, 1500.0, 0.006, decay=0.18,
              harmonics=((1, 1.0),), attack=0.7, release=1.1)
    _add_tone(sfx, phase, 3.2, 1524.0, 0.006, decay=0.18,
              harmonics=((1, 1.0),), sweep_hz_per_second=-7.5, attack=0.7, release=1.1)
    _add_tone(sfx, phase, 3.2, 750.0, 0.002, decay=0.2,
              harmonics=((1, 1.0),), attack=0.8, release=1.1)

    # Act 2 warms into synthetic cello-like unison and low harmonics.
    warm = at("warm-unison")
    for delay, frequency, amplitude in ((0.0, 130.81, 0.008), (0.12, 196.00, 0.006), (0.28, 261.63, 0.0035)):
        _add_tone(sfx, warm + int(delay * SAMPLE_RATE), 4.4 - delay, frequency, amplitude,
                  decay=0.18, harmonics=((1, 1.0), (2, 0.26), (3, 0.09)), attack=0.55, release=1.6)

    # Act 3: escapement ticks and a restrained sub-bass pulse at the crossroads.
    clock = at("crossroads-clock")
    for tick in range(12):
        tick_start = clock + int(tick * 0.72 * SAMPLE_RATE)
        _add_deterministic_transient(sfx, tick_start, 0.075, 0.010, (740.0, 1110.0, 1480.0),
                                     decay=24.0, attack=0.0005, release=0.065)
        _add_tone(sfx, tick_start, 0.28, 49.0, 0.012, decay=8.0,
                  harmonics=((1, 1.0), (2, 0.08)), attack=0.01, release=0.2)

    # The low pulse rises, then a deterministic filtered-noise-like whoosh
    # and a short biometric lock click mark the confirm impact.
    surge = at("subcurrent-surge")
    _add_tone(sfx, surge, 4.0, 43.65, 0.011, decay=0.05,
              harmonics=((1, 1.0), (2, 0.12)), sweep_hz_per_second=16.0, attack=1.1, release=1.0)
    _add_deterministic_noise(sfx, surge, 4.4, 0.005, 3660, attack=1.4, release=1.0, decay=0.05)
    impact = at("confirm-impact")
    _add_deterministic_noise(sfx, impact, 0.72, 0.018, 3900, attack=0.002, release=0.55, decay=1.7)
    _add_deterministic_transient(sfx, impact + int(0.28 * SAMPLE_RATE), 0.18, 0.018,
                                 (72.0, 112.0, 840.0, 1680.0), decay=11.0,
                                 attack=0.001, release=0.15)

    # Act 4: a thin, inharmonic ice-glass harmonic and restrained noise shimmer.
    glass = at("ice-glass")
    for delay, frequency, amplitude in ((0.0, 1396.91, 0.0045), (0.32, 2093.0, 0.003), (0.78, 2793.83, 0.002)):
        _add_tone(sfx, glass + int(delay * SAMPLE_RATE), 3.2 - delay, frequency, amplitude,
                  decay=0.7, harmonics=((1, 1.0), (2, 0.08)), attack=0.03, release=2.3)
    _add_deterministic_noise(sfx, glass, 1.8, 0.0014, 4200, attack=0.12, release=1.2, decay=0.15)

    # The source-defined relay gap is silent in every stem. After it, two
    # distinct lub-dub pairs return with a metallic cyan resonance tail.
    for index in range(SILENCE_START_SAMPLE, SILENCE_END_SAMPLE):
        sfx[index] = 0.0
    after = at("double-heartbeat")
    for delay, level in ((0.0, 0.024), (0.18, 0.016), (0.76, 0.022), (0.94, 0.014)):
        _add_tone(sfx, after + int(delay * SAMPLE_RATE), 0.34, 55.0, level,
                  decay=4.3, harmonics=((1, 1.0), (2, 0.15)), attack=0.012, release=0.2)
    for delay, frequency, level in ((0.0, 392.0, 0.004), (0.24, 587.33, 0.0025), (0.55, 783.99, 0.0015)):
        _add_tone(sfx, after + int(delay * SAMPLE_RATE), 3.4 - delay, frequency, level,
                  decay=0.85, harmonics=((1, 1.0), (2, 0.22), (3, 0.08)), attack=0.02, release=2.4)
    return sfx


def _float_mono_to_stereo_wav(path: Path, samples: array.array) -> None:
    pcm = array.array("h")
    for value in samples:
        limited = max(-0.95, min(0.95, value))
        sample = int(round(limited * 32767.0))
        pcm.extend((sample, sample))
    if sys.byteorder != "little":
        pcm.byteswap()
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        out.writeframes(pcm.tobytes())


def _ffmpeg(args: list[str], failure: str) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if proc.returncode != 0:
        raise PipelineError(f"{failure} (ffmpeg exit {proc.returncode}); detailed output was not retained")
    return proc


def _parse_last_json(stderr: str) -> dict[str, Any]:
    starts = [match.start() for match in re.finditer(r"\{", stderr)]
    for start in reversed(starts):
        try:
            value, _ = json.JSONDecoder().raw_decode(stderr[start:])
            if isinstance(value, dict) and "input_i" in value:
                return value
        except Exception:
            continue
    raise PipelineError("Could not parse ffmpeg loudnorm first-pass measurements")


def _measure_ebu_r128(path: Path) -> dict[str, float]:
    proc = subprocess.run(
        ["/opt/homebrew/bin/ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
    )
    if proc.returncode != 0:
        raise PipelineError(f"Final EBU R128/true-peak measurement failed (ffmpeg exit {proc.returncode})")
    integrated = re.findall(r"^\s*I:\s*(-?(?:\d+(?:\.\d+)?|inf))\s*LUFS\s*$", proc.stderr, re.IGNORECASE | re.MULTILINE)
    # FFmpeg's summary prints a `True peak:` heading followed by `Peak:`.
    true_peak = re.findall(r"^\s*Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS\s*$", proc.stderr, re.IGNORECASE | re.MULTILINE)
    if not integrated or not true_peak:
        raise PipelineError("ffmpeg EBU R128 output did not include integrated loudness and true peak")
    try:
        integrated_lufs = float(integrated[-1])
        peak_dbfs = float(true_peak[-1])
    except ValueError as exc:
        raise PipelineError("ffmpeg EBU R128 output contained a non-finite integrated loudness") from exc
    if not math.isfinite(integrated_lufs) or not math.isfinite(peak_dbfs):
        raise PipelineError("ffmpeg EBU R128 output contained non-finite measurements")
    return {"integratedLufs": integrated_lufs, "truePeakDbtp": peak_dbfs}


def _mute_exact_silence_window(path: Path) -> None:
    """Force the required 30-frame window to exact PCM zero, then verify it."""
    info = pcm_wav_payload(path)
    if (info["channels"], info["sampleRate"], info["bitsPerSample"], info["sampleFrames"]) != (2, SAMPLE_RATE, 16, TOTAL_SAMPLES):
        raise PipelineError("Candidate must be exactly 90 seconds of stereo 48 kHz PCM16 before silence verification")
    payload = bytearray(info["payload"])
    start_byte = SILENCE_START_SAMPLE * 4
    end_byte = SILENCE_END_SAMPLE * 4
    payload[start_byte:end_byte] = bytes(end_byte - start_byte)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.stem}-silence-", suffix=".wav", dir=path.parent)
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        write_pcm_wav(temp_path, bytes(payload), 2, SAMPLE_RATE, 2)
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)
    checked = pcm_wav_payload(path)
    if any(checked["payload"][start_byte:end_byte]):
        raise PipelineError("Exact silence verification failed after loudness processing")


def _apply_gain_correction(source: Path, output: Path, gain_db: float) -> None:
    # Oversample before the true-peak limiter, then return to the canonical rate
    # with an exact frame count. Limiter gain compensation stays disabled.
    filter_chain = (
        "aresample=192000,"
        f"volume={gain_db:.8f}dB,"
        f"alimiter=limit={CORRECTION_LIMIT_LINEAR:.9f}:level=false:latency=true,"
        f"aresample={SAMPLE_RATE},apad=whole_len={TOTAL_SAMPLES},"
        f"atrim=end_sample={TOTAL_SAMPLES},asetpts=N/SR/TB"
    )
    _ffmpeg(
        ["/opt/homebrew/bin/ffmpeg", "-hide_banner", "-nostats", "-i", str(source),
         "-map", "0:a:0", "-af", filter_chain, "-ar", str(SAMPLE_RATE), "-ac", "2",
         "-c:a", "pcm_s16le", str(output)],
        "Post-normalization loudness correction failed",
    )
    info = pcm_wav_payload(output)
    if (info["channels"], info["sampleRate"], info["bitsPerSample"], info["sampleFrames"]) != (2, SAMPLE_RATE, 16, TOTAL_SAMPLES):
        raise PipelineError("Post-normalization correction changed the exact 90-second PCM frame count")


def _loudness_targets_pass(measurement: dict[str, float]) -> bool:
    return (
        abs(measurement["integratedLufs"] - LOUDNESS_TARGET_LUFS) <= LOUDNESS_TOLERANCE_LU
        and measurement["truePeakDbtp"] <= -1.0
    )


def _write_mix_measurement_failure(measurement: dict[str, float], corrections: list[dict[str, Any]]) -> None:
    write_json(REVIEW / "audio-mix-qa.json", {
        "schemaVersion": 1,
        "generatedAt": now_iso(),
        "status": "failed",
        "master": "public/audio/master.wav",
        "masterWritten": False,
        "targetLufs": LOUDNESS_TARGET_LUFS,
        "integratedLufsTolerance": {"target": LOUDNESS_TARGET_LUFS, "plusMinus": LOUDNESS_TOLERANCE_LU},
        "requiredMaximumTruePeakDbtp": -1.0,
        "measuredFinalIntegratedLufs": measurement["integratedLufs"],
        "measuredFinalTruePeakDbtp": measurement["truePeakDbtp"],
        "postGainCorrections": corrections,
        "correctionPolicy": {
            "maxPasses": LOUDNESS_CORRECTION_MAX_PASSES,
            "maxGainDbPerPass": LOUDNESS_CORRECTION_MAX_GAIN_DB,
            "limiterCeilingDbtp": -1.4,
        },
        "candidateRetained": False,
    })


def _write_mix_preflight_failure(failures: list[dict[str, Any]]) -> None:
    write_json(REVIEW / "audio-mix-qa.json", {
        "schemaVersion": 1,
        "generatedAt": now_iso(),
        "status": "preflight_failed",
        "failures": failures,
        "staleIdentityMismatches": failures,
        "masterWritten": False,
    })


def mix() -> dict[str, Any]:
    settings = load_synthesis_settings()
    tmp_root = required_tmp_dir()
    segments = load_segments()
    manifest_file = REVIEW / "audio-synthesis.json"
    if not manifest_file.exists():
        raise PipelineError("Missing review/audio-synthesis.json; synthesize the approved adapted segments first")
    manifest = read_json(manifest_file)
    manifest_cues = manifest.get("cues", [])
    if not isinstance(manifest_cues, list):
        raise PipelineError("review/audio-synthesis.json cues must be an array")
    duplicate_manifest_ids = sorted({cue.get("id") for cue in manifest_cues if sum(1 for item in manifest_cues if item.get("id") == cue.get("id")) > 1})
    cues = {cue.get("id"): cue for cue in manifest_cues}
    failures: list[dict[str, Any]] = []
    if duplicate_manifest_ids:
        failures.append({"reason": "duplicate_manifest_ids", "segmentIds": duplicate_manifest_ids})
    segment_ids = [segment["id"] for segment in segments]
    extra_ids = sorted(set(cues) - set(segment_ids))
    if extra_ids:
        failures.append({"reason": "manifest_has_unreferenced_cues", "segmentIds": extra_ids})
    for segment in segments:
        segment_id = segment["id"]
        cue = cues.get(segment_id)
        if cue is None:
            failures.append({"segmentId": segment_id, "reason": "missing_synthesis_cue"})
            continue
        text = segment["tts_phonetic_text"]
        expected_key = stable_cache_key(text, settings)
        expected_text_hash = sha256_bytes(text.encode("utf-8"))
        mismatch: dict[str, Any] = {"segmentId": segment_id}
        reasons: list[str] = []
        if cue.get("cacheKey") != expected_key:
            reasons.append("cache_key_does_not_match_current_text_and_settings")
            mismatch["expectedCacheKey"] = expected_key
            mismatch["manifestCacheKey"] = cue.get("cacheKey")
        if cue.get("spokenText") != text:
            reasons.append("manifest_spoken_text_differs_from_current_segment")
        if cue.get("textSha256") != expected_text_hash:
            reasons.append("manifest_text_hash_differs_from_current_segment")
        if cue.get("actualModel") != EXPECTED_MODEL or cue.get("actualVoice") != VOICE:
            reasons.append("actual_model_or_voice_mismatch")
            mismatch["expectedModel"] = EXPECTED_MODEL
            mismatch["actualModel"] = cue.get("actualModel")
            mismatch["expectedVoice"] = VOICE
            mismatch["actualVoice"] = cue.get("actualVoice")
        raw_path = PROJECT / cue.get("rawAudioFile", "")
        if not raw_path.is_file() or sha256_file(raw_path) != cue.get("rawSha256"):
            reasons.append("raw_provider_wav_missing_or_hash_mismatch")
        canonical_path = PROJECT / cue.get("canonicalAudioFile", "")
        if not canonical_path.is_file() or sha256_file(canonical_path) != cue.get("canonicalSha256"):
            reasons.append("canonical_wav_missing_or_hash_mismatch")
        if reasons:
            mismatch["reasons"] = reasons
            failures.append(mismatch)
    if failures:
        _write_mix_preflight_failure(failures)
        bad_ids = sorted({str(item.get("segmentId", item.get("reason", "manifest"))) for item in failures})
        raise PipelineError(f"Synthesis identity/cache preflight failed for {', '.join(bad_ids)}; see review/audio-mix-qa.json")

    voice = array.array("h", [0]) * TOTAL_SAMPLES
    active_ranges: list[tuple[int, int, str]] = []
    cue_fit_reports: list[dict[str, Any]] = []
    for segment in segments:
        segment_id = segment["id"]
        if segment_id not in cues:
            raise PipelineError(f"Missing synthesized cue {segment_id}")
        cue = cues[segment_id]
        path = PROJECT / cue["canonicalAudioFile"]
        samples = _read_mono_pcm16(path)
        active_start, active_end = _active_bounds_array(samples)
        fit_fields = cue_window_fields(segment, active_start, active_end, len(samples))
        cue_fit_reports.append({
            "id": segment_id,
            "sourceSampleCount": len(samples),
            "activeStartSample": active_start,
            "activeEndSampleExclusive": active_end,
            **fit_fields,
        })
        anchor = fit_fields["placementStartFrameForFit"]
        window_end = fit_fields["windowEndFrame"]
        offset = anchor * SAMPLES_PER_FRAME
        window_samples = (window_end - anchor) * SAMPLES_PER_FRAME
        if len(samples) > window_samples:
            failure = {
                "segmentId": segment_id,
                "reason": "full_canonical_cue_exceeds_frame_window",
                "placementStartFrame": anchor,
                "windowEndFrame": window_end,
                "sourcePcmSampleCount": len(samples),
                "sourcePcmDurationSeconds": len(samples) / SAMPLE_RATE,
                "windowSampleCapacity": window_samples,
                "windowDurationSeconds": window_samples / SAMPLE_RATE,
                "activeStartSample": active_start,
                "activeEndSampleExclusive": active_end,
                "activeStartSampleAbsolute": None if active_start is None else offset + active_start,
                "activeEndSampleExclusiveAbsolute": None if active_end is None else offset + active_end,
                "activeThresholdPcm16": ACTIVE_THRESHOLD,
                "action": "Adjust timing outside this script or obtain a new authorized narration; no trim or speed change was applied.",
            }
            _write_mix_preflight_failure([failure])
            raise PipelineError(
                f"{segment_id} canonical WAV is {len(samples)} samples ({len(samples) / SAMPLE_RATE:.3f}s), "
                f"but its [startFrame,endFrame) window holds {window_samples} samples ({window_samples / SAMPLE_RATE:.3f}s); "
                "no trim or speed change was applied; see review/audio-mix-qa.json"
            )
        if offset + len(samples) > TOTAL_SAMPLES:
            failure = {
                "segmentId": segment_id,
                "reason": "full_canonical_cue_exceeds_master_end",
                "placementStartFrame": anchor,
                "sourcePcmSampleCount": len(samples),
                "masterSampleCount": TOTAL_SAMPLES,
                "absoluteEndSampleExclusive": offset + len(samples),
                "activeStartSample": active_start,
                "activeEndSampleExclusive": active_end,
            }
            _write_mix_preflight_failure([failure])
            raise PipelineError(f"{segment_id} canonical WAV would exceed the 90-second master; see review/audio-mix-qa.json")
        if active_end is not None and offset + active_end > window_end * SAMPLES_PER_FRAME:
            raise PipelineError(
                f"{segment_id} active audio overruns its frame window: activeEndSample={offset + active_end}, "
                f"windowEndSample={window_end * SAMPLES_PER_FRAME}; no trim or speed change applied"
            )
        if not fit_fields["fitsOriginalWindowWithoutTrimOrSpeedChange"]:
            failure = {
                "segmentId": segment_id,
                "reason": "active_narration_exceeds_frame_window",
                "sourcePcmSampleCount": len(samples),
                "activeStartSample": active_start,
                "activeEndSampleExclusive": active_end,
                **fit_fields,
            }
            _write_mix_preflight_failure([failure])
            raise PipelineError(f"{segment_id} active narration exceeds its frame window; no trim or speed change applied; see review/audio-mix-qa.json")
        if active_start is not None and active_end is not None:
            active_ranges.append((offset + active_start, offset + active_end, segment_id))
        for index, value in enumerate(samples):
            voice[offset + index] = value
    active_ranges.sort()
    for previous, current in zip(active_ranges, active_ranges[1:]):
        if current[0] < previous[1]:
            raise PipelineError(f"Active narration overlap: {previous[2]} and {current[2]}")
    silence_voice = voice[SILENCE_START_SAMPLE:SILENCE_END_SAMPLE]
    silence_active = [index for index, sample in enumerate(silence_voice) if abs(sample) > ACTIVE_THRESHOLD]
    if silence_active:
        absolute_start = SILENCE_START_SAMPLE + silence_active[0]
        absolute_end = SILENCE_START_SAMPLE + silence_active[-1] + 1
        failure = {
            "reason": "active_narration_intersects_absolute_silence",
            "startSample": absolute_start,
            "endSampleExclusive": absolute_end,
            "activeThresholdPcm16": ACTIVE_THRESHOLD,
            "activeSampleCount": len(silence_active),
        }
        _write_mix_preflight_failure([failure])
        raise PipelineError(
            "Active narration intersects the required absolute-silence window "
            f"(samples {absolute_start}:{absolute_end}); no narration was muted or trimmed"
        )

    event_map, source_event_document = _load_sfx_event_map()

    stems = AUDIO / "stems"
    stem_paths = {
        "narration": stems / "narration.wav",
        "score": stems / "score.wav",
        "sfx": stems / "sfx.wav",
    }
    if any(path.exists() for path in stem_paths.values()) or (AUDIO / "master.wav").exists():
        raise PipelineError("An EP18 v04 stem or master already exists; refusing to overwrite")
    stems.mkdir(parents=True, exist_ok=True)
    _write_stereo_pcm16(stem_paths["narration"], voice)
    _float_mono_to_stereo_wav(stem_paths["score"], _make_score(segments))
    _float_mono_to_stereo_wav(stem_paths["sfx"], _make_sfx(event_map))
    sfx_event_document = {
        "schemaVersion": 1,
        **source_event_document,
        "vocalBandProtection": {"method": "two broad parametric reductions", "bandHz": [1000, 4000], "gainDb": "up to -7 dB"},
        "absoluteSilence": {"startFrame": SILENCE_START_FRAME, "endFrame": SILENCE_END_FRAME,
                             "startSample": SILENCE_START_SAMPLE, "endSampleExclusive": SILENCE_END_SAMPLE},
        "synthesis": "deterministic procedural tones, fixed partial transients and seeded XorShift noise; no sampled instruments or voice recordings",
    }
    write_json(AUDIO / "sfx_events.json", sfx_event_document)
    # Sidechain ducks the score under narration and suppresses the transient
    # presence band so event attacks remain below speech intelligibility.
    graph = (
        "[0:a]asplit=2[voice_mix][voice_key];"
        "[1:a][voice_key]sidechaincompress=threshold=0.025:ratio=2.2:attack=12:release=260[score_ducked];"
        "[2:a]equalizer=f=2000:t=q:w=0.55:g=-7,equalizer=f=3300:t=q:w=0.7:g=-5[sfx_soft];"
        "[voice_mix][score_ducked][sfx_soft]amix=inputs=3:duration=longest:normalize=0,loudnorm=I=-16:LRA=11:TP=-1.6:print_format=json"
    )
    first = _ffmpeg(
        ["/opt/homebrew/bin/ffmpeg", "-hide_banner", "-nostats", "-i", str(stem_paths["narration"]),
         "-i", str(stem_paths["score"]), "-i", str(stem_paths["sfx"]), "-filter_complex", graph,
         "-t", "90", "-f", "null", "-"],
        "Loudness first pass failed",
    )
    measured = _parse_last_json(first.stderr)
    norm = (
        "[0:a]asplit=2[voice_mix][voice_key];"
        "[1:a][voice_key]sidechaincompress=threshold=0.025:ratio=2.2:attack=12:release=260[score_ducked];"
        "[2:a]equalizer=f=2000:t=q:w=0.55:g=-7,equalizer=f=3300:t=q:w=0.7:g=-5[sfx_soft];"
        "[voice_mix][score_ducked][sfx_soft]amix=inputs=3:duration=longest:normalize=0,"
        f"loudnorm=I=-16:LRA=11:TP=-1.6:measured_I={measured['input_i']}:measured_LRA={measured['input_lra']}:"
        f"measured_TP={measured['input_tp']}:measured_thresh={measured['input_thresh']}:offset={measured['target_offset']}:"
        "linear=true:print_format=summary"
    )
    temp_context = tempfile.TemporaryDirectory(prefix="si-ep18-sovereign-subcurrent-v04-audio-", dir=tmp_root)
    with temp_context as temp_dir:
        normalized = Path(temp_dir) / "master-normalized.wav"
        _ffmpeg(
            ["/opt/homebrew/bin/ffmpeg", "-hide_banner", "-nostats", "-i", str(stem_paths["narration"]),
             "-i", str(stem_paths["score"]), "-i", str(stem_paths["sfx"]), "-filter_complex", norm,
             "-t", "90", "-ar", str(SAMPLE_RATE), "-ac", "2", "-c:a", "pcm_s16le", str(normalized)],
            "Loudness second pass failed",
        )
        normalized_info = pcm_wav_payload(normalized)
        if (normalized_info["channels"], normalized_info["sampleRate"], normalized_info["bitsPerSample"], normalized_info["sampleFrames"]) != (2, SAMPLE_RATE, 16, TOTAL_SAMPLES):
            raise PipelineError("Loudnorm output did not have exactly 90 seconds of stereo 48 kHz PCM16")
        _mute_exact_silence_window(normalized)
        candidate = normalized
        ebu_final = _measure_ebu_r128(candidate)
        post_gain_corrections: list[dict[str, Any]] = []
        for correction_pass in range(1, LOUDNESS_CORRECTION_MAX_PASSES + 1):
            if _loudness_targets_pass(ebu_final):
                break
            measured_before = dict(ebu_final)
            requested_gain_db = LOUDNESS_TARGET_LUFS - ebu_final["integratedLufs"]
            if abs(ebu_final["integratedLufs"] - LOUDNESS_TARGET_LUFS) <= LOUDNESS_TOLERANCE_LU:
                # Loudness is already in range; a zero-dB pass still runs the
                # oversampled limiter if only the true-peak gate needs repair.
                requested_gain_db = 0.0
            applied_gain_db = max(
                -LOUDNESS_CORRECTION_MAX_GAIN_DB,
                min(LOUDNESS_CORRECTION_MAX_GAIN_DB, requested_gain_db),
            )
            corrected = Path(temp_dir) / f"master-correction-{correction_pass}.wav"
            _apply_gain_correction(candidate, corrected, applied_gain_db)
            _mute_exact_silence_window(corrected)
            ebu_final = _measure_ebu_r128(corrected)
            post_gain_corrections.append({
                "pass": correction_pass,
                "gainCorrectionDb": round(applied_gain_db, 4),
                "measuredBefore": measured_before,
                "measuredAfter": dict(ebu_final),
            })
            candidate = corrected
        if not _loudness_targets_pass(ebu_final):
            _write_mix_measurement_failure(ebu_final, post_gain_corrections)
            if abs(ebu_final["integratedLufs"] - LOUDNESS_TARGET_LUFS) > LOUDNESS_TOLERANCE:
                raise PipelineError(
                    f"Corrected candidate remains at {ebu_final['integratedLufs']:.2f} LUFS after "
                    f"{len(post_gain_corrections)} correction pass(es); formal master was not written"
                )
            raise PipelineError(
                f"Corrected candidate true peak remains {ebu_final['truePeakDbtp']:.2f} dBTP after "
                f"{len(post_gain_corrections)} correction pass(es); formal master was not written"
            )
        master = AUDIO / "master.wav"
        fd, publish_temp_name = tempfile.mkstemp(prefix=".master-publish-", suffix=".wav", dir=AUDIO)
        os.close(fd)
        publish_temp = Path(publish_temp_name)
        try:
            shutil.copyfile(candidate, publish_temp)
            publish_info = pcm_wav_payload(publish_temp)
            if (publish_info["channels"], publish_info["sampleRate"], publish_info["bitsPerSample"], publish_info["sampleFrames"]) != (2, SAMPLE_RATE, 16, TOTAL_SAMPLES):
                raise PipelineError("Passing candidate changed format or frame count while publishing")
            silence_bytes = publish_info["payload"][SILENCE_START_SAMPLE * 4:SILENCE_END_SAMPLE * 4]
            if any(silence_bytes):
                raise PipelineError("Exact silence verification failed on the passing candidate")
            os.replace(publish_temp, master)
        finally:
            publish_temp.unlink(missing_ok=True)
    master_info = pcm_wav_payload(AUDIO / "master.wav")
    ebu_final = _measure_ebu_r128(AUDIO / "master.wav")
    integrated_lufs = ebu_final["integratedLufs"]
    true_peak = ebu_final["truePeakDbtp"]
    if not _loudness_targets_pass(ebu_final):
        _write_mix_measurement_failure(ebu_final, post_gain_corrections)
        (AUDIO / "master.wav").unlink(missing_ok=True)
        raise PipelineError("Published master failed its post-copy EBU R128 verification")
    report = {
        "schemaVersion": 1,
        "generatedAt": now_iso(),
        "status": "pass",
        "master": "public/audio/master.wav",
        "sampleRate": SAMPLE_RATE,
        "channels": 2,
        "bitsPerSample": 16,
        "sampleFramesPerChannel": master_info["sampleFrames"],
        "durationSeconds": master_info["sampleFrames"] / SAMPLE_RATE,
        "targetLufs": LOUDNESS_TARGET_LUFS,
        "targetLra": 11,
        "targetTruePeakDbtp": -1.6,
        "measuredInputLoudnorm": {key: measured.get(key) for key in ("input_i", "input_lra", "input_tp", "input_thresh", "target_offset")},
        "measuredFinalIntegratedLufs": integrated_lufs,
        "measuredFinalTruePeakDbtp": true_peak,
        "integratedLufsTolerance": {"target": LOUDNESS_TARGET_LUFS, "plusMinus": LOUDNESS_TOLERANCE_LU, "passed": True},
        "requiredMaximumTruePeakDbtp": -1.0,
        "postGainCorrections": post_gain_corrections,
        "correctionPolicy": {
            "maxPasses": LOUDNESS_CORRECTION_MAX_PASSES,
            "maxGainDbPerPass": LOUDNESS_CORRECTION_MAX_GAIN_DB,
            "limiterCeilingDbtp": -1.4,
            "limiterLinear": CORRECTION_LIMIT_LINEAR,
            "oversampleRateHz": 192000,
        },
        "absoluteSilenceVerified": {"startFrame": SILENCE_START_FRAME, "endFrame": SILENCE_END_FRAME,
                                    "samplesPerChannel": SILENCE_END_SAMPLE - SILENCE_START_SAMPLE},
        "stems": {key: str(path.relative_to(PROJECT)) for key, path in stem_paths.items()},
        "voiceActiveRanges": [
            {"id": segment_id, "startSample": start_sample, "endSampleExclusive": end_sample}
            for start_sample, end_sample, segment_id in active_ranges
        ],
        "narrationCueFit": cue_fit_reports,
        "masterSha256": sha256_file(AUDIO / "master.wav"),
    }
    write_json(REVIEW / "audio-mix-qa.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    synth = sub.add_parser("synthesize", help="synthesize selected narration cues")
    synth.add_argument("--ids", nargs="+", required=True)
    synth.add_argument("--verbose", action="store_true", help="capture CLI diagnostics internally; never print raw provider output")
    sub.add_parser("mix", help="mix current v04 segments into the 90-second master")
    args = parser.parse_args()
    try:
        if args.command == "synthesize":
            cues = synthesize(args.ids, args.verbose)
            print(json.dumps({
                "command": "synthesize",
                "source": "segments.json",
                "cues": [{
                    "id": cue["id"],
                    "actualModel": cue.get("actualModel"),
                    "actualVoice": cue.get("actualVoice"),
                    "durationSeconds": cue.get("durationSeconds"),
                    "activeDurationSeconds": cue.get("activeDurationSeconds"),
                    "activeStartFrame": cue.get("activeStartFrame"),
                    "activeEndFrameExclusive": cue.get("activeEndFrameExclusive"),
                    "windowSeconds": cue.get("windowSeconds"),
                    "fitsOriginalWindowWithoutTrimOrSpeedChange": cue.get("fitsOriginalWindowWithoutTrimOrSpeedChange"),
                    "fitsFullCanonicalWindowWithoutTrimOrSpeedChange": cue.get("fitsFullCanonicalWindowWithoutTrimOrSpeedChange"),
                    "windowSampleCapacity": cue.get("windowSampleCapacity"),
                    "canonicalAudioFile": cue.get("canonicalAudioFile"),
                } for cue in cues],
            }, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(mix(), ensure_ascii=False, indent=2))
    except PipelineError as exc:
        print(f"audio_pipeline: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
