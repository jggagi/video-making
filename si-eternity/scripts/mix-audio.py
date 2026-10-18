#!/usr/bin/env python3
"""Build the deterministic, frame-aligned v2 voice/music/SFX mix.

This script never calls a TTS provider and never modifies its source clips.
Run it with the project's pinned Python environment after voice-manifest.json
contains all 22 canonical clips.
"""

from __future__ import annotations

import argparse
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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EDITIONS = ("audio-v2", "audio-v3")
EDITION = "audio-v2"
STEMS_EDITION = "audio-v2"
AUDIO_ROOT = PROJECT_ROOT / "public" / EDITION
PLAN_PATH = PROJECT_ROOT / EDITION / "voice-plan.json"
VOICE_MANIFEST_PATH = PROJECT_ROOT / EDITION / "voice-manifest.json"
MIX_MANIFEST_PATH = AUDIO_ROOT / "mix-manifest.json"
ALIGNED_ROOT = AUDIO_ROOT / "aligned"
AMBIENT_PATH = AUDIO_ROOT / "ambient-score.wav"
SFX_PATH = AUDIO_ROOT / "sound-design.wav"
NARRATION_PATH = AUDIO_ROOT / "narration.wav"
VOICE_REVIEW_PATH = AUDIO_ROOT / "voice-review.wav"
PREMASTER_PATH = AUDIO_ROOT / ".mixed-pre-master.wav"
SOUNDTRACK_PATH = AUDIO_ROOT / "soundtrack.wav"

SOURCE_RATE = 24_000
MIX_RATE = 48_000
CHANNELS = 2
SAMPLE_WIDTH = 2
DURATION_SECONDS = 180
TOTAL_FRAMES = MIX_RATE * DURATION_SECONDS
CHUNK_FRAMES = MIX_RATE * 4
EXPECTED_CUES = 22
MAX_ATEMPO = 1.18
TARGET_RMS_DBFS = -20.0
MAX_VOICE_GAIN_DB = 6.0
VOICE_PEAK_CEILING_DBFS = -3.0
NON_SILENT_FLOOR_DBFS = -60.0
MUSIC_GAIN = 1.0
SFX_GAIN = 0.7
DUCK_DB = -7.0
DUCK_LEAD_SECONDS = 0.150
DUCK_ATTACK_SECONDS = 0.090
DUCK_RELEASE_SECONDS = 0.450
MASTER_FADE_IN_SECONDS = 0.001
MASTER_FADE_OUT_START = 179.7
MASTER_FADE_OUT_SECONDS = 0.3
TARGET_LUFS = -18.0
TARGET_TRUE_PEAK_DBTP = -1.5
TARGET_LRA = 8.0
REVIEW_GAP_FRAMES = round(0.150 * SOURCE_RATE)

VOICE_PARAMS = {
    "sampleRate": MIX_RATE,
    "channels": 1,
    "format": "pcm_s16le",
    "targetNonSilentRmsDbfs": TARGET_RMS_DBFS,
    "nonSilentFloorDbfs": NON_SILENT_FLOOR_DBFS,
    "maxGainDb": MAX_VOICE_GAIN_DB,
    "peakCeilingDbfs": VOICE_PEAK_CEILING_DBFS,
    "atempoMax": MAX_ATEMPO,
}


class MixError(RuntimeError):
    """A source or output failed a required mix acceptance check."""


class NeedsSolError(MixError):
    """A timing or quality decision requires the root agent."""


class BlockedError(MixError):
    """A required local executable or input is unavailable."""


@dataclass
class Cue:
    plan: dict[str, Any]
    source_path: Path
    source_sha256: str
    source_pcm24: bytes
    source_frames24: int
    start_frame: int
    deadline_frame: int
    atempo: float
    available_frames: int
    aligned_path: Path | None = None
    aligned_sidecar: Path | None = None
    aligned_pcm16: bytes = b""
    aligned_frames: int = 0
    normalization: dict[str, float] = field(default_factory=dict)
    cache_hit: bool = False

    @property
    def cue_id(self) -> str:
        return str(self.plan["id"])

    @property
    def actual_start_seconds(self) -> float:
        return self.start_frame / MIX_RATE

    @property
    def actual_end_frame(self) -> int:
        return self.start_frame + self.aligned_frames

    @property
    def actual_end_seconds(self) -> float:
        return self.actual_end_frame / MIX_RATE


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _safe_project_path(relative: str, label: str) -> Path:
    candidate = (PROJECT_ROOT / relative).resolve()
    if not candidate.is_relative_to(PROJECT_ROOT.resolve()):
        raise NeedsSolError(f"{label} resolves outside the project: {relative!r}.")
    if not candidate.is_file():
        raise NeedsSolError(f"Missing {label}: {candidate}.")
    return candidate


def _project_relative(path: Path) -> str:
    """Return a resolved project file as a stable project-relative POSIX path."""
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise NeedsSolError(f"Path is outside the project and cannot be recorded: {path}.") from exc


def _tool_path(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise BlockedError(f"Required local tool {name!r} is unavailable on PATH.")
    return executable


def _run_checked(command: list[str], *, input_bytes: bytes | None = None, max_capture: int = 128 * 1024 * 1024) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(
            command,
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise BlockedError(f"Could not execute {command[0]!r}: {exc}.") from exc
    if len(result.stdout) > max_capture:
        raise MixError(f"Unexpectedly large stdout from {command[0]} ({len(result.stdout)} bytes).")
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip().splitlines()
        message = detail[-1] if detail else f"exit status {result.returncode}"
        raise MixError(f"Command failed ({Path(command[0]).name}): {message}")
    return result


def _probe_audio(path: Path) -> dict[str, Any]:
    command = [
        _tool_path("ffprobe"), "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,sample_rate,channels,bits_per_sample,sample_fmt",
        "-show_entries", "format=duration", "-of", "json", str(path),
    ]
    result = _run_checked(command)
    try:
        data = json.loads(result.stdout.decode("utf-8"))
        stream = data["streams"][0]
        return {
            "codecName": stream.get("codec_name"),
            "sampleRate": int(stream["sample_rate"]),
            "channels": int(stream["channels"]),
            "bitsPerSample": int(stream.get("bits_per_sample") or 0),
            "sampleFormat": stream.get("sample_fmt"),
            "durationSeconds": float(data["format"]["duration"]),
        }
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise MixError(f"Could not read audio stream metadata for {path}: {exc}.") from exc


def _decode_pcm_bytes(path: Path, rate: int, channels: int) -> bytes:
    command = [
        _tool_path("ffmpeg"), "-hide_banner", "-v", "error", "-xerror", "-err_detect", "explode",
        "-i", str(path), "-map", "0:a:0", "-vn", "-sn", "-dn",
        "-ac", str(channels), "-ar", str(rate), "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1",
    ]
    return _run_checked(command, max_capture=32 * 1024 * 1024).stdout


def _strict_decode_stats(path: Path, rate: int, channels: int) -> dict[str, int]:
    """Fully decode to PCM in bounded chunks and report exact samples and peak."""
    command = [
        _tool_path("ffmpeg"), "-hide_banner", "-v", "error", "-xerror", "-err_detect", "explode",
        "-i", str(path), "-map", "0:a:0", "-vn", "-sn", "-dn",
        "-ac", str(channels), "-ar", str(rate), "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1",
    ]
    with tempfile.TemporaryFile(mode="w+b") as error_file:
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=error_file)
        except OSError as exc:
            raise BlockedError(f"Could not execute ffmpeg: {exc}.") from exc
        assert process.stdout is not None
        byte_count = 0
        peak = 0
        carry = b""
        frame_bytes = channels * SAMPLE_WIDTH
        while True:
            block = process.stdout.read(1024 * 1024)
            if not block:
                break
            data = carry + block
            usable = len(data) - (len(data) % frame_bytes)
            if usable:
                samples = np.frombuffer(data[:usable], dtype="<i2")
                if samples.size:
                    peak = max(peak, int(np.max(np.abs(samples.astype(np.int32)))))
                byte_count += usable
            carry = data[usable:]
        process.stdout.close()
        return_code = process.wait()
        error_file.seek(0)
        stderr = error_file.read(32_768).decode("utf-8", "replace").strip()
    if return_code != 0:
        last = stderr.splitlines()[-1] if stderr else f"exit status {return_code}"
        raise MixError(f"Strict FFmpeg decode failed for {path}: {last}.")
    if carry or byte_count % frame_bytes:
        raise MixError(f"Decoded samples are not frame-aligned for {path}.")
    return {"frameCount": byte_count // frame_bytes, "peakInteger": peak}


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise NeedsSolError(f"Missing {label}: {path}.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NeedsSolError(f"Cannot read {label} at {path}: {exc}.") from exc
    if not isinstance(value, dict):
        raise NeedsSolError(f"{label} must be a JSON object.")
    return value


def _validate_voice_headers(plan: dict[str, Any], manifest: dict[str, Any]) -> None:
    for label, document in (("voice plan", plan), ("voice manifest", manifest)):
        if int(document.get("sampleRate", -1)) != SOURCE_RATE:
            raise NeedsSolError(f"{label} must declare {SOURCE_RATE} Hz source clips.")
        if document.get("format") != "wav":
            raise NeedsSolError(f"{label} must declare WAV source clips.")
    if int(plan.get("fps", -1)) != 60 or float(plan.get("durationSeconds", -1)) != DURATION_SECONDS:
        raise NeedsSolError("Voice plan must target 180 seconds at 60 fps.")
    if len(plan.get("cues", [])) != EXPECTED_CUES:
        raise NeedsSolError(f"Expected {EXPECTED_CUES} planned voice cues; found {len(plan.get('cues', []))}.")
    if len(manifest.get("cues", [])) != EXPECTED_CUES:
        raise NeedsSolError(f"Expected {EXPECTED_CUES} canonical manifest cues; found {len(manifest.get('cues', []))}.")


def _validate_music_stem(path: Path, label: str) -> dict[str, Any]:
    info = _probe_audio(path)
    if (info["codecName"], info["sampleRate"], info["channels"], info["bitsPerSample"]) != ("pcm_s16le", MIX_RATE, CHANNELS, 16):
        raise NeedsSolError(
            f"{label} must be stereo 48 kHz PCM16; got {info['codecName']}, {info['sampleRate']} Hz, "
            f"{info['channels']} ch, {info['bitsPerSample']} bits."
        )
    if abs(info["durationSeconds"] - DURATION_SECONDS) > 1 / MIX_RATE:
        raise NeedsSolError(f"{label} must be exactly {DURATION_SECONDS} seconds; ffprobe reports {info['durationSeconds']:.9f}.")
    try:
        with wave.open(str(path), "rb") as reader:
            params_ok = (
                reader.getnchannels() == CHANNELS
                and reader.getsampwidth() == SAMPLE_WIDTH
                and reader.getframerate() == MIX_RATE
                and reader.getnframes() == TOTAL_FRAMES
                and reader.getcomptype() == "NONE"
            )
    except (wave.Error, EOFError) as exc:
        raise NeedsSolError(f"{label} has an invalid RIFF/WAV header: {exc}.") from exc
    if not params_ok:
        raise NeedsSolError(f"{label} WAV header does not declare exactly {TOTAL_FRAMES} stereo PCM16 frames at {MIX_RATE} Hz.")
    decoded = _strict_decode_stats(path, MIX_RATE, CHANNELS)
    if decoded["frameCount"] != TOTAL_FRAMES:
        raise NeedsSolError(f"{label} strict decode produced {decoded['frameCount']} frames; expected {TOTAL_FRAMES}.")
    return {**info, **decoded, "sha256": _sha256_file(path)}


def _validate_source_cue(plan_cue: dict[str, Any], manifest_cue: dict[str, Any]) -> tuple[Path, str, bytes, int]:
    cue_id = str(plan_cue.get("id", ""))
    if not re.fullmatch(r"voice-[0-9]{2}", cue_id):
        raise NeedsSolError(f"Invalid cue id {cue_id!r}; expected voice-NN.")
    for key in ("id", "file", "spokenText", "startSeconds", "deadlineSeconds", "subtitleFrom", "subtitleTo"):
        if plan_cue.get(key) != manifest_cue.get(key):
            raise NeedsSolError(f"Plan/manifest mismatch for {cue_id}: field {key!r} differs.")
    source_path = _safe_project_path(str(plan_cue.get("file", "")), f"source clip {cue_id}")
    expected_hash = str(manifest_cue.get("sha256", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        raise NeedsSolError(f"Manifest has no valid canonical SHA-256 for {cue_id}.")
    before = source_path.stat()
    actual_hash = _sha256_file(source_path)
    after = source_path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise NeedsSolError(f"Source clip changed while being verified: {cue_id}.")
    if actual_hash != expected_hash:
        raise NeedsSolError(f"Canonical source SHA-256 mismatch for {cue_id}; expected {expected_hash}, got {actual_hash}.")
    info = _probe_audio(source_path)
    if (info["codecName"], info["sampleRate"], info["channels"], info["bitsPerSample"]) != ("pcm_s16le", SOURCE_RATE, 1, 16):
        raise NeedsSolError(f"{cue_id} must be canonical mono 24 kHz PCM16; got {info}.")
    pcm = _decode_pcm_bytes(source_path, SOURCE_RATE, 1)
    if len(pcm) == 0 or len(pcm) % SAMPLE_WIDTH:
        raise NeedsSolError(f"{cue_id} decoded to empty or misaligned PCM.")
    source_frames = len(pcm) // SAMPLE_WIDTH
    decoded_duration = source_frames / SOURCE_RATE
    manifest_duration = float(manifest_cue.get("durationSeconds", -1))
    if abs(decoded_duration - manifest_duration) > 1 / SOURCE_RATE:
        raise NeedsSolError(
            f"{cue_id} decoded duration {decoded_duration:.9f}s disagrees with manifest {manifest_duration:.9f}s."
        )
    if "decodedSamples" in manifest_cue and int(manifest_cue["decodedSamples"]) != source_frames:
        raise NeedsSolError(f"{cue_id} decoded sample count disagrees with voice-manifest.json.")
    if _sha256_file(source_path) != expected_hash:
        raise NeedsSolError(f"Source clip changed during strict decode: {cue_id}.")
    return source_path, actual_hash, pcm, source_frames


def _preflight_cues(plan: dict[str, Any], manifest: dict[str, Any]) -> list[Cue]:
    manifest_by_id = {str(item.get("id")): item for item in manifest["cues"]}
    if len(manifest_by_id) != EXPECTED_CUES:
        raise NeedsSolError("voice-manifest.json contains duplicate cue IDs.")
    cues: list[Cue] = []
    previous_start = -1
    previous_end = 0
    max_final_frame = math.floor(179.65 * MIX_RATE)
    for plan_cue in plan["cues"]:
        cue_id = str(plan_cue.get("id", ""))
        manifest_cue = manifest_by_id.get(cue_id)
        if manifest_cue is None:
            raise NeedsSolError(f"No canonical manifest record for {cue_id}.")
        start_seconds = float(plan_cue["startSeconds"])
        deadline_seconds = float(plan_cue["deadlineSeconds"])
        if not (math.isfinite(start_seconds) and math.isfinite(deadline_seconds) and 0 <= start_seconds < deadline_seconds <= DURATION_SECONDS):
            raise NeedsSolError(f"Invalid timing window for {cue_id}: {start_seconds}..{deadline_seconds}s.")
        planned_start = round(start_seconds * MIX_RATE)
        deadline = math.floor(deadline_seconds * MIX_RATE)
        if planned_start < previous_start:
            raise NeedsSolError("voice-plan.json cues must be ordered by startSeconds.")
        actual_start = max(planned_start, previous_end)
        available = deadline - actual_start
        if available <= 0:
            raise NeedsSolError(f"No non-overlapping playback slot remains for {cue_id} before its deadline.")
        source_path, source_hash, source_pcm, source_frames = _validate_source_cue(plan_cue, manifest_cue)
        expected_frames48 = source_frames * (MIX_RATE // SOURCE_RATE)
        factor = expected_frames48 / available
        atempo = max(1.0, factor)
        if atempo > MAX_ATEMPO + 1e-9:
            raise NeedsSolError(
                f"{cue_id} needs atempo={atempo:.4f} to fit {deadline_seconds - actual_start / MIX_RATE:.3f}s; "
                f"the limit is {MAX_ATEMPO:.2f}. No output was written and no TTS was called."
            )
        cue = Cue(
            plan=plan_cue,
            source_path=source_path,
            source_sha256=source_hash,
            source_pcm24=source_pcm,
            source_frames24=source_frames,
            start_frame=actual_start,
            deadline_frame=deadline,
            atempo=atempo,
            available_frames=available,
        )
        cues.append(cue)
        previous_start = planned_start
        # Reserve the source-duration estimate until FFmpeg reports the exact aligned length.
        previous_end = actual_start + min(expected_frames48, available)
        if previous_end > max_final_frame:
            raise NeedsSolError(f"{cue_id} would extend past 179.65 seconds before tempo fitting.")
    return cues


def _cache_key(cue: Cue) -> str:
    payload = {
        "schemaVersion": 1,
        "id": cue.cue_id,
        "spokenText": cue.plan["spokenText"],
        "sourceSha256": cue.source_sha256,
        "plannedStartSeconds": cue.plan["startSeconds"],
        "deadlineSeconds": cue.plan["deadlineSeconds"],
        "startFrame": cue.start_frame,
        "availableFrames": cue.available_frames,
        "atempo": round(cue.atempo, 10),
        "parameters": VOICE_PARAMS,
    }
    return _sha256_bytes(_canonical_json(payload))


def _dbfs(value: float) -> float:
    return 20.0 * math.log10(max(value, 1e-12))


def _normalize_voice(samples: np.ndarray, cue_id: str) -> tuple[np.ndarray, dict[str, float]]:
    if samples.dtype != np.float32 or samples.ndim != 1 or samples.size == 0:
        raise MixError(f"Aligned source for {cue_id} is empty or not mono float32.")
    if not bool(np.isfinite(samples).all()):
        raise MixError(f"Aligned source for {cue_id} contains NaN or infinity.")
    floor = np.float32(10.0 ** (NON_SILENT_FLOOR_DBFS / 20.0))
    active_mask = np.abs(samples) >= floor
    if not bool(active_mask.any()):
        raise NeedsSolError(f"{cue_id} has no non-silent samples at the {NON_SILENT_FLOOR_DBFS:g} dBFS threshold.")
    active = samples[active_mask]
    rms_before = float(np.sqrt(np.mean(active * active, dtype=np.float32), dtype=np.float32))
    peak_before = float(np.max(np.abs(samples)))
    if not math.isfinite(rms_before) or rms_before <= 0 or not math.isfinite(peak_before):
        raise NeedsSolError(f"{cue_id} has invalid RMS or peak measurements.")
    desired_gain = 10.0 ** (TARGET_RMS_DBFS / 20.0) / rms_before
    gain = min(10.0 ** (MAX_VOICE_GAIN_DB / 20.0), desired_gain)
    peak_limit = 10.0 ** (VOICE_PEAK_CEILING_DBFS / 20.0)
    if peak_before * gain > peak_limit:
        gain = peak_limit / peak_before
    if not math.isfinite(gain) or gain <= 0:
        raise NeedsSolError(f"Could not derive a finite normalization gain for {cue_id}.")
    normalized = np.multiply(samples, np.float32(gain), dtype=np.float32)
    if not bool(np.isfinite(normalized).all()):
        raise NeedsSolError(f"Normalization produced NaN or infinity for {cue_id}.")
    peak_after = float(np.max(np.abs(normalized)))
    if peak_after > peak_limit + 1e-6:
        raise NeedsSolError(f"{cue_id} peak remains above the {VOICE_PEAK_CEILING_DBFS:g} dBFS ceiling.")
    active_after = normalized[active_mask]
    rms_after = float(np.sqrt(np.mean(active_after * active_after, dtype=np.float32), dtype=np.float32))
    return normalized, {
        "nonSilentFloorDbfs": NON_SILENT_FLOOR_DBFS,
        "nonSilentSampleCount": float(int(active_mask.sum())),
        "nonSilentRmsBeforeDbfs": _dbfs(rms_before),
        "targetRmsDbfs": TARGET_RMS_DBFS,
        "appliedGainDb": 20.0 * math.log10(gain),
        "nonSilentRmsAfterDbfs": _dbfs(rms_after),
        "peakBeforeDbfs": _dbfs(peak_before),
        "peakAfterDbfs": _dbfs(peak_after),
    }


def _tempo_pcm(cue: Cue) -> np.ndarray:
    expected_source_frames48 = cue.source_frames24 * (MIX_RATE // SOURCE_RATE)
    factor = cue.atempo
    for attempt in range(2):
        filters: list[str] = []
        if factor > 1.0 + 1e-9:
            filters.append(f"atempo={factor:.10f}")
        filters.append(f"aresample={MIX_RATE}")
        command = [
            _tool_path("ffmpeg"), "-hide_banner", "-v", "error", "-xerror",
            "-f", "s16le", "-ar", str(SOURCE_RATE), "-ac", "1", "-i", "pipe:0",
            "-map", "0:a:0", "-af", ",".join(filters), "-ac", "1", "-ar", str(MIX_RATE),
            "-c:a", "pcm_f32le", "-f", "f32le", "pipe:1",
        ]
        result = _run_checked(command, input_bytes=cue.source_pcm24)
        if len(result.stdout) % 4:
            raise MixError(f"FFmpeg returned misaligned float samples for {cue.cue_id}.")
        samples = np.frombuffer(result.stdout, dtype="<f4").astype(np.float32, copy=False)
        if not bool(np.isfinite(samples).all()):
            raise NeedsSolError(f"FFmpeg tempo conversion produced NaN or infinity for {cue.cue_id}.")
        if samples.size <= cue.available_frames:
            return samples
        if factor <= 1.0 or attempt == 1:
            raise NeedsSolError(
                f"{cue.cue_id} conversion produced {samples.size} samples for a {cue.available_frames}-sample slot; "
                "whole-clip playback would overlap or miss its deadline."
            )
        factor *= samples.size / cue.available_frames * (1.0 + 2.0 / cue.available_frames)
        if factor > MAX_ATEMPO + 1e-9:
            raise NeedsSolError(
                f"{cue.cue_id} needs atempo={factor:.4f} after sample-accurate fitting; "
                f"the limit is {MAX_ATEMPO:.2f}. No TTS fallback is permitted."
            )
        cue.atempo = factor
    raise AssertionError("unreachable tempo loop")


def _write_pcm_wave(path: Path, pcm: bytes, rate: int, channels: int) -> int:
    frame_bytes = SAMPLE_WIDTH * channels
    if len(pcm) % frame_bytes:
        raise MixError(f"PCM payload for {path.name} is not frame-aligned.")
    frames = len(pcm) // frame_bytes
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with wave.open(str(path), "wb") as writer:
            writer.setnchannels(channels)
            writer.setsampwidth(SAMPLE_WIDTH)
            writer.setframerate(rate)
            writer.setcomptype("NONE", "not compressed")
            writer.writeframes(pcm)
    except (wave.Error, OSError) as exc:
        raise MixError(f"Could not write PCM WAV {path}: {exc}.") from exc
    return frames


def _read_pcm_wave(path: Path, rate: int, channels: int, expected_frames: int | None = None) -> bytes:
    info = _probe_audio(path)
    if (info["codecName"], info["sampleRate"], info["channels"], info["bitsPerSample"]) != ("pcm_s16le", rate, channels, 16):
        raise NeedsSolError(f"Cached WAV {path} has unexpected format: {info}.")
    data = _decode_pcm_bytes(path, rate, channels)
    frame_bytes = channels * SAMPLE_WIDTH
    if len(data) % frame_bytes:
        raise NeedsSolError(f"Cached WAV {path} decoded to partial frames.")
    frames = len(data) // frame_bytes
    if expected_frames is not None and frames != expected_frames:
        raise NeedsSolError(f"Cached WAV {path} has {frames} frames; expected {expected_frames}.")
    return data


def _process_cue(cue: Cue, stage: Path) -> tuple[Path, Path, dict[str, Any]]:
    key = _cache_key(cue)
    cached_wav = ALIGNED_ROOT / f"{cue.cue_id}.wav"
    cached_json = ALIGNED_ROOT / f"{cue.cue_id}.json"
    if cached_wav.is_file() and cached_json.is_file():
        try:
            metadata = json.loads(cached_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            metadata = {}
        if metadata.get("cacheKey") == key and metadata.get("processedSha256") == _sha256_file(cached_wav):
            frames = int(metadata.get("sampleCount", -1))
            pcm = _read_pcm_wave(cached_wav, MIX_RATE, 1, frames)
            if frames <= cue.available_frames:
                cue.aligned_path = cached_wav
                cue.aligned_sidecar = cached_json
                cue.aligned_pcm16 = pcm
                cue.aligned_frames = frames
                cue.normalization = dict(metadata.get("normalization", {}))
                cue.cache_hit = True
                return cached_wav, cached_json, metadata

    float_samples = _tempo_pcm(cue)
    normalized, measurements = _normalize_voice(float_samples, cue.cue_id)
    quantized = np.rint(np.clip(normalized, -1.0, 1.0) * np.float32(32767.0)).astype("<i2")
    pcm = quantized.tobytes()
    frames = len(pcm) // SAMPLE_WIDTH
    if frames > cue.available_frames:
        raise NeedsSolError(f"{cue.cue_id} aligned output exceeds its non-overlapping timing slot.")
    peak_q = int(np.max(np.abs(quantized.astype(np.int32)))) if quantized.size else 0
    peak_q_dbfs = _dbfs(peak_q / 32768.0)
    if peak_q_dbfs > VOICE_PEAK_CEILING_DBFS + 0.02:
        raise NeedsSolError(f"{cue.cue_id} PCM16 peak is {peak_q_dbfs:.3f} dBFS, above the voice ceiling.")
    measurements["pcm16PeakDbfs"] = peak_q_dbfs
    measurements["tempoFactor"] = cue.atempo
    measurements["sampleCount"] = float(frames)
    staged_wav = stage / "aligned" / f"{cue.cue_id}.wav"
    _write_pcm_wave(staged_wav, pcm, MIX_RATE, 1)
    processed_hash = _sha256_file(staged_wav)
    metadata = {
        "schemaVersion": 1,
        "id": cue.cue_id,
        "spokenText": cue.plan["spokenText"],
        "sourcePath": _project_relative(cue.source_path),
        "sourceSha256": cue.source_sha256,
        "cacheKey": key,
        "parameters": VOICE_PARAMS,
        "actualStartSeconds": cue.actual_start_seconds,
        "deadlineSeconds": float(cue.plan["deadlineSeconds"]),
        "atempo": cue.atempo,
        "sampleRate": MIX_RATE,
        "channels": 1,
        "sampleCount": frames,
        "durationSeconds": frames / MIX_RATE,
        "processedSha256": processed_hash,
        "normalization": measurements,
    }
    staged_json = stage / "aligned" / f"{cue.cue_id}.json"
    staged_json.parent.mkdir(parents=True, exist_ok=True)
    staged_json.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cue.aligned_path = staged_wav
    cue.aligned_sidecar = staged_json
    cue.aligned_pcm16 = pcm
    cue.aligned_frames = frames
    cue.normalization = measurements
    return staged_wav, staged_json, metadata


def _write_zeros(writer: wave.Wave_write, frames: int, channels: int, rate: int) -> None:
    block_frames = max(1, rate * 4)
    while frames > 0:
        count = min(frames, block_frames)
        writer.writeframesraw(bytes(count * channels * SAMPLE_WIDTH))
        frames -= count


def _build_voice_review(cues: list[Cue], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    total_frames = 0
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(SAMPLE_WIDTH)
        writer.setframerate(SOURCE_RATE)
        writer.setcomptype("NONE", "not compressed")
        for index, cue in enumerate(cues):
            writer.writeframesraw(cue.source_pcm24)
            total_frames += cue.source_frames24
            if index + 1 < len(cues):
                _write_zeros(writer, REVIEW_GAP_FRAMES, 1, SOURCE_RATE)
                total_frames += REVIEW_GAP_FRAMES
    return total_frames


def _build_narration(cues: list[Cue], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cursor = 0
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(CHANNELS)
        writer.setsampwidth(SAMPLE_WIDTH)
        writer.setframerate(MIX_RATE)
        writer.setcomptype("NONE", "not compressed")
        for cue in cues:
            if cue.aligned_frames <= 0 or len(cue.aligned_pcm16) != cue.aligned_frames * SAMPLE_WIDTH:
                raise MixError(f"Aligned PCM is missing or malformed for {cue.cue_id}.")
            if cue.start_frame < cursor:
                raise NeedsSolError(f"Voice overlap detected before {cue.cue_id}.")
            _write_zeros(writer, cue.start_frame - cursor, CHANNELS, MIX_RATE)
            mono = np.frombuffer(cue.aligned_pcm16, dtype="<i2")
            stereo = np.empty((mono.size, CHANNELS), dtype="<i2")
            stereo[:, 0] = mono
            stereo[:, 1] = mono
            writer.writeframesraw(stereo.tobytes())
            cursor = cue.actual_end_frame
            if cursor > cue.deadline_frame:
                raise NeedsSolError(f"Whole speech clip {cue.cue_id} extends past its deadline.")
        if cursor > TOTAL_FRAMES:
            raise NeedsSolError("Narration exceeds the 180-second master duration.")
        _write_zeros(writer, TOTAL_FRAMES - cursor, CHANNELS, MIX_RATE)


class FloatStereoWaveWriter:
    """Chunked IEEE-float WAV writer so the pre-master never clips."""

    def __init__(self, path: Path, rate: int) -> None:
        self.path = path
        self.rate = rate
        self.data_bytes = 0
        path.parent.mkdir(parents=True, exist_ok=True)
        self.handle: BinaryIO = path.open("wb")
        self.handle.write(b"RIFF" + struct.pack("<I", 36) + b"WAVE")
        self.handle.write(b"fmt " + struct.pack("<IHHIIHH", 16, 3, CHANNELS, rate, rate * CHANNELS * 4, CHANNELS * 4, 32))
        self.handle.write(b"data" + struct.pack("<I", 0))

    def write(self, samples: np.ndarray) -> None:
        if samples.dtype != np.float32 or samples.ndim != 2 or samples.shape[1] != CHANNELS:
            raise MixError("Pre-master writer received a non-stereo-float32 chunk.")
        if not bool(np.isfinite(samples).all()):
            raise NeedsSolError("Pre-master mix contains NaN or infinity.")
        payload = np.asarray(samples, dtype="<f4").tobytes(order="C")
        self.handle.write(payload)
        self.data_bytes += len(payload)

    def close(self) -> None:
        if self.handle.closed:
            return
        if self.data_bytes > 0xFFFFFFFF - 36:
            self.handle.close()
            raise MixError("Pre-master WAV exceeds the classic RIFF size limit.")
        self.handle.seek(4)
        self.handle.write(struct.pack("<I", 36 + self.data_bytes))
        self.handle.seek(40)
        self.handle.write(struct.pack("<I", self.data_bytes))
        self.handle.flush()
        os.fsync(self.handle.fileno())
        self.handle.close()

    def __enter__(self) -> "FloatStereoWaveWriter":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()


def _smoothstep(values: np.ndarray) -> np.ndarray:
    x = np.clip(values, 0.0, 1.0).astype(np.float32, copy=False)
    return x * x * (np.float32(3.0) - np.float32(2.0) * x)


def _duck_envelope(first_frame: int, frame_count: int, cues: list[Cue]) -> np.ndarray:
    times = (np.arange(frame_count, dtype=np.float32) + np.float32(first_frame)) / np.float32(MIX_RATE)
    duck_db = np.zeros(frame_count, dtype=np.float32)
    for cue in cues:
        start = cue.actual_start_seconds
        end = cue.actual_end_seconds
        lead_start = start - DUCK_LEAD_SECONDS
        release_end = end + DUCK_RELEASE_SECONDS
        chunk_start = first_frame / MIX_RATE
        chunk_end = (first_frame + frame_count) / MIX_RATE
        if chunk_end < lead_start or chunk_start > release_end:
            continue
        candidate = np.zeros(frame_count, dtype=np.float32)
        attack_end = lead_start + DUCK_ATTACK_SECONDS
        attack_mask = (times >= lead_start) & (times < attack_end)
        if bool(attack_mask.any()):
            candidate[attack_mask] = np.float32(DUCK_DB) * _smoothstep(
                (times[attack_mask] - np.float32(lead_start)) / np.float32(DUCK_ATTACK_SECONDS)
            )
        hold_mask = (times >= attack_end) & (times <= end)
        candidate[hold_mask] = np.float32(DUCK_DB)
        release_mask = (times > end) & (times <= release_end)
        if bool(release_mask.any()):
            release_t = _smoothstep((times[release_mask] - np.float32(end)) / np.float32(DUCK_RELEASE_SECONDS))
            candidate[release_mask] = np.float32(DUCK_DB) * (np.float32(1.0) - release_t)
        np.minimum(duck_db, candidate, out=duck_db)
    return np.power(np.float32(10.0), duck_db / np.float32(20.0)).astype(np.float32, copy=False)


def _build_premaster(narration_path: Path, stage_path: Path, cues: list[Cue], stem_hashes: dict[str, Any]) -> dict[str, float]:
    stats = {"frameCount": 0, "peak": 0.0, "sumSquares": 0.0, "sampleCount": 0}
    try:
        ambient_reader = wave.open(str(AMBIENT_PATH), "rb")
        sfx_reader = wave.open(str(SFX_PATH), "rb")
        voice_reader = wave.open(str(narration_path), "rb")
    except (wave.Error, OSError) as exc:
        raise NeedsSolError(f"Could not open verified mix stems: {exc}.") from exc
    try:
        with FloatStereoWaveWriter(stage_path, MIX_RATE) as writer:
            for first in range(0, TOTAL_FRAMES, CHUNK_FRAMES):
                frames = min(CHUNK_FRAMES, TOTAL_FRAMES - first)
                expected_bytes = frames * CHANNELS * SAMPLE_WIDTH
                ambient_bytes = ambient_reader.readframes(frames)
                sfx_bytes = sfx_reader.readframes(frames)
                voice_bytes = voice_reader.readframes(frames)
                if len(ambient_bytes) != expected_bytes or len(sfx_bytes) != expected_bytes or len(voice_bytes) != expected_bytes:
                    raise NeedsSolError(f"A stem ended early at output frame {first}.")
                ambient = np.frombuffer(ambient_bytes, dtype="<i2").reshape(frames, CHANNELS).astype(np.float32) / np.float32(32768.0)
                sfx = np.frombuffer(sfx_bytes, dtype="<i2").reshape(frames, CHANNELS).astype(np.float32) / np.float32(32768.0)
                voice = np.frombuffer(voice_bytes, dtype="<i2").reshape(frames, CHANNELS).astype(np.float32) / np.float32(32768.0)
                ambient *= _duck_envelope(first, frames, cues)[:, None]
                ambient += np.float32(SFX_GAIN) * sfx
                ambient += voice
                writer.write(ambient)
                stats["frameCount"] += frames
                stats["peak"] = max(stats["peak"], float(np.max(np.abs(ambient))))
                stats["sumSquares"] += float(np.sum(ambient * ambient, dtype=np.float64))
                stats["sampleCount"] += int(ambient.size)
            if ambient_reader.readframes(1) or sfx_reader.readframes(1) or voice_reader.readframes(1):
                raise NeedsSolError("A stem contains samples beyond the required 180-second duration.")
    finally:
        ambient_reader.close()
        sfx_reader.close()
        voice_reader.close()
    if stats["frameCount"] != TOTAL_FRAMES:
        raise NeedsSolError(f"Premaster contains {stats['frameCount']} frames; expected {TOTAL_FRAMES}.")
    if not math.isfinite(stats["peak"]) or not math.isfinite(stats["sumSquares"]):
        raise NeedsSolError("Premaster measurements are not finite.")
    stats["samplePeakDbfs"] = _dbfs(stats["peak"])
    stats["sampleRmsDbfs"] = _dbfs(math.sqrt(stats["sumSquares"] / stats["sampleCount"]))
    return {key: float(value) for key, value in stats.items()}


def _loudnorm_json(stderr: bytes, label: str) -> dict[str, Any]:
    text = stderr.decode("utf-8", "replace")
    candidates = re.findall(r'\{\s*"input_i".*?\}', text, flags=re.DOTALL)
    if not candidates:
        raise NeedsSolError(f"FFmpeg {label} loudnorm pass returned no measurement JSON.")
    try:
        value = json.loads(candidates[-1])
    except json.JSONDecodeError as exc:
        raise NeedsSolError(f"FFmpeg {label} loudnorm measurements are malformed: {exc}.") from exc
    for key in ("input_i", "input_tp", "input_lra", "input_thresh", "output_i", "output_tp", "output_lra", "output_thresh", "target_offset"):
        try:
            number = float(value[key])
        except (KeyError, TypeError, ValueError) as exc:
            raise NeedsSolError(f"FFmpeg {label} loudnorm field {key!r} is unavailable.") from exc
        if not math.isfinite(number):
            raise NeedsSolError(f"FFmpeg {label} loudnorm field {key!r} is not finite.")
    return value


def _run_loudnorm(premaster: Path, staged_master: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    fade_filter = (
        f"afade=t=in:st=0:d={MASTER_FADE_IN_SECONDS:.6f}:curve=qsin,"
        f"afade=t=out:st={MASTER_FADE_OUT_START:.6f}:d={MASTER_FADE_OUT_SECONDS:.6f}:curve=qsin"
    )
    base = _tool_path("ffmpeg")
    first_command = [
        base, "-hide_banner", "-nostats", "-v", "info", "-xerror", "-i", str(premaster),
        "-map", "0:a:0", "-af", f"{fade_filter},loudnorm=I={TARGET_LUFS}:TP={TARGET_TRUE_PEAK_DBTP}:LRA={TARGET_LRA}:print_format=json",
        "-f", "null", "-",
    ]
    first = subprocess.run(first_command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False)
    if first.returncode != 0:
        detail = first.stderr.decode("utf-8", "replace").strip().splitlines()
        raise NeedsSolError(f"FFmpeg loudnorm analysis failed: {detail[-1] if detail else first.returncode}.")
    measurements = _loudnorm_json(first.stderr, "analysis")
    try:
        measured_i = float(measurements["input_i"])
        measured_tp = float(measurements["input_tp"])
        measured_lra = float(measurements["input_lra"])
        measured_thresh = float(measurements["input_thresh"])
        offset = float(measurements["target_offset"])
    except (TypeError, ValueError) as exc:
        raise NeedsSolError("FFmpeg returned non-numeric loudnorm measurements.") from exc
    loudnorm = (
        f"loudnorm=I={TARGET_LUFS}:TP={TARGET_TRUE_PEAK_DBTP}:LRA={TARGET_LRA}:"
        f"measured_I={measured_i:.6f}:measured_TP={measured_tp:.6f}:"
        f"measured_LRA={measured_lra:.6f}:measured_thresh={measured_thresh:.6f}:"
        f"offset={offset:.6f}:linear=true:print_format=json"
    )
    staged_master.parent.mkdir(parents=True, exist_ok=True)
    second_command = [
        base, "-hide_banner", "-nostats", "-v", "info", "-xerror", "-y", "-i", str(premaster),
        "-map", "0:a:0", "-af", f"{fade_filter},{loudnorm}",
        "-ar", str(MIX_RATE), "-ac", str(CHANNELS), "-c:a", "pcm_s16le", str(staged_master),
    ]
    second = subprocess.run(second_command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False)
    if second.returncode != 0:
        detail = second.stderr.decode("utf-8", "replace").strip().splitlines()
        raise NeedsSolError(f"FFmpeg loudnorm master pass failed: {detail[-1] if detail else second.returncode}.")
    output = _loudnorm_json(second.stderr, "master")
    if str(output.get("normalization_type", "")).lower() not in {"linear", "dynamic"}:
        raise NeedsSolError(
            f"FFmpeg returned an unsupported two-pass loudness normalization mode: "
            f"{output.get('normalization_type')!r}. The unmastered premaster is preserved."
        )
    output_i = float(output["output_i"])
    output_tp = float(output["output_tp"])
    if abs(output_i - TARGET_LUFS) > 0.35:
        raise NeedsSolError(f"Master integrated loudness is {output_i:.2f} LUFS, outside the -18 LUFS target tolerance.")
    if output_tp > TARGET_TRUE_PEAK_DBTP + 0.15:
        raise NeedsSolError(f"Master true peak is {output_tp:.2f} dBTP, above the -1.5 dBTP target tolerance.")
    return measurements, output


def _validate_master(path: Path) -> dict[str, Any]:
    info = _probe_audio(path)
    expected = ("pcm_s16le", MIX_RATE, CHANNELS, 16)
    actual = (info["codecName"], info["sampleRate"], info["channels"], info["bitsPerSample"])
    if actual != expected:
        raise NeedsSolError(f"Master WAV header is {actual}; expected {expected}.")
    if abs(info["durationSeconds"] - DURATION_SECONDS) > 1 / MIX_RATE:
        raise NeedsSolError(f"Master duration is {info['durationSeconds']:.9f}s; expected exactly 180s.")
    decoded = _strict_decode_stats(path, MIX_RATE, CHANNELS)
    if decoded["frameCount"] != TOTAL_FRAMES:
        raise NeedsSolError(f"Master strict decode produced {decoded['frameCount']} frames; expected {TOTAL_FRAMES}.")
    if decoded["peakInteger"] >= 32760:
        raise NeedsSolError(f"Master sample peak {decoded['peakInteger']} approaches PCM full scale; possible clipping.")
    return {**info, **decoded, "sha256": _sha256_file(path), "decodedDurationSeconds": decoded["frameCount"] / MIX_RATE}


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _commit_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, target)


def run_mix() -> dict[str, Any]:
    for name in ("ffmpeg", "ffprobe"):
        _tool_path(name)
    plan = _read_json(PLAN_PATH, "voice plan")
    voice_manifest = _read_json(VOICE_MANIFEST_PATH, "voice manifest")
    _validate_voice_headers(plan, voice_manifest)

    # Read and fully validate the two immutable 180-second PCM16 stereo source stems.
    ambient_info = _validate_music_stem(AMBIENT_PATH, "ambient-score.wav")
    sfx_info = _validate_music_stem(SFX_PATH, "sound-design.wav")
    cues = _preflight_cues(plan, voice_manifest)
    if cues[-1].start_frame >= TOTAL_FRAMES or cues[-1].deadline_frame > TOTAL_FRAMES:
        raise NeedsSolError("Voice timeline exceeds the exact 180-second master window.")

    AUDIO_ROOT.mkdir(parents=True, exist_ok=True)
    stage_context = tempfile.TemporaryDirectory(prefix=".mix-stage-", dir=AUDIO_ROOT)
    stage = Path(stage_context.name)
    keep_premaster = False
    try:
        cue_metadata: list[dict[str, Any]] = []
        for cue in cues:
            aligned_wav, aligned_sidecar, metadata = _process_cue(cue, stage)
            cue.aligned_path = aligned_wav
            cue.aligned_sidecar = aligned_sidecar
            cue_metadata.append(metadata)
        review_path = stage / "voice-review.wav"
        review_frames = _build_voice_review(cues, review_path)
        narration_path = stage / "narration.wav"
        _build_narration(cues, narration_path)

        # Verify the independent narration header and full decoded length before mixing.
        narration_info = _probe_audio(narration_path)
        if (narration_info["codecName"], narration_info["sampleRate"], narration_info["channels"], narration_info["bitsPerSample"]) != ("pcm_s16le", MIX_RATE, CHANNELS, 16):
            raise NeedsSolError(f"Narration stem has an invalid PCM16 stereo header: {narration_info}.")
        narration_decode = _strict_decode_stats(narration_path, MIX_RATE, CHANNELS)
        if narration_decode["frameCount"] != TOTAL_FRAMES:
            raise NeedsSolError("Narration stem does not decode to exactly 180 seconds.")
        review_info = _probe_audio(review_path)
        review_decode = _strict_decode_stats(review_path, SOURCE_RATE, 1)
        if review_decode["frameCount"] != review_frames:
            raise NeedsSolError("Voice review stem failed strict decode or its sample count differs.")

        staged_premaster = stage / ".mixed-pre-master.wav"
        premaster_measurements = _build_premaster(narration_path, staged_premaster, cues, {"ambient": ambient_info, "sfx": sfx_info})
        # Preserve the exact unmastered signal if loudness or final decode validation fails.
        premaster_stage_hash = _sha256_file(staged_premaster)
        _commit_file(staged_premaster, PREMASTER_PATH)
        keep_premaster = True

        staged_master = stage / "soundtrack.wav"
        loudnorm_analysis, loudnorm_output = _run_loudnorm(PREMASTER_PATH, staged_master)
        master_info = _validate_master(staged_master)

        # Prepare output metadata and all hashes before replacing any completed deliverable.
        outputs = {
            "narration": {"path": _project_relative(NARRATION_PATH), "sha256": _sha256_file(narration_path), "sampleCount": TOTAL_FRAMES},
            "voiceReview": {"path": _project_relative(VOICE_REVIEW_PATH), "sha256": _sha256_file(review_path), "sampleCount": review_frames},
            "soundtrack": {"path": _project_relative(SOUNDTRACK_PATH), **master_info},
        }
        source_hashes = {
            "ambientScore": {"path": _project_relative(AMBIENT_PATH), "sha256": ambient_info["sha256"]},
            "soundDesign": {"path": _project_relative(SFX_PATH), "sha256": sfx_info["sha256"]},
            "voice": [
                {"id": cue.cue_id, "path": _project_relative(cue.source_path), "sha256": cue.source_sha256}
                for cue in cues
            ],
        }
        mix_manifest = {
            "schemaVersion": 1,
            "project": "一眼万年 (One Blink, Ten Millennia)" if EDITION == "audio-v3" else "The Half-Second Eternity",
            "edition": EDITION,
            "stemsEdition": STEMS_EDITION,
            "durationSeconds": DURATION_SECONDS,
            "sampleRate": MIX_RATE,
            "channels": CHANNELS,
            "sampleCount": TOTAL_FRAMES,
            "sampleFormat": "pcm_s16le",
            "sources": source_hashes,
            "gains": {"music": MUSIC_GAIN, "soundDesign": SFX_GAIN, "voice": 1.0},
            "ducking": {
                "targetMusicReductionDb": DUCK_DB,
                "leadSeconds": DUCK_LEAD_SECONDS,
                "attackSeconds": DUCK_ATTACK_SECONDS,
                "releaseSeconds": DUCK_RELEASE_SECONDS,
                "envelope": "smoothstep; overlapping speech envelopes use the deepest attenuation",
                "appliesTo": "music only",
            },
            "voiceNormalization": VOICE_PARAMS,
            "masterFade": {"inSeconds": MASTER_FADE_IN_SECONDS, "outStartSeconds": MASTER_FADE_OUT_START, "outSeconds": MASTER_FADE_OUT_SECONDS},
            "loudnorm": {
                "targetIntegratedLufs": TARGET_LUFS,
                "targetTruePeakDbtp": TARGET_TRUE_PEAK_DBTP,
                "targetLra": TARGET_LRA,
                "analysisPass": loudnorm_analysis,
                "masterPass": loudnorm_output,
                "normalizationType": loudnorm_output.get("normalization_type"),
            },
            "premaster": {
                "sha256": premaster_stage_hash,
                "samplePeakDbfs": premaster_measurements["samplePeakDbfs"],
                "sampleRmsDbfs": premaster_measurements["sampleRmsDbfs"],
                "frameCount": int(premaster_measurements["frameCount"]),
                "retainedOnValidationError": True,
            },
            "truePeakDbtp": float(loudnorm_output["output_tp"]),
            "decodedMasterDurationSeconds": master_info["decodedDurationSeconds"],
            "decodedMasterSampleCount": master_info["frameCount"],
            "cues": [
                {
                    "id": cue.cue_id,
                    "spokenText": cue.plan["spokenText"],
                    "plannedStartSeconds": float(cue.plan["startSeconds"]),
                    "actualStartSeconds": cue.actual_start_seconds,
                    "deadlineSeconds": float(cue.plan["deadlineSeconds"]),
                    "actualEndSeconds": cue.actual_end_seconds,
                    "sourceDurationSeconds": cue.source_frames24 / SOURCE_RATE,
                    "alignedDurationSeconds": cue.aligned_frames / MIX_RATE,
                    "sourceSampleCount24k": cue.source_frames24,
                    "alignedSampleCount48k": cue.aligned_frames,
                    "atempo": cue.atempo,
                    "tempoChanged": cue.atempo > 1.0 + 1e-9,
                    "cacheHit": cue.cache_hit,
                    "normalization": cue.normalization,
                    "alignedSha256": _sha256_file(cue.aligned_path) if cue.aligned_path else None,
                }
                for cue in cues
            ],
            "outputs": outputs,
        }

        # Commit caches and independent stems only after the final master passes all checks.
        for cue in cues:
            if cue.cache_hit:
                continue
            assert cue.aligned_path is not None and cue.aligned_sidecar is not None
            _commit_file(cue.aligned_path, ALIGNED_ROOT / f"{cue.cue_id}.wav")
            _commit_file(cue.aligned_sidecar, ALIGNED_ROOT / f"{cue.cue_id}.json")
        _commit_file(narration_path, NARRATION_PATH)
        _commit_file(review_path, VOICE_REVIEW_PATH)
        _commit_file(staged_master, SOUNDTRACK_PATH)
        _write_json(MIX_MANIFEST_PATH, mix_manifest)
        keep_premaster = False
        PREMASTER_PATH.unlink(missing_ok=True)
        print(f"PASS: 22 cues aligned; master is exactly {TOTAL_FRAMES} stereo frames at {MIX_RATE} Hz.")
        print(f"Soundtrack: {SOUNDTRACK_PATH}")
        print(f"Mix manifest: {MIX_MANIFEST_PATH}")
        return mix_manifest
    except Exception:
        # The project-level premaster is intentionally kept once it has been completed.
        if keep_premaster:
            print(f"Unmastered premaster preserved for diagnosis: {PREMASTER_PATH}", file=sys.stderr)
        raise
    finally:
        stage_context.cleanup()


def main(argv: list[str] | None = None) -> int:
    global PROJECT_ROOT, EDITION, STEMS_EDITION, AUDIO_ROOT, PLAN_PATH, VOICE_MANIFEST_PATH, MIX_MANIFEST_PATH, ALIGNED_ROOT
    global AMBIENT_PATH, SFX_PATH, NARRATION_PATH, VOICE_REVIEW_PATH, PREMASTER_PATH, SOUNDTRACK_PATH
    parser = argparse.ArgumentParser(
        description="Align the immutable canonical voice cues, duck the existing score/SFX, and master the exact 180-second soundtrack."
    )
    parser.add_argument(
        "--project-root", type=Path, default=PROJECT_ROOT,
        help="Project root (defaults to the si-eternity directory containing this script).",
    )
    parser.add_argument("--edition", choices=EDITIONS, default="audio-v2", help="Edition plan and output directory (default: audio-v2).")
    parser.add_argument("--stems-edition", choices=EDITIONS, default=None, help="Edition containing ambient-score.wav and sound-design.wav (default: selected edition).")
    parser.add_argument("--version", action="version", version="mix-audio.py 1.0")
    args = parser.parse_args(argv)
    PROJECT_ROOT = args.project_root.resolve()
    EDITION = args.edition
    STEMS_EDITION = args.stems_edition or EDITION
    AUDIO_ROOT = PROJECT_ROOT / "public" / EDITION
    PLAN_PATH = PROJECT_ROOT / EDITION / "voice-plan.json"
    VOICE_MANIFEST_PATH = PROJECT_ROOT / EDITION / "voice-manifest.json"
    MIX_MANIFEST_PATH = AUDIO_ROOT / "mix-manifest.json"
    ALIGNED_ROOT = AUDIO_ROOT / "aligned"
    STEMS_ROOT = PROJECT_ROOT / "public" / STEMS_EDITION
    AMBIENT_PATH = STEMS_ROOT / "ambient-score.wav"
    SFX_PATH = STEMS_ROOT / "sound-design.wav"
    NARRATION_PATH = AUDIO_ROOT / "narration.wav"
    VOICE_REVIEW_PATH = AUDIO_ROOT / "voice-review.wav"
    PREMASTER_PATH = AUDIO_ROOT / ".mixed-pre-master.wav"
    SOUNDTRACK_PATH = AUDIO_ROOT / "soundtrack.wav"
    try:
        run_mix()
    except NeedsSolError as exc:
        print(f"NEEDS_SOL: {exc}", file=sys.stderr)
        return 2
    except BlockedError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 3
    except MixError as exc:
        print(f"NEEDS_SOL: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
