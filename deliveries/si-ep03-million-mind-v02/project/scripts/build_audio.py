#!/usr/bin/env python3
"""Build EP3 v02 audio assets from the project timeline and SFX event map.

Provider calls happen only through the explicit ``--generate`` mode. Mixing is
independent and never starts TTS implicitly.
"""

from __future__ import annotations

import argparse
import array
import hashlib
import json
import math
import random
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any


PROJECT = Path(__file__).resolve().parents[1]
AUDIO = PROJECT / "public" / "audio"
RAW = AUDIO / "raw"
CANONICAL = AUDIO / "canonical"
CUES = AUDIO / "cues"
SEGMENTS_PATH = PROJECT / "segments.json"
SFX_EVENTS_PATH = PROJECT / "sfx_events.json"
MANIFEST_PATH = AUDIO / "provider-manifest.json"
TIMING_PATH = PROJECT / "audio-timing.json"

BL = Path("/Users/guoq/.local/n/bin/bl")
PROVIDER = "Aliyun Bailian"
MODEL = "cosyvoice-v3-flash"
VOICE = "longtian_v3"
RATE = 0.98
RAW_RATE = 24_000
SAMPLE_RATE = 48_000
FPS = 60
DURATION_SECONDS = 120
TOTAL_FRAMES = FPS * DURATION_SECONDS
TOTAL_SAMPLES = SAMPLE_RATE * DURATION_SECONDS
SAMPLES_PER_FRAME = SAMPLE_RATE // FPS
VOICE_ONSET_DELAY_FRAMES = 12


class AudioBuildError(RuntimeError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AudioBuildError(f"cannot read {path.name}: {exc}") from None
    if not isinstance(value, dict):
        raise AudioBuildError(f"{path.name} must contain a JSON object")
    return value


def settings() -> dict[str, Any]:
    return {
        "provider": PROVIDER,
        "model": MODEL,
        "voice": VOICE,
        "rate": RATE,
        "format": "wav",
        "sampleRate": RAW_RATE,
        "channels": 1,
        "bitsPerSample": 16,
    }


def cache_key(text: str) -> str:
    canonical = json.dumps(
        {"text": text, "settings": settings()},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(canonical)


def load_segments() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = load_json(SEGMENTS_PATH)
    if (data.get("fps"), data.get("duration_seconds"), data.get("sample_rate")) != (
        FPS, DURATION_SECONDS, SAMPLE_RATE
    ):
        raise AudioBuildError("segments.json must remain 120 seconds at 60 fps and 48 kHz")
    provider = data.get("provider", {})
    expected_provider = {
        "provider": PROVIDER,
        "model": MODEL,
        "voice": VOICE,
        "rate": RATE,
        "format": "wav",
        "sample_rate": RAW_RATE,
    }
    if provider != expected_provider:
        raise AudioBuildError("segments.json provider settings differ from the approved EP3 v02 settings")
    segments = data.get("segments")
    if not isinstance(segments, list) or not segments:
        raise AudioBuildError("segments.json has no segments")
    seen: set[str] = set()
    for segment in segments:
        segment_id = segment.get("id")
        if not isinstance(segment_id, str) or segment_id in seen:
            raise AudioBuildError("segment IDs must be unique strings")
        seen.add(segment_id)
        if not isinstance(segment.get("tts_phonetic_text"), str) or not segment["tts_phonetic_text"].strip():
            raise AudioBuildError(f"{segment_id} has no TTS text")
        if not isinstance(segment.get("chunks"), list) or not segment["chunks"]:
            raise AudioBuildError(f"{segment_id} has no caption chunks")
    return data, segments


def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        return {"version": 1, "provider": PROVIDER, "settings": settings(), "segments": {}}
    manifest = load_json(MANIFEST_PATH)
    if manifest.get("provider") != PROVIDER or manifest.get("settings") != settings():
        raise AudioBuildError("provider manifest settings do not match this project")
    if not isinstance(manifest.get("segments"), dict):
        raise AudioBuildError("provider manifest has no segment map")
    return manifest


def parse_wav_pcm(path: Path) -> dict[str, Any]:
    """Read a PCM WAV payload by its chunks, tolerating incorrect RIFF lengths."""
    payload = path.read_bytes()
    if len(payload) < 12 or payload[:4] != b"RIFF" or payload[8:12] != b"WAVE":
        raise AudioBuildError(f"{path.name} is not a RIFF/WAVE file")
    declared_riff = struct.unpack_from("<I", payload, 4)[0]
    offset = 12
    fmt: tuple[int, int, int, int, int, int] | None = None
    raw_pcm: bytes | None = None
    declared_data: int | None = None
    while offset + 8 <= len(payload):
        chunk_id = payload[offset:offset + 4]
        declared_size = struct.unpack_from("<I", payload, offset + 4)[0]
        body_start = offset + 8
        available = len(payload) - body_start
        actual_size = min(declared_size, available)
        body_end = body_start + actual_size
        if chunk_id == b"fmt ":
            if actual_size < 16:
                raise AudioBuildError(f"{path.name} has a truncated WAV fmt chunk")
            fmt = struct.unpack_from("<HHIIHH", payload, body_start)
        elif chunk_id == b"data":
            declared_data = declared_size
            raw_pcm = payload[body_start:body_end]
            # Preserve the provider's declared size in metadata, even if it
            # exceeds the physical PCM payload; canonicalization fixes headers.
        if declared_size > available:
            break
        offset = body_start + declared_size + (declared_size & 1)
    if fmt is None or raw_pcm is None:
        raise AudioBuildError(f"{path.name} is missing its PCM fmt or data chunk")
    audio_format, channels, sample_rate, byte_rate, block_align, bits = fmt
    if (audio_format, channels, sample_rate, byte_rate, block_align, bits) != (
        1, 1, RAW_RATE, RAW_RATE * 2, 2, 16
    ):
        raise AudioBuildError(f"{path.name} is not PCM16 mono at {RAW_RATE} Hz")
    if not raw_pcm or len(raw_pcm) % block_align:
        raise AudioBuildError(f"{path.name} has empty or unaligned PCM data")
    return {
        "pcm": raw_pcm,
        "samples": len(raw_pcm) // block_align,
        "rawBytes": len(payload),
        "declaredRiffBytes": declared_riff + 8,
        "declaredDataBytes": declared_data,
        "pcmSha256": sha256_bytes(raw_pcm),
        "headerMatchesPhysicalPayload": declared_riff == len(payload) - 8
        and declared_data == len(raw_pcm),
    }


def canonicalize_wav(raw_path: Path, canonical_path: Path) -> dict[str, Any]:
    info = parse_wav_pcm(raw_path)
    pcm: bytes = info["pcm"]
    header = (
        b"RIFF"
        + struct.pack("<I", 36 + len(pcm))
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, RAW_RATE, RAW_RATE * 2, 2, 16)
        + b"data"
        + struct.pack("<I", len(pcm))
    )
    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    canonical_path.write_bytes(header + pcm)
    normalized = parse_wav_pcm(canonical_path)
    if normalized["pcmSha256"] != info["pcmSha256"] or normalized["samples"] != info["samples"]:
        raise AudioBuildError("header-only WAV canonicalization changed its PCM payload")
    strict_decode(canonical_path)
    return {
        "rawSha256": sha256_file(raw_path),
        "rawPcmSha256": info["pcmSha256"],
        "rawBytes": info["rawBytes"],
        "rawDeclaredRiffBytes": info["declaredRiffBytes"],
        "rawDeclaredDataBytes": info["declaredDataBytes"],
        "rawHeaderMatchesPhysicalPayload": info["headerMatchesPhysicalPayload"],
        "canonicalSha256": sha256_file(canonical_path),
        "canonicalPcmSha256": normalized["pcmSha256"],
        "pcmHashUnchanged": True,
        "samplesAt24k": info["samples"],
        "secondsAt24k": info["samples"] / RAW_RATE,
        "strictDecode": "passed",
    }


def strict_decode(path: Path) -> None:
    executable = shutil.which("ffmpeg")
    if executable is None:
        raise AudioBuildError("ffmpeg is required to decode/canonicalize WAV assets")
    result = subprocess.run(
        [executable, "-hide_banner", "-loglevel", "error", "-xerror", "-i", str(path), "-f", "null", "-"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode:
        raise AudioBuildError(f"strict ffmpeg decode failed for {path.name} (exit {result.returncode})")


def resample_48k(canonical_path: Path, cue_path: Path) -> dict[str, Any]:
    executable = shutil.which("ffmpeg")
    if executable is None:
        raise AudioBuildError("ffmpeg is required to resample narration cues")
    cue_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            executable, "-hide_banner", "-loglevel", "error", "-xerror", "-y",
            "-i", str(canonical_path), "-ar", str(SAMPLE_RATE), "-ac", "1",
            "-c:a", "pcm_s16le", str(cue_path),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode:
        raise AudioBuildError(f"ffmpeg resample failed for {canonical_path.name} (exit {result.returncode})")
    strict_decode(cue_path)
    with wave.open(str(cue_path), "rb") as wav:
        if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) != (SAMPLE_RATE, 1, 2):
            raise AudioBuildError(f"resampled cue has unexpected PCM format: {cue_path.name}")
        sample_count = wav.getnframes()
    if sample_count <= 0:
        raise AudioBuildError(f"resampled cue is empty: {cue_path.name}")
    return {
        "cue48kSha256": sha256_file(cue_path),
        "samplesAt48k": sample_count,
        "secondsAt48k": sample_count / SAMPLE_RATE,
        "strictDecode": "passed",
    }


def collect_identity_values(obj: Any, names: set[str]) -> list[str]:
    values: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            normalized = key.casefold().replace("-", "_")
            if normalized in names:
                if isinstance(value, str):
                    values.append(value)
                elif isinstance(value, dict):
                    for nested in ("id", "value", "name"):
                        if isinstance(value.get(nested), str):
                            values.append(value[nested])
            values.extend(collect_identity_values(value, names))
    elif isinstance(obj, list):
        for value in obj:
            values.extend(collect_identity_values(value, names))
    return values


def effective_identity(response_text: str) -> tuple[str | None, str | None, str]:
    try:
        response = json.loads(response_text)
    except json.JSONDecodeError:
        return None, None, "unknown"
    models = set(collect_identity_values(response, {"model", "model_id", "modelid", "resolved_model"}))
    voices = set(collect_identity_values(response, {"voice", "voice_id", "voiceid", "resolved_voice"}))
    if len(models) != 1 or len(voices) != 1:
        return None, None, "unknown"
    model, voice = next(iter(models)), next(iter(voices))
    # Identity fields are the only response values written to the manifest.
    # Reject arbitrary URLs, tokens, and free-form payloads even in these fields.
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", model) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", voice):
        return None, None, "unknown"
    if model != MODEL or voice != VOICE:
        return model, voice, "mismatch"
    return model, voice, "verified"


def verified_cache(entry: dict[str, Any], raw_path: Path, canonical_path: Path, cue_path: Path) -> bool:
    if entry.get("status") != "verified" or entry.get("effectiveIdentityStatus") != "verified":
        return False
    paths = ((raw_path, "rawSha256"), (canonical_path, "canonicalSha256"), (cue_path, "cue48kSha256"))
    for path, field in paths:
        if not path.is_file() or sha256_file(path) != entry.get(field):
            return False
    return True


def finalize_cached_raw(entry: dict[str, Any], raw_path: Path, canonical_path: Path, cue_path: Path) -> None:
    if entry.get("effectiveIdentityStatus") != "verified":
        raise AudioBuildError(
            f"{entry.get('segmentId', 'segment')} has an unverified effective provider identity; "
            "preserving raw WAV and stopping without resynthesis"
        )
    if entry.get("effectiveModel") != MODEL or entry.get("effectiveVoice") != VOICE:
        raise AudioBuildError(f"{entry.get('segmentId', 'segment')} effective provider identity changed")
    if not raw_path.is_file():
        raise AudioBuildError(f"verified raw WAV is missing for {entry.get('segmentId', 'segment')}")
    if entry.get("rawSha256") and sha256_file(raw_path) != entry["rawSha256"]:
        raise AudioBuildError(f"raw WAV hash changed for {entry.get('segmentId', 'segment')}")
    canonical_meta = canonicalize_wav(raw_path, canonical_path)
    cue_meta = resample_48k(canonical_path, cue_path)
    entry.update(canonical_meta)
    entry.update(cue_meta)
    entry.update({
        "status": "verified",
        "updatedAtUtc": None,
    })


def call_bailian(segment: dict[str, Any], entry: dict[str, Any], raw_path: Path, manifest: dict[str, Any]) -> None:
    if not BL.is_file():
        raise AudioBuildError(f"Bailian CLI is unavailable at the approved path: {BL}")
    text = segment["tts_phonetic_text"]
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix="ep3-v02-", suffix=".txt", delete=False) as temp:
        text_path = Path(temp.name)
        temp.write(text.encode("utf-8"))
    command = [
        str(BL), "speech", "synthesize",
        "--text-file", str(text_path),
        "--voice", VOICE,
        "--model", MODEL,
        "--rate", f"{RATE:g}",
        "--format", "wav",
        "--sample-rate", str(RAW_RATE),
        "--out", str(raw_path),
        "--concurrent", "1",
        "--output", "json",
    ]
    try:
        completed = subprocess.run(command, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError:
        entry["requestStatus"] = "cli_unavailable"
        entry["status"] = "failed"
        write_json(MANIFEST_PATH, manifest)
        raise AudioBuildError("Bailian CLI could not be started; raw command output was not retained") from None
    finally:
        text_path.unlink(missing_ok=True)
    entry["requestExitCode"] = completed.returncode
    if completed.returncode != 0:
        entry["requestStatus"] = "failed"
        entry["status"] = "failed"
        write_json(MANIFEST_PATH, manifest)
        raise AudioBuildError(f"Bailian synthesis failed for {segment['id']} (exit {completed.returncode})")
    if not raw_path.is_file() or raw_path.stat().st_size <= 44:
        entry["requestStatus"] = "succeeded_without_wav"
        entry["status"] = "failed"
        write_json(MANIFEST_PATH, manifest)
        raise AudioBuildError(f"Bailian returned no usable local WAV for {segment['id']}")

    model, voice, identity_status = effective_identity(completed.stdout)
    entry["requestStatus"] = "succeeded"
    entry["effectiveIdentityStatus"] = identity_status
    entry["effectiveModel"] = model
    entry["effectiveVoice"] = voice
    entry["rawSha256"] = sha256_file(raw_path)
    entry["status"] = "identity_unknown" if identity_status == "unknown" else (
        "identity_mismatch" if identity_status == "mismatch" else "raw_saved"
    )
    # Only normalized model/voice fields are persisted. Raw JSON, stderr,
    # credentials, signed URLs and headers are discarded.
    write_json(MANIFEST_PATH, manifest)
    if identity_status == "unknown":
        raise AudioBuildError(
            f"effective model/voice is unknown for {segment['id']}; raw WAV retained and generation stopped"
        )
    if identity_status == "mismatch":
        raise AudioBuildError(
            f"effective model/voice changed for {segment['id']}; raw WAV retained and generation stopped"
        )


def generate_one(segment: dict[str, Any], manifest: dict[str, Any]) -> None:
    segment_id = segment["id"]
    text = segment["tts_phonetic_text"]
    key = cache_key(text)
    raw_path = RAW / f"{key}.wav"
    canonical_path = CANONICAL / f"{key}.wav"
    cue_path = CUES / f"{key}.wav"
    text_hash = sha256_bytes(text.encode("utf-8"))
    entry = manifest["segments"].get(segment_id)
    if entry is not None and (entry.get("cacheKey"), entry.get("textSha256"), entry.get("settings")) != (
        key, text_hash, settings()
    ):
        raise AudioBuildError(f"provider manifest cache identity mismatch for {segment_id}")
    if entry is not None and verified_cache(entry, raw_path, canonical_path, cue_path):
        print(f"{segment_id}: verified cache hit ({entry['samplesAt48k']} samples at 48 kHz)")
        return
    if raw_path.exists() and entry is None:
        raise AudioBuildError(
            f"unverified raw output already exists for {segment_id}; refusing duplicate billed synthesis"
        )
    if entry is None:
        entry = {
            "segmentId": segment_id,
            "cacheKey": key,
            "textSha256": text_hash,
            "settings": settings(),
            "requestStatus": "not_started",
            "effectiveIdentityStatus": "unknown",
            "effectiveModel": None,
            "effectiveVoice": None,
            "status": "pending",
            "rawFile": str(raw_path.relative_to(PROJECT)),
            "canonicalFile": str(canonical_path.relative_to(PROJECT)),
            "cue48kFile": str(cue_path.relative_to(PROJECT)),
        }
        manifest["segments"][segment_id] = entry
    if not raw_path.exists() and entry.get("requestStatus") not in {"succeeded", "succeeded_without_wav"}:
        entry["requestStatus"] = "in_progress"
        entry["status"] = "in_progress"
        write_json(MANIFEST_PATH, manifest)
        call_bailian(segment, entry, raw_path, manifest)
    elif not raw_path.exists():
        raise AudioBuildError(f"provider cache has no raw WAV for {segment_id}; refusing to synthesize again")
    if entry.get("effectiveIdentityStatus") != "verified":
        raise AudioBuildError(
            f"effective provider identity is {entry.get('effectiveIdentityStatus', 'unknown')} for {segment_id}; "
            "raw WAV retained and generation stopped"
        )
    if entry.get("rawSha256") and sha256_file(raw_path) != entry["rawSha256"]:
        raise AudioBuildError(f"raw WAV hash mismatch for {segment_id}")
    canonical_meta = canonicalize_wav(raw_path, canonical_path)
    cue_meta = resample_48k(canonical_path, cue_path)
    entry.update(canonical_meta)
    entry.update(cue_meta)
    entry["status"] = "verified"
    write_json(MANIFEST_PATH, manifest)
    print(f"{segment_id}: generated and verified ({cue_meta['samplesAt48k']} samples at 48 kHz)")


def audit(manifest: dict[str, Any], segments: list[dict[str, Any]]) -> int:
    issues: list[str] = []
    entries = manifest["segments"]
    for segment in segments:
        segment_id = segment["id"]
        entry = entries.get(segment_id)
        if entry is None:
            issues.append(f"{segment_id}: missing provider cache")
            continue
        key = cache_key(segment["tts_phonetic_text"])
        if entry.get("cacheKey") != key or entry.get("textSha256") != sha256_bytes(segment["tts_phonetic_text"].encode("utf-8")):
            issues.append(f"{segment_id}: cache key/text hash mismatch")
            continue
        raw = RAW / f"{key}.wav"
        canonical = CANONICAL / f"{key}.wav"
        cue = CUES / f"{key}.wav"
        if entry.get("effectiveIdentityStatus") != "verified":
            issues.append(f"{segment_id}: effective provider identity {entry.get('effectiveIdentityStatus', 'unknown')}")
            continue
        if entry.get("effectiveModel") != MODEL or entry.get("effectiveVoice") != VOICE:
            issues.append(f"{segment_id}: effective model/voice mismatch")
            continue
        try:
            if not verified_cache(entry, raw, canonical, cue):
                issues.append(f"{segment_id}: cache file missing or hash/format check failed")
                continue
            canonical_info = parse_wav_pcm(canonical)
            strict_decode(canonical)
            strict_decode(cue)
            with wave.open(str(cue), "rb") as wav:
                actual_samples = wav.getnframes()
                actual_format = (wav.getframerate(), wav.getnchannels(), wav.getsampwidth())
            if canonical_info["samples"] != entry.get("samplesAt24k"):
                issues.append(f"{segment_id}: 24 kHz sample count mismatch")
            elif actual_samples != entry.get("samplesAt48k") or actual_format != (SAMPLE_RATE, 1, 2):
                issues.append(f"{segment_id}: 48 kHz sample count/format mismatch")
            else:
                print(f"{segment_id}: verified, {actual_samples} actual samples at 48 kHz")
        except (AudioBuildError, OSError, wave.Error) as exc:
            issues.append(f"{segment_id}: {exc}")
    print(json.dumps({"mode": "audit", "issues": issues, "segmentCount": len(segments)}, ensure_ascii=False, indent=2))
    return 1 if issues else 0


def load_numpy() -> Any | None:
    try:
        import numpy as np
        return np
    except ImportError:
        return None


def pcm16_array(payload: bytes) -> array.array:
    values = array.array("h")
    values.frombytes(payload)
    if sys.byteorder != "little":
        values.byteswap()
    return values


def read_cue(path: Path, entry: dict[str, Any]) -> array.array:
    with wave.open(str(path), "rb") as wav:
        if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) != (SAMPLE_RATE, 1, 2):
            raise AudioBuildError(f"cue has unexpected PCM format: {path.name}")
        count = wav.getnframes()
        raw = wav.readframes(count)
    if count != entry.get("samplesAt48k") or len(raw) != count * 2:
        raise AudioBuildError(f"cue sample count differs from provider manifest: {path.name}")
    return pcm16_array(raw)


def find_natural_gap(samples: array.array, target: int) -> tuple[int, int, float]:
    """Find a real low-energy interval that contains the absolute S08 split."""
    window = 480  # 10 ms at 48 kHz
    hop = 240  # 5 ms search resolution
    minimum_run = 4_800  # 100 ms, including the anchor
    threshold_rms = 280.0  # approximately -41.4 dBFS for PCM16
    if target <= 0 or target >= len(samples):
        raise AudioBuildError("NEEDS_SOL: S08 does not span the absolute-silence anchor")
    quiet: list[bool] = []
    for start in range(0, max(0, len(samples) - window + 1), hop):
        energy = 0
        for value in samples[start:start + window]:
            energy += value * value
        quiet.append(math.sqrt(energy / window) <= threshold_rms)
    runs: list[tuple[int, int, float]] = []
    index = 0
    while index < len(quiet):
        if not quiet[index]:
            index += 1
            continue
        first = index
        while index + 1 < len(quiet) and quiet[index + 1]:
            index += 1
        last = index
        start_sample = first * hop
        end_sample = min(len(samples), last * hop + window)
        if end_sample - start_sample >= minimum_run and start_sample <= target <= end_sample:
            runs.append((start_sample, end_sample, (end_sample - start_sample) / SAMPLE_RATE))
        index += 1
    if not runs:
        raise AudioBuildError(
            "NEEDS_SOL: S08 has no natural low-energy PCM interval spanning the frame-6000 silence anchor; "
            "no speech was cut or time-stretched"
        )
    return min(runs, key=lambda run: abs((run[0] + run[1]) // 2 - target))


def caption_weight(text: str) -> float:
    count = sum(1 for char in text if "\u3400" <= char <= "\u9fff")
    count += sum(0.55 for char in text if char.isascii() and char.isalnum())
    count += sum(0.65 for char in text if char in "，。；：？！、,.!?;:")
    return max(1.0, count)


def weighted_frame_boundaries(start: int, length: int, chunks: list[str]) -> list[int]:
    weights = [caption_weight(chunk) for chunk in chunks]
    total = sum(weights)
    if length < len(chunks):
        raise AudioBuildError("measured narration duration is too short for non-empty caption windows")
    boundaries = [start]
    cumulative = 0.0
    for weight in weights[:-1]:
        cumulative += weight
        boundary = start + round(length * cumulative / total)
        lower = boundaries[-1] + 1
        upper = start + length - (len(chunks) - len(boundaries))
        boundaries.append(max(lower, min(upper, boundary)))
    boundaries.append(start + length)
    return boundaries


def chunk_windows(
    segment: dict[str, Any],
    segment_start_sample: int,
    ordinary_samples: int,
    *,
    s08_prefix_samples: int | None = None,
    s08_suffix_samples: int | None = None,
) -> list[dict[str, Any]]:
    chunks = segment["chunks"]
    segment_id = segment["id"]
    if "".join(chunks) != segment["display_subtitle"]:
        raise AudioBuildError(f"{segment_id} chunks do not reproduce the display subtitle exactly")
    for index, chunk in enumerate(chunks, start=1):
        if not isinstance(chunk, str) or not chunk.strip():
            raise AudioBuildError(f"{segment_id} caption chunk {index} is empty")
        if sum(1 for char in chunk if "\u3400" <= char <= "\u9fff") > 14:
            raise AudioBuildError(f"{segment_id} caption chunk {index} exceeds 14 Chinese characters")
    windows: list[dict[str, Any]] = []
    if s08_prefix_samples is None or s08_suffix_samples is None:
        total_frames = max(1, math.ceil(ordinary_samples / SAMPLES_PER_FRAME))
        boundaries = weighted_frame_boundaries(0, total_frames, chunks)
        for index, chunk in enumerate(chunks):
            start_sample = segment_start_sample + boundaries[index] * SAMPLES_PER_FRAME
            end_sample = min(
                segment_start_sample + ordinary_samples,
                segment_start_sample + boundaries[index + 1] * SAMPLES_PER_FRAME,
            )
            windows.append({
                "id": f"{segment_id}-C{index + 1:02d}",
                "segmentId": segment_id,
                "startFrame": start_sample // SAMPLES_PER_FRAME,
                "endFrame": max(start_sample // SAMPLES_PER_FRAME + 1, math.ceil(end_sample / SAMPLES_PER_FRAME)),
                "text": chunk,
            })
        return windows

    if len(chunks) < 2:
        raise AudioBuildError("S08 needs at least two caption chunks around its silence break")
    weights = [caption_weight(chunk) for chunk in chunks]
    all_weight = sum(weights)
    before_ratio = s08_prefix_samples / max(1, s08_prefix_samples + s08_suffix_samples)
    split_chunk = min(
        range(1, len(chunks)),
        key=lambda count: abs(sum(weights[:count]) / all_weight - before_ratio),
    )
    anchor_frame = 6_000
    resume_frame = 6_020
    prefix_frames = max(split_chunk, round((s08_prefix_samples / SAMPLE_RATE) * FPS))
    prefix_frames = min(prefix_frames, anchor_frame - segment_start_sample // SAMPLES_PER_FRAME)
    suffix_frames = max(len(chunks) - split_chunk, round((s08_suffix_samples / SAMPLE_RATE) * FPS))
    suffix_frames = min(suffix_frames, int(segment["endFrame"]) - resume_frame)
    if suffix_frames < len(chunks) - split_chunk:
        raise AudioBuildError("S08 caption phrase estimates do not fit after the silence window")
    before = weighted_frame_boundaries(
        segment_start_sample // SAMPLES_PER_FRAME,
        prefix_frames,
        chunks[:split_chunk],
    )
    after = weighted_frame_boundaries(resume_frame, suffix_frames, chunks[split_chunk:])
    for index, chunk in enumerate(chunks):
        if index < split_chunk:
            start_frame, end_frame = before[index], before[index + 1]
        else:
            local_index = index - split_chunk
            start_frame, end_frame = after[local_index], after[local_index + 1]
        windows.append({
            "id": f"{segment_id}-C{index + 1:02d}",
            "segmentId": segment_id,
            "startFrame": start_frame,
            "endFrame": end_frame,
            "text": chunk,
        })
    return windows


def write_mono_narration(samples: array.array, output_path: Path) -> None:
    mono_temp = output_path.with_name("narration-mono.tmp.wav")
    stereo_temp = output_path.with_name("narration-stereo.tmp.wav")
    mono_temp.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(mono_temp), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        if sys.byteorder == "little":
            wav.writeframes(samples.tobytes())
        else:
            samples.byteswap()
            wav.writeframes(samples.tobytes())
            samples.byteswap()
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        mono_temp.unlink(missing_ok=True)
        raise AudioBuildError("ffmpeg is required to write the stereo narration stem")
    result = subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-xerror", "-y", "-i", str(mono_temp),
            "-af", "pan=stereo|FL=FC|FR=FC", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(stereo_temp),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    mono_temp.unlink(missing_ok=True)
    if result.returncode:
        stereo_temp.unlink(missing_ok=True)
        raise AudioBuildError(f"ffmpeg stereo narration conversion failed (exit {result.returncode})")
    validate_stem(stereo_temp, expected_channels=2)
    stereo_temp.replace(output_path)


def validate_stem(path: Path, *, expected_channels: int = 2) -> dict[str, Any]:
    strict_decode(path)
    with wave.open(str(path), "rb") as wav:
        actual = (wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getnframes())
    expected = (SAMPLE_RATE, expected_channels, 2, TOTAL_SAMPLES)
    if actual != expected:
        raise AudioBuildError(f"{path.name} must be 48 kHz stereo PCM16 with {TOTAL_SAMPLES} frames; got {actual}")
    return {
        "file": str(path.relative_to(PROJECT)),
        "sha256": sha256_file(path),
        "sampleRate": actual[0],
        "channels": actual[1],
        "sampleWidthBytes": actual[2],
        "samplesPerChannel": actual[3],
        "strictDecode": "passed",
    }


def absolute_silence_peak(path: Path, start_sample: int = 4_800_000, end_sample: int = 4_816_000) -> int:
    peak = 0
    with wave.open(str(path), "rb") as wav:
        if wav.getframerate() != SAMPLE_RATE or wav.getnchannels() != 2 or wav.getsampwidth() not in (2, 3):
            raise AudioBuildError(f"cannot inspect absolute-silence window in {path.name}")
        wav.setpos(start_sample)
        remaining = end_sample - start_sample
        while remaining:
            count = min(24_000, remaining)
            raw = wav.readframes(count)
            if wav.getsampwidth() == 2:
                values = pcm16_array(raw)
                block_peak = max((abs(value) for value in values), default=0)
            else:
                block_peak = 0
                for offset in range(0, len(raw), 3):
                    sample = int.from_bytes(raw[offset:offset + 3], "little", signed=False)
                    if sample & 0x800000:
                        sample -= 0x1000000
                    block_peak = max(block_peak, abs(sample))
            peak = max(peak, block_peak)
            remaining -= count
    return peak


def synthesize_score_values(start: int, count: int, np: Any | None) -> tuple[Any, Any]:
    if np is not None:
        indices = np.arange(start, start + count, dtype=np.float64)
        time = indices / SAMPLE_RATE
        roots = np.array([73.416, 65.406, 98.0, 58.270], dtype=np.float64)
        chord = roots[(np.floor(time / 24.0).astype(np.int64)) % len(roots)]
        bed = (
            0.042 * np.sin(2 * np.pi * chord * time)
            + 0.027 * np.sin(2 * np.pi * chord * 1.189207 * time + 0.2)
            + 0.022 * np.sin(2 * np.pi * chord * 1.498307 * time + 0.5)
            + 0.016 * np.sin(2 * np.pi * chord * 2.0 * time)
            + 0.018 * np.sin(2 * np.pi * (chord / 2.0) * time + 0.7)
        )
        beat_phase = np.mod(time, 0.8)
        beat_number = np.floor(time / 0.8).astype(np.int64)
        notes = np.array([293.66, 349.23, 440.0, 523.25, 440.0, 349.23, 261.63, 329.63])
        note = notes[beat_number % len(notes)]
        pluck = 0.014 * np.sin(2 * np.pi * note * time) * np.exp(-beat_phase * 4.2)
        slow = 0.78 + 0.22 * np.sin(2 * np.pi * time / 19.0)
        left = (bed + pluck) * slow
        right = (bed + pluck * 0.94) * (0.8 + 0.2 * np.sin(2 * np.pi * time / 23.0 + 0.4))
        mute = (indices >= 4_800_000) & (indices < 4_816_000)
        left[mute] = 0.0
        right[mute] = 0.0
        return left, right

    left: list[float] = []
    right: list[float] = []
    roots = (73.416, 65.406, 98.0, 58.270)
    notes = (293.66, 349.23, 440.0, 523.25, 440.0, 349.23, 261.63, 329.63)
    for index in range(start, start + count):
        if 4_800_000 <= index < 4_816_000:
            left.append(0.0)
            right.append(0.0)
            continue
        time = index / SAMPLE_RATE
        root = roots[int(time / 24.0) % len(roots)]
        bed = (
            0.042 * math.sin(2 * math.pi * root * time)
            + 0.027 * math.sin(2 * math.pi * root * 1.189207 * time + 0.2)
            + 0.022 * math.sin(2 * math.pi * root * 1.498307 * time + 0.5)
            + 0.016 * math.sin(2 * math.pi * root * 2.0 * time)
            + 0.018 * math.sin(2 * math.pi * root / 2.0 * time + 0.7)
        )
        beat_phase = time % 0.8
        note = notes[int(time / 0.8) % len(notes)]
        pluck = 0.014 * math.sin(2 * math.pi * note * time) * math.exp(-beat_phase * 4.2)
        left.append((bed + pluck) * (0.78 + 0.22 * math.sin(2 * math.pi * time / 19.0)))
        right.append((bed + pluck * 0.94) * (0.8 + 0.2 * math.sin(2 * math.pi * time / 23.0 + 0.4)))
    return left, right


def smooth_noise(count: int, seed: int, np: Any | None) -> Any:
    rng = random.Random(seed)
    if np is not None:
        step = 240  # 5 ms grains, then a low-pass pass below 1 kHz
        values = np.repeat(np.asarray([rng.uniform(-1.0, 1.0) for _ in range((count + step - 1) // step)]), step)[:count]
        filtered = np.empty(count, dtype=np.float64)
        state = 0.0
        coefficient = 0.11
        for index, value in enumerate(values):
            state += coefficient * (float(value) - state)
            filtered[index] = state
        return filtered
    values = [rng.uniform(-1.0, 1.0) for _ in range((count + 239) // 240)]
    result: list[float] = []
    state = 0.0
    coefficient = 0.11
    for index in range(count):
        target = values[index // 240]
        state += coefficient * (target - state)
        result.append(state)
    return result


def event_wave_python(event_id: str, count: int, seed: int) -> list[float]:
    duration = count / SAMPLE_RATE
    time = [index / SAMPLE_RATE for index in range(count)]
    rng = random.Random(seed)
    noise = None
    if event_id in {"mortality-reset", "zero-copy-fork", "golden-lock-click", "mobius-glitch"}:
        held = [rng.uniform(-1.0, 1.0) for _ in range((count + 239) // 240)]
        noise = []
        state = 0.0
        for index in range(count):
            state += 0.11 * (held[index // 240] - state)
            noise.append(state)

    def oscillator(frequency: float, phase: float = 0.0) -> list[float]:
        return [math.sin(2 * math.pi * frequency * value + phase) for value in time]

    def sweep(start_hz: float, end_hz: float) -> list[float]:
        return [
            math.sin(2 * math.pi * (start_hz * value + 0.5 * (end_hz - start_hz) * value * value / duration))
            for value in time
        ]

    def decay(rate: float) -> list[float]:
        return [math.exp(-rate * value) for value in time]

    if event_id == "isolated-sonar":
        env = decay(2.7)
        return [0.11 * value * gain for value, gain in zip(oscillator(400.0), env)]
    if event_id == "mortality-reset":
        env = decay(7.0)
        tone = oscillator(54.0)
        return [(0.13 * value + 0.035 * n) * gain for value, n, gain in zip(tone, noise, env)]
    if event_id == "cyan-scan":
        env = [(1.0 - value / duration) * math.exp(-0.55 * value) for value in time]
        bass, laser = oscillator(45.0), sweep(190.0, 780.0)
        return [(0.055 * low + 0.07 * high) * gain for low, high, gain in zip(bass, laser, env)]
    if event_id == "zero-copy-fork":
        env = decay(1.55)
        grain, tone, pulse = noise, oscillator(620.0), oscillator(6.0)
        return [
            (0.085 * n * (0.55 + 0.45 * p ** 2) + 0.035 * t) * gain
            for n, t, p, gain in zip(grain, tone, pulse, env)
        ]
    if event_id == "pruning-wave":
        result = [0.0] * count
        for tone_index, start in enumerate((0.0, 0.24, 0.49, 0.76, 1.05)):
            frequency = 500.0 + tone_index * 78.0
            for index, value in enumerate(time):
                if value < start:
                    continue
                local = value - start
                result[index] += 0.035 * math.sin(2 * math.pi * frequency * value + tone_index * 0.53) * math.exp(-3.0 * local)
        return result
    if event_id == "babel-collision":
        env = decay(2.7)
        tones = (oscillator(315.0), oscillator(337.0, 0.4), oscillator(485.0, 1.0))
        return [(0.06 * a + 0.05 * b + 0.035 * c) * gain for a, b, c, gain in zip(*tones, env)]
    if event_id == "optical-lock":
        pulse = oscillator(1.2)
        tones = (oscillator(220.0), oscillator(329.63, 0.3), oscillator(440.0, 0.8), oscillator(659.25, 1.2))
        return [
            0.045 * (a + b + c + 0.55 * d) * (0.78 + 0.22 * p) * (0.7 + 0.3 * min(1.0, value / max(0.1, duration * 0.2)))
            for a, b, c, d, p, value in zip(*tones, pulse, time)
        ]
    if event_id == "shepard-rise":
        result = [0.0] * count
        for octave in range(4):
            f0 = 55.0 * (2 ** octave)
            tone = sweep(f0, f0 * 2.0)
            for index, (value, progress) in enumerate(zip(tone, time)):
                result[index] += 0.028 * value * (0.5 + 0.5 * math.cos(2 * math.pi * progress / duration))
        return result
    if event_id == "golden-lock-click":
        env, tone = decay(75.0), oscillator(760.0)
        return [(0.14 * value + 0.035 * n) * gain for value, n, gain in zip(tone, noise, env)]
    if event_id == "shimmer-tail":
        env = decay(1.25)
        tones = (oscillator(493.88), oscillator(587.33, 0.4), oscillator(739.99, 0.8), oscillator(880.0, 1.1))
        return [(0.028 * a + 0.026 * b + 0.022 * c + 0.018 * d) * gain for a, b, c, d, gain in zip(*tones, env)]
    if event_id == "mobius-glitch":
        env = decay(5.0)
        tones = (oscillator(73.42), oscillator(220.0, 0.5))
        return [
            (1.0 if value < min(0.24, duration / 2) else -1.0)
            * (0.08 * a + 0.04 * b + 0.035 * n) * gain
            for a, b, n, gain, value in zip(*tones, noise, env, time)
        ]
    raise AudioBuildError(f"no deterministic SFX recipe for event {event_id}")


def event_wave(event_id: str, count: int, seed: int, np: Any | None) -> Any:
    if np is None:
        return event_wave_python(event_id, count, seed)
    duration = count / SAMPLE_RATE
    if np is not None:
        time = np.arange(count, dtype=np.float64) / SAMPLE_RATE
        exp = np.exp
        sin = np.sin
    else:
        time = [index / SAMPLE_RATE for index in range(count)]
        exp = math.exp
        sin = math.sin

    def oscillator(frequency: float, phase: float = 0.0) -> Any:
        if np is not None:
            return np.sin(2 * np.pi * frequency * time + phase)
        return [math.sin(2 * math.pi * frequency * value + phase) for value in time]

    def tone_sweep(start_hz: float, end_hz: float) -> Any:
        if np is not None:
            phase = 2 * np.pi * (start_hz * time + 0.5 * (end_hz - start_hz) * time * time / duration)
            return np.sin(phase)
        return [math.sin(2 * math.pi * (start_hz * value + 0.5 * (end_hz - start_hz) * value * value / duration)) for value in time]

    noise = None
    if event_id in {"mortality-reset", "zero-copy-fork", "golden-lock-click", "mobius-glitch"}:
        noise = smooth_noise(count, seed, np)
    if event_id == "isolated-sonar":
        envelope = exp(-2.7 * time)
        return 0.11 * oscillator(400.0) * envelope
    if event_id == "mortality-reset":
        envelope = exp(-7.0 * time)
        return 0.13 * oscillator(54.0) * envelope + 0.035 * noise * envelope
    if event_id == "cyan-scan":
        envelope = (1.0 - time / duration) * exp(-0.55 * time)
        return 0.055 * oscillator(45.0) * envelope + 0.07 * tone_sweep(190.0, 780.0) * envelope
    if event_id == "zero-copy-fork":
        gate = 0.55 + 0.45 * (oscillator(6.0) ** 2)
        envelope = exp(-1.55 * time)
        return 0.085 * noise * gate * envelope + 0.035 * oscillator(620.0) * envelope
    if event_id == "pruning-wave":
        result = [0.0] * count if np is None else np.zeros(count, dtype=np.float64)
        for index, start in enumerate((0.0, 0.24, 0.49, 0.76, 1.05)):
            local = [max(0.0, value - start) for value in time] if np is None else np.maximum(0.0, time - start)
            envelope = exp(-3.0 * local)
            frequency = 500.0 + index * 78.0
            result += 0.035 * oscillator(frequency, index * 0.53) * envelope * (time >= start)
        return result
    if event_id == "babel-collision":
        envelope = exp(-2.7 * time)
        return envelope * (0.06 * oscillator(315.0) + 0.05 * oscillator(337.0, 0.4) + 0.035 * oscillator(485.0, 1.0))
    if event_id == "optical-lock":
        pulse = 0.78 + 0.22 * oscillator(1.2)
        envelope = 0.7 + 0.3 * np.minimum(1.0, time / max(0.1, duration * 0.2)) if np is not None else [0.7 + 0.3 * min(1.0, value / max(0.1, duration * 0.2)) for value in time]
        return 0.045 * (oscillator(220.0) + oscillator(329.63, 0.3) + oscillator(440.0, 0.8) + 0.55 * oscillator(659.25, 1.2)) * pulse * envelope
    if event_id == "shepard-rise":
        progress = time / duration
        total = [0.0] * count if np is None else np.zeros(count, dtype=np.float64)
        for octave in range(4):
            f0 = 55.0 * (2 ** octave)
            f1 = f0 * 2.0
            total += 0.028 * tone_sweep(f0, f1) * (0.5 + 0.5 * np.cos(2 * np.pi * progress) if np is not None else [0.5 + 0.5 * math.cos(2 * math.pi * value) for value in progress])
        return total
    if event_id == "golden-lock-click":
        envelope = exp(-75.0 * time)
        return 0.14 * oscillator(760.0) * envelope + 0.035 * noise * envelope
    if event_id == "shimmer-tail":
        envelope = exp(-1.25 * time)
        return envelope * (0.028 * oscillator(493.88) + 0.026 * oscillator(587.33, 0.4) + 0.022 * oscillator(739.99, 0.8) + 0.018 * oscillator(880.0, 1.1))
    if event_id == "mobius-glitch":
        flip = np.where(time < min(0.24, duration / 2), 1.0, -1.0)
        envelope = exp(-5.0 * time)
        return flip * envelope * (0.08 * oscillator(73.42) + 0.04 * oscillator(220.0, 0.5) + 0.035 * noise)
    raise AudioBuildError(f"no deterministic SFX recipe for event {event_id}")


def write_stereo_values(wav: wave.Wave_write, left: Any, right: Any, np: Any | None) -> None:
    if np is not None:
        interleaved = np.empty((len(left), 2), dtype=np.int16)
        interleaved[:, 0] = np.rint(np.clip(left, -0.96, 0.96) * 32767).astype(np.int16)
        interleaved[:, 1] = np.rint(np.clip(right, -0.96, 0.96) * 32767).astype(np.int16)
        wav.writeframesraw(interleaved.astype("<i2", copy=False).tobytes())
        return
    output = array.array("h")
    for lval, rval in zip(left, right):
        output.append(max(-32768, min(32767, round(max(-0.96, min(0.96, lval)) * 32767))))
        output.append(max(-32768, min(32767, round(max(-0.96, min(0.96, rval)) * 32767))))
    if sys.byteorder == "little":
        wav.writeframesraw(output.tobytes())
    else:
        output.byteswap()
        wav.writeframesraw(output.tobytes())


def render_score(path: Path, np: Any | None) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        for start in range(0, TOTAL_SAMPLES, SAMPLE_RATE):
            count = min(SAMPLE_RATE, TOTAL_SAMPLES - start)
            left, right = synthesize_score_values(start, count, np)
            write_stereo_values(wav, left, right, np)
    result = validate_stem(path)
    if absolute_silence_peak(path) != 0:
        raise AudioBuildError("score stem is not exactly zero for samples [4800000,4816000)")
    return result


def load_sfx_events() -> list[dict[str, Any]]:
    data = load_json(SFX_EVENTS_PATH)
    if (data.get("fps"), data.get("sample_rate")) != (FPS, SAMPLE_RATE):
        raise AudioBuildError("sfx_events.json must use 60 fps and 48 kHz")
    events = data.get("events")
    if not isinstance(events, list):
        raise AudioBuildError("sfx_events.json has no event list")
    ids: set[str] = set()
    for event in events:
        event_id = event.get("id")
        frame = event.get("frame")
        if not isinstance(event_id, str) or event_id in ids:
            raise AudioBuildError("SFX event IDs must be unique strings")
        ids.add(event_id)
        if not isinstance(frame, int) or event.get("sample") != frame * SAMPLES_PER_FRAME:
            raise AudioBuildError(f"SFX event sample/frame mapping mismatch for {event_id}")
    required = {
        "isolated-sonar", "mortality-reset", "cyan-scan", "zero-copy-fork", "pruning-wave",
        "babel-collision", "optical-lock", "shepard-rise", "absolute-silence",
        "golden-lock-click", "shimmer-tail", "mobius-glitch",
    }
    if ids != required:
        raise AudioBuildError(f"SFX event set differs from the approved EP3 v02 map: {sorted(ids ^ required)}")
    silence = next(event for event in events if event["id"] == "absolute-silence")
    if (silence.get("frame"), silence.get("endFrame"), silence.get("sample"), silence.get("endSample")) != (
        6_000, 6_020, 4_800_000, 4_816_000
    ):
        raise AudioBuildError("absolute-silence event must remain [frame 6000, frame 6020)")
    return events


def event_duration_samples(event_id: str, frame: int, event_map: dict[str, Any]) -> int:
    if event_id == "absolute-silence":
        return (event_map["endFrame"] - frame) * SAMPLES_PER_FRAME
    if event_id == "shepard-rise":
        return (6_000 - frame) * SAMPLES_PER_FRAME
    seconds = {
        "isolated-sonar": 1.2,
        "mortality-reset": 0.8,
        "cyan-scan": 1.3,
        "zero-copy-fork": 1.8,
        "pruning-wave": 2.4,
        "babel-collision": 1.4,
        "optical-lock": 2.5,
        "golden-lock-click": 0.08,
        "shimmer-tail": 1.8,
        "mobius-glitch": 0.6,
    }[event_id]
    return round(seconds * SAMPLE_RATE)


def render_sfx(path: Path, mapping_path: Path, np: Any | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_events = load_sfx_events()
    mapped: list[dict[str, Any]] = []
    for event in source_events:
        frame = event["frame"]
        start = event["sample"]
        duration = event_duration_samples(event["id"], frame, event)
        if start < 0 or start + duration > TOTAL_SAMPLES:
            raise AudioBuildError(f"SFX event exceeds the master sample range: {event['id']}")
        seed = int(hashlib.sha256(event["id"].encode("utf-8")).hexdigest()[:8], 16)
        values = None if event["id"] == "absolute-silence" else event_wave(event["id"], duration, seed, np)
        pan = {
            "isolated-sonar": (0.82, 0.82),
            "mortality-reset": (0.84, 0.78),
            "cyan-scan": (0.83, 0.62),
            "zero-copy-fork": (0.66, 0.86),
            "pruning-wave": (0.78, 0.88),
            "babel-collision": (0.84, 0.74),
            "optical-lock": (0.80, 0.86),
            "shepard-rise": (0.82, 0.82),
            "golden-lock-click": (0.88, 0.80),
            "shimmer-tail": (0.72, 0.88),
            "mobius-glitch": (0.84, -0.84),
        }.get(event["id"], (0.0, 0.0))
        mapped.append({
            "id": event["id"],
            "frame": frame,
            "sampleIndex": start,
            "declaredSample": event["sample"],
            "mappingErrorSamples": start - event["sample"],
            "endSampleExclusive": start + duration,
            "durationSamples": duration,
            "type": event["type"],
            "deterministicSeed": seed,
            "leftGain": pan[0],
            "rightGain": pan[1],
            "waveform": values,
        })

    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        chunk_size = SAMPLE_RATE
        for block_start in range(0, TOTAL_SAMPLES, chunk_size):
            block_count = min(chunk_size, TOTAL_SAMPLES - block_start)
            if np is not None:
                left = np.zeros(block_count, dtype=np.float64)
                right = np.zeros(block_count, dtype=np.float64)
            else:
                left = [0.0] * block_count
                right = [0.0] * block_count
            block_end = block_start + block_count
            for event in mapped:
                waveform = event["waveform"]
                if waveform is None:
                    continue
                overlap_start = max(block_start, event["sampleIndex"])
                overlap_end = min(block_end, event["endSampleExclusive"])
                if overlap_start >= overlap_end:
                    continue
                source_start = overlap_start - event["sampleIndex"]
                dest_start = overlap_start - block_start
                length = overlap_end - overlap_start
                source_slice = waveform[source_start:source_start + length]
                if np is not None:
                    left[dest_start:dest_start + length] += source_slice * event["leftGain"]
                    right[dest_start:dest_start + length] += source_slice * event["rightGain"]
                else:
                    for offset, value in enumerate(source_slice):
                        left[dest_start + offset] += value * event["leftGain"]
                        right[dest_start + offset] += value * event["rightGain"]
            silence_start, silence_end = 4_800_000, 4_816_000
            mute_start = max(block_start, silence_start)
            mute_end = min(block_end, silence_end)
            if mute_start < mute_end:
                local_start, local_end = mute_start - block_start, mute_end - block_start
                if np is not None:
                    left[local_start:local_end] = 0.0
                    right[local_start:local_end] = 0.0
                else:
                    for index in range(local_start, local_end):
                        left[index] = 0.0
                        right[index] = 0.0
            write_stereo_values(wav, left, right, np)
    for event in mapped:
        event.pop("waveform")
    write_json(mapping_path, {
        "fps": FPS,
        "sampleRate": SAMPLE_RATE,
        "samplesPerFrame": SAMPLES_PER_FRAME,
        "eventMapping": mapped,
        "absoluteSilence": {
            "startSample": 4_800_000,
            "endSampleExclusive": 4_816_000,
            "frames": [6_000, 6_020],
            "exactlyZero": True,
        },
    })
    result = validate_stem(path)
    if absolute_silence_peak(path) != 0:
        raise AudioBuildError("SFX stem is not exactly zero for samples [4800000,4816000)")
    return result, mapped


def require_verified_caches(segments: list[dict[str, Any]], manifest: dict[str, Any]) -> dict[str, tuple[array.array, dict[str, Any]]]:
    missing: list[str] = []
    cues: dict[str, tuple[array.array, dict[str, Any]]] = {}
    for segment in segments:
        segment_id = segment["id"]
        entry = manifest["segments"].get(segment_id)
        if entry is None or not verified_cache(
            entry,
            RAW / f"{cache_key(segment['tts_phonetic_text'])}.wav",
            CANONICAL / f"{cache_key(segment['tts_phonetic_text'])}.wav",
            CUES / f"{cache_key(segment['tts_phonetic_text'])}.wav",
        ):
            missing.append(segment_id)
            continue
        if entry.get("effectiveModel") != MODEL or entry.get("effectiveVoice") != VOICE:
            missing.append(segment_id)
            continue
        cue_path = CUES / f"{entry['cacheKey']}.wav"
        cues[segment_id] = (read_cue(cue_path, entry), entry)
    if missing:
        raise AudioBuildError(
            "--mix requires verified, hash-matching provider caches for every segment; missing/invalid: "
            + ", ".join(missing)
            + ". Run --generate for approved IDs first; --mix never starts TTS."
        )
    return cues


def build_narration(segments: list[dict[str, Any]], cues: dict[str, tuple[array.array, dict[str, Any]]]) -> tuple[dict[str, Any], dict[str, Any]]:
    narration = array.array("h", [0]) * TOTAL_SAMPLES
    timing_segments: list[dict[str, Any]] = []
    captions: list[dict[str, Any]] = []
    previous_end_sample = 0
    for segment in segments:
        segment_id = segment["id"]
        cue, entry = cues[segment_id]
        segment_start_frame = int(segment["startFrame"])
        segment_end_frame = int(segment["endFrame"])
        start_frame = segment_start_frame + VOICE_ONSET_DELAY_FRAMES
        start_sample = start_frame * SAMPLES_PER_FRAME
        if start_sample < previous_end_sample:
            raise AudioBuildError(f"narration segments overlap at {segment_id}")
        split_metadata: dict[str, Any] | None = None
        s08_prefix = None
        s08_suffix = None
        if segment_id == "S08" and start_sample < 4_800_000 < start_sample + len(cue):
            silence_start = 4_800_000
            silence_end = 4_816_000
            target = silence_start - start_sample
            gap_start, gap_end, gap_seconds = find_natural_gap(cue, target)
            prefix = cue[:target]
            suffix = cue[gap_end:]
            prefix_end = start_sample + len(prefix)
            suffix_end = silence_end + len(suffix)
            scheduled_samples = len(prefix) + (silence_end - silence_start) + len(suffix)
            if prefix_end > silence_start or silence_end + len(suffix) > segment_end_frame * SAMPLES_PER_FRAME:
                raise AudioBuildError("NEEDS_SOL: S08 cannot fit around the absolute-silence anchor without clipping")
            narration[start_sample:prefix_end] = prefix
            narration[silence_end:silence_end + len(suffix)] = suffix
            s08_prefix = len(prefix)
            s08_suffix = len(suffix)
            end_sample = suffix_end
            split_metadata = {
                "splitAtSample": silence_start,
                "resumeAtSample": silence_end,
                "naturalGapStartSample": gap_start,
                "naturalGapEndSampleExclusive": gap_end,
                "naturalGapDurationSeconds": round(gap_seconds, 6),
                "quietSamplesRemoved": gap_end - target,
                "sampleAwareSplit": True,
                "spokenSamplesPreserved": len(prefix) + len(suffix),
            }
        else:
            scheduled_samples = len(cue)
            end_sample = start_sample + scheduled_samples
            if end_sample > segment_end_frame * SAMPLES_PER_FRAME:
                raise AudioBuildError(
                    f"{segment_id} PCM does not fit its segment at 1.0x playback; no speech was sped up or truncated"
                )
            narration[start_sample:end_sample] = cue
        if end_sample > TOTAL_SAMPLES:
            raise AudioBuildError(f"{segment_id} exceeds the 120-second PCM master boundary")
        previous_end_sample = end_sample
        captions.extend(chunk_windows(
            segment,
            start_sample,
            scheduled_samples,
            s08_prefix_samples=s08_prefix,
            s08_suffix_samples=s08_suffix,
        ))
        timing = {
            "id": segment_id,
            "startFrame": start_frame,
            "endFrame": math.ceil(end_sample / SAMPLES_PER_FRAME),
            "pcmStartSample": start_sample,
            "pcmEndSampleExclusive": end_sample,
            "pcmSamples": len(cue),
            "scheduledPcmSamples": scheduled_samples,
            "sampleRate": SAMPLE_RATE,
            "segmentStartFrame": segment_start_frame,
            "segmentEndFrame": segment_end_frame,
            "cacheKey": entry["cacheKey"],
            "split": split_metadata,
        }
        timing_segments.append(timing)
    narration_path = AUDIO / "narration.wav"
    write_mono_narration(narration, narration_path)
    silence_peak = absolute_silence_peak(narration_path)
    if silence_peak != 0:
        raise AudioBuildError(f"narration stem violates the 20-frame silence window (peak {silence_peak})")
    stem_meta = validate_stem(narration_path)
    timing_data = {
        "durationSeconds": DURATION_SECONDS,
        "fps": FPS,
        "sampleRate": SAMPLE_RATE,
        "samplesPerFrame": SAMPLES_PER_FRAME,
        "samplesPerChannel": TOTAL_SAMPLES,
        "segments": timing_segments,
        "captions": captions,
        "captionTimingMethod": "Measured segment PCM duration is divided among provided display chunks by text-length phrase estimates; this is not word-level alignment evidence.",
        "voiceOnsetDelayFrames": VOICE_ONSET_DELAY_FRAMES,
        "absoluteSilence": {"startSample": 4_800_000, "endSampleExclusive": 4_816_000, "exactlyZero": True},
    }
    return stem_meta, timing_data


def run_ffmpeg(args: list[str], *, label: str, capture: bool = False) -> str:
    result = subprocess.run(
        args,
        check=False,
        stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode:
        raise AudioBuildError(f"{label} failed (exit {result.returncode}); raw tool output was discarded")
    return result.stderr or ""


def parse_loudnorm_json(output: str) -> dict[str, Any]:
    matches = list(re.finditer(r"\{\s*\"input_i\"[\s\S]*?\}", output))
    if not matches:
        raise AudioBuildError("ffmpeg loudnorm did not return parseable first-pass measurements")
    try:
        result = json.loads(matches[-1].group(0))
    except json.JSONDecodeError:
        raise AudioBuildError("ffmpeg loudnorm measurement JSON was malformed") from None
    required = ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")
    if any(not isinstance(result.get(key), (str, int, float)) for key in required):
        raise AudioBuildError("ffmpeg loudnorm measurement JSON is incomplete")
    return {key: result[key] for key in (*required, "output_i", "output_tp", "output_lra", "normalization_type", "target_offset") if key in result}


def parse_ebur128(path: Path) -> dict[str, Any]:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise AudioBuildError("ffmpeg is required to measure integrated loudness and true peak")
    output = run_ffmpeg([
        ffmpeg, "-hide_banner", "-nostats", "-i", str(path),
        "-af", "ebur128=peak=true", "-f", "null", "-",
    ], label="ebur128 measurement", capture=True)
    integrated = re.search(r"^\s*I:\s*(-?\d+(?:\.\d+)?)\s+LUFS\s*$", output, re.MULTILINE)
    true_peak = re.search(r"^\s*True peak:\s*(-?\d+(?:\.\d+)?)\s+dBTP\s*$", output, re.MULTILINE)
    if true_peak is None:
        # FFmpeg 8 prints the oversampled true peak as a nested Peak: dBFS
        # line under the True peak heading; its context defines dBTP.
        true_peak = re.search(r"True peak:\s*\n\s*Peak:\s*(-?\d+(?:\.\d+)?)\s+dBFS", output)
    sample_peak = re.search(r"^\s*Sample peak:\s*(-?\d+(?:\.\d+)?)\s+dBFS\s*$", output, re.MULTILINE)
    if integrated is None or true_peak is None:
        raise AudioBuildError("ffmpeg ebur128 did not report integrated LUFS and true peak")
    return {
        "integratedLUFS": float(integrated.group(1)),
        "truePeakDBTP": float(true_peak.group(1)),
        "samplePeakDBFS": float(sample_peak.group(1)) if sample_peak else None,
    }


def force_exact_silence(path: Path) -> None:
    # FFmpeg PCM24 WAV may include extensible fmt and LIST chunks. Read actual
    # decoded PCM through wave instead of assuming a 44-byte container header.
    with wave.open(str(path), "rb") as wav:
        params = wav.getparams()
        if (params.framerate, params.nchannels, params.sampwidth, params.nframes) != (
            SAMPLE_RATE, 2, 3, TOTAL_SAMPLES
        ):
            raise AudioBuildError(f"master must be exact 48 kHz stereo PCM24 with {TOTAL_SAMPLES} frames; got {params}")
        pcm = bytearray(wav.readframes(TOTAL_SAMPLES))
    if len(pcm) != TOTAL_SAMPLES * 6:
        raise AudioBuildError("PCM24 master physical sample count mismatch")
    pcm[4_800_000 * 6:4_816_000 * 6] = bytes(16_000 * 6)
    temporary = path.with_name(path.stem + ".silence.tmp.wav")
    with wave.open(str(temporary), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(3)
        out.setframerate(SAMPLE_RATE)
        out.writeframes(pcm)
    temporary.replace(path)


def mix_master() -> tuple[dict[str, Any], dict[str, Any]]:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise AudioBuildError("ffmpeg is required to mix and loudness-normalize the PCM master")
    narration = AUDIO / "narration.wav"
    score = AUDIO / "score.wav"
    sfx = AUDIO / "sfx.wav"
    master = AUDIO / "master.wav"
    pass2 = AUDIO / "master-normalized.tmp.wav"
    mix_filter = (
        "[1:a][0:a]sidechaincompress=threshold=0.035:ratio=5:attack=20:release=250:makeup=1[ducked];"
        "[0:a][ducked][2:a]amix=inputs=3:duration=longest:normalize=0,"
        f"aresample=48000,atrim=end_sample={TOTAL_SAMPLES},asetpts=PTS-STARTPTS[mix]"
    )
    first_pass = run_ffmpeg([
        ffmpeg, "-hide_banner", "-nostats", "-i", str(narration), "-i", str(score), "-i", str(sfx),
        "-filter_complex", mix_filter + ";[mix]loudnorm=I=-17:TP=-1.5:LRA=9:print_format=json[out]",
        "-map", "[out]", "-ar", str(SAMPLE_RATE), "-ac", "2", "-f", "null", "-",
    ], label="first-pass loudnorm analysis", capture=True)
    measurements = parse_loudnorm_json(first_pass)
    measured_i = measurements["input_i"]
    measured_tp = measurements["input_tp"]
    measured_lra = measurements["input_lra"]
    measured_thresh = measurements["input_thresh"]
    offset = measurements["target_offset"]
    normalized_filter = (
        mix_filter
        + ";[mix]loudnorm=I=-17:TP=-1.5:LRA=9"
        + f":measured_I={measured_i}:measured_TP={measured_tp}:measured_LRA={measured_lra}"
        + f":measured_thresh={measured_thresh}:offset={offset}:linear=true:print_format=json[out]"
    )
    second_pass = run_ffmpeg([
        ffmpeg, "-hide_banner", "-nostats", "-y", "-i", str(narration), "-i", str(score), "-i", str(sfx),
        "-filter_complex", normalized_filter, "-map", "[out]", "-ar", str(SAMPLE_RATE), "-ac", "2",
        "-c:a", "pcm_s24le", str(pass2),
    ], label="second-pass loudnorm render", capture=True)
    second_pass_stats = parse_loudnorm_json(second_pass)
    force_exact_silence(pass2)
    # Ensure the normalized filter preserved the authored PCM timeline exactly.
    strict_decode(pass2)
    with wave.open(str(pass2), "rb") as wav:
        params = wav.getparams()
    if (params.framerate, params.nchannels, params.sampwidth, params.nframes) != (
        SAMPLE_RATE, 2, 3, TOTAL_SAMPLES
    ):
        raise AudioBuildError(f"loudnorm output changed the master sample count: {params}")
    pass2.replace(master)
    loudness = parse_ebur128(master)
    if loudness["truePeakDBTP"] > -1.5:
        # Add a small linear margin if ffmpeg's measured result rounds above its
        # requested ceiling. This changes gain only; it does not move any event.
        attenuation_db = -1.6 - loudness["truePeakDBTP"]
        corrected = AUDIO / "master-truepeak.tmp.wav"
        run_ffmpeg([
            ffmpeg, "-hide_banner", "-loglevel", "error", "-xerror", "-y", "-i", str(master),
            "-af", f"volume={attenuation_db:.6f}dB", "-ar", str(SAMPLE_RATE), "-ac", "2",
            "-c:a", "pcm_s24le", str(corrected),
        ], label="true-peak headroom correction")
        force_exact_silence(corrected)
        strict_decode(corrected)
        with wave.open(str(corrected), "rb") as wav:
            corrected_params = wav.getparams()
        if (corrected_params.framerate, corrected_params.nchannels, corrected_params.sampwidth, corrected_params.nframes) != (
            SAMPLE_RATE, 2, 3, TOTAL_SAMPLES
        ):
            corrected.unlink(missing_ok=True)
            raise AudioBuildError("true-peak correction changed the exact master sample count")
        corrected.replace(master)
        loudness = parse_ebur128(master)
    if loudness["truePeakDBTP"] > -1.5:
        raise AudioBuildError(f"master exceeds the -1.5 dBTP ceiling: {loudness['truePeakDBTP']} dBTP")
    if absolute_silence_peak(master, 4_800_000, 4_816_000) != 0:
        raise AudioBuildError("master absolute-silence window is not exactly zero after loudnorm")
    if not -18.0 <= loudness["integratedLUFS"] <= -16.0:
        raise AudioBuildError(f"master loudness outside target range: {loudness['integratedLUFS']} LUFS")
    master_info = {
        "file": str(master.relative_to(PROJECT)),
        "sha256": sha256_file(master),
        "sampleRate": SAMPLE_RATE,
        "channels": 2,
        "sampleWidthBytes": 3,
        "samplesPerChannel": TOTAL_SAMPLES,
        "durationSeconds": TOTAL_SAMPLES / SAMPLE_RATE,
        "strictDecode": "passed",
        "loudnormFirstPass": measurements,
        "loudnormSecondPass": second_pass_stats,
        "ebur128Final": loudness,
        "truePeakLimitDBTP": -1.5,
        "filterLatencyCompensation": "FFmpeg loudnorm timestamps retained; source stems and event sample positions were not shifted.",
    }
    return master_info, measurements


def run_mix(data: dict[str, Any], segments: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    cues = require_verified_caches(segments, manifest)
    np = load_numpy()
    narration_meta, timing_data = build_narration(segments, cues)
    score_meta = render_score(AUDIO / "score.wav", np)
    sfx_meta, _ = render_sfx(AUDIO / "sfx.wav", AUDIO / "sfx-sample-map.json", np)
    master_meta, _ = mix_master()
    # The output timing is committed only after the PCM stems/master meet all
    # sample-count, true-peak and exact-silence checks.
    write_json(TIMING_PATH, timing_data)
    silence = {
        "startFrame": 6_000,
        "endFrameExclusive": 6_020,
        "startSample": 4_800_000,
        "endSampleExclusive": 4_816_000,
        "narrationPeak": absolute_silence_peak(AUDIO / "narration.wav"),
        "scorePeak": absolute_silence_peak(AUDIO / "score.wav"),
        "sfxPeak": absolute_silence_peak(AUDIO / "sfx.wav"),
        "masterPeak": absolute_silence_peak(AUDIO / "master.wav", 4_800_000, 4_816_000),
    }
    if any(silence[key] != 0 for key in ("narrationPeak", "scorePeak", "sfxPeak", "masterPeak")):
        raise AudioBuildError(f"absolute-silence window failed after mix: {silence}")
    mix_settings = {
        "version": 1,
        "durationSeconds": DURATION_SECONDS,
        "fps": FPS,
        "sampleRate": SAMPLE_RATE,
        "samplesPerFrame": SAMPLES_PER_FRAME,
        "samplesPerChannel": TOTAL_SAMPLES,
        "totalFrames": TOTAL_FRAMES,
        "channels": 2,
        "runtime": {
            "python": sys.executable,
            "numpy": getattr(np, "__version__", None),
            "synthesisFallback": "Python stdlib math/array" if np is None else None,
        },
        "stemFiles": {"narration": narration_meta, "score": score_meta, "sfx": sfx_meta},
        "master": master_meta,
        "ducking": {"filter": "sidechaincompress", "threshold": 0.035, "ratio": 5, "attackMs": 20, "releaseMs": 250},
        "loudnormTarget": {"integratedLUFS": -17, "truePeakDBTP": -1.5, "lraLU": 9, "passes": 2},
        "absoluteSilence": silence,
        "sfxSampleMap": str((AUDIO / "sfx-sample-map.json").relative_to(PROJECT)),
        "captionTiming": timing_data["captionTimingMethod"],
    }
    write_json(AUDIO / "mix-settings.json", mix_settings)
    print(json.dumps({
        "status": "mix_complete",
        "master": master_meta,
        "absoluteSilence": silence,
        "audioTiming": str(TIMING_PATH.relative_to(PROJECT)),
        "mixSettings": str((AUDIO / "mix-settings.json").relative_to(PROJECT)),
    }, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--generate", metavar="ID|all", help="generate one segment (for example S02) or all")
    mode.add_argument("--mix", action="store_true", help="build deterministic stems and the PCM master from verified cues")
    mode.add_argument("--audit", action="store_true", help="read-only audit of provider caches and WAV sample counts")
    args = parser.parse_args()
    try:
        data, segments = load_segments()
        manifest = load_manifest()
        if args.audit:
            return audit(manifest, segments)
        if args.mix:
            run_mix(data, segments, manifest)
            return 0
        if args.generate != "all" and args.generate not in {segment["id"] for segment in segments}:
            raise AudioBuildError(f"unknown segment {args.generate!r}; expected one of the project IDs or 'all'")
        AUDIO.mkdir(parents=True, exist_ok=True)
        for directory in (RAW, CANONICAL, CUES):
            directory.mkdir(parents=True, exist_ok=True)
        selected = segments if args.generate == "all" else [segment for segment in segments if segment["id"] == args.generate]
        for segment in selected:
            generate_one(segment, manifest)
        return 0
    except (AudioBuildError, OSError, ValueError, wave.Error) as exc:
        print(f"build_audio.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
