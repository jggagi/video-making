#!/usr/bin/env python3
"""Build QStory EP03 local narration, original ambience, effects, and QA metadata."""

from __future__ import annotations

import argparse
import array
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TIMELINE = ROOT / "source" / "EP03_timeline.json"
AUDIO = ROOT / "public" / "audio"
REVIEW = ROOT / "review"
TIMING = ROOT / "src" / "audio-timing.json"
QA = REVIEW / "audio-qa.json"
VOICE = "Tingting"
VOICE_LABEL = "Tingting (Chinese (China mainland))"
BASE_RATE = 180
FAST_RATE = 185
SAMPLE_RATE = 48_000
FPS = 30
TOTAL_SECONDS = 180
TOTAL_SAMPLES = SAMPLE_RATE * TOTAL_SECONDS


def run(args: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_data() -> dict:
    data = json.loads(TIMELINE.read_text(encoding="utf-8"))
    if data.get("durationSec") != TOTAL_SECONDS or data.get("fps") != FPS:
        raise ValueError("timeline must remain 180 seconds at 30 fps")
    captions = data.get("captions", [])
    if len(captions) != 25:
        raise ValueError(f"expected the 25 source captions, found {len(captions)}")
    if [item["id"] for item in captions] != [f"caption-{i:03d}" for i in range(1, 26)]:
        raise ValueError("source caption IDs/order changed")
    return data


def shot_by_id(data: dict) -> dict[str, dict]:
    return {shot["id"]: shot for shot in data["shots"]}


def cache_key(text: str, rate: int) -> str:
    material = json.dumps(
        {"text": text, "voice": VOICE_LABEL, "rate": rate, "sampleRate": SAMPLE_RATE},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def probe_audio(path: Path) -> dict:
    result = run(
        [
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=sample_rate,channels,sample_fmt,duration,duration_ts,time_base",
            "-of", "json", str(path),
        ],
        capture=True,
    )
    streams = json.loads(result.stdout).get("streams", [])
    if len(streams) != 1:
        raise ValueError(f"expected one audio stream in {path}")
    return streams[0]


def synthesize(text: str, rate: int) -> Path:
    key = cache_key(text, rate)
    cache_dir = AUDIO / "voice-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    output = cache_dir / f"{key}.wav"
    if output.exists():
        info = probe_audio(output)
        if int(info.get("sample_rate", 0)) == SAMPLE_RATE and int(info.get("channels", 0)) == 1:
            return output
        output.unlink()

    with tempfile.TemporaryDirectory(prefix="qstory-say-") as temp_dir:
        raw = Path(temp_dir) / "say.wav"
        run([
            "say", "-v", VOICE, "-r", str(rate), "--file-format=WAVE",
            f"--data-format=LEI16@{SAMPLE_RATE}", "--channels=1", "-o", str(raw), text,
        ])
        if not raw.exists() or raw.stat().st_size <= 44:
            raise RuntimeError(f"say produced no audio for {text!r}")
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw),
             "-ar", str(SAMPLE_RATE), "-ac", "1", "-c:a", "pcm_s16le", str(output)])
    return output


def read_mono_wav(path: Path) -> tuple[bytes, int]:
    with wave.open(str(path), "rb") as wav:
        if wav.getframerate() != SAMPLE_RATE or wav.getnchannels() != 1 or wav.getsampwidth() != 2:
            raise ValueError(f"expected mono 48kHz PCM16 cue, got {path}: {wav.getparams()}")
        return wav.readframes(wav.getnframes()), wav.getnframes()


def make_sample(data: dict) -> dict:
    caption = data["captions"][0]
    rate = BASE_RATE
    cached = synthesize(caption["text"], rate)
    sample_path = AUDIO / "sample_voice.wav"
    shutil.copyfile(cached, sample_path)
    info = probe_audio(sample_path)
    pcm, samples = read_mono_wav(sample_path)
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(sample_path), "-f", "null", "-"])
    result = {
        "captionId": caption["id"],
        "text": caption["text"],
        "speaker": caption["speaker"],
        "voice": VOICE_LABEL,
        "rate": rate,
        "sampleRate": SAMPLE_RATE,
        "channels": 1,
        "decodedSamples": samples,
        "audioSeconds": round(samples / SAMPLE_RATE, 6),
        "sha256": sha256(sample_path),
        "ffprobe": info,
        "ffmpegDecode": "passed",
        "nonzeroPcmBytes": sum(1 for value in pcm if value),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def cue_records(data: dict) -> list[dict]:
    shots = shot_by_id(data)
    records = []
    previous_end = 0
    for caption in data["captions"]:
        rate = BASE_RATE
        wav_path = synthesize(caption["text"], rate)
        pcm, sample_count = read_mono_wav(wav_path)
        seconds = sample_count / SAMPLE_RATE
        wanted_frames = math.ceil((seconds + 0.15) * FPS)
        planned_start = int(caption["fromFrame"])
        planned_end = int(caption["toFrameExclusive"])
        shot = shots[caption["shotId"]]
        shot_start = int(shot["fromFrame"])
        shot_end = int(shot["fromFrame"] + shot["durationInFrames"])
        # Preserve planned entrances; if natural speech runs long, use unused shot room.
        # Later cues move forward after the prior cue rather than moving speech into the
        # 129-130 second silent interval or cutting spoken PCM at a planned caption end.
        start = max(planned_start, previous_end)
        end = start + wanted_frames
        if end > shot_end:
            if rate != FAST_RATE:
                rate = FAST_RATE
                wav_path = synthesize(caption["text"], rate)
                pcm, sample_count = read_mono_wav(wav_path)
                seconds = sample_count / SAMPLE_RATE
                wanted_frames = math.ceil((seconds + 0.15) * FPS)
                start = max(planned_start, previous_end)
                end = start + wanted_frames
        mute_start = 129 * FPS
        mute_end = 130 * FPS
        overlaps_mute = start < mute_end and end > mute_start
        if start < shot_start or end > shot_end or start < previous_end or overlaps_mute:
            raise RuntimeError(
                f"{caption['id']} cannot fit shot/caption without overlap at {rate} wpm: "
                f"start={start}, end={end}, shot=[{shot_start},{shot_end}), "
                f"caption=[{planned_start},{planned_end}), previousEnd={previous_end}, "
                f"mute=[{mute_start},{mute_end})"
            )
        records.append({
            "id": caption["id"],
            "shotId": caption["shotId"],
            "text": caption["text"],
            "speaker": caption["speaker"],
            "fromFrame": start,
            "toFrameExclusive": end,
            "audioSeconds": round(seconds, 6),
            "voice": VOICE_LABEL,
            "rate": rate,
            "wavPath": wav_path,
            "pcm": pcm,
            "sampleCount": sample_count,
            "plannedFromFrame": planned_start,
            "plannedToFrameExclusive": planned_end,
        })
        previous_end = end
    return records


def write_mono_stem(records: list[dict], path: Path) -> None:
    pcm = bytearray(TOTAL_SAMPLES * 2)
    occupied: list[tuple[int, int]] = []
    for record in records:
        start = record["fromFrame"] * (SAMPLE_RATE // FPS)
        end = start + record["sampleCount"]
        if end > TOTAL_SAMPLES:
            raise RuntimeError(f"voice cue extends beyond 180 seconds: {record['id']}")
        if occupied and start < occupied[-1][1]:
            raise RuntimeError(f"voice PCM overlap at {record['id']}")
        pcm[start * 2:end * 2] = record["pcm"]
        occupied.append((start, end))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm)


def frequency(note: str) -> float:
    names = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4,
             "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9,
             "A#": 10, "Bb": 10, "B": 11}
    match = re.fullmatch(r"([A-G](?:#|b)?)(-?\d+)", note)
    if not match:
        raise ValueError(note)
    midi = (int(match.group(2)) + 1) * 12 + names[match.group(1)]
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


def section_for(t: float) -> tuple[tuple[str, ...], float, float]:
    # A slow minor/add9 progression with a changing upper arpeggio, not a single drone.
    prog = [
        (0.0, ("D2", "A2", "C3", "E3", "F#3"), 0.10, 0.08),
        (12.0, ("Bb1", "F2", "A2", "C3", "D3"), 0.11, 0.085),
        (28.0, ("G1", "D2", "F2", "A2", "C3"), 0.12, 0.09),
        (42.0, ("A1", "E2", "G2", "B2", "C#3"), 0.12, 0.095),
        (60.0, ("D2", "A2", "C3", "E3", "F#3"), 0.13, 0.11),
        (76.0, ("F1", "C2", "E2", "G2", "A2"), 0.14, 0.12),
        (85.0, ("Bb1", "F2", "A2", "C3", "D3"), 0.14, 0.13),
        (101.0, ("G1", "D2", "F2", "A2", "C#3"), 0.13, 0.11),
        (110.0, ("G1", "D2", "F2", "A2", "C3"), 0.12, 0.08),
        (127.0, ("C2", "G2", "Bb2", "D3", "E3"), 0.035, 0.03),
        (130.0, ("C2", "G2", "Bb2", "D3", "E3"), 0.08, 0.06),
        (136.0, ("D2", "A2", "C3", "E3", "F#3"), 0.095, 0.07),
        (145.0, ("F1", "C2", "E2", "G2", "A2"), 0.09, 0.06),
        (153.0, ("Bb1", "F2", "A2", "C3", "D3"), 0.075, 0.045),
        (160.0, ("D2", "A2", "C3", "E3", "F#3"), 0.045, 0.025),
        (165.0, ("D2", "A2", "C3", "E3", "F#3"), 0.028, 0.012),
        (171.0, ("D2", "A2", "C3", "E3", "F#3"), 0.032, 0.022),
        (176.0, ("D2", "A2", "C3", "E3", "F#3"), 0.026, 0.028),
    ]
    current = prog[0]
    for item in prog:
        if item[0] <= t:
            current = item
        else:
            break
    return current[1], current[2], current[3]


def voice_duck_frames(records: list[dict]) -> list[bool]:
    active = [False] * (TOTAL_SECONDS * FPS)
    for cue in records:
        start = max(0, cue["fromFrame"] - 10)
        end = min(len(active), cue["toFrameExclusive"] + 12)
        for frame in range(start, end):
            active[frame] = True
    return active


def render_music(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    step = 0.25
    chunk_samples = int(SAMPLE_RATE * step)
    pluck_notes = [frequency(n) for n in ("D4", "A3", "C4", "E4", "F#4", "A3", "C4", "D4")]
    duck_frames = voice_duck_frames(records)
    dissonance_frequency = frequency("C#4")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        for chunk_start in range(0, TOTAL_SAMPLES, chunk_samples):
            frames = min(chunk_samples, TOTAL_SAMPLES - chunk_start)
            stereo = array.array("h")
            chord, pad_level, pluck_level = section_for(chunk_start / SAMPLE_RATE)
            chord_frequencies = [frequency(note) for note in chord]
            for i in range(frames):
                sample_index = chunk_start + i
                t = sample_index / SAMPLE_RATE
                if 129.0 <= t < 130.0:
                    stereo.extend((0, 0))
                    continue
                section_fade = min(1.0, max(0.0, t / 1.8), max(0.0, (179.9 - t) / 3.6))
                breath = 0.85 + 0.15 * math.sin(2 * math.pi * 0.075 * t)
                pad = 0.0
                for index, f in enumerate(chord_frequencies):
                    phase = 2.0 * math.pi * f * t
                    shimmer = 0.97 + 0.03 * math.sin(2.0 * math.pi * (0.11 + index * 0.013) * t)
                    pad += (math.sin(phase) + 0.18 * math.sin(2 * phase + 0.14)) * shimmer / (1.0 + index * 0.42)
                pad *= pad_level * breath
                # Slow arpeggio pulses give the harmony a changing, identifiable shape.
                pulse = t / 0.72
                pulse_index = math.floor(pulse)
                pulse_age = (pulse - pulse_index) * 0.72
                note = pluck_notes[(pulse_index + int(t // 12.0)) % len(pluck_notes)]
                pluck_env = math.exp(-pulse_age * 4.4) * min(1.0, max(0.0, (0.72 - pulse_age) / 0.06))
                pluck = (math.sin(2 * math.pi * note * pulse_age)
                         + 0.36 * math.sin(2 * math.pi * note * 2.01 * pulse_age)
                         + 0.14 * math.sin(2 * math.pi * note * 3.02 * pulse_age)) * pluck_env * pluck_level
                # A restrained beating upper tone makes the 101s caution feel uneasy.
                dissonance = 0.0
                if 101.0 <= t < 110.0:
                    dissonance = 0.025 * math.sin(2 * math.pi * dissonance_frequency * t) * (0.5 + 0.5 * math.sin(2 * math.pi * 0.18 * t))
                # Lower the musical bed around spoken phrases; the stem stays independently audible.
                duck = 0.47 if duck_frames[sample_index // (SAMPLE_RATE // FPS)] else 1.0
                if t >= 179.9:
                    fade = max(0.0, (180.0 - t) / 0.1)
                else:
                    fade = 1.0
                mono = (pad + pluck + dissonance) * duck * section_fade * fade
                # Slightly wider upper voices, with a deterministic slow stereo movement.
                width = 0.06 * math.sin(2 * math.pi * 0.021 * t)
                left = max(-0.8, min(0.8, mono * (1.0 - width)))
                right = max(-0.8, min(0.8, mono * (1.0 + width)))
                stereo.extend((int(left * 32767), int(right * 32767)))
            wav.writeframes(stereo.tobytes())


def bell(t: float, start: float, freq: float, amp: float, decay: float = 4.0) -> float:
    age = t - start
    if age < 0 or age > 1.6:
        return 0.0
    env = math.exp(-age * decay)
    return amp * env * (math.sin(2 * math.pi * freq * age) + 0.24 * math.sin(2 * math.pi * freq * 2.7 * age))


def crack(t: float, start: float) -> float:
    age = t - start
    if age < 0 or age > 0.7:
        return 0.0
    env = math.exp(-age * 13.0)
    # Fixed multi-tone impulse with a short granular tail; no random source or loop seam.
    noise = (math.sin(2 * math.pi * 1733 * age) + 0.7 * math.sin(2 * math.pi * 2381 * age + 0.7)
             + 0.4 * math.sin(2 * math.pi * 3191 * age + 1.1))
    return 0.065 * env * noise


def render_sfx(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    values = array.array("f", [0.0]) * TOTAL_SAMPLES

    def add_event(start: float, duration: float, generator) -> None:
        first = max(0, round(start * SAMPLE_RATE))
        last = min(TOTAL_SAMPLES, round((start + duration) * SAMPLE_RATE))
        for sample_index in range(first, last):
            t = sample_index / SAMPLE_RATE
            values[sample_index] += generator(t)

    transfer_times = [20.7, 22.4, 24.2, 29.1, 31.0, 33.0, 63.1, 64.6, 66.1, 68.2,
                      85.7, 88.1, 90.3, 94.4, 97.2, 103.4, 106.2, 108.4]
    check_times = [118.35, 119.7, 121.05, 122.8, 124.0, 125.6, 126.5, 131.0, 132.0, 133.2]
    add_event(165.0, 6.0, lambda t: 0.0018 * (math.sin(2 * math.pi * 49.0 * t)
              + 0.55 * math.sin(2 * math.pi * 73.3 * t + 0.4)
              + 0.22 * math.sin(2 * math.pi * 137.0 * t + 1.2))
              * (max(0.0, (171.0 - t) / 0.4) if t > 170.6 else 1.0))
    add_event(0.0, 5.0, lambda t: (0.0018 * (math.sin(2 * math.pi * 49.0 * t)
              + 0.55 * math.sin(2 * math.pi * 73.3 * t + 0.4)
              + 0.22 * math.sin(2 * math.pi * 137.0 * t + 1.2))
              * (max(0.0, (4.6 - t) / 0.4) if t > 4.6 else 1.0)))
    for index, cue_time in enumerate(transfer_times):
        freq = 1500.0 + (index % 3) * 220.0
        add_event(cue_time, 1.6, lambda t, cue_time=cue_time, freq=freq: bell(t, cue_time, freq, 0.018, 5.2))
    add_event(30.2, 1.6, lambda t: bell(t, 30.2, 710.0, 0.014, 3.2))
    add_event(32.1, 1.6, lambda t: bell(t, 32.1, 880.0, 0.010, 4.5))
    add_event(111.3, 0.7, lambda t: crack(t, 111.3))
    for index, cue_time in enumerate(check_times):
        freq = 850.0 + (index % 4) * 175.0
        add_event(cue_time, 1.6, lambda t, cue_time=cue_time, freq=freq: bell(t, cue_time, freq, 0.013, 6.0))
    add_event(136.6, 1.6, lambda t: bell(t, 136.6, 630.0, 0.015, 2.6))
    add_event(138.2, 1.6, lambda t: bell(t, 138.2, 940.0, 0.010, 3.5))

    chunk_samples = SAMPLE_RATE // 4
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        for chunk_start in range(0, TOTAL_SAMPLES, chunk_samples):
            frames = min(chunk_samples, TOTAL_SAMPLES - chunk_start)
            stereo = array.array("h")
            for i in range(frames):
                sample_index = chunk_start + i
                t = sample_index / SAMPLE_RATE
                if 129.0 <= t < 130.0:
                    stereo.extend((0, 0))
                    continue
                value = values[sample_index]
                if 179.3 <= t < 180.0:
                    value *= max(0.0, (180.0 - t) / 0.7)
                stereo.extend((int(max(-0.7, min(0.7, value)) * 32767),
                               int(max(-0.7, min(0.7, value * 0.93)) * 32767)))
            wav.writeframes(stereo.tobytes())


def ffmpeg_decode_check(path: Path) -> None:
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path), "-f", "null", "-"])


def loudnorm_measure(path: Path) -> dict:
    result = run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
        "-af", "loudnorm=I=-16:TP=-1:LRA=11:print_format=json", "-f", "null", "-",
    ], capture=True)
    combined = (result.stderr or "")
    matches = re.findall(r"\{\s*\"input_i\".*?\}", combined, re.S)
    if not matches:
        raise RuntimeError("ffmpeg loudnorm did not return analysis JSON")
    return json.loads(matches[-1])


def mix_and_loudnorm(path: Path, voice: Path, music: Path, sfx: Path) -> dict:
    mix = AUDIO / "mix_pre_loudnorm.wav"
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(voice), "-i", str(music), "-i", str(sfx),
        "-filter_complex", "[0:a]pan=stereo|c0=c0|c1=c0[v];[v][1:a][2:a]amix=inputs=3:duration=longest:normalize=0,alimiter=limit=0.95:attack=5:release=50[m]",
        "-map", "[m]", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s24le", str(mix),
    ])
    first = loudnorm_measure(mix)
    measured_i = first["input_i"]
    measured_tp = first["input_tp"]
    measured_lra = first["input_lra"]
    measured_thresh = first["input_thresh"]
    offset = first["target_offset"]
    filter_arg = (
        f"loudnorm=I=-16:TP=-1:LRA=11:measured_I={measured_i}:measured_TP={measured_tp}:"
        f"measured_LRA={measured_lra}:measured_thresh={measured_thresh}:offset={offset}:"
        "linear=true:print_format=json"
    )
    result = run([
        "ffmpeg", "-hide_banner", "-nostats", "-y", "-i", str(mix), "-af", filter_arg,
        "-t", str(TOTAL_SECONDS), "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s24le", str(path),
    ], capture=True)
    matches = re.findall(r"\{\s*\"input_i\".*?\}", result.stderr or "", re.S)
    if not matches:
        raise RuntimeError("ffmpeg loudnorm second pass did not return analysis JSON")
    return {"firstPass": first, "secondPass": json.loads(matches[-1])}


def window_peak(path: Path, start_seconds: float, end_seconds: float) -> int:
    with wave.open(str(path), "rb") as wav:
        if wav.getframerate() != SAMPLE_RATE:
            raise ValueError(f"bad sample rate in {path}")
        start = round(start_seconds * SAMPLE_RATE)
        end = round(end_seconds * SAMPLE_RATE)
        wav.setpos(start)
        raw = wav.readframes(end - start)
        width = wav.getsampwidth()
    values = []
    for i in range(0, len(raw), width):
        sample = int.from_bytes(raw[i:i + width], "little", signed=False)
        sign_bit = 1 << (width * 8 - 1)
        if sample & sign_bit:
            sample -= 1 << (width * 8)
        values.append(abs(sample))
    return max(values, default=0)


def force_pcm_silence(path: Path, start_seconds: float, end_seconds: float) -> None:
    temp_path = path.with_suffix(".silence.wav")
    with wave.open(str(path), "rb") as source:
        params = source.getparams()
        start = round(start_seconds * params.framerate)
        end = round(end_seconds * params.framerate)
        with wave.open(str(temp_path), "wb") as target:
            target.setparams(params)
            position = 0
            while position < params.nframes:
                count = min(48_000, params.nframes - position)
                block = source.readframes(count)
                block_frames = len(block) // (params.nchannels * params.sampwidth)
                overlap_start = max(position, start)
                overlap_end = min(position + block_frames, end)
                if overlap_start < overlap_end:
                    first = (overlap_start - position) * params.nchannels * params.sampwidth
                    last = (overlap_end - position) * params.nchannels * params.sampwidth
                    block = block[:first] + bytes(last - first) + block[last:]
                target.writeframes(block)
                position += block_frames
    temp_path.replace(path)


def ebur128_result(path: Path) -> dict:
    result = run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
        "-af", "ebur128=peak=true", "-f", "null", "-",
    ], capture=True)
    output = result.stderr or ""
    integrated_match = re.search(r"^\s*I:\s*(-?\d+(?:\.\d+)?)\s+LUFS\s*$", output, re.M)
    peak_match = re.search(r"^\s*True peak:\s*(-?\d+(?:\.\d+)?)\s+dBTP\s*$", output, re.M)
    if integrated_match is None:
        raise RuntimeError("ffmpeg ebur128 did not report integrated loudness")
    sample_peak_match = re.search(r"^\s*Peak:\s*(-?\d+(?:\.\d+)?)\s+dBFS\s*$", output, re.M)
    return {
        "integratedLUFS": f"{integrated_match.group(1)} LUFS",
        "samplePeak": f"{sample_peak_match.group(1)} dBFS" if sample_peak_match else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--sample", action="store_true", help="render/decode only the first source caption as a sample")
    mode.add_argument("--full", action="store_true", help="render all voice cues, score, effects, mix, timing, and QA")
    args = parser.parse_args()

    for executable in ("say", "ffmpeg", "ffprobe"):
        if shutil.which(executable) is None:
            raise RuntimeError(f"required local executable is unavailable: {executable}")
    data = source_data()
    AUDIO.mkdir(parents=True, exist_ok=True)
    REVIEW.mkdir(parents=True, exist_ok=True)
    (ROOT / "src").mkdir(parents=True, exist_ok=True)

    if args.sample:
        make_sample(data)
        return 0

    records = cue_records(data)
    voice_path = AUDIO / "voice_zh.wav"
    music_path = AUDIO / "music.wav"
    sfx_path = AUDIO / "sfx.wav"
    soundtrack_path = AUDIO / "soundtrack.wav"
    write_mono_stem(records, voice_path)
    render_music(records, music_path)
    render_sfx(sfx_path)

    timing = {
        "cues": [{key: record[key] for key in (
            "id", "shotId", "text", "speaker", "fromFrame", "toFrameExclusive", "audioSeconds", "voice", "rate"
        )} for record in records],
        "durationSeconds": TOTAL_SECONDS,
        "provider": "macOS say",
        "voice": VOICE_LABEL,
        "sampleRate": SAMPLE_RATE,
    }
    TIMING.write_text(json.dumps(timing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    mix_results = mix_and_loudnorm(soundtrack_path, voice_path, music_path, sfx_path)
    silent = {
        "fromSeconds": 129.0,
        "toSecondsExclusive": 130.0,
        "voiceMaxAbsPcm": window_peak(voice_path, 129.0, 130.0),
        "musicMaxAbsPcm": window_peak(music_path, 129.0, 130.0),
        "sfxMaxAbsPcm": window_peak(sfx_path, 129.0, 130.0),
    }
    if any(silent[key] != 0 for key in ("voiceMaxAbsPcm", "musicMaxAbsPcm", "sfxMaxAbsPcm")):
        raise RuntimeError(f"129-130s source-stem exact silence failed: {silent}")
    force_pcm_silence(soundtrack_path, 129.0, 130.0)
    silent["soundtrackMaxAbsPcm"] = window_peak(soundtrack_path, 129.0, 130.0)
    if silent["soundtrackMaxAbsPcm"] != 0:
        raise RuntimeError(f"129-130s final soundtrack silence failed: {silent}")

    decoded = {}
    for path in (voice_path, music_path, sfx_path, soundtrack_path):
        ffmpeg_decode_check(path)
        with wave.open(str(path), "rb") as wav:
            expected_frames = TOTAL_SAMPLES
            if wav.getnframes() != expected_frames or wav.getframerate() != SAMPLE_RATE:
                raise RuntimeError(f"{path.name}: expected {expected_frames} frames at {SAMPLE_RATE}Hz, got {wav.getparams()}")
            decoded[path.name] = {
                "frames": wav.getnframes(),
                "sampleRate": wav.getframerate(),
                "channels": wav.getnchannels(),
                "sampleWidthBytes": wav.getsampwidth(),
                "sha256": sha256(path),
                "ffprobe": probe_audio(path),
                "ffmpegDecode": "passed",
            }

    sample_path = AUDIO / "sample_voice.wav"
    sample_meta = None
    if sample_path.exists():
        sample_meta = {"captionId": "caption-001", "sha256": sha256(sample_path),
                       "decodedSamples": len(read_mono_wav(sample_path)[0]) // 2}

    loudness = ebur128_result(soundtrack_path)
    loudnorm_final_measurement = loudnorm_measure(soundtrack_path)
    loudness["truePeak"] = f"{loudnorm_final_measurement['input_tp']} dBTP"
    qa = {
        "status": "automated_pcm_checks_passed",
        "sourceTimelineSha256": sha256(TIMELINE),
        "provider": "macOS say",
        "voice": VOICE_LABEL,
        "baseRateWpm": BASE_RATE,
        "acceleratedShortCueRateWpm": FAST_RATE,
        "musicDesign": "Original evolving minor/add9 polyphonic score with shifting chord beds, arpeggiated pluck pulses, a restrained dissonance cue, recovery after silence, and an unresolved ending.",
        "sample": sample_meta,
        "cueCount": len(records),
        "cueIds": [record["id"] for record in records],
        "cueTiming": [{key: record[key] for key in (
            "id", "fromFrame", "toFrameExclusive", "plannedFromFrame", "plannedToFrameExclusive", "audioSeconds", "rate"
        )} | {"decodedSamples": record["sampleCount"]} for record in records],
        "decodedFiles": decoded,
        "silenceWindow": silent,
        "ebur128Final": loudness,
        "humanListening": "not performed",
        "visualOrPlaybackAcceptance": "not performed",
        "ffmpegMixAnalysis": {**mix_results, "finalMeasuredInput": loudnorm_final_measurement},
    }
    # Keep the report machine-readable and avoid reporting approximations as human review.
    QA.write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": qa["status"], "timing": str(TIMING), "qa": str(QA),
                      "files": decoded, "silenceWindow": silent, "loudness": loudness},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"audio build failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
