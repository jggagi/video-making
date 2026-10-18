#!/usr/bin/env python3
"""Build EP04 audio from approved local PCM cues and deterministic synthesis.

This tool has no speech-provider path. ``--audit`` reads cue WAVs; ``--mix``
requires them and builds the narration, score, SFX, and normalized master.
"""

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
import wave
from pathlib import Path
from typing import Any


PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT.parent
AUDIO = PROJECT / "public" / "audio"
CUES = AUDIO / "cues"
SEGMENTS_PATH = PROJECT / "segments.json"
EVENTS_PATH = PROJECT / "sfx_events.json"
TIMING_PATH = PROJECT / "audio-timing.json"
SETTINGS_PATH = AUDIO / "mix-settings.json"
MANIFEST_PATH = AUDIO / "mix-manifest.json"

FPS = 60
SAMPLE_RATE = 48_000
SAMPLES_PER_FRAME = 800
DURATION_SECONDS = 120
TOTAL_FRAMES = 7_200
TOTAL_SAMPLES = 5_760_000
BLOCK_SAMPLES = 24_000
SILENCE_START_FRAME = 5_740
SILENCE_END_FRAME = 5_760
SILENCE_START = SILENCE_START_FRAME * SAMPLES_PER_FRAME
SILENCE_END = SILENCE_END_FRAME * SAMPLES_PER_FRAME
FOG_FRAME = 1_260
FOG_SAMPLE = FOG_FRAME * SAMPLES_PER_FRAME

EXPECTED_EVENTS = {
    "compiler_arpeggio": 120,
    "anvil_lock": 960,
    "fog_sub_drop": 1_260,
    "sonar_feedback": 1_920,
    "glitch_rip": 2_880,
    "counter_divergence": 3_900,
    "shepard_mobius": 4_680,
    "physical_veto": 5_760,
    "organ_resolution": 6_500,
    "thermal_hiss": 7_020,
}
EVENT_DURATIONS = {
    "compiler_arpeggio": 2.2,
    "anvil_lock": 2.4,
    "fog_sub_drop": 2.5,
    "sonar_feedback": 3.4,
    "glitch_rip": 2.4,
    "counter_divergence": 3.5,
    "shepard_mobius": 8.0,
    "physical_veto": 4.5,
    "organ_resolution": 5.5,
    "thermal_hiss": 3.2,
}


class AudioBuildError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AudioBuildError(f"cannot read {path.name}: {exc}") from None
    if not isinstance(value, dict):
        raise AudioBuildError(f"{path.name} must contain a JSON object")
    return value


def load_sources() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if not (WORK / "source" / "script.md").is_file():
        raise AudioBuildError("source/script.md is missing")
    segments_data = read_json(SEGMENTS_PATH)
    if (segments_data.get("fps"), segments_data.get("duration_seconds"), segments_data.get("sample_rate")) != (
        FPS, DURATION_SECONDS, SAMPLE_RATE
    ):
        raise AudioBuildError("segments.json must describe 120 seconds at 60 fps and 48 kHz")
    segments = segments_data.get("segments")
    if not isinstance(segments, list) or [item.get("id") for item in segments] != [f"S{i:02d}" for i in range(1, 11)]:
        raise AudioBuildError("segments.json must contain S01 through S10 in order")
    for segment in segments:
        if not all(isinstance(segment.get(field), str) and segment[field].strip() for field in (
            "original_script", "display_subtitle", "tts_phonetic_text"
        )):
            raise AudioBuildError(f"{segment.get('id', 'segment')} needs original, display, and TTS text")
        chunks = segment.get("chunks")
        if not isinstance(chunks, list) or not chunks or any(not isinstance(item, str) or not item for item in chunks):
            raise AudioBuildError(f"{segment['id']} has no valid caption chunks")
        if "".join("".join(chunks).split()) != "".join(segment["display_subtitle"].split()):
            raise AudioBuildError(f"{segment['id']} caption chunks do not preserve display_subtitle")
        if not (0 <= int(segment.get("startFrame", -1)) < int(segment.get("endFrame", -1)) <= TOTAL_FRAMES):
            raise AudioBuildError(f"{segment['id']} has an invalid frame window")

    event_data = read_json(EVENTS_PATH)
    if (event_data.get("fps"), event_data.get("sampleRate"), event_data.get("samplesPerFrame")) != (
        FPS, SAMPLE_RATE, SAMPLES_PER_FRAME
    ):
        raise AudioBuildError("sfx_events.json must use 60 fps, 48 kHz, and 800 samples per frame")
    silence = event_data.get("absoluteSilence", {})
    if (silence.get("startFrame"), silence.get("endFrame")) != (SILENCE_START_FRAME, SILENCE_END_FRAME):
        raise AudioBuildError("sfx_events.json must retain the exact [5740,5760) silence window")
    events = event_data.get("events")
    if not isinstance(events, list):
        raise AudioBuildError("sfx_events.json has no event list")
    event_map = {event.get("id"): event for event in events}
    if set(event_map) != set(EXPECTED_EVENTS):
        raise AudioBuildError("sfx_events.json event IDs differ from the EP04 audio design")
    for event_id, frame in EXPECTED_EVENTS.items():
        event = event_map[event_id]
        if event.get("frame") != frame or event.get("sampleIndex") != frame * SAMPLES_PER_FRAME:
            raise AudioBuildError(f"{event_id} must start at frame {frame} / sample {frame * SAMPLES_PER_FRAME}")
    return segments, events, event_data


def wav_info(path: Path) -> dict[str, Any]:
    try:
        with wave.open(str(path), "rb") as wav:
            params = wav.getparams()
            if (params.framerate, params.nchannels, params.sampwidth, params.comptype) != (
                SAMPLE_RATE, 1, 2, "NONE"
            ):
                raise AudioBuildError(f"{path.name} must be 48 kHz mono PCM16 WAV; got {params}")
            samples = params.nframes
            raw = wav.readframes(samples)
    except (OSError, wave.Error) as exc:
        raise AudioBuildError(f"cannot read PCM cue {path.name}: {exc}") from None
    if samples <= 0 or len(raw) != samples * 2:
        raise AudioBuildError(f"{path.name} has an empty or physically incomplete PCM payload")
    return {
        "path": path,
        "samples": samples,
        "seconds": samples / SAMPLE_RATE,
        "sha256": sha256_file(path),
        "pcmSha256": sha256_bytes(raw),
    }


def read_cue(path: Path) -> tuple[array.array, dict[str, Any]]:
    info = wav_info(path)
    with wave.open(str(path), "rb") as wav:
        raw = wav.readframes(info["samples"])
    values = array.array("h")
    values.frombytes(raw)
    if sys.byteorder != "little":
        values.byteswap()
    if len(values) != info["samples"]:
        raise AudioBuildError(f"{path.name} PCM sample count changed during read")
    return values, info


def cue_paths() -> tuple[list[Path], tuple[Path, Path] | None, list[str]]:
    regular = [CUES / f"S{i:02d}.wav" for i in range(1, 11) if i != 8]
    s08 = CUES / "S08.wav"
    s08a, s08b = CUES / "S08a.wav", CUES / "S08b.wav"
    if s08a.exists() != s08b.exists():
        raise AudioBuildError("S08a.wav and S08b.wav must be supplied together")
    split = (s08a, s08b) if s08a.exists() else None
    required = regular + ([] if split else [s08])
    missing = [str(path.relative_to(WORK)) for path in required if not path.is_file()]
    return required, split, missing


def audit_cues(segments: list[dict[str, Any]]) -> int:
    required, split, missing = cue_paths()
    paths = list(required) + (list(split) if split else [])
    measured: list[dict[str, Any]] = []
    for path in paths:
        if not path.is_file():
            continue
        info = wav_info(path)
        measured.append({
            "file": str(path.relative_to(WORK)),
            "samplesAt48k": info["samples"],
            "seconds": round(info["seconds"], 6),
            "sha256": info["sha256"],
            "pcmSha256": info["pcmSha256"],
        })
    if missing:
        print(json.dumps({
            "status": "pending_cues",
            "cueDirectory": str(CUES.relative_to(WORK)),
            "missing": missing,
            "availableMeasuredCues": [],
            "note": "No provider calls were attempted. Supply local 48 kHz mono PCM16 cue WAVs before --mix.",
        }, ensure_ascii=False, indent=2))
        return 0
    print(json.dumps({
        "status": "cues_measured",
        "segmentCount": len(segments),
        "cueCount": len(paths),
        "cues": measured,
    }, ensure_ascii=False, indent=2))
    return 0


def cjk_count(text: str) -> int:
    return sum("\u3400" <= char <= "\u9fff" for char in text)


def caption_weight(text: str) -> float:
    return max(1.0, cjk_count(text) + 0.55 * sum(char.isascii() and char.isalnum() for char in text))


def caption_groups(segment: dict[str, Any]) -> list[dict[str, Any]]:
    chunks = segment["chunks"]
    for index, chunk in enumerate(chunks):
        if cjk_count(chunk) > 14:
            raise AudioBuildError(f"{segment['id']} caption chunk {index + 1} exceeds 14 Chinese characters")
    display_only_indices = {len(chunks) - 1} if segment["id"] == "S10" else set()
    groups: list[dict[str, Any]] = []
    index = 0
    while index < len(chunks):
        selected = [index]
        if index + 1 < len(chunks) and cjk_count(chunks[index + 1]) <= 14:
            selected.append(index + 1)
        lines = [chunks[item] for item in selected]
        groups.append({
            "text": "\n".join(lines),
            "weight": sum(caption_weight(line) for line in lines),
            "chunkIndices": selected,
            "displayOnlyText": [line for item, line in zip(selected, lines) if item in display_only_indices],
        })
        index += len(selected)
    return groups


def weighted_boundaries(frame_start: int, frame_length: int, groups: list[dict[str, Any]]) -> list[int]:
    if not groups:
        return [frame_start, frame_start + frame_length]
    if frame_length < len(groups):
        raise AudioBuildError("measured PCM is too short to give every caption a non-empty frame window")
    total = sum(group["weight"] for group in groups)
    boundaries = [frame_start]
    cumulative = 0.0
    for group in groups[:-1]:
        cumulative += group["weight"]
        candidate = frame_start + round(frame_length * cumulative / total)
        lower = boundaries[-1] + 1
        upper = frame_start + frame_length - (len(groups) - len(boundaries))
        boundaries.append(max(lower, min(upper, candidate)))
    boundaries.append(frame_start + frame_length)
    return boundaries


def captions_for_span(
    segment: dict[str, Any],
    groups: list[dict[str, Any]],
    start_sample: int,
    sample_count: int,
    first_index: int,
) -> list[dict[str, Any]]:
    if not groups:
        return []
    start_frame = start_sample // SAMPLES_PER_FRAME
    frame_length = max(1, math.ceil(sample_count / SAMPLES_PER_FRAME))
    boundaries = weighted_boundaries(start_frame, frame_length, groups)
    captions: list[dict[str, Any]] = []
    for offset, group in enumerate(groups):
        caption = {
            "id": f"{segment['id']}-C{first_index + offset:02d}",
            "segmentId": segment["id"],
            "startFrame": boundaries[offset],
            "endFrame": boundaries[offset + 1],
            "text": group["text"],
            "sourceChunkIndices": group["chunkIndices"],
            "displayOnlyText": group["displayOnlyText"],
            "alignment": "estimated phrase timing from measured cue samples; not word aligned",
        }
        if group["displayOnlyText"]:
            caption["displayHoldUntilFrame"] = TOTAL_FRAMES
            caption["displayOnlyNote"] = "The EP05 bracket is visual text and is absent from TTS input."
        captions.append(caption)
    return captions


def low_energy_split_ok(cue: array.array, target: int) -> tuple[bool, dict[str, Any]]:
    margin = SAMPLE_RATE // 10
    start, end = target - margin, target + margin
    if start < 0 or end > len(cue):
        return False, {"targetSampleInCue": target, "quietWindowSamples": 2 * margin, "reason": "split lacks 100 ms on both sides"}
    block = cue[start:end]
    peak = max((abs(value) for value in block), default=0)
    rms = math.sqrt(sum(value * value for value in block) / max(1, len(block)))
    return peak <= 512 and rms <= 160.0, {
        "targetSampleInCue": target,
        "quietWindowStartSample": start,
        "quietWindowEndSampleExclusive": end,
        "quietWindowSamples": len(block),
        "peakPcm16": peak,
        "rmsPcm16": round(rms, 3),
        "criterion": "100 ms on each side, peak <=512 and RMS <=160",
    }


def silence_peak(path: Path) -> int:
    try:
        with wave.open(str(path), "rb") as wav:
            params = wav.getparams()
            if (params.framerate, params.nchannels, params.sampwidth, params.nframes) != (
                SAMPLE_RATE, 2, 2, TOTAL_SAMPLES
            ):
                raise AudioBuildError(f"{path.name} is not exact 48 kHz stereo PCM16 master length")
            wav.setpos(SILENCE_START)
            raw = wav.readframes(SILENCE_END - SILENCE_START)
    except (OSError, wave.Error) as exc:
        raise AudioBuildError(f"cannot inspect silence in {path.name}: {exc}") from None
    values = array.array("h")
    values.frombytes(raw)
    if sys.byteorder != "little":
        values.byteswap()
    if len(values) != (SILENCE_END - SILENCE_START) * 2:
        raise AudioBuildError(f"{path.name} silence window has a short PCM payload")
    return max((abs(value) for value in values), default=0)


def write_stereo_from_spans(spans: list[dict[str, Any]], path: Path) -> dict[str, Any]:
    spans.sort(key=lambda item: item["startSample"])
    for previous, current in zip(spans, spans[1:]):
        if previous["startSample"] + previous["sampleCount"] > current["startSample"]:
            raise AudioBuildError(f"narration spans overlap: {previous['segmentId']} and {current['segmentId']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        span_index = 0
        for block_start in range(0, TOTAL_SAMPLES, BLOCK_SAMPLES):
            count = min(BLOCK_SAMPLES, TOTAL_SAMPLES - block_start)
            mono = array.array("h", [0]) * count
            block_end = block_start + count
            while span_index < len(spans) and spans[span_index]["startSample"] + spans[span_index]["sampleCount"] <= block_start:
                span_index += 1
            cursor = span_index
            while cursor < len(spans) and spans[cursor]["startSample"] < block_end:
                span = spans[cursor]
                overlap_start = max(block_start, span["startSample"])
                overlap_end = min(block_end, span["startSample"] + span["sampleCount"])
                if overlap_end > overlap_start:
                    source_start = span["cueOffset"] + overlap_start - span["startSample"]
                    target_start = overlap_start - block_start
                    length = overlap_end - overlap_start
                    mono[target_start:target_start + length] = span["cue"][source_start:source_start + length]
                cursor += 1
            stereo = array.array("h")
            stereo.extend([0] * (count * 2))
            stereo[0::2] = mono
            stereo[1::2] = mono
            if sys.byteorder != "little":
                stereo.byteswap()
            wav.writeframesraw(stereo.tobytes())
    return validate_stem(path)


def validate_stem(path: Path) -> dict[str, Any]:
    with wave.open(str(path), "rb") as wav:
        params = wav.getparams()
        actual = (params.framerate, params.nchannels, params.sampwidth, params.nframes, params.comptype)
    expected = (SAMPLE_RATE, 2, 2, TOTAL_SAMPLES, "NONE")
    if actual != expected:
        raise AudioBuildError(f"{path.name} must be 48 kHz stereo PCM16 with {TOTAL_SAMPLES} samples/ch; got {actual}")
    return {
        "file": str(path.relative_to(WORK)),
        "sha256": sha256_file(path),
        "sampleRate": SAMPLE_RATE,
        "channels": 2,
        "sampleWidthBytes": 2,
        "samplesPerChannel": TOTAL_SAMPLES,
        "durationSeconds": TOTAL_SAMPLES / SAMPLE_RATE,
    }


def make_narration(segments: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    timing_segments: list[dict[str, Any]] = []
    captions: list[dict[str, Any]] = []
    previous_end_sample = 0
    for segment in segments:
        segment_id = segment["id"]
        segment_start = int(segment["startFrame"])
        segment_end = int(segment["endFrame"])
        cue_path = CUES / f"{segment_id}.wav"
        part_meta: list[dict[str, Any]] = []
        split_meta = None
        if segment_id == "S08" and (CUES / "S08a.wav").is_file() and (CUES / "S08b.wav").is_file():
            cue_a, info_a = read_cue(CUES / "S08a.wav")
            cue_b, info_b = read_cue(CUES / "S08b.wav")
            groups = caption_groups(segment)
            if len(groups) != 2:
                raise AudioBuildError("NEEDS_SOL: S08a/b schedule expects the two clause caption groups")
            first_delay_capacity = (SILENCE_START - segment_start * SAMPLES_PER_FRAME - len(cue_a)) // SAMPLES_PER_FRAME
            first_delay_frames = max(0, min(12, first_delay_capacity))
            first_start_frame = segment_start + first_delay_frames
            first_start_sample = first_start_frame * SAMPLES_PER_FRAME
            first_end_sample = first_start_sample + len(cue_a)
            second_start_sample = SILENCE_END
            second_end_sample = second_start_sample + len(cue_b)
            if first_end_sample > SILENCE_START:
                raise AudioBuildError(
                    f"NEEDS_SOL: S08a measured {len(cue_a)} samples; maximum before frame 5740 is "
                    f"{SILENCE_START - first_start_sample}; no speech was sped up or truncated"
                )
            if second_end_sample > segment_end * SAMPLES_PER_FRAME:
                raise AudioBuildError(
                    f"NEEDS_SOL: S08b measured {len(cue_b)} samples; maximum after frame 5760 is "
                    f"{segment_end * SAMPLES_PER_FRAME - second_start_sample}; no speech was sped up or truncated"
                )
            if first_start_sample < previous_end_sample:
                raise AudioBuildError("S08a overlaps the preceding narration segment")
            spans.extend([
                {"startSample": first_start_sample, "sampleCount": len(cue_a), "cueOffset": 0, "cue": cue_a, "segmentId": "S08a"},
                {"startSample": second_start_sample, "sampleCount": len(cue_b), "cueOffset": 0, "cue": cue_b, "segmentId": "S08b"},
            ])
            captions.extend(captions_for_span(segment, [groups[0]], first_start_sample, len(cue_a), 1))
            captions.extend(captions_for_span(segment, [groups[1]], second_start_sample, len(cue_b), 2))
            previous_end_sample = second_end_sample
            part_meta = [
                {"file": str((CUES / "S08a.wav").relative_to(WORK)), "samplesAt48k": len(cue_a), "sha256": info_a["sha256"]},
                {"file": str((CUES / "S08b.wav").relative_to(WORK)), "samplesAt48k": len(cue_b), "sha256": info_b["sha256"]},
            ]
            start_frame = first_start_frame
            end_sample = second_end_sample
            raw_samples = len(cue_a) + len(cue_b)
            scheduled_samples = raw_samples + (SILENCE_START - first_end_sample) + (second_start_sample - SILENCE_START)
            split_meta = {
                "mode": "root-supplied-two-clause-cues",
                "resumeAtSample": SILENCE_END,
                "spokenSamplesPreserved": raw_samples,
            }
        else:
            if not cue_path.is_file():
                raise AudioBuildError(f"missing cue {cue_path.relative_to(WORK)}")
            cue, cue_info = read_cue(cue_path)
            raw_samples = len(cue)
            preferred_delay = 12
            if segment_id in {"S01", "S03"}:
                delay_frames = preferred_delay
            else:
                insertion = (SILENCE_END - SILENCE_START) if segment_id == "S08" else 0
                available_frames = (segment_end * SAMPLES_PER_FRAME - segment_start * SAMPLES_PER_FRAME - len(cue) - insertion) // SAMPLES_PER_FRAME
                delay_frames = max(0, min(preferred_delay, available_frames))
            if segment_id == "S10" and (segment_end * SAMPLES_PER_FRAME - (segment_start + delay_frames) * SAMPLES_PER_FRAME) < len(cue):
                delay_frames = 0
            start_frame = segment_start + delay_frames
            start_sample = start_frame * SAMPLES_PER_FRAME
            end_sample = start_sample + len(cue)
            if end_sample > segment_end * SAMPLES_PER_FRAME:
                available = segment_end * SAMPLES_PER_FRAME - start_sample
                raise AudioBuildError(
                    f"NEEDS_SOL: {segment_id} measured {len(cue)} samples, but its window allows {available}; "
                    "no speech was sped up or truncated"
                )
            if start_sample < previous_end_sample:
                raise AudioBuildError(f"{segment_id} overlaps the previous measured narration cue")
            if segment_id == "S08":
                target = SILENCE_START - start_sample
                feasible, quiet_info = low_energy_split_ok(cue, target)
                if not feasible:
                    raise AudioBuildError(
                        f"NEEDS_SOL: S08 measured {len(cue)} samples; no natural low-energy split at "
                        f"the frame-5740 silence anchor ({quiet_info}); provide S08a.wav/S08b.wav if needed"
                    )
                prefix_count = target
                suffix_count = len(cue) - target
                resume_sample = SILENCE_END
                resumed_end = resume_sample + suffix_count
                if target <= 0 or resumed_end > segment_end * SAMPLES_PER_FRAME:
                    raise AudioBuildError(
                        f"NEEDS_SOL: S08 measured {len(cue)} samples and cannot fit around the silence window; "
                        f"resumed end sample would be {resumed_end}, limit {segment_end * SAMPLES_PER_FRAME}"
                    )
                spans.extend([
                    {"startSample": start_sample, "sampleCount": prefix_count, "cueOffset": 0, "cue": cue, "segmentId": segment_id},
                    {"startSample": resume_sample, "sampleCount": suffix_count, "cueOffset": target, "cue": cue, "segmentId": segment_id},
                ])
                groups = caption_groups(segment)
                if len(groups) < 2:
                    raise AudioBuildError("NEEDS_SOL: S08 needs two phrase groups around its silence split")
                ratio = target / max(1, len(cue))
                candidates = range(1, len(groups))
                split_count = min(candidates, key=lambda n: abs(sum(g["weight"] for g in groups[:n]) / sum(g["weight"] for g in groups) - ratio))
                captions.extend(captions_for_span(segment, groups[:split_count], start_sample, prefix_count, 1))
                captions.extend(captions_for_span(segment, groups[split_count:], resume_sample, suffix_count, split_count + 1))
                end_sample = resumed_end
                scheduled_samples = len(cue) + (SILENCE_END - SILENCE_START)
                split_meta = {
                    "mode": "natural-low-energy-split",
                    "splitAtSample": SILENCE_START,
                    "resumeAtSample": SILENCE_END,
                    "cueSplitSample": target,
                    "quietWindow": quiet_info,
                    "spokenSamplesPreserved": len(cue),
                    "insertedSilenceSamples": SILENCE_END - SILENCE_START,
                }
            else:
                spans.append({"startSample": start_sample, "sampleCount": len(cue), "cueOffset": 0, "cue": cue, "segmentId": segment_id})
                end_sample = start_sample + len(cue)
                scheduled_samples = len(cue)
                captions.extend(captions_for_span(segment, caption_groups(segment), start_sample, len(cue), 1))
            previous_end_sample = end_sample
            part_meta = [{
                "file": str(cue_path.relative_to(WORK)),
                "samplesAt48k": len(cue),
                "sha256": cue_info["sha256"],
                "pcmSha256": cue_info["pcmSha256"],
            }]

        if end_sample > TOTAL_SAMPLES:
            raise AudioBuildError(f"{segment_id} extends past the 120-second master")
        if segment_id == "S08" and split_meta and split_meta["mode"] == "root-supplied-two-clause-cues":
            actual_start_frame = first_start_frame
        else:
            actual_start_frame = start_frame
        timing_segments.append({
            "id": segment_id,
            "declaredStartFrame": segment_start,
            "declaredEndFrame": segment_end,
            "startFrame": actual_start_frame,
            "endFrame": math.ceil(end_sample / SAMPLES_PER_FRAME),
            "voiceStartSample": actual_start_frame * SAMPLES_PER_FRAME,
            "voiceEndSampleExclusive": end_sample,
            "samplesAt48k": raw_samples,
            "scheduledSamples": scheduled_samples,
            "cueParts": part_meta,
            "delayFrames": actual_start_frame - segment_start,
            "split": split_meta,
        })

    narration_path = AUDIO / "narration.wav"
    stem = write_stereo_from_spans(spans, narration_path)
    if silence_peak(narration_path) != 0:
        raise AudioBuildError("narration stem is not exactly zero in samples [4592000,4608000)")
    timing = {
        "durationSeconds": DURATION_SECONDS,
        "fps": FPS,
        "sampleRate": SAMPLE_RATE,
        "samplesPerFrame": SAMPLES_PER_FRAME,
        "samplesPerChannel": TOTAL_SAMPLES,
        "segments": timing_segments,
        "captions": sorted(captions, key=lambda item: (item["startFrame"], item["id"])),
        "captionTimingMethod": "Measured cue PCM sample counts are divided among supplied phrase chunks by text-length estimates; phrase timing is estimated and not word aligned.",
        "absoluteSilence": {
            "startFrame": SILENCE_START_FRAME,
            "endFrameExclusive": SILENCE_END_FRAME,
            "startSample": SILENCE_START,
            "endSampleExclusive": SILENCE_END,
            "exactlyZero": True,
        },
    }
    return stem, timing


def load_numpy() -> Any | None:
    try:
        import numpy as np
        return np
    except ImportError:
        return None


def score_block(start: int, count: int, np: Any | None) -> tuple[Any, Any]:
    roots = (55.0, 65.406, 73.416, 82.407)
    if np is not None:
        indices = np.arange(start, start + count, dtype=np.float64)
        t = indices / SAMPLE_RATE
        chord_index = (np.floor(t / 12.0).astype(np.int64) + np.floor(t / 31.0).astype(np.int64)) % len(roots)
        root = np.asarray(roots)[chord_index]
        pulse_rate = np.where(indices < 1_800 * SAMPLES_PER_FRAME, 0.035, np.where(indices < 3_600 * SAMPLES_PER_FRAME, 0.075, 0.11))
        pulse = 0.72 + 0.28 * np.sin(2 * np.pi * pulse_rate * t + 0.4 * np.sin(2 * np.pi * t / 18.0))
        pad = (
            0.050 * np.sin(2 * np.pi * root * t)
            + 0.030 * np.sin(2 * np.pi * root * 1.5 * t + 0.3)
            + 0.021 * np.sin(2 * np.pi * root * 1.78 * t + 0.8)
            + 0.014 * np.sin(2 * np.pi * root * 2.0 * t + 0.2)
        )
        air = np.where(indices < FOG_SAMPLE, 0.010 * np.sin(2 * np.pi * 1318.51 * t + 0.6), 0.0)
        tension = np.where(indices >= 3_600 * SAMPLES_PER_FRAME, 0.009 * np.sin(2 * np.pi * (196.0 + 2.0 * np.sin(2 * np.pi * t / 7.0)) * t), 0.0)
        resolve = np.where(indices >= 5_400 * SAMPLES_PER_FRAME, 0.012 * np.sin(2 * np.pi * 110.0 * t + 0.2), 0.0)
        base = (pad + air + tension + resolve) * pulse
        left = base * (0.94 + 0.06 * np.sin(2 * np.pi * t / 17.0))
        right = base * (0.88 + 0.12 * np.sin(2 * np.pi * t / 21.0 + 0.7))
        return left, right

    left: list[float] = []
    right: list[float] = []
    for sample in range(start, start + count):
        t = sample / SAMPLE_RATE
        chord_index = (int(t // 12.0) + int(t // 31.0)) % len(roots)
        root = roots[chord_index]
        pulse_rate = 0.035 if sample < 1_800 * SAMPLES_PER_FRAME else 0.075 if sample < 3_600 * SAMPLES_PER_FRAME else 0.11
        pulse = 0.72 + 0.28 * math.sin(2 * math.pi * pulse_rate * t + 0.4 * math.sin(2 * math.pi * t / 18.0))
        pad = (0.050 * math.sin(2 * math.pi * root * t) + 0.030 * math.sin(2 * math.pi * root * 1.5 * t + 0.3)
               + 0.021 * math.sin(2 * math.pi * root * 1.78 * t + 0.8) + 0.014 * math.sin(2 * math.pi * root * 2.0 * t + 0.2))
        air = 0.010 * math.sin(2 * math.pi * 1318.51 * t + 0.6) if sample < FOG_SAMPLE else 0.0
        tension = 0.009 * math.sin(2 * math.pi * (196.0 + 2.0 * math.sin(2 * math.pi * t / 7.0)) * t) if sample >= 3_600 * SAMPLES_PER_FRAME else 0.0
        resolve = 0.012 * math.sin(2 * math.pi * 110.0 * t + 0.2) if sample >= 5_400 * SAMPLES_PER_FRAME else 0.0
        base = (pad + air + tension + resolve) * pulse
        left.append(base * (0.94 + 0.06 * math.sin(2 * math.pi * t / 17.0)))
        right.append(base * (0.88 + 0.12 * math.sin(2 * math.pi * t / 21.0 + 0.7)))
    return left, right


def pseudo_noise(t: Any, seed: int, np: Any | None) -> Any:
    phase = (seed % 997) / 997.0 * 2 * math.pi
    if np is not None:
        return (0.52 * np.sin(2 * np.pi * 1731.0 * t + phase)
                + 0.31 * np.sin(2 * np.pi * 2933.0 * t + phase * 1.7)
                + 0.17 * np.sin(2 * np.pi * 6197.0 * t + phase * 2.3))
    return 0.52 * math.sin(2 * math.pi * 1731.0 * t + phase) + 0.31 * math.sin(2 * math.pi * 2933.0 * t + phase * 1.7) + 0.17 * math.sin(2 * math.pi * 6197.0 * t + phase * 2.3)


def event_block(event_id: str, start_local: int, count: int, seed: int, np: Any | None) -> tuple[Any, Any]:
    duration = EVENT_DURATIONS[event_id]
    pan = {
        "compiler_arpeggio": (0.78, 0.94), "anvil_lock": (0.88, 0.78), "fog_sub_drop": (0.9, 0.9),
        "sonar_feedback": (0.78, 0.88), "glitch_rip": (0.86, 0.78), "counter_divergence": (0.88, 0.8),
        "shepard_mobius": (1.0, -1.0), "physical_veto": (0.92, 0.86), "organ_resolution": (0.88, 0.88),
        "thermal_hiss": (0.78, 0.88),
    }[event_id]
    if np is not None:
        t = np.arange(start_local, start_local + count, dtype=np.float64) / SAMPLE_RATE
        env = np.clip(1.0 - t / duration, 0.0, 1.0)
        if event_id == "compiler_arpeggio":
            step = np.floor(t / 0.24).astype(np.int64)
            notes = np.asarray([523.25, 659.25, 783.99, 1046.5, 1318.51, 1567.98])
            local = np.mod(t, 0.24)
            mono = 0.11 * np.sin(2 * np.pi * notes[np.minimum(step, 5)] * t) * np.exp(-local * 12.0)
        elif event_id == "anvil_lock":
            mono = 0.18 * np.sin(2 * np.pi * 72.0 * t) * np.exp(-t * 5.0) + 0.075 * np.sin(2 * np.pi * 440.0 * t) * np.exp(-np.maximum(0.0, t - 0.22) * 3.2) * (t >= 0.22)
            mono += 0.035 * np.sin(2 * np.pi * 659.25 * t) * np.exp(-np.maximum(0.0, t - 0.28) * 2.6) * (t >= 0.28)
        elif event_id == "fog_sub_drop":
            mono = 0.20 * np.sin(2 * np.pi * 40.0 * t) * np.exp(-t * 2.0) + 0.025 * np.sin(2 * np.pi * 83.0 * t) * np.exp(-t * 1.3)
        elif event_id == "sonar_feedback":
            phase = 2 * np.pi * (760.0 * t - 48.0 * t * t)
            mono = 0.115 * np.sin(phase) * np.exp(-t * 1.5) + 0.035 * np.sin(phase * 1.51 + 0.6) * np.exp(-t * 2.3)
        elif event_id == "glitch_rip":
            noise = pseudo_noise(t, seed, np)
            gate = (np.sin(2 * np.pi * 19.0 * t) > -0.12).astype(np.float64)
            mono = (0.085 * noise + 0.045 * np.sin(2 * np.pi * 307.0 * t) + 0.028 * np.sin(2 * np.pi * 733.0 * t + 0.4)) * gate * np.exp(-t * 1.3)
        elif event_id == "counter_divergence":
            rate = 5.0 + 17.0 * t / duration
            click_phase = np.mod(t * rate, 1.0)
            clicks = np.exp(-click_phase * 90.0) * np.sin(2 * np.pi * 1550.0 * t)
            mono = 0.10 * clicks + 0.055 * np.sin(2 * np.pi * 48.0 * t) * (0.7 + 0.3 * np.sin(2 * np.pi * 2.0 * t))
        elif event_id == "shepard_mobius":
            mono = np.zeros(count, dtype=np.float64)
            for octave in range(5):
                frequency = 55.0 * (2 ** octave) * (2.0 ** (t / duration))
                gain = 0.028 * (0.5 + 0.5 * np.cos(2 * np.pi * t / duration + octave * 0.14))
                mono += gain * np.sin(2 * np.pi * frequency * t + octave * 0.43)
        elif event_id == "physical_veto":
            sweep = 180.0 + 1050.0 * np.exp(-t * 1.8)
            phase = 2 * np.pi * (180.0 * t + 1050.0 * (1.0 - np.exp(-t * 1.8)) / 1.8)
            mono = (0.18 * np.sin(phase) + 0.14 * np.sin(2 * np.pi * 54.0 * t) + 0.065 * pseudo_noise(t, seed, np)) * np.exp(-t * 0.72)
        elif event_id == "organ_resolution":
            fade = np.minimum(1.0, t / 0.3) * np.minimum(1.0, (duration - t) / 0.7)
            mono = fade * (0.075 * np.sin(2 * np.pi * 110.0 * t) + 0.061 * np.sin(2 * np.pi * 164.81 * t + 0.2)
                           + 0.052 * np.sin(2 * np.pi * 220.0 * t + 0.5) + 0.032 * np.sin(2 * np.pi * 329.63 * t + 0.7))
        else:
            noise = pseudo_noise(t, seed, np)
            fade = np.minimum(1.0, t / 0.08) * np.minimum(1.0, (duration - t) / 0.5)
            mono = fade * (0.10 * noise + 0.018 * np.sin(2 * np.pi * 58.0 * t))
        return mono * pan[0], mono * pan[1]

    left: list[float] = []
    right: list[float] = []
    for sample in range(start_local, start_local + count):
        t = sample / SAMPLE_RATE
        if event_id == "compiler_arpeggio":
            step = min(5, int(t / 0.24))
            notes = (523.25, 659.25, 783.99, 1046.5, 1318.51, 1567.98)
            mono = 0.11 * math.sin(2 * math.pi * notes[step] * t) * math.exp(-(t % 0.24) * 12.0)
        elif event_id == "anvil_lock":
            mono = 0.18 * math.sin(2 * math.pi * 72.0 * t) * math.exp(-t * 5.0)
            if t >= 0.22:
                mono += 0.075 * math.sin(2 * math.pi * 440.0 * t) * math.exp(-(t - 0.22) * 3.2)
            if t >= 0.28:
                mono += 0.035 * math.sin(2 * math.pi * 659.25 * t) * math.exp(-(t - 0.28) * 2.6)
        elif event_id == "fog_sub_drop":
            mono = 0.20 * math.sin(2 * math.pi * 40.0 * t) * math.exp(-t * 2.0) + 0.025 * math.sin(2 * math.pi * 83.0 * t) * math.exp(-t * 1.3)
        elif event_id == "sonar_feedback":
            phase = 2 * math.pi * (760.0 * t - 48.0 * t * t)
            mono = 0.115 * math.sin(phase) * math.exp(-t * 1.5) + 0.035 * math.sin(phase * 1.51 + 0.6) * math.exp(-t * 2.3)
        elif event_id == "glitch_rip":
            noise = pseudo_noise(t, seed, None)
            gate = 1.0 if math.sin(2 * math.pi * 19.0 * t) > -0.12 else 0.0
            mono = (0.085 * noise + 0.045 * math.sin(2 * math.pi * 307.0 * t) + 0.028 * math.sin(2 * math.pi * 733.0 * t + 0.4)) * gate * math.exp(-t * 1.3)
        elif event_id == "counter_divergence":
            rate = 5.0 + 17.0 * t / duration
            phase = (t * rate) % 1.0
            mono = 0.10 * math.exp(-phase * 90.0) * math.sin(2 * math.pi * 1550.0 * t) + 0.055 * math.sin(2 * math.pi * 48.0 * t) * (0.7 + 0.3 * math.sin(2 * math.pi * 2.0 * t))
        elif event_id == "shepard_mobius":
            mono = sum(0.028 * (0.5 + 0.5 * math.cos(2 * math.pi * t / duration + octave * 0.14))
                       * math.sin(2 * math.pi * 55.0 * (2 ** octave) * (2.0 ** (t / duration)) * t + octave * 0.43)
                       for octave in range(5))
        elif event_id == "physical_veto":
            phase = 2 * math.pi * (180.0 * t + 1050.0 * (1.0 - math.exp(-t * 1.8)) / 1.8)
            mono = (0.18 * math.sin(phase) + 0.14 * math.sin(2 * math.pi * 54.0 * t) + 0.065 * pseudo_noise(t, seed, None)) * math.exp(-t * 0.72)
        elif event_id == "organ_resolution":
            fade = min(1.0, t / 0.3) * min(1.0, (duration - t) / 0.7)
            mono = fade * (0.075 * math.sin(2 * math.pi * 110.0 * t) + 0.061 * math.sin(2 * math.pi * 164.81 * t + 0.2)
                           + 0.052 * math.sin(2 * math.pi * 220.0 * t + 0.5) + 0.032 * math.sin(2 * math.pi * 329.63 * t + 0.7))
        else:
            fade = min(1.0, t / 0.08) * min(1.0, (duration - t) / 0.5)
            mono = fade * (0.10 * pseudo_noise(t, seed, None) + 0.018 * math.sin(2 * math.pi * 58.0 * t))
        left.append(mono * pan[0])
        right.append(mono * pan[1])
    return left, right


def silence_float_block(start: int, left: Any, right: Any, np: Any | None) -> None:
    start_index = max(0, SILENCE_START - start)
    end_index = min(len(left), SILENCE_END - start)
    if end_index <= start_index:
        return
    if np is not None:
        left[start_index:end_index] = 0.0
        right[start_index:end_index] = 0.0
    else:
        for index in range(start_index, end_index):
            left[index] = 0.0
            right[index] = 0.0


def write_float_stereo_block(wav: wave.Wave_write, left: Any, right: Any, np: Any | None) -> None:
    if np is not None:
        left_pcm = np.clip(np.asarray(left) * 32767.0, -32768, 32767).astype("<i2")
        right_pcm = np.clip(np.asarray(right) * 32767.0, -32768, 32767).astype("<i2")
        interleaved = np.empty(left_pcm.size * 2, dtype="<i2")
        interleaved[0::2] = left_pcm
        interleaved[1::2] = right_pcm
        wav.writeframesraw(interleaved.tobytes())
        return
    values = array.array("h")
    for left_value, right_value in zip(left, right):
        values.append(max(-32768, min(32767, round(left_value * 32767.0))))
        values.append(max(-32768, min(32767, round(right_value * 32767.0))))
    if sys.byteorder != "little":
        values.byteswap()
    wav.writeframesraw(values.tobytes())


def render_score(path: Path, np: Any | None) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        for start in range(0, TOTAL_SAMPLES, BLOCK_SAMPLES):
            count = min(BLOCK_SAMPLES, TOTAL_SAMPLES - start)
            left, right = score_block(start, count, np)
            silence_float_block(start, left, right, np)
            write_float_stereo_block(wav, left, right, np)
    info = validate_stem(path)
    if silence_peak(path) != 0:
        raise AudioBuildError("score stem is not exactly zero in samples [4592000,4608000)")
    return info


def load_event_map(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mapped: list[dict[str, Any]] = []
    for event in events:
        event_id = event["id"]
        duration_samples = round(EVENT_DURATIONS[event_id] * SAMPLE_RATE)
        start = int(event["frame"]) * SAMPLES_PER_FRAME
        seed = int.from_bytes(hashlib.sha256(event_id.encode("utf-8")).digest()[:4], "big")
        mapped.append({
            "id": event_id,
            "frame": int(event["frame"]),
            "startSample": start,
            "durationSamples": duration_samples,
            "endSampleExclusive": start + duration_samples,
            "description": event.get("description", ""),
            "deterministicSeed": seed,
        })
    return mapped


def render_sfx(path: Path, events: list[dict[str, Any]], np: Any | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    mapped = load_event_map(events)
    for event in mapped:
        if event["id"] != "physical_veto" and event["startSample"] < SILENCE_END and event["endSampleExclusive"] > SILENCE_START:
            raise AudioBuildError(f"SFX {event['id']} overlaps the absolute-silence window")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        for block_start in range(0, TOTAL_SAMPLES, BLOCK_SAMPLES):
            count = min(BLOCK_SAMPLES, TOTAL_SAMPLES - block_start)
            if np is not None:
                left = np.zeros(count, dtype=np.float64)
                right = np.zeros(count, dtype=np.float64)
            else:
                left, right = [0.0] * count, [0.0] * count
            block_end = block_start + count
            for event in mapped:
                overlap_start = max(block_start, event["startSample"])
                overlap_end = min(block_end, event["endSampleExclusive"])
                if overlap_end <= overlap_start:
                    continue
                local_start = overlap_start - event["startSample"]
                event_left, event_right = event_block(event["id"], local_start, overlap_end - overlap_start, event["deterministicSeed"], np)
                destination = overlap_start - block_start
                if np is not None:
                    left[destination:destination + len(event_left)] += event_left
                    right[destination:destination + len(event_right)] += event_right
                else:
                    for offset, (left_value, right_value) in enumerate(zip(event_left, event_right)):
                        left[destination + offset] += left_value
                        right[destination + offset] += right_value
            silence_float_block(block_start, left, right, np)
            write_float_stereo_block(wav, left, right, np)
    info = validate_stem(path)
    if silence_peak(path) != 0:
        raise AudioBuildError("SFX stem is not exactly zero in samples [4592000,4608000)")
    return info, mapped


def run_ffmpeg(args: list[str], label: str) -> str:
    result = subprocess.run(args, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode:
        detail = (result.stderr or result.stdout or "").strip().splitlines()[-8:]
        raise AudioBuildError(f"{label} failed (exit {result.returncode}): {' | '.join(detail)}")
    return result.stderr or ""


def loudnorm_measurements(output: str) -> dict[str, Any]:
    matches = list(re.finditer(r"\{\s*\"input_i\"[\s\S]*?\}", output))
    if not matches:
        raise AudioBuildError("FFmpeg loudnorm returned no first-pass measurement JSON")
    try:
        value = json.loads(matches[-1].group(0))
    except json.JSONDecodeError:
        raise AudioBuildError("FFmpeg loudnorm returned malformed measurement JSON") from None
    needed = ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")
    if any(key not in value for key in needed):
        raise AudioBuildError("FFmpeg loudnorm measurement is incomplete")
    return value


def ebur128(path: Path) -> dict[str, float]:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise AudioBuildError("ffmpeg is required for loudness and true-peak verification")
    output = run_ffmpeg([
        ffmpeg, "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"
    ], "ebur128 measurement")
    integrated = re.search(r"^\s*I:\s*(-?\d+(?:\.\d+)?)\s+LUFS\s*$", output, re.MULTILINE)
    true_peak = re.search(r"^\s*True peak:\s*(-?\d+(?:\.\d+)?)\s+dBTP\s*$", output, re.MULTILINE)
    if true_peak is None:
        true_peak = re.search(r"True peak:\s*\n\s*Peak:\s*(-?\d+(?:\.\d+)?)\s+dBFS", output)
    if integrated is None or true_peak is None:
        raise AudioBuildError("FFmpeg ebur128 did not report integrated LUFS and true peak")
    return {"integratedLUFS": float(integrated.group(1)), "truePeakDBTP": float(true_peak.group(1))}


def force_exact_silence(path: Path) -> None:
    temporary = path.with_name(path.stem + ".silence.tmp.wav")
    try:
        with wave.open(str(path), "rb") as source, wave.open(str(temporary), "wb") as target:
            params = source.getparams()
            if (params.framerate, params.nchannels, params.sampwidth, params.nframes) != (SAMPLE_RATE, 2, 2, TOTAL_SAMPLES):
                raise AudioBuildError(f"master must be exact 48 kHz stereo PCM16 before silence correction; got {params}")
            target.setparams(params)
            position = 0
            while position < TOTAL_SAMPLES:
                count = min(BLOCK_SAMPLES, TOTAL_SAMPLES - position)
                raw = bytearray(source.readframes(count))
                if len(raw) != count * 4:
                    raise AudioBuildError("master PCM payload ended before its declared sample count")
                overlap_start = max(position, SILENCE_START)
                overlap_end = min(position + count, SILENCE_END)
                if overlap_end > overlap_start:
                    byte_start = (overlap_start - position) * 4
                    byte_end = (overlap_end - position) * 4
                    raw[byte_start:byte_end] = bytes(byte_end - byte_start)
                target.writeframesraw(raw)
                position += count
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def mix_master() -> tuple[dict[str, Any], dict[str, Any]]:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise AudioBuildError("ffmpeg is required to build the exact PCM master")
    narration, score, sfx = AUDIO / "narration.wav", AUDIO / "score.wav", AUDIO / "sfx.wav"
    master = AUDIO / "master.wav"
    normalized_temp = AUDIO / "master-normalized.tmp.wav"
    common = (
        "[0:a]asplit=2[narration_sidechain][narration_mix];"
        "[1:a]equalizer=f=2200:t=q:w=0.7:g=-5[scorecarved];"
        "[scorecarved][narration_sidechain]sidechaincompress=threshold=0.035:ratio=5:attack=20:release=250:makeup=1[ducked];"
        "[2:a]equalizer=f=2200:t=q:w=0.7:g=-5[sfxcarved];"
        f"[narration_mix][ducked][sfxcarved]amix=inputs=3:duration=longest:normalize=0,aresample={SAMPLE_RATE},"
        f"apad,atrim=end_sample={TOTAL_SAMPLES},asetpts=PTS-STARTPTS[mix]"
    )
    first = run_ffmpeg([
        ffmpeg, "-hide_banner", "-nostats", "-i", str(narration), "-i", str(score), "-i", str(sfx),
        "-filter_complex", common + ";[mix]loudnorm=I=-17:TP=-1.8:LRA=9:print_format=json[out]",
        "-map", "[out]", "-ar", str(SAMPLE_RATE), "-ac", "2", "-f", "null", "-",
    ], "first-pass loudnorm analysis")
    first_stats = loudnorm_measurements(first)
    second_filter = (
        common + ";[mix]loudnorm=I=-17:TP=-1.8:LRA=9"
        + f":measured_I={first_stats['input_i']}:measured_TP={first_stats['input_tp']}"
        + f":measured_LRA={first_stats['input_lra']}:measured_thresh={first_stats['input_thresh']}"
        + f":offset={first_stats['target_offset']}:linear=true:print_format=json[out]"
    )
    second = run_ffmpeg([
        ffmpeg, "-hide_banner", "-nostats", "-y", "-i", str(narration), "-i", str(score), "-i", str(sfx),
        "-filter_complex", second_filter, "-map", "[out]", "-ar", str(SAMPLE_RATE), "-ac", "2",
        "-c:a", "pcm_s16le", str(normalized_temp),
    ], "second-pass loudnorm render")
    second_stats = loudnorm_measurements(second)
    validate_stem(normalized_temp)
    normalized_temp.replace(master)
    force_exact_silence(master)
    loudness = ebur128(master)
    if loudness["truePeakDBTP"] > -1.0:
        correction_db = -1.2 - loudness["truePeakDBTP"]
        corrected = AUDIO / "master-truepeak.tmp.wav"
        run_ffmpeg([
            ffmpeg, "-hide_banner", "-loglevel", "error", "-xerror", "-y", "-i", str(master),
            "-af", f"volume={correction_db:.6f}dB", "-ar", str(SAMPLE_RATE), "-ac", "2",
            "-c:a", "pcm_s16le", str(corrected),
        ], "true-peak headroom correction")
        validate_stem(corrected)
        force_exact_silence(corrected)
        corrected.replace(master)
        loudness = ebur128(master)
    if not -18.0 <= loudness["integratedLUFS"] <= -16.0:
        raise AudioBuildError(f"master loudness {loudness['integratedLUFS']} LUFS is outside -18 to -16 LUFS")
    if loudness["truePeakDBTP"] > -1.0:
        raise AudioBuildError(f"master true peak {loudness['truePeakDBTP']} dBTP exceeds -1.0 dBTP")
    if silence_peak(master) != 0:
        raise AudioBuildError("master silence window is not exactly zero after loudnorm")
    result = validate_stem(master)
    result.update({
        "strictDecode": "passed",
        "loudnormFirstPass": first_stats,
        "loudnormSecondPass": second_stats,
        "ebur128Final": loudness,
        "loudnormTarget": {"integratedLUFS": -17.0, "truePeakDBTP": -1.8, "truePeakAcceptanceDBTP": -1.0, "passes": 2},
        "latencyNote": "FFmpeg timestamps are retained; source stems and authored event sample positions are not shifted.",
    })
    return result, {"firstPass": first_stats, "secondPass": second_stats}


def run_mix(segments: list[dict[str, Any]], events: list[dict[str, Any]], event_data: dict[str, Any]) -> None:
    _, _, missing = cue_paths()
    if missing:
        raise AudioBuildError("--mix pending: missing local PCM cues: " + ", ".join(missing))
    AUDIO.mkdir(parents=True, exist_ok=True)
    narration_info, timing = make_narration(segments)
    np = load_numpy()
    score_info = render_score(AUDIO / "score.wav", np)
    sfx_info, event_map = render_sfx(AUDIO / "sfx.wav", events, np)
    for path in (AUDIO / "narration.wav", AUDIO / "score.wav", AUDIO / "sfx.wav"):
        if silence_peak(path) != 0:
            raise AudioBuildError(f"{path.name} violates exact silence samples [{SILENCE_START},{SILENCE_END})")
    master_info, normalization = mix_master()
    timing["sourceEvents"] = event_data
    timing["sfxOnsets"] = event_map
    write_json(TIMING_PATH, timing)
    settings = {
        "version": 1,
        "durationSeconds": DURATION_SECONDS,
        "fps": FPS,
        "sampleRate": SAMPLE_RATE,
        "samplesPerFrame": SAMPLES_PER_FRAME,
        "samplesPerChannel": TOTAL_SAMPLES,
        "channels": 2,
        "runtime": {"python": sys.version.split()[0], "numpy": getattr(np, "__version__", None), "stdlibFallback": "array/wave/math" if np is None else None},
        "outputs": {"narration": narration_info, "score": score_info, "sfx": sfx_info, "master": master_info},
        "ducking": {"filter": "sidechaincompress", "threshold": 0.035, "ratio": 5, "attackMs": 20, "releaseMs": 250},
        "voiceBandCarve": {"frequencyHz": 2200, "q": 0.7, "gainDB": -5, "appliedTo": ["score", "sfx"]},
        "loudnorm": normalization,
        "absoluteSilence": {"startFrame": SILENCE_START_FRAME, "endFrameExclusive": SILENCE_END_FRAME, "startSample": SILENCE_START, "endSampleExclusive": SILENCE_END, "allStemsExactZero": True},
        "sfxOnsets": event_map,
        "captionTiming": timing["captionTimingMethod"],
    }
    write_json(SETTINGS_PATH, settings)
    write_json(MANIFEST_PATH, {
        "version": 1,
        "status": "built",
        "mixSettings": str(SETTINGS_PATH.relative_to(WORK)),
        "audioTiming": str(TIMING_PATH.relative_to(WORK)),
        "stemsAndMaster": settings["outputs"],
        "inputCues": [part for segment in timing["segments"] for part in segment["cueParts"]],
        "eventOnsets": event_map,
    })
    print(json.dumps({
        "status": "mix_complete",
        "master": master_info,
        "silence": settings["absoluteSilence"],
        "audioTiming": str(TIMING_PATH.relative_to(WORK)),
        "mixSettings": str(SETTINGS_PATH.relative_to(WORK)),
        "mixManifest": str(MANIFEST_PATH.relative_to(WORK)),
    }, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--mix", action="store_true", help="build deterministic stems/master from local cue WAVs")
    mode.add_argument("--audit", action="store_true", help="read-only cue inventory and measured PCM sample counts")
    args = parser.parse_args()
    try:
        segments, events, event_data = load_sources()
        if args.audit:
            return audit_cues(segments)
        run_mix(segments, events, event_data)
        return 0
    except (AudioBuildError, OSError, ValueError, wave.Error, OverflowError) as exc:
        print(f"build_audio.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
