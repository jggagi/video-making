#!/usr/bin/env python3
"""Build EP19's deterministic 90-second procedural audio package.

The narration cues are treated as immutable source waveforms: they are decoded
and resampled, placed at their authored frame, and never time-stretched or
trimmed.  A cue that cannot fit its authored window is an input error for the
production owner to resolve.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any

import numpy as np


PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT.parent
SAMPLE_RATE = 48_000
FRAME_RATE = 60
SAMPLES_PER_FRAME = SAMPLE_RATE // FRAME_RATE
TOTAL_FRAMES = 5_400
TOTAL_SAMPLES = TOTAL_FRAMES * SAMPLES_PER_FRAME
SILENCE_START_FRAME = 4_860
SILENCE_END_FRAME = 4_890
SILENCE_START_SAMPLE = SILENCE_START_FRAME * SAMPLES_PER_FRAME
SILENCE_END_SAMPLE = SILENCE_END_FRAME * SAMPLES_PER_FRAME
SILENCE_SLICE = slice(SILENCE_START_SAMPLE, SILENCE_END_SAMPLE)
VOICE_GAIN = 0.56
LOUDNESS_TARGET = -16.0
TRUE_PEAK_TARGET = -1.5
TRUE_PEAK_SAFETY = -1.25


EVENT_SPECS: list[dict[str, Any]] = [
    {
        "frame": 60,
        "name": "glass_slide_dark_bowed_cello",
        "durationFrames": 126,
        "kind": "glass_slide",
        "gain": 0.055,
        "components": [[690.0, 470.0, 0.68], [110.0, 108.0, 0.55], [220.0, 217.0, 0.15]],
        "envelope": "short_attack_exponential_room_tail",
        "pan": -0.12,
    },
    {
        "frame": 840,
        "name": "inverted_mirror_reverse_reverb_rise",
        "durationFrames": 210,
        "kind": "reverse_rise",
        "gain": 0.043,
        "components": [[180.0, 660.0, 0.55], [360.0, 1_320.0, 0.20]],
        "envelope": "slow_quadratic_rise_with_soft_release",
        "pan": 0.10,
    },
    {
        "frame": 1_500,
        "name": "water_surface_tension_break_low_thud",
        "durationFrames": 90,
        "kind": "water_thud",
        "gain": 0.070,
        "components": [[58.0, 39.0, 0.78], [510.0, 390.0, 0.18], [1_020.0, 780.0, 0.08]],
        "envelope": "low_thud_with_damped_surface_ripples",
        "pan": 0.0,
    },
    {
        "frame": 2_220,
        "name": "silk_unspooling_warm_golden_shimmer",
        "durationFrames": 150,
        "kind": "silk_shimmer",
        "gain": 0.041,
        "components": [[720.0, 910.0, 0.42], [1_080.0, 1_365.0, 0.28], [1_440.0, 1_820.0, 0.12]],
        "envelope": "breathing_pulses_with_gentle_release",
        "pan": 0.16,
    },
    {
        "frame": 2_940,
        "name": "interlocking_melancholic_pad_swell",
        "durationFrames": 360,
        "kind": "pad_swell",
        "gain": 0.030,
        "components": [[110.0, 110.0, 0.48], [146.83, 146.83, 0.42], [164.81, 164.81, 0.38], [329.62, 329.62, 0.10]],
        "envelope": "slow_interlocking_two_phase_swell",
        "pan": -0.04,
    },
    {
        "frame": 3_900,
        "name": "puppet_string_tension_snap_cold_glass",
        "durationFrames": 42,
        "kind": "string_snap",
        "gain": 0.060,
        "components": [[1_420.0, 820.0, 0.62], [710.0, 410.0, 0.23], [110.0, 72.0, 0.15]],
        "envelope": "sharp_tension_pulse_and_short_decay",
        "pan": 0.10,
    },
    {
        "frame": 4_500,
        "name": "suspended_ethereal_string_harmonic",
        "durationFrames": 360,
        "kind": "suspended_harmonic",
        "gain": 0.027,
        "components": [[440.0, 440.0, 0.52], [660.0, 659.0, 0.38], [880.0, 882.0, 0.16]],
        "envelope": "breathless_hold_and_long_fade",
        "pan": -0.08,
    },
    {
        "frame": 4_860,
        "name": "absolute_silence_all_stems",
        "durationFrames": 30,
        "kind": "absolute_silence_marker",
        "gain": 0.0,
        "components": [],
        "envelope": "exact_zero_samples_on_every_stem",
        "pan": 0.0,
    },
    {
        "frame": 4_890,
        "name": "single_descending_pizzicato_warm_room_tail",
        "durationFrames": 84,
        "kind": "descending_pizzicato",
        "gain": 0.083,
        "components": [[164.81, 110.0, 0.76], [329.62, 220.0, 0.25], [494.43, 330.0, 0.09]],
        "envelope": "single_pluck_short_body_tiny_warm_room_fade",
        "pan": 0.0,
        "echoes": [[0.105, 0.20], [0.190, 0.11], [0.315, 0.055]],
    },
]


class BuildError(RuntimeError):
    """A production input or processing result needs the owner to resolve it."""


def _ffmpeg_path() -> str:
    binary = shutil.which("ffmpeg")
    if not binary:
        raise BuildError("ffmpeg is required on PATH to decode cues and master audio.")
    return binary


def _ffmpeg_env() -> dict[str, str]:
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    return env


def load_segments() -> list[dict[str, Any]]:
    path = PROJECT / "segments.json"
    if not path.is_file():
        raise BuildError(f"Missing segment manifest: {path}")
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BuildError(f"Cannot read segment manifest {path}: {exc}") from exc
    if not isinstance(rows, list) or [row.get("id") for row in rows] != [f"S{i:02d}" for i in range(1, 9)]:
        raise BuildError("segments.json must contain S01 through S08 in authored order.")
    for row in rows:
        if not isinstance(row.get("startFrame"), int) or not isinstance(row.get("endFrame"), int):
            raise BuildError(f"{row.get('id', 'segment')}: startFrame and endFrame must be integers.")
        if row["startFrame"] < 0 or row["endFrame"] <= row["startFrame"] or row["endFrame"] > TOTAL_FRAMES:
            raise BuildError(f"{row['id']}: invalid authored frame window {row['startFrame']}..{row['endFrame']}.")
        if not isinstance(row.get("display_subtitle"), str) or not row["display_subtitle"].strip():
            raise BuildError(f"{row['id']}: display_subtitle is required for timed captions.")
    if rows[-1]["endFrame"] != TOTAL_FRAMES:
        raise BuildError(f"S08 must end at frame {TOTAL_FRAMES}; found {rows[-1]['endFrame']}.")
    return rows


def decode_cue(path: Path) -> np.ndarray:
    if not path.is_file():
        raise BuildError(f"Missing narration cue: {path}")
    command = [
        _ffmpeg_path(), "-hide_banner", "-v", "error", "-nostdin",
        "-i", str(path), "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE),
        "-acodec", "pcm_s16le", "-f", "s16le", "pipe:1",
    ]
    result = subprocess.run(command, capture_output=True, check=False, env=_ffmpeg_env())
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise BuildError(f"ffmpeg could not decode {path.name}: {detail or result.returncode}")
    if not result.stdout or len(result.stdout) % 2:
        raise BuildError(f"{path.name}: ffmpeg returned empty or malformed PCM16 data.")
    return np.frombuffer(result.stdout, dtype="<i2").copy()


def active_bounds(samples: np.ndarray) -> tuple[int, int]:
    """Return sample bounds for voice-active 10 ms windows; this never edits audio."""
    window = SAMPLE_RATE // 100
    values = samples.astype(np.float32) / 32768.0
    count = math.ceil(len(values) / window)
    padded = np.pad(values, (0, count * window - len(values)))
    rms = np.sqrt(np.mean(padded.reshape(count, window) ** 2, axis=1))
    threshold = 10.0 ** (-50.0 / 20.0)
    active = np.flatnonzero(rms >= threshold)
    if active.size == 0:
        threshold = 10.0 ** (-60.0 / 20.0)
        active = np.flatnonzero(rms >= threshold)
    if active.size == 0:
        raise BuildError("Cue has no measurable active audio above -60 dBFS RMS in 10 ms windows.")
    start = int(active[0] * window)
    end = min(len(samples), int((active[-1] + 1) * window))
    return start, end


def cue_start_frame(row: dict[str, Any]) -> int:
    # The authored final quote waits through the 30-frame silence and a 12-frame pluck lead-in.
    return 4_902 if row["id"] == "S08" else row["startFrame"]


def inspect_cues(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[np.ndarray]]:
    cue_dir = PROJECT / "public" / "audio" / "cues"
    reports: list[dict[str, Any]] = []
    sources: list[np.ndarray] = []
    for row in rows:
        sid = row["id"]
        samples = decode_cue(cue_dir / f"{sid}.wav")
        onset, active_end = active_bounds(samples)
        start_frame = cue_start_frame(row)
        required_end_frame = start_frame + math.ceil(len(samples) / SAMPLES_PER_FRAME)
        authored_end = row["endFrame"]
        reports.append({
            "id": sid,
            "actualSamples": int(len(samples)),
            "durationSeconds": round(len(samples) / SAMPLE_RATE, 6),
            "activeOnsetSample": onset,
            "activeEndSample": active_end,
            "activeOnsetSeconds": round(onset / SAMPLE_RATE, 6),
            "startFrame": start_frame,
            "requiredEndFrame": required_end_frame,
            "authoredEndFrame": authored_end,
            "fitsAuthoredWindow": start_frame * SAMPLES_PER_FRAME + len(samples) <= authored_end * SAMPLES_PER_FRAME,
        })
        sources.append(samples)
    return reports, sources


def _smoothstep(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(values, 0.0, 1.0)
    return clipped * clipped * (3.0 - 2.0 * clipped)


def voice_duck_envelope(narration: np.ndarray) -> np.ndarray:
    block = SAMPLE_RATE // 50  # 20 ms control rate
    mono = narration[:, 0]
    blocks = math.ceil(len(mono) / block)
    padded = np.pad(mono, (0, blocks * block - len(mono)))
    rms = np.sqrt(np.mean(padded.reshape(blocks, block) ** 2, axis=1))
    presence = np.clip((rms - 0.003) / 0.035, 0.0, 1.0)
    smooth = np.zeros_like(presence)
    value = 0.0
    for index, target in enumerate(presence):
        coefficient = 0.24 if target > value else 0.055
        value += coefficient * (float(target) - value)
        smooth[index] = value
    sample_gain = np.repeat(1.0 - 0.62 * smooth, block)[: len(mono)]
    return sample_gain.astype(np.float32)


def make_score(narration: np.ndarray) -> np.ndarray:
    time = np.arange(TOTAL_SAMPLES, dtype=np.float64) / SAMPLE_RATE
    tremble = 1.0 + 0.0017 * np.sin(2.0 * np.pi * time / 17.0)
    phrase = 0.33 + 0.055 * np.sin(2.0 * np.pi * time / 31.0 + 0.3)
    swell = _smoothstep((time - 49.0) / 8.0)
    release = 1.0 - _smoothstep((time - 76.0) / 11.0)
    amplitude = (0.016 * phrase * (1.0 + 0.56 * swell) * release).astype(np.float32)
    harmonic = (
        0.40 * np.sin(2.0 * np.pi * 110.0 * time)
        + 0.34 * np.sin(2.0 * np.pi * 146.83 * time + 0.15)
        + 0.30 * np.sin(2.0 * np.pi * 164.81 * time + 0.37)
        + 0.08 * np.sin(2.0 * np.pi * 220.0 * time + 0.11)
    )
    mono = (amplitude * tremble * harmonic).astype(np.float32)
    del time, tremble, phrase, swell, release, amplitude, harmonic
    mono *= voice_duck_envelope(narration)
    score = np.empty((TOTAL_SAMPLES, 2), dtype=np.float32)
    score[:, 0] = mono * 0.985
    score[:, 1] = mono * 0.965
    del mono
    score[SILENCE_SLICE] = 0.0
    return score


def _component(freq0: float, freq1: float, t: np.ndarray, duration: float) -> np.ndarray:
    if abs(freq1 - freq0) < 1e-9:
        phase = 2.0 * np.pi * freq0 * t
    else:
        phase = 2.0 * np.pi * (freq0 * t + 0.5 * (freq1 - freq0) * t * t / duration)
    return np.sin(phase)


def _event_envelope(kind: str, progress: np.ndarray, t: np.ndarray, duration: float) -> np.ndarray:
    if kind == "glass_slide":
        return np.minimum(1.0, t / 0.035) * np.exp(-3.8 * progress)
    if kind == "reverse_rise":
        return _smoothstep(progress / 0.72) * (1.0 - _smoothstep((progress - 0.80) / 0.20))
    if kind == "water_thud":
        return np.exp(-7.0 * progress) * (0.66 + 0.34 * np.cos(2.0 * np.pi * 4.0 * progress))
    if kind == "silk_shimmer":
        pulse = 0.60 + 0.40 * np.sin(2.0 * np.pi * (3.2 * t) + 0.6) ** 2
        return np.minimum(1.0, t / 0.10) * np.exp(-2.2 * progress) * pulse
    if kind == "pad_swell":
        return _smoothstep(progress / 0.36) * (1.0 - _smoothstep((progress - 0.70) / 0.30))
    if kind == "string_snap":
        return np.minimum(1.0, t / 0.003) * np.exp(-12.0 * progress)
    if kind == "suspended_harmonic":
        return (0.50 + 0.50 * np.sin(np.pi * np.clip(progress, 0.0, 1.0)) ** 2) * (1.0 - _smoothstep((progress - 0.70) / 0.30))
    if kind == "descending_pizzicato":
        return np.minimum(1.0, t / 0.002) * np.exp(-8.3 * progress)
    raise BuildError(f"Unknown procedural event kind: {kind}")


def make_sfx() -> np.ndarray:
    sfx = np.zeros((TOTAL_SAMPLES, 2), dtype=np.float32)
    for spec in EVENT_SPECS:
        if spec["kind"] == "absolute_silence_marker":
            continue
        start = int(spec["frame"]) * SAMPLES_PER_FRAME
        count = min(int(spec["durationFrames"]) * SAMPLES_PER_FRAME, TOTAL_SAMPLES - start)
        if count <= 0:
            continue
        duration = count / SAMPLE_RATE
        t = np.arange(count, dtype=np.float64) / SAMPLE_RATE
        progress = np.clip(t / max(duration, 1e-9), 0.0, 1.0)
        env = _event_envelope(spec["kind"], progress, t, duration)
        mono = np.zeros(count, dtype=np.float64)
        for freq0, freq1, weight in spec["components"]:
            mono += float(weight) * _component(float(freq0), float(freq1), t, duration)
        mono *= env * float(spec["gain"])
        pan = float(spec.get("pan", 0.0))
        left = mono * (1.0 - 0.10 * pan)
        right = mono * (1.0 + 0.10 * pan)
        sfx[start : start + count, 0] += left.astype(np.float32)
        sfx[start : start + count, 1] += right.astype(np.float32)

        # The closing pluck alone receives three quiet deterministic room echoes.
        for delay_seconds, echo_gain in spec.get("echoes", []):
            delay = round(float(delay_seconds) * SAMPLE_RATE)
            echo_start = start + delay
            echo_count = min(count, TOTAL_SAMPLES - echo_start)
            if echo_count > 0:
                sfx[echo_start : echo_start + echo_count, 0] += (left[:echo_count] * float(echo_gain)).astype(np.float32)
                sfx[echo_start : echo_start + echo_count, 1] += (right[:echo_count] * float(echo_gain)).astype(np.float32)
        del t, progress, env, mono, left, right
    sfx[SILENCE_SLICE] = 0.0
    return sfx


def fit_and_place(rows: list[dict[str, Any]], reports: list[dict[str, Any]], sources: list[np.ndarray]) -> tuple[np.ndarray, list[dict[str, Any]]]:
    narration = np.zeros((TOTAL_SAMPLES, 2), dtype=np.float32)
    timing: list[dict[str, Any]] = []
    for row, report, source in zip(rows, reports, sources):
        sid = row["id"]
        start_frame = cue_start_frame(row)
        start_sample = start_frame * SAMPLES_PER_FRAME
        end_sample = start_sample + len(source)
        authored_limit = row["endFrame"] * SAMPLES_PER_FRAME
        if end_sample > authored_limit:
            duration = len(source) / SAMPLE_RATE
            required = start_frame + math.ceil(len(source) / SAMPLES_PER_FRAME)
            raise BuildError(
                f"{sid} cue duration {duration:.3f}s requires audio through frame {required}, "
                f"but its authored window ends at frame {row['endFrame']}. The source waveform "
                "was not cropped or time-compressed; root must resolve the slot."
            )
        if end_sample > TOTAL_SAMPLES:
            raise BuildError(f"{sid} cue would exceed the {TOTAL_FRAMES}-frame master.")
        values = source.astype(np.float32) / 32768.0 * VOICE_GAIN
        narration[start_sample:end_sample, 0] = values
        narration[start_sample:end_sample, 1] = values
        active_onset, active_end = report["activeOnsetSample"], report["activeEndSample"]
        active_start_frame = start_frame + active_onset // SAMPLES_PER_FRAME
        active_end_frame = start_frame + math.ceil(active_end / SAMPLES_PER_FRAME)
        actual_end_frame = start_frame + math.ceil(len(source) / SAMPLES_PER_FRAME)
        timing.append({
            "id": sid,
            "actualSamples": int(len(source)),
            "durationSeconds": round(len(source) / SAMPLE_RATE, 6),
            "startFrame": start_frame,
            "endFrame": actual_end_frame,
            "activeStartFrame": active_start_frame,
            "activeEndFrame": active_end_frame,
        })
    narration[SILENCE_SLICE] = 0.0
    return narration, timing


def wrap_caption_lines(text: str, max_chars: int = 13) -> list[str]:
    flattened = "".join(part.strip() for part in text.splitlines())
    punctuation = set("，、；：。！？…,.!?;:")
    lines: list[str] = []
    while flattened:
        if len(flattened) <= max_chars:
            lines.append(flattened)
            break
        cut = max_chars
        lower = max(1, max_chars - 5)
        for index in range(max_chars, lower - 1, -1):
            if flattened[index - 1] in punctuation:
                cut = index
                break
        lines.append(flattened[:cut])
        flattened = flattened[cut:]
    return lines


def make_captions(rows: list[dict[str, Any]], timing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    captions: list[dict[str, Any]] = []
    timing_by_id = {record["id"]: record for record in timing}
    for row in rows:
        record = timing_by_id[row["id"]]
        lines = wrap_caption_lines(row["display_subtitle"])
        blocks = [lines[index : index + 2] for index in range(0, len(lines), 2)]
        active_start = int(record["activeStartFrame"])
        active_end = int(record["activeEndFrame"])
        if active_end <= active_start:
            active_start, active_end = int(record["startFrame"]), int(record["endFrame"])
        span = active_end - active_start
        weights = [sum(len(line) for line in block) for block in blocks]
        total_weight = max(1, sum(weights))
        cursor = active_start
        used_weight = 0
        for index, (block, weight) in enumerate(zip(blocks, weights)):
            used_weight += weight
            if index == len(blocks) - 1:
                end = active_end
            else:
                end = active_start + round(span * used_weight / total_weight)
                remaining = len(blocks) - index - 1
                end = min(end, active_end - remaining)
                end = max(end, cursor + 1)
            end = min(end, active_end)
            text = "\n".join(block)
            if any(len(line) > 13 for line in block):
                raise BuildError(f"{row['id']}: generated caption line exceeded 13 characters.")
            captions.append({
                "segmentId": row["id"],
                "startFrame": cursor,
                "endFrame": max(cursor + 1, end),
                "text": text,
                "alignment": "estimated_character_weighted",
            })
            cursor = max(cursor + 1, end)
    return captions


def frame_srt_time(frame: int) -> str:
    milliseconds = round(frame * 1000.0 / FRAME_RATE)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def make_srt(captions: list[dict[str, Any]]) -> str:
    entries = []
    for index, caption in enumerate(captions, start=1):
        entries.append(
            f"{index}\n{frame_srt_time(caption['startFrame'])} --> "
            f"{frame_srt_time(caption['endFrame'])}\n{caption['text']}"
        )
    return "\n\n".join(entries) + "\n"


def encode_pcm16(samples: np.ndarray) -> bytes:
    if not np.all(np.isfinite(samples)):
        raise BuildError("Audio contains NaN or infinite sample values.")
    if samples.ndim != 2 or samples.shape != (TOTAL_SAMPLES, 2):
        raise BuildError(f"Expected stereo {TOTAL_SAMPLES}-sample arrays; got {samples.shape}.")
    if float(np.max(np.abs(samples))) > 1.0001:
        raise BuildError("Audio would clip PCM16; adjust source level or mastering before writing.")
    pcm = np.rint(np.clip(samples, -1.0, 1.0) * 32768.0).astype("<i2")
    return pcm.tobytes(order="C")


def wav_bytes(pcm_frames: bytes) -> bytes:
    import io

    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(2)
        writer.setsampwidth(2)
        writer.setframerate(SAMPLE_RATE)
        writer.writeframes(pcm_frames)
    return output.getvalue()


def run_ffmpeg_filter(pcm_input: bytes, filter_graph: str, output_format: str, input_format: str = "f32le") -> tuple[bytes, str]:
    codec = "pcm_f32le" if output_format == "f32le" else "pcm_s16le"
    command = [
        _ffmpeg_path(), "-hide_banner", "-nostats", "-v", "info", "-nostdin",
        "-f", input_format, "-ar", str(SAMPLE_RATE), "-ac", "2", "-i", "pipe:0",
        "-af", filter_graph,
    ]
    if output_format == "null":
        command.extend(["-f", "null", "-"])
    else:
        command.extend(["-ar", str(SAMPLE_RATE), "-ac", "2", "-acodec", codec, "-f", output_format, "pipe:1"])
    result = subprocess.run(command, input=pcm_input, capture_output=True, check=False, env=_ffmpeg_env())
    stderr = result.stderr.decode("utf-8", errors="replace")
    if result.returncode != 0:
        raise BuildError(f"ffmpeg audio filter failed: {stderr.strip()[-1600:]}")
    return result.stdout, stderr


def _json_stats(text: str, expected_key: str) -> dict[str, Any]:
    matches = re.findall(r"\{\s*\"input_i\".*?\}", text, flags=re.DOTALL)
    for candidate in reversed(matches):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if expected_key in parsed:
            return parsed
    raise BuildError("ffmpeg loudnorm did not return its expected JSON measurements.")


def loudness_normalize(mix: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    mix_bytes = np.asarray(mix, dtype="<f4").tobytes(order="C")
    first_pass = f"loudnorm=I={LOUDNESS_TARGET}:TP={TRUE_PEAK_TARGET}:LRA=7:print_format=json"
    _, first_log = run_ffmpeg_filter(mix_bytes, first_pass, "null")
    stats = _json_stats(first_log, "input_i")
    required = ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")
    if any(key not in stats for key in required):
        raise BuildError(f"ffmpeg loudnorm omitted required two-pass fields: {stats}")
    measured_i = str(stats["input_i"])
    measured_tp = str(stats["input_tp"])
    measured_lra = str(stats["input_lra"])
    measured_thresh = str(stats["input_thresh"])
    offset = str(stats["target_offset"])
    second_pass = (
        f"loudnorm=I={LOUDNESS_TARGET}:TP={TRUE_PEAK_TARGET}:LRA=7:"
        f"measured_I={measured_i}:measured_TP={measured_tp}:measured_LRA={measured_lra}:"
        f"measured_thresh={measured_thresh}:offset={offset}:linear=true:print_format=json,"
        "alimiter=limit=0.841395:level=false:attack=5:release=80:latency=true"
    )
    normalized, final_log = run_ffmpeg_filter(mix_bytes, second_pass, "f32le")
    if len(normalized) != TOTAL_SAMPLES * 2 * 4:
        actual = len(normalized) // 8
        raise BuildError(
            f"ffmpeg mastering emitted {actual} stereo samples per channel; exactly {TOTAL_SAMPLES} are required. "
            "No audio was cropped or time-compressed to repair the count."
        )
    output = np.frombuffer(normalized, dtype="<f4").reshape(TOTAL_SAMPLES, 2).copy()
    return output, {"firstPass": stats, "secondPassLog": final_log[-1600:]}


def measure_pcm16(pcm: bytes) -> tuple[dict[str, float], str]:
    _, log = run_ffmpeg_filter(pcm, "ebur128=peak=true", "null", input_format="s16le")
    integrated_matches = re.findall(r"\bI:\s*(-?(?:inf|nan|\d+(?:\.\d+)?))\s*LUFS", log, flags=re.IGNORECASE)
    lra_matches = re.findall(r"\bLRA:\s*(-?(?:inf|nan|\d+(?:\.\d+)?))\s*LU", log, flags=re.IGNORECASE)
    true_peak_section = log.rsplit("True peak:", 1)[-1]
    peak_matches = re.findall(r"\bPeak:\s*(-?(?:inf|nan|\d+(?:\.\d+)?))\s*dBFS", true_peak_section, flags=re.IGNORECASE)
    if not integrated_matches or not peak_matches:
        raise BuildError(f"ffmpeg ebur128=peak=true did not report integrated loudness and true peak: {log[-1800:]}")
    integrated = float(integrated_matches[-1])
    peak = float(peak_matches[-1])
    lra = float(lra_matches[-1]) if lra_matches else None
    if not math.isfinite(integrated) or not math.isfinite(peak):
        raise BuildError(f"ffmpeg returned unusable loudness measurements: I={integrated}, true peak={peak}.")
    return {"integratedLufs": integrated, "loudnessRangeLu": lra, "truePeakDbtp": peak}, log[-2200:]


def finalize_master(master_float: np.ndarray) -> tuple[bytes, dict[str, Any]]:
    master_float[SILENCE_SLICE] = 0.0
    raw_pcm = encode_pcm16(master_float)
    measurements, report = measure_pcm16(raw_pcm)
    if abs(measurements["integratedLufs"] - LOUDNESS_TARGET) > 0.2 or measurements["truePeakDbtp"] > -1.0:
        requested_gain = LOUDNESS_TARGET - measurements["integratedLufs"]
        peak_headroom_gain = TRUE_PEAK_SAFETY - measurements["truePeakDbtp"]
        correction = min(requested_gain, peak_headroom_gain)
        corrected = np.frombuffer(raw_pcm, dtype="<i2").astype(np.float32).reshape(TOTAL_SAMPLES, 2) / 32768.0
        corrected *= np.float32(10.0 ** (correction / 20.0))
        corrected[SILENCE_SLICE] = 0.0
        raw_pcm = encode_pcm16(corrected)
        del corrected
        measurements, report = measure_pcm16(raw_pcm)
    if abs(measurements["integratedLufs"] - LOUDNESS_TARGET) > 0.2:
        raise BuildError(
            f"Final integrated loudness is {measurements['integratedLufs']:.2f} LUFS after linear calibration; "
            f"target is {LOUDNESS_TARGET:.1f} ±0.2 LUFS. Root must resolve the mix/peak tradeoff."
        )
    if measurements["truePeakDbtp"] > -1.0:
        raise BuildError(
            f"Final true peak is {measurements['truePeakDbtp']:.2f} dBTP; it must be at or below -1.0 dBTP."
        )
    pcm_array = np.frombuffer(raw_pcm, dtype="<i2").reshape(TOTAL_SAMPLES, 2)
    if np.any(pcm_array[SILENCE_SLICE] != 0):
        raise BuildError("Master silence interval was not exact digital zero after loudness processing.")
    return raw_pcm, {"measurements": measurements, "ebur128Report": report}


def sfx_json() -> dict[str, Any]:
    events = []
    for spec in EVENT_SPECS:
        start_sample = int(spec["frame"]) * SAMPLES_PER_FRAME
        event = dict(spec)
        event["startSample"] = start_sample
        event["endSampleExclusive"] = start_sample + int(spec["durationFrames"]) * SAMPLES_PER_FRAME
        events.append(event)
    return {
        "sampleRate": SAMPLE_RATE,
        "frameRate": FRAME_RATE,
        "samplesPerFrame": SAMPLES_PER_FRAME,
        "events": events,
        "absoluteSilence": {
            "startFrame": SILENCE_START_FRAME,
            "endFrameExclusive": SILENCE_END_FRAME,
            "startSample": SILENCE_START_SAMPLE,
            "endSampleExclusive": SILENCE_END_SAMPLE,
            "allStemSamplesExactZero": True,
        },
    }


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def write_json(path: Path, data: dict[str, Any]) -> None:
    atomic_write(path, (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8"))


def mix() -> None:
    rows = load_segments()
    reports, sources = inspect_cues(rows)
    audio_dir = PROJECT / "public" / "audio"
    master_path = audio_dir / "master.wav"
    if master_path.exists():
        raise BuildError(f"Refusing to overwrite completed master: {master_path}")

    narration, timing = fit_and_place(rows, reports, sources)
    score = make_score(narration)
    sfx = make_sfx()
    for name, stem in (("narration", narration), ("score", score), ("sfx", sfx)):
        if stem.shape != (TOTAL_SAMPLES, 2):
            raise BuildError(f"{name} stem does not contain exactly {TOTAL_SAMPLES} stereo samples.")
        if np.any(stem[SILENCE_SLICE] != 0.0):
            raise BuildError(f"{name} stem is not exact zero over frames {SILENCE_START_FRAME}..{SILENCE_END_FRAME}.")
    mix_buffer = narration + score + sfx
    normalized, mastering = loudness_normalize(mix_buffer)
    master_pcm, final_audio_qa = finalize_master(normalized)

    stem_payloads: dict[str, bytes] = {}
    for name, stem in (("narration", narration), ("score", score), ("sfx", sfx)):
        pcm = encode_pcm16(stem)
        if len(pcm) != TOTAL_SAMPLES * 2 * 2:
            raise BuildError(f"{name} PCM stem has an invalid interleaved byte count.")
        stem_payloads[name] = wav_bytes(pcm)
    master_wav = wav_bytes(master_pcm)
    captions = make_captions(rows, timing)
    timing_json = {
        "status": "MIXED",
        "sampleRate": SAMPLE_RATE,
        "channels": 2,
        "frameRate": FRAME_RATE,
        "samplesPerFrame": SAMPLES_PER_FRAME,
        "masterSamplesPerChannel": TOTAL_SAMPLES,
        "durationSeconds": TOTAL_FRAMES / FRAME_RATE,
        "segments": timing,
        "captions": captions,
    }
    qa_json = {
        "status": "AUTOMATED_AUDIO_QA_ONLY",
        "humanReviewStatus": "NOT_REVIEWED",
        "humanListeningRequired": True,
        "master": {
            "path": "public/audio/master.wav",
            "sampleRate": SAMPLE_RATE,
            "channels": 2,
            "samplesPerChannel": TOTAL_SAMPLES,
            "durationSeconds": TOTAL_SAMPLES / SAMPLE_RATE,
            "sha256": hashlib.sha256(master_wav).hexdigest(),
        },
        "stems": {
            name: {
                "path": f"public/audio/{name}.wav",
                "sampleRate": SAMPLE_RATE,
                "channels": 2,
                "samplesPerChannel": TOTAL_SAMPLES,
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
            for name, payload in stem_payloads.items()
        },
        "measurements": final_audio_qa["measurements"],
        "normalization": {
            "targetIntegratedLufs": LOUDNESS_TARGET,
            "targetTruePeakDbtp": TRUE_PEAK_TARGET,
            "linearCalibrationAppliedIfNeeded": True,
            "twoPassLoudnorm": mastering["firstPass"],
        },
        "exactSilence": {
            "startFrame": SILENCE_START_FRAME,
            "endFrameExclusive": SILENCE_END_FRAME,
            "startSample": SILENCE_START_SAMPLE,
            "endSampleExclusive": SILENCE_END_SAMPLE,
            "allStemsAndMasterAreExactZero": True,
        },
        "ebur128Report": final_audio_qa["ebur128Report"],
    }

    # Write the master last so its presence means every preceding check passed.
    for name, payload in stem_payloads.items():
        atomic_write(audio_dir / f"{name}.wav", payload)
    atomic_write(PROJECT / "audio-timing.json", (json.dumps(timing_json, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    write_json(PROJECT / "sfx_events.json", sfx_json())
    atomic_write(WORK / "小红书" / "captions.srt", make_srt(captions).encode("utf-8"))
    write_json(WORK / "review" / "audio-qa.json", qa_json)
    atomic_write(master_path, master_wav)
    print(json.dumps({"status": "MIXED", "master": str(master_path), "measurements": final_audio_qa["measurements"]}, ensure_ascii=False, indent=2))


def audit_cues() -> None:
    rows = load_segments()
    reports, _ = inspect_cues(rows)
    print(json.dumps({"sampleRate": SAMPLE_RATE, "samplesPerFrame": SAMPLES_PER_FRAME, "cues": reports}, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or audit the EP19 deterministic audio package.")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--audit-cues", action="store_true", help="Decode and report cue timing only; writes no files.")
    modes.add_argument("--mix", action="store_true", help="Build exact-duration stems, master, timing, captions, and QA files.")
    args = parser.parse_args()
    try:
        if args.audit_cues:
            audit_cues()
        else:
            mix()
    except BuildError as exc:
        print(f"audio build error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
