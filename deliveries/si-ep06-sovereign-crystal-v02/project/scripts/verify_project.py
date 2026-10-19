#!/usr/bin/env python3
"""Validate authored EP06 v02 timing and source inputs without rendering media."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import wave
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DELIVERY_DIR = PROJECT_DIR.parent
REVIEW_DIR = DELIVERY_DIR / "review"
MANIFEST_PATH = DELIVERY_DIR / "delivery.json"
FPS = 60
FRAME_COUNT = 7200
SAMPLE_RATE = 48_000
SAMPLES_PER_FRAME = 800
SAMPLES_PER_CHANNEL = 5_760_000


class ValidationError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_file(path: Path, label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot read {label}: {exc}") from None
    if not isinstance(data, dict):
        raise ValidationError(f"{label} must contain a JSON object")
    return data


def contained_path(base: Path, relative: str, label: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ValidationError(f"{label} path is missing")
    candidate = (base / relative).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError:
        raise ValidationError(f"{label} path escapes its owning directory") from None
    return candidate


def report_path() -> Path:
    preferred = REVIEW_DIR / "project-validation.json"
    if not preferred.exists():
        return preferred
    for number in range(2, 10000):
        candidate = preferred.with_name(f"project-validation-r{number:02d}.json")
        if not candidate.exists():
            return candidate
    raise ValidationError("no unused project-validation report name is available")


def run_checks() -> dict[str, Any]:
    manifest = json_file(MANIFEST_PATH, "delivery.json")
    segments_doc = json_file(PROJECT_DIR / "segments.json", "segments.json")
    timeline = json_file(PROJECT_DIR / "timeline.json", "timeline.json")
    timing = json_file(PROJECT_DIR / "audio-timing.json", "audio-timing.json")
    events_doc = json_file(PROJECT_DIR / "sfx_events.json", "sfx_events.json")
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, details: Any = None) -> None:
        checks.append({"name": name, "pass": bool(passed), **({"details": details} if details is not None else {})})

    expected_manifest_timing = (manifest.get("duration_seconds"), manifest.get("fps"), manifest.get("total_frames"))
    check("manifest_120s_60fps_7200frames", expected_manifest_timing == (120, FPS, FRAME_COUNT), expected_manifest_timing)
    check("authored_segments_timing_header", (segments_doc.get("duration_seconds"), segments_doc.get("fps"), segments_doc.get("total_frames"), segments_doc.get("sample_rate"), segments_doc.get("samples_per_frame")) == (120, FPS, FRAME_COUNT, SAMPLE_RATE, SAMPLES_PER_FRAME))
    scenes = timeline.get("scenes")
    timeline_failures: list[str] = []
    if (timeline.get("fps"), timeline.get("total_frames")) != (FPS, FRAME_COUNT) or not isinstance(scenes, list) or not scenes:
        timeline_failures.append("timeline.json must declare 60 fps, 7200 frames and a non-empty scenes array")
    else:
        cursor = 0
        for index, scene in enumerate(scenes):
            if not isinstance(scene, dict):
                timeline_failures.append(f"scene {index} is not an object")
                continue
            start, end = scene.get("startFrame"), scene.get("endFrame")
            if not isinstance(start, int) or not isinstance(end, int) or start != cursor or not start < end <= FRAME_COUNT:
                timeline_failures.append(f"scene {index} does not continue contiguous frame coverage")
                continue
            if not isinstance(scene.get("motion"), str) or not scene["motion"].strip():
                timeline_failures.append(f"scene {index} has no authored motion note")
            cursor = end
        if cursor != FRAME_COUNT:
            timeline_failures.append(f"timeline scene coverage stops at frame {cursor}, not {FRAME_COUNT}")
    check("timeline_contiguous_120s_coverage", not timeline_failures, timeline_failures or f"{len(scenes)} motion-noted scenes cover frames 0–7199")
    check("measured_audio_timing_header", (timing.get("durationSeconds"), timing.get("fps"), timing.get("sampleRate"), timing.get("samplesPerFrame"), timing.get("samplesPerChannel"), timing.get("status")) == (120, FPS, SAMPLE_RATE, SAMPLES_PER_FRAME, SAMPLES_PER_CHANNEL, "measured_pcm_with_estimated_phrase_timing"))

    script_path = contained_path(DELIVERY_DIR, manifest.get("script", {}).get("path"), "original script")
    expected_script_hash = manifest.get("script", {}).get("sha256")
    script_hash = sha256_file(script_path) if script_path.is_file() else None
    check("original_script_hash", script_hash is not None and script_hash == expected_script_hash, {"path": script_path.relative_to(DELIVERY_DIR).as_posix(), "sha256": script_hash})

    authored_segments = segments_doc.get("segments")
    measured_segments = timing.get("segments")
    check("ten_authored_and_measured_segments", isinstance(authored_segments, list) and isinstance(measured_segments, list) and len(authored_segments) == len(measured_segments) == 10)
    segment_failures: list[str] = []
    if isinstance(authored_segments, list) and isinstance(measured_segments, list):
        if len(authored_segments) != 10 or len(measured_segments) != 10:
            segment_failures.append("expected exactly ten source and measured segments")
        for index, (authored, measured) in enumerate(zip(authored_segments, measured_segments)):
            if not isinstance(authored, dict) or not isinstance(measured, dict):
                segment_failures.append(f"segment {index} is not an object")
                continue
            start, end = authored.get("startFrame"), authored.get("endFrame")
            if authored.get("id") != measured.get("id") or start != measured.get("declaredStartFrame") or end != measured.get("declaredEndFrame"):
                segment_failures.append(f"segment {index} authored/measured identifiers or frame windows differ")
            if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= FRAME_COUNT:
                segment_failures.append(f"segment {index} has an invalid frame range")
            voice_start, voice_end = measured.get("voiceStartSample"), measured.get("voiceEndSampleExclusive")
            if not isinstance(voice_start, int) or not isinstance(voice_end, int) or not 0 <= voice_start < voice_end <= SAMPLES_PER_CHANNEL:
                segment_failures.append(f"segment {index} has an invalid measured PCM range")
            elif voice_start != start * SAMPLES_PER_FRAME or voice_end > end * SAMPLES_PER_FRAME:
                segment_failures.append(f"segment {index} measured voice does not fit its authored frame window")
            cue_name = measured.get("cueFile")
            cue_path = contained_path(DELIVERY_DIR, cue_name, f"{measured.get('id')} cue") if isinstance(cue_name, str) else None
            cue_ok = False
            cue_details: dict[str, Any] = {"path": cue_name}
            if cue_path is not None and cue_path.is_file():
                cue_details["sha256"] = sha256_file(cue_path)
                try:
                    with wave.open(str(cue_path), "rb") as cue:
                        cue_shape = (cue.getframerate(), cue.getnchannels(), cue.getsampwidth(), cue.getnframes(), cue.getcomptype())
                        cue_pcm = cue.readframes(cue.getnframes())
                    cue_pcm_hash = hashlib.sha256(cue_pcm).hexdigest()
                    cue_details.update({"sample_rate": cue_shape[0], "channels": cue_shape[1], "sample_width_bytes": cue_shape[2], "samples": cue_shape[3], "pcm_sha256": cue_pcm_hash})
                    cue_ok = (
                        cue_shape[0] == SAMPLE_RATE
                        and cue_shape[1] in (1, 2)
                        and cue_shape[2] == 2
                        and cue_shape[3] == measured.get("cueSamplesAt48k")
                        and cue_shape[4] == "NONE"
                        and cue_details["sha256"] == measured.get("cueSha256")
                        and cue_pcm_hash == measured.get("cuePcmSha256")
                    )
                except (OSError, wave.Error):
                    cue_ok = False
            if not cue_ok:
                segment_failures.append(f"segment {index} cue file is missing or its measured hash differs")
    check("source_and_measured_segment_frames_match", not segment_failures, segment_failures or "all ten measured spans match authored frames")

    captions = timing.get("captions")
    caption_failures: list[str] = []
    last_end = -1
    if not isinstance(captions, list) or not captions:
        caption_failures.append("no measured phrase captions were found")
    else:
        for index, caption in enumerate(captions):
            if not isinstance(caption, dict):
                caption_failures.append(f"caption {index} is not an object")
                continue
            start, end, text = caption.get("startFrame"), caption.get("endFrame"), caption.get("text")
            if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= FRAME_COUNT:
                caption_failures.append(f"caption {index} has invalid frame bounds")
                continue
            if start < last_end:
                caption_failures.append(f"caption {index} overlaps a preceding caption")
            last_end = end
            if not isinstance(text, str) or len(text.splitlines()) > 2 or any(len(re.findall(r"[\u3400-\u9fff]", line)) > 14 for line in text.splitlines()):
                caption_failures.append(f"caption {index} exceeds the authored two-line/14-Chinese-character layout")
    check("measured_caption_frame_order_and_layout", not caption_failures, caption_failures or f"{len(captions)} captions are ordered and within layout limits")

    silence = timing.get("absoluteSilence")
    silence_ok = isinstance(silence, dict) and (silence.get("startFrame"), silence.get("endFrameExclusive"), silence.get("startSample"), silence.get("endSampleExclusive"), silence.get("samplesZeroInAllStemsAndMaster")) == (5740, 5760, 4_592_000, 4_608_000, True)
    check("authored_20_frame_absolute_silence_metadata", silence_ok, silence)
    check("s08_voice_ends_before_silence", isinstance(measured_segments, list) and len(measured_segments) >= 8 and measured_segments[7].get("voiceEndSampleExclusive", SAMPLES_PER_CHANNEL) <= 5740 * SAMPLES_PER_FRAME)
    source_events = events_doc.get("events")
    timing_events = timing.get("sfxEvents")
    sfx_in_sync = (
        isinstance(source_events, list)
        and isinstance(timing_events, list)
        and len(source_events) == len(timing_events) == 13
        and all(
            isinstance(source, dict)
            and isinstance(measured, dict)
            and (source.get("id"), source.get("frame"), source.get("sampleIndex"))
            == (measured.get("id"), measured.get("frame"), measured.get("sampleIndex"))
            for source, measured in zip(source_events, timing_events)
        )
    )
    check("sfx_events_share_60fps_48khz_clock", (events_doc.get("fps"), events_doc.get("sampleRate"), events_doc.get("samplesPerFrame")) == (FPS, SAMPLE_RATE, SAMPLES_PER_FRAME) and sfx_in_sync)

    source_files = sorted(path for path in (PROJECT_DIR / "src").rglob("*") if path.is_file() and path.suffix in {".ts", ".tsx", ".js", ".jsx"})
    source = "\n".join(path.read_text(encoding="utf-8") for path in source_files)
    deterministic = not re.search(r"\bMath\.random\s*\(|\bDate\.now\s*\(", source)
    check("frame_deterministic_source", bool(source_files) and deterministic, {"files": [path.relative_to(PROJECT_DIR).as_posix() for path in source_files]})

    audio_spec = manifest.get("audio", {})
    master_path = contained_path(DELIVERY_DIR, audio_spec.get("master"), "PCM master")
    master_result: dict[str, Any] = {"path": master_path.relative_to(DELIVERY_DIR).as_posix(), "exists": master_path.is_file()}
    master_ok = False
    if master_path.is_file():
        try:
            with wave.open(str(master_path), "rb") as master:
                observed = (master.getframerate(), master.getnchannels(), master.getsampwidth(), master.getnframes(), master.getcomptype())
                master.setpos(4_592_000)
                silence_bytes = master.readframes(16_000)
            actual_hash = sha256_file(master_path)
            silence_zero = len(silence_bytes) == 16_000 * 2 * 2 and not any(silence_bytes)
            master_result.update({"sample_rate": observed[0], "channels": observed[1], "sample_width_bytes": observed[2], "samples_per_channel": observed[3], "sha256": actual_hash, "s08_silence_window_zero": silence_zero})
            master_ok = observed == (SAMPLE_RATE, 2, 2, SAMPLES_PER_CHANNEL, "NONE") and actual_hash == audio_spec.get("sha256") and audio_spec.get("sample_rate") == SAMPLE_RATE and audio_spec.get("channels") == 2 and audio_spec.get("samples_per_channel") == SAMPLES_PER_CHANNEL
            check("shared_pcm_master_s08_silence_exact_zero", silence_zero, {"start_sample": 4_592_000, "end_sample_exclusive": 4_608_000})
        except (OSError, wave.Error) as exc:
            master_result["error"] = str(exc)
            check("shared_pcm_master_s08_silence_exact_zero", False, str(exc))
    check("shared_pcm_master_exact_format_and_manifest_hash", master_ok, master_result)

    failed = [item["name"] for item in checks if not item["pass"]]
    return {
        "status": "PASS" if not failed else "FAIL",
        "scope": "authored source, measured PCM timing, captions and master identity; this report does not validate rendered media or human acceptance",
        "inputs": {
            "delivery_json_sha256": sha256_file(MANIFEST_PATH),
            "segments_json_sha256": sha256_file(PROJECT_DIR / "segments.json"),
            "timeline_json_sha256": sha256_file(PROJECT_DIR / "timeline.json"),
            "audio_timing_json_sha256": sha256_file(PROJECT_DIR / "audio-timing.json"),
        },
        "checks": checks,
        "failures": failed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-write", action="store_true", help="Print the report without saving a fresh JSON report.")
    args = parser.parse_args()
    try:
        result = run_checks()
    except (ValidationError, OSError, KeyError, TypeError) as exc:
        print(f"[verify-project] ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not args.no_write:
        REVIEW_DIR.mkdir(parents=True, exist_ok=True)
        target = report_path()
        temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, target)
        print(f"Report: {target}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
