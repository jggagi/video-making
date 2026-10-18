#!/usr/bin/env python3
"""Build a local 60 second XHS PCM mix from the verified EP02 assets."""

from array import array
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import wave


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "xhs-timeline.json"
VOICED_MIX_PATH = ROOT / "out" / "voiced-v2-mix-manifest.json"
SOURCE_DIR = ROOT / "public" / "audio"
OUTPUT_DIR = ROOT / "public" / "audio-xhs-v1"
MANIFEST_PATH = ROOT / "out" / "xhs-v1-audio-manifest.json"

FPS = 60
SAMPLE_RATE = 48_000
CHANNELS = 2
SAMPLE_WIDTH = 2
DURATION_FRAMES = 3_600
SAMPLES_PER_FRAME = SAMPLE_RATE // FPS
TOTAL_SAMPLE_FRAMES = DURATION_FRAMES * SAMPLES_PER_FRAME
TOTAL_SCALARS = TOTAL_SAMPLE_FRAMES * CHANNELS
GENERATOR_VERSION = 1
DUCK_GAIN = 10.0 ** (-8.0 / 20.0)
DUCK_LEAD = round(0.150 * SAMPLE_RATE)
DUCK_ATTACK = round(0.090 * SAMPLE_RATE)
DUCK_RELEASE = round(0.350 * SAMPLE_RATE)
SHORT_FADE = round(0.015 * SAMPLE_RATE)
FINAL_FADE = round(0.600 * SAMPLE_RATE)
TONE_STOP_FRAME = 36
NOISE_SOURCE_START_FRAME = 1_200
NOISE_DEST_START_FRAME = 36
NOISE_FRAMES = 12
QUIET_START_FRAME = 48
VOICE_ENTRY_FRAME = 66
MAX_SAMPLE_PEAK = 0.9
MAX_TRUE_PEAK_DBTP = -1.0

STEM_NAMES = ("overload", "order", "atmosphere")
TONE_FREQUENCIES = tuple(range(220, 1_981, 220))


class MixError(Exception):
    """An input or validation error that prevents a trustworthy mix."""


class NeedsSol(MixError):
    """A mixing threshold needs a root-owned gain or timing decision."""


def fail(message):
    raise MixError(message)


def needs_sol(message):
    raise NeedsSol(message)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative(path):
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def load_json(path):
    try:
        with path.open("r", encoding="utf-8") as source:
            return json.load(source)
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Cannot read {relative(path)}: {exc}")


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def safe_project_file(value, label):
    if not isinstance(value, str) or not value:
        fail(f"{label} must be a non-empty project-relative path.")
    path = Path(value)
    if path.is_absolute():
        fail(f"{label} must be project-relative: {value!r}")
    resolved = (ROOT / path).resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError:
        fail(f"{label} escapes the project root: {value!r}")
    if not resolved.is_file():
        fail(f"Required input is missing: {value}")
    return resolved


def load_wav_payload(path, expected_frames=None, first_frame=0, frame_count=None, expected_channels=CHANNELS):
    try:
        with wave.open(str(path), "rb") as wav:
            params = (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype())
            wanted = (expected_channels, SAMPLE_WIDTH, SAMPLE_RATE, "NONE")
            if params != wanted:
                fail(
                    f"{relative(path)} must be {expected_channels}-channel PCM16 at 48000 Hz; "
                    f"found channels/sample-width/rate/compression={params}."
                )
            total_frames = wav.getnframes()
            if expected_frames is not None and total_frames != expected_frames:
                fail(f"{relative(path)} has {total_frames} frames; expected {expected_frames}.")
            if first_frame < 0 or first_frame > total_frames:
                fail(f"Unsafe WAV seek in {relative(path)}: frame {first_frame} of {total_frames}.")
            if frame_count is None:
                frame_count = total_frames - first_frame
            if frame_count < 0 or first_frame + frame_count > total_frames:
                fail(f"WAV slice exceeds {relative(path)} bounds.")
            wav.setpos(first_frame)
            payload = wav.readframes(frame_count)
    except (OSError, wave.Error) as exc:
        fail(f"Cannot read WAV {relative(path)}: {exc}")

    expected_bytes = frame_count * expected_channels * SAMPLE_WIDTH
    if len(payload) != expected_bytes:
        fail(f"WAV slice from {relative(path)} contains {len(payload)} bytes; expected {expected_bytes}.")
    return payload, total_frames


def as_int16(payload):
    samples = array("h")
    samples.frombytes(payload)
    if sys.byteorder != "little":
        samples.byteswap()
    return samples


def int16_bytes(samples):
    if sys.byteorder == "little":
        return samples.tobytes()
    copy = array("h", samples)
    copy.byteswap()
    return copy.tobytes()


def write_wav(path, payload):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(SAMPLE_WIDTH)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(payload)


def smoothstep(value):
    x = min(1.0, max(0.0, value))
    return x * x * (3.0 - 2.0 * x)


def validate_inputs():
    plan = load_json(PLAN_PATH)
    voiced_mix = load_json(VOICED_MIX_PATH)
    plan_sha = sha256_file(PLAN_PATH)
    mix_sha = sha256_file(VOICED_MIX_PATH)

    required_plan = {
        "fps": FPS,
        "durationInFrames": DURATION_FRAMES,
        "sampleRate": SAMPLE_RATE,
        "overloadFrame": 36,
        "noiseDurationFrames": NOISE_FRAMES,
        "voiceEntryFrame": VOICE_ENTRY_FRAME,
        "chunkFrames": list(range(0, 36, 4)),
    }
    for key, expected in required_plan.items():
        if plan.get(key) != expected:
            fail(f"xhs-timeline.json {key} must be {expected!r}; found {plan.get(key)!r}.")
    if voiced_mix.get("format", {}).get("sampleRate") != SAMPLE_RATE:
        fail("voiced-v2 mix manifest does not describe 48000 Hz audio.")
    if voiced_mix.get("format", {}).get("channels") != CHANNELS or voiced_mix.get("format", {}).get("bitsPerSample") != 16:
        fail("voiced-v2 mix manifest does not describe stereo PCM16.")

    manifest_stems = voiced_mix.get("inputs", {}).get("sourceStems")
    if not isinstance(manifest_stems, dict):
        fail("voiced-v2 mix manifest is missing its sourceStems map.")
    stem_inputs = {}
    for name in STEM_NAMES:
        entry = manifest_stems.get(name)
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            fail(f"voiced-v2 mix manifest has no valid {name!r} source stem.")
        path = safe_project_file(entry["path"], f"{name} source path")
        actual_hash = sha256_file(path)
        if actual_hash != entry.get("sha256"):
            fail(f"{name} source stem SHA256 does not match voiced-v2 mix manifest.")
        total_frames = load_wav_payload(path, expected_frames=voiced_mix["format"]["sampleFrames"], frame_count=0)[1]
        stem_inputs[name] = {
            "path": relative(path),
            "sha256": actual_hash,
            "pathObject": path,
            "totalFrames": total_frames,
        }

    cues = plan.get("cues")
    voiced_cues = voiced_mix.get("cues")
    if not isinstance(cues, list) or len(cues) != 11:
        fail("xhs-timeline.json must contain exactly 11 cached aligned voice cues.")
    if not isinstance(voiced_cues, list):
        fail("voiced-v2 mix manifest is missing its cue array.")
    voiced_by_id = {item.get("id"): item for item in voiced_cues if isinstance(item, dict)}
    resolved_cues = []
    previous_end_sample = 0
    seen = set()
    for cue in cues:
        if not isinstance(cue, dict):
            fail("Every XHS cue must be an object.")
        cue_id = cue.get("id")
        if not isinstance(cue_id, str) or cue_id in seen:
            fail(f"Invalid or duplicate XHS cue id: {cue_id!r}.")
        seen.add(cue_id)
        for field in ("startFrame", "endFrame", "sampleFrames", "rate"):
            if not is_int(cue.get(field)) and field != "rate":
                fail(f"XHS cue {cue_id!r} must have integer {field}.")
        if cue.get("rate") != 1:
            fail(f"XHS cue {cue_id!r} rate must be exactly 1.")
        start_frame = cue["startFrame"]
        sample_frames = cue["sampleFrames"]
        if start_frame < VOICE_ENTRY_FRAME or sample_frames <= 0:
            fail(f"XHS cue {cue_id!r} has an invalid start or sample count.")
        start_sample = start_frame * SAMPLES_PER_FRAME
        end_sample = start_sample + sample_frames
        end_frame = (end_sample + SAMPLES_PER_FRAME - 1) // SAMPLES_PER_FRAME
        if cue["endFrame"] != end_frame:
            fail(f"XHS cue {cue_id!r} endFrame does not match its actual sample count.")
        if end_frame > DURATION_FRAMES or end_sample > TOTAL_SAMPLE_FRAMES:
            fail(f"XHS cue {cue_id!r} does not fit the 60 second output.")
        if start_sample < previous_end_sample:
            fail(f"XHS cue {cue_id!r} overlaps the preceding full cached voice clip.")
        previous_end_sample = end_sample

        aligned_path = safe_project_file(cue.get("file"), f"{cue_id} aligned cue path")
        source_path = safe_project_file(cue.get("sourceFile"), f"{cue_id} source cue path")
        aligned_hash = sha256_file(aligned_path)
        source_hash = sha256_file(source_path)
        if aligned_hash != cue.get("sha256"):
            fail(f"Aligned cue SHA256 does not match xhs-timeline.json for {cue_id!r}.")
        if source_hash != cue.get("sourceSha256"):
            fail(f"Original cue SHA256 does not match xhs-timeline.json for {cue_id!r}.")

        mix_cue = voiced_by_id.get(cue_id)
        if not mix_cue:
            fail(f"voiced-v2 mix manifest has no source/aligned record for {cue_id!r}.")
        if mix_cue.get("alignedSha256") != aligned_hash or mix_cue.get("sourceSha256") != source_hash:
            fail(f"Cached cue hashes for {cue_id!r} do not match voiced-v2 mix manifest.")
        if mix_cue.get("alignedFile") != cue["file"] or mix_cue.get("file") != cue["sourceFile"]:
            fail(f"Cached cue paths for {cue_id!r} do not match voiced-v2 mix manifest.")

        try:
            with wave.open(str(aligned_path), "rb") as wav:
                params = (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype())
                expected = (1, SAMPLE_WIDTH, SAMPLE_RATE, "NONE")
                if params != expected:
                    fail(f"Aligned cue {cue_id!r} must be mono PCM16 at 48000 Hz; found {params}.")
                actual_frames = wav.getnframes()
                if actual_frames != sample_frames:
                    fail(
                        f"Aligned cue {cue_id!r} has {actual_frames} frames per channel; "
                        f"xhs-timeline.json records {sample_frames}."
                    )
        except (OSError, wave.Error) as exc:
            fail(f"Cannot read aligned cue {cue_id!r}: {exc}")

        resolved_cues.append({
            "id": cue_id,
            "file": cue["file"],
            "alignedPath": aligned_path,
            "alignedSha256": aligned_hash,
            "sourceFile": cue["sourceFile"],
            "sourcePath": source_path,
            "sourceSha256": source_hash,
            "startFrame": start_frame,
            "endFrame": end_frame,
            "startSample": start_sample,
            "endSample": end_sample,
            "sampleFrames": sample_frames,
            "atempo": 1,
        })

    edits = plan.get("musicEdits")
    expected_edits = [
        {"from": 66, "to": 1320, "sourceFrame": 1800},
        {"from": 1320, "to": 1680, "sourceFrame": 3800},
        {"from": 1680, "to": 2220, "sourceFrame": 6700},
        {"from": 2220, "to": 3600, "sourceFrame": 8400},
    ]
    if edits != expected_edits:
        fail("xhs-timeline.json musicEdits do not match the approved four source segments.")
    for edit in edits:
        if edit["from"] < VOICE_ENTRY_FRAME or edit["to"] > DURATION_FRAMES or edit["to"] <= edit["from"]:
            fail(f"Invalid music edit bounds: {edit!r}.")
        source_end = edit["sourceFrame"] + (edit["to"] - edit["from"])
        if source_end * SAMPLES_PER_FRAME > stem_inputs["order"]["totalFrames"]:
            fail(f"Music edit exceeds original order.wav: {edit!r}.")
    atmosphere_end = 1_800 + (DURATION_FRAMES - VOICE_ENTRY_FRAME)
    if atmosphere_end * SAMPLES_PER_FRAME > stem_inputs["atmosphere"]["totalFrames"]:
        fail("The optional original atmosphere stem does not cover the approved 60 second span.")

    # Confirm the source noise window exists and that its cache hash remains the voiced-v2 input.
    if (NOISE_SOURCE_START_FRAME + NOISE_FRAMES) * SAMPLES_PER_FRAME > stem_inputs["overload"]["totalFrames"]:
        fail("Original overload noise source slice is outside overload.wav.")

    return {
        "plan": plan,
        "planSha256": plan_sha,
        "voicedMix": voiced_mix,
        "voicedMixSha256": mix_sha,
        "cues": resolved_cues,
        "musicEdits": edits,
        "sourceStems": stem_inputs,
    }


def build_narration(cues):
    payload = bytearray(TOTAL_SCALARS * SAMPLE_WIDTH)
    peak = 0
    clips = []
    for cue in cues:
        source_payload, _ = load_wav_payload(
            cue["alignedPath"], expected_frames=cue["sampleFrames"], expected_channels=1,
        )
        mono_samples = as_int16(source_payload)
        stereo_samples = array("h")
        for sample in mono_samples:
            stereo_samples.extend((sample, sample))
        stereo_payload = int16_bytes(stereo_samples)
        first_scalar = cue["startSample"] * CHANNELS
        byte_start = first_scalar * SAMPLE_WIDTH
        byte_end = byte_start + len(stereo_payload)
        payload[byte_start:byte_end] = stereo_payload
        peak = max(peak, max(abs(sample) for sample in mono_samples))
        clips.append({
            **{key: cue[key] for key in (
                "id", "file", "alignedSha256", "sourceFile", "sourceSha256",
                "startFrame", "endFrame", "startSample", "endSample", "sampleFrames", "atempo",
            )},
            "inputChannels": 1,
            "outputChannels": 2,
            "channelMapping": "L=mono,R=mono; unity",
            "pcmPayloadSha256": sha256_bytes(source_payload),
            "stereoPayloadSha256": sha256_bytes(stereo_payload),
        })
    return bytes(payload), peak / 32768.0, clips


def build_overload(stem_path):
    samples = array("h", [0]) * TOTAL_SCALARS
    tone_stop_sample = TONE_STOP_FRAME * SAMPLES_PER_FRAME
    attack_samples = round(0.035 * SAMPLE_RATE)
    layer_descriptions = []
    for index, frequency in enumerate(TONE_FREQUENCIES):
        start_frame = index * 4
        start_sample = start_frame * SAMPLES_PER_FRAME
        amplitude = 0.025 / math.sqrt(index + 1)
        pan = math.sin(index * 1.11) * 0.12
        left_gain = math.sqrt((1.0 - pan) * 0.5)
        right_gain = math.sqrt((1.0 + pan) * 0.5)
        for sample_frame in range(start_sample, tone_stop_sample):
            local = sample_frame - start_sample
            attack = smoothstep((local + 1) / attack_samples)
            value = math.sin(2.0 * math.pi * frequency * local / SAMPLE_RATE) * amplitude * attack
            left_index = sample_frame * CHANNELS
            samples[left_index] += round(value * left_gain * 32768.0)
            samples[left_index + 1] += round(value * right_gain * 32768.0)
        layer_descriptions.append({
            "index": index,
            "frequencyHz": frequency,
            "startFrame": start_frame,
            "startSample": start_sample,
            "amplitude": amplitude,
            "pan": pan,
            "attackMilliseconds": 35,
            "stopFrame": TONE_STOP_FRAME,
        })

    noise_start = NOISE_DEST_START_FRAME * SAMPLES_PER_FRAME
    noise_count = NOISE_FRAMES * SAMPLES_PER_FRAME
    source_start = NOISE_SOURCE_START_FRAME * SAMPLES_PER_FRAME
    noise_payload, _ = load_wav_payload(stem_path, first_frame=source_start, frame_count=noise_count)
    noise = as_int16(noise_payload)
    dest_scalar = noise_start * CHANNELS
    samples[dest_scalar:dest_scalar + len(noise)] = noise

    tone_peak = max(abs(sample) for sample in samples[:tone_stop_sample * CHANNELS]) / 32768.0
    return int16_bytes(samples), noise_payload, {
        "toneLayers": layer_descriptions,
        "noiseCopy": {
            "sourcePath": "public/audio/overload.wav",
            "sourceFrameRange": [NOISE_SOURCE_START_FRAME, NOISE_SOURCE_START_FRAME + NOISE_FRAMES],
            "destinationFrameRange": [NOISE_DEST_START_FRAME, NOISE_DEST_START_FRAME + NOISE_FRAMES],
            "sourcePcmSha256": sha256_bytes(noise_payload),
            "destinationPcmSha256": sha256_bytes(noise_payload),
            "exactPayloadCopy": True,
        },
        "toneSamplePeak": tone_peak,
    }


def build_duck_envelope(cues):
    envelope = array("f", [1.0]) * TOTAL_SAMPLE_FRAMES
    for cue in cues:
        start = cue["startSample"]
        end = cue["endSample"]
        ramp_start = max(0, start - DUCK_LEAD)
        ramp_end = min(start, ramp_start + DUCK_ATTACK)
        ramp_length = ramp_end - ramp_start
        if ramp_length:
            for offset in range(ramp_length):
                value = 1.0 - (1.0 - DUCK_GAIN) * ((offset + 1) / ramp_length)
                index = ramp_start + offset
                if value < envelope[index]:
                    envelope[index] = value
        hold_start = ramp_end
        if end > hold_start:
            hold_end = min(end, TOTAL_SAMPLE_FRAMES)
            for index in range(hold_start, hold_end):
                if DUCK_GAIN < envelope[index]:
                    envelope[index] = DUCK_GAIN
        release_end = min(TOTAL_SAMPLE_FRAMES, end + DUCK_RELEASE)
        release_length = release_end - end
        if release_length > 0:
            denominator = max(1, release_length - 1)
            for offset in range(release_length):
                value = DUCK_GAIN + (1.0 - DUCK_GAIN) * (offset / denominator)
                index = end + offset
                if value < envelope[index]:
                    envelope[index] = value
    return envelope


def edit_fade(edit_index, edit, sample_frame, edits):
    local = sample_frame - edit["from"] * SAMPLES_PER_FRAME
    length = (edit["to"] - edit["from"]) * SAMPLES_PER_FRAME
    gain = 1.0
    # The first segment and ordinary later entries receive a 15 ms fade-in.
    if edit["from"] != 1_680 and (edit_index == 0 or edit["from"] in (1_320, 2_220)) and local < SHORT_FADE:
        gain = min(gain, local / max(1, SHORT_FADE - 1))
    # Preserve the manifold entry at frame 1680 without a seam fade.
    if edit["to"] in (1_320, 2_220):
        tail = length - local
        if tail <= SHORT_FADE:
            gain = min(gain, max(0.0, (tail - 1) / max(1, SHORT_FADE - 1)))
    if edit["to"] == DURATION_FRAMES:
        tail = length - local
        if tail <= FINAL_FADE:
            gain = min(gain, max(0.0, (tail - 1) / max(1, FINAL_FADE - 1)))
    return gain


def atmosphere_fade(sample_frame):
    start = VOICE_ENTRY_FRAME * SAMPLES_PER_FRAME
    if sample_frame < start:
        return 0.0
    gain = 1.0
    local = sample_frame - start
    if local < SHORT_FADE:
        gain = min(gain, local / max(1, SHORT_FADE - 1))
    tail = TOTAL_SAMPLE_FRAMES - sample_frame
    if tail <= FINAL_FADE:
        gain = min(gain, max(0.0, (tail - 1) / max(1, FINAL_FADE - 1)))
    return gain


def encode_stem_sample(value, name, sample_frame):
    scaled = value * 32768.0
    if scaled < -32768.0 or scaled > 32767.0:
        needs_sol(f"{name} stem would clip at sample frame {sample_frame}; revise the approved gains.")
    return int(round(scaled))


def build_score(stems, edits, duck):
    music_pcm = array("h", [0]) * TOTAL_SCALARS
    edit_metadata = []
    for edit_index, edit in enumerate(edits):
        frame_count = (edit["to"] - edit["from"]) * SAMPLES_PER_FRAME
        source_start = edit["sourceFrame"] * SAMPLES_PER_FRAME
        source_payload, _ = load_wav_payload(
            stems["order"]["pathObject"], first_frame=source_start, frame_count=frame_count,
        )
        source_samples = as_int16(source_payload)
        dest_scalar = edit["from"] * SAMPLES_PER_FRAME * CHANNELS
        music_pcm[dest_scalar:dest_scalar + len(source_samples)] = source_samples
        edit_metadata.append({
            "destinationFrameRange": [edit["from"], edit["to"]],
            "sourceFrameRange": [edit["sourceFrame"], edit["sourceFrame"] + edit["to"] - edit["from"]],
            "sampleFrames": frame_count,
            "sameSpeed": True,
        })

    atmosphere_start = 1_800 * SAMPLES_PER_FRAME
    atmosphere_count = (DURATION_FRAMES - VOICE_ENTRY_FRAME) * SAMPLES_PER_FRAME
    atmosphere_payload, _ = load_wav_payload(
        stems["atmosphere"]["pathObject"], first_frame=atmosphere_start, frame_count=atmosphere_count,
    )
    atmosphere_samples = as_int16(atmosphere_payload)
    atmosphere = array("h", [0]) * TOTAL_SCALARS
    atmosphere_scalar = VOICE_ENTRY_FRAME * SAMPLES_PER_FRAME * CHANNELS
    atmosphere[atmosphere_scalar:atmosphere_scalar + len(atmosphere_samples)] = atmosphere_samples

    score = array("h", [0]) * TOTAL_SCALARS
    edit_index = 0
    for sample_frame in range(VOICE_ENTRY_FRAME * SAMPLES_PER_FRAME, TOTAL_SAMPLE_FRAMES):
        while edit_index + 1 < len(edits) and sample_frame >= edits[edit_index]["to"] * SAMPLES_PER_FRAME:
            edit_index += 1
        edit = edits[edit_index]
        music_gain = edit_fade(edit_index, edit, sample_frame, edits) * duck[sample_frame]
        atmosphere_gain = 0.45 * atmosphere_fade(sample_frame) * duck[sample_frame]
        scalar = sample_frame * CHANNELS
        left = music_pcm[scalar] / 32768.0 * music_gain + atmosphere[scalar] / 32768.0 * atmosphere_gain
        right = music_pcm[scalar + 1] / 32768.0 * music_gain + atmosphere[scalar + 1] / 32768.0 * atmosphere_gain
        score[scalar] = encode_stem_sample(left, "Score", sample_frame)
        score[scalar + 1] = encode_stem_sample(right, "Score", sample_frame)

    return int16_bytes(score), {
        "musicEdits": edit_metadata,
        "atmosphere": {
            "sourcePath": stems["atmosphere"]["path"],
            "sourceFrameRange": [1_800, 1_800 + DURATION_FRAMES - VOICE_ENTRY_FRAME],
            "destinationFrameRange": [VOICE_ENTRY_FRAME, DURATION_FRAMES],
            "gain": 0.45,
        },
        "ducking": {
            "tracks": ["music", "atmosphere"],
            "attenuationDb": -8.0,
            "leadMilliseconds": 150,
            "attackMilliseconds": 90,
            "releaseMilliseconds": 350,
            "envelope": "linear amplitude ramp begins at cue start minus lead; hold spans full cue; release follows cue",
        },
        "fades": {
            "shortFadeMilliseconds": 15,
            "cuts": [1_320, 2_220],
            "manifoldEntryFrame": 1_680,
            "manifoldEntryPreserved": True,
            "finalFadeMilliseconds": 600,
        },
    }


def build_soundtrack(narration_payload, score_payload, overload_payload):
    narration = as_int16(narration_payload)
    score = as_int16(score_payload)
    overload = as_int16(overload_payload)
    if not (len(narration) == len(score) == len(overload) == TOTAL_SCALARS):
        fail("One or more PCM stems have an unexpected scalar sample count.")
    soundtrack = array("h")
    peak = 0
    for index in range(TOTAL_SCALARS):
        value = narration[index] + score[index] + overload[index]
        if value < -32768 or value > 32767:
            needs_sol(f"Soundtrack would clip at interleaved sample index {index}; root must revise the mix.")
        soundtrack.append(value)
        peak = max(peak, abs(value))
    if peak / 32768.0 >= MAX_SAMPLE_PEAK:
        needs_sol(f"Soundtrack sample peak {peak / 32768.0:.6f} is not below {MAX_SAMPLE_PEAK:.2f}.")
    return int16_bytes(soundtrack), peak / 32768.0


def verify_pcm_layout(path, payload):
    try:
        with wave.open(str(path), "rb") as wav:
            actual = (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes(), wav.getcomptype())
            expected = (CHANNELS, SAMPLE_WIDTH, SAMPLE_RATE, TOTAL_SAMPLE_FRAMES, "NONE")
            if actual != expected:
                fail(f"{relative(path)} has WAV metadata {actual}; expected {expected}.")
            actual_payload = wav.readframes(TOTAL_SAMPLE_FRAMES)
    except (OSError, wave.Error) as exc:
        fail(f"Cannot verify generated WAV {relative(path)}: {exc}")
    if actual_payload != payload:
        fail(f"{relative(path)} payload changed during WAV writing.")


def measure_loudness(path, ffmpeg):
    command = [
        ffmpeg, "-nostdin", "-hide_banner", "-nostats", "-i", str(path),
        "-af", "loudnorm=I=-23:TP=-1:LRA=7:print_format=json", "-f", "null", "-",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        fail(f"Cannot run ffmpeg loudness measurement: {exc}")
    if result.returncode != 0:
        fail(f"ffmpeg loudness measurement failed: {result.stderr[-2_000:]}")
    matches = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", result.stderr, re.DOTALL)
    if not matches:
        fail("ffmpeg did not report loudness and true-peak measurements.")
    try:
        report = json.loads(matches[-1])
        integrated = float(report["input_i"])
        true_peak = float(report["input_tp"])
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        fail(f"Cannot parse ffmpeg loudness/true-peak report: {exc}")
    if not math.isfinite(integrated) or not math.isfinite(true_peak):
        fail("ffmpeg loudness/true-peak report is not finite.")
    return {
        "integratedLufs": integrated,
        "truePeakDbtp": true_peak,
        "measurement": "ffmpeg loudnorm input_i/input_tp analysis; output files are unprocessed PCM",
    }


def verify_silence(payload, first_frame, end_frame, label):
    first_byte = first_frame * SAMPLES_PER_FRAME * CHANNELS * SAMPLE_WIDTH
    end_byte = end_frame * SAMPLES_PER_FRAME * CHANNELS * SAMPLE_WIDTH
    if any(payload[first_byte:end_byte]):
        fail(f"{label} is not digital zero in frames {first_frame}..{end_frame}.")


def check_inputs_unchanged(inputs):
    for name, stem in inputs["sourceStems"].items():
        if sha256_file(stem["pathObject"]) != stem["sha256"]:
            fail(f"Original {name} source stem changed while the XHS mix was being built.")
    for cue in inputs["cues"]:
        if sha256_file(cue["alignedPath"]) != cue["alignedSha256"]:
            fail(f"Cached aligned voice {cue['id']!r} changed while the mix was being built.")
        if sha256_file(cue["sourcePath"]) != cue["sourceSha256"]:
            fail(f"Original voice source {cue['id']!r} changed while the mix was being built.")
    if sha256_file(PLAN_PATH) != inputs["planSha256"]:
        fail("xhs-timeline.json changed while the XHS mix was being built.")
    if sha256_file(VOICED_MIX_PATH) != inputs["voicedMixSha256"]:
        fail("voiced-v2 mix manifest changed while the XHS mix was being built.")


def main():
    inputs = validate_inputs()
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        fail("ffmpeg is required for actual loudness and true-peak validation.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".mix-xhs-", dir=OUTPUT_DIR) as temporary:
        temp_dir = Path(temporary)
        narration_payload, narration_peak, cue_manifest = build_narration(inputs["cues"])
        overload_payload, noise_payload, overload_info = build_overload(inputs["sourceStems"]["overload"]["pathObject"])
        duck = build_duck_envelope(inputs["cues"])
        score_payload, score_info = build_score(inputs["sourceStems"], inputs["musicEdits"], duck)
        soundtrack_payload, soundtrack_peak = build_soundtrack(narration_payload, score_payload, overload_payload)

        verify_silence(overload_payload, QUIET_START_FRAME, VOICE_ENTRY_FRAME, "Overload stem quiet interval")
        for label, payload in (
            ("Narration stem", narration_payload),
            ("Score stem", score_payload),
            ("Soundtrack", soundtrack_payload),
        ):
            verify_silence(payload, QUIET_START_FRAME, VOICE_ENTRY_FRAME, f"{label} quiet interval")
        noise_start_byte = NOISE_DEST_START_FRAME * SAMPLES_PER_FRAME * CHANNELS * SAMPLE_WIDTH
        noise_end_byte = (NOISE_DEST_START_FRAME + NOISE_FRAMES) * SAMPLES_PER_FRAME * CHANNELS * SAMPLE_WIDTH
        output_noise_payload = overload_payload[noise_start_byte:noise_end_byte]
        if output_noise_payload != noise_payload:
            fail("The XHS overload noise payload does not exactly match source frames 1200..1212.")
        if len(inputs["cues"]) != 11 or any(cue["atempo"] != 1 for cue in cue_manifest):
            fail("Expected 11 complete cached voice cues with atempo=1.")

        temp_paths = {
            "narration": temp_dir / "narration.wav",
            "score": temp_dir / "score.wav",
            "overload": temp_dir / "overload.wav",
            "soundtrack": temp_dir / "soundtrack.wav",
        }
        payloads = {
            "narration": narration_payload,
            "score": score_payload,
            "overload": overload_payload,
            "soundtrack": soundtrack_payload,
        }
        for name, path in temp_paths.items():
            write_wav(path, payloads[name])
            verify_pcm_layout(path, payloads[name])

        loudness = measure_loudness(temp_paths["soundtrack"], ffmpeg)
        if loudness["truePeakDbtp"] >= MAX_TRUE_PEAK_DBTP:
            needs_sol(
                f"Soundtrack true peak is {loudness['truePeakDbtp']:.3f} dBTP; "
                f"it must be below {MAX_TRUE_PEAK_DBTP:.1f} dBTP."
            )
        check_inputs_unchanged(inputs)

        hashes = {name: sha256_file(path) for name, path in temp_paths.items()}
        manifest = {
            "edition": "EP02 Xiaohongshu local-only 60 second PCM mix v1",
            "generatorVersion": GENERATOR_VERSION,
            "planSha256": inputs["planSha256"],
            "format": {
                "fps": FPS,
                "sampleRate": SAMPLE_RATE,
                "channels": CHANNELS,
                "bitsPerSample": SAMPLE_WIDTH * 8,
                "durationFrames": DURATION_FRAMES,
                "sampleFrames": TOTAL_SAMPLE_FRAMES,
                "durationSeconds": DURATION_FRAMES / FPS,
            },
            "inputs": {
                "sourceStems": {
                    name: {"path": entry["path"], "sha256": entry["sha256"]}
                    for name, entry in inputs["sourceStems"].items()
                },
                "voicedV2MixManifest": {
                    "path": relative(VOICED_MIX_PATH),
                    "sha256": inputs["voicedMixSha256"],
                },
            },
            "cues": cue_manifest,
            "outputs": {
                name: {"path": f"public/audio-xhs-v1/{name}.wav", "sha256": hashes[name]}
                for name in ("overload", "narration", "score", "soundtrack")
            },
            "validation": {
                "noiseSampleCopy": True,
                "quietFrameRange": [QUIET_START_FRAME, VOICE_ENTRY_FRAME],
                "samplePeakDbfs": None if soundtrack_peak == 0 else 20.0 * math.log10(soundtrack_peak),
                "integratedLufs": loudness["integratedLufs"],
                "truePeakDbtp": loudness["truePeakDbtp"],
                "ffmpegMeasurement": loudness["measurement"],
                "narrationSamplePeak": narration_peak,
                "soundtrackSamplePeak": soundtrack_peak,
                "soundtrackSamplePeakBelow0_9": soundtrack_peak < MAX_SAMPLE_PEAK,
            },
            "provenance": {
                "musicEdits": score_info["musicEdits"],
                "atmosphere": score_info["atmosphere"],
                "ducking": score_info["ducking"],
                "fades": score_info["fades"],
                "overload": overload_info,
                "noisePayloadSha256": sha256_bytes(noise_payload),
                "clipSamplesPreserved": True,
                "clipSampleFramesPerChannel": {cue["id"]: cue["sampleFrames"] for cue in cue_manifest},
                "atempo": 1,
                "planSha256": inputs["planSha256"],
                "sourceInputStemsSha256": {name: entry["sha256"] for name, entry in inputs["sourceStems"].items()},
            },
            "cloud": {"providerCalls": 0, "asrUploads": 0},
        }

        check_inputs_unchanged(inputs)
        # All PCM has passed validation in a private temporary directory; publish only these four new outputs.
        for name, temp_path in temp_paths.items():
            os.replace(temp_path, OUTPUT_DIR / f"{name}.wav")
        temp_manifest = temp_dir / "xhs-v1-audio-manifest.json"
        temp_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temp_manifest, MANIFEST_PATH)

    print(json.dumps({
        "status": "DONE",
        "manifest": relative(MANIFEST_PATH),
        "planSha256": inputs["planSha256"],
        "outputs": {key: value["sha256"] for key, value in manifest["outputs"].items()},
        "validation": manifest["validation"],
        "cueCount": len(manifest["cues"]),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except NeedsSol as exc:
        print(f"NEEDS_SOL: {exc}", file=sys.stderr)
        sys.exit(2)
    except MixError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
