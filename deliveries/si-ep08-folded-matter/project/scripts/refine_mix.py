#!/usr/bin/env python3
"""Refine the EP08 local mix without changing narration or any TTS cue."""

from __future__ import annotations

import array
import hashlib
import json
import math
import shutil
import subprocess
import sys
import wave
from pathlib import Path
from typing import Any


PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT.parent
AUDIO = PROJECT / "public" / "audio"
TIMING_PATH = PROJECT / "audio-timing.json"
PROVIDER_MANIFEST_PATH = AUDIO / "provider-manifest.json"
MIX_MANIFEST_PATH = AUDIO / "mix-manifest.json"
MIX_SETTINGS_PATH = AUDIO / "mix-settings.json"
REFINEMENT_PATH = AUDIO / "mix-refinement.json"
V1_DIR = AUDIO / "mix-v01"

FPS = 60
SAMPLE_RATE = 48_000
SAMPLES_PER_FRAME = 800
DURATION_SECONDS = 120
TOTAL_SAMPLES = 5_760_000
SILENCE_START_SAMPLE = 4_704_000
SILENCE_END_SAMPLE = 4_728_000
DUCK_GAIN = 10.0 ** (-6.0 / 20.0)
PREATTACK_SAMPLES = round(0.060 * SAMPLE_RATE)
RELEASE_SAMPLES = round(0.350 * SAMPLE_RATE)
SCORE_FADE_IN_SAMPLES = round(0.050 * SAMPLE_RATE)
SCORE_FADE_OUT_START = round(118.5 * SAMPLE_RATE)
SFX_EQ = "equalizer=f=1400:t=q:w=0.7:g=-9,equalizer=f=2800:t=q:w=0.7:g=-9"

EXPECTED_OUTPUTS = ("narration", "score", "sfx", "master")
V1_FILES = (
    "narration.wav", "score.wav", "sfx.wav", "master.wav",
    "mix-settings.json", "mix-manifest.json", "provider-manifest.json",
)


class RefinementError(RuntimeError):
    pass


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha_bytes(encoded)


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RefinementError(f"cannot read {label}: {exc}") from None
    if not isinstance(value, dict):
        raise RefinementError(f"{label} must contain a JSON object")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def current_hashes() -> dict[str, str]:
    return {name: sha_file(AUDIO / f"{name}.wav") for name in EXPECTED_OUTPUTS}


def verify_wav(path: Path) -> dict[str, Any]:
    try:
        with wave.open(str(path), "rb") as wav:
            params = wav.getparams()
            expected = (SAMPLE_RATE, 2, 2, TOTAL_SAMPLES, "NONE")
            actual = (params.framerate, params.nchannels, params.sampwidth, params.nframes, params.comptype)
            if actual != expected:
                raise RefinementError(f"{path.name} must be 48 kHz stereo PCM16 with {TOTAL_SAMPLES} samples/channel; got {actual}")
            raw = wav.readframes(params.nframes)
    except (OSError, wave.Error) as exc:
        raise RefinementError(f"cannot read WAV {path}: {exc}") from None
    if len(raw) != TOTAL_SAMPLES * 4:
        raise RefinementError(f"{path.name} has an incomplete PCM payload")
    return {
        "file": str(path.relative_to(WORK)),
        "sha256": sha_file(path),
        "pcmSha256": sha_bytes(raw),
        "sampleRate": SAMPLE_RATE,
        "channels": 2,
        "sampleWidthBytes": 2,
        "samplesPerChannel": TOTAL_SAMPLES,
        "durationSeconds": 120.0,
    }


def verify_pause(path: Path) -> int:
    with wave.open(str(path), "rb") as wav:
        wav.setpos(SILENCE_START_SAMPLE)
        raw = wav.readframes(SILENCE_END_SAMPLE - SILENCE_START_SAMPLE)
    values = array.array("h")
    values.frombytes(raw)
    peak = max((abs(value) for value in values), default=0)
    if peak:
        raise RefinementError(f"{path.name} is nonzero inside [4,704,000,4,728,000); peak={peak}")
    return peak


def strict_decode(path: Path, label: str) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RefinementError("ffmpeg is required for strict decode validation")
    result = subprocess.run(
        [ffmpeg, "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
    )
    if result.returncode:
        details = " | ".join((result.stderr or "").strip().splitlines()[-5:])
        raise RefinementError(f"strict decode of {label} failed (exit {result.returncode}): {details}")


def verify_cues_and_manifest() -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    manifest = read_json(MIX_MANIFEST_PATH, "mix-manifest.json")
    provider = read_json(PROVIDER_MANIFEST_PATH, "provider-manifest.json")
    if manifest.get("status") != "built" or not isinstance(manifest.get("outputs"), dict):
        raise RefinementError("canonical mix manifest is not in a built state")
    if not isinstance(provider.get("segments"), dict) or len(provider["segments"]) != 10:
        raise RefinementError("provider manifest must contain exactly ten verified TTS cues")
    for name in EXPECTED_OUTPUTS:
        path = AUDIO / f"{name}.wav"
        expected = manifest["outputs"].get(name, {}).get("sha256")
        if not path.is_file() or not expected or sha_file(path) != expected:
            raise RefinementError(f"NEEDS_SOL: canonical {name}.wav changed from its current mix manifest")
        verify_wav(path)
    cue_hashes = {}
    for sid, entry in sorted(provider["segments"].items()):
        cue_path = (PROJECT / entry.get("cue_path", "")).resolve()
        if not cue_path.is_relative_to(PROJECT.resolve()) or not cue_path.is_file():
            raise RefinementError(f"NEEDS_SOL: {sid} cue is missing or escapes the project")
        actual = sha_file(cue_path)
        if actual != entry.get("cue_sha256"):
            raise RefinementError(f"NEEDS_SOL: {sid} TTS cue changed from its provider manifest")
        cue_hashes[sid] = actual
    timing = read_json(TIMING_PATH, "audio-timing.json")
    if (timing.get("status"), timing.get("fps"), timing.get("sampleRate"), timing.get("samplesPerChannel")) != (
        "measured_pcm_with_estimated_phrase_timing", FPS, SAMPLE_RATE, TOTAL_SAMPLES,
    ):
        raise RefinementError("audio-timing.json is not the measured 120s/48kHz timeline")
    segments = timing.get("segments")
    if not isinstance(segments, list) or [item.get("id") for item in segments] != [f"S{i:02d}" for i in range(1, 11)]:
        raise RefinementError("audio-timing.json must contain S01 through S10 in order")
    if (timing.get("absoluteSilence", {}).get("startSample"), timing.get("absoluteSilence", {}).get("endSampleExclusive")) != (SILENCE_START_SAMPLE, SILENCE_END_SAMPLE):
        raise RefinementError("audio-timing.json absolute silence does not match [4,704,000,4,728,000)")
    for item in segments:
        if item["voiceStartSample"] < 0 or item["voiceStartSample"] >= item["voiceEndSampleExclusive"] or item["voiceEndSampleExclusive"] > TOTAL_SAMPLES:
            raise RefinementError(f"{item['id']} has invalid measured voice bounds")
        if item["voiceStartSample"] < SILENCE_END_SAMPLE and item["voiceEndSampleExclusive"] > SILENCE_START_SAMPLE:
            raise RefinementError(f"NEEDS_SOL: {item['id']} voice crosses the authored silence interval")
    return manifest, provider, cue_hashes


def preserve_v1() -> dict[str, str]:
    expected = {}
    for name in V1_FILES:
        source = AUDIO / name
        if not source.is_file():
            raise RefinementError(f"cannot preserve v1: missing canonical {name}")
        expected[name] = sha_file(source)
    V1_DIR.mkdir(parents=True, exist_ok=True)
    for name, digest in expected.items():
        target = V1_DIR / name
        if target.exists():
            if sha_file(target) != digest:
                raise RefinementError(f"NEEDS_SOL: existing mix-v01/{name} differs from current canonical v1; preserved")
        else:
            shutil.copyfile(AUDIO / name, target)
        if sha_file(target) != digest:
            raise RefinementError(f"mix-v01 copy verification failed for {name}")
    return expected


def smoothstep(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def voice_windows(timing: dict[str, Any]) -> list[tuple[int, int, int, int]]:
    result = []
    for item in timing["segments"]:
        start = int(item["voiceStartSample"])
        end = int(item["voiceEndSampleExclusive"])
        result.append((max(0, start - PREATTACK_SAMPLES), start, end, min(TOTAL_SAMPLES, end + RELEASE_SAMPLES)))
    result.sort(key=lambda row: row[1])
    return result


def envelope_at(sample: int, windows: list[tuple[int, int, int, int]], current: int) -> tuple[float, int]:
    while current < len(windows) and sample >= windows[current][3]:
        current += 1
    gain = 1.0
    index = current
    while index < len(windows) and windows[index][0] <= sample:
        pre, start, end, post = windows[index]
        if sample < start:
            value = 1.0 + (DUCK_GAIN - 1.0) * smoothstep((sample - pre) / max(1, start - pre))
        elif sample < end:
            value = DUCK_GAIN
        elif sample < post:
            value = DUCK_GAIN + (1.0 - DUCK_GAIN) * smoothstep((sample - end) / max(1, post - end))
        else:
            value = 1.0
        gain = min(gain, value)
        index += 1
    return gain, current


def render_refined_score(source: Path, target: Path, timing: dict[str, Any]) -> dict[str, Any]:
    windows = voice_windows(timing)
    fade_out_samples = TOTAL_SAMPLES - SCORE_FADE_OUT_START
    temp = target.with_name(target.stem + ".tmp.wav")
    current_window = 0
    try:
        with wave.open(str(source), "rb") as src, wave.open(str(temp), "wb") as dst:
            params = src.getparams()
            if (params.framerate, params.nchannels, params.sampwidth, params.nframes, params.comptype) != (SAMPLE_RATE, 2, 2, TOTAL_SAMPLES, "NONE"):
                raise RefinementError("source score.wav changed format or duration after preflight")
            dst.setnchannels(2)
            dst.setsampwidth(2)
            dst.setframerate(SAMPLE_RATE)
            block_start = 0
            while block_start < TOTAL_SAMPLES:
                count = min(24_000, TOTAL_SAMPLES - block_start)
                raw = src.readframes(count)
                values = array.array("h")
                values.frombytes(raw)
                if len(values) != count * 2:
                    raise RefinementError("source score ended before 120 seconds")
                output = array.array("h")
                output.extend(values)
                for offset in range(count):
                    sample = block_start + offset
                    duck, current_window = envelope_at(sample, windows, current_window)
                    fade_in = smoothstep(sample / max(1, SCORE_FADE_IN_SAMPLES)) if sample < SCORE_FADE_IN_SAMPLES else 1.0
                    if sample >= SCORE_FADE_OUT_START:
                        fade_out = 1.0 - smoothstep((sample - SCORE_FADE_OUT_START) / max(1, fade_out_samples - 1))
                    else:
                        fade_out = 1.0
                    gain = duck * fade_in * fade_out
                    output[2 * offset] = max(-32768, min(32767, round(output[2 * offset] * gain)))
                    output[2 * offset + 1] = max(-32768, min(32767, round(output[2 * offset + 1] * gain)))
                # The last stereo frame is a deliberate exact zero endpoint.
                if block_start + count == TOTAL_SAMPLES:
                    output[-2] = 0
                    output[-1] = 0
                if sys.byteorder != "little":
                    output.byteswap()
                dst.writeframesraw(output.tobytes())
                block_start += count
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)
    info = verify_wav(target)
    info["design"] = {
        "sourceScoreSha256": sha_file(source),
        "duckGainDb": -6.0,
        "duckGainLinear": DUCK_GAIN,
        "voiceSpanCount": len(windows),
        "voiceTimingSource": "project/audio-timing.json measured voiceStartSample/voiceEndSampleExclusive",
        "preattackMilliseconds": 60,
        "releaseMilliseconds": 350,
        "envelope": "smoothstep; -6 dB over active measured speech span",
        "scoreFadeInMilliseconds": 50,
        "scoreFadeOut": {"startSeconds": 118.5, "endSeconds": 120.0, "lastFrameExactZero": True},
    }
    return info


def render_eq_sfx(source: Path, target: Path) -> dict[str, Any]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RefinementError("ffmpeg is required for the requested SFX-only equalization")
    result = subprocess.run([
        ffmpeg, "-hide_banner", "-nostats", "-y", "-i", str(source), "-map", "0:a:0", "-vn",
        "-af", SFX_EQ, "-ar", str(SAMPLE_RATE), "-ac", "2", "-c:a", "pcm_s16le", str(target),
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if result.returncode:
        detail = " | ".join((result.stderr or "").strip().splitlines()[-6:])
        raise RefinementError(f"SFX equalizer failed (exit {result.returncode}): {detail}")
    info = verify_wav(target)
    info["design"] = {
        "sourceSfxSha256": sha_file(source),
        "filter": SFX_EQ,
        "frequencyReductions": [
            {"frequencyHz": 1400, "widthType": "q", "q": 0.7, "gainDb": -9},
            {"frequencyHz": 2800, "widthType": "q", "q": 0.7, "gainDb": -9},
        ],
        "sampleTimeline": "same sample rate and sample count; no delay, trim, or resampling",
    }
    return info


def apply_endpoint_fade(path: Path) -> dict[str, Any]:
    temporary = path.with_name(path.stem + ".endpoint.tmp.wav")
    fade_samples = TOTAL_SAMPLES - SCORE_FADE_OUT_START
    try:
        with wave.open(str(path), "rb") as src, wave.open(str(temporary), "wb") as dst:
            params = src.getparams()
            if (params.framerate, params.nchannels, params.sampwidth, params.nframes, params.comptype) != (SAMPLE_RATE, 2, 2, TOTAL_SAMPLES, "NONE"):
                raise RefinementError("normalized master has unexpected format or duration before endpoint fade")
            dst.setnchannels(2)
            dst.setsampwidth(2)
            dst.setframerate(SAMPLE_RATE)
            block_start = 0
            while block_start < TOTAL_SAMPLES:
                count = min(24_000, TOTAL_SAMPLES - block_start)
                raw = src.readframes(count)
                values = array.array("h")
                values.frombytes(raw)
                if len(values) != count * 2:
                    raise RefinementError("normalized master ended before 120 seconds")
                for offset in range(count):
                    sample = block_start + offset
                    if sample >= SCORE_FADE_OUT_START:
                        fade = 1.0 - smoothstep((sample - SCORE_FADE_OUT_START) / max(1, fade_samples - 1))
                        values[2 * offset] = round(values[2 * offset] * fade)
                        values[2 * offset + 1] = round(values[2 * offset + 1] * fade)
                if block_start + count == TOTAL_SAMPLES:
                    values[-2] = values[-1] = 0
                if sys.byteorder != "little":
                    values.byteswap()
                dst.writeframesraw(values.tobytes())
                block_start += count
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return verify_wav(path)


def final_metrics(path: Path) -> dict[str, Any]:
    import build_audio
    info = verify_wav(path)
    strict_decode(path, "refined master")
    zero_peak = verify_pause(path)
    loudness = build_audio.ebur128(path)
    if not -18.0 <= loudness["integratedLUFS"] <= -16.0:
        raise RefinementError(f"final master loudness {loudness['integratedLUFS']} LUFS is outside [-18,-16]")
    if loudness["truePeakDBTP"] > -1.0:
        raise RefinementError(f"final master true peak {loudness['truePeakDBTP']} dBTP exceeds -1.0 dBTP")
    with wave.open(str(path), "rb") as wav:
        wav.setpos(TOTAL_SAMPLES - 1)
        final = array.array("h")
        final.frombytes(wav.readframes(1))
    endpoint_peak = max((abs(value) for value in final), default=0)
    if endpoint_peak != 0:
        raise RefinementError(f"final master endpoint sample is not exact zero: {endpoint_peak}")
    return {**info, "ebur128Final": loudness, "strictDecode": "passed", "silencePeakPcm16": zero_peak, "endpointPeakPcm16": endpoint_peak}


def verify_completed_refinement() -> bool:
    if not REFINEMENT_PATH.is_file():
        return False
    record = read_json(REFINEMENT_PATH, "mix-refinement.json")
    after = record.get("after", {}).get("sha256", {})
    for name in EXPECTED_OUTPUTS:
        if after.get(name) != sha_file(AUDIO / f"{name}.wav"):
            raise RefinementError(f"NEEDS_SOL: existing refinement record does not match canonical {name}.wav")
    print(json.dumps({"status": "verified_refinement_already_applied", "masterSha256": after["master"], "levels": record.get("after", {}).get("levels")}, ensure_ascii=False))
    return True


def main() -> int:
    sys.path.insert(0, str(PROJECT / "scripts"))
    try:
        import build_audio

        if verify_completed_refinement():
            return 0
        mix_manifest, provider_manifest, cue_hashes = verify_cues_and_manifest()
        before_hashes = current_hashes()
        before_levels = build_audio.ebur128(AUDIO / "master.wav")
        v1_hashes = preserve_v1()
        timing = read_json(TIMING_PATH, "audio-timing.json")
        v1_manifest_hash = sha_file(MIX_MANIFEST_PATH)
        v1_settings_hash = sha_file(MIX_SETTINGS_PATH)
        v1_provider_hash = sha_file(PROVIDER_MANIFEST_PATH)
        # The manifest is checked again after its archived copy is verified.
        if v1_hashes["mix-manifest.json"] != v1_manifest_hash or v1_hashes["mix-settings.json"] != v1_settings_hash or v1_hashes["provider-manifest.json"] != v1_provider_hash:
            raise RefinementError("v1 manifest copies do not match the verified canonical source files")

        score_source = AUDIO / "score.wav"
        sfx_source = AUDIO / "sfx.wav"
        narration = AUDIO / "narration.wav"
        score_temp = AUDIO / "score.refined.tmp.wav"
        sfx_temp = AUDIO / "sfx.eq.tmp.wav"
        master_temp = AUDIO / "master.refined.tmp.wav"
        for path in (score_temp, sfx_temp, master_temp):
            if path.exists():
                raise RefinementError(f"temporary output already exists; preserved: {path.name}")
        try:
            refined_score = render_refined_score(score_source, score_temp, timing)
            refined_sfx = render_eq_sfx(sfx_source, sfx_temp)
            for name, path in (("score", score_temp), ("sfx", sfx_temp)):
                verify_pause(path)
                strict_decode(path, f"refined {name} stem")
            narration_info = verify_wav(narration)
            verify_pause(narration)
            normalized_master = build_audio.mix_master(master_temp, [narration, score_temp, sfx_temp])
            apply_endpoint_fade(master_temp)
            master_info = {**normalized_master, **final_metrics(master_temp)}
            if sha_file(narration) != before_hashes["narration"]:
                raise RefinementError("NEEDS_SOL: narration.wav changed during the refinement")
            for sid, digest in cue_hashes.items():
                entry = provider_manifest["segments"][sid]
                cue_path = (PROJECT / entry["cue_path"]).resolve()
                if sha_file(cue_path) != digest:
                    raise RefinementError(f"NEEDS_SOL: {sid} TTS cue changed during the refinement")
            for path in (score_temp, sfx_temp, master_temp):
                if verify_pause(path) != 0:
                    raise RefinementError(f"{path.name} does not preserve exact silence")

            after_hashes = {
                "narration": narration_info["sha256"],
                "score": refined_score["sha256"],
                "sfx": refined_sfx["sha256"],
                "master": master_info["sha256"],
            }
            if after_hashes["narration"] != before_hashes["narration"]:
                raise RefinementError("narration output hash is not immutable")
            event_onsets = mix_manifest.get("eventOnsets", [])
            for event in event_onsets:
                if event.get("sampleIndex") != event.get("frame") * SAMPLES_PER_FRAME:
                    raise RefinementError(f"SFX event timeline is inconsistent for {event.get('id')}")
            settings = read_json(MIX_SETTINGS_PATH, "mix-settings.json")
            source_hashes = {
                "segmentsJson": sha_file(PROJECT / "segments.json"),
                "providerManifest": v1_provider_hash,
                "audioTiming": sha_file(TIMING_PATH),
                "narrationSha256": narration_info["sha256"],
                "cueWavs": [{"id": sid, "sha256": digest} for sid, digest in sorted(cue_hashes.items())],
                "originalScoreSha256": before_hashes["score"],
                "originalSfxSha256": before_hashes["sfx"],
                "refinementScriptSha256": sha_file(Path(__file__).resolve()),
            }
            refinement_settings = {
                "baseMix": "mix-v01",
                "scoreDucking": refined_score["design"],
                "sfxEqualizer": refined_sfx["design"],
                "masterEndpointFade": {"startSeconds": 118.5, "endSeconds": 120.0, "lastSampleExactZero": True},
                "sourceHashes": source_hashes,
            }
            input_set_hash = canonical_hash({"sourceHashes": source_hashes, "refinement": refinement_settings})

            output_info = {
                "narration": narration_info,
                "score": refined_score,
                "sfx": refined_sfx,
                "master": master_info,
            }
            for name, info in output_info.items():
                info["file"] = str((AUDIO / f"{name}.wav").relative_to(WORK))
            silence_meta = {
                "startFrame": 5880, "endFrameExclusive": 5910,
                "startSample": SILENCE_START_SAMPLE, "endSampleExclusive": SILENCE_END_SAMPLE,
                "samplesZeroInAllStemsAndMaster": True,
            }
            updated_settings = {
                "version": 2,
                "inputSetSha256": input_set_hash,
                "durationSeconds": DURATION_SECONDS,
                "fps": FPS,
                "sampleRate": SAMPLE_RATE,
                "samplesPerFrame": SAMPLES_PER_FRAME,
                "samplesPerChannel": TOTAL_SAMPLES,
                "channels": 2,
                "blockSamples": 24_000,
                "scoreDesign": refined_score["design"],
                "sfxDesign": refined_sfx["design"],
                "sfxOnsets": event_onsets,
                "loudnormTarget": master_info["normalizationTarget"],
                "masterEndpointFade": refinement_settings["masterEndpointFade"],
                "absoluteSilence": silence_meta,
                "sourceHashes": source_hashes,
                "outputs": output_info,
            }
            updated_manifest = {
                "version": 2,
                "status": "built",
                "inputSetSha256": input_set_hash,
                "sourceHashes": source_hashes,
                "outputs": output_info,
                "eventOnsets": event_onsets,
                "absoluteSilence": silence_meta,
                "audioTiming": "project/audio-timing.json",
                "authorization": "project/audio-authorization.json",
                "refinement": refinement_settings,
                "previousMix": {"directory": "project/public/audio/mix-v01", "mixManifestSha256": v1_manifest_hash},
            }
            refinement_record = {
                "version": 1,
                "status": "refined",
                "preservedV1": {"directory": "project/public/audio/mix-v01", "filesSha256": v1_hashes},
                "before": {"sha256": before_hashes, "levels": before_levels},
                "after": {
                    "sha256": after_hashes,
                    "levels": master_info["ebur128Final"],
                    "masterSamplesPerChannel": master_info["samplesPerChannel"],
                    "masterSampleRate": master_info["sampleRate"],
                    "channels": master_info["channels"],
                    "absoluteSilence": {"startSample": SILENCE_START_SAMPLE, "endSampleExclusive": SILENCE_END_SAMPLE, "allStemsExactZero": True},
                    "endpointSamplePeakPcm16": master_info["endpointPeakPcm16"],
                },
                "dsp": refinement_settings,
                "narrationUnchanged": before_hashes["narration"] == after_hashes["narration"],
                "cueCountUnchanged": len(cue_hashes),
                "humanListening": "not performed",
            }

            # Preserve the old narration bytes and atomically replace only the three requested mix outputs.
            score_temp.replace(AUDIO / "score.wav")
            sfx_temp.replace(AUDIO / "sfx.wav")
            master_temp.replace(AUDIO / "master.wav")
            write_json(MIX_SETTINGS_PATH, updated_settings)
            write_json(MIX_MANIFEST_PATH, updated_manifest)
            refinement_record["after"]["canonicalMetadataSha256"] = {
                "mix-settings.json": sha_file(MIX_SETTINGS_PATH),
                "mix-manifest.json": sha_file(MIX_MANIFEST_PATH),
            }
            write_json(REFINEMENT_PATH, refinement_record)

            # Final canonical hashes and sample-level constraints after the renames.
            for name in EXPECTED_OUTPUTS:
                expected = output_info[name]["sha256"]
                if sha_file(AUDIO / f"{name}.wav") != expected:
                    raise RefinementError(f"final canonical {name}.wav differs from its recorded hash")
                verify_pause(AUDIO / f"{name}.wav")
            if sha_file(AUDIO / "narration.wav") != before_hashes["narration"]:
                raise RefinementError("canonical narration hash changed during final replacement")
            print(json.dumps({
                "status": "refinement_complete",
                "masterSha256": after_hashes["master"],
                "integratedLUFS": master_info["ebur128Final"]["integratedLUFS"],
                "truePeakDBTP": master_info["ebur128Final"]["truePeakDBTP"],
                "samplesPerChannel": master_info["samplesPerChannel"],
                "zeroWindow": [SILENCE_START_SAMPLE, SILENCE_END_SAMPLE],
                "endpointSamplePeakPcm16": master_info["endpointPeakPcm16"],
                "narrationUnchanged": True,
                "cueCount": len(cue_hashes),
            }, ensure_ascii=False, indent=2))
            return 0
        finally:
            for path in (score_temp, sfx_temp, master_temp):
                path.unlink(missing_ok=True)
    except (RefinementError, OSError, ValueError, wave.Error, subprocess.SubprocessError, KeyError) as exc:
        print(f"refine_mix.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
