#!/usr/bin/env python3
"""Generate and audit EP04's approved local TTS cue assets, one request at a time."""

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
from pathlib import Path
from typing import Any


PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT.parent
AUDIO = PROJECT / "public" / "audio"
RAW = AUDIO / "raw"
CANONICAL = AUDIO / "canonical"
CUES = AUDIO / "cues"
INPUTS = AUDIO / "tts-input"
SEGMENTS_PATH = PROJECT / "segments.json"
MANIFEST_PATH = AUDIO / "provider-manifest.json"
AUTH_PATH = PROJECT / "audio-authorization.json"
BL = Path("/Users/guoq/.local/n/bin/bl")
EXPECTED_MODEL = "cosyvoice-v3-flash"
EXPECTED_VOICE = "longtian_v3"
SAMPLE_RATE = 24_000
SETTINGS = {
    "provider": "Aliyun Bailian",
    "model_selection": "active profile default",
    "effective_model": EXPECTED_MODEL,
    "voice": EXPECTED_VOICE,
    "rate": 1.0,
    "format": "wav",
    "sample_rate": SAMPLE_RATE,
}
CLI_VERSION = "2.3.2"
AUTH_QUESTION = "是否允许把本片所给的 S01–S09 旁白文本发送给阿里云百炼，沿用 EP04 的 cosyvoice-v3-flash／longtian_v3 合成配音？可能产生计费；只发送本片文本，不上传其他文件，横竖版共用一次生成结果。"
AUTH_ANSWER = "允许，按此范围生成"
AUTHORIZED_AT_UTC = "2026-10-19T10:16:58Z"


class AudioError(RuntimeError):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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


def cache_key(text: str) -> str:
    payload = json.dumps(
        {"text": text, "settings": SETTINGS},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(payload)


def load_source_segments() -> list[dict[str, Any]]:
    data = json.loads(SEGMENTS_PATH.read_text(encoding="utf-8"))
    segments = data.get("segments") if isinstance(data, dict) else None
    if not isinstance(segments, list) or [item.get("id") for item in segments] != [f"S{i:02d}" for i in range(1, 11)]:
        raise AudioError("segments.json must contain S01 through S10 in order")
    return segments


def plan_tasks(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for segment in segments:
        segment_id = segment["id"]
        text = segment.get("tts_phonetic_text")
        if not isinstance(text, str) or not text.strip():
            raise AudioError(f"{segment_id} has no TTS text")
        if segment_id == "S08":
            part_a = "直到漫长的十年过去，笨重的物理世界，"
            part_b = "终于传回了，唯一的一声回音：错误。"
            if text != part_a + part_b:
                raise AudioError("S08 text differs from the packet-approved grammatical split")
            for part_id, part_text, start, end, active_deadline in (
                ("S08a", part_a, segment["startFrame"], 5820, 5820),
                ("S08b", part_b, 5850, segment["endFrame"], segment["endFrame"]),
            ):
                path = INPUTS / f"{part_id}.txt"
                if path.exists() and path.read_text(encoding="utf-8").strip() != part_text:
                    raise AudioError(f"{path.name} differs from the approved S08 split; preserving it")
                if not path.exists():
                    path.write_text(part_text + "\n", encoding="utf-8")
                tasks.append({
                    "id": part_id,
                    "parent_id": "S08",
                    "text": part_text,
                    "start_frame": start,
                    "end_frame": end,
                    "active_deadline_frame": active_deadline,
                    "text_path": path,
                })
            continue

        input_path = INPUTS / f"{segment_id}.txt"
        if not input_path.is_file() or input_path.read_text(encoding="utf-8").strip() != text:
            raise AudioError(f"{segment_id} tts-input file does not match segments.json")
        tasks.append({
            "id": segment_id,
            "parent_id": segment_id,
            "text": text,
            "start_frame": int(segment["startFrame"]),
            "end_frame": int(segment["endFrame"]),
            "active_deadline_frame": int(segment["endFrame"]),
            "text_path": input_path,
        })
    return tasks


def empty_manifest() -> dict[str, Any]:
    return {
        "version": 1,
        "status": "synthesis_in_progress",
        "settings": {**SETTINGS, "cli_version": CLI_VERSION},
        "authorization": {
            "manifest": "project/audio-authorization.json",
            "scope": "New EP04 TTS cues S01-S09; S08 is split at the approved grammatical pause; S10 reuses the verified prior cue.",
            "source": "Current explicit request to synthesize the supplied EP04 TTS text, continuing the existing EP04 Bailian workflow per Sol/root routing.",
            "provider_selection_note": "The user did not name a new provider and there is no separate direct provider-selection reply recorded.",
        },
        "cache_key_note": "New cue keys hash the exact text and provider/model/voice/rate/format/sample-rate settings; S10 preserves its source EP04 cache identity.",
        "segments": {},
    }


def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        return empty_manifest()
    value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if value.get("settings") != {**SETTINGS, "cli_version": CLI_VERSION}:
        raise AudioError("Existing provider manifest settings differ; preserving it")
    return value


def safe_cli_json(stdout: str) -> dict[str, Any]:
    start, end = stdout.find("{"), stdout.rfind("}")
    if start < 0 or end < start:
        raise AudioError("Bailian response did not contain the expected JSON metadata")
    try:
        value = json.loads(stdout[start:end + 1])
    except json.JSONDecodeError:
        raise AudioError("Bailian response JSON was malformed; raw response was not saved") from None
    if not isinstance(value, dict):
        raise AudioError("Bailian response metadata was not an object")
    return value


def request_speech(task: dict[str, Any], raw_path: Path) -> dict[str, str]:
    if not BL.is_file():
        raise AudioError("The preflighted Bailian CLI path is missing")
    if raw_path.exists():
        raise AudioError(f"Untracked raw output already exists at {raw_path}; preserving it")
    command = [
        str(BL), "speech", "synthesize",
        "--text-file", str(task["text_path"]),
        "--out", str(raw_path),
        "--voice", EXPECTED_VOICE,
        "--rate", "1.0",
        "--format", "wav",
        "--sample-rate", str(SAMPLE_RATE),
        "--output", "json",
    ]
    result = subprocess.run(command, cwd=WORK, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        # Do not persist or echo CLI output, which can include temporary signed URLs.
        raise AudioError(f"Bailian synthesis failed for {task['id']} (exit {result.returncode}); details are not echoed")
    metadata = safe_cli_json(result.stdout)
    model = metadata.get("model")
    voice = metadata.get("voice")
    if model != EXPECTED_MODEL or voice != EXPECTED_VOICE:
        raise AudioError(f"Provider identity mismatch for {task['id']}: model={model!r}, voice={voice!r}")
    if not raw_path.is_file() or raw_path.stat().st_size == 0:
        raise AudioError(f"Bailian did not produce the requested raw WAV for {task['id']}")
    return {"effective_model": model, "effective_voice": voice}


def parse_provider_wav(path: Path) -> tuple[bytes, dict[str, Any]]:
    raw = path.read_bytes()
    if len(raw) < 44 or raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise AudioError(f"{path.name} is not a RIFF/WAVE file")
    riff_declared = struct.unpack_from("<I", raw, 4)[0]
    offset = 12
    fmt: tuple[int, ...] | None = None
    data_start: int | None = None
    data_declared: int | None = None
    while offset + 8 <= len(raw):
        chunk_id = raw[offset:offset + 4]
        chunk_size = struct.unpack_from("<I", raw, offset + 4)[0]
        start = offset + 8
        if chunk_id == b"fmt ":
            if chunk_size < 16 or start + 16 > len(raw):
                raise AudioError(f"{path.name} has a truncated fmt chunk")
            fmt = struct.unpack_from("<HHIIHH", raw, start)
        elif chunk_id == b"data":
            data_start, data_declared = start, chunk_size
            break
        next_offset = start + chunk_size + (chunk_size & 1)
        if next_offset > len(raw):
            raise AudioError(f"{path.name} has a truncated non-data chunk")
        offset = next_offset
    if fmt is None or data_start is None or data_declared is None:
        raise AudioError(f"{path.name} is missing fmt or data")
    encoding, channels, rate, byte_rate, block_align, bits = fmt
    if (encoding, channels, rate, byte_rate, block_align, bits) != (1, 1, SAMPLE_RATE, SAMPLE_RATE * 2, 2, 16):
        raise AudioError(f"{path.name} must be mono PCM16 at 24 kHz")
    available = len(raw) - data_start
    overflow = data_declared > available or riff_declared > len(raw) - 8
    if data_declared > available:
        # Repair only verified PCM16 data occupying the physical tail of the file.
        if data_start + available != len(raw) or available == 0 or available % 2:
            raise AudioError(f"{path.name} has an unverified WAV size overflow; raw file preserved")
        payload = raw[data_start:]
        repair = "declared RIFF/data sizes exceed the physical trailing PCM payload; payload is complete and 16-bit aligned"
    else:
        payload = raw[data_start:data_start + data_declared]
        repair = None
        if len(payload) == 0 or len(payload) % 2:
            raise AudioError(f"{path.name} payload is empty or not 16-bit aligned")
    info = {
        "raw_bytes": len(raw),
        "raw_sha256": sha256_bytes(raw),
        "riff_declared_size": riff_declared,
        "riff_actual_size": len(raw) - 8,
        "data_declared_size": data_declared,
        "data_available_size": available,
        "actual_samples_24k": len(payload) // 2,
        "pcm_sha256_24k": sha256_bytes(payload),
        "repair_verified": overflow,
        "repair_note": repair,
    }
    return payload, info


def write_canonical(path: Path, payload: bytes) -> str:
    expected_hash = sha256_bytes(payload)
    if path.exists():
        with wave.open(str(path), "rb") as wav:
            existing = wav.readframes(wav.getnframes())
            params = wav.getparams()
        if (params.nchannels, params.sampwidth, params.framerate, params.comptype) != (1, 2, SAMPLE_RATE, "NONE"):
            raise AudioError(f"Existing canonical WAV {path.name} has unexpected format; preserving it")
        if sha256_bytes(existing) != expected_hash:
            raise AudioError(f"Existing canonical WAV {path.name} differs; preserving it")
        return sha256_file(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(payload)
    return sha256_file(path)


def active_bounds(payload: bytes, rate: int) -> dict[str, int]:
    values = array.array("h")
    values.frombytes(payload)
    if sys.byteorder != "little":
        values.byteswap()
    if not values:
        raise AudioError("Cannot measure active span in empty PCM")
    peak = max(abs(value) for value in values)
    threshold = max(48, int(peak * 0.004))
    window = max(1, rate // 200)  # 5 ms.
    rolling = sum(value * value for value in values[:window])
    first = None
    last = None
    limit = threshold * threshold * window
    for index in range(0, len(values) - window + 1):
        if index:
            rolling += values[index + window - 1] ** 2 - values[index - 1] ** 2
        if rolling >= limit:
            if first is None:
                first = index
            last = index + window
    if first is None or last is None:
        raise AudioError("No active PCM span detected in TTS cue")
    return {
        "onset_sample": first,
        "active_end_sample_exclusive": last,
        "threshold_pcm16": threshold,
        "window_samples": window,
        "peak_pcm16": peak,
    }


def make_48k_cue(canonical_path: Path, cue_path: Path, samples_24k: int) -> tuple[str, bytes]:
    if cue_path.exists():
        with wave.open(str(cue_path), "rb") as wav:
            params = wav.getparams()
            frames = wav.readframes(wav.getnframes())
        if (params.nchannels, params.sampwidth, params.framerate, params.comptype) != (1, 2, 48_000, "NONE"):
            raise AudioError(f"Existing cue {cue_path.name} has unexpected format; preserving it")
        if params.nframes != samples_24k * 2:
            raise AudioError(f"Existing cue {cue_path.name} has a different sample count; preserving it")
        return sha256_file(cue_path), frames
    cue_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "/opt/homebrew/bin/ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
        "-i", str(canonical_path), "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", str(cue_path),
    ]
    result = subprocess.run(command, cwd=WORK, capture_output=True, check=False)
    if result.returncode != 0:
        raise AudioError(f"ffmpeg resampling failed for {cue_path.name}; output details are not echoed")
    with wave.open(str(cue_path), "rb") as wav:
        params = wav.getparams()
        frames = wav.readframes(wav.getnframes())
    if (params.nchannels, params.sampwidth, params.framerate, params.comptype, params.nframes) != (
        1, 2, 48_000, "NONE", samples_24k * 2
    ):
        raise AudioError(f"Resampled cue {cue_path.name} failed exact PCM validation")
    return sha256_file(cue_path), frames


def process_task(task: dict[str, Any], manifest: dict[str, Any], known_model: str | None = None) -> dict[str, Any]:
    key = cache_key(task["text"])
    raw_path = RAW / f"{task['id']}-{key[:12]}.wav"
    canonical_path = CANONICAL / f"{task['id']}-{key[:12]}.wav"
    cue_path = CUES / f"{task['id']}.wav"
    existing = manifest["segments"].get(task["id"])
    if existing:
        for rel, field in ((existing["raw_path"], "raw_sha256"), (existing["canonical_path"], "canonical_sha256"), (existing["cue_path"], "cue_sha256")):
            path = PROJECT / rel
            if not path.is_file() or sha256_file(path) != existing[field]:
                raise AudioError(f"Matching cache file for {task['id']} is missing or divergent; preserving it")
        return existing
    if raw_path.exists():
        provider = {"effective_model": known_model, "effective_voice": EXPECTED_VOICE}
    else:
        provider = request_speech(task, raw_path)
    if provider.get("effective_model") != EXPECTED_MODEL or provider.get("effective_voice") != EXPECTED_VOICE:
        raise AudioError(f"Provider identity for {task['id']} is not verified against the chosen EP04 settings")

    payload, raw_info = parse_provider_wav(raw_path)
    canonical_sha = write_canonical(canonical_path, payload)
    cue_sha, cue_pcm = make_48k_cue(canonical_path, cue_path, raw_info["actual_samples_24k"])
    active = active_bounds(cue_pcm, 48_000)
    duration = raw_info["actual_samples_24k"] / SAMPLE_RATE
    entry = {
        "parent_id": task["parent_id"],
        "cache_key": key,
        "tts_phonetic_text": task["text"],
        "settings": {**SETTINGS, "cli_version": CLI_VERSION},
        "effective_model": provider["effective_model"],
        "effective_voice": provider["effective_voice"],
        "identity_status": "reported by Bailian CLI response" if known_model is None else "reported by S04 viability sample; cue generated in this run",
        "raw_path": str(raw_path.relative_to(PROJECT)),
        "raw_sha256": raw_info["raw_sha256"],
        "raw_bytes": raw_info["raw_bytes"],
        "raw_wav_repair": {
            "verified": raw_info["repair_verified"],
            "riff_declared_size": raw_info["riff_declared_size"],
            "riff_actual_size": raw_info["riff_actual_size"],
            "data_declared_size": raw_info["data_declared_size"],
            "data_available_size": raw_info["data_available_size"],
            "note": raw_info["repair_note"],
        },
        "actual_samples_24k": raw_info["actual_samples_24k"],
        "actual_samples_48k": raw_info["actual_samples_24k"] * 2,
        "duration_seconds": round(duration, 6),
        "pcm_sha256_24k": raw_info["pcm_sha256_24k"],
        "canonical_path": str(canonical_path.relative_to(PROJECT)),
        "canonical_sha256": canonical_sha,
        "cue_path": str(cue_path.relative_to(PROJECT)),
        "cue_sha256": cue_sha,
        "cue_pcm_sha256_48k": sha256_bytes(cue_pcm),
        "active_pcm_48k": active,
    }
    manifest["segments"][task["id"]] = entry
    write_json(MANIFEST_PATH, manifest)
    return entry


def reuse_s10(manifest: dict[str, Any]) -> dict[str, Any]:
    segment = load_source_segments()[-1]
    text = segment["tts_phonetic_text"]
    source_manifest_path = WORK.parent / "si-ep04-verifier-paradox-v02/project/public/audio/provider-manifest.json"
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    source_entry = source_manifest["segments"]["S10"]
    if source_entry.get("tts_phonetic_text") != text:
        raise AudioError("Prior EP04 S10 text is not an exact match; preserving target assets")
    source_project = source_manifest_path.parents[2]
    source_path = source_project / source_entry["cue_path"]
    if sha256_file(source_path) != source_entry["cue_sha256"]:
        raise AudioError("Prior EP04 S10 cue differs from its verified manifest; preserving target assets")
    target_path = CUES / "S10.wav"
    if target_path.exists():
        if sha256_file(target_path) != source_entry["cue_sha256"]:
            raise AudioError("Target S10 cue exists with divergent content; preserving it")
    else:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
    entry = {
        "parent_id": "S10",
        "cache_key": source_entry["cache_key"],
        "tts_phonetic_text": text,
        "settings": source_manifest["settings"],
        "effective_model": source_entry["effective_model"][0],
        "effective_voice": source_entry["effective_voice"][0],
        "identity_status": source_entry["identity_status"],
        "reused_from": "deliveries/si-ep04-verifier-paradox-v02/project/public/audio/cues/S10.wav",
        "cue_path": str(target_path.relative_to(PROJECT)),
        "cue_sha256": sha256_file(target_path),
        "actual_samples_24k": source_entry["actual_samples_24k"],
        "actual_samples_48k": source_entry["samples_48k"],
        "duration_seconds": source_entry["duration_seconds"],
        "source_cue_sha256": source_entry["cue_sha256"],
    }
    with wave.open(str(target_path), "rb") as wav:
        params = wav.getparams()
        cue_pcm = wav.readframes(wav.getnframes())
    if (params.nchannels, params.sampwidth, params.framerate, params.comptype) != (1, 2, 48_000, "NONE"):
        raise AudioError("Prior EP04 S10 cue is not 48 kHz mono PCM16")
    entry["cue_pcm_sha256_48k"] = sha256_bytes(cue_pcm)
    entry["active_pcm_48k"] = active_bounds(cue_pcm, 48_000)
    manifest["segments"]["S10"] = entry
    write_json(MANIFEST_PATH, manifest)
    return entry


def prepare_authorization(sample_info: dict[str, Any]) -> None:
    value = {
        "provider": SETTINGS["provider"],
        "scope": "S01-S09 supplied TTS text; S08 split into two complete cues; S10 reused from prior EP04.",
        "authorized": True,
        "source": "Direct human authorization relayed by Sol/root in the current task turn.",
        "authorized_at_utc": AUTHORIZED_AT_UTC,
        "authorization_question": AUTH_QUESTION,
        "authorization_answer": AUTH_ANSWER,
        "settings": {
            "model_selection": SETTINGS["model_selection"],
            "expected_effective_model": EXPECTED_MODEL,
            "voice": EXPECTED_VOICE,
            "rate": SETTINGS["rate"],
            "format": SETTINGS["format"],
            "sample_rate": SAMPLE_RATE,
            "cli_version": CLI_VERSION,
        },
        "preflight_sample": sample_info,
    }
    write_json(AUTH_PATH, value)


def verify_authorization() -> None:
    if not AUTH_PATH.is_file():
        raise AudioError("audio-authorization.json is missing; provider calls are not authorized")
    value = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
    if (
        value.get("authorized") is not True
        or value.get("authorization_question") != AUTH_QUESTION
        or value.get("authorization_answer") != AUTH_ANSWER
        or value.get("authorized_at_utc") != AUTHORIZED_AT_UTC
        or value.get("provider") != SETTINGS["provider"]
        or value.get("settings", {}).get("expected_effective_model") != EXPECTED_MODEL
        or value.get("settings", {}).get("voice") != EXPECTED_VOICE
    ):
        raise AudioError("audio-authorization.json does not contain the exact human authorization for these provider settings")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare-local", action="store_true", help="Repair the verified S04 WAV and reuse S10 without provider calls")
    mode.add_argument("--synthesize", action="store_true", help="Synthesize missing cues serially; S10 is reused")
    args = parser.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    CANONICAL.mkdir(parents=True, exist_ok=True)
    CUES.mkdir(parents=True, exist_ok=True)
    segments = load_source_segments()
    tasks = plan_tasks(segments)
    manifest = load_manifest()

    # The first S04 call was the mandated viability sample. Record only safe metadata,
    # never the temporary signed result URL emitted by the CLI.
    s04 = next(task for task in tasks if task["id"] == "S04")
    s04_key = cache_key(s04["text"])
    s04_raw = RAW / f"S04-{s04_key[:12]}.wav"
    if not s04_raw.is_file():
        raise AudioError("The S04 viability sample is missing")
    s04_payload, s04_info = parse_provider_wav(s04_raw)
    prepare_authorization({
        "id": "S04",
        "effective_model": EXPECTED_MODEL,
        "effective_voice": EXPECTED_VOICE,
        "raw_path": str(s04_raw.relative_to(PROJECT)),
        "raw_sha256": s04_info["raw_sha256"],
        "actual_samples_24k": s04_info["actual_samples_24k"],
        "duration_seconds": round(s04_info["actual_samples_24k"] / SAMPLE_RATE, 6),
        "wav_size_repair_verified": s04_info["repair_verified"],
    })

    if args.prepare_local:
        s04_entry = process_task(s04, manifest, known_model=EXPECTED_MODEL)
        s10_entry = reuse_s10(manifest)
        manifest["status"] = "local_preparation_complete_waiting_for_remaining_tts"
        manifest["synthesis_order"] = "serial"
        write_json(MANIFEST_PATH, manifest)
        verify_authorization()
        print(
            f"Prepared S04 {s04_entry['duration_seconds']:.3f}s and verified/reused S10 "
            f"{s10_entry['duration_seconds']:.3f}s; no provider calls made.",
            flush=True,
        )
        return 0

    verify_authorization()

    s04_duration = s04_info["actual_samples_24k"] / SAMPLE_RATE
    print(f"S04 viability sample: {s04_duration:.2f} s at 24 kHz.", flush=True)
    for index, task in enumerate(tasks, start=1):
        if task["id"] == "S04":
            model = EXPECTED_MODEL
        else:
            model = None
        entry = process_task(task, manifest, known_model=model)
        active_end = entry["active_pcm_48k"]["active_end_sample_exclusive"]
        absolute_active_end = int(task["start_frame"]) * 800 + active_end
        deadline = int(task["active_deadline_frame"]) * 800
        if absolute_active_end > deadline:
            onset = entry["active_pcm_48k"]["onset_sample"]
            overflow_samples = absolute_active_end - deadline
            raise AudioError(
                f"{task['id']} cue PCM is {entry['actual_samples_48k']} samples at 48 kHz "
                f"({entry['duration_seconds']:.6f}s); active bounds are [{onset}, {active_end}) samples, "
                f"and active speech exceeds the slot by {overflow_samples} samples "
                f"({overflow_samples / 48_000:.6f}s); no trimming or speed change was applied"
            )
        print(f"cue {index}/{len(tasks)} {task['id']} {entry['duration_seconds']:.3f}s verified", flush=True)
    reuse_s10(manifest)
    manifest["status"] = "complete"
    manifest["synthesis_order"] = "serial"
    write_json(MANIFEST_PATH, manifest)
    print(f"Saved provider manifest: {MANIFEST_PATH.relative_to(WORK)}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AudioError as exc:
        print(f"audio_synthesis: {exc}", file=sys.stderr)
        raise SystemExit(2)
