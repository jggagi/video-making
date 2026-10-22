#!/usr/bin/env python3
"""Build the 120-second Babel Library audio stems, captions, and PCM master."""

from __future__ import annotations

import argparse
from array import array
from contextlib import ExitStack
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from typing import Any, Iterable, Iterator


PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT.parent
AUDIO = PROJECT / "public" / "audio"
SEGMENTS_PATH = PROJECT / "segments.json"
AUTHORIZATION_PATH = PROJECT / "audio-authorization.json"
PROVIDER_MANIFEST_PATH = AUDIO / "provider-manifest.json"
TIMING_PATH = PROJECT / "audio-timing.json"
MIX_MANIFEST_PATH = AUDIO / "mix-manifest.json"
QA_PATH = WORK / "review" / "audio-qa.json"
SRT_PATH = WORK / "小红书" / "captions.srt"

FPS = 60
SAMPLE_RATE = 48_000
CHANNELS = 2
SAMPLES_PER_FRAME = SAMPLE_RATE // FPS
DURATION_SECONDS = 120
TOTAL_FRAMES = FPS * DURATION_SECONDS
TOTAL_SAMPLES = SAMPLE_RATE * DURATION_SECONDS
BLOCK_SAMPLES = 24_000
ACTIVE_WINDOW_SAMPLES = 240
ACTIVE_MIN_PCM = 48
ACTIVE_PEAK_FRACTION = 0.004
MIN_CAPTION_FRAMES = 2
TARGET_LUFS = -16.0
LOUDNESS_TOLERANCE_LUFS = 1.0
LOUDNORM_TRUE_PEAK = -1.8
LIMITER_CEILING_DBTP = -1.5
ACCEPTED_TRUE_PEAK_DBTP = -1.0


class AudioBuildError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AudioBuildError(f"cannot read {label}: {exc}") from None


def load_source() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    segments = read_json(SEGMENTS_PATH, "segments.json")
    authorization = read_json(AUTHORIZATION_PATH, "audio-authorization.json")
    delivery_path = WORK / "delivery.json"
    delivery = read_json(delivery_path, "delivery.json")

    if not isinstance(delivery, dict):
        raise AudioBuildError("delivery.json must contain a JSON object")
    if not isinstance(authorization, dict):
        raise AudioBuildError("audio-authorization.json must contain a JSON object")
    if delivery.get("duration_seconds") != DURATION_SECONDS or delivery.get("fps") != FPS:
        raise AudioBuildError("delivery.json must declare a 120-second, 60 fps film")
    if delivery.get("total_frames") != TOTAL_FRAMES:
        raise AudioBuildError("delivery.json total_frames must equal 7200")
    if not isinstance(segments, list) or not segments:
        raise AudioBuildError("segments.json must contain a non-empty ordered list")

    prior_end = 0
    seen: set[str] = set()
    for index, item in enumerate(segments):
        if not isinstance(item, dict):
            raise AudioBuildError(f"segment {index} must be a JSON object")
        segment_id = item.get("id")
        start, end = item.get("startFrame"), item.get("endFrame")
        if not isinstance(segment_id, str) or not re.fullmatch(r"S\d{2}", segment_id):
            raise AudioBuildError(f"segment {index} needs an ID such as S01")
        if segment_id in seen:
            raise AudioBuildError(f"duplicate segment ID: {segment_id}")
        seen.add(segment_id)
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= TOTAL_FRAMES:
            raise AudioBuildError(f"{segment_id} has invalid startFrame/endFrame")
        if start < prior_end:
            raise AudioBuildError(f"{segment_id} overlaps or precedes the previous authored window")
        for field in ("display_subtitle", "tts_phonetic_text"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise AudioBuildError(f"{segment_id} needs non-empty {field}")
        chunks = item.get("chunks")
        if not isinstance(chunks, list) or not chunks or any(
            not isinstance(chunk, str) or not chunk.strip() for chunk in chunks
        ):
            raise AudioBuildError(f"{segment_id} needs non-empty caption chunks")
        normalize = lambda text: re.sub(r"\s+", "", text)
        if normalize("".join(chunks)) != normalize(item["display_subtitle"]):
            raise AudioBuildError(f"{segment_id} chunks do not preserve display_subtitle")
        prior_end = end

    if authorization.get("authorized") is not True:
        raise AudioBuildError("audio-authorization.json does not authorize this narration")
    for field in ("provider", "voice", "scope", "source", "text_sha256"):
        if not isinstance(authorization.get(field), str) or not authorization[field].strip():
            raise AudioBuildError(f"audio-authorization.json needs non-empty {field}")
    expected_text_hash = hashlib.sha256(json.dumps(
        [item["tts_phonetic_text"] for item in segments],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    if authorization["text_sha256"] != expected_text_hash:
        raise AudioBuildError(
            "audio-authorization.json text_sha256 does not match the ordered segment texts "
            f"(expected {expected_text_hash})"
        )
    return segments, authorization, delivery


def active_bounds(samples: array) -> tuple[int, int, dict[str, Any]]:
    if not samples:
        raise AudioBuildError("cue WAV has no PCM samples")
    peak = max(abs(value) for value in samples)
    if peak == 0:
        raise AudioBuildError("cue WAV is digital silence")
    threshold = max(ACTIVE_MIN_PCM, round(peak * ACTIVE_PEAK_FRACTION))
    window = min(ACTIVE_WINDOW_SAMPLES, len(samples))
    required_power = window * threshold * threshold
    power = sum(value * value for value in samples[:window])
    first: int | None = None
    last: int | None = None
    for start in range(len(samples) - window + 1):
        if power >= required_power:
            if first is None:
                first = start
            last = start + window
        if start + window < len(samples):
            power += samples[start + window] * samples[start + window] - samples[start] * samples[start]
    if first is None or last is None:
        # Match the synthesis-time EP13 fallback for very short or sparse cues:
        # retain the first/last above-threshold samples rather than rejecting
        # otherwise measurable speech that has no full 5 ms RMS window.
        first = next((index for index, value in enumerate(samples) if abs(value) >= threshold), None)
        last_index = next(
            (index for index in range(len(samples) - 1, -1, -1) if abs(samples[index]) >= threshold),
            None,
        )
        if first is None or last_index is None:
            raise AudioBuildError("cue WAV has no measurable PCM activity")
        last = last_index + 1
    return first, last, {
        "method": "5 ms sliding RMS; threshold=max(48 PCM16, 0.4% of cue peak)",
        "thresholdPcm16": threshold,
        "windowSamples": window,
    }


def safe_project_path(raw: Any, label: str) -> Path:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise AudioBuildError(f"{label} must be a project-relative POSIX path")
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise AudioBuildError(f"{label} must remain within the project directory")
    lexical = PROJECT / relative
    # Check lexical components before resolving; resolving first would hide a
    # symlink that points back inside the project.
    for component in (lexical, *lexical.parents):
        if component == PROJECT.parent:
            break
        if component.is_symlink():
            raise AudioBuildError(f"{label} must not traverse symlinks: {raw}")
    candidate = lexical.resolve()
    try:
        candidate.relative_to(PROJECT.resolve())
    except ValueError:
        raise AudioBuildError(f"{label} escapes the project directory") from None
    if candidate.is_symlink() or not candidate.is_file():
        raise AudioBuildError(f"{label} is missing or not a regular file: {raw}")
    return candidate


def inspect_cue(path: Path, entry: dict[str, Any], segment_id: str) -> dict[str, Any]:
    declared_hash = entry.get("cue_sha256")
    if not isinstance(declared_hash, str) or sha256_file(path) != declared_hash:
        raise AudioBuildError(f"{segment_id} cue SHA-256 differs from provider-manifest.json")
    try:
        with wave.open(str(path), "rb") as wav:
            params = wav.getparams()
            if (params.framerate, params.nchannels, params.sampwidth, params.comptype) != (
                SAMPLE_RATE, 1, 2, "NONE"
            ):
                raise AudioBuildError(f"{segment_id} cue must be mono 48 kHz PCM16")
            raw = wav.readframes(params.nframes)
            sample_count = params.nframes
    except (OSError, wave.Error) as exc:
        raise AudioBuildError(f"cannot read {segment_id} cue WAV: {exc}") from None
    if len(raw) != sample_count * 2:
        raise AudioBuildError(f"{segment_id} cue WAV has an incomplete PCM payload")
    samples = array("h")
    samples.frombytes(raw)
    if sys.byteorder != "little":
        samples.byteswap()
    actual_samples = entry.get("actual_samples_48k")
    duration = entry.get("duration_seconds")
    if type(actual_samples) is not int or actual_samples != sample_count:
        raise AudioBuildError(f"{segment_id} actual_samples_48k differs from the WAV payload")
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration):
        raise AudioBuildError(f"{segment_id} duration_seconds must be finite")
    if abs(float(duration) - sample_count / SAMPLE_RATE) > 1 / SAMPLE_RATE + 1e-9:
        raise AudioBuildError(f"{segment_id} duration_seconds differs from the WAV sample count")
    onset, active_end, method = active_bounds(samples)
    return {
        "path": path,
        "sha256": declared_hash,
        "samples": sample_count,
        "onset": onset,
        "active_end": active_end,
        "active_bounds_method": method,
    }


def load_cues(
    segments: list[dict[str, Any]], authorization: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    manifest = read_json(PROVIDER_MANIFEST_PATH, "public/audio/provider-manifest.json")
    settings = manifest.get("settings") if isinstance(manifest, dict) else None
    entries = manifest.get("segments") if isinstance(manifest, dict) else None
    if not isinstance(settings, dict) or not isinstance(entries, dict):
        raise AudioBuildError("provider-manifest.json needs settings and segments objects")
    for field in ("provider", "effective_model", "voice"):
        if not isinstance(settings.get(field), str) or not settings[field].strip():
            raise AudioBuildError(f"provider-manifest.json settings needs non-empty {field}")
    if settings["provider"] != authorization["provider"] or settings["voice"] != authorization["voice"]:
        raise AudioBuildError("provider-manifest.json provider/voice differs from audio authorization")
    expected_ids = [item["id"] for item in segments]
    if set(entries) != set(expected_ids):
        raise AudioBuildError("provider-manifest.json segment IDs must exactly match segments.json")

    measured: list[dict[str, Any]] = []
    cue_by_id: dict[str, dict[str, Any]] = {}
    previous_cue_end = 0
    previous_voice_end = 0
    for segment in segments:
        segment_id = segment["id"]
        entry = entries.get(segment_id)
        if not isinstance(entry, dict):
            raise AudioBuildError(f"provider-manifest.json {segment_id} entry must be an object")
        path = safe_project_path(entry.get("cue_path"), f"{segment_id} cue_path")
        cue = inspect_cue(path, entry, segment_id)
        cue_start = segment["startFrame"] * SAMPLES_PER_FRAME
        cue_end = cue_start + cue["samples"]
        voice_start = cue_start + cue["onset"]
        voice_end = cue_start + cue["active_end"]
        window_end = segment["endFrame"] * SAMPLES_PER_FRAME
        if voice_end > window_end:
            raise AudioBuildError(
                f"{segment_id} active speech ends beyond its authored window; preserve full-rate speech and revise timing"
            )
        if cue_end > TOTAL_SAMPLES:
            raise AudioBuildError(f"{segment_id} complete cue ends beyond the 120-second master")
        if cue_start < previous_cue_end:
            raise AudioBuildError(f"{segment_id} complete cue overlaps the preceding complete cue")
        if voice_start < previous_voice_end:
            raise AudioBuildError(f"{segment_id} active speech overlaps the preceding segment")
        previous_cue_end = cue_end
        previous_voice_end = voice_end
        item = {
            "id": segment_id,
            "startFrame": segment["startFrame"],
            "endFrame": segment["endFrame"],
            "cueStartSample": cue_start,
            "cueEndSampleExclusive": cue_end,
            "voiceStartSample": voice_start,
            "voiceEndSampleExclusive": voice_end,
            "voiceStartFrame": voice_start / SAMPLES_PER_FRAME,
            "voiceEndFrame": voice_end / SAMPLES_PER_FRAME,
            "measuredSamples": cue["samples"],
            "cueSha256": cue["sha256"],
            "activeBoundsMethod": cue["active_bounds_method"],
        }
        measured.append(item)
        cue_by_id[segment_id] = cue
    return measured, cue_by_id, settings


def caption_rows(segments: list[dict[str, Any]], measured: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    previous_end = 0
    for segment, timing in zip(segments, measured):
        start = max(0, math.floor(timing["voiceStartFrame"]))
        end = min(TOTAL_FRAMES, math.ceil(timing["voiceEndFrame"]))
        chunks = [text.strip() for text in segment["chunks"] if text.strip()]
        if end - start < len(chunks) * MIN_CAPTION_FRAMES:
            raise AudioBuildError(
                f"{segment['id']} measured speech span is too short for its caption chunks at the minimum duration"
            )
        if start < previous_end:
            raise AudioBuildError(f"{segment['id']} caption span overlaps the preceding segment")
        weights = [max(1, len(re.sub(r"\s+", "", text))) for text in chunks]
        extra_frames = end - start - len(chunks) * MIN_CAPTION_FRAMES
        total_weight = sum(weights)
        allocations = [(extra_frames * weight) // total_weight for weight in weights]
        remainders = [(extra_frames * weight) % total_weight for weight in weights]
        remainder = extra_frames - sum(allocations)
        for index in sorted(range(len(chunks)), key=lambda i: (-remainders[i], i))[:remainder]:
            allocations[index] += 1
        cursor = start
        for chunk, extra in zip(chunks, allocations):
            chunk_end = cursor + MIN_CAPTION_FRAMES + extra
            rows.append({
                "segmentId": segment["id"],
                "startFrame": cursor,
                "endFrame": chunk_end,
                "text": chunk,
                "alignment": "estimated_character_weighted_within_measured_active_pcm; not ASR or forced alignment",
            })
            cursor = chunk_end
        if cursor > end:
            raise AudioBuildError(f"{segment['id']} caption timing extends beyond measured speech")
        previous_end = end
    return rows


def srt_time(frame: int) -> str:
    milliseconds = round(frame * 1000 / FPS)
    hours, rest = divmod(milliseconds, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    seconds, millis = divmod(rest, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def render_srt(captions: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for index, caption in enumerate(captions, 1):
        blocks.extend((
            str(index),
            f"{srt_time(caption['startFrame'])} --> {srt_time(caption['endFrame'])}",
            caption["text"],
            "",
        ))
    return "\n".join(blocks)


def duck_gains(block_start: int, count: int, spans: list[dict[str, Any]], depth_db: float) -> list[float]:
    gains = [1.0] * count
    target = 10 ** (depth_db / 20.0)
    attack = int(0.060 * SAMPLE_RATE)
    release = int(0.250 * SAMPLE_RATE)
    block_end = block_start + count
    for span in spans:
        start, end = span["voiceStartSample"], span["voiceEndSampleExclusive"]
        attack_start = max(0, start - attack)
        release_end = min(TOTAL_SAMPLES, end + release)
        left, right = max(block_start, attack_start), min(block_end, start)
        for sample in range(left, right):
            progress = (sample - attack_start) / max(1, attack)
            gains[sample - block_start] = min(gains[sample - block_start], 1.0 - (1.0 - target) * progress)
        left, right = max(block_start, start), min(block_end, end)
        for sample in range(left, right):
            gains[sample - block_start] = min(gains[sample - block_start], target)
        left, right = max(block_start, end), min(block_end, release_end)
        for sample in range(left, right):
            progress = (sample - end) / max(1, release)
            gains[sample - block_start] = min(gains[sample - block_start], target + (1.0 - target) * progress)
    return gains


def write_wav(path: Path, block_iterator: Iterable[bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        for block in block_iterator:
            wav.writeframesraw(block)


def pcm16(value: float) -> int:
    return max(-32768, min(32767, round(value * 32767.0)))


def write_narration(path: Path, cues: dict[str, dict[str, Any]], measured: list[dict[str, Any]]) -> None:
    def blocks() -> Iterator[bytes]:
        with ExitStack() as stack:
            readers: list[tuple[dict[str, Any], wave.Wave_read]] = []
            for item in measured:
                cue = cues[item["id"]]
                reader = stack.enter_context(wave.open(str(cue["path"]), "rb"))
                readers.append((item, reader))
            for block_start in range(0, TOTAL_SAMPLES, BLOCK_SAMPLES):
                count = min(BLOCK_SAMPLES, TOTAL_SAMPLES - block_start)
                block_end = block_start + count
                mono = array("i", [0]) * count
                for item, reader in readers:
                    left = max(block_start, item["cueStartSample"])
                    right = min(block_end, item["cueEndSampleExclusive"])
                    if right <= left:
                        continue
                    source_start = left - item["cueStartSample"]
                    reader.setpos(source_start)
                    raw = reader.readframes(right - left)
                    source = array("h")
                    source.frombytes(raw)
                    if sys.byteorder != "little":
                        source.byteswap()
                    target_start = left - block_start
                    for offset, value in enumerate(source):
                        mono[target_start + offset] += value
                stereo = array("h")
                for value in mono:
                    sample = max(-32768, min(32767, value))
                    stereo.append(sample)
                    stereo.append(sample)
                if sys.byteorder != "little":
                    stereo.byteswap()
                yield stereo.tobytes()
    write_wav(path, blocks())


def motif_sample(age: float, midi: int, amplitude: float) -> float:
    if age < 0.0 or age >= 1.35:
        return 0.0
    frequency = 440.0 * (2.0 ** ((midi - 69) / 12.0))
    attack = min(1.0, age / 0.018)
    envelope = attack * math.exp(-2.8 * age)
    harmonics = (
        math.sin(2.0 * math.pi * frequency * age)
        + 0.22 * math.sin(2.0 * math.pi * frequency * 2.01 * age + 0.1)
        + 0.08 * math.sin(2.0 * math.pi * frequency * 3.97 * age + 0.2)
    )
    return amplitude * envelope * harmonics


def score_sample(sample: int) -> tuple[float, float]:
    seconds = sample / SAMPLE_RATE
    value = 0.0
    if 0.0 <= seconds <= 72.0:
        onset = math.floor(seconds / 6.0) * 6.0
        local = seconds - onset
        note_index = min(2, int(local / 0.62))
        if note_index < 3:
            age = local - note_index * 0.62
            value += motif_sample(age, (60, 64, 67)[note_index], 0.070)
    if 96.0 <= seconds < 110.0:
        age = seconds - 96.0
        fade_in = min(1.0, age / 1.8)
        fade_out = min(1.0, max(0.0, (110.0 - seconds) / 1.4))
        envelope = 0.028 * fade_in * fade_out
        for midi, phase in ((48, 0.0), (52, 0.15), (55, 0.31)):
            frequency = 440.0 * (2.0 ** ((midi - 69) / 12.0))
            value += envelope * math.sin(2.0 * math.pi * frequency * age + phase)
    if 110.0 <= seconds < 120.0:
        age = seconds - 110.0
        fade_in = min(1.0, age / 0.75)
        natural_decay = math.exp(-0.22 * age)
        final_fade = min(1.0, max(0.0, (120.0 - seconds) / 2.0))
        envelope = 0.048 * fade_in * natural_decay * final_fade
        for midi, phase in ((60, 0.0), (63, 0.12), (67, 0.27)):
            frequency = 440.0 * (2.0 ** ((midi - 69) / 12.0))
            value += envelope * (
                0.82 * math.sin(2.0 * math.pi * frequency * age + phase)
                + 0.14 * math.sin(2.0 * math.pi * frequency * 2.0 * age + phase)
                + 0.04 * math.sin(2.0 * math.pi * frequency * 3.0 * age + phase)
            )
    return value, value * 0.985


def write_score(path: Path, measured: list[dict[str, Any]]) -> None:
    def blocks() -> Iterator[bytes]:
        for block_start in range(0, TOTAL_SAMPLES, BLOCK_SAMPLES):
            count = min(BLOCK_SAMPLES, TOTAL_SAMPLES - block_start)
            gains = duck_gains(block_start, count, measured, -8.0)
            stereo = array("h")
            for local in range(count):
                left, right = score_sample(block_start + local)
                gain = gains[local]
                stereo.append(pcm16(left * gain))
                stereo.append(pcm16(right * gain))
            if sys.byteorder != "little":
                stereo.byteswap()
            yield stereo.tobytes()
    write_wav(path, blocks())


def accelerated_pulse_age(seconds: float, start: float, duration: float, start_hz: float, end_hz: float) -> float | None:
    local = seconds - start
    if not 0.0 <= local < duration:
        return None
    slope = (end_hz - start_hz) / duration
    cycles = start_hz * local + 0.5 * slope * local * local
    pulse = math.floor(cycles)
    pulse_time = (math.sqrt(start_hz * start_hz + 2.0 * slope * pulse) - start_hz) / slope if pulse else 0.0
    age = local - pulse_time
    return age if 0.0 <= age < 0.045 else None


def stamp_sample(seconds: float, onset: float, noise: float) -> float:
    age = seconds - onset
    if not 0.0 <= age < 0.34:
        return 0.0
    return (
        0.105 * math.sin(2.0 * math.pi * 86.0 * age) * math.exp(-31.0 * age)
        + 0.038 * math.sin(2.0 * math.pi * 310.0 * age) * math.exp(-48.0 * age)
        + 0.018 * noise * math.exp(-22.0 * age)
    )


def sfx_sample(seconds: float, white: float, low_noise: float) -> tuple[float, float]:
    value = 0.0017 * (white - low_noise) * (0.60 + 0.40 * math.sin(2.0 * math.pi * 0.17 * seconds) ** 2)
    value += stamp_sample(seconds, 3.0, low_noise)
    value += stamp_sample(seconds, 100.5, low_noise)

    tap_age = accelerated_pulse_age(seconds, 74.0, 10.0, 1.2, 4.8)
    if tap_age is not None:
        value += (0.032 * math.sin(2.0 * math.pi * 175.0 * tap_age) + 0.022 * low_noise) * math.exp(-75.0 * tap_age)

    ratchet_age = accelerated_pulse_age(seconds, 74.0, 0.5, 5.0, 22.0)
    if ratchet_age is not None:
        progress = min(1.0, max(0.0, (seconds - 74.0) / 0.5))
        value += (0.035 + 0.045 * progress) * (0.75 * white + 0.25 * math.sin(2.0 * math.pi * 780.0 * ratchet_age))
        value *= 1.0

    click_age = seconds - (4470 * SAMPLES_PER_FRAME / SAMPLE_RATE)
    if 0.0 <= click_age < 0.10:
        value += (0.085 * white + 0.10 * math.sin(2.0 * math.pi * 1450.0 * click_age)) * math.exp(-72.0 * click_age)

    page_age = seconds - 90.0
    if 0.0 <= page_age < 1.45:
        envelope = min(1.0, page_age / 0.12) * math.exp(-1.65 * page_age)
        flutter = 0.55 + 0.45 * math.sin(2.0 * math.pi * (5.1 * page_age + 0.8 * page_age * page_age)) ** 2
        value += 0.055 * low_noise * envelope * flutter
    return value, value * 0.91 + 0.0002 * low_noise


def write_sfx(path: Path, measured: list[dict[str, Any]]) -> None:
    def blocks() -> Iterator[bytes]:
        rng = random.Random(0xBAbe2026)
        low_noise = 0.0
        for block_start in range(0, TOTAL_SAMPLES, BLOCK_SAMPLES):
            count = min(BLOCK_SAMPLES, TOTAL_SAMPLES - block_start)
            gains = duck_gains(block_start, count, measured, -6.0)
            stereo = array("h")
            for local in range(count):
                white = rng.uniform(-1.0, 1.0)
                low_noise += 0.035 * (white - low_noise)
                seconds = (block_start + local) / SAMPLE_RATE
                left, right = sfx_sample(seconds, white, low_noise)
                gain = gains[local]
                stereo.append(pcm16(left * gain))
                stereo.append(pcm16(right * gain))
            if sys.byteorder != "little":
                stereo.byteswap()
            yield stereo.tobytes()
    write_wav(path, blocks())


def inspect_pcm(path: Path) -> dict[str, Any]:
    try:
        with wave.open(str(path), "rb") as wav:
            params = wav.getparams()
            expected = (SAMPLE_RATE, CHANNELS, 2, TOTAL_SAMPLES, "NONE")
            actual = (params.framerate, params.nchannels, params.sampwidth, params.nframes, params.comptype)
            if actual != expected:
                raise AudioBuildError(f"{path.name} has unexpected WAV format/sample count: {actual}")
            peak = 0
            while True:
                raw = wav.readframes(BLOCK_SAMPLES)
                if not raw:
                    break
                values = array("h")
                values.frombytes(raw)
                if sys.byteorder != "little":
                    values.byteswap()
                if values:
                    peak = max(peak, max(abs(value) for value in values))
    except (OSError, wave.Error) as exc:
        raise AudioBuildError(f"cannot validate {path.name}: {exc}") from None
    return {
        "path": path.name,
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "sample_rate": SAMPLE_RATE,
        "channels": CHANNELS,
        "sample_width_bytes": 2,
        "samples_per_channel": TOTAL_SAMPLES,
        "duration_seconds": DURATION_SECONDS,
        "sample_peak_pcm16": peak,
    }


def run_ffmpeg(argv: list[str], label: str) -> str:
    try:
        result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    except FileNotFoundError as exc:
        raise AudioBuildError(f"{label}: executable is unavailable: {exc.filename}") from None
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()[-8:]
        raise AudioBuildError(f"{label} failed (exit {result.returncode}): {' | '.join(detail)}")
    return result.stderr or result.stdout


def parse_loudnorm(text: str) -> dict[str, Any]:
    matches = list(re.finditer(r'\{\s*"input_i"[\s\S]*?\}', text))
    if not matches:
        raise AudioBuildError("FFmpeg loudnorm did not return measurement JSON")
    try:
        value = json.loads(matches[-1].group(0))
    except json.JSONDecodeError:
        raise AudioBuildError("FFmpeg loudnorm returned malformed measurement JSON") from None
    required = ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")
    if any(key not in value for key in required):
        raise AudioBuildError("FFmpeg loudnorm measurement is incomplete")
    try:
        for key in required:
            number = float(value[key])
            if not math.isfinite(number):
                raise ValueError
    except (TypeError, ValueError):
        raise AudioBuildError("FFmpeg loudnorm measurement contains a non-finite value") from None
    return value


def measure_ebur128(path: Path, ffmpeg: str) -> dict[str, float]:
    text = run_ffmpeg([
        ffmpeg, "-hide_banner", "-nostats", "-i", str(path),
        "-map", "0:a:0", "-af", "ebur128=peak=true", "-f", "null", "-",
    ], "final EBU R128 verification")
    integrated = re.search(r"(?m)^\s*I:\s*(-?\d+(?:\.\d+)?)\s+LUFS\s*$", text)
    peak = re.search(r"(?m)^\s*True peak:\s*(-?\d+(?:\.\d+)?)\s+dBTP\s*$", text)
    if peak is None:
        peak = re.search(r"True peak:\s*\n\s*Peak:\s*(-?\d+(?:\.\d+)?)\s+dBFS", text)
    if integrated is None or peak is None:
        raise AudioBuildError("FFmpeg ebur128 did not report integrated LUFS and true peak")
    return {"integrated_lufs": float(integrated.group(1)), "true_peak_dbtp": float(peak.group(1))}


def build_master(path: Path, stems: list[Path], ffmpeg: str) -> dict[str, Any]:
    input_args = [ffmpeg, "-hide_banner", "-nostats"]
    for stem in stems:
        input_args.extend(("-i", str(stem)))
    mix = (
        "[0:a][1:a][2:a]amix=inputs=3:duration=longest:dropout_transition=0:normalize=0,"
        f"aresample={SAMPLE_RATE},apad,atrim=end_sample={TOTAL_SAMPLES},"
        "asetpts=PTS-STARTPTS,aresample=192000"
    )
    first = run_ffmpeg(input_args + [
        "-filter_complex", mix + f",loudnorm=I={TARGET_LUFS}:TP={LOUDNORM_TRUE_PEAK}:LRA=11:print_format=json[out]",
        "-map", "[out]", "-f", "null", "-",
    ], "first-pass loudnorm analysis")
    measured = parse_loudnorm(first)
    second_mix = (
        mix + f",loudnorm=I={TARGET_LUFS}:TP={LOUDNORM_TRUE_PEAK}:LRA=11"
        + f":measured_I={measured['input_i']}:measured_TP={measured['input_tp']}"
        + f":measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}"
        + f":offset={measured['target_offset']}:linear=true:print_format=json"
        + f",alimiter=limit={10 ** (LIMITER_CEILING_DBTP / 20.0):.9f}:attack=5:release=50:level=false"
        + f",aresample={SAMPLE_RATE},apad=whole_len={TOTAL_SAMPLES},atrim=end_sample={TOTAL_SAMPLES}"
        ",asetpts=PTS-STARTPTS[out]"
    )
    second = run_ffmpeg(input_args + [
        "-filter_complex", second_mix, "-map", "[out]", "-ar", str(SAMPLE_RATE), "-ac", str(CHANNELS),
        "-c:a", "pcm_s16le", "-f", "wav", "-y", str(path),
    ], "second-pass loudnorm render")
    second_measurement = parse_loudnorm(second)
    run_ffmpeg([ffmpeg, "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"], "strict master decode")
    final = measure_ebur128(path, ffmpeg)
    if abs(final["integrated_lufs"] - TARGET_LUFS) > LOUDNESS_TOLERANCE_LUFS:
        raise AudioBuildError(
            f"final integrated loudness {final['integrated_lufs']:.2f} LUFS is outside "
            f"{TARGET_LUFS:.1f} ± {LOUDNESS_TOLERANCE_LUFS:.1f} LUFS"
        )
    if final["true_peak_dbtp"] > ACCEPTED_TRUE_PEAK_DBTP:
        raise AudioBuildError(
            f"final true peak {final['true_peak_dbtp']:.2f} dBTP exceeds "
            f"{ACCEPTED_TRUE_PEAK_DBTP:.1f} dBTP"
        )
    return {
        "loudnorm_first_pass": measured,
        "loudnorm_second_pass": second_measurement,
        "final_measurement": final,
        "targets": {
            "integrated_lufs": TARGET_LUFS,
            "integrated_lufs_tolerance": LOUDNESS_TOLERANCE_LUFS,
            "loudnorm_true_peak_dbtp": LOUDNORM_TRUE_PEAK,
            "oversampled_limiter_ceiling_dbtp": LIMITER_CEILING_DBTP,
            "accepted_true_peak_max_dbtp": ACCEPTED_TRUE_PEAK_DBTP,
            "oversample_rate_hz": 192_000,
        },
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def event_metadata() -> list[dict[str, Any]]:
    events = [
        ("paper_wood_stamp_open", 180, 0.34, "low-passed wood and paper stamp"),
        ("mechanical_ratchet", 4440, 30 / FPS, "accelerating local ratchet rising pulse"),
        ("freeze_click", 4470, 0.10, "freeze click at ratchet end"),
        ("page_turn", 5400, 1.45, "procedural page turn"),
        ("paper_wood_stamp_close", 6030, 0.34, "low-passed wood and paper stamp"),
    ]
    return [{
        "id": event_id,
        "startFrame": frame,
        "endFrameExclusive": frame + math.ceil(duration * FPS),
        "startSample": frame * SAMPLES_PER_FRAME,
        "endSampleExclusive": min(TOTAL_SAMPLES, frame * SAMPLES_PER_FRAME + round(duration * SAMPLE_RATE)),
        "durationSeconds": duration,
        "kind": description,
    } for event_id, frame, duration, description in events]


def output_paths() -> dict[str, Path]:
    return {
        "narration": AUDIO / "narration.wav",
        "score": AUDIO / "score.wav",
        "sfx": AUDIO / "sfx.wav",
        "master": AUDIO / "master.wav",
        "audio_timing": TIMING_PATH,
        "audio_qa": QA_PATH,
        "captions": SRT_PATH,
        "mix_manifest": MIX_MANIFEST_PATH,
    }


def verify_existing_outputs(paths: dict[str, Path], input_hash: str) -> bool:
    present = [path for path in paths.values() if path.exists()]
    if not present:
        return False
    manifest_path = paths["mix_manifest"]
    if not manifest_path.is_file():
        raise AudioBuildError(f"audio outputs already exist without a matching mix manifest; preserved: {present[0]}")
    manifest = read_json(manifest_path, "mix-manifest.json")
    if manifest.get("status") != "built" or manifest.get("input_set_sha256") != input_hash:
        raise AudioBuildError("existing audio outputs use different inputs or lack a completed manifest; preserved")
    recorded = manifest.get("files")
    if not isinstance(recorded, dict):
        raise AudioBuildError("existing mix manifest has no output file hash map; preserved")
    for key, path in paths.items():
        if key == "mix_manifest":
            continue
        expected = recorded.get(key, {}).get("sha256") if isinstance(recorded.get(key), dict) else None
        if not path.is_file() or expected != sha256_file(path):
            raise AudioBuildError(f"existing {path.name} is missing or differs from its manifest; preserved")
    return True


def publish_files(staged: dict[str, Path], targets: dict[str, Path]) -> None:
    created: list[Path] = []
    temporary: list[Path] = []
    try:
        for key, target in targets.items():
            source = staged[key]
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() or target.is_symlink():
                raise AudioBuildError(f"refusing to overwrite existing output: {target}")
            temp = target.with_name(f".{target.name}.{os.getpid()}.publish-tmp")
            if temp.exists() or temp.is_symlink():
                raise AudioBuildError(f"refusing to overwrite existing staged output: {temp}")
            temporary.append(temp)
            with source.open("rb") as src, temp.open("xb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
                dst.flush()
                os.fsync(dst.fileno())
            if sha256_file(temp) != sha256_file(source):
                raise AudioBuildError(f"staged copy changed while publishing {target.name}")
            try:
                os.link(temp, target)
            except FileExistsError:
                raise AudioBuildError(f"destination appeared during publish; preserved: {target}") from None
            created.append(target)
            temp.unlink()
        for target in {path.parent for path in targets.values()}:
            try:
                directory_fd = os.open(target, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except OSError:
                pass
    except BaseException:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise
    finally:
        for path in temporary:
            path.unlink(missing_ok=True)


def source_validation() -> int:
    segments, authorization, delivery = load_source()
    print(json.dumps({
        "status": "source_validated",
        "durationSeconds": DURATION_SECONDS,
        "fps": FPS,
        "totalFrames": TOTAL_FRAMES,
        "samplesPerChannel": TOTAL_SAMPLES,
        "segmentCount": len(segments),
        "captionChunkCount": sum(len(item["chunks"]) for item in segments),
        "authorizedProvider": authorization["provider"],
        "authorizedVoice": authorization["voice"],
        "deliverySlug": delivery.get("slug"),
        "mediaBuild": "NOT_RUN",
    }, ensure_ascii=False, indent=2))
    return 0


def run_mix() -> int:
    segments, authorization, delivery = load_source()
    measured, cues, settings = load_cues(segments, authorization)
    captions = caption_rows(segments, measured)
    paths = output_paths()
    input_files = {
        "segments_sha256": sha256_file(SEGMENTS_PATH),
        "authorization_sha256": sha256_file(AUTHORIZATION_PATH),
        "provider_manifest_sha256": sha256_file(PROVIDER_MANIFEST_PATH),
        "cue_sha256": {item["id"]: cues[item["id"]]["sha256"] for item in measured},
    }
    input_set_sha256 = canonical_hash(input_files)
    if verify_existing_outputs(paths, input_set_sha256):
        print("Existing audio outputs match the current input and manifest hashes; nothing overwritten.")
        return 0
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise AudioBuildError("ffmpeg is required for loudnorm, limiting, and final measurement")

    stage_paths: dict[str, Path] = {}
    with tempfile.TemporaryDirectory(prefix="babel-audio-build-") as scratch_name:
        scratch = Path(scratch_name)
        for key in ("narration", "score", "sfx", "master"):
            stage_paths[key] = scratch / f"{key}.wav"
        write_narration(stage_paths["narration"], cues, measured)
        write_score(stage_paths["score"], measured)
        write_sfx(stage_paths["sfx"], measured)
        for key in ("narration", "score", "sfx"):
            inspect_pcm(stage_paths[key])
        loudness = build_master(
            stage_paths["master"],
            [stage_paths["narration"], stage_paths["score"], stage_paths["sfx"]],
            ffmpeg,
        )
        file_records = {
            key: inspect_pcm(stage_paths[key])
            for key in ("narration", "score", "sfx", "master")
        }
        timing = {
            "schema_version": 1,
            "duration_seconds": DURATION_SECONDS,
            "fps": FPS,
            "sample_rate": SAMPLE_RATE,
            "samples_per_channel": TOTAL_SAMPLES,
            "caption_alignment": "estimated character-weighted timing across measured active PCM; not ASR or forced alignment",
            "active_bounds_method": "5 ms sliding RMS; threshold=max(48 PCM16, 0.4% of cue peak)",
            "segments": measured,
            "captions": captions,
        }
        qa = {
            "schema_version": 1,
            "status": "TECHNICAL_AUDIO_CHECKS_PASSED",
            "duration_seconds": DURATION_SECONDS,
            "fps": FPS,
            "sample_rate": SAMPLE_RATE,
            "channels": CHANNELS,
            "samples_per_channel": TOTAL_SAMPLES,
            "outputs": file_records,
            "loudness": loudness,
            "human_listening": "NOT_RUN",
            "acceptance_judgment": "NOT_RECORDED",
        }
        events = event_metadata()
        manifest = {
            "schema_version": 1,
            "status": "built",
            "work": delivery.get("slug"),
            "duration_seconds": DURATION_SECONDS,
            "fps": FPS,
            "sample_rate": SAMPLE_RATE,
            "samples_per_frame": SAMPLES_PER_FRAME,
            "samples_per_channel": TOTAL_SAMPLES,
            "provider": {
                "provider": settings["provider"],
                "effective_model": settings["effective_model"],
                "voice": settings["voice"],
            },
            "inputs": input_files,
            "input_set_sha256": input_set_sha256,
            "files": {},
            "event_frame_sample_mapping": {
                "formula": "sample = frame * 48000 / 60 = frame * 800",
                "events": events,
            },
            "sound_design": {
                "score": "Quiet warm sparse plucked sine-harmonic motif at MIDI 60/64/67 every 6 seconds through frame 4320; lower-register phrase at 96-110 seconds; held C-minor sonority at 110-120 seconds with natural fade.",
                "texture": "Low-level deterministic procedural paper/pencil noise; no external music or SFX assets.",
                "events": events,
                "voice_duck_db": {"score": -8.0, "sfx": -6.0},
                "narration": "Complete mono cues placed at authored segment start frames; no trimming or speed change.",
            },
            "mastering": loudness,
            "limitations": [
                "Caption alignment is estimated from measured active PCM and chunk character weights; no ASR or forced alignment was performed.",
                "Human listening was not performed.",
            ],
        }
        staged: dict[str, Path] = {}
        for key, record in file_records.items():
            staged[key] = stage_paths[key]
        timing_path = scratch / "audio-timing.json"
        qa_path = scratch / "audio-qa.json"
        captions_path = scratch / "captions.srt"
        write_json(timing_path, timing)
        write_json(qa_path, qa)
        captions_path.write_text(render_srt(captions), encoding="utf-8", newline="\n")
        staged.update({"audio_timing": timing_path, "audio_qa": qa_path, "captions": captions_path})
        manifest["files"] = {
            key: {"path": paths[key].relative_to(WORK).as_posix(), "sha256": sha256_file(staged[key]), "bytes": staged[key].stat().st_size}
            for key in staged
        }
        manifest_path = scratch / "mix-manifest.json"
        write_json(manifest_path, manifest)
        staged["mix_manifest"] = manifest_path

        # Publish the manifest last so it never advertises a partial output set.
        publish_order = {key: paths[key] for key in staged if key != "mix_manifest"}
        publish_order["mix_manifest"] = paths["mix_manifest"]
        publish_files(staged, publish_order)
        print(json.dumps({
            "status": "built",
            "work": delivery.get("slug"),
            "durationSeconds": DURATION_SECONDS,
            "samplesPerChannel": TOTAL_SAMPLES,
            "outputs": {key: record["sha256"] for key, record in file_records.items()},
            "integratedLufs": loudness["final_measurement"]["integrated_lufs"],
            "truePeakDbtp": loudness["final_measurement"]["true_peak_dbtp"],
            "humanListening": "NOT_RUN",
        }, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--validate-source", "--source-validation", dest="validate_source", action="store_true",
        help="validate duration, segment, caption, and text-bound authorization inputs without reading cues or mixing",
    )
    mode.add_argument("--mix", action="store_true", help="build the audio stems, captions, and measured PCM master")
    args = parser.parse_args()
    try:
        if args.validate_source:
            return source_validation()
        return run_mix()
    except (AudioBuildError, OSError, ValueError, wave.Error, subprocess.SubprocessError) as exc:
        print(f"build_audio.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
