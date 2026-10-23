#!/usr/bin/env python3
"""Check EP18 project identity, eight cue windows, captions, source hash, and available PCM evidence."""

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
WORK_ID = "si-ep18-sovereign-subcurrent-v02"
WORK_TITLE = "心印潜流 · v02"
TOTAL_FRAMES = 5_400
SILENCE_START_SAMPLE = 3_888_000
SILENCE_END_SAMPLE = 3_912_000
EXPECTED_IDS = ["S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08"]


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


def compact_text(value: str) -> str:
    return value.replace("\r", "").replace("\n", "")


def safe_delivery_file(relative: Any) -> Path | None:
    if not isinstance(relative, str) or not relative.strip():
        return None
    root = DELIVERY_DIR.resolve()
    path = (DELIVERY_DIR / relative).resolve()
    return path if path.is_relative_to(root) and path.is_file() else None


def inspect_master(path: Path) -> tuple[dict[str, Any], dict[str, Any], bool, bool]:
    before = (path.stat().st_size, path.stat().st_mtime_ns)
    with wave.open(str(path), "rb") as wav:
        measured = {
            "sampleRateHz": wav.getframerate(),
            "channels": wav.getnchannels(),
            "sampleWidthBytes": wav.getsampwidth(),
            "sampleFramesPerChannel": wav.getnframes(),
            "compressionType": wav.getcomptype(),
        }
        can_check_silence = wav.getnchannels() == 2 and wav.getsampwidth() == 2 and wav.getnframes() >= SILENCE_END_SAMPLE
        if can_check_silence:
            wav.setpos(SILENCE_START_SAMPLE)
            raw = wav.readframes(SILENCE_END_SAMPLE - SILENCE_START_SAMPLE)
            zero_frames = sum(left == 0 and right == 0 for left, right in struct.iter_unpack("<hh", raw))
            silence = {
                "rangeSamplesPerChannel": [SILENCE_START_SAMPLE, SILENCE_END_SAMPLE],
                "rangeIsHalfOpen": True,
                "framesRead": len(raw) // 4,
                "allStereoSamplesExactZero": zero_frames == SILENCE_END_SAMPLE - SILENCE_START_SAMPLE,
            }
        else:
            silence = {
                "rangeSamplesPerChannel": [SILENCE_START_SAMPLE, SILENCE_END_SAMPLE],
                "rangeIsHalfOpen": True,
                "framesRead": None,
                "allStereoSamplesExactZero": False,
            }
    after = (path.stat().st_size, path.stat().st_mtime_ns)
    stable = before == after
    format_ok = measured == {
        "sampleRateHz": 48_000,
        "channels": 2,
        "sampleWidthBytes": 2,
        "sampleFramesPerChannel": 4_320_000,
        "compressionType": "NONE",
    }
    return measured, silence, stable, format_ok and stable and silence["allStereoSamplesExactZero"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-write", action="store_true", help="print evidence without writing project-check.json")
    args = parser.parse_args()
    checks: list[dict[str, Any]] = []
    measured: dict[str, Any] = {}

    def record(name: str, status: str, details: Any) -> None:
        checks.append({"name": name, "status": status, "details": details})

    loaded: dict[str, Any] = {}
    files = {
        "delivery": DELIVERY_DIR / "delivery.json",
        "segments": PROJECT_DIR / "segments.json",
        "captions": PROJECT_DIR / "captions.json",
        "authorization": PROJECT_DIR / "audio-authorization.json",
        "package": PROJECT_DIR / "package.json",
    }
    for key, path in files.items():
        try:
            loaded[key] = read_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            loaded[key] = None
            record("read_" + key, "FAIL", str(exc))
        else:
            record("read_" + key, "PASS", str(path.relative_to(DELIVERY_DIR)))

    delivery = loaded.get("delivery") if isinstance(loaded.get("delivery"), dict) else {}
    segments = loaded.get("segments") if isinstance(loaded.get("segments"), list) else []
    captions = loaded.get("captions") if isinstance(loaded.get("captions"), list) else []
    authorization = loaded.get("authorization") if isinstance(loaded.get("authorization"), dict) else {}
    package = loaded.get("package") if isinstance(loaded.get("package"), dict) else {}
    output_map = delivery.get("outputs") if isinstance(delivery, dict) else {}
    xhs = output_map.get("xiaohongshu") if isinstance(output_map, dict) else {}
    expected_output = "小红书/si-ep18-sovereign-subcurrent-v02-xiaohongshu-90s-portrait.mp4"
    identity = {
        "slug": delivery.get("slug"),
        "title": delivery.get("title"),
        "platforms": delivery.get("platforms"),
        "outputPlatforms": sorted(output_map) if isinstance(output_map, dict) else None,
        "durationSeconds": delivery.get("duration_seconds"),
        "fps": delivery.get("fps"),
        "totalFrames": delivery.get("total_frames"),
        "outputPath": xhs.get("path") if isinstance(xhs, dict) else None,
        "dimensions": [xhs.get("width"), xhs.get("height")] if isinstance(xhs, dict) else None,
        "remotionVersion": (package.get("dependencies") or {}).get("remotion") if isinstance(package, dict) else None,
    }
    measured["identity"] = identity
    identity_ok = (
        identity["slug"] == WORK_ID and identity["title"] == WORK_TITLE
        and identity["platforms"] == ["xiaohongshu"] and identity["outputPlatforms"] == ["xiaohongshu"]
        and identity["durationSeconds"] == 90 and identity["fps"] == 60 and identity["totalFrames"] == TOTAL_FRAMES
        and identity["outputPath"] == expected_output and identity["dimensions"] == [2160, 3840]
        and identity["remotionVersion"] == "4.0.534"
    )
    record("native_delivery_identity", "PASS" if identity_ok else "FAIL", identity)

    segment_issues: list[str] = []
    ids = [row.get("id") for row in segments if isinstance(row, dict)]
    if ids != EXPECTED_IDS:
        segment_issues.append("segments.json must contain exactly S01 through S08 in order")
    last_end = -1
    for row in segments:
        if not isinstance(row, dict):
            segment_issues.append("segment entry is not an object")
            continue
        start, end = row.get("startFrame"), row.get("endFrame")
        if not (is_int(start) and is_int(end) and 0 <= start < end <= TOTAL_FRAMES):
            segment_issues.append(str(row.get("id")) + " has invalid frame bounds")
            continue
        if start < last_end:
            segment_issues.append(str(row.get("id")) + " overlaps the preceding cue")
        last_end = max(last_end, end)
        for field in ("display_subtitle", "tts_phonetic_text"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                segment_issues.append(str(row.get("id")) + " lacks " + field)
    record("eight_cue_windows", "PASS" if not segment_issues else "FAIL", segment_issues or {"ids": ids, "cueCount": len(segments)})

    caption_issues: list[str] = []
    if not captions:
        caption_issues.append("captions.json is empty")
    last_caption_end = -1
    segment_by_id = {row.get("id"): row for row in segments if isinstance(row, dict)}
    for index, row in enumerate(captions):
        if not isinstance(row, dict):
            caption_issues.append("caption[" + str(index) + "] is not an object")
            continue
        start, end, text = row.get("startFrame"), row.get("endFrame"), row.get("text")
        if not (is_int(start) and is_int(end) and 0 <= start < end <= TOTAL_FRAMES):
            caption_issues.append("caption[" + str(index) + "] has invalid frame bounds")
        elif start < last_caption_end:
            caption_issues.append("caption[" + str(index) + "] overlaps the preceding caption")
        if is_int(end):
            last_caption_end = max(last_caption_end, end)
        if not isinstance(text, str) or not text.strip():
            caption_issues.append("caption[" + str(index) + "] has no text")
            continue
        if len(text.splitlines()) > 2 or any(len(line) > 17 for line in text.splitlines()):
            caption_issues.append("caption[" + str(index) + "] exceeds two lines or 17 characters per line")
        cue = segment_by_id.get(row.get("id"))
        if cue is None:
            caption_issues.append("caption[" + str(index) + "] has no matching cue")
        elif is_int(start) and is_int(end) and (start < cue["startFrame"] or end > cue["endFrame"]):
            caption_issues.append("caption[" + str(index) + "] is outside its cue window")
    caption_text_issues = []
    for cue_id, cue in segment_by_id.items():
        actual = "".join(compact_text(row.get("text", "")) for row in captions if isinstance(row, dict) and row.get("id") == cue_id and isinstance(row.get("text"), str))
        expected = cue.get("display_subtitle")
        if not isinstance(expected, str) or compact_text(expected) != actual:
            caption_text_issues.append(cue_id + " caption text does not match display_subtitle")
    caption_issues.extend(caption_text_issues)
    record("caption_cue_alignment", "PASS" if not caption_issues else "FAIL", caption_issues or {"captionCount": len(captions)})

    script_meta = delivery.get("script") if isinstance(delivery, dict) else {}
    script_path = safe_delivery_file(script_meta.get("path") if isinstance(script_meta, dict) else None)
    actual_script_hash = sha256_file(script_path) if script_path else None
    expected_script_hash = script_meta.get("sha256") if isinstance(script_meta, dict) else None
    script_info = {"path": str(script_path.relative_to(DELIVERY_DIR)) if script_path else None, "expectedSha256": expected_script_hash, "actualSha256": actual_script_hash}
    measured["sourceScript"] = script_info
    record("source_script_hash", "PASS" if actual_script_hash and actual_script_hash == expected_script_hash else "FAIL", script_info)

    forbidden = re.compile(r"Math\.random\s*\(|Date\.now\s*\(|rotateX|rotateY|perspective|WebGL", re.IGNORECASE)
    source_files = sorted(path for path in (PROJECT_DIR / "src").rglob("*") if path.is_file())
    forbidden_hits: list[str] = []
    for path in source_files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if forbidden.search(line):
                forbidden_hits.append(str(path.relative_to(PROJECT_DIR)) + ":" + str(line_number))
    if not source_files:
        forbidden_hits.append("src/ is missing or empty")
    record("deterministic_2d_source_scan", "PASS" if not forbidden_hits else "FAIL", forbidden_hits or {"filesScanned": len(source_files)})

    synthesis_path = DELIVERY_DIR / "review" / "audio-synthesis.json"
    if synthesis_path.is_file():
        try:
            synthesis = read_json(synthesis_path)
            cues = synthesis.get("cues", []) if isinstance(synthesis, dict) else []
            cue_map = {cue.get("id"): cue for cue in cues if isinstance(cue, dict)}
            synth_ok = len(cues) == 8 and set(cue_map) == set(EXPECTED_IDS) and all(
                cue_map[item].get("actualModel") == authorization.get("expectedEffectiveModel")
                and cue_map[item].get("actualVoice") == authorization.get("voice") for item in EXPECTED_IDS
            )
            synthesis_info = {"sha256": sha256_file(synthesis_path), "cueIds": sorted(cue_map), "cueCount": len(cues)}
            record("measured_synthesis_identity", "PASS" if synth_ok else "FAIL", synthesis_info)
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            record("measured_synthesis_identity", "FAIL", str(exc))
    else:
        record("measured_synthesis_identity", "SKIPPED", "No synthesis report exists yet")

    master_rel = (delivery.get("audio") or {}).get("master") if isinstance(delivery, dict) else None
    master_path = safe_delivery_file(master_rel)
    if master_path:
        try:
            master_format, silence, master_stable, master_ok = inspect_master(master_path)
            mix_path = DELIVERY_DIR / "review" / "audio-mix-qa.json"
            mix = read_json(mix_path) if mix_path.is_file() else {}
            master_sha = sha256_file(master_path)
            mix_ok = isinstance(mix, dict) and mix.get("status") == "pass" and mix.get("masterSha256") == master_sha
            measured["audioMaster"] = {"path": str(master_path.relative_to(DELIVERY_DIR)), "sha256": master_sha, "format": master_format, "exactSilence": silence, "stableDuringRead": master_stable}
            record("pcm_master_format_and_silence", "PASS" if master_ok else "FAIL", measured["audioMaster"])
            record("audio_mix_qa_bound_to_master", "PASS" if mix_ok else "FAIL", {"status": mix.get("status"), "masterShaMatches": mix.get("masterSha256") == master_sha})
        except (OSError, wave.Error, EOFError, struct.error, json.JSONDecodeError) as exc:
            record("pcm_master_format_and_silence", "FAIL", str(exc))
    else:
        record("pcm_master_format_and_silence", "SKIPPED", "No PCM master exists yet")
        record("audio_mix_qa_bound_to_master", "SKIPPED", "No PCM master exists yet")

    qa = delivery.get("qa", {}) if isinstance(delivery, dict) else {}
    report = {
        "schemaVersion": 1,
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project": WORK_ID,
        "automatedStatus": "FAIL" if any(check["status"] == "FAIL" for check in checks) else "PASS",
        "checksSummary": {status.lower(): sum(check["status"] == status for check in checks) for status in ("PASS", "FAIL", "SKIPPED")},
        "checks": checks,
        "measured": measured,
        "humanAcceptance": {
            "representativeFrames": str(qa.get("representative_frames", "pending")).upper(),
            "continuousHumanReview": str(qa.get("continuous_human_review", "pending")).upper(),
            "targetDevicePlayback": str(qa.get("target_device_playback", "pending")).upper(),
            "automatedQa": str(qa.get("automated", "pending")).upper(),
        },
    }
    if args.no_write:
        report["reportPath"] = None
    else:
        if REPORT_PATH.exists():
            raise FileExistsError("Refusing to overwrite existing project-check.json")
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        report["reportPath"] = str(REPORT_PATH.relative_to(DELIVERY_DIR))
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["automatedStatus"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
