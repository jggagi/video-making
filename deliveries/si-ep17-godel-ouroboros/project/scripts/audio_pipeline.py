#!/usr/bin/env python3
"""EP17 speech synthesis and deterministic 90-second audio assembly.

The synthesis path keeps provider WAVs immutable, verifies their PCM payload,
and writes a separate canonical mono 48 kHz cue.  ``mix`` verifies cue identity
against the current segment text before assembling the independent stems.
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
EXPECTED_MODEL = "cosyvoice-v3-flash"
VOICE = "longtian_v3"
FPS = 60
SAMPLE_RATE = 48_000
SAMPLES_PER_FRAME = SAMPLE_RATE // FPS
TOTAL_FRAMES = 5_400
TOTAL_SAMPLES = TOTAL_FRAMES * SAMPLES_PER_FRAME
SILENCE_START_FRAME = 4_860
SILENCE_END_FRAME = 4_890
SILENCE_START_SAMPLE = SILENCE_START_FRAME * SAMPLES_PER_FRAME
SILENCE_END_SAMPLE = SILENCE_END_FRAME * SAMPLES_PER_FRAME
ACTIVE_THRESHOLD = 32  # PCM16 ~= -60 dBFS; used only to report active bounds.
LOUDNESS_TARGET_LUFS = -16.0
LOUDNESS_TOLERANCE_LU = 0.15
LOUDNESS_CORRECTION_MAX_PASSES = 2
LOUDNESS_CORRECTION_MAX_GAIN_DB = 2.0
CORRECTION_LIMIT_LINEAR = 10 ** (-1.4 / 20.0)

SYNTH_SETTINGS = {
    "provider": "Aliyun Bailian",
    "requestedModel": None,  # Profile default; deliberately omit --model.
    "expectedEffectiveModel": EXPECTED_MODEL,
    "voice": VOICE,
    "rate": 1.0,
    "format": "wav",
    "sampleRate": 24_000,
    "language": "zh",
    "concurrent": 1,
}

SFX_EVENTS = [
    {"id": "lens-iris", "frame": 840, "kind": "low-inward-sweep", "seconds": 2.8, "levelDbfs": -27},
    {"id": "logical-fracture", "frame": 1500, "kind": "metallic-snap-and-tritone", "seconds": 1.7, "levelDbfs": -28},
    {"id": "crab-canon", "frame": 2220, "kind": "forward-reverse-harpsichord", "seconds": 22.0, "levelDbfs": -31},
    {"id": "shepard-descent", "frame": 2940, "kind": "descending-shepard-risset", "seconds": 24.0, "levelDbfs": -30},
    {"id": "stack-overflow", "frame": 3900, "kind": "rising-digital-cycle", "seconds": 3.5, "levelDbfs": -29},
    {"id": "accelerating-ticks", "frame": 4500, "kind": "deterministic-polyrhythmic-ticks", "seconds": 6.0, "levelDbfs": -32},
    {"id": "relay-cut", "frame": 4860, "kind": "hard-cut-to-absolute-silence", "seconds": 0.5, "levelDbfs": None},
    {"id": "external-warm-pluck", "frame": 4890, "kind": "warm-harp-pluck", "seconds": 1.8, "levelDbfs": -27},
]


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


def load_segments(original: bool) -> list[dict[str, Any]]:
    name = "segments-original.json" if original else "segments.json"
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


def safe_auth_check() -> bool:
    if not BL.is_file():
        raise PipelineError("Configured Bailian CLI path is unavailable")
    proc = subprocess.run(
        [str(BL), "auth", "status", "--output", "json"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    try:
        response = json.loads(proc.stdout)
    except Exception as exc:
        raise PipelineError("Bailian auth status did not return parseable JSON; response was not retained") from exc
    flags: list[bool] = []
    auth_keys = {"authenticated", "isauthenticated", "loggedin", "isloggedin", "hasapikey"}

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if re.sub(r"[^a-z0-9]", "", str(key).lower()) in auth_keys and isinstance(child, bool):
                    flags.append(child)
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(response)
    authenticated = proc.returncode == 0 and bool(flags) and all(flags)
    safe = {
        "capturedAt": now_iso(),
        "provider": "Aliyun Bailian",
        "cliVersion": "2.5.0",
        "skillVersion": "2.5.0",
        "latestPublishedVersionAtPreflight": "2.5.0",
        "authenticated": authenticated,
        "authCheckExitCode": proc.returncode,
        "rawProviderOutputRetained": False,
        "authEvidence": "allowlisted boolean from bl auth status --output json",
        "ttsIdentityCheck": "per-request returned model and voice are verified before canonicalization",
    }
    write_json(REVIEW / "provider-preflight.json", safe)
    if not authenticated:
        raise PipelineError("Bailian auth status is not authenticated; synthesis stopped")
    return authenticated


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
    header_mismatch = (riff_declared != len(raw) or data_declared != len(data_payload))
    return {
        **fmt,
        "sampleWidthBytes": sample_width,
        "payload": data_payload,
        "sampleFrames": len(data_payload) // expected_align,
        "physicalBytes": len(raw),
        "riffDeclaredBytes": riff_declared,
        "dataDeclaredBytes": data_declared,
        "dataPhysicalBytes": len(data_payload),
        "headerMismatch": header_mismatch,
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


def stable_cache_key(text: str) -> str:
    material = {"spokenText": text, **SYNTH_SETTINGS}
    return sha256_bytes(json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def manifest_path(original: bool) -> Path:
    name = "audio-original-samples.json" if original else "audio-synthesis.json"
    return REVIEW / name


def existing_manifest(original: bool) -> dict[str, Any]:
    path = manifest_path(original)
    if not path.exists():
        return {"schemaVersion": 1, "source": "segments-original.json" if original else "segments.json", "cues": []}
    doc = read_json(path)
    if not isinstance(doc, dict) or not isinstance(doc.get("cues"), list):
        raise PipelineError(f"Invalid existing manifest {path.name}")
    return doc


def find_cached_cue(cache_key: str) -> dict[str, Any] | None:
    for name in ("audio-original-samples.json", "audio-synthesis.json"):
        path = REVIEW / name
        if not path.exists():
            continue
        doc = read_json(path)
        for cue in doc.get("cues", []):
            if cue.get("cacheKey") == cache_key and cue.get("actualModel") == EXPECTED_MODEL and cue.get("actualVoice") == VOICE:
                candidate = PROJECT / cue.get("canonicalAudioFile", "")
                if candidate.is_file() and sha256_file(candidate) == cue.get("canonicalSha256"):
                    return cue
    return None


def run_provider_synthesis(text_file: Path, raw_path: Path, verbose: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
    args = [
        str(BL), "speech", "synthesize",
        "--text-file", str(text_file),
        "--voice", VOICE,
        "--rate", "1.0",
        "--format", "wav",
        "--sample-rate", "24000",
        "--language", "zh",
        "--concurrent", "1",
        "--out", str(raw_path),
        "--output", "json",
    ]
    if verbose:
        args.append("--verbose")
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
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
    model, voice, evidence = extract_returned_identity(response)
    if model != EXPECTED_MODEL or voice != VOICE:
        safe_model = model if model and re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", model) else None
        safe_voice = voice if voice and re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", voice) else None
        raise PipelineError(
            "Returned provider identity did not verify; "
            f"actualModel={safe_model!r}, actualVoice={safe_voice!r}, "
            f"modelEvidencePaths={evidence['modelPaths']}, voiceEvidencePaths={evidence['voicePaths']}. "
            "Response was not retained and no canonical cue was written."
        )
    if not raw_path.is_file() or raw_path.stat().st_size == 0:
        raise PipelineError("Provider returned success without a non-empty WAV file")
    return response, {"actualModel": model, "actualVoice": voice, "identityEvidencePaths": evidence}


def frame_for_sample_ceil(sample: int) -> int:
    return (sample * FPS + SAMPLE_RATE - 1) // SAMPLE_RATE


def cue_window_fields(segment: dict[str, Any], active_start: int | None, active_end: int | None) -> dict[str, Any]:
    segment_id = segment["id"]
    anchor = segment["startFrame"]
    if segment_id == "S08" and anchor < SILENCE_END_FRAME:
        anchor = SILENCE_END_FRAME
    end = segment["endFrame"]
    start_frame = None if active_start is None else anchor + active_start * FPS // SAMPLE_RATE
    end_frame = None if active_end is None else anchor + frame_for_sample_ceil(active_end)
    return {
        "placementStartFrameForFit": anchor,
        "windowEndFrame": end,
        "windowSeconds": (end - anchor) / FPS,
        "activeStartFrame": start_frame,
        "activeEndFrameExclusive": end_frame,
        "activeDurationSeconds": 0 if active_start is None or active_end is None else (active_end - active_start) / SAMPLE_RATE,
        "fitsOriginalWindowWithoutTrimOrSpeedChange": end_frame is None or end_frame <= end,
    }


def synthesize(ids: list[str], original: bool, verbose: bool = False) -> list[dict[str, Any]]:
    safe_auth_check()
    rows = load_segments(original)
    by_id = {row["id"]: row for row in rows}
    missing = [segment_id for segment_id in ids if segment_id not in by_id]
    if missing:
        raise PipelineError(f"Unknown segment ids: {', '.join(missing)}")
    AUDIO.mkdir(parents=True, exist_ok=True)
    text_dir = AUDIO / "text"
    raw_dir = AUDIO / "history" / "raw"
    text_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    canonical_dir = AUDIO / ("original-samples" if original else "voice")
    canonical_dir.mkdir(parents=True, exist_ok=True)
    manifest = existing_manifest(original)
    cues_by_key = {cue.get("cacheKey"): cue for cue in manifest["cues"]}
    results: list[dict[str, Any]] = []
    for segment_id in ids:
        segment = by_id[segment_id]
        text = segment["tts_phonetic_text"]
        cache_key = stable_cache_key(text)
        cached = find_cached_cue(cache_key)
        if cached:
            cue = dict(cached)
            cue["id"] = segment_id
            cue["cacheReuse"] = True
            cue["sourceSegmentFile"] = "segments-original.json" if original else "segments.json"
            cue["sourceStartFrame"] = segment["startFrame"]
            cue["sourceEndFrame"] = segment["endFrame"]
            cue.update(cue_window_fields(segment, cue.get("activeStartSample"), cue.get("activeEndSampleExclusive")))
            manifest["cues"] = [c for c in manifest["cues"] if c.get("cacheKey") != cache_key]
            manifest["cues"].append(cue)
            write_json(manifest_path(original), manifest)
            results.append(cue)
            continue
        if cache_key in cues_by_key:
            old = cues_by_key[cache_key]
            path = PROJECT / old.get("canonicalAudioFile", "")
            if not path.is_file() or sha256_file(path) != old.get("canonicalSha256"):
                raise PipelineError(f"Cached cue integrity mismatch for {segment_id}; refusing overwrite")
        text_path = text_dir / f"{segment_id}-{cache_key[:12]}.txt"
        if text_path.exists() and text_path.read_text(encoding="utf-8") != text:
            raise PipelineError(f"Refusing to overwrite divergent text file {text_path.name}")
        text_path.write_text(text, encoding="utf-8")
        raw_path = raw_dir / f"{cache_key}.wav"
        if raw_path.exists():
            raise PipelineError(f"Raw cache file exists without a verified matching manifest: {raw_path.name}")
        _, identity = run_provider_synthesis(text_path, raw_path, verbose)
        raw_info = pcm_wav_payload(raw_path)
        if raw_info["sampleRate"] != 24_000 or raw_info["channels"] != 1:
            raise PipelineError(
                f"Provider WAV format mismatch: rate={raw_info['sampleRate']}, channels={raw_info['channels']}; raw WAV retained"
            )
        repaired_temp: Path | None = None
        source_for_ffmpeg = raw_path
        if raw_info["headerMismatch"]:
            fd, temp_name = tempfile.mkstemp(prefix="ep17-repaired-", suffix=".wav", dir=os.environ.get("TMPDIR"))
            os.close(fd)
            repaired_temp = Path(temp_name)
            write_pcm_wav(repaired_temp, raw_info["payload"], raw_info["channels"], raw_info["sampleRate"], raw_info["sampleWidthBytes"])
            checked = pcm_wav_payload(repaired_temp)
            if checked["headerMismatch"] or checked["sampleFrames"] != raw_info["sampleFrames"]:
                repaired_temp.unlink(missing_ok=True)
                raise PipelineError("Validated WAV header repair failed; original provider WAV was retained")
            source_for_ffmpeg = repaired_temp
        canonical_path = canonical_dir / f"{segment_id}-{cache_key[:12]}.wav"
        if canonical_path.exists():
            if repaired_temp:
                repaired_temp.unlink(missing_ok=True)
            raise PipelineError(f"Canonical output already exists without a matching cache record: {canonical_path.name}")
        fd, canonical_temp_name = tempfile.mkstemp(prefix=f".{segment_id}-", suffix=".wav", dir=canonical_dir)
        os.close(fd)
        Path(canonical_temp_name).unlink(missing_ok=True)
        canonical_temp = Path(canonical_temp_name)
        try:
            proc = subprocess.run(
                ["/opt/homebrew/bin/ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-n", "-i", str(source_for_ffmpeg),
                 "-map", "0:a:0", "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(canonical_temp)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
            )
            if proc.returncode != 0 or not canonical_temp.is_file():
                raise PipelineError(f"Canonical resampling failed (ffmpeg exit {proc.returncode}); raw WAV retained")
        finally:
            if repaired_temp:
                repaired_temp.unlink(missing_ok=True)
        canonical_info = pcm_wav_payload(canonical_temp)
        if (canonical_info["sampleRate"], canonical_info["channels"], canonical_info["bitsPerSample"]) != (SAMPLE_RATE, 1, 16):
            canonical_temp.unlink(missing_ok=True)
            raise PipelineError("Canonical WAV is not mono 48 kHz PCM16")
        active_start, active_end = active_bounds(canonical_info["payload"], canonical_info["sampleFrames"])
        fit_fields = cue_window_fields(segment, active_start, active_end)
        os.replace(canonical_temp, canonical_path)
        cue = {
            "id": segment_id,
            "spokenText": text,
            "sourceSegmentFile": "segments-original.json" if original else "segments.json",
            "sourceStartFrame": segment["startFrame"],
            "sourceEndFrame": segment["endFrame"],
            **fit_fields,
            "provider": SYNTH_SETTINGS["provider"],
            "requestedModel": None,
            "actualModel": identity["actualModel"],
            "voice": VOICE,
            "actualVoice": identity["actualVoice"],
            "identityEvidencePaths": identity["identityEvidencePaths"],
            "rate": 1.0,
            "formatRequested": "wav",
            "providerSampleRate": raw_info["sampleRate"],
            "providerChannels": raw_info["channels"],
            "providerBitsPerSample": raw_info["bitsPerSample"],
            "rawAudioFile": str(raw_path.relative_to(PROJECT)),
            "rawSha256": sha256_file(raw_path),
            "rawSampleCount": raw_info["sampleFrames"],
            "rawDurationSeconds": raw_info["sampleFrames"] / raw_info["sampleRate"],
            "rawHeaderMismatchRepairedForCanonical": raw_info["headerMismatch"],
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
            "textSha256": sha256_file(text_path),
            "cacheReuse": False,
            "generatedAt": now_iso(),
        }
        manifest["schemaVersion"] = 1
        manifest["source"] = "segments-original.json" if original else "segments.json"
        manifest["settings"] = SYNTH_SETTINGS
        manifest["cues"] = [c for c in manifest["cues"] if c.get("cacheKey") != cache_key]
        manifest["cues"].append(cue)
        manifest["updatedAt"] = now_iso()
        write_json(manifest_path(original), manifest)
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
              sweep_hz_per_second: float = 0.0, attack: float = 0.004) -> None:
    count = min(int(duration * SAMPLE_RATE), len(buffer) - start)
    if count <= 0:
        return
    tau = 2.0 * math.pi
    attack_samples = max(1, int(attack * SAMPLE_RATE))
    for offset in range(count):
        t = offset / SAMPLE_RATE
        envelope = min(1.0, offset / attack_samples) * math.exp(-decay * t)
        phase_base = tau * (frequency * t + 0.5 * sweep_hz_per_second * t * t)
        value = 0.0
        for harmonic, weight in harmonics:
            value += weight * math.sin(phase_base * harmonic)
        buffer[start + offset] += amplitude * envelope * value


def _add_noise_burst(buffer: array.array, start: int, duration: float, amplitude: float, seed: int,
                     decay: float = 12.0) -> None:
    import random
    rng = random.Random(seed)
    count = min(int(duration * SAMPLE_RATE), len(buffer) - start)
    for offset in range(max(0, count)):
        t = offset / SAMPLE_RATE
        buffer[start + offset] += amplitude * rng.uniform(-1.0, 1.0) * math.exp(-decay * t)


def _make_score() -> array.array:
    score = array.array("f", [0.0]) * TOTAL_SAMPLES
    # D-minor arpeggio; the first consonant chord lands exactly at frame 60.
    anchor = 60 * SAMPLES_PER_FRAME
    for freq, gain in ((293.66, 0.55), (440.00, 0.38), (587.33, 0.25)):
        _add_tone(score, anchor, 0.85, freq, 0.045 * gain, decay=2.8,
                  harmonics=((1, 1.0), (2, 0.25), (3, 0.07)))
    notes = (293.66, 440.00, 587.33, 698.46, 880.00, 698.46, 587.33, 440.00,
             349.23, 523.25, 698.46, 783.99, 1046.50, 783.99, 698.46, 523.25)
    step = int(0.31 * SAMPLE_RATE)
    note_len = 0.24
    for index, start in enumerate(range(anchor + step, SILENCE_START_SAMPLE, step)):
        _add_tone(score, start, note_len, notes[index % len(notes)], 0.028,
                  decay=7.5, harmonics=((1, 1.0), (2, 0.22), (4, 0.07)), attack=0.001)
    # A quiet forward/reverse counterpoint enters at frame 2220.
    crab_start = 2_220 * SAMPLES_PER_FRAME
    crab_step = int(0.42 * SAMPLE_RATE)
    crab_notes = (293.66, 349.23, 440.00, 523.25, 587.33, 698.46, 880.00, 698.46)
    for index in range(48):
        t0 = crab_start + index * crab_step
        t1 = crab_start + (47 - index) * crab_step
        _add_tone(score, t0, 0.34, crab_notes[index % len(crab_notes)], 0.010,
                  decay=6.0, harmonics=((1, 1.0), (2, 0.17)), attack=0.002)
        _add_tone(score, t1, 0.34, crab_notes[index % len(crab_notes)], 0.008,
                  decay=6.0, harmonics=((1, 1.0), (2, 0.17)), attack=0.002)
    # A continuous 11-partial descending Shepard-Risset glide runs from 49s through 73s.
    shepard_start = 2_940 * SAMPLES_PER_FRAME
    shepard_count = min(24 * SAMPLE_RATE, TOTAL_SAMPLES - shepard_start)
    tau = 2.0 * math.pi
    fade_seconds = 0.5
    gaussian_center = math.log2(600.0 / 55.0)
    log_two = math.log(2.0)
    for offset in range(shepard_count):
        t = offset / SAMPLE_RATE
        fade_in = 0.5 - 0.5 * math.cos(math.pi * min(1.0, t / fade_seconds))
        fade_out = 0.5 - 0.5 * math.cos(math.pi * min(1.0, (24.0 - t) / fade_seconds))
        edge_envelope = min(fade_in, fade_out)
        out = 0.0
        for layer in range(11):
            log_frequency = layer - t / 8.0
            freq = 55.0 * (2.0 ** log_frequency)
            if freq < 20.0 or freq > 18_000.0:
                continue
            phase = tau * (55.0 * (2.0 ** layer)) * (8.0 / log_two) * (1.0 - 2.0 ** (-t / 8.0))
            gaussian = math.exp(-0.5 * ((log_frequency - gaussian_center) / 1.1) ** 2)
            out += gaussian * math.sin(phase)
        score[shepard_start + offset] += (0.018 / 4.0) * edge_envelope * out
    # Do not let the cold bed or its tails cross the exact relay silence. The
    # warm harmonics are added only after the 30-frame silent window.
    for index in range(SILENCE_START_SAMPLE, TOTAL_SAMPLES):
        score[index] = 0.0
    # Sparse warm, non-looping harmonics after the relay silence.
    warm = 4_890 * SAMPLES_PER_FRAME
    for freq, gain in ((392.00, 0.60), (493.88, 0.28), (587.33, 0.18)):
        _add_tone(score, warm, 1.4, freq, 0.025 * gain, decay=1.8,
                  harmonics=((1, 1.0), (2, 0.16), (3, 0.04)), attack=0.003)
    return score


def _make_sfx() -> array.array:
    sfx = array.array("f", [0.0]) * TOTAL_SAMPLES
    _add_tone(sfx, 840 * SAMPLES_PER_FRAME, 2.8, 86.0, 0.030, decay=0.7,
              harmonics=((1, 1.0), (0.5, 0.1)), sweep_hz_per_second=-15.0, attack=0.03)
    _add_noise_burst(sfx, 840 * SAMPLES_PER_FRAME, 1.5, 0.008, seed=17017, decay=2.4)
    fracture = 1_500 * SAMPLES_PER_FRAME
    _add_noise_burst(sfx, fracture, 0.14, 0.060, seed=17018, decay=27.0)
    _add_tone(sfx, fracture, 1.5, 640.0, 0.024, decay=2.8, harmonics=((1, 1.0),), attack=0.001)
    _add_tone(sfx, fracture, 1.5, 905.10, 0.020, decay=2.8, harmonics=((1, 1.0),), attack=0.001)
    # A restrained rising clock-cycle edge, followed by six seconds of ticks.
    overflow = 3_900 * SAMPLES_PER_FRAME
    _add_tone(sfx, overflow, 3.3, 740.0, 0.012, decay=0.25,
              harmonics=((1, 1.0), (3, 0.35)), sweep_hz_per_second=1250.0, attack=0.02)
    tick_start = 4_500 * SAMPLES_PER_FRAME
    rng_seed = 17019
    for n in range(64):
        phase = n / 63.0
        at = tick_start + int((1.0 - (1.0 - phase) ** 2) * 5.8 * SAMPLE_RATE)
        _add_noise_burst(sfx, at, 0.018, 0.013, seed=rng_seed + n, decay=160.0)
        _add_tone(sfx, at, 0.022, 1800 + phase * 1200, 0.008, decay=90.0,
                  harmonics=((1, 1.0),), attack=0.0003)
    # Relay click at the cut is deliberately excluded; the 30-frame window is zero.
    warm = 4_890 * SAMPLES_PER_FRAME
    _add_tone(sfx, warm, 1.8, 392.0, 0.038, decay=1.5,
              harmonics=((1, 1.0), (2, 0.18), (3, 0.06)), attack=0.008)
    for index in range(SILENCE_START_SAMPLE, SILENCE_END_SAMPLE):
        sfx[index] = 0.0
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
        "staleIdentityMismatches": failures,
        "masterWritten": False,
    })


def mix() -> dict[str, Any]:
    segments = load_segments(False)
    manifest_file = REVIEW / "audio-synthesis.json"
    if not manifest_file.exists():
        raise PipelineError("Missing review/audio-synthesis.json; synthesize the approved adapted segments first")
    manifest = read_json(manifest_file)
    manifest_cues = manifest.get("cues", [])
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
        expected_key = stable_cache_key(text)
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
        if reasons:
            mismatch["reasons"] = reasons
            failures.append(mismatch)
    if failures:
        _write_mix_preflight_failure(failures)
        bad_ids = sorted({str(item.get("segmentId", item.get("reason", "manifest"))) for item in failures})
        raise PipelineError(f"Synthesis identity/cache preflight failed for {', '.join(bad_ids)}; see review/audio-mix-qa.json")

    voice = array.array("h", [0]) * TOTAL_SAMPLES
    active_ranges: list[tuple[int, int, str]] = []
    for segment in segments:
        segment_id = segment["id"]
        if segment_id not in cues:
            raise PipelineError(f"Missing synthesized cue {segment_id}")
        cue = cues[segment_id]
        path = PROJECT / cue["canonicalAudioFile"]
        if not path.is_file() or sha256_file(path) != cue.get("canonicalSha256"):
            raise PipelineError(f"Cue hash mismatch for {segment_id}")
        samples = _read_mono_pcm16(path)
        active_start, active_end = _active_bounds_array(samples)
        fit_fields = cue_window_fields(segment, active_start, active_end)
        anchor = fit_fields["placementStartFrameForFit"]
        window_end = fit_fields["windowEndFrame"]
        offset = anchor * SAMPLES_PER_FRAME
        if offset + len(samples) > TOTAL_SAMPLES:
            raise PipelineError(f"{segment_id} source audio would be truncated at the master end")
        if active_end is not None and offset + active_end > window_end * SAMPLES_PER_FRAME:
            raise PipelineError(
                f"{segment_id} active audio overruns its frame window: activeEndSample={offset + active_end}, "
                f"windowEndSample={window_end * SAMPLES_PER_FRAME}; no trim or speed change applied"
            )
        if not fit_fields["fitsOriginalWindowWithoutTrimOrSpeedChange"]:
            raise PipelineError(f"{segment_id} active narration exceeds its updated frame window; no trim or speed change applied")
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

    stems = AUDIO / "stems"
    stem_paths = {
        "narration": stems / "narration.wav",
        "score": stems / "score.wav",
        "sfx": stems / "sfx.wav",
    }
    if any(path.exists() for path in stem_paths.values()) or (AUDIO / "master.wav").exists():
        raise PipelineError("An EP17 stem or master already exists; refusing to overwrite")
    stems.mkdir(parents=True, exist_ok=True)
    _write_stereo_pcm16(stem_paths["narration"], voice)
    _float_mono_to_stereo_wav(stem_paths["score"], _make_score())
    _float_mono_to_stereo_wav(stem_paths["sfx"], _make_sfx())
    write_json(AUDIO / "sfx_events.json", {
        "schemaVersion": 1,
        "fps": FPS,
        "sampleRate": SAMPLE_RATE,
        "events": SFX_EVENTS,
        "vocalBandProtection": {"method": "static attenuation", "bandHz": [1000, 4000], "gainDb": -4},
        "absoluteSilence": {"startFrame": SILENCE_START_FRAME, "endFrame": SILENCE_END_FRAME,
                             "startSample": SILENCE_START_SAMPLE, "endSampleExclusive": SILENCE_END_SAMPLE},
    })
    # Sidechain ducks the score under narration; the SFX stem receives a gentle
    # 1-4 kHz reduction so transient design stays below the speech intelligibility band.
    graph = (
        "[0:a]asplit=2[voice_mix][voice_key];"
        "[1:a][voice_key]sidechaincompress=threshold=0.025:ratio=2.2:attack=12:release=260[score_ducked];"
        "[2:a]equalizer=f=1600:t=q:w=1.2:g=-4,equalizer=f=3000:t=q:w=1.2:g=-4[sfx_soft];"
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
        "[2:a]equalizer=f=1600:t=q:w=1.2:g=-4,equalizer=f=3000:t=q:w=1.2:g=-4[sfx_soft];"
        "[voice_mix][score_ducked][sfx_soft]amix=inputs=3:duration=longest:normalize=0,"
        f"loudnorm=I=-16:LRA=11:TP=-1.6:measured_I={measured['input_i']}:measured_LRA={measured['input_lra']}:"
        f"measured_TP={measured['input_tp']}:measured_thresh={measured['input_thresh']}:offset={measured['target_offset']}:"
        "linear=true:print_format=summary"
    )
    tmp_root = os.environ.get("TMPDIR")
    temp_context = tempfile.TemporaryDirectory(prefix="ep17-audio-", dir=tmp_root)
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
        "masterSha256": sha256_file(AUDIO / "master.wav"),
    }
    write_json(REVIEW / "audio-mix-qa.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    synth = sub.add_parser("synthesize", help="synthesize selected narration cues")
    synth.add_argument("--ids", nargs="+", required=True)
    synth.add_argument("--original", action="store_true", help="read segments-original.json")
    synth.add_argument("--verbose", action="store_true", help="capture CLI diagnostics internally; never print raw provider output")
    sub.add_parser("mix", help="mix current approved segments into the 90-second master")
    args = parser.parse_args()
    try:
        if args.command == "synthesize":
            cues = synthesize(args.ids, args.original, args.verbose)
            print(json.dumps({
                "command": "synthesize",
                "source": "segments-original.json" if args.original else "segments.json",
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
