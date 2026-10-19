#!/usr/bin/env python3
"""Create local EP07 narration cues with macOS Speech and FFmpeg.

This utility uses only ``/usr/bin/say`` and local FFmpeg. It never contacts a
speech provider, reads credentials, performs ASR, or uploads media. Its default
action is to synthesize all current segment texts at native say rate 210.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any


PROJECT = Path(__file__).resolve().parents[1]
AUDIO_DIR = PROJECT / "public" / "audio"
RAW_DIR = AUDIO_DIR / "raw"
CUES_DIR = AUDIO_DIR / "cues"
SEGMENTS_PATH = PROJECT / "segments.json"
MANIFEST_PATH = AUDIO_DIR / "provider-manifest.json"
SAY = Path("/usr/bin/say")
PROVIDER = "macOS Speech"
VOICE = "Tingting"
DEFAULT_RATE = 210
SAMPLE_RATE = 48_000
CHANNELS = 1
SAMPLE_WIDTH_BYTES = 2

LOCAL_AUTHORIZATION = {
    "provider": PROVIDER,
    "scope": "EP07 segment narration selected for local on-device synthesis",
    "source": "Sol/root decision under the current user make-and-publish request",
    "note": (
        "Tingting is the announced local implementation choice made by Sol/root; "
        "the user has not selected this voice individually. No cloud disclosure is authorized by this record."
    ),
}


class SynthesisError(RuntimeError):
    """A local synthesis, cache, or media validation failure."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SynthesisError(f"cannot read {label}: {exc}") from None
    if not isinstance(value, dict):
        raise SynthesisError(f"{label} must contain a JSON object")
    return value


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as stream:
            temporary_path = Path(stream.name)
            stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def load_segments() -> list[dict[str, Any]]:
    data = read_json(SEGMENTS_PATH, "segments.json")
    segments = data.get("segments")
    if not isinstance(segments, list) or not segments:
        raise SynthesisError("segments.json must contain a non-empty segments array")
    seen: set[str] = set()
    for item in segments:
        if not isinstance(item, dict):
            raise SynthesisError("every segment must be a JSON object")
        segment_id = item.get("id")
        text = item.get("tts_phonetic_text")
        if not isinstance(segment_id, str) or not segment_id.strip() or segment_id in seen:
            raise SynthesisError(f"segment id is missing or duplicated: {segment_id!r}")
        if not isinstance(text, str) or not text.strip():
            raise SynthesisError(f"{segment_id} has no tts_phonetic_text")
        seen.add(segment_id)
    return segments


def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        return {
            "version": 1,
            "settings": {},
            "authorization": LOCAL_AUTHORIZATION,
            "segments": {},
            "cacheHistory": [],
        }
    manifest = read_json(MANIFEST_PATH, "provider-manifest.json")
    if not isinstance(manifest.get("segments"), dict):
        raise SynthesisError("existing provider-manifest.json has no segments map; it was left unchanged")
    if not isinstance(manifest.get("cacheHistory", []), list):
        raise SynthesisError("existing provider-manifest.json cacheHistory must be an array")
    manifest.setdefault("cacheHistory", [])
    return manifest


def settings_for(rate: int) -> dict[str, Any]:
    return {
        "provider": PROVIDER,
        "engine": str(SAY),
        "voice": VOICE,
        "requested_voice": VOICE,
        # `say` accepts an explicit voice but returns no separate effective
        # identity. Keep the requested value and mark it as unobserved.
        "effective_voice": VOICE,
        "effective_voice_observed": False,
        "effective_voice_status": "requested_voice_used_as_fallback; runtime identity not separately reported",
        "rate": rate,
        "format": "mono PCM16 WAV cue; source retained as AIFF",
        "sample_rate": SAMPLE_RATE,
        "channels": CHANNELS,
    }


def cache_key(text: str, rate: int) -> str:
    identity = {
        "text": text,
        "voice": VOICE,
        "rate": rate,
        "provider": PROVIDER,
    }
    return hashlib.sha256(canonical_json(identity)).hexdigest()


def decode_extended80(payload: bytes) -> float:
    if len(payload) != 10:
        raise SynthesisError("AIFF sample-rate field is truncated")
    sign_exponent = int.from_bytes(payload[:2], "big")
    mantissa = int.from_bytes(payload[2:], "big")
    exponent = sign_exponent & 0x7FFF
    if exponent == 0 and mantissa == 0:
        return 0.0
    value = mantissa * (2.0 ** (exponent - 16383 - 63))
    return -value if sign_exponent & 0x8000 else value


def read_aiff_info(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            header = stream.read(12)
            if len(header) != 12 or header[:4] != b"FORM" or header[8:12] not in (b"AIFF", b"AIFC"):
                raise SynthesisError(f"{path.name} is not a valid AIFF/AIFC file")
            form_kind = header[8:12].decode("ascii")
            comm: dict[str, Any] | None = None
            while True:
                chunk_header = stream.read(8)
                if not chunk_header:
                    break
                if len(chunk_header) != 8:
                    raise SynthesisError(f"{path.name} has a truncated AIFF chunk header")
                chunk_name = chunk_header[:4]
                chunk_size = struct.unpack(">I", chunk_header[4:])[0]
                chunk_start = stream.tell()
                if chunk_name == b"COMM":
                    chunk = stream.read(min(chunk_size, 64))
                    if len(chunk) < 18:
                        raise SynthesisError(f"{path.name} has a truncated AIFF COMM chunk")
                    channels, frames, sample_bits = struct.unpack(">HIH", chunk[:8])
                    sample_rate = decode_extended80(chunk[8:18])
                    comm = {
                        "channels": channels,
                        "sampleFrames": frames,
                        "sampleBits": sample_bits,
                        "sampleRate": int(round(sample_rate)),
                        "sampleRateExact": sample_rate,
                        "container": form_kind,
                    }
                    break
                stream.seek(chunk_start + chunk_size + (chunk_size & 1))
    except OSError as exc:
        raise SynthesisError(f"cannot inspect raw AIFF {path.name}: {exc}") from None
    if comm is None or comm["sampleRate"] <= 0 or comm["sampleFrames"] <= 0:
        raise SynthesisError(f"{path.name} has no valid AIFF sample metadata")
    return comm


def read_cue_info(path: Path) -> dict[str, Any]:
    try:
        with wave.open(str(path), "rb") as wav:
            params = wav.getparams()
            payload = wav.readframes(params.nframes)
    except (OSError, wave.Error) as exc:
        raise SynthesisError(f"cannot inspect PCM cue {path.name}: {exc}") from None
    expected = (SAMPLE_RATE, CHANNELS, SAMPLE_WIDTH_BYTES, "NONE")
    observed = (params.framerate, params.nchannels, params.sampwidth, params.comptype)
    if observed != expected or params.nframes <= 0 or len(payload) != params.nframes * CHANNELS * SAMPLE_WIDTH_BYTES:
        raise SynthesisError(f"{path.name} is not complete mono 48 kHz PCM16 WAV: {observed}")
    return {
        "samplesAt48k": int(params.nframes),
        "durationSeconds": params.nframes / SAMPLE_RATE,
        "pcmSha256": sha256_bytes(payload),
    }


def contained_manifest_path(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise SynthesisError(f"cache manifest {label} is missing")
    path = (PROJECT / value).resolve()
    try:
        path.relative_to(PROJECT.resolve())
    except ValueError:
        raise SynthesisError(f"cache manifest {label} escapes the EP07 project") from None
    return path


def verify_cached_entry(segment_id: str, text: str, rate: int, key: str,
                        entry: dict[str, Any]) -> bool:
    if entry.get("cache_key") != key:
        return False
    if entry.get("tts_phonetic_text") != text or entry.get("settings") != settings_for(rate):
        raise SynthesisError(f"{segment_id} cache key matched but text/settings diverged; preserved for review")
    if entry.get("authorization") != LOCAL_AUTHORIZATION:
        raise SynthesisError(f"{segment_id} cache authorization record differs from the current local synthesis scope")
    raw_path = contained_manifest_path(entry.get("raw_path"), f"{segment_id}.raw_path")
    cue_path = contained_manifest_path(entry.get("cue_path"), f"{segment_id}.cue_path")
    if not raw_path.is_file() or not cue_path.is_file():
        raise SynthesisError(f"{segment_id} matching cache has a missing raw/cue file; preserved for review")
    raw_hash = sha256_file(raw_path)
    cue_hash = sha256_file(cue_path)
    if raw_hash != entry.get("raw_sha256") or cue_hash != entry.get("cue_sha256"):
        raise SynthesisError(f"{segment_id} matching cache hash differs from the manifest; files were preserved")
    raw_info = read_aiff_info(raw_path)
    cue_info = read_cue_info(cue_path)
    if raw_info != entry.get("rawAudio"):
        raise SynthesisError(f"{segment_id} matching cache raw AIFF metadata differs from the manifest")
    if cue_info["samplesAt48k"] != entry.get("actual_samples_48k"):
        raise SynthesisError(f"{segment_id} matching cache PCM sample count differs from the manifest")
    if cue_info["pcmSha256"] != entry.get("cue_pcm_sha256"):
        raise SynthesisError(f"{segment_id} matching cache PCM hash differs from the manifest")
    return True


def versioned_paths(segment_id: str, key: str) -> tuple[Path, Path, int | None]:
    stem = f"{segment_id}-{key[:16]}"
    suffixes: list[int | None] = [None, *range(2, 10_000)]
    for revision in suffixes:
        tail = "" if revision is None else f"-r{revision:02d}"
        raw = RAW_DIR / f"{stem}{tail}.aiff"
        cue = CUES_DIR / f"{stem}{tail}.wav"
        if not raw.exists() and not cue.exists():
            return raw, cue, revision
    raise SynthesisError(f"no free versioned cache path remains for {segment_id}")


def link_new_file(source: Path, target: Path) -> None:
    """Publish a staged artifact atomically without ever replacing an existing file."""
    try:
        os.link(source, target)
    except FileExistsError:
        raise SynthesisError(f"refusing to replace existing versioned artifact {target.relative_to(PROJECT)}") from None
    except OSError as exc:
        raise SynthesisError(f"cannot publish staged artifact {target.name} without replacement: {exc}") from None
    source.unlink()


def run_local_command(command: list[str], label: str) -> None:
    try:
        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    except OSError as exc:
        raise SynthesisError(f"cannot run {label}: {exc}") from None
    if process.returncode:
        detail = (process.stderr or process.stdout or "").strip().splitlines()[-6:]
        raise SynthesisError(f"{label} failed with exit {process.returncode}: {' | '.join(detail)}")


def dedupe_history(history: list[Any], candidate: dict[str, Any]) -> None:
    fingerprint = (candidate.get("segmentId"), candidate.get("cache_key"), candidate.get("cue_path"))
    for existing in history:
        if isinstance(existing, dict) and (
            existing.get("segmentId"), existing.get("cache_key"), existing.get("cue_path")
        ) == fingerprint:
            return
    history.append(candidate)


def archive_previous_entry(manifest: dict[str, Any], segment_id: str) -> None:
    previous = manifest.get("segments", {}).get(segment_id)
    if isinstance(previous, dict):
        dedupe_history(manifest["cacheHistory"], {**previous, "segmentId": segment_id})


def manifest_settings(rate: int) -> dict[str, Any]:
    return settings_for(rate)


def synthesize_one(segment: dict[str, Any], rate: int, manifest: dict[str, Any], ffmpeg: str) -> dict[str, Any]:
    segment_id = segment["id"]
    text = segment["tts_phonetic_text"]
    key = cache_key(text, rate)
    current = manifest["segments"].get(segment_id)
    if isinstance(current, dict) and verify_cached_entry(segment_id, text, rate, key, current):
        return {"id": segment_id, "status": "cached", "cue_path": current["cue_path"],
                "cue_sha256": current["cue_sha256"], "actual_samples_48k": current["actual_samples_48k"]}

    if not SAY.is_file():
        raise SynthesisError(f"{SAY} is unavailable; no synthesis was attempted")
    raw_target, cue_target, revision = versioned_paths(segment_id, key)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CUES_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f".{segment_id}-local-speech-", dir=AUDIO_DIR) as temporary_dir:
        stage = Path(temporary_dir)
        staged_raw = stage / "narration.aiff"
        staged_cue = stage / "narration.wav"
        run_local_command([
            str(SAY), "-v", VOICE, "-r", str(rate), "-o", str(staged_raw), text,
        ], f"local macOS Speech synthesis for {segment_id}")
        if not staged_raw.is_file() or staged_raw.stat().st_size == 0:
            raise SynthesisError(f"macOS Speech returned no raw AIFF for {segment_id}")
        raw_info = read_aiff_info(staged_raw)
        run_local_command([
            ffmpeg, "-hide_banner", "-nostdin", "-v", "error", "-y", "-i", str(staged_raw),
            "-map", "0:a:0", "-map_metadata", "-1", "-vn", "-ac", str(CHANNELS), "-ar", str(SAMPLE_RATE),
            "-sample_fmt", "s16", "-c:a", "pcm_s16le", str(staged_cue),
        ], f"local PCM conversion for {segment_id}")
        if not staged_cue.is_file() or staged_cue.stat().st_size == 0:
            raise SynthesisError(f"FFmpeg returned no PCM cue for {segment_id}")
        cue_info = read_cue_info(staged_cue)
        expected_samples = int(round(raw_info["sampleFrames"] * SAMPLE_RATE / raw_info["sampleRate"]))
        if abs(cue_info["samplesAt48k"] - expected_samples) > 1:
            raise SynthesisError(
                f"{segment_id} PCM conversion sample count {cue_info['samplesAt48k']} differs from "
                f"the full-source resample estimate {expected_samples}; no versioned artifacts or manifest entry were written"
            )
        raw_hash = sha256_file(staged_raw)
        cue_hash = sha256_file(staged_cue)
        link_new_file(staged_raw, raw_target)
        link_new_file(staged_cue, cue_target)

    entry = {
        "cache_key": key,
        "tts_phonetic_text": text,
        "settings": settings_for(rate),
        "authorization": LOCAL_AUTHORIZATION,
        "raw_path": str(raw_target.relative_to(PROJECT)),
        "raw_sha256": raw_hash,
        "rawAudio": raw_info,
        "cue_path": str(cue_target.relative_to(PROJECT)),
        "cue_sha256": cue_hash,
        "cue_pcm_sha256": cue_info["pcmSha256"],
        "actual_samples_48k": cue_info["samplesAt48k"],
        "duration_seconds": cue_info["durationSeconds"],
        "rawSampleRate": raw_info["sampleRate"],
        "rawChannels": raw_info["channels"],
        "rawSampleFrames": raw_info["sampleFrames"],
        "rawSampleBits": raw_info["sampleBits"],
        "rateUsed": rate,
        "trimmed": False,
        "resampling": "FFmpeg sample-rate/channel/PCM conversion only; no time stretch, trim, or silence removal",
        "versionRevision": revision,
    }
    old_settings = manifest.get("settings")
    new_settings = manifest_settings(rate)
    if old_settings and old_settings != new_settings:
        settings_history = manifest.setdefault("settingsHistory", [])
        if not isinstance(settings_history, list):
            raise SynthesisError("existing provider-manifest.json settingsHistory must be an array")
        snapshot = {"settings": old_settings}
        if snapshot not in settings_history:
            settings_history.append(snapshot)
    old_auth = manifest.get("authorization")
    if old_auth and old_auth != LOCAL_AUTHORIZATION:
        authorization_history = manifest.setdefault("authorizationHistory", [])
        if not isinstance(authorization_history, list):
            raise SynthesisError("existing provider-manifest.json authorizationHistory must be an array")
        if old_auth not in authorization_history:
            authorization_history.append(old_auth)
    archive_previous_entry(manifest, segment_id)
    manifest["version"] = manifest.get("version", 1)
    manifest["settings"] = new_settings
    manifest["authorization"] = LOCAL_AUTHORIZATION
    manifest["segments"][segment_id] = entry
    write_json_atomic(MANIFEST_PATH, manifest)
    return {
        "id": segment_id,
        "status": "synthesized",
        "raw_path": entry["raw_path"],
        "raw_sha256": raw_hash,
        "cue_path": entry["cue_path"],
        "cue_sha256": cue_hash,
        "actual_samples_48k": cue_info["samplesAt48k"],
        "duration_seconds": cue_info["durationSeconds"],
        "cache_key": key,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--segment", default="all", help="one segment id such as S01, or 'all' (default)")
    parser.add_argument("--rate", type=int, default=DEFAULT_RATE, help=f"native /usr/bin/say rate (default {DEFAULT_RATE})")
    args = parser.parse_args()
    try:
        if not 1 <= args.rate <= 1_000:
            raise SynthesisError("--rate must be an integer from 1 through 1000")
        segments = load_segments()
        by_id = {item["id"]: item for item in segments}
        selector = args.segment
        if selector != "all" and selector not in by_id:
            raise SynthesisError(f"unknown segment {selector!r}; choose one of {', '.join(by_id)} or 'all'")
        selected = segments if selector == "all" else [by_id[selector]]
        if not SAY.is_file():
            raise SynthesisError(f"{SAY} is unavailable; no synthesis was attempted")
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            raise SynthesisError("ffmpeg is unavailable; no synthesis was attempted")
        manifest = load_manifest()
        results = []
        for segment in selected:
            results.append(synthesize_one(segment, args.rate, manifest, ffmpeg))
        print(json.dumps({
            "status": "complete",
            "provider": PROVIDER,
            "voiceRequested": VOICE,
            "voiceObserved": False,
            "rate": args.rate,
            "selectedCount": len(selected),
            "results": results,
        }, ensure_ascii=False, indent=2))
        return 0
    except (SynthesisError, OSError, ValueError, wave.Error, OverflowError) as exc:
        print(f"synthesize_local.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
