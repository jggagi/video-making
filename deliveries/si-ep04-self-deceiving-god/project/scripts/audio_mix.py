#!/usr/bin/env python3
"""Build deterministic EP04 audio from complete, locally verified PCM cues.

This script has no provider path. ``--audit`` is read-only; ``--mix`` refuses
to render when cues are missing or any spoken PCM exceeds its authored window.
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
DELIVERY = PROJECT.parent
AUDIO = PROJECT / "public" / "audio"
CUES = AUDIO / "cues"
SEGMENTS_PATH = PROJECT / "segments.json"
EVENTS_PATH = PROJECT / "sfx_events.json"
PROVIDER_MANIFEST_PATH = AUDIO / "provider-manifest.json"
TIMING_PATH = PROJECT / "audio-timing.json"
SETTINGS_PATH = AUDIO / "mix-settings.json"
MIX_MANIFEST_PATH = AUDIO / "mix-manifest.json"

FPS = 60
SAMPLE_RATE = 48_000
SAMPLES_PER_FRAME = 800
DURATION_SECONDS = 120
TOTAL_FRAMES = FPS * DURATION_SECONDS
TOTAL_SAMPLES = SAMPLE_RATE * DURATION_SECONDS
BLOCK_SAMPLES = 24_000
SILENCE_START_FRAME = 5_820
SILENCE_END_FRAME = 5_850
SILENCE_START = SILENCE_START_FRAME * SAMPLES_PER_FRAME
SILENCE_END = SILENCE_END_FRAME * SAMPLES_PER_FRAME

SFX_DURATIONS = {
    "crystalline_ticks": 3.0,
    "guillotine": 2.0,
    "vacuum38": 5.0,
    "amber_clock": 10.0,
    "mirror_split": 4.0,
    "shepard": 17.0,
    "organ": 18.0,
    "silence": 0.5,
    "truth_drop": 0.3,
    "glass_shatter": 5.0,
    "cello": 6.0,
    "thermal": 3.0,
}


class AudioBuildError(RuntimeError):
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
    temporary = path.with_name(path.name + ".tmp")
    if temporary.exists():
        raise AudioBuildError(f"preserving existing temporary file {temporary}")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AudioBuildError(f"cannot read {path}: {exc}") from None
    if not isinstance(value, dict):
        raise AudioBuildError(f"{path.name} must contain a JSON object")
    return value


def load_sources() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    data = read_json(SEGMENTS_PATH)
    if (data.get("fps"), data.get("duration_seconds"), data.get("sample_rate")) != (FPS, DURATION_SECONDS, SAMPLE_RATE):
        raise AudioBuildError("segments.json must describe 120 seconds at 60 fps and 48 kHz")
    segments = data.get("segments")
    if not isinstance(segments, list) or [item.get("id") for item in segments] != [f"S{i:02d}" for i in range(1, 11)]:
        raise AudioBuildError("segments.json must contain S01 through S10 in order")
    for item in segments:
        if not all(isinstance(item.get(field), str) and item[field].strip() for field in ("display_subtitle", "tts_phonetic_text")):
            raise AudioBuildError(f"{item.get('id', 'segment')} needs display_subtitle and tts_phonetic_text")
        start, end = int(item["startFrame"]), int(item["endFrame"])
        if not 0 <= start < end <= TOTAL_FRAMES:
            raise AudioBuildError(f"{item['id']} has an invalid frame window")

    event_data = read_json(EVENTS_PATH)
    if (event_data.get("fps"), event_data.get("sample_rate"), event_data.get("samples_per_frame")) != (FPS, SAMPLE_RATE, SAMPLES_PER_FRAME):
        raise AudioBuildError("sfx_events.json must use 60 fps, 48 kHz, and 800 samples per frame")
    events = event_data.get("events")
    if not isinstance(events, list) or {event.get("id") for event in events} != set(SFX_DURATIONS):
        raise AudioBuildError("sfx_events.json event IDs differ from the approved score design")
    for event in events:
        frame = event.get("frame")
        if not isinstance(frame, int) or not 0 <= frame < TOTAL_FRAMES:
            raise AudioBuildError(f"{event.get('id')} has an invalid frame")
        if event.get("sample") != frame * SAMPLES_PER_FRAME:
            raise AudioBuildError(f"{event['id']} sample anchor does not equal frame * 800")
        if abs(float(event.get("durationSeconds", -1)) - SFX_DURATIONS[event["id"]]) > 1e-9:
            raise AudioBuildError(f"{event['id']} duration differs from the approved deterministic profile")
    silence_event = next(event for event in events if event["id"] == "silence")
    if (silence_event["frame"], silence_event["durationSeconds"]) != (SILENCE_START_FRAME, 0.5):
        raise AudioBuildError("authored silence must be exactly [5820, 5850)")
    return segments, events, event_data


def cue_parts(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for segment in segments:
        sid = segment["id"]
        if sid == "S08":
            result.extend([
                {"id": "S08a", "parent_id": sid, "startFrame": segment["startFrame"], "endFrame": SILENCE_START_FRAME},
                {"id": "S08b", "parent_id": sid, "startFrame": SILENCE_END_FRAME, "endFrame": segment["endFrame"]},
            ])
        else:
            result.append({"id": sid, "parent_id": sid, "startFrame": segment["startFrame"], "endFrame": segment["endFrame"]})
    return result


def wav_read(path: Path, expected_channels: int | None = None) -> tuple[array.array, dict[str, Any]]:
    try:
        with wave.open(str(path), "rb") as wav:
            params = wav.getparams()
            raw = wav.readframes(params.nframes)
    except (OSError, wave.Error) as exc:
        raise AudioBuildError(f"cannot read {path}: {exc}") from None
    if (params.framerate, params.sampwidth, params.comptype) != (SAMPLE_RATE, 2, "NONE"):
        raise AudioBuildError(f"{path.name} must be uncompressed 48 kHz PCM16")
    if expected_channels is not None and params.nchannels != expected_channels:
        raise AudioBuildError(f"{path.name} must have {expected_channels} channels")
    expected_bytes = params.nframes * params.nchannels * 2
    if params.nframes <= 0 or len(raw) != expected_bytes:
        raise AudioBuildError(f"{path.name} has an empty or physically incomplete PCM payload")
    values = array.array("h")
    values.frombytes(raw)
    if sys.byteorder != "little":
        values.byteswap()
    return values, {
        "samplesPerChannel": params.nframes,
        "channels": params.nchannels,
        "durationSeconds": params.nframes / SAMPLE_RATE,
        "sha256": sha256_file(path),
        "pcmSha256": sha256_bytes(raw),
    }


def active_bounds(values: array.array) -> dict[str, int]:
    if not values:
        raise AudioBuildError("cannot measure an empty cue")
    peak = max(abs(value) for value in values)
    threshold = max(48, int(peak * 0.004))
    window = min(240, len(values))
    required = window * threshold * threshold
    rolling = sum(value * value for value in values[:window])
    first = last = None
    for start in range(len(values) - window + 1):
        if rolling >= required:
            if first is None:
                first = start
            last = start + window
        if start + window < len(values):
            rolling += values[start + window] ** 2 - values[start] ** 2
    if first is None or last is None:
        raise AudioBuildError("cue has no measurable active PCM")
    return {"onsetSample": first, "activeEndSampleExclusive": last, "thresholdPcm16": threshold, "windowSamples": window, "peakPcm16": peak}


def load_cues(segments: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    manifest = read_json(PROVIDER_MANIFEST_PATH)
    entries = manifest.get("segments", {})
    parts = cue_parts(segments)
    measured: list[dict[str, Any]] = []
    missing: list[str] = []
    for part in parts:
        cue_id = part["id"]
        entry = entries.get(cue_id)
        original_path = CUES / f"{cue_id}.wav"
        path = original_path
        if not isinstance(entry, dict) or not path.is_file():
            missing.append(cue_id)
            continue
        if entry.get("tts_phonetic_text") is not None:
            expected_text = entry["tts_phonetic_text"]
            segment = next(item for item in segments if item["id"] == part["parent_id"])
            if cue_id == "S08a":
                expected_text = "直到漫长的十年过去，笨重的物理世界，"
            elif cue_id == "S08b":
                expected_text = "终于传回了，唯一的一声回音：错误。"
            else:
                expected_text = segment["tts_phonetic_text"]
            if entry.get("tts_phonetic_text") != expected_text:
                raise AudioBuildError(f"provider manifest text mismatch for {cue_id}")
        playback_adjustment = None
        source_info = None
        if cue_id == "S09" and entry.get("playback_override"):
            override = entry["playback_override"]
            if (override.get("trim_start_samples"), override.get("trim_end_samples")) != (9_600, 7_680):
                raise AudioBuildError("S09 playback override differs from the root-approved exact boundary-zero trim")
            if override.get("path") != "public/audio/cues/S09-window.wav":
                raise AudioBuildError("S09 playback override path is not the approved derived cue path")
            original_values, source_info = wav_read(original_path, expected_channels=1)
            if entry.get("cue_sha256") != source_info["sha256"] or override.get("source_cue_sha256") != source_info["sha256"]:
                raise AudioBuildError("S09 immutable source cue hash differs from its playback override evidence")
            if len(original_values) != 449_280:
                raise AudioBuildError("S09 immutable source cue sample count changed")
            if any(original_values[:9_600]) or any(original_values[-7_680:]):
                raise AudioBuildError("S09 approved boundary regions are no longer exact digital zero")
            path = PROJECT / override["path"]
            if not path.is_file():
                missing.append("S09-window")
                continue
            values, info = wav_read(path, expected_channels=1)
            expected_pcm = original_values[9_600:-7_680]
            if len(values) != 432_000 or values.tobytes() != expected_pcm.tobytes():
                raise AudioBuildError("S09 playback PCM is not byte-equal to the immutable cue interior")
            if info["sha256"] != override.get("sha256") or info["pcmSha256"] != override.get("pcm_sha256"):
                raise AudioBuildError("S09 playback cue hash differs from recorded trim evidence")
            if override.get("retained_pcm_sha256") != sha256_bytes(expected_pcm.tobytes()):
                raise AudioBuildError("S09 retained interior PCM hash differs from recorded evidence")
            playback_adjustment = {
                "decision": override["decision"],
                "trimStartSamples": 9_600,
                "trimEndSamples": 7_680,
                "sourceSamplesAt48k": 449_280,
                "playbackSamplesAt48k": 432_000,
                "sourceCueSha256": source_info["sha256"],
                "playbackCueSha256": info["sha256"],
                "retainedPcmSha256": override["retained_pcm_sha256"],
                "retainedInteriorByteEqual": True,
            }
        else:
            values, info = wav_read(path, expected_channels=1)
        if cue_id != "S09" and entry.get("cue_sha256") and entry["cue_sha256"] != info["sha256"]:
            raise AudioBuildError(f"{cue_id} cue hash differs from provider manifest")
        active = active_bounds(values)
        slot_samples = (int(part["endFrame"]) - int(part["startFrame"])) * SAMPLES_PER_FRAME
        overflow = active["activeEndSampleExclusive"] > slot_samples
        measured.append({
            **part,
            "path": path,
            "samples": info["samplesPerChannel"],
            "durationSeconds": info["durationSeconds"],
            "sha256": info["sha256"],
            "pcmSha256": info["pcmSha256"],
            "active": active,
            "slotSamples": slot_samples,
            "activeOverflowSamples": max(0, active["activeEndSampleExclusive"] - slot_samples),
            "fits": not overflow and info["samplesPerChannel"] <= slot_samples,
            "sourcePath": original_path,
            "playbackAdjustment": playback_adjustment,
            "pcm": values,
        })
    return measured, missing


def audit(segments: list[dict[str, Any]]) -> int:
    measured, missing = load_cues(segments)
    report = []
    playback_adjustments = []
    for item in measured:
        report.append({key: item[key] for key in (
            "id", "startFrame", "endFrame", "samples", "durationSeconds", "active", "slotSamples", "activeOverflowSamples", "fits", "sha256"
        )})
        if item.get("playbackAdjustment"):
            playback_adjustments.append(item["playbackAdjustment"])
    status = "pending_cues" if missing else "needs_sol_fit" if any(not item["fits"] for item in measured) else "cues_fit"
    print(json.dumps({"status": status, "measuredCues": report, "missingCueIds": missing, "playbackAdjustments": playback_adjustments}, ensure_ascii=False, indent=2))
    return 0


def cjk_count(text: str) -> int:
    return sum("\u3400" <= char <= "\u9fff" for char in text)


def phrase_lines(line: str) -> list[str]:
    """Split at punctuation and wrap any long phrase without dropping text."""
    phrases = re.findall(r".*?[，。；：？！,;!?]|.+$", line)
    result: list[str] = []
    for phrase in phrases:
        if not phrase:
            continue
        current = ""
        count = 0
        for char in phrase:
            current += char
            if "\u3400" <= char <= "\u9fff":
                count += 1
            if count >= 14:
                result.append(current)
                current, count = "", 0
        if current:
            result.append(current)
    if "".join(result) != line:
        raise AudioBuildError("caption phrase splitting did not preserve the source line")
    return result


def caption_groups(lines: list[str]) -> list[list[str]]:
    phrases = [phrase for line in lines for phrase in phrase_lines(line)]
    groups = [phrases[index:index + 2] for index in range(0, len(phrases), 2)]
    for group in groups:
        if len(group) > 2 or any(cjk_count(line) > 14 for line in group):
            raise AudioBuildError("caption group exceeds the two-line / 14 Chinese character limit")
    return groups


def text_weight(text: str) -> float:
    return max(1.0, cjk_count(text) + 0.55 * sum(char.isascii() and char.isalnum() for char in text))


def frame_boundaries(start: int, end: int, groups: list[list[str]]) -> list[int]:
    length = end - start
    if length < len(groups):
        raise AudioBuildError("measured speech is too brief for non-empty estimated caption frame windows")
    weights = [sum(text_weight(line) for line in group) for group in groups]
    total = sum(weights)
    boundaries = [start]
    consumed = 0.0
    for weight in weights[:-1]:
        consumed += weight
        guess = start + round(length * consumed / total)
        lo = boundaries[-1] + 1
        hi = end - (len(groups) - len(boundaries))
        boundaries.append(max(lo, min(hi, guess)))
    boundaries.append(end)
    return boundaries


def timecode(milliseconds: int) -> str:
    hours, rest = divmod(milliseconds, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    seconds, ms = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"


def make_captions(segments: list[dict[str, Any]], measured: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lookup = {item["id"]: item for item in measured}
    captions: list[dict[str, Any]] = []
    segment_records: list[dict[str, Any]] = []
    for segment in segments:
        sid = segment["id"]
        display_lines = segment["display_subtitle"].splitlines()
        parts = [lookup[sid]] if sid != "S08" else [lookup["S08a"], lookup["S08b"]]
        if sid == "S10":
            spoken_lines = display_lines[:1]
            display_only_lines = display_lines[1:]
            part_lines = [spoken_lines]
        elif sid == "S08":
            if len(display_lines) != 2:
                raise AudioBuildError("S08 display must have two phrases around the absolute silence")
            part_lines = [[display_lines[0]], [display_lines[1]]]
            display_only_lines = []
        else:
            part_lines = [display_lines]
            display_only_lines = []

        cue_records: list[dict[str, Any]] = []
        for part, lines in zip(parts, part_lines):
            layout_path = PROJECT / "caption-layout.json"
            custom = json.loads(layout_path.read_text(encoding="utf-8")) if layout_path.exists() else {}
            groups = custom.get(part["id"], caption_groups(lines))
            if "".join("".join(group) for group in groups) != "".join(lines):
                raise AudioBuildError(f"{part['id']} manual caption layout changed source characters")
            absolute_start = int(part["startFrame"]) * SAMPLES_PER_FRAME + part["active"]["onsetSample"]
            absolute_end = int(part["startFrame"]) * SAMPLES_PER_FRAME + part["active"]["activeEndSampleExclusive"]
            start_frame = absolute_start // SAMPLES_PER_FRAME
            end_frame = min(int(part["endFrame"]), math.ceil(absolute_end / SAMPLES_PER_FRAME))
            boundaries = frame_boundaries(start_frame, end_frame, groups)
            for index, group in enumerate(groups, start=1):
                if boundaries[index] <= boundaries[index - 1]:
                    raise AudioBuildError(f"{sid} has an empty caption interval")
                text = "\n".join(group)
                caption = {
                    "id": f"{part['id']}-C{index:02d}",
                    "segmentId": sid,
                    "startFrame": boundaries[index - 1],
                    "endFrame": boundaries[index],
                    "text": text,
                    "alignment": "estimated phrase timing weighted within measured active PCM; not word aligned",
                }
                captions.append(caption)
            cue_records.append({
                "id": part["id"],
                "cueFile": str(part["path"].relative_to(PROJECT)),
                "startFrame": part["startFrame"],
                "endFrame": part["endFrame"],
                "samplesAt48k": part["samples"],
                "durationSeconds": round(part["durationSeconds"], 6),
                "activePcm48k": part["active"],
                "activeStartAbsoluteSample": absolute_start,
                "activeEndAbsoluteSampleExclusive": absolute_end,
                "sha256": part["sha256"],
                "playbackAdjustment": part.get("playbackAdjustment"),
                "alignment": "measured cue PCM; caption phrases estimated",
            })
        if display_only_lines:
            spoken_end = max(item["endFrame"] for item in captions if item["segmentId"] == sid)
            groups = caption_groups(display_only_lines)
            if len(groups) != 1:
                raise AudioBuildError("S10 display-only EP05 tag should be one two-line-or-less caption")
            text = "\n".join(groups[0])
            captions.append({
                "id": "S10-DISPLAY-ONLY",
                "segmentId": sid,
                "startFrame": spoken_end,
                "endFrame": TOTAL_FRAMES,
                "text": text,
                "alignment": "display-only EP05 tag after spoken S10 phrase",
                "displayOnly": True,
            })
        segment_records.append({
            "id": sid,
            "startFrame": int(segment["startFrame"]),
            "endFrame": int(segment["endFrame"]),
            "cueParts": cue_records,
        })

    captions.sort(key=lambda item: (item["startFrame"], item["endFrame"], item["id"]))
    for caption in captions:
        lines = caption["text"].splitlines()
        if not 1 <= len(lines) <= 2 or any(cjk_count(line) > 14 for line in lines):
            raise AudioBuildError(f"caption {caption['id']} exceeds the two-line / 14 Chinese character limit")
        if not 0 <= caption["startFrame"] < caption["endFrame"] <= TOTAL_FRAMES:
            raise AudioBuildError(f"caption {caption['id']} is outside the film timeline")
        if caption["startFrame"] < SILENCE_END_FRAME and caption["endFrame"] > SILENCE_START_FRAME:
            raise AudioBuildError("caption overlaps the absolute-silence frames [5820,5850)")
    return segment_records, captions


def write_captions_srt(captions: list[dict[str, Any]]) -> None:
    blocks = []
    for index, caption in enumerate(captions, start=1):
        start_ms = round(caption["startFrame"] * 1000 / FPS)
        end_ms = round(caption["endFrame"] * 1000 / FPS)
        blocks.append(f"{index}\n{timecode(start_ms)} --> {timecode(end_ms)}\n{caption['text']}\n")
    payload = "\n".join(blocks)
    paths = [DELIVERY / platform / "captions.srt" for platform in ("B站", "小红书")]
    conflicts = [path for path in paths if path.exists() or path.with_name(path.name + ".tmp").exists()]
    if conflicts:
        raise AudioBuildError("preserving existing subtitle files: " + ", ".join(map(str, conflicts)))
    temporaries = []
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(payload, encoding="utf-8")
        temporaries.append((temporary, path))
    for temporary, path in temporaries:
        temporary.replace(path)


def zero_overlap(start: int, left: list[float] | array.array, right: list[float] | array.array) -> None:
    lo, hi = max(0, SILENCE_START - start), min(len(left), SILENCE_END - start)
    for index in range(lo, max(lo, hi)):
        left[index] = 0.0
        right[index] = 0.0


def write_float_block(wav: wave.Wave_write, left: list[float] | array.array, right: list[float] | array.array) -> None:
    pcm = array.array("h")
    for lval, rval in zip(left, right):
        pcm.append(max(-32768, min(32767, round(lval * 32767.0))))
        pcm.append(max(-32768, min(32767, round(rval * 32767.0))))
    if sys.byteorder != "little":
        pcm.byteswap()
    wav.writeframesraw(pcm.tobytes())


def write_wav_atomic(path: Path, writer: Any) -> dict[str, Any]:
    temporary = path.with_name(path.stem + ".tmp.wav")
    if path.exists() or temporary.exists():
        raise AudioBuildError(f"preserving existing audio output {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    writer(temporary)
    _, info = wav_read(temporary, expected_channels=2)
    if info["samplesPerChannel"] != TOTAL_SAMPLES:
        temporary.unlink(missing_ok=True)
        raise AudioBuildError(f"{path.name} does not contain exactly {TOTAL_SAMPLES} samples per channel")
    temporary.replace(path)
    info["path"] = str(path.relative_to(DELIVERY))
    return info


def render_narration(path: Path, measured: list[dict[str, Any]]) -> dict[str, Any]:
    timed = sorted(measured, key=lambda item: item["startFrame"])
    for item in timed:
        if not item["fits"]:
            raise AudioBuildError(
                f"NEEDS_SOL: {item['id']} cue PCM is {item['samples']} samples at 48 kHz "
                f"({item['durationSeconds']:.6f}s), slot is {item['slotSamples']} samples "
                f"({item['slotSamples'] / SAMPLE_RATE:.6f}s), active speech exceeds slot by "
                f"{item['activeOverflowSamples']} samples; no trimming or speed change applied"
            )
    cursor = 0

    def emit(temporary: Path) -> None:
        nonlocal cursor
        with wave.open(str(temporary), "wb") as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            for block_start in range(0, TOTAL_SAMPLES, BLOCK_SAMPLES):
                block_count = min(BLOCK_SAMPLES, TOTAL_SAMPLES - block_start)
                interleaved = array.array("h", [0]) * (block_count * 2)
                block_end = block_start + block_count
                while cursor < len(timed):
                    item = timed[cursor]
                    cue_start = int(item["startFrame"]) * SAMPLES_PER_FRAME
                    cue_end = cue_start + item["samples"]
                    if cue_end <= block_start:
                        cursor += 1
                        continue
                    if cue_start >= block_end:
                        break
                    lo, hi = max(cue_start, block_start), min(cue_end, block_end)
                    mono = item["pcm"]
                    for absolute in range(lo, hi):
                        sample = mono[absolute - cue_start]
                        dest = (absolute - block_start) * 2
                        interleaved[dest] = sample
                        interleaved[dest + 1] = sample
                    if cue_end <= block_end:
                        cursor += 1
                    else:
                        break
                if SILENCE_START < block_end and SILENCE_END > block_start:
                    lo = max(SILENCE_START, block_start) - block_start
                    hi = min(SILENCE_END, block_end) - block_start
                    interleaved[lo * 2:hi * 2] = array.array("h", [0]) * ((hi - lo) * 2)
                if sys.byteorder != "little":
                    interleaved.byteswap()
                wav.writeframesraw(interleaved.tobytes())

    info = write_wav_atomic(path, emit)
    return info


def score_sample(sample: int) -> tuple[float, float]:
    t = sample / SAMPLE_RATE
    # Glass harmonics in the opening slowly give way to a 38 Hz vacuum.
    crystal_gain = 0.045 * max(0.0, min(1.0, (21.0 - t) / 3.0))
    crystal = crystal_gain * (math.sin(2 * math.pi * 523.25 * t) + 0.55 * math.sin(2 * math.pi * 783.99 * t + 0.3))
    vacuum_gain = 0.0 if t < 21 else 0.055 * min(1.0, (t - 21) / 5.0)
    vacuum = vacuum_gain * (math.sin(2 * math.pi * 38.0 * t) + 0.22 * math.sin(2 * math.pi * 76.0 * t + 0.2))
    clock_gain = 0.0 if t < 34 else 0.009 * min(1.0, (t - 34) / 1.5)
    clock = clock_gain * math.sin(2 * math.pi * (2.0 + 0.15 * math.sin(2 * math.pi * t / 10.0)) * t)

    split_gain = max(0.0, min(1.0, (t - 48.0) / 4.0))
    split_fade = max(0.0, min(1.0, (97.0 - t) / 4.0))
    split_l = 0.026 * split_gain * split_fade * math.sin(2 * math.pi * 110.0 * t)
    split_r = 0.026 * split_gain * split_fade * math.sin(2 * math.pi * 164.81 * t + 0.35)

    spiral_u = max(0.0, min(1.0, (t - 63.333333) / 17.0))
    spiral_fade = max(0.0, min(1.0, (97.0 - t) / 8.0))
    spiral = 0.014 * spiral_fade * sum(
        (0.5 + 0.5 * math.cos(2 * math.pi * spiral_u + octave * 0.19))
        * math.sin(2 * math.pi * (55.0 * (2 ** octave) * (2.0 ** spiral_u)) * t + octave * 0.41)
        for octave in range(5)
    )

    organ_env = max(0.0, min(1.0, (t - 78.333333) / 3.0)) * max(0.0, min(1.0, (97.0 - t) / 4.0))
    organ = organ_env * (0.022 * math.sin(2 * math.pi * 55.0 * t)
                         + 0.018 * math.sin(2 * math.pi * 82.407 * t + 0.15)
                         + 0.016 * math.sin(2 * math.pi * 110.0 * t + 0.3)
                         + 0.011 * math.sin(2 * math.pi * 164.81 * t + 0.5))

    cello_env = max(0.0, min(1.0, (t - 108.333333) / 0.5)) * max(0.0, min(1.0, (114.333333 - t) / 1.0))
    cello = 0.065 * cello_env * (math.sin(2 * math.pi * 55.0 * t) + 0.35 * math.sin(2 * math.pi * 82.407 * t + 0.2))
    hiss_env = max(0.0, min(1.0, (t - 117.0) / 0.25)) * max(0.0, min(1.0, (120.0 - t) / 0.4))
    hiss = 0.0035 * hiss_env * (math.sin(2 * math.pi * 1471.0 * t) + 0.6 * math.sin(2 * math.pi * 2381.0 * t + 0.6))

    base = crystal + vacuum + clock + spiral + organ + cello + hiss
    pulse = 0.86 + 0.14 * math.sin(2 * math.pi * (0.035 if t < 34 else 0.065) * t + 0.25 * math.sin(2 * math.pi * t / 18.0))
    left = (base + split_l) * pulse
    right = (base + split_r) * pulse
    return left, right


def render_score(path: Path) -> dict[str, Any]:
    def emit(temporary: Path) -> None:
        with wave.open(str(temporary), "wb") as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            for block_start in range(0, TOTAL_SAMPLES, BLOCK_SAMPLES):
                count = min(BLOCK_SAMPLES, TOTAL_SAMPLES - block_start)
                left, right = [], []
                for sample in range(block_start, block_start + count):
                    lval, rval = score_sample(sample)
                    left.append(lval)
                    right.append(rval)
                zero_overlap(block_start, left, right)
                write_float_block(wav, left, right)
    return write_wav_atomic(path, emit)


def noise_sample(t: float, seed: int) -> float:
    phase = (seed % 997) / 997.0 * 2.0 * math.pi
    return (0.52 * math.sin(2 * math.pi * 1731.0 * t + phase)
            + 0.31 * math.sin(2 * math.pi * 2933.0 * t + phase * 1.7)
            + 0.17 * math.sin(2 * math.pi * 6197.0 * t + phase * 2.3))


def event_sample(event_id: str, t: float, duration: float, seed: int) -> tuple[float, float]:
    env = max(0.0, 1.0 - t / duration)
    if event_id == "silence":
        return 0.0, 0.0
    if event_id == "crystalline_ticks":
        phase = t % 0.42
        note = (784.0, 1046.5, 1318.5, 1568.0, 2093.0)[min(4, int(t / 0.42) % 5)]
        value = 0.13 * math.sin(2 * math.pi * note * t) * math.exp(-phase * 8.0) * env
        pan = 0.68 + 0.28 * math.sin(t * 2.3)
    elif event_id == "guillotine":
        value = (0.20 * math.sin(2 * math.pi * 55.0 * t) * math.exp(-t * 5.0)
                 + 0.085 * math.sin(2 * math.pi * 440.0 * t) * math.exp(-max(0.0, t - 0.18) * 4.2))
        pan = 0.82
    elif event_id == "vacuum38":
        value = (0.21 * math.sin(2 * math.pi * 38.0 * t) * math.exp(-t * 1.5)
                 + 0.032 * math.sin(2 * math.pi * 76.0 * t + 0.2) * math.exp(-t * 0.8))
        pan = 0.94
    elif event_id == "amber_clock":
        local = t % 2.5
        tick = math.exp(-local * 30.0) * math.sin(2 * math.pi * 930.0 * t)
        value = 0.12 * tick + 0.018 * math.sin(2 * math.pi * 52.0 * t) * (0.7 + 0.3 * math.sin(2 * math.pi * t / 2.5))
        pan = 0.76 + 0.16 * math.sin(t * 0.25)
    elif event_id == "mirror_split":
        ping = math.sin(2 * math.pi * 660.0 * t) * math.exp(-t * 2.3)
        overtone = 0.42 * math.sin(2 * math.pi * 990.0 * t + 0.4) * math.exp(-t * 2.0)
        return 0.13 * (ping + overtone), 0.13 * (-ping + overtone)
    elif event_id == "shepard":
        u = t / duration
        value = 0.04 * sum((0.5 + 0.5 * math.cos(2 * math.pi * u + octave * 0.2))
                           * math.sin(2 * math.pi * (55.0 * (2 ** octave) * (2.0 ** u)) * t + octave * 0.43)
                           for octave in range(5))
        pan = 0.82 + 0.14 * math.sin(t * 0.38)
    elif event_id == "organ":
        fade = min(1.0, t / 0.5) * min(1.0, (duration - t) / 1.0)
        value = fade * (0.065 * math.sin(2 * math.pi * 55.0 * t)
                        + 0.052 * math.sin(2 * math.pi * 82.407 * t + 0.2)
                        + 0.045 * math.sin(2 * math.pi * 110.0 * t + 0.4)
                        + 0.028 * math.sin(2 * math.pi * 164.81 * t + 0.6))
        pan = 0.88
    elif event_id == "truth_drop":
        value = 0.28 * math.sin(2 * math.pi * (62.0 + 30.0 * t) * t) * math.exp(-t * 16.0)
        value += 0.11 * math.sin(2 * math.pi * 890.0 * t) * math.exp(-t * 28.0)
        pan = 0.9
    elif event_id == "glass_shatter":
        value = 0.075 * noise_sample(t, seed) * math.exp(-t * 0.78)
        for index, frequency in enumerate((1568.0, 2093.0, 2637.0, 3136.0)):
            delay = 0.05 * index
            local = max(0.0, t - delay)
            value += 0.035 * math.sin(2 * math.pi * frequency * local) * math.exp(-local * (2.2 + 0.25 * index)) if t >= delay else 0.0
        pan = 0.88 + 0.1 * math.sin(t * 1.1)
    elif event_id == "cello":
        fade = min(1.0, t / 0.35) * min(1.0, (duration - t) / 0.7)
        value = fade * (0.14 * math.sin(2 * math.pi * 55.0 * t)
                        + 0.055 * math.sin(2 * math.pi * 110.0 * t + 0.2)
                        + 0.025 * math.sin(2 * math.pi * 165.0 * t + 0.4))
        pan = 0.91
    else:  # thermal
        fade = min(1.0, t / 0.08) * min(1.0, (duration - t) / 0.4)
        value = fade * (0.085 * noise_sample(t, seed) + 0.018 * math.sin(2 * math.pi * 58.0 * t))
        pan = 0.78 + 0.15 * math.sin(t * 1.7)
    return value * min(1.0, pan), value * max(0.0, 1.0 - pan * 0.2)


def render_sfx(path: Path, events: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    mapped = []
    for event in events:
        event_id = event["id"]
        duration_samples = round(SFX_DURATIONS[event_id] * SAMPLE_RATE)
        start = event["frame"] * SAMPLES_PER_FRAME
        mapped.append({
            "id": event_id,
            "frame": event["frame"],
            "startSample": start,
            "durationSamples": duration_samples,
            "endSampleExclusive": start + duration_samples,
            "durationSeconds": SFX_DURATIONS[event_id],
            "deterministicSeed": int.from_bytes(hashlib.sha256(event_id.encode("utf-8")).digest()[:4], "big"),
        })
    for event in mapped:
        if event["id"] != "silence" and event["startSample"] < SILENCE_END and event["endSampleExclusive"] > SILENCE_START:
            raise AudioBuildError(f"SFX {event['id']} overlaps the absolute-silence interval")

    def emit(temporary: Path) -> None:
        with wave.open(str(temporary), "wb") as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            for block_start in range(0, TOTAL_SAMPLES, BLOCK_SAMPLES):
                count = min(BLOCK_SAMPLES, TOTAL_SAMPLES - block_start)
                left, right = [0.0] * count, [0.0] * count
                block_end = block_start + count
                for event in mapped:
                    start = max(block_start, event["startSample"])
                    end = min(block_end, event["endSampleExclusive"])
                    if event["id"] == "silence" or end <= start:
                        continue
                    duration = event["durationSeconds"]
                    seed = event["deterministicSeed"]
                    for absolute in range(start, end):
                        t = (absolute - event["startSample"]) / SAMPLE_RATE
                        lval, rval = event_sample(event["id"], t, duration, seed)
                        dest = absolute - block_start
                        left[dest] += lval
                        right[dest] += rval
                zero_overlap(block_start, left, right)
                write_float_block(wav, left, right)
    return write_wav_atomic(path, emit), mapped


def silence_peak(path: Path) -> int:
    with wave.open(str(path), "rb") as wav:
        params = wav.getparams()
        if (params.framerate, params.nchannels, params.sampwidth, params.nframes) != (SAMPLE_RATE, 2, 2, TOTAL_SAMPLES):
            raise AudioBuildError(f"{path.name} has unexpected format/duration")
        peak = 0
        position = 0
        while position < TOTAL_SAMPLES:
            count = min(BLOCK_SAMPLES, TOTAL_SAMPLES - position)
            raw = wav.readframes(count)
            if len(raw) != count * 4:
                raise AudioBuildError(f"{path.name} has a short PCM read")
            overlap_start = max(position, SILENCE_START)
            overlap_end = min(position + count, SILENCE_END)
            if overlap_end > overlap_start:
                begin = (overlap_start - position) * 4
                finish = (overlap_end - position) * 4
                samples = array.array("h")
                samples.frombytes(raw[begin:finish])
                if sys.byteorder != "little":
                    samples.byteswap()
                peak = max(peak, max((abs(value) for value in samples), default=0))
            position += count
    return peak


def run_ffmpeg(args: list[str], label: str) -> str:
    result = subprocess.run(args, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode:
        detail = (result.stderr or result.stdout or "").strip().splitlines()[-8:]
        raise AudioBuildError(f"{label} failed (exit {result.returncode}): {' | '.join(detail)}")
    return result.stderr or ""


def loudnorm_measurements(output: str) -> dict[str, Any]:
    matches = list(re.finditer(r"\{\s*\"input_i\"[\s\S]*?\}", output))
    if not matches:
        raise AudioBuildError("FFmpeg loudnorm returned no measurement JSON")
    value = json.loads(matches[-1].group(0))
    needed = ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")
    if any(key not in value for key in needed):
        raise AudioBuildError("FFmpeg loudnorm measurement is incomplete")
    return value


def ebur128(path: Path) -> dict[str, float]:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise AudioBuildError("ffmpeg is required for final loudness validation")
    output = run_ffmpeg([ffmpeg, "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"], "ebur128")
    integrated = re.search(r"^\s*I:\s*(-?\d+(?:\.\d+)?)\s+LUFS\s*$", output, re.MULTILINE)
    true_peak = re.search(r"^\s*True peak:\s*(-?\d+(?:\.\d+)?)\s+dBTP\s*$", output, re.MULTILINE)
    if true_peak is None:
        true_peak = re.search(r"True peak:\s*\n\s*Peak:\s*(-?\d+(?:\.\d+)?)\s+dBFS", output)
    if integrated is None or true_peak is None:
        raise AudioBuildError("FFmpeg ebur128 did not report integrated LUFS and true peak")
    return {"integratedLUFS": float(integrated.group(1)), "truePeakDBTP": float(true_peak.group(1))}


def force_exact_silence(path: Path) -> None:
    temporary = path.with_name(path.stem + ".silence.tmp.wav")
    if temporary.exists():
        raise AudioBuildError(f"preserving existing temporary file {temporary}")
    with wave.open(str(path), "rb") as source, wave.open(str(temporary), "wb") as target:
        params = source.getparams()
        if (params.framerate, params.nchannels, params.sampwidth, params.nframes) != (SAMPLE_RATE, 2, 2, TOTAL_SAMPLES):
            raise AudioBuildError("master dimensions changed before exact-silence correction")
        target.setparams(params)
        position = 0
        while position < TOTAL_SAMPLES:
            count = min(BLOCK_SAMPLES, TOTAL_SAMPLES - position)
            raw = bytearray(source.readframes(count))
            if len(raw) != count * 4:
                raise AudioBuildError("master PCM payload is physically short")
            lo, hi = max(position, SILENCE_START), min(position + count, SILENCE_END)
            if hi > lo:
                raw[(lo - position) * 4:(hi - position) * 4] = bytes((hi - lo) * 4)
            target.writeframesraw(raw)
            position += count
    temporary.replace(path)


def prepare_s09_window() -> int:
    """Create only the root-approved playback copy, retaining source PCM exactly."""
    manifest = read_json(PROVIDER_MANIFEST_PATH)
    entries = manifest.get("segments", {})
    entry = entries.get("S09")
    if not isinstance(entry, dict):
        raise AudioBuildError("provider manifest has no S09 source cue entry")
    source = CUES / "S09.wav"
    values, source_info = wav_read(source, expected_channels=1)
    if entry.get("cue_sha256") != source_info["sha256"]:
        raise AudioBuildError("S09 source cue differs from its provider manifest; preserving it")
    if len(values) != 449_280:
        raise AudioBuildError(f"S09 source cue must contain 449280 samples, found {len(values)}")
    head = values[:9_600]
    tail = values[-7_680:]
    if any(head) or any(tail):
        raise AudioBuildError("root-approved S09 boundary-zero ranges are not exact digital silence")
    interior = values[9_600:-7_680]
    if len(interior) != 432_000:
        raise AudioBuildError("S09 interior sample count is not exactly 432000")
    interior_bytes = interior.tobytes()
    if sys.byteorder != "little":
        # Source/derived WAVs are little-endian; canonicalize the bytes used as evidence.
        interior_copy = array.array("h", interior)
        interior_copy.byteswap()
        interior_bytes = interior_copy.tobytes()
    target = CUES / "S09-window.wav"
    if target.exists():
        derived, derived_info = wav_read(target, expected_channels=1)
        if derived.tobytes() != interior.tobytes():
            raise AudioBuildError("existing S09-window.wav diverges from the approved source interior; preserving it")
    else:
        temporary = target.with_name(target.stem + ".tmp.wav")
        if temporary.exists():
            raise AudioBuildError("preserving existing temporary S09-window output")
        with wave.open(str(temporary), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(interior_bytes)
        derived, derived_info = wav_read(temporary, expected_channels=1)
        if derived.tobytes() != interior.tobytes():
            temporary.unlink(missing_ok=True)
            raise AudioBuildError("S09 derived WAV did not preserve every interior PCM sample")
        temporary.replace(target)
        derived_info["sha256"] = sha256_file(target)
    if derived_info["samplesPerChannel"] != 432_000 or derived.tobytes() != interior.tobytes():
        raise AudioBuildError("S09 derived cue failed exact length/interior-equality validation")
    active = active_bounds(derived)
    override = {
        "decision": "Root approved removing exactly verified boundary zeros for playback; source/raw/canonical cue remain immutable; no spoken sample removed and no speed change applied.",
        "policy": "exact_boundary_silence_trim_only",
        "source_cue_path": "public/audio/cues/S09.wav",
        "source_cue_sha256": source_info["sha256"],
        "source_pcm_sha256": source_info["pcmSha256"],
        "source_samples_48k": 449_280,
        "trim_start_samples": 9_600,
        "trim_end_samples": 7_680,
        "trim_start_seconds": 0.2,
        "trim_end_seconds": 0.16,
        "boundary_zero_evidence": {
            "head_samples": 9_600,
            "head_max_abs_pcm16": max((abs(value) for value in head), default=0),
            "head_rms_pcm16": 0.0,
            "tail_samples": 7_680,
            "tail_max_abs_pcm16": max((abs(value) for value in tail), default=0),
            "tail_rms_pcm16": 0.0,
        },
        "path": "public/audio/cues/S09-window.wav",
        "sha256": derived_info["sha256"],
        "pcm_sha256": derived_info["pcmSha256"],
        "retained_pcm_sha256": sha256_bytes(interior_bytes),
        "retained_pcm_byte_equal_to_source_slice": True,
        "playback_samples_48k": 432_000,
        "playback_duration_seconds": 9.0,
        "active_pcm_48k_after_trim": active,
    }
    old = entry.get("playback_override")
    if old is not None:
        old_comparison, new_comparison = dict(old), dict(override)
        old_comparison.pop("active_pcm_48k_after_trim", None)
        new_comparison.pop("active_pcm_48k_after_trim", None)
        if old_comparison != new_comparison:
            raise AudioBuildError("provider manifest already contains divergent S09 playback override evidence; preserving it")
    entry["playback_override"] = override
    manifest["playback_override_note"] = "Root-approved S09 exact-boundary-zero playback copy; the original provider cue and raw/canonical assets are preserved."
    expected_ids = {f"S{i:02d}" for i in range(1, 8)} | {"S08a", "S08b", "S09", "S10"}
    if expected_ids.issubset(entries):
        manifest["status"] = "complete_with_root_approved_s09_boundary_silence_playback_copy"
    write_json(PROVIDER_MANIFEST_PATH, manifest)
    print(json.dumps({"status": "s09_playback_copy_verified", "sourceSha256": source_info["sha256"], "playbackSha256": derived_info["sha256"], "samplesAt48k": 432_000, "activeAfterTrim": active, "retainedPcmByteEqual": True}, ensure_ascii=False, indent=2))
    return 0


def mix_master() -> dict[str, Any]:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise AudioBuildError("ffmpeg is required to build the PCM master")
    narration, score, sfx = (AUDIO / f"{name}.wav" for name in ("narration", "score", "sfx"))
    master = AUDIO / "master.wav"
    normalized = AUDIO / "master-normalized.tmp.wav"
    working = AUDIO / "master-work.wav"
    if master.exists() or normalized.exists() or working.exists():
        raise AudioBuildError("preserving existing master output or temporary file")

    common = (
        "[0:a]asplit=2[voice_sc][voice_mix];"
        "[1:a]equalizer=f=1200:t=q:w=0.75:g=-4,equalizer=f=2500:t=q:w=0.75:g=-4,equalizer=f=3700:t=q:w=0.75:g=-4[score_carved];"
        "[score_carved][voice_sc]sidechaincompress=threshold=0.035:ratio=5:attack=20:release=250:makeup=1[score_ducked];"
        "[2:a]equalizer=f=1200:t=q:w=0.75:g=-4,equalizer=f=2500:t=q:w=0.75:g=-4,equalizer=f=3700:t=q:w=0.75:g=-4[sfx_carved];"
        "[sfx_carved][voice_sc]sidechaincompress=threshold=0.035:ratio=3:attack=10:release=200:makeup=1[sfx_ducked];"
        f"[voice_mix][score_ducked][sfx_ducked]amix=inputs=3:duration=longest:normalize=0,aresample={SAMPLE_RATE},apad,atrim=end_sample={TOTAL_SAMPLES},asetpts=PTS-STARTPTS[mix]"
    )
    first = run_ffmpeg([
        ffmpeg, "-hide_banner", "-nostats", "-i", str(narration), "-i", str(score), "-i", str(sfx),
        "-filter_complex", common + ";[mix]loudnorm=I=-17:TP=-1.8:LRA=9:print_format=json[out]",
        "-map", "[out]", "-ar", str(SAMPLE_RATE), "-ac", "2", "-f", "null", "-",
    ], "first-pass loudnorm measurement")
    first_stats = loudnorm_measurements(first)
    second_filter = (
        common + ";[mix]loudnorm=I=-17:TP=-1.8:LRA=9"
        + f":measured_I={first_stats['input_i']}:measured_TP={first_stats['input_tp']}"
        + f":measured_LRA={first_stats['input_lra']}:measured_thresh={first_stats['input_thresh']}"
        + f":offset={first_stats['target_offset']}:linear=true:print_format=json,"
        "aresample=192000,alimiter=limit=0.8128:level=false:latency=true,aresample=48000,"
        f"apad,atrim=end_sample={TOTAL_SAMPLES}[out]"
    )
    second = run_ffmpeg([
        ffmpeg, "-hide_banner", "-nostats", "-y", "-i", str(narration), "-i", str(score), "-i", str(sfx),
        "-filter_complex", second_filter, "-map", "[out]", "-ar", str(SAMPLE_RATE), "-ac", "2",
        "-c:a", "pcm_s16le", str(normalized),
    ], "second-pass loudnorm render with oversampled limiter")
    second_stats = loudnorm_measurements(second)
    _, info = wav_read(normalized, expected_channels=2)
    if info["samplesPerChannel"] != TOTAL_SAMPLES:
        normalized.unlink(missing_ok=True)
        raise AudioBuildError(f"normalized render has {info['samplesPerChannel']} samples/channel, expected {TOTAL_SAMPLES}")
    normalized.replace(working)
    force_exact_silence(working)
    final = ebur128(working)
    if final["truePeakDBTP"] > -1.0:
        raise AudioBuildError(f"final true peak {final['truePeakDBTP']} dBTP exceeds -1.0 dBTP")
    if not -18.0 <= final["integratedLUFS"] <= -16.0:
        raise AudioBuildError(f"final loudness {final['integratedLUFS']} LUFS is outside -18 to -16 LUFS")
    if silence_peak(working) != 0:
        raise AudioBuildError("master is not exact zero throughout [4656000,4680000)")
    _, final_info = wav_read(working, expected_channels=2)
    working.replace(master)
    final_info.update({
        "strictDecode": "passed",
        "loudnormFirstPass": first_stats,
        "loudnormSecondPass": second_stats,
        "ebur128Final": final,
        "loudnormTarget": {"integratedLUFS": -17.0, "truePeakDBTP": -1.8, "acceptanceTruePeakDBTP": -1.0, "passes": 2},
        "oversampledLimiter": "aresample=192000, alimiter=limit=0.8128:level=false:latency=true, aresample=48000",
    })
    return final_info


def run_mix(segments: list[dict[str, Any]], events: list[dict[str, Any]], event_data: dict[str, Any]) -> int:
    measured, missing = load_cues(segments)
    if missing:
        print(json.dumps({"status": "ready_blocked", "reason": "missing local cue PCM", "missingCueIds": missing}, ensure_ascii=False, indent=2))
        return 2
    overflow = [item for item in measured if not item["fits"]]
    if overflow:
        print(json.dumps({
            "status": "needs_sol_fit",
            "reason": "one or more complete cue WAVs exceed their authored spoken window; no trim or speed change was applied",
            "cues": [{
                "id": item["id"], "samplesAt48k": item["samples"], "durationSeconds": item["durationSeconds"],
                "slotSamples": item["slotSamples"], "active": item["active"], "activeOverflowSamples": item["activeOverflowSamples"],
            } for item in overflow],
        }, ensure_ascii=False, indent=2))
        return 3
    output_paths = [AUDIO / name for name in ("narration.wav", "score.wav", "sfx.wav", "master.wav")]
    existing = [str(path.relative_to(DELIVERY)) for path in output_paths if path.exists()]
    if existing:
        raise AudioBuildError("preserving existing audio outputs: " + ", ".join(existing))

    AUDIO.mkdir(parents=True, exist_ok=True)
    narration_info = render_narration(AUDIO / "narration.wav", measured)
    score_info = render_score(AUDIO / "score.wav")
    sfx_info, event_map = render_sfx(AUDIO / "sfx.wav", events)
    for path in output_paths[:3]:
        if silence_peak(path) != 0:
            raise AudioBuildError(f"{path.name} violates exact silence samples [{SILENCE_START},{SILENCE_END})")
    master_info = mix_master()
    segment_records, captions = make_captions(segments, measured)
    timing = {
        "durationSeconds": DURATION_SECONDS,
        "fps": FPS,
        "sampleRate": SAMPLE_RATE,
        "samplesPerChannel": TOTAL_SAMPLES,
        "status": "measured_pcm_with_estimated_phrase_timing",
        "captionTimingMethod": "phrases weighted by display-text length inside measured active PCM spans; not ASR or word alignment",
        "silence": {"startFrame": SILENCE_START_FRAME, "endFrameExclusive": SILENCE_END_FRAME, "startSample": SILENCE_START, "endSampleExclusive": SILENCE_END},
        "playbackAdjustments": [item["playbackAdjustment"] for item in measured if item.get("playbackAdjustment")],
        "segments": segment_records,
        "captions": captions,
        "sfxOnsets": event_map,
    }
    write_captions_srt(captions)
    write_json(TIMING_PATH, timing)
    settings = {
        "version": 1,
        "durationSeconds": DURATION_SECONDS,
        "fps": FPS,
        "sampleRate": SAMPLE_RATE,
        "samplesPerFrame": SAMPLES_PER_FRAME,
        "samplesPerChannel": TOTAL_SAMPLES,
        "channels": 2,
        "renderer": "deterministic local procedural score/SFX plus measured PCM narration",
        "ducking": {"ratio": {"score": 5, "sfx": 3}, "attackMs": 20, "releaseMs": 250},
        "voiceBandCarve": {"bandsHz": [1200, 2500, 3700], "q": 0.75, "gainDB": -4, "appliedTo": ["score", "sfx"]},
        "loudness": {"targetLUFS": -17, "targetTruePeakDBTP": -1.8, "acceptanceLUFS": [-18, -16], "maximumTruePeakDBTP": -1.0, "passes": 2},
        "oversampledLimiter": "aresample=192000, alimiter=limit=0.8128:level=false:latency=true, aresample=48000",
        "absoluteSilence": {"startFrame": SILENCE_START_FRAME, "endFrameExclusive": SILENCE_END_FRAME, "startSample": SILENCE_START, "endSampleExclusive": SILENCE_END, "allStemsExactZero": True},
        "outputs": {"narration": narration_info, "score": score_info, "sfx": sfx_info, "master": master_info},
        "captions": {"count": len(captions), "maxChineseCharsPerLine": 14, "maxLines": 2, "alignment": "estimated phrase timing"},
        "sourceEvents": event_data,
    }
    write_json(SETTINGS_PATH, settings)
    write_json(MIX_MANIFEST_PATH, {
        "version": 1,
        "status": "built",
        "audioTiming": str(TIMING_PATH.relative_to(DELIVERY)),
        "mixSettings": str(SETTINGS_PATH.relative_to(DELIVERY)),
        "outputs": settings["outputs"],
        "cueHashes": [{"id": item["id"], "sha256": item["sha256"], "samplesAt48k": item["samples"]} for item in measured],
        "eventOnsets": event_map,
    })
    print(json.dumps({"status": "mix_complete", "master": master_info, "silence": timing["silence"], "captionCount": len(captions)}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--audit", action="store_true", help="read-only sample-count and cue-fit audit")
    mode.add_argument("--mix", action="store_true", help="build narration/score/SFX stems and normalized master")
    mode.add_argument("--prepare-s09-window", action="store_true", help="create the explicitly approved S09 exact-boundary-zero playback copy")
    args = parser.parse_args()
    try:
        if args.prepare_s09_window:
            return prepare_s09_window()
        segments, events, event_data = load_sources()
        if args.audit:
            return audit(segments)
        return run_mix(segments, events, event_data)
    except (AudioBuildError, OSError, ValueError, wave.Error, OverflowError) as exc:
        print(f"audio_mix: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
