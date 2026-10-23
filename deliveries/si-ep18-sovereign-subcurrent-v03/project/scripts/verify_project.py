#!/usr/bin/env python3
"""Verify EP18 v03 source, timing, caption, audio, font, and media bindings.

The report distinguishes measured file/sample facts from estimated phrase
caption timing. It does not perform ASR or claim human/device acceptance.
"""

from __future__ import annotations

import hashlib
import html
import json
import math
import re
import struct
import sys
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


PROJECT = Path(__file__).resolve().parents[1]
DELIVERY = PROJECT.parent
REPORT_PATH = DELIVERY / "review" / "project-verification.json"
WORK_ID = "si-ep18-sovereign-subcurrent-v03"
WORK_TITLE = "心印潜流 · v03"
EXPECTED_IDS = [f"S{i:02d}" for i in range(1, 9)]
FPS = 60
SAMPLE_RATE = 48_000
SAMPLES_PER_FRAME = SAMPLE_RATE // FPS
TOTAL_FRAMES = 5_400
TOTAL_SAMPLES = TOTAL_FRAMES * SAMPLES_PER_FRAME
SILENCE_FRAMES = (4_860, 4_890)
SILENCE_SAMPLES = tuple(frame * SAMPLES_PER_FRAME for frame in SILENCE_FRAMES)
# The preserved attachment is part of this portable editable delivery.
ATTACHMENT = DELIVERY / "source" / "script.md"


class ContractError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fingerprint(path: Path) -> dict[str, Any]:
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    stable = (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    return {"sha256": digest.hexdigest(), "bytes": after.st_size, "stableDuringHash": stable}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def resolve_inside(path_value: Any, root: Path) -> Path | None:
    if not isinstance(path_value, str) or not path_value.strip():
        return None
    candidate = (root / path_value).resolve()
    resolved_root = root.resolve()
    if candidate.is_relative_to(resolved_root) and candidate.is_file():
        return candidate
    return None


def strip_newlines(value: str) -> str:
    return value.replace("\r", "").replace("\n", "")


def sanitized_error(exc: Exception) -> str:
    message = str(exc)
    for local_root in (str(DELIVERY), str(PROJECT), str(Path.home())):
        if local_root:
            message = message.replace(local_root, "<local>")
    return message


def attachment_rows(markdown: str) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for line in markdown.splitlines():
        cells = line.split("|")
        if len(cells) < 6:
            continue
        match = re.fullmatch(r"\s*\*\*(S\d{2})\*\*\s*", cells[1])
        if not match:
            continue
        cue_id = match.group(1)
        display = re.sub(r"<br\s*/?>", "", html.unescape(cells[3]), flags=re.IGNORECASE).strip()
        spoken = html.unescape(cells[4]).strip()
        if cue_id in rows:
            raise ContractError(f"Attachment table repeats {cue_id}")
        rows[cue_id] = {"display_subtitle": display, "tts_phonetic_text": spoken}
    return rows


def pcm_wav_info(path: Path) -> dict[str, Any]:
    """Read PCM chunk metadata and physical sample payload, including streaming WAV headers."""
    raw = path.read_bytes()
    if len(raw) < 12 or raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise ContractError(f"{path.name} is not a RIFF/WAVE file")
    riff_declared = struct.unpack_from("<I", raw, 4)[0] + 8
    offset = 12
    fmt: dict[str, int] | None = None
    data_start: int | None = None
    data_declared: int | None = None
    while offset + 8 <= len(raw):
        tag = raw[offset:offset + 4]
        chunk_size = struct.unpack_from("<I", raw, offset + 4)[0]
        start = offset + 8
        available = len(raw) - start
        if tag == b"fmt ":
            if chunk_size < 16 or chunk_size > available:
                raise ContractError(f"{path.name} has an invalid or truncated PCM format chunk")
            code, channels, rate, byte_rate, block_align, bits = struct.unpack_from("<HHIIHH", raw, start)
            fmt = {"formatCode": code, "channels": channels, "sampleRateHz": rate,
                   "byteRate": byte_rate, "blockAlign": block_align, "bitsPerSample": bits}
        elif tag == b"data":
            data_start, data_declared = start, chunk_size
            break
        else:
            if chunk_size > available:
                raise ContractError(f"{path.name} contains a truncated {tag!r} chunk")
        offset = start + chunk_size + (chunk_size & 1)
    if fmt is None or data_start is None or data_declared is None:
        raise ContractError(f"{path.name} has no complete fmt/data chunk pair")
    width = fmt["bitsPerSample"] // 8
    if fmt["formatCode"] != 1 or width < 1 or fmt["blockAlign"] != fmt["channels"] * width:
        raise ContractError(f"{path.name} is not consistently described integer PCM")
    physical_payload_bytes = min(data_declared, max(0, len(raw) - data_start))
    if physical_payload_bytes == 0 or physical_payload_bytes % fmt["blockAlign"]:
        raise ContractError(f"{path.name} has an empty or unaligned physical PCM payload")
    payload = raw[data_start:data_start + physical_payload_bytes]
    physical_end = data_start + physical_payload_bytes + (physical_payload_bytes & 1)
    header_mismatch = riff_declared != len(raw) or data_declared != physical_payload_bytes
    stream_repair_form = (
        riff_declared > len(raw)
        and data_declared > physical_payload_bytes
        and riff_declared == data_start + data_declared
        and physical_end == len(raw)
    )
    return {
        **fmt,
        "sampleFramesPerChannel": physical_payload_bytes // fmt["blockAlign"],
        "physicalBytes": len(raw),
        "riffDeclaredBytes": riff_declared,
        "dataDeclaredBytes": data_declared,
        "dataPhysicalBytes": physical_payload_bytes,
        "dataOffset": data_start,
        "payloadSha256": sha256_bytes(payload),
        "headerMismatch": header_mismatch,
        "streamingHeaderRepairForm": stream_repair_form,
    }


def main() -> int:
    if REPORT_PATH.exists():
        print("verify_project: refusing to overwrite existing project-verification.json", file=sys.stderr)
        return 2

    checks: list[dict[str, Any]] = []
    input_hashes: dict[str, Any] = {}
    loaded: dict[str, Any] = {}
    input_paths = {
        "delivery": (DELIVERY / "delivery.json", "delivery.json"),
        "segments": (PROJECT / "segments.json", "project/segments.json"),
        "captions": (PROJECT / "captions.json", "project/captions.json"),
        "authorization": (PROJECT / "audio-authorization.json", "project/audio-authorization.json"),
        "audioPlan": (PROJECT / "audio-plan.json", "project/audio-plan.json"),
        "audioTiming": (PROJECT / "audio-timing.json", "project/audio-timing.json"),
        "timeline": (PROJECT / "timeline.json", "project/timeline.json"),
        "sfxEvents": (PROJECT / "sfx_events.json", "project/sfx_events.json"),
        "fontSources": (PROJECT / "font-sources.json", "project/font-sources.json"),
        "synthesis": (DELIVERY / "review" / "audio-synthesis.json", "review/audio-synthesis.json"),
        "frameSmoke": (DELIVERY / "review" / "frame-smoke-check.json", "review/frame-smoke-check.json"),
    }

    def record(name: str, passed: bool, details: Any) -> None:
        checks.append({"name": name, "status": "PASS" if passed else "FAIL", "details": details})

    for key, (path, relative) in input_paths.items():
        try:
            loaded[key] = read_json(path)
            fp = fingerprint(path)
            input_hashes[relative] = fp
            record("read_" + key, fp["stableDuringHash"], {"path": relative, **fp})
        except (OSError, json.JSONDecodeError, UnicodeDecodeError, ContractError) as exc:
            loaded[key] = None
            input_hashes[relative] = {"status": "MISSING_OR_INVALID"}
            record("read_" + key, False, {"path": relative, "exceptionType": type(exc).__name__, "error": sanitized_error(exc)})

    delivery = loaded.get("delivery") if isinstance(loaded.get("delivery"), dict) else {}
    segments = loaded.get("segments") if isinstance(loaded.get("segments"), list) else []
    captions = loaded.get("captions") if isinstance(loaded.get("captions"), list) else []
    authorization = loaded.get("authorization") if isinstance(loaded.get("authorization"), dict) else {}
    audio_plan = loaded.get("audioPlan") if isinstance(loaded.get("audioPlan"), dict) else {}
    audio_timing = loaded.get("audioTiming") if isinstance(loaded.get("audioTiming"), dict) else {}
    timeline = loaded.get("timeline") if isinstance(loaded.get("timeline"), dict) else {}
    sfx = loaded.get("sfxEvents") if isinstance(loaded.get("sfxEvents"), dict) else {}
    synthesis = loaded.get("synthesis") if isinstance(loaded.get("synthesis"), dict) else {}
    frame_smoke = loaded.get("frameSmoke") if isinstance(loaded.get("frameSmoke"), dict) else {}
    measured: dict[str, Any] = {}
    bindings: dict[str, Any] = {"inputFiles": input_hashes}

    def check_delivery() -> dict[str, Any]:
        outputs = delivery.get("outputs") if isinstance(delivery, dict) else None
        xhs = outputs.get("xiaohongshu") if isinstance(outputs, dict) else None
        values = {
            "slug": delivery.get("slug"), "title": delivery.get("title"),
            "platforms": delivery.get("platforms"), "durationSeconds": delivery.get("duration_seconds"),
            "fps": delivery.get("fps"), "totalFrames": delivery.get("total_frames"),
            "audioMaster": (delivery.get("audio") or {}).get("master") if isinstance(delivery.get("audio"), dict) else None,
            "output": xhs,
        }
        expected_output = "小红书/si-ep18-sovereign-subcurrent-v03-xiaohongshu-90s-portrait.mp4"
        passed = (
            values["slug"] == WORK_ID and values["title"] == WORK_TITLE
            and values["platforms"] == ["xiaohongshu"]
            and values["durationSeconds"] == 90 and values["fps"] == FPS
            and values["totalFrames"] == TOTAL_FRAMES
            and isinstance(xhs, dict) and xhs.get("path") == expected_output
            and (xhs.get("width"), xhs.get("height")) == (2160, 3840)
        )
        measured["deliveryIdentity"] = values
        return {"passed": passed, "details": values}

    def check_script_hash() -> dict[str, Any]:
        script = delivery.get("script") if isinstance(delivery.get("script"), dict) else {}
        path = resolve_inside(script.get("path"), DELIVERY)
        actual = fingerprint(path) if path else None
        expected = script.get("sha256")
        ok = bool(path and actual and actual["stableDuringHash"] and actual["sha256"] == expected)
        details = {"path": script.get("path"), "expectedSha256": expected, "actual": actual}
        bindings["sourceScript"] = details
        return {"passed": ok, "details": details}

    def check_attachment_text() -> dict[str, Any]:
        if not ATTACHMENT.is_file():
            return {"passed": False, "details": {"attachment": ATTACHMENT.name, "error": "source attachment is unavailable"}}
        raw = ATTACHMENT.read_bytes()
        text = raw.decode("utf-8")
        table = attachment_rows(text)
        current = {row.get("id"): row for row in segments if isinstance(row, dict)}
        issues: list[str] = []
        if list(current) != EXPECTED_IDS:
            issues.append("segments.json must contain S01-S08 in order")
        if set(table) != set(EXPECTED_IDS):
            issues.append("attachment narration table must contain exactly S01-S08")
        for cue_id in EXPECTED_IDS:
            segment, source_row = current.get(cue_id), table.get(cue_id)
            if segment is None or source_row is None:
                issues.append(cue_id + " is missing from the segment or attachment table")
                continue
            for field in ("display_subtitle", "tts_phonetic_text"):
                actual = segment.get(field)
                if not isinstance(actual, str) or actual != source_row[field]:
                    issues.append(cue_id + " " + field + " differs from the attachment table")
        attachment_fp = fingerprint(ATTACHMENT)
        bindings["attachment"] = {"name": ATTACHMENT.name, **attachment_fp}
        return {"passed": not issues and attachment_fp["stableDuringHash"], "details": {"issues": issues, "cueIds": sorted(table), "attachmentSha256": attachment_fp["sha256"], "attachmentName": ATTACHMENT.name}}

    def check_authorization() -> dict[str, Any]:
        issues: list[str] = []
        if authorization.get("authorized") is not True:
            issues.append("audio-authorization.json is not marked authorized")
        if audio_plan.get("model") != authorization.get("model"):
            issues.append("audio plan model differs from current authorization")
        if audio_plan.get("voice") != authorization.get("voice"):
            issues.append("audio plan voice differs from current authorization")
        texts = [row.get("tts_phonetic_text") for row in segments if isinstance(row, dict)]
        actual_hash = sha256_bytes(json.dumps(texts, ensure_ascii=False).encode("utf-8"))
        expected_hash = authorization.get("ordered_text_sha256")
        if actual_hash != expected_hash:
            issues.append("ordered prepared narration hash differs from audio authorization")
        details = {
            "authorized": authorization.get("authorized"), "provider": authorization.get("provider"),
            "model": authorization.get("model"), "voice": authorization.get("voice"),
            "preparedTextSha256": actual_hash, "authorizedTextSha256": expected_hash,
            "rate": audio_plan.get("rate"),
        }
        measured["narrationAuthorization"] = details
        bindings["authorization"] = input_hashes.get("project/audio-authorization.json")
        return {"passed": not issues, "details": {"issues": issues, **details}}

    def check_captions() -> dict[str, Any]:
        issues: list[str] = []
        segment_map = {row.get("id"): row for row in segments if isinstance(row, dict)}
        if [row.get("id") for row in segments if isinstance(row, dict)] != EXPECTED_IDS:
            issues.append("segments.json must contain exactly S01-S08 in order")
        previous_end = 0
        caption_texts: dict[str, list[str]] = {cue_id: [] for cue_id in EXPECTED_IDS}
        for index, row in enumerate(captions):
            if not isinstance(row, dict):
                issues.append(f"caption[{index}] must be an object")
                continue
            cue_id = row.get("id")
            start, end, text = row.get("startFrame"), row.get("endFrame"), row.get("text")
            if cue_id not in segment_map:
                issues.append(f"caption[{index}] has no matching cue id")
            if not (is_int(start) and is_int(end) and 0 <= start < end <= TOTAL_FRAMES):
                issues.append(f"caption[{index}] does not have valid half-open frame bounds within 5400")
            else:
                if start < previous_end:
                    issues.append(f"caption[{index}] is out of order or overlaps the prior caption")
                previous_end = end
            if not isinstance(text, str) or not text:
                issues.append(f"caption[{index}] has no text")
                continue
            lines = text.replace("\r", "").split("\n")
            if len(lines) > 2 or any(len(line) > 17 for line in lines):
                issues.append(f"caption[{index}] exceeds two lines or 17 characters per line")
            if cue_id in caption_texts:
                caption_texts[cue_id].append(text)
        for cue_id in EXPECTED_IDS:
            segment = segment_map.get(cue_id)
            expected = segment.get("display_subtitle") if isinstance(segment, dict) else None
            actual = "".join(caption_texts[cue_id])
            if not isinstance(expected, str) or strip_newlines(actual) != strip_newlines(expected):
                issues.append(cue_id + " joined captions differ from display_subtitle")
        details = {"captionCount": len(captions), "cueCaptionCounts": {key: len(value) for key, value in caption_texts.items()}, "issues": issues}
        measured["captions"] = details
        return {"passed": not issues and bool(captions), "details": details}

    def check_timeline() -> dict[str, Any]:
        issues: list[str] = []
        acts = timeline.get("acts") if isinstance(timeline, dict) else None
        if timeline.get("durationFrames") != TOTAL_FRAMES or timeline.get("fps") != FPS:
            issues.append("timeline durationFrames/fps differ from 5400/60")
        if not isinstance(acts, list) or len(acts) != 4:
            issues.append("timeline must define exactly four acts")
        else:
            expected_start = 0
            for index, act in enumerate(acts):
                if not isinstance(act, dict):
                    issues.append(f"act[{index}] is not an object")
                    continue
                start, end = act.get("startFrame"), act.get("endFrame")
                if not (is_int(start) and is_int(end) and start == expected_start and start < end <= TOTAL_FRAMES):
                    issues.append(f"act[{index}] does not continue the half-open 0..5400 timeline")
                if is_int(end):
                    expected_start = end
            if expected_start != TOTAL_FRAMES:
                issues.append("four acts do not end at frame 5400")
        measured["timeline"] = {"actCount": len(acts) if isinstance(acts, list) else None, "acts": acts}
        return {"passed": not issues, "details": {"issues": issues, "acts": acts}}

    def check_events() -> dict[str, Any]:
        issues: list[str] = []
        if sfx.get("fps") != FPS or sfx.get("sampleRate") != SAMPLE_RATE:
            issues.append("sfx_events.json must declare 60 fps and 48000 Hz")
        if timeline.get("fps") != FPS:
            issues.append("timeline.json must declare 60 fps")
        sfx_rows = sfx.get("events") if isinstance(sfx, dict) else None
        timeline_rows = timeline.get("events") if isinstance(timeline, dict) else None
        if not isinstance(sfx_rows, list) or not isinstance(timeline_rows, list):
            issues.append("timeline and SFX event arrays are required")
            sfx_rows, timeline_rows = [], []

        def event_pairs(rows: list[Any], label: str) -> list[tuple[int, int]]:
            result: list[tuple[int, int]] = []
            for index, row in enumerate(rows):
                if not isinstance(row, dict) or not is_int(row.get("frame")) or not is_int(row.get("sampleIndex")):
                    issues.append(f"{label} event[{index}] lacks integer frame/sampleIndex")
                    continue
                frame, sample = row["frame"], row["sampleIndex"]
                if not (0 <= frame < TOTAL_FRAMES) or sample != frame * SAMPLES_PER_FRAME:
                    issues.append(f"{label} event[{index}] sampleIndex is not frame*800")
                result.append((frame, sample))
            return result

        sfx_pairs = event_pairs(sfx_rows, "sfx_events.json")
        timeline_pairs = event_pairs(timeline_rows, "timeline.json")
        if sorted(sfx_pairs) != sorted(timeline_pairs):
            issues.append("timeline events and sfx_events frame/sample maps differ")
        if (3_900, 3_900 * SAMPLES_PER_FRAME) not in sfx_pairs:
            issues.append("confirm event at frame 3900/sample 3120000 is missing")
        if (4_860, SILENCE_SAMPLES[0]) not in sfx_pairs:
            issues.append("silence-start event at frame 4860/sample 3888000 is missing")
        if (4_890, SILENCE_SAMPLES[1]) not in sfx_pairs:
            issues.append("post-silence event at frame 4890/sample 3912000 is missing")
        if sfx.get("silenceRangeFrames") != list(SILENCE_FRAMES):
            issues.append("sfx silence frame range must be [4860,4890)")
        if sfx.get("silenceRangeSamples") != list(SILENCE_SAMPLES):
            issues.append("sfx silence sample range must be [3888000,3912000)")
        details = {
            "sfxEventCount": len(sfx_pairs), "timelineEventCount": len(timeline_pairs),
            "confirmFrame3900Present": (3_900, 3_900 * SAMPLES_PER_FRAME) in sfx_pairs,
            "silenceRangeFramesHalfOpen": sfx.get("silenceRangeFrames"),
            "silenceRangeSamplesHalfOpen": sfx.get("silenceRangeSamples"), "issues": issues,
        }
        measured["events"] = details
        return {"passed": not issues, "details": details}

    def check_synthesis_and_timing() -> dict[str, Any]:
        issues: list[str] = []
        cues = synthesis.get("cues") if isinstance(synthesis, dict) else None
        timings = audio_timing.get("segments") if isinstance(audio_timing, dict) else None
        if not isinstance(cues, list) or len(cues) != 8:
            issues.append("audio-synthesis.json must contain exactly eight cues")
            cues = []
        if not isinstance(timings, list) or len(timings) != 8:
            issues.append("audio-timing.json must contain exactly eight measured cue windows")
            timings = []
        if audio_timing.get("status") != "MEASURED":
            issues.append("audio-timing.json status must be MEASURED")
        if (audio_timing.get("duration_seconds"), audio_timing.get("fps"), audio_timing.get("samples_per_channel")) != (90, FPS, TOTAL_SAMPLES):
            issues.append("audio timing header differs from 90s/60fps/4320000 samples")
        cue_map = {row.get("id"): row for row in cues if isinstance(row, dict)}
        timing_map = {row.get("id"): row for row in timings if isinstance(row, dict)}
        segment_map = {row.get("id"): row for row in segments if isinstance(row, dict)}
        if set(cue_map) != set(EXPECTED_IDS) or len(cue_map) != 8:
            issues.append("synthesis cue IDs must be unique S01-S08")
        if set(timing_map) != set(EXPECTED_IDS) or len(timing_map) != 8:
            issues.append("audio timing IDs must be unique S01-S08")
        cue_evidence: list[dict[str, Any]] = []
        expected_model = authorization.get("model")
        expected_voice = authorization.get("voice")
        plan_rate = audio_plan.get("rate")

        for cue_id in EXPECTED_IDS:
            cue, timing, segment = cue_map.get(cue_id), timing_map.get(cue_id), segment_map.get(cue_id)
            if not isinstance(cue, dict) or not isinstance(timing, dict) or not isinstance(segment, dict):
                issues.append(cue_id + " lacks a synthesis cue, timing row, or source segment")
                continue
            spoken = segment.get("tts_phonetic_text")
            text_sha = sha256_bytes(spoken.encode("utf-8")) if isinstance(spoken, str) else None
            if cue.get("spokenText") != spoken:
                issues.append(cue_id + " reported spokenText differs from prepared TTS text")
            if cue.get("textSha256") != text_sha:
                issues.append(cue_id + " textSha256 does not hash the exact prepared TTS text")
            if cue.get("actualModel") != expected_model or cue.get("actualVoice") != expected_voice:
                issues.append(cue_id + " actual model/voice differs from current authorization")

            raw_path = resolve_inside(cue.get("rawAudioFile"), PROJECT)
            canonical_path = resolve_inside(cue.get("canonicalAudioFile"), PROJECT)
            text_path = resolve_inside(cue.get("textFile"), PROJECT)
            if raw_path is None or canonical_path is None or text_path is None:
                issues.append(cue_id + " raw, canonical, or sent-text file path is missing or escapes project")
                cue_evidence.append({"id": cue_id, "status": "FAIL", "reason": "missing_or_unsafe_audio_path"})
                continue
            raw_fp, canonical_fp = fingerprint(raw_path), fingerprint(canonical_path)
            text_fp = fingerprint(text_path)
            raw_info, canonical_info = pcm_wav_info(raw_path), pcm_wav_info(canonical_path)
            if not raw_fp["stableDuringHash"] or raw_fp["sha256"] != cue.get("rawSha256"):
                issues.append(cue_id + " provider WAV hash differs or changed during hashing")
            if not canonical_fp["stableDuringHash"] or canonical_fp["sha256"] != cue.get("canonicalSha256"):
                issues.append(cue_id + " canonical WAV hash differs or changed during hashing")
            if text_fp["sha256"] != text_sha or not text_fp["stableDuringHash"] or text_path.read_text(encoding="utf-8") != spoken:
                issues.append(cue_id + " exact sent-text file does not match the authorized cue text/hash")
            if (raw_info["sampleRateHz"], raw_info["channels"], raw_info["bitsPerSample"]) != (24_000, 1, cue.get("providerBitsPerSample")):
                issues.append(cue_id + " raw provider WAV format differs from its measured 24 kHz mono metadata")
            if raw_info["sampleFramesPerChannel"] != cue.get("rawSampleCount"):
                issues.append(cue_id + " rawSampleCount differs from the physical provider WAV samples")
            raw_mismatch_repaired = cue.get("rawHeaderMismatchRepairedForCanonical") is True
            if raw_info["headerMismatch"] and not (raw_mismatch_repaired and raw_info["streamingHeaderRepairForm"]):
                issues.append(cue_id + " raw WAV header mismatch is not the recorded verified streaming form")
            if (canonical_info["sampleRateHz"], canonical_info["channels"], canonical_info["bitsPerSample"]) != (SAMPLE_RATE, 1, 16):
                issues.append(cue_id + " canonical cue is not mono 48 kHz PCM16")
            if canonical_info["headerMismatch"]:
                issues.append(cue_id + " canonical WAV has inconsistent RIFF/data lengths")

            canonical_frames = canonical_info["sampleFramesPerChannel"]
            raw_frames = raw_info["sampleFramesPerChannel"]
            if cue.get("sampleCount") != canonical_frames or cue.get("canonicalSampleCount") != canonical_frames:
                issues.append(cue_id + " reported canonical sample count differs from the WAV payload")
            duration_delta = abs(canonical_frames / SAMPLE_RATE - raw_frames / raw_info["sampleRateHz"])
            duration_tolerance = (1 / raw_info["sampleRateHz"]) + (1 / SAMPLE_RATE)
            duration_preserved = duration_delta <= duration_tolerance
            if not duration_preserved:
                issues.append(cue_id + " canonical conversion changed raw cue duration beyond resampling tolerance")
            if not isinstance(plan_rate, (int, float)) or isinstance(plan_rate, bool) or not isinstance(cue.get("rate"), (int, float)) or not math.isclose(float(cue["rate"]), float(plan_rate), rel_tol=0.0, abs_tol=1e-9):
                issues.append(cue_id + " synthesis rate differs from the current authorized audio plan")

            start_frame, end_frame = segment.get("startFrame"), segment.get("endFrame")
            placement = cue.get("placementStartFrameForFit")
            if not is_int(placement):
                issues.append(cue_id + " placement start is not an integer frame")
            elif cue_id == "S08" and placement < SILENCE_FRAMES[1]:
                issues.append("S08 placement begins before the 30-frame silence ends at frame 4890")
            elif cue_id != "S08" and placement != start_frame:
                issues.append(cue_id + " placement start differs from its source segment start")
            active_start = cue.get("activeStartSample")
            active_end = cue.get("activeEndSampleExclusive")
            if not (is_int(active_start) and is_int(active_end) and 0 <= active_start < active_end <= canonical_frames):
                issues.append(cue_id + " active PCM bounds are invalid or outside the complete canonical cue")
            else:
                active_start_frame = placement + active_start // SAMPLES_PER_FRAME
                active_end_frame = placement + (active_end + SAMPLES_PER_FRAME - 1) // SAMPLES_PER_FRAME
                if cue.get("activeStartFrame") != active_start_frame or cue.get("activeEndFrameExclusive") != active_end_frame:
                    issues.append(cue_id + " synthesis report active frame bounds differ from measured PCM samples")
                if timing.get("activeStartFrame") != active_start_frame or timing.get("activeEndFrameExclusive") != active_end_frame:
                    issues.append(cue_id + " audio-timing active frame window differs from measured PCM samples")
                if active_end_frame > end_frame:
                    issues.append(cue_id + " active PCM extends beyond its original source frame window")
            window_capacity_samples = (end_frame - placement) * SAMPLES_PER_FRAME if is_int(end_frame) and is_int(placement) else -1
            full_cue_fits = 0 <= canonical_frames <= window_capacity_samples
            if not full_cue_fits:
                issues.append(cue_id + " full canonical cue does not fit the source window without trimming/speed change")
            if cue.get("fitsFullCanonicalWindowWithoutTrimOrSpeedChange") is not True:
                issues.append(cue_id + " synthesis report does not confirm full-cue fit without trim/speed change")
            if cue.get("fitsOriginalWindowWithoutTrimOrSpeedChange") is not True:
                issues.append(cue_id + " synthesis report does not confirm active audio fits the original window")

            timing_path = timing.get("cuePath")
            expected_cue_path = str(canonical_path.relative_to(PROJECT))
            if timing_path != expected_cue_path or timing.get("sha256") != canonical_fp["sha256"]:
                issues.append(cue_id + " audio-timing cue path/hash does not bind the canonical PCM file")
            actual_duration = canonical_frames / SAMPLE_RATE
            if not isinstance(timing.get("actualDurationSeconds"), (int, float)) or abs(float(timing["actualDurationSeconds"]) - actual_duration) > (1 / SAMPLE_RATE):
                issues.append(cue_id + " audio-timing duration differs from complete canonical PCM length")
            if timing.get("placementStartFrame") != placement or timing.get("endFrame") != end_frame:
                issues.append(cue_id + " audio-timing placement/window differs from the measured cue record")

            sidecar_path = resolve_inside(cue.get("identitySidecarFile"), PROJECT)
            sidecar_sha = cue.get("identitySidecarSha256")
            sidecar_matches: bool | None = None
            if sidecar_path is not None:
                sidecar_fp = fingerprint(sidecar_path)
                try:
                    sidecar = read_json(sidecar_path)
                except (OSError, json.JSONDecodeError):
                    sidecar = None
                sidecar_matches = bool(
                    sidecar_fp["sha256"] == sidecar_sha and isinstance(sidecar, dict)
                    and sidecar.get("actualModel") == expected_model
                    and sidecar.get("actualVoice") == expected_voice
                    and sidecar.get("textSha256") == text_sha
                    and sidecar.get("rawSha256") == raw_fp["sha256"]
                )
                if not sidecar_matches:
                    issues.append(cue_id + " provider identity sidecar does not bind current model/voice/text/raw hash")
            elif sidecar_sha is not None or cue.get("identitySidecarFile") is not None:
                issues.append(cue_id + " declared provider identity sidecar is unavailable")

            cue_evidence.append({
                "id": cue_id, "actualModel": cue.get("actualModel"), "actualVoice": cue.get("actualVoice"),
                "spokenTextSha256": text_sha, "reportedTextSha256": cue.get("textSha256"),
                "providerWav": {"path": str(raw_path.relative_to(PROJECT)), **raw_fp, **raw_info},
                "canonicalWav": {"path": str(canonical_path.relative_to(PROJECT)), **canonical_fp, **canonical_info},
                "reportedRawHeaderRepair": raw_mismatch_repaired,
                "rawToCanonicalDurationSecondsDelta": duration_delta,
                "durationPreservedWithoutPostAcceleration": duration_preserved,
                "synthesisRate": cue.get("rate"), "authorizedPlanRate": plan_rate,
                "placementStartFrame": placement, "sourceEndFrame": end_frame,
                "fullCanonicalSamplesFitWithoutTrimOrSpeedChange": full_cue_fits,
                "providerIdentitySidecarMatches": sidecar_matches,
            })

        details = {
            "cueCount": len(cue_evidence), "cueEvidence": cue_evidence,
            "issues": issues,
            "captionAlignmentClaim": "estimated phrase weights within measured PCM activity; not exact ASR or word-level alignment",
        }
        measured["synthesisAndTiming"] = details
        return {"passed": not issues and len(cue_evidence) == 8, "details": details}

    def check_master() -> dict[str, Any]:
        audio = delivery.get("audio") if isinstance(delivery.get("audio"), dict) else {}
        path = resolve_inside(audio.get("master"), DELIVERY)
        if path is None:
            return {"passed": False, "details": {"error": "delivery PCM master is missing or outside the v03 delivery"}}
        before = path.stat()
        with wave.open(str(path), "rb") as wav:
            fmt = {
                "sampleRateHz": wav.getframerate(), "channels": wav.getnchannels(),
                "sampleWidthBytes": wav.getsampwidth(), "sampleFramesPerChannel": wav.getnframes(),
                "compressionType": wav.getcomptype(),
            }
            if (fmt["sampleRateHz"], fmt["channels"], fmt["sampleWidthBytes"], fmt["sampleFramesPerChannel"], fmt["compressionType"]) == (SAMPLE_RATE, 2, 2, TOTAL_SAMPLES, "NONE"):
                wav.setpos(SILENCE_SAMPLES[0])
                silence = wav.readframes(SILENCE_SAMPLES[1] - SILENCE_SAMPLES[0])
                silence_exact_zero = len(silence) == (SILENCE_SAMPLES[1] - SILENCE_SAMPLES[0]) * 4 and not any(silence)
            else:
                silence_exact_zero = False
        fp = fingerprint(path)
        after = path.stat()
        stable = (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns) and fp["stableDuringHash"]
        info = {"path": str(path.relative_to(DELIVERY)), **fp, "format": fmt,
                "exact30FrameSilence": {"framesHalfOpen": list(SILENCE_FRAMES), "samplesPerChannelHalfOpen": list(SILENCE_SAMPLES), "allStereoSamplesZero": silence_exact_zero},
                "stableDuringReadAndHash": stable}
        bindings["master"] = info
        measured["master"] = info
        passed = fmt == {"sampleRateHz": SAMPLE_RATE, "channels": 2, "sampleWidthBytes": 2,
                         "sampleFramesPerChannel": TOTAL_SAMPLES, "compressionType": "NONE"} and silence_exact_zero and stable
        return {"passed": passed, "details": info}

    def check_fonts() -> dict[str, Any]:
        declared = loaded.get("fontSources")
        issues: list[str] = []
        if not isinstance(declared, list) or not declared:
            return {"passed": False, "details": {"issues": ["font-sources.json must be a non-empty array"]}}
        by_path: dict[str, dict[str, Any]] = {}
        records: list[dict[str, Any]] = []
        for item in declared:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                issues.append("font source entry is not a path-bearing object")
                continue
            relative = item["path"]
            if relative in by_path:
                issues.append("font source path is duplicated: " + relative)
                continue
            by_path[relative] = item
            path = resolve_inside(relative, PROJECT)
            if path is None:
                issues.append("declared font/license file is missing or escapes project: " + relative)
                continue
            fp = fingerprint(path)
            declared_sha, declared_bytes = item.get("sha256"), item.get("bytes")
            matched = (fp["sha256"] == declared_sha and fp["bytes"] == declared_bytes and fp["stableDuringHash"])
            if not matched:
                issues.append("font/license file SHA or byte count differs from font-sources.json: " + relative)
            if not isinstance(item.get("source"), str) or not item["source"].startswith("https://"):
                issues.append("font/license source URL is missing: " + relative)
            if not isinstance(item.get("license"), str) or not item["license"].strip():
                issues.append("font/license declaration is missing: " + relative)
            records.append({"path": relative, **fp, "declaredSource": item.get("source"),
                            "declaredLicense": item.get("license"), "matchesDeclaredSha256AndBytes": matched})

        film_source = PROJECT / "src" / "Film.tsx"
        used_names: list[str] = []
        if film_source.is_file():
            used_names = re.findall(r"staticFile\(['\"]fonts/([^'\"]+)['\"]\)", film_source.read_text(encoding="utf-8"))
        if not used_names:
            issues.append("Film.tsx contains no statically declared bundled font files")
        for name in sorted(set(used_names)):
            relative = "public/fonts/" + name
            if relative not in by_path:
                issues.append("used font is not covered by font-sources.json: " + relative)
                continue
            font_entry = by_path[relative]
            if not isinstance(font_entry.get("license"), str) or not font_entry.get("license"):
                issues.append("used font has no declared license: " + relative)
            expected_license_file = "public/fonts/" + Path(name).stem + "-OFL.txt"
            if expected_license_file not in by_path:
                issues.append("used font has no corresponding bundled OFL text: " + expected_license_file)
            elif by_path[expected_license_file].get("license") != font_entry.get("license"):
                issues.append("font and bundled OFL text declare different licenses: " + relative)
        details = {"usedFontFiles": sorted(set(used_names)), "declaredFiles": records, "issues": issues}
        measured["fontSources"] = details
        return {"passed": not issues and bool(records), "details": details}

    def check_sources_and_frame_smoke() -> dict[str, Any]:
        source_root = PROJECT / "src"
        source_files = sorted(path for path in source_root.rglob("*") if path.is_file()) if source_root.is_dir() else []
        issues: list[str] = []
        forbidden = re.compile(r"\bMath\s*\.\s*random\s*\(|\bDate\s*\.\s*now\s*\(|\bperspective\s*\(|\brotateX\s*\(|\brotateY\s*\(|\bWebGL\b", re.IGNORECASE)
        source_hashes: dict[str, Any] = {}
        hits: list[str] = []
        for path in source_files:
            relative = "project/src/" + str(path.relative_to(source_root))
            fp = fingerprint(path)
            source_hashes[relative] = fp
            if not fp["stableDuringHash"]:
                issues.append(relative + " changed during hashing")
            try:
                source = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                issues.append(relative + " could not be read as UTF-8: " + str(exc))
                continue
            for line_number, line in enumerate(source.splitlines(), start=1):
                if forbidden.search(line):
                    hits.append(f"{relative}:{line_number}")
        if not source_files:
            issues.append("project/src is missing or empty")
        if hits:
            issues.extend("forbidden source token at " + hit for hit in hits)
        smoke = frame_smoke if isinstance(frame_smoke, dict) else {}
        smoke_sources = smoke.get("sourceSha256") if isinstance(smoke.get("sourceSha256"), dict) else {}
        current_scene = source_hashes.get("project/src/Scene.tsx")
        smoke_scene_sha = smoke_sources.get("project/src/Scene.tsx")
        if smoke.get("status") != "passed" or smoke.get("framesExpected") != TOTAL_FRAMES or smoke.get("framesExecuted") != TOTAL_FRAMES:
            issues.append("frame-smoke-check.json does not record all 5400 frames passing")
        if not current_scene or current_scene.get("sha256") != smoke_scene_sha:
            issues.append("current Scene.tsx SHA-256 differs from the frame-smoke source hash")
        details = {
            "sourceFileCount": len(source_files), "sourceSha256": source_hashes,
            "forbiddenHits": hits, "frameSmokeReportSha256": input_hashes.get("review/frame-smoke-check.json", {}).get("sha256"),
            "frameSmokeSceneSha256": smoke_scene_sha,
            "currentSceneSha256": current_scene.get("sha256") if current_scene else None,
            "frameSmokeStatus": smoke.get("status"), "framesExpected": smoke.get("framesExpected"),
            "framesExecuted": smoke.get("framesExecuted"), "issues": issues,
        }
        bindings["sourceFiles"] = source_hashes
        bindings["frameSmoke"] = {key: details[key] for key in ("frameSmokeReportSha256", "frameSmokeSceneSha256", "currentSceneSha256", "frameSmokeStatus", "framesExpected", "framesExecuted")}
        measured["sourceAndFrameSmoke"] = details
        return {"passed": not issues, "details": details}

    def check_movie_hash() -> dict[str, Any]:
        outputs = delivery.get("outputs") if isinstance(delivery, dict) else None
        xhs = outputs.get("xiaohongshu") if isinstance(outputs, dict) else None
        relative = xhs.get("path") if isinstance(xhs, dict) else None
        path = resolve_inside(relative, DELIVERY)
        if path is None:
            return {"passed": False, "details": {"path": relative, "error": "final v03 movie is missing or outside delivery"}}
        if path.name != "si-ep18-sovereign-subcurrent-v03-xiaohongshu-90s-portrait.mp4":
            return {"passed": False, "details": {"path": relative, "error": "delivery does not identify the exact v03 movie"}}
        fp = fingerprint(path)
        declared = delivery.get("final_movie_sha256")
        matches = declared is None or (isinstance(declared, str) and fp["sha256"].lower() == declared.lower())
        info = {"path": str(path.relative_to(DELIVERY)), **fp, "deliveryManifestSha256": declared, "matchesDeliveryManifestSha256": matches}
        bindings["movie"] = info
        measured["movie"] = info
        return {"passed": fp["stableDuringHash"] and matches, "details": info}

    checks_to_run: list[tuple[str, Callable[[], dict[str, Any]]]] = [
        ("v03_native_delivery_identity", check_delivery),
        ("original_script_sha256_matches_delivery", check_script_hash),
        ("prepared_cues_match_attachment_table", check_attachment_text),
        ("authorization_binds_ordered_prepared_text", check_authorization),
        ("captions_match_text_and_layout_contract", check_captions),
        ("four_acts_cover_contiguous_5400_frames", check_timeline),
        ("events_map_to_48khz_samples_and_silence_window", check_events),
        ("measured_cues_preserve_full_pcm_and_fit_windows", check_synthesis_and_timing),
        ("master_is_exact_stereo_pcm16_with_silence", check_master),
        ("bundled_font_and_license_hashes_match_sources", check_fonts),
        ("src_is_deterministic_2d_and_matches_frame_smoke", check_sources_and_frame_smoke),
        ("final_movie_sha256_is_bound", check_movie_hash),
    ]
    for name, evaluator in checks_to_run:
        try:
            result = evaluator()
            record(name, bool(result.get("passed")), result.get("details"))
        except Exception as exc:
            record(name, False, {"error": sanitized_error(exc), "exceptionType": type(exc).__name__})

    qa = delivery.get("qa", {}) if isinstance(delivery.get("qa"), dict) else {}
    status = "PASS" if checks and all(row["status"] == "PASS" for row in checks) else "FAIL"
    report = {
        "schemaVersion": 1,
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "work": {"id": WORK_ID, "title": WORK_TITLE},
        "status": status,
        "checkCounts": {state.lower(): sum(row["status"] == state for row in checks) for state in ("PASS", "FAIL")},
        "checks": checks,
        "bindings": bindings,
        "measured": measured,
        "captionAlignment": "Estimated phrase placement inside measured PCM activity; not exact ASR or word-level alignment.",
        "humanAcceptance": {
            "representativeFrames": qa.get("representative_frames", "pending"),
            "continuousHumanReview": qa.get("continuous_human_review", "pending"),
            "targetDevicePlayback": qa.get("target_device_playback", "pending"),
            "deliveryManifestChangedByVerifier": False,
        },
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with REPORT_PATH.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except FileExistsError:
        print("verify_project: refusing to overwrite existing project-verification.json", file=sys.stderr)
        return 2
    print(json.dumps({"status": status, "report": str(REPORT_PATH.relative_to(DELIVERY)), "checkCounts": report["checkCounts"]}, ensure_ascii=False, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
