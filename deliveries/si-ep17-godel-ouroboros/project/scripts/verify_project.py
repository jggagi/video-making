#!/usr/bin/env python3
"""Check EP17 project manifests and optional PCM master without rendering media."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DELIVERY_DIR = PROJECT_DIR.parent
REPORT_PATH = DELIVERY_DIR / "review" / "project-check.json"
TOTAL_FRAMES = 5400
SILENCE_START_SAMPLE = 3_888_000
SILENCE_END_SAMPLE = 3_912_000


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def compact_text(text: str) -> str:
    return text.replace("\r", "").replace("\n", "")


def stat_signature(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns


def inspect_master(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read the WAV header and only the specified 0.5 second zero-sample window."""
    before = stat_signature(path)
    with wave.open(str(path), "rb") as wav:
        measured = {
            "sample_rate_hz": wav.getframerate(),
            "channels": wav.getnchannels(),
            "sample_width_bytes": wav.getsampwidth(),
            "sample_frames_per_channel": wav.getnframes(),
            "compression_type": wav.getcomptype(),
            "compression_name": wav.getcompname(),
        }
        zero_check: dict[str, Any] = {
            "range_samples_per_channel": [SILENCE_START_SAMPLE, SILENCE_END_SAMPLE],
            "range_is_half_open": True,
            "samples_per_channel_expected": SILENCE_END_SAMPLE - SILENCE_START_SAMPLE,
        }
        can_read_range = (
            wav.getnchannels() == 2
            and wav.getsampwidth() == 2
            and wav.getnframes() >= SILENCE_END_SAMPLE
        )
        if can_read_range:
            wav.setpos(SILENCE_START_SAMPLE)
            raw = wav.readframes(SILENCE_END_SAMPLE - SILENCE_START_SAMPLE)
            zeros = [0, 0]
            total = 0
            for left, right in struct.iter_unpack("<hh", raw):
                zeros[0] += left == 0
                zeros[1] += right == 0
                total += 1
            zero_check.update(
                {
                    "frames_read": total,
                    "zero_samples_per_channel": zeros,
                    "all_zero_per_channel": zeros == [total, total]
                    and total == SILENCE_END_SAMPLE - SILENCE_START_SAMPLE,
                }
            )
        else:
            zero_check.update(
                {
                    "frames_read": None,
                    "zero_samples_per_channel": None,
                    "all_zero_per_channel": False,
                }
            )
    after = stat_signature(path)
    return measured, {
        "samples": zero_check,
        "file_stable_during_read": before == after,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="print the check report without creating review/project-check.json",
    )
    args = parser.parse_args()

    checks: list[dict[str, Any]] = []
    measured: dict[str, Any] = {}

    def record(name: str, ok: bool, details: Any) -> None:
        checks.append({"name": name, "status": "PASS" if ok else "FAIL", "details": details})

    inputs: dict[str, Any] = {}
    for key, rel in {
        "delivery": "delivery.json",
        "timeline": "project/timeline.json",
        "segments": "project/segments.json",
        "captions": "project/captions.json",
        "audio_timing": "project/audio-timing.json",
    }.items():
        path = DELIVERY_DIR / rel
        try:
            inputs[key] = read_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            inputs[key] = None
            record(f"read_{key}", False, f"{path}: {exc}")
        else:
            record(f"read_{key}", True, str(path.relative_to(DELIVERY_DIR)))

    delivery = inputs.get("delivery") or {}
    timeline = inputs.get("timeline") or {}
    segments = inputs.get("segments") or []
    captions = inputs.get("captions") or []
    audio_timing = inputs.get("audio_timing") or {}

    platforms = delivery.get("platforms") if isinstance(delivery, dict) else None
    output_map = delivery.get("outputs") if isinstance(delivery, dict) else None
    platform_ok = (
        platforms == ["xiaohongshu"]
        and isinstance(output_map, dict)
        and set(output_map) == {"xiaohongshu"}
    )
    record(
        "xiaohongshu_only",
        platform_ok,
        {"platforms": platforms, "output_platforms": sorted(output_map) if isinstance(output_map, dict) else None},
    )

    xhs_output = output_map.get("xiaohongshu", {}) if isinstance(output_map, dict) else {}
    project_spec = {
        "duration_seconds": delivery.get("duration_seconds") if isinstance(delivery, dict) else None,
        "fps": delivery.get("fps") if isinstance(delivery, dict) else None,
        "total_frames": delivery.get("total_frames") if isinstance(delivery, dict) else None,
        "width": xhs_output.get("width") if isinstance(xhs_output, dict) else None,
        "height": xhs_output.get("height") if isinstance(xhs_output, dict) else None,
        "timeline_duration_seconds": timeline.get("duration_seconds") if isinstance(timeline, dict) else None,
        "timeline_fps": timeline.get("fps") if isinstance(timeline, dict) else None,
        "timeline_total_frames": timeline.get("total_frames") if isinstance(timeline, dict) else None,
        "sample_rate_hz": timeline.get("sample_rate") if isinstance(timeline, dict) else None,
        "samples_per_channel": timeline.get("samples_per_channel") if isinstance(timeline, dict) else None,
    }
    measured["project_spec"] = project_spec
    spec_ok = (
        project_spec["duration_seconds"] == 90
        and project_spec["fps"] == 60
        and project_spec["total_frames"] == TOTAL_FRAMES
        and project_spec["width"] == 2160
        and project_spec["height"] == 3840
        and project_spec["timeline_duration_seconds"] == 90
        and project_spec["timeline_fps"] == 60
        and project_spec["timeline_total_frames"] == TOTAL_FRAMES
        and project_spec["sample_rate_hz"] == 48_000
        and project_spec["samples_per_channel"] == 4_320_000
    )
    record("native_project_spec", spec_ok, project_spec)

    integer_issues: list[str] = []
    if isinstance(timeline, dict):
        for collection_name, collection in (("acts", timeline.get("acts", [])), ("events", timeline.get("events", []))):
            if not isinstance(collection, list):
                integer_issues.append(f"timeline.{collection_name} is not a list")
                continue
            for index, item in enumerate(collection):
                if not isinstance(item, dict):
                    integer_issues.append(f"timeline.{collection_name}[{index}] is not an object")
                    continue
                keys = ("startFrame", "endFrame") if collection_name == "acts" else ("frame", "sample")
                for field in keys:
                    if field not in item or not is_int(item[field]):
                        integer_issues.append(f"timeline.{collection_name}[{index}].{field} is missing or not an integer")
        disclaimer = timeline.get("disclaimer", {})
        if not isinstance(disclaimer, dict) or any(
            not is_int(disclaimer.get(field)) for field in ("startFrame", "endFrame")
        ):
            integer_issues.append("timeline.disclaimer boundaries must be integers")
    else:
        integer_issues.append("timeline is not an object")

    if not isinstance(segments, list):
        integer_issues.append("segments.json is not a list")
        segments = []
    if not isinstance(captions, list):
        integer_issues.append("captions.json is not a list")
        captions = []
    for label, rows, fields in (
        ("segments", segments, ("startFrame", "endFrame")),
        ("captions", captions, ("startFrame", "endFrame")),
        ("audio_timing.segments", audio_timing.get("segments", []) if isinstance(audio_timing, dict) else [],
         ("startFrame", "endFrame", "activeStartFrame", "activeEndFrameExclusive")),
    ):
        if not isinstance(rows, list):
            integer_issues.append(f"{label} is not a list")
            continue
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                integer_issues.append(f"{label}[{index}] is not an object")
                continue
            for field in fields:
                if field not in row or not is_int(row[field]):
                    integer_issues.append(f"{label}[{index}].{field} is missing or not an integer")
    record("integer_timeline_boundaries", not integer_issues, integer_issues or "All declared frame/sample boundaries are integers.")

    segment_map: dict[str, dict[str, Any]] = {
        s.get("id"): s for s in segments if isinstance(s, dict) and isinstance(s.get("id"), str)
    }
    segment_issues: list[str] = []
    if len(segment_map) != len(segments):
        segment_issues.append("segment IDs are missing or duplicated")
    last_segment_end = -1
    for segment in sorted(segment_map.values(), key=lambda row: row.get("startFrame", -1)):
        start, end = segment.get("startFrame"), segment.get("endFrame")
        label = str(segment.get("id"))
        if not (is_int(start) and is_int(end) and 0 <= start < end <= TOTAL_FRAMES):
            segment_issues.append(f"{label} has invalid frame bounds: {start!r}..{end!r}")
            continue
        if start < last_segment_end:
            segment_issues.append(f"{label} overlaps the preceding segment window")
        last_segment_end = max(last_segment_end, end)
    record("segment_windows_and_bounds", not segment_issues, segment_issues or "Segment windows are integer, in-bounds, and non-overlapping.")

    caption_line_issues: list[str] = []
    caption_window_issues: list[str] = []
    last_caption_end = -1
    for index, caption in enumerate(sorted(captions, key=lambda row: row.get("startFrame", -1) if isinstance(row, dict) else -1)):
        if not isinstance(caption, dict):
            caption_line_issues.append(f"caption[{index}] is not an object")
            continue
        text = caption.get("text")
        if not isinstance(text, str):
            caption_line_issues.append(f"caption[{index}] text is not a string")
            text = ""
        lines = text.splitlines() or [""]
        if len(lines) > 2:
            caption_line_issues.append(f"caption[{index}] has {len(lines)} lines")
        for line_number, line in enumerate(lines, start=1):
            if len(line) > 17:
                caption_line_issues.append(f"caption[{index}] line {line_number} has {len(line)} characters")

        start, end = caption.get("startFrame"), caption.get("endFrame")
        cap_id = caption.get("id")
        segment = segment_map.get(cap_id)
        if not (is_int(start) and is_int(end) and 0 <= start < end <= TOTAL_FRAMES):
            caption_window_issues.append(f"caption[{index}] has invalid frame bounds: {start!r}..{end!r}")
        elif start < last_caption_end:
            caption_window_issues.append(f"caption[{index}] overlaps the preceding caption")
        if segment is None:
            caption_window_issues.append(f"caption[{index}] has no segment window for id {cap_id!r}")
        elif is_int(start) and is_int(end) and (start < segment.get("startFrame", -1) or end > segment.get("endFrame", TOTAL_FRAMES + 1)):
            caption_window_issues.append(f"caption[{index}] is outside {cap_id} segment window")
        if is_int(end):
            last_caption_end = max(last_caption_end, end)
    record("caption_line_limits", not caption_line_issues, caption_line_issues or "All captions fit within two lines of at most 17 characters each.")
    record("caption_overlap_windows_bounds", not caption_window_issues, caption_window_issues or "Captions are non-overlapping and within their segment and project bounds.")

    concatenation_issues: list[str] = []
    for segment_id, segment in segment_map.items():
        expected = segment.get("display_subtitle")
        actual = "".join(
            compact_text(row.get("text", ""))
            for row in captions
            if isinstance(row, dict) and row.get("id") == segment_id and isinstance(row.get("text"), str)
        )
        if not isinstance(expected, str) or compact_text(expected) != actual:
            concatenation_issues.append(f"{segment_id}: caption chunks do not exactly match display_subtitle after removing line breaks")
    record("caption_text_matches_segments", not concatenation_issues, concatenation_issues or "Punctuation and wording match each display_subtitle after removing line breaks.")

    audio_segments = audio_timing.get("segments", []) if isinstance(audio_timing, dict) else []
    measured["audio_timing"] = {
        "status": audio_timing.get("status") if isinstance(audio_timing, dict) else None,
        "duration_seconds": audio_timing.get("duration_seconds") if isinstance(audio_timing, dict) else None,
        "fps": audio_timing.get("fps") if isinstance(audio_timing, dict) else None,
        "samples_per_channel": audio_timing.get("samples_per_channel") if isinstance(audio_timing, dict) else None,
        "caption_alignment_note": audio_timing.get("captionAlignment") if isinstance(audio_timing, dict) else None,
        "segments": [
            {
                "id": row.get("id"),
                "actual_duration_seconds": row.get("actualDurationSeconds"),
                "active_start_frame": row.get("activeStartFrame"),
                "active_end_frame_exclusive": row.get("activeEndFrameExclusive"),
                "cue_sha256": row.get("sha256"),
            }
            for row in audio_segments if isinstance(row, dict)
        ],
    }
    timing_ok = (
        isinstance(audio_timing, dict)
        and audio_timing.get("status") == "MEASURED"
        and audio_timing.get("duration_seconds") == 90
        and audio_timing.get("fps") == 60
        and audio_timing.get("samples_per_channel") == 4_320_000
    )
    record("audio_timing_measured_fields", timing_ok, {k: v for k, v in measured["audio_timing"].items() if k != "segments"})
    timing_captions = audio_timing.get("captions") if isinstance(audio_timing, dict) else None
    record("captions_match_audio_timing", timing_captions == captions, "audio-timing.json captions match captions.json" if timing_captions == captions else "audio-timing.json captions differ from captions.json")

    source_info: dict[str, Any] = {"expected_sha256": None, "actual_sha256": None, "path": None}
    source_ok = False
    script_meta = delivery.get("script", {}) if isinstance(delivery, dict) else {}
    relative_source = script_meta.get("path") if isinstance(script_meta, dict) else None
    expected_hash = script_meta.get("sha256") if isinstance(script_meta, dict) else None
    if isinstance(relative_source, str):
        source_path = (DELIVERY_DIR / relative_source).resolve()
        if source_path.is_relative_to(DELIVERY_DIR.resolve()) and source_path.is_file():
            actual_hash = sha256_file(source_path)
            source_ok = isinstance(expected_hash, str) and actual_hash.lower() == expected_hash.lower()
            source_info = {
                "path": str(source_path.relative_to(DELIVERY_DIR.resolve())),
                "expected_sha256": expected_hash,
                "actual_sha256": actual_hash,
            }
        else:
            source_info["path"] = relative_source
    measured["source_hash"] = source_info
    record("original_source_hash_matches", source_ok, source_info)

    forbidden = re.compile(r"Math\.random\s*\(|Date\.now\s*\(|rotateX|rotateY|perspective|WebGL", re.IGNORECASE)
    src_dir = PROJECT_DIR / "src"
    forbidden_hits: list[str] = []
    if src_dir.is_dir():
        for source_path in sorted(path for path in src_dir.rglob("*") if path.is_file()):
            try:
                source_text = source_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for line_number, line in enumerate(source_text.splitlines(), start=1):
                if forbidden.search(line):
                    forbidden_hits.append(f"{source_path.relative_to(PROJECT_DIR)}:{line_number}")
        source_scan_ok = not forbidden_hits
    else:
        source_scan_ok = False
        forbidden_hits.append("src/ directory is missing")
    record("source_forbidden_patterns", source_scan_ok, forbidden_hits or "No forbidden nondeterministic/3D/WebGL patterns found under src/.")

    audio_master_rel = (delivery.get("audio") or {}).get("master") if isinstance(delivery, dict) else None
    audio_master = (DELIVERY_DIR / audio_master_rel).resolve() if isinstance(audio_master_rel, str) else None
    audio_master_check: dict[str, Any] = {"status": "NOT_RUN"}
    if audio_master is not None and audio_master.is_relative_to(DELIVERY_DIR.resolve()) and audio_master.is_file():
        try:
            wav_fields, zero_fields = inspect_master(audio_master)
        except (OSError, wave.Error, EOFError, struct.error) as exc:
            audio_master_check = {"status": "FAIL", "error": str(exc)}
            record("audio_master_pcm", False, audio_master_check)
        else:
            expected_audio = (
                wav_fields["sample_rate_hz"] == 48_000
                and wav_fields["channels"] == 2
                and wav_fields["sample_width_bytes"] == 2
                and wav_fields["sample_frames_per_channel"] == 4_320_000
                and wav_fields["compression_type"] == "NONE"
            )
            stable = zero_fields["file_stable_during_read"]
            zero_ok = zero_fields["samples"]["all_zero_per_channel"]
            audio_master_check = {
                "status": "PASS" if expected_audio and stable and zero_ok else "FAIL",
                "measured": wav_fields,
                "zero_window": zero_fields["samples"],
                "file_stable_during_read": stable,
            }
            record("audio_master_pcm", expected_audio and stable and zero_ok, audio_master_check)
    else:
        audio_master_check = {"status": "NOT_RUN", "reason": "No PCM master sample check was performed."}
        checks.append({"name": "audio_master_pcm", "status": "SKIPPED", "details": audio_master_check})
    measured["audio_master"] = audio_master_check

    qa = delivery.get("qa", {}) if isinstance(delivery, dict) else {}
    human_acceptance = {
        "representative_frames": str(qa.get("representative_frames", "pending")).upper(),
        "continuous_human_review": str(qa.get("continuous_human_review", "pending")).upper(),
        "target_device_playback": str(qa.get("target_device_playback", "pending")).upper(),
        "model_visual_review": "NOT_RUN",
    }
    failed = sum(check["status"] == "FAIL" for check in checks)
    passed = sum(check["status"] == "PASS" for check in checks)
    skipped = sum(check["status"] == "SKIPPED" for check in checks)
    report = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project": "si-ep17-godel-ouroboros",
        "automated_status": "PASS" if failed == 0 else "FAIL",
        "checks_summary": {"passed": passed, "failed": failed, "skipped": skipped},
        "checks": checks,
        "measured": measured,
        "human_acceptance": human_acceptance,
    }
    if not args.no_write:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        report["report_path"] = str(REPORT_PATH.relative_to(DELIVERY_DIR))
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        report["report_path"] = None
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
