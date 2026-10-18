#!/usr/bin/env python3
"""Build the offline EP02 voiced-v2 PCM mix from verified local WAV assets."""

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


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLAN_DIR = PROJECT_ROOT / "audio-voiced-v2"
PLAN_PATH = PLAN_DIR / "voice-plan.json"
VOICE_MANIFEST_PATH = PLAN_DIR / "voice-manifest.json"
STEM_DIR = PROJECT_ROOT / "public" / "audio"
OUTPUT_DIR = PROJECT_ROOT / "public" / "audio-voiced-v2"
MIX_MANIFEST_PATH = PROJECT_ROOT / "out" / "voiced-v2-mix-manifest.json"

FPS = 60
SAMPLE_RATE = 48_000
SOURCE_RATE = 24_000
CHANNELS = 2
TOTAL_FRAMES = 10_800
SAMPLES_PER_FRAME = SAMPLE_RATE // FPS
TOTAL_SAMPLES = TOTAL_FRAMES * SAMPLES_PER_FRAME
MAX_ATEMPO = 1.18
PLAN_CUE_FIELDS = (
    "id",
    "text",
    "spokenText",
    "subtitleFrom",
    "subtitleTo",
    "startFrame",
    "deadlineFrame",
    "file",
)
STEM_NAMES = ("overload", "order", "atmosphere")

NON_SILENT_FLOOR = 10.0 ** (-60.0 / 20.0)
TARGET_RMS = 10.0 ** (-20.0 / 20.0)
MAX_GAIN = 10.0 ** (6.0 / 20.0)
VOICE_PEAK_CEILING = 10.0 ** (-3.0 / 20.0)
DUCK_GAIN = 10.0 ** (-7.0 / 20.0)
DUCK_LEAD_SAMPLES = round(0.150 * SAMPLE_RATE)
DUCK_ATTACK_SAMPLES = round(0.090 * SAMPLE_RATE)
DUCK_RELEASE_SAMPLES = round(0.450 * SAMPLE_RATE)
MAX_VOICE_END_SAMPLE = round(179.8 * SAMPLE_RATE)
QUIET_AFTER_NOISE_START = 1_212 * SAMPLES_PER_FRAME
FIRST_VOICE_SAMPLE = 1_242 * SAMPLES_PER_FRAME


class MixError(Exception):
    """Input or execution invariant that prevents a safe mix."""


class NeedsSol(MixError):
    """A gain or timing decision needs to return to the root agent."""


def fail(message):
    raise MixError(message)


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path):
    try:
        with path.open("r", encoding="utf-8") as source:
            return json.load(source)
    except FileNotFoundError:
        fail(f"Required input is missing: {path.relative_to(PROJECT_ROOT)}")
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Cannot read JSON input {path.relative_to(PROJECT_ROOT)}: {exc}")


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def validate_plan(root):
    if not PLAN_PATH.is_file():
        fail(f"Required input is missing: {PLAN_PATH.relative_to(root)}")
    if not VOICE_MANIFEST_PATH.is_file():
        fail(f"Required input is missing: {VOICE_MANIFEST_PATH.relative_to(root)}")

    plan = load_json(PLAN_PATH)
    manifest = load_json(VOICE_MANIFEST_PATH)
    for key, expected in (
        ("fps", FPS),
        ("durationInFrames", TOTAL_FRAMES),
        ("sampleRate", SAMPLE_RATE),
        ("sourceSampleRate", SOURCE_RATE),
    ):
        if plan.get(key) != expected:
            fail(f"voice-plan.json {key} must be {expected}; found {plan.get(key)!r}")
    if plan.get("overloadVoiceEntryFrame") != 1_242:
        fail("voice-plan.json overloadVoiceEntryFrame must be 1242.")

    cues = plan.get("cues")
    manifest_cues = manifest.get("cues")
    if not isinstance(cues, list) or not cues:
        fail("voice-plan.json must contain at least one cue.")
    if not isinstance(manifest_cues, list):
        fail("voice-manifest.json must contain a cues array.")
    if len(cues) != len(manifest_cues):
        fail("voice-manifest.json cue count does not match voice-plan.json.")

    manifest_by_id = {}
    for entry in manifest_cues:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            fail("Every voice-manifest.json cue must be an object with an id.")
        cue_id = entry["id"]
        if cue_id in manifest_by_id:
            fail(f"Duplicate cue id in voice-manifest.json: {cue_id!r}")
        manifest_by_id[cue_id] = entry

    resolved_cues = []
    seen_ids = set()
    for cue in cues:
        if not isinstance(cue, dict):
            fail("Every voice-plan.json cue must be an object.")
        missing = [field for field in PLAN_CUE_FIELDS if field not in cue]
        if missing:
            fail(f"Voice cue is missing required plan fields: {', '.join(missing)}")
        cue_id = cue["id"]
        if not isinstance(cue_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", cue_id):
            fail(f"Cue id must be a safe filename component: {cue_id!r}")
        if cue_id in seen_ids:
            fail(f"Duplicate cue id in voice-plan.json: {cue_id!r}")
        seen_ids.add(cue_id)
        for field in ("text", "spokenText", "file"):
            if not isinstance(cue[field], str) or not cue[field].strip():
                fail(f"Voice cue {cue_id!r} has an empty or invalid {field}.")
        if not is_int(cue["startFrame"]) or not is_int(cue["deadlineFrame"]):
            fail(f"Voice cue {cue_id!r} startFrame and deadlineFrame must be integers.")
        start_frame = cue["startFrame"]
        deadline_frame = cue["deadlineFrame"]
        if start_frame < 0 or deadline_frame <= start_frame or deadline_frame > TOTAL_FRAMES:
            fail(f"Voice cue {cue_id!r} has unsafe frame bounds {start_frame}..{deadline_frame}.")
        if deadline_frame > MAX_VOICE_END_SAMPLE // SAMPLES_PER_FRAME:
            fail(
                f"Voice cue {cue_id!r} deadline must not exceed the 179.8 second boundary "
                f"(frame {MAX_VOICE_END_SAMPLE // SAMPLES_PER_FRAME})."
            )

        manifest_entry = manifest_by_id.get(cue_id)
        if manifest_entry is None:
            fail(f"voice-manifest.json has no entry for cue {cue_id!r}.")
        for field in PLAN_CUE_FIELDS:
            if field not in manifest_entry or manifest_entry[field] != cue[field]:
                fail(f"voice-manifest.json {cue_id!r} field {field!r} does not match voice-plan.json.")
        source_hash = manifest_entry.get("sha256")
        if not isinstance(source_hash, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", source_hash):
            fail(f"voice-manifest.json cue {cue_id!r} has an invalid sha256.")

        relative_file = Path(cue["file"])
        if relative_file.is_absolute():
            fail(f"Voice cue {cue_id!r} file must be project-relative.")
        source_path = (root / relative_file).resolve()
        try:
            source_path.relative_to(root.resolve())
        except ValueError:
            fail(f"Voice cue {cue_id!r} file escapes the project root.")
        if source_path.suffix.lower() != ".wav":
            fail(f"Voice cue {cue_id!r} file must be a WAV file.")
        if not source_path.is_file():
            fail(f"Required voice source is missing: {relative_file.as_posix()}")
        actual_hash = sha256_file(source_path)
        if actual_hash.lower() != source_hash.lower():
            fail(f"Voice source SHA256 does not match voice-manifest.json for cue {cue_id!r}.")

        try:
            with wave.open(str(source_path), "rb") as source_wav:
                if source_wav.getcomptype() != "NONE":
                    fail(f"Voice cue {cue_id!r} must use uncompressed PCM WAV.")
                if source_wav.getframerate() != SOURCE_RATE or source_wav.getnchannels() != 1 or source_wav.getsampwidth() != 2:
                    fail(f"Voice cue {cue_id!r} must be a {SOURCE_RATE} Hz mono WAV.")
                source_frames = source_wav.getnframes()
                if source_frames <= 0:
                    fail(f"Voice cue {cue_id!r} contains no audio frames.")
        except (OSError, wave.Error) as exc:
            fail(f"Cannot read canonical WAV for cue {cue_id!r}: {exc}")

        available_samples = (deadline_frame - start_frame) * SAMPLES_PER_FRAME
        original_seconds = source_frames / SOURCE_RATE
        required_tempo = max(1.0, original_seconds / (available_samples / SAMPLE_RATE))
        if required_tempo > MAX_ATEMPO + 1e-9:
            raise NeedsSol(
                f"Cue {cue_id!r} needs atempo {required_tempo:.6f}, above the {MAX_ATEMPO:.2f} limit; "
                "the source must not be cut."
            )

        resolved_cues.append({
            "plan": cue,
            "manifest": manifest_entry,
            "path": source_path,
            "sourceFrames": source_frames,
            "sourceSha256": actual_hash,
            "originalDurationSeconds": original_seconds,
            "availableSamples": available_samples,
        })

    if set(manifest_by_id) != seen_ids:
        fail("voice-manifest.json contains cues that are absent from voice-plan.json.")
    if not any(item["plan"]["startFrame"] == 1_242 for item in resolved_cues):
        fail("A narration cue must start at frame 1242 to preserve the 0.5 second post-noise quiet.")
    return plan, manifest, resolved_cues


def read_stem(path):
    if not path.is_file():
        fail(f"Required source stem is missing: {path.relative_to(PROJECT_ROOT)}")
    try:
        with wave.open(str(path), "rb") as source:
            actual = (source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getnframes())
            expected = (CHANNELS, 2, SAMPLE_RATE, TOTAL_SAMPLES)
            if source.getcomptype() != "NONE" or actual != expected:
                fail(
                    f"Source stem {path.name} must be stereo PCM16, 48000 Hz, "
                    f"and {TOTAL_SAMPLES} frames; found {actual}."
                )
            pcm = array("h")
            pcm.frombytes(source.readframes(TOTAL_SAMPLES))
    except (OSError, wave.Error) as exc:
        fail(f"Cannot read source stem {path.name}: {exc}")
    if sys.byteorder != "little":
        pcm.byteswap()
    if len(pcm) != TOTAL_SAMPLES * CHANNELS:
        fail(f"Source stem {path.name} decoded to an unexpected sample count.")
    return pcm


def decode_voice(path, tempo, ffmpeg):
    command = [
        ffmpeg,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-map",
        "0:a:0",
        "-vn",
        *(["-af", f"atempo={tempo:.9f}"] if abs(tempo - 1.0) > 1e-9 else []),
        "-ac",
        "1",
        "-ar",
        str(SAMPLE_RATE),
        "-f",
        "s16le",
        "pipe:1",
    ]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    except OSError as exc:
        fail(f"Could not run ffmpeg for {path.name}: {exc}")
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        fail(f"ffmpeg could not decode {path.name}: {detail or result.returncode}")
    if len(result.stdout) % 2:
        fail(f"ffmpeg returned malformed PCM for {path.name}.")
    pcm = array("h")
    pcm.frombytes(result.stdout)
    if sys.byteorder != "little":
        pcm.byteswap()
    if not pcm:
        fail(f"ffmpeg returned no audio for {path.name}.")
    return pcm


def safe_atempo(cue, ffmpeg):
    plan = cue["plan"]
    capacity = cue["availableSamples"]
    tempo = max(
        1.0,
        cue["originalDurationSeconds"] / (capacity / SAMPLE_RATE),
    )
    for _ in range(5):
        decoded = decode_voice(cue["path"], tempo, ffmpeg)
        if len(decoded) <= capacity:
            return decoded, tempo
        corrected = tempo * (len(decoded) / capacity) * 1.00001
        if corrected > MAX_ATEMPO + 1e-9:
            raise NeedsSol(
                f"Cue {plan['id']!r} still exceeds its deadline after atempo={tempo:.6f}; "
                "the source must not be cut."
            )
        tempo = min(MAX_ATEMPO, corrected)
    raise NeedsSol(f"Cue {plan['id']!r} did not fit its deadline after safe atempo adjustment.")


def normalize_voice(decoded, cue_id):
    peak = max(abs(sample) for sample in decoded) / 32768.0
    squares = 0.0
    count = 0
    for sample in decoded:
        value = sample / 32768.0
        if abs(value) > NON_SILENT_FLOOR:
            squares += value * value
            count += 1
    if count == 0:
        fail(f"Voice cue {cue_id!r} has no samples above -60 dBFS.")

    nonsilent_rms = math.sqrt(squares / count)
    gain = min(MAX_GAIN, TARGET_RMS / nonsilent_rms)
    if peak * gain > VOICE_PEAK_CEILING:
        gain = VOICE_PEAK_CEILING / peak
    if not math.isfinite(gain) or gain <= 0:
        fail(f"Voice cue {cue_id!r} produced an invalid normalization gain.")

    normalized = array("h")
    for sample in decoded:
        adjusted = int(round(sample * gain))
        if adjusted < -32768 or adjusted > 32767:
            fail(f"Voice cue {cue_id!r} would clip during per-cue normalization.")
        normalized.append(adjusted)
    return normalized, gain, nonsilent_rms, peak


def little_endian_bytes(samples):
    if sys.byteorder == "little":
        return samples.tobytes()
    copy = array(samples.typecode, samples)
    copy.byteswap()
    return copy.tobytes()


def write_wav(path, channels, frames, sample_iter):
    with wave.open(str(path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        for block in sample_iter:
            output.writeframesraw(little_endian_bytes(block))
        output.writeframes(b"")


def build_duck_envelope(cues):
    duck = array("f", [1.0]) * TOTAL_SAMPLES

    def apply_min(start, values):
        end = min(TOTAL_SAMPLES, start + len(values))
        for offset in range(max(0, start), end):
            value = values[offset - start]
            if value < duck[offset]:
                duck[offset] = value

    for cue in cues:
        start = cue["startSample"]
        end = cue["endSample"]
        ramp_start = max(0, start - DUCK_LEAD_SAMPLES)
        attack_length = min(DUCK_ATTACK_SAMPLES, start - ramp_start)
        if attack_length:
            attack = array(
                "f",
                (
                    1.0 - (1.0 - DUCK_GAIN) * (index + 1) / attack_length
                    for index in range(attack_length)
                ),
            )
            apply_min(ramp_start, attack)
        attack_end = ramp_start + attack_length
        hold_length = max(0, end - attack_end)
        if hold_length:
            apply_min(attack_end, array("f", [DUCK_GAIN]) * hold_length)
        release_length = min(DUCK_RELEASE_SAMPLES, TOTAL_SAMPLES - end)
        if release_length:
            denominator = max(1, release_length - 1)
            release = array(
                "f",
                (
                    DUCK_GAIN + (1.0 - DUCK_GAIN) * index / denominator
                    for index in range(release_length)
                ),
            )
            apply_min(end, release)
    return duck


def sample_blocks(frames_per_block=16_384):
    for first in range(0, TOTAL_SAMPLES, frames_per_block):
        count = min(frames_per_block, TOTAL_SAMPLES - first)
        yield first, count


def encode_sample(value, name, frame):
    scaled = value * 32768.0
    if scaled < -32768.0 or scaled > 32767.0:
        raise NeedsSol(f"{name} would clip at sample frame {frame}; revise gains before mixing.")
    return int(round(scaled))


def create_outputs(temp_dir, voice, duck, overload, order, atmosphere):
    narration_path = temp_dir / "narration.wav"
    soundtrack_path = temp_dir / "soundtrack.wav"
    mix_peak = 0.0
    narration_peak = 0.0
    left_peak = 0.0
    right_peak = 0.0
    final_left = final_right = None
    silence_ok = True

    with wave.open(str(narration_path), "wb") as narration, wave.open(str(soundtrack_path), "wb") as soundtrack:
        for output in (narration, soundtrack):
            output.setnchannels(CHANNELS)
            output.setsampwidth(2)
            output.setframerate(SAMPLE_RATE)

        for first, count in sample_blocks():
            narration_block = array("h")
            soundtrack_block = array("h")
            for frame in range(first, first + count):
                voice_sample = voice[frame]
                voice_pcm = encode_sample(voice_sample, "Narration", frame)
                narration_block.extend((voice_pcm, voice_pcm))
                narration_amplitude = abs(voice_pcm) / 32768.0
                narration_peak = max(narration_peak, narration_amplitude)

                source_index = frame * CHANNELS
                duck_gain = duck[frame]
                left = (
                    overload[source_index] / 32768.0
                    + order[source_index] / 32768.0 * duck_gain
                    + atmosphere[source_index] / 32768.0 * duck_gain
                    + voice_sample
                )
                right = (
                    overload[source_index + 1] / 32768.0
                    + order[source_index + 1] / 32768.0 * duck_gain
                    + atmosphere[source_index + 1] / 32768.0 * duck_gain
                    + voice_sample
                )
                left_pcm = encode_sample(left, "Soundtrack", frame)
                right_pcm = encode_sample(right, "Soundtrack", frame)
                soundtrack_block.extend((left_pcm, right_pcm))
                left_amplitude = abs(left_pcm) / 32768.0
                right_amplitude = abs(right_pcm) / 32768.0
                left_peak = max(left_peak, left_amplitude)
                right_peak = max(right_peak, right_amplitude)
                mix_peak = max(mix_peak, left_amplitude, right_amplitude)

                if QUIET_AFTER_NOISE_START <= frame < FIRST_VOICE_SAMPLE:
                    silence_ok = silence_ok and left_pcm == 0 and right_pcm == 0
                if frame == TOTAL_SAMPLES - 1:
                    final_left, final_right = left_pcm, right_pcm

            narration.writeframesraw(little_endian_bytes(narration_block))
            soundtrack.writeframesraw(little_endian_bytes(soundtrack_block))
        narration.writeframes(b"")
        soundtrack.writeframes(b"")

    if not silence_ok:
        fail("The 0.5 second quiet after the overload noise is not sample-exact.")
    if final_left != 0 or final_right != 0:
        fail("The final soundtrack sample must be digital zero.")
    if mix_peak > 0.85:
        raise NeedsSol(
            f"Mixed soundtrack sample peak is {mix_peak:.6f} (>0.85); root must revise gains."
        )
    return {
        "narration": {
            "path": "public/audio-voiced-v2/narration.wav",
            "samplePeak": narration_peak,
            "samplePeakDbfs": None if narration_peak == 0 else 20.0 * math.log10(narration_peak),
            "sha256": sha256_file(narration_path),
        },
        "soundtrack": {
            "path": "public/audio-voiced-v2/soundtrack.wav",
            "samplePeak": mix_peak,
            "samplePeakDbfs": None if mix_peak == 0 else 20.0 * math.log10(mix_peak),
            "leftSamplePeak": left_peak,
            "rightSamplePeak": right_peak,
            "sha256": sha256_file(soundtrack_path),
        },
    }


def main():
    root = PROJECT_ROOT.resolve()
    plan, source_manifest, cues = validate_plan(root)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        fail("ffmpeg is required but is not available on PATH.")

    stem_paths = {name: STEM_DIR / f"{name}.wav" for name in STEM_NAMES}
    stem_hashes = {}
    for name, path in stem_paths.items():
        if not path.is_file():
            fail(f"Required source stem is missing: {path.relative_to(root)}")
        stem_hashes[name] = sha256_file(path)
    overload = read_stem(stem_paths["overload"])
    order = read_stem(stem_paths["order"])
    atmosphere = read_stem(stem_paths["atmosphere"])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    temp_dir_path = Path(tempfile.mkdtemp(prefix=".voiced-v2-mix-", dir=OUTPUT_DIR))
    temp_dir = temp_dir_path
    try:
        cue_results = []
        voice = array("d", [0.0]) * TOTAL_SAMPLES
        manifest_cues = []
        aligned_dir = temp_dir / "aligned"
        aligned_dir.mkdir()
        for cue in cues:
            plan_cue = cue["plan"]
            decoded, tempo = safe_atempo(cue, ffmpeg)
            normalized, gain, nonsilent_rms, input_peak = normalize_voice(decoded, plan_cue["id"])
            start_sample = plan_cue["startFrame"] * SAMPLES_PER_FRAME
            end_sample = start_sample + len(normalized)
            if end_sample > plan_cue["deadlineFrame"] * SAMPLES_PER_FRAME:
                raise NeedsSol(
                    f"Cue {plan_cue['id']!r} exceeds its deadline after decoding; the source must not be cut."
                )
            if end_sample >= MAX_VOICE_END_SAMPLE:
                raise NeedsSol(
                    f"Cue {plan_cue['id']!r} ends at or after 179.8 seconds; root must revise its timing."
                )
            if start_sample < FIRST_VOICE_SAMPLE and end_sample > QUIET_AFTER_NOISE_START:
                fail(
                    f"Voice cue {plan_cue['id']!r} overlaps the 0.5 second quiet after the overload noise."
                )

            for offset, sample in enumerate(normalized):
                voice[start_sample + offset] += sample / 32768.0

            aligned_path = aligned_dir / f"{plan_cue['id']}.wav"
            write_wav(aligned_path, 1, len(normalized), (normalized,))
            duration_seconds = len(normalized) / SAMPLE_RATE
            gain_db = 20.0 * math.log10(gain)
            sidecar = {
                "id": plan_cue["id"],
                "file": f"public/audio-voiced-v2/aligned/{plan_cue['id']}.wav",
                "sampleRate": SAMPLE_RATE,
                "channels": 1,
                "bitsPerSample": 16,
                "originalDurationSeconds": cue["originalDurationSeconds"],
                "actualDurationSeconds": duration_seconds,
                "atempo": tempo,
                "gain": gain,
                "gainDb": gain_db,
                "nonsilentRmsBeforeGainDbfs": 20.0 * math.log10(nonsilent_rms),
                "samplePeakBeforeGain": input_peak,
                "sha256": sha256_file(aligned_path),
            }
            sidecar_path = aligned_dir / f"{plan_cue['id']}.json"
            sidecar_path.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            result = {
                "id": plan_cue["id"],
                "file": plan_cue["file"],
                "alignedFile": sidecar["file"],
                "sourceSha256": cue["sourceSha256"],
                "alignedSha256": sidecar["sha256"],
                "originalDurationSeconds": cue["originalDurationSeconds"],
                "actualDurationSeconds": duration_seconds,
                "startFrame": plan_cue["startFrame"],
                "endFrame": plan_cue["startFrame"] + math.ceil(len(normalized) / SAMPLES_PER_FRAME),
                "deadlineFrame": plan_cue["deadlineFrame"],
                "startSample": start_sample,
                "endSample": end_sample,
                "atempo": tempo,
                "gain": gain,
                "gainDb": gain_db,
                "nonsilentRmsBeforeGainDbfs": 20.0 * math.log10(nonsilent_rms),
                "sidecar": f"public/audio-voiced-v2/aligned/{plan_cue['id']}.json",
            }
            cue_results.append({
                **result,
                "startSample": start_sample,
                "endSample": end_sample,
            })
            manifest_cues.append(result)

        if max(abs(sample) for sample in voice) > 1.0:
            raise NeedsSol("Overlapping narration cues would clip the narration stem; root must revise gains.")
        if max(cue["endSample"] for cue in cue_results) >= MAX_VOICE_END_SAMPLE:
            raise NeedsSol("Narration ends at or after 179.8 seconds; root must revise timing.")

        duck = build_duck_envelope(cue_results)
        outputs = create_outputs(temp_dir, voice, duck, overload, order, atmosphere)
        for name, path in stem_paths.items():
            if sha256_file(path) != stem_hashes[name]:
                fail(f"Source stem {name}.wav changed while the mix was being built.")

        plan_hash = sha256_file(PLAN_PATH)
        voice_manifest_hash = sha256_file(VOICE_MANIFEST_PATH)
        mix_manifest = {
            "edition": "EP02 voiced-v2 offline PCM mix",
            "format": {
                "sampleRate": SAMPLE_RATE,
                "channels": CHANNELS,
                "bitsPerSample": 16,
                "fps": FPS,
                "durationFrames": TOTAL_FRAMES,
                "sampleFrames": TOTAL_SAMPLES,
                "durationSeconds": TOTAL_FRAMES / FPS,
            },
            "inputs": {
                "voicePlan": {
                    "path": PLAN_PATH.relative_to(root).as_posix(),
                    "sha256": plan_hash,
                },
                "voiceManifest": {
                    "path": VOICE_MANIFEST_PATH.relative_to(root).as_posix(),
                    "sha256": voice_manifest_hash,
                },
                "sourceStems": {
                    name: {
                        "path": path.relative_to(root).as_posix(),
                        "sha256": stem_hashes[name],
                    }
                    for name, path in stem_paths.items()
                },
            },
            "normalization": {
                "nonsilentThresholdDbfs": -60,
                "targetNonsilentRmsDbfs": -20,
                "maxGainDb": 6,
                "samplePeakCeilingDbfs": -3,
            },
            "ducking": {
                "tracks": ["order", "atmosphere"],
                "attenuationDb": -7,
                "leadMilliseconds": 150,
                "attackMilliseconds": 90,
                "releaseMilliseconds": 450,
                "envelope": "linear amplitude ramps; overlapping cue envelopes use the lower gain",
            },
            "cues": manifest_cues,
            "outputs": outputs,
            "measurementNote": "Sample peaks are reported; LUFS and true peak were not measured.",
        }
        temp_manifest = temp_dir / "voiced-v2-mix-manifest.json"
        temp_manifest.write_text(json.dumps(mix_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        aligned_final = OUTPUT_DIR / "aligned"
        aligned_final.mkdir(parents=True, exist_ok=True)
        for item in manifest_cues:
            cue_id = item["id"]
            os.replace(aligned_dir / f"{cue_id}.wav", aligned_final / f"{cue_id}.wav")
            os.replace(aligned_dir / f"{cue_id}.json", aligned_final / f"{cue_id}.json")
        os.replace(temp_dir / "narration.wav", OUTPUT_DIR / "narration.wav")
        os.replace(temp_dir / "soundtrack.wav", OUTPUT_DIR / "soundtrack.wav")
        MIX_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temp_manifest, MIX_MANIFEST_PATH)
        print(json.dumps({
            "status": "PASS",
            "narration": str((OUTPUT_DIR / "narration.wav").relative_to(root)),
            "soundtrack": str((OUTPUT_DIR / "soundtrack.wav").relative_to(root)),
            "manifest": str(MIX_MANIFEST_PATH.relative_to(root)),
            "cueCount": len(manifest_cues),
            "soundtrackSamplePeak": outputs["soundtrack"]["samplePeak"],
            "soundtrackSha256": outputs["soundtrack"]["sha256"],
        }, ensure_ascii=False, indent=2))
    finally:
        shutil.rmtree(temp_dir_path, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except NeedsSol as exc:
        print(f"NEEDS_SOL: {exc}", file=sys.stderr)
        sys.exit(2)
    except MixError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
