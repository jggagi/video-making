#!/usr/bin/env python3
"""Compose the deterministic procedural music and sound-design stems."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import wave
from pathlib import Path
from typing import Any

import numpy as np


SAMPLE_RATE = 48_000
DURATION_SECONDS = 180
FRAME_COUNT = SAMPLE_RATE * DURATION_SECONDS
CHANNELS = 2
SAMPLE_WIDTH = 2
CHUNK_FRAMES = SAMPLE_RATE * 4
SEED = 421_980_160
TAU = 2.0 * math.pi
PEAK_CEILING = 10.0 ** (-6.0 / 20.0)
PROJECT_ROOT = Path(__file__).resolve().parents[1]

CHORDS_MIDI = np.array(
    [
        [38, 50, 57, 62, 65, 69],  # D minor add9
        [34, 46, 53, 58, 62, 65],  # B-flat major
        [41, 53, 57, 60, 64, 67],  # F major add9
        [36, 48, 55, 60, 64, 67],  # C major add9
    ],
    dtype=np.float64,
)
CHORDS_HZ = 440.0 * np.power(2.0, (CHORDS_MIDI - 69.0) / 12.0)
ARP_HZ = 440.0 * np.power(2.0, (np.array([62, 69, 65, 72, 74, 69, 76, 72]) - 69.0) / 12.0)
ARP_STEP_SECONDS = 0.42
PAD_VOICE_AMPLITUDE = 0.043


def _smoothstep(value: np.ndarray) -> np.ndarray:
    clipped = np.clip(value, 0.0, 1.0)
    return clipped * clipped * (3.0 - 2.0 * clipped)


def _seed_unit(index: int) -> float:
    value = math.sin((index + 1) * 127.1 + SEED * 0.001) * 43_758.5453123
    return value - math.floor(value)


def _stereo_pan(pan: float) -> tuple[float, float]:
    normalized = min(1.0, max(-1.0, pan))
    return math.sqrt((1.0 - normalized) * 0.5), math.sqrt((1.0 + normalized) * 0.5)


def _pad_voice(t: np.ndarray, frequency: np.ndarray, phase_offset: float, brightness: np.ndarray) -> np.ndarray:
    phase = TAU * frequency * t + 0.025 * np.sin(TAU * 0.09 * t + phase_offset) + phase_offset
    wave = np.sin(phase)
    wave += (0.12 + brightness * 0.28) * np.sin(2.0 * phase + 0.13)
    wave += (0.035 + brightness * 0.13) * np.sin(3.0 * phase + 0.37)
    wave += 0.008 * np.sin(4.0 * phase + 0.61)
    return wave


def _render_pad(t: np.ndarray) -> np.ndarray:
    count = t.size
    output = np.zeros((count, CHANNELS), dtype=np.float64)
    slots = np.floor(t / 7.5).astype(np.int32)
    local = t - slots * 7.5
    transition = _smoothstep((local - 6.1) / 1.4)
    chord_index = slots % len(CHORDS_HZ)
    next_index = (chord_index + 1) % len(CHORDS_HZ)
    brightness = np.interp(
        t,
        [0.0, 30.0, 75.0, 114.0, 119.0, 120.0, 155.0, 160.0, 162.0, 180.0],
        [0.012, 0.022, 0.070, 0.082, 0.040, 0.026, 0.020, 0.010, 0.024, 0.010],
    )
    pad_level = np.interp(
        t,
        [0.0, 2.0, 28.0, 33.0, 70.0, 78.0, 112.0, 117.0, 120.0, 155.0, 160.0, 162.0, 175.0, 179.8, 180.0],
        [0.0, 0.82, 0.82, 0.86, 0.86, 0.98, 0.98, 0.78, 0.55, 0.55, 0.015, 0.70, 0.70, 0.0, 0.0],
    )
    breathe = 0.93 + 0.07 * np.sin(TAU * 0.035 * t + 0.4)
    amplitude = PAD_VOICE_AMPLITUDE * pad_level * breathe

    for voice in range(CHORDS_HZ.shape[1]):
        phase = TAU * _seed_unit(voice + 11)
        pan = 0.54 * math.sin((voice + 1) * 1.91 + SEED * 0.00001)
        left_gain, right_gain = _stereo_pan(pan)
        current_frequency = CHORDS_HZ[chord_index, voice]
        next_frequency = CHORDS_HZ[next_index, voice]
        current = _pad_voice(t, current_frequency, phase, brightness)
        following = _pad_voice(t, next_frequency, phase, brightness)
        voice_wave = current * (1.0 - transition) + following * transition
        output[:, 0] += voice_wave * amplitude * left_gain
        output[:, 1] += voice_wave * amplitude * right_gain

    resolved = t >= 160.0
    output[resolved] = _render_resolved_pad(t[resolved])
    return output


def _render_resolved_pad(t: np.ndarray) -> np.ndarray:
    count = t.size
    output = np.zeros((count, CHANNELS), dtype=np.float64)
    brightness = np.interp(t, [160.0, 162.0, 175.0, 180.0], [0.012, 0.024, 0.018, 0.010])
    pad_level = np.interp(t, [160.0, 162.0, 175.0, 179.8, 180.0], [0.015, 0.70, 0.70, 0.0, 0.0])
    breathe = 0.93 + 0.07 * np.sin(TAU * 0.035 * t + 0.4)
    amplitude = PAD_VOICE_AMPLITUDE * pad_level * breathe
    for voice, frequency in enumerate(CHORDS_HZ[0]):
        phase = TAU * _seed_unit(voice + 11)
        pan = 0.54 * math.sin((voice + 1) * 1.91 + SEED * 0.00001)
        left_gain, right_gain = _stereo_pan(pan)
        voice_wave = _pad_voice(t, np.full_like(t, frequency), phase, brightness)
        output[:, 0] += voice_wave * amplitude * left_gain
        output[:, 1] += voice_wave * amplitude * right_gain
    return output


def _render_arpeggio(t: np.ndarray) -> np.ndarray:
    count = t.size
    output = np.zeros((count, CHANNELS), dtype=np.float64)
    level = np.interp(
        t,
        [0.0, 29.0, 32.0, 72.0, 78.0, 114.0, 118.5, 120.0, 121.0, 153.5, 155.0, 180.0],
        [0.0, 0.0, 0.0065, 0.0065, 0.0120, 0.0120, 0.0, 0.0, 0.0080, 0.0080, 0.0, 0.0],
    )
    step_index = np.floor(t / ARP_STEP_SECONDS).astype(np.int32)
    phase = (t - step_index * ARP_STEP_SECONDS) / ARP_STEP_SECONDS
    frequency = ARP_HZ[step_index % len(ARP_HZ)]
    envelope = _smoothstep(phase / 0.12) * _smoothstep((1.0 - phase) / 0.22)
    oscillator_phase = TAU * frequency * t + (step_index % 8) * 0.17
    note = np.sin(oscillator_phase) + 0.095 * np.sin(2.0 * oscillator_phase + 0.2)
    note *= level * envelope
    pan = 0.45 * np.sin((step_index % 8) * 0.81 + 0.3)
    output[:, 0] = note * np.sqrt((1.0 - pan) * 0.5)
    output[:, 1] = note * np.sqrt((1.0 + pan) * 0.5)
    return output


def _render_subheartbeat(t: np.ndarray) -> np.ndarray:
    output = np.zeros((t.size, CHANNELS), dtype=np.float64)
    active = (t >= 120.0) & (t < 155.0)
    if not np.any(active):
        return output
    local = t[active] - 120.0
    beat_phase = np.mod(local, 1.5)
    level = 0.011 * np.interp(t[active], [120.0, 122.0, 153.0, 155.0], [0.0, 1.0, 1.0, 0.0])
    envelope = np.exp(-beat_phase / 0.46) * _smoothstep(beat_phase / 0.025)
    pulse = np.sin(TAU * 48.0 * t[active] + 0.2) * envelope * level
    pulse += 0.18 * np.sin(TAU * 72.0 * t[active] + 0.1) * envelope * level
    output[active, 0] = pulse * 0.71
    output[active, 1] = pulse * 0.71
    return output


def _render_bell(
    t: np.ndarray,
    onset: float,
    frequencies: tuple[float, ...],
    amplitudes: tuple[float, ...],
    decay_seconds: tuple[float, ...],
    phase_seed: int,
) -> np.ndarray:
    output = np.zeros((t.size, CHANNELS), dtype=np.float64)
    delta = t - onset
    active = delta >= 0.0
    safe_delta = np.maximum(delta, 0.0)
    attack = 1.0 - np.exp(-safe_delta / 0.006)
    for index, (frequency, amplitude, decay) in enumerate(zip(frequencies, amplitudes, decay_seconds)):
        phase = TAU * _seed_unit(phase_seed + index) * 0.07
        tone = np.sin(TAU * frequency * safe_delta + phase)
        tone += 0.12 * np.sin(TAU * (frequency * 2.756) * safe_delta + phase * 1.7)
        signal = tone * amplitude * attack * np.exp(-safe_delta / decay) * active
        pan = 0.48 * math.sin((index + phase_seed) * 1.13)
        left_gain, right_gain = _stereo_pan(pan)
        output[:, 0] += signal * left_gain
        output[:, 1] += signal * right_gain
    return output


def _render_sweep(t: np.ndarray, onset: float, duration: float, start_hz: float, end_hz: float, amplitude: float, pan: float) -> np.ndarray:
    output = np.zeros((t.size, CHANNELS), dtype=np.float64)
    delta = t - onset
    active = (delta >= 0.0) & (delta <= duration)
    safe_delta = np.clip(delta, 0.0, duration)
    rate = (end_hz - start_hz) / duration
    phase = TAU * (start_hz * safe_delta + 0.5 * rate * safe_delta * safe_delta)
    envelope = np.sin(math.pi * safe_delta / duration) ** 2
    envelope *= np.exp(-safe_delta / (duration * 1.8)) * active
    signal = amplitude * envelope * np.sin(phase)
    left_gain, right_gain = _stereo_pan(pan)
    output[:, 0] = signal * left_gain
    output[:, 1] = signal * right_gain
    return output


def _render_resonance(t: np.ndarray, onset: float, frequency: float, amplitude: float, decay: float, pan: float) -> np.ndarray:
    output = np.zeros((t.size, CHANNELS), dtype=np.float64)
    delta = t - onset
    active = delta >= 0.0
    safe_delta = np.maximum(delta, 0.0)
    envelope = (1.0 - np.exp(-safe_delta / 0.009)) * np.exp(-safe_delta / decay) * active
    tone = np.sin(TAU * frequency * safe_delta + 0.08)
    tone += 0.14 * np.sin(TAU * frequency * 2.03 * safe_delta + 0.31)
    signal = amplitude * envelope * tone
    left_gain, right_gain = _stereo_pan(pan)
    output[:, 0] = signal * left_gain
    output[:, 1] = signal * right_gain
    return output


def _render_gear_ticks(t: np.ndarray) -> np.ndarray:
    output = np.zeros((t.size, CHANNELS), dtype=np.float64)
    active_span = (t >= 120.0) & (t < 155.0)
    if not np.any(active_span):
        return output
    relative = t[active_span] - 120.0
    tick_number = np.floor(relative / 0.82).astype(np.int32)
    tick_time = relative - tick_number * 0.82
    active_tick = tick_time < 0.065
    envelope = np.exp(-tick_time / 0.014) * _smoothstep(tick_time / 0.004) * active_tick
    frequency = 790.0 + 46.0 * (tick_number % 5)
    phase = TAU * frequency * tick_time
    tick = 0.014 * envelope * (np.sin(phase) + 0.19 * np.sin(1.71 * phase + 0.23))
    pan = 0.28 * np.sin(tick_number * 1.37)
    output[active_span, 0] = tick * np.sqrt((1.0 - pan) * 0.5)
    output[active_span, 1] = tick * np.sqrt((1.0 + pan) * 0.5)
    return output


def _render_music_chunk(t: np.ndarray) -> np.ndarray:
    output = _render_pad(t)
    output += _render_arpeggio(t)
    output += _render_subheartbeat(t)
    output += _render_bell(
        t,
        160.0,
        (587.33, 880.00, 1174.66, 1396.91, 1760.00),
        (0.025, 0.020, 0.017, 0.012, 0.008),
        (4.8, 4.0, 5.4, 3.2, 2.5),
        160,
    )
    return output.astype(np.float32)


def _render_sound_design_chunk(t: np.ndarray) -> np.ndarray:
    output = np.zeros((t.size, CHANNELS), dtype=np.float64)
    output += _render_bell(t, 0.72, (1760.0, 2349.32, 3135.96), (0.050, 0.030, 0.016), (0.30, 0.48, 0.78), 8)
    output += _render_sweep(t, 30.0, 1.55, 470.0, 1180.0, 0.052, -0.22)
    output += _render_sweep(t, 75.0, 1.85, 380.0, 1490.0, 0.050, 0.18)
    output += _render_gear_ticks(t)
    output += _render_resonance(t, 160.0, 52.0, 0.058, 0.52, -0.05)
    output += _render_resonance(t, 160.0, 83.0, 0.027, 0.82, 0.12)
    output += _render_sweep(t, 160.0, 2.6, 104.0, 410.0, 0.031, 0.04)
    output += _render_bell(
        t,
        160.0,
        (659.25, 880.00, 1174.66, 1567.98, 2093.00),
        (0.043, 0.037, 0.026, 0.017, 0.010),
        (1.4, 2.0, 2.8, 2.2, 1.7),
        320,
    )
    return output.astype(np.float32)


class StereoMultitap:
    """Small deterministic stereo room echo with chunk-persistent dry history."""

    def __init__(self, taps: tuple[tuple[float, float, bool], ...]) -> None:
        self.taps = tuple((round(delay * SAMPLE_RATE), gain, cross) for delay, gain, cross in taps)
        self.history_frames = max(delay for delay, _, _ in self.taps) + 1
        self.history = np.zeros((self.history_frames, CHANNELS), dtype=np.float32)

    def process(self, dry: np.ndarray) -> np.ndarray:
        source = np.asarray(dry, dtype=np.float32)
        extended = np.concatenate((self.history, source), axis=0)
        start = self.history_frames
        positions = np.arange(source.shape[0], dtype=np.int64) + start
        wet = source.copy()
        for delay, gain, cross in self.taps:
            delayed = extended[positions - delay]
            if cross:
                wet[:, 0] += gain * delayed[:, 1]
                wet[:, 1] += gain * delayed[:, 0]
            else:
                wet += gain * delayed
        self.history = extended[-self.history_frames :].copy()
        return wet


def _end_fade(t: np.ndarray) -> np.ndarray:
    return 1.0 - _smoothstep((t - 175.0) / (179.8 - 175.0))


def _pcm16(stereo: np.ndarray) -> tuple[np.ndarray, float, int]:
    if not np.isfinite(stereo).all():
        raise ValueError("synthesis produced a non-finite sample")
    peak = float(np.max(np.abs(stereo))) if stereo.size else 0.0
    guard_gain = min(1.0, PEAK_CEILING / peak) if peak > 0.0 else 1.0
    guarded = stereo * guard_gain
    pcm = np.rint(np.clip(guarded, -PEAK_CEILING, PEAK_CEILING) * 32767.0).astype("<i2")
    pcm_peak = int(np.max(np.abs(pcm.astype(np.int32)))) if pcm.size else 0
    return pcm, guard_gain, pcm_peak


def _dbfs(value: float) -> float:
    if value <= 0.0:
        return -120.0
    return 20.0 * math.log10(value)


def _write_stems(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    music_path = output_dir / "ambient-score.wav"
    design_path = output_dir / "sound-design.wav"
    music_tmp = output_dir / ".ambient-score.wav.partial"
    design_tmp = output_dir / ".sound-design.wav.partial"
    music_echo = StereoMultitap(((0.31, 0.12, False), (0.57, 0.065, True), (0.83, 0.032, False)))
    design_echo = StereoMultitap(((0.24, 0.075, False), (0.49, 0.045, True), (0.76, 0.022, False)))
    meters = {
        "music": {"peak": 0, "sum_squares": 0.0, "samples": 0, "guarded_chunks": 0, "sha256": hashlib.sha256()},
        "sound_design": {"peak": 0, "sum_squares": 0.0, "samples": 0, "guarded_chunks": 0, "sha256": hashlib.sha256()},
    }

    try:
        with wave.open(str(music_tmp), "wb") as music_writer, wave.open(str(design_tmp), "wb") as design_writer:
            for writer in (music_writer, design_writer):
                writer.setnchannels(CHANNELS)
                writer.setsampwidth(SAMPLE_WIDTH)
                writer.setframerate(SAMPLE_RATE)

            for start in range(0, FRAME_COUNT, CHUNK_FRAMES):
                stop = min(FRAME_COUNT, start + CHUNK_FRAMES)
                t = np.arange(start, stop, dtype=np.float64) / SAMPLE_RATE
                music_dry = _render_music_chunk(t)
                design_dry = _render_sound_design_chunk(t)
                music = music_echo.process(music_dry)
                music *= _end_fade(t).astype(np.float32)[:, None]
                design = design_echo.process(design_dry)
                design *= _end_fade(t).astype(np.float32)[:, None]
                chunks = ((music_writer, music, meters["music"]), (design_writer, design, meters["sound_design"]))

                for writer, audio, meter in chunks:
                    pcm, guard_gain, peak = _pcm16(audio)
                    if guard_gain < 1.0:
                        meter["guarded_chunks"] += 1
                    writer.writeframesraw(pcm.tobytes(order="C"))
                    meter["sha256"].update(pcm.tobytes(order="C"))
                    meter["peak"] = max(meter["peak"], peak)
                    as_float = pcm.astype(np.float64) / 32768.0
                    meter["sum_squares"] += float(np.sum(as_float * as_float))
                    meter["samples"] += int(pcm.size)

                if stop == FRAME_COUNT or stop % (SAMPLE_RATE * 20) == 0:
                    print(f"Composed {stop / SAMPLE_RATE:6.1f} / {DURATION_SECONDS} seconds", flush=True)

        music_tmp.replace(music_path)
        design_tmp.replace(design_path)
    except Exception:
        music_tmp.unlink(missing_ok=True)
        design_tmp.unlink(missing_ok=True)
        raise

    result: dict[str, Any] = {}
    for name, meter in meters.items():
        rms = math.sqrt(meter["sum_squares"] / meter["samples"])
        relative_path = f"public/audio-v2/{'ambient-score.wav' if name == 'music' else 'sound-design.wav'}"
        file_hash = hashlib.sha256()
        filename = music_path if name == "music" else design_path
        with filename.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                file_hash.update(block)
        result[name] = {
            "path": relative_path,
            "duration_seconds": DURATION_SECONDS,
            "sample_frames": FRAME_COUNT,
            "channels": CHANNELS,
            "sample_rate_hz": SAMPLE_RATE,
            "encoding": "PCM signed 16-bit little-endian",
            "sample_peak_dbfs": round(_dbfs(meter["peak"] / 32768.0), 3),
            "integrated_rms_dbfs_not_lufs": round(_dbfs(rms), 3),
            "sha256": file_hash.hexdigest(),
            "pcm_sha256": meter["sha256"].hexdigest(),
            "peak_guard_chunks": meter["guarded_chunks"],
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "public" / "audio-v2",
        help="output directory (default: si-eternity/public/audio-v2)",
    )
    args = parser.parse_args()
    stems = _write_stems(args.output_dir)
    manifest = {
        "title": "The Half-Second Eternity — procedural score v1",
        "seed": SEED,
        "architecture": "Original D-minor/B-flat/F/C layered sine-and-partial synth pads, gentle arpeggios, a low sub-heartbeat, deterministic stereo multitap, and independent synthesized glass/transition/gear/impact design.",
        "arrangement": [
            {"from_seconds": 0, "to_seconds": 30, "description": "Slow spacious laboratory suspense; warm low pads and a delicate opening glass ping."},
            {"from_seconds": 30, "to_seconds": 75, "description": "Search pulse and restrained arpeggiated complexity; transition cues at 30 and 75 seconds."},
            {"from_seconds": 75, "to_seconds": 120, "description": "Rising harmonic brightness and arpeggios, then a soft harmonic resolution from 117 to 120 seconds."},
            {"from_seconds": 120, "to_seconds": 155, "description": "Contrasting digital pulse with a slow quiet sub-heartbeat and soft mechanical gear ticks."},
            {"from_seconds": 155, "to_seconds": 160, "description": "Pullback to near silence before the exact 160-second event."},
            {"from_seconds": 160, "to_seconds": 175, "description": "Restrained glass-crystal strike and magnetic bloom at exactly 160 seconds, followed by a warm D-minor hover."},
            {"from_seconds": 175, "to_seconds": 180, "description": "Gentle fade reaches digital silence by 179.8 seconds."},
        ],
        "events": [
            {"time_seconds": 0.72, "stem": "sound_design", "event": "delicate glass droplet ping"},
            {"time_seconds": 30.0, "stem": "sound_design", "event": "brief digital transition"},
            {"time_seconds": 75.0, "stem": "sound_design", "event": "rising projection transition"},
            {"time_seconds": 120.0, "stem": "sound_design", "event": "soft gear ticks begin"},
            {"time_seconds": 160.0, "stem": "both", "event": "restrained crystal impact and magnetic bloom"},
            {"time_seconds": 179.8, "stem": "both", "event": "fade reaches zero"},
        ],
        "format": {
            "sample_rate_hz": SAMPLE_RATE,
            "channels": CHANNELS,
            "duration_seconds": DURATION_SECONDS,
            "stereo_sample_frames": FRAME_COUNT,
            "sample_encoding": "PCM signed 16-bit little-endian",
            "peak_ceiling_dbfs": -6.0,
            "music_loudness_hint": "approximately -27 LUFS before the final mix; RMS is reported separately and is not LUFS",
        },
        "stems": stems,
    }
    manifest_path = args.output_dir / "manifest.json"
    temporary_manifest = args.output_dir / ".manifest.json.partial"
    temporary_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary_manifest.replace(manifest_path)
    print(f"Wrote {args.output_dir / 'ambient-score.wav'}")
    print(f"Wrote {args.output_dir / 'sound-design.wav'}")
    print(f"Wrote {manifest_path}")
    for name, stem in stems.items():
        print(
            f"{name}: peak {stem['sample_peak_dbfs']:.3f} dBFS, "
            f"integrated RMS {stem['integrated_rms_dbfs_not_lufs']:.3f} dBFS, "
            f"sha256 {stem['sha256']}"
        )


if __name__ == "__main__":
    main()
