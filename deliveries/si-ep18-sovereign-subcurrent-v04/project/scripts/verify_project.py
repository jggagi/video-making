#!/usr/bin/env python3
"""Check EP18 v04 source contracts and report media/human gates separately.

This source-only verifier uses files inside this delivery. It does not render,
decode, import Downloads, or claim visual, narration, playback, or publication
acceptance.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT = Path(__file__).resolve().parents[1]
DELIVERY = PROJECT.parent
REVIEW = DELIVERY / "review"
REPORT_PATH = REVIEW / "project-verification.json"
WORK_ID = "si-ep18-sovereign-subcurrent-v04"
EXPECTED_IDS = [f"S{i:02d}" for i in range(1, 9)]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_hash(path: Path) -> dict[str, Any]:
    before = path.stat()
    digest = sha256_file(path)
    after = path.stat()
    stable = (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    return {"sha256": digest, "bytes": after.st_size, "stableDuringHash": stable}


def record(checks: list[dict[str, Any]], name: str, status: str, details: Any) -> None:
    checks.append({"name": name, "status": status, "details": details})


def is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def source_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    if REPORT_PATH.exists():
        print("verify_project: refusing to overwrite existing project-verification.json", file=sys.stderr)
        return 2

    checks: list[dict[str, Any]] = []
    input_hashes: dict[str, Any] = {}
    loaded: dict[str, Any] = {}
    input_files = {
        "delivery": DELIVERY / "delivery.json",
        "contentChecklist": PROJECT / "content-checklist.json",
        "renderPlan": PROJECT / "render-plan.json",
        "segments": PROJECT / "segments.json",
        "captions": PROJECT / "captions.json",
        "audioPlan": PROJECT / "audio-plan.json",
        "audioTiming": PROJECT / "audio-timing.json",
        "timeline": PROJECT / "timeline.json",
        "sfxEvents": PROJECT / "sfx_events.json",
    }
    for name, path in input_files.items():
        relative = str(path.relative_to(DELIVERY))
        try:
            loaded[name] = read_json(path)
            fingerprint = stable_hash(path)
            input_hashes[relative] = fingerprint
            record(checks, "read_" + name, "PASS" if fingerprint["stableDuringHash"] else "FAIL", fingerprint)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            loaded[name] = None
            input_hashes[relative] = {"status": "MISSING_OR_INVALID"}
            record(checks, "read_" + name, "PENDING" if name == "audioTiming" else "FAIL", str(exc))

    delivery = loaded.get("delivery") if isinstance(loaded.get("delivery"), dict) else {}
    plan = loaded.get("renderPlan") if isinstance(loaded.get("renderPlan"), dict) else {}
    checklist = loaded.get("contentChecklist") if isinstance(loaded.get("contentChecklist"), dict) else {}
    segments = loaded.get("segments") if isinstance(loaded.get("segments"), list) else []
    captions = loaded.get("captions") if isinstance(loaded.get("captions"), list) else []
    audio_plan = loaded.get("audioPlan") if isinstance(loaded.get("audioPlan"), dict) else {}
    audio_timing = loaded.get("audioTiming") if isinstance(loaded.get("audioTiming"), dict) else {}
    timeline = loaded.get("timeline") if isinstance(loaded.get("timeline"), dict) else {}
    sfx = loaded.get("sfxEvents") if isinstance(loaded.get("sfxEvents"), dict) else {}

    title = delivery.get("title")
    work = plan.get("work") if isinstance(plan.get("work"), dict) else {}
    composition = plan.get("composition") if isinstance(plan.get("composition"), dict) else {}
    content = checklist.get("narration") if isinstance(checklist.get("narration"), dict) else {}
    story_anchors = checklist.get("storyAnchors") if isinstance(checklist.get("storyAnchors"), dict) else {}
    scene_contract = checklist.get("scene") if isinstance(checklist.get("scene"), dict) else {}
    plan_frames = plan.get("frames") if isinstance(plan.get("frames"), dict) else {}
    planned_anchors = plan_frames.get("anchors") if isinstance(plan_frames.get("anchors"), dict) else {}
    expected_frames = composition.get("durationInFrames")
    expected_fps = composition.get("fps")

    identity_ok = (
        delivery.get("slug") == WORK_ID == work.get("id")
        and isinstance(title, str) and title == work.get("title") == "心印潜流 · 人与影 · v04"
        and delivery.get("platforms") == [work.get("platform")] == ["xiaohongshu"]
        and delivery.get("duration_seconds") == 90
        and delivery.get("fps") == expected_fps == 60
        and delivery.get("total_frames") == expected_frames == 5400
    )
    record(checks, "delivery_identity_and_duration", "PASS" if identity_ok else "FAIL", {
        "id": delivery.get("slug"), "title": title, "platforms": delivery.get("platforms"),
        "durationSeconds": delivery.get("duration_seconds"), "fps": delivery.get("fps"),
        "frames": delivery.get("total_frames"),
    })

    script_meta = delivery.get("script") if isinstance(delivery.get("script"), dict) else {}
    script_relative = script_meta.get("path")
    script_path = (DELIVERY / script_relative).resolve() if isinstance(script_relative, str) else None
    try:
        if script_path is None or not script_path.is_relative_to(DELIVERY.resolve()) or not script_path.is_file():
            raise OSError("delivery.json original script path is missing or outside this delivery")
        script_fingerprint = stable_hash(script_path)
        expected_script_sha = script_meta.get("sha256")
        script_ok = script_fingerprint["stableDuringHash"] and script_fingerprint["sha256"] == expected_script_sha
        input_hashes[str(script_path.relative_to(DELIVERY))] = script_fingerprint
        record(checks, "original_script_preserved_byte_hash", "PASS" if script_ok else "FAIL", {
            "path": script_relative, "expectedSha256": expected_script_sha, **script_fingerprint,
        })
    except (OSError, ValueError) as exc:
        record(checks, "original_script_preserved_byte_hash", "FAIL", str(exc))

    revision_path = PROJECT / "adapted-script.md"
    revision_ok = revision_path.is_file() and revision_path.stat().st_size > 0
    if revision_ok:
        input_hashes["project/adapted-script.md"] = stable_hash(revision_path)
    record(checks, "user_revision_retained", "PASS" if revision_ok else "FAIL", {
        "path": "project/adapted-script.md", "exists": revision_ok,
    })

    segment_ids = [row.get("id") for row in segments if isinstance(row, dict)]
    texts = [row.get("display_subtitle") for row in segments if isinstance(row, dict)]
    spoken = [row.get("tts_phonetic_text") for row in segments if isinstance(row, dict)]
    narration = "".join(value for value in texts if isinstance(value, str))
    count_expected = content.get("characterCount")
    ids_expected = content.get("orderedIds")
    required_numbers = content.get("requiredStoryNumbers", [])
    numbers_ok = all(any(isinstance(token, str) and token in narration for token in alternatives)
                     for alternatives in required_numbers if isinstance(alternatives, list))
    cue_text_ok = (
        segment_ids == ids_expected == EXPECTED_IDS
        and len(segments) == content.get("segmentCount") == 8
        and len(narration) == count_expected == 181
        and len(spoken) == len(texts) == 8
        and all(isinstance(a, str) and a == b for a, b in zip(texts, spoken))
        and numbers_ok
    )
    record(checks, "eight_current_narration_cues", "PASS" if cue_text_ok else "FAIL", {
        "ids": segment_ids, "characterCountIncludingPunctuation": len(narration),
        "expectedCharacterCount": count_expected, "displayEqualsTts": len(spoken) == len(texts) == 8 and all(a == b for a, b in zip(texts, spoken)),
        "requiredStoryNumbersPresent": numbers_ok,
    })

    revision_text_ok = False
    try:
        revision_text = source_text(revision_path)
        blocks = re.split(r"(?m)^## (S\d{2})\s*$", revision_text)
        revision_rows = {blocks[i]: blocks[i + 1].strip() for i in range(1, len(blocks) - 1, 2)}
        revision_text_ok = list(revision_rows) == EXPECTED_IDS and all(
            revision_rows.get(row.get("id")) == row.get("display_subtitle")
            for row in segments if isinstance(row, dict)
        )
    except (OSError, UnicodeDecodeError):
        pass
    record(checks, "retained_revision_matches_current_cues", "PASS" if revision_text_ok else "FAIL", {
        "path": "project/adapted-script.md", "matchesAllEightCues": revision_text_ok,
    })

    natural_instruction = audio_plan.get("instruction")
    brisk_terms = ("快语速", "快速朗读", "加快语速", "快节奏", "brisk", "speed up")
    has_natural_language = isinstance(natural_instruction, str) and any(
        cue in natural_instruction for cue in ("常速", "自然说话", "自然的节奏")
    )
    excludes_brisk = isinstance(natural_instruction, str) and not any(term.casefold() in natural_instruction.casefold() for term in brisk_terms)
    pacing_ok = audio_plan.get("rate") == content.get("audioPlanRate") == 1.0 and has_natural_language and excludes_brisk
    record(checks, "natural_rate_one_narration", "PASS" if pacing_ok else "FAIL", {
        "rate": audio_plan.get("rate"), "instruction": natural_instruction,
        "naturalPaceSpecified": has_natural_language, "briskPaceSpecified": not excludes_brisk,
    })

    output_path = ((delivery.get("outputs") or {}).get("xiaohongshu") or {}).get("path")
    planned_output = (plan.get("output") or {}).get("path")
    native_ok = (
        composition.get("id") == checklist.get("scene", {}).get("compositionId") == "PortraitVertical"
        and composition.get("component") == checklist.get("scene", {}).get("component") == "Film"
        and (composition.get("width"), composition.get("height")) == (2160, 3840)
        and composition.get("logicalCanvas") == {"width": 1080, "height": 1920}
        and output_path == planned_output
        and isinstance(delivery.get("outputs"), dict)
        and (delivery["outputs"]["xiaohongshu"].get("width"), delivery["outputs"]["xiaohongshu"].get("height")) == (2160, 3840)
    )
    record(checks, "native_portrait_composition_contract", "PASS" if native_ok else "FAIL", {
        "composition": composition, "output": output_path,
    })

    root_path, film_path, scene_path = (PROJECT / "src" / name for name in ("Root.tsx", "Film.tsx", "Scene.tsx"))
    try:
        root_text, film_text, scene_text = (source_text(path) for path in (root_path, film_path, scene_path))
        root_ok = all(re.search(pattern, root_text) for pattern in (
            r"id\s*=\s*[\"']PortraitVertical[\"']",
            r"component\s*=\s*\{?Film\}?",
            r"width\s*=\s*\{?2160\}?",
            r"height\s*=\s*\{?3840\}?",
            r"fps\s*=\s*\{?60\}?",
            r"durationInFrames\s*=\s*\{?5400\}?",
        ))
        caption_group = re.search(r"\{cap&&<g(?P<group>.*?)</g>\}", film_text, re.DOTALL)
        caption_font = re.search(r"fontSize\s*=\s*[\"'](\d+(?:\.\d+)?)[\"']", caption_group.group("group")) if caption_group else None
        caption_font_size = float(caption_font.group(1)) if caption_font else 0
        planned_covers = plan_frames.get("coverFrames") if isinstance(plan_frames.get("coverFrames"), dict) else {}
        cover_source_ok = all(
            f"cover==='{kind}'?{frame}" in film_text for kind, frame in planned_covers.items()
        ) and set(planned_covers) == {"A", "B"}
        film_layout_ok = (
            "lines.length>2" in film_text and "Array.from(l).length>17" in film_text
            and "captions" in film_text and caption_font_size >= scene_contract.get("captionMinimumFontSize", 43)
        )
        scene_names = scene_contract.get("requiredHumanShadowHelpers", [])
        scene_ok = (
            "export const WIDTH = 1080" in scene_text and "export const HEIGHT = 1920" in scene_text
            and "export const NATIVE_WIDTH = 2160" in scene_text and "export const NATIVE_HEIGHT = 3840" in scene_text
            and "export const drawScene = (context: CanvasRenderingContext2D, frame: number)" in scene_text
            and "export const Scene: React.FC<{frame: number}>" in scene_text
            and all(re.search(r"\b" + re.escape(name) + r"\b", scene_text) for name in scene_names)
            and "drawScene(context, frame)" in scene_text
            and "<Scene frame={frame}/>" in film_text
        )
        input_hashes.update({
            "project/src/Root.tsx": stable_hash(root_path),
            "project/src/Film.tsx": stable_hash(film_path),
            "project/src/Scene.tsx": stable_hash(scene_path),
            "project/captions.json": stable_hash(PROJECT / "captions.json"),
        })
        record(checks, "composition_source_matches_plan", "PASS" if root_ok else "FAIL", {"source": "project/src/Root.tsx", "matchesPlan": root_ok})
        record(checks, "human_shadow_scene_source_contract", "PASS" if scene_ok else "FAIL", {
            "source": "project/src/Scene.tsx", "hasRequiredHelpers": scene_names,
            "sourceContractOnly": True,
        })
        record(checks, "mobile_caption_source_contract", "PASS" if film_layout_ok else "FAIL", {
            "source": "project/src/Film.tsx", "fontSize": caption_font_size,
            "minimumFontSize": scene_contract.get("captionMinimumFontSize", 43),
            "maximumRows": scene_contract.get("captionMaximumRows", 2),
            "maximumCharactersPerRow": scene_contract.get("captionMaximumCharactersPerRow", 17),
        })
        record(checks, "cover_source_frames_match_plan", "PASS" if cover_source_ok else "FAIL", {
            "plannedCoverFrames": planned_covers, "sourceMatchesPlan": cover_source_ok,
        })
    except (OSError, UnicodeDecodeError) as exc:
        record(checks, "composition_source_matches_plan", "FAIL", str(exc))
        record(checks, "human_shadow_scene_source_contract", "FAIL", str(exc))
        record(checks, "mobile_caption_source_contract", "FAIL", str(exc))
        record(checks, "cover_source_frames_match_plan", "FAIL", str(exc))

    caption_issues: list[str] = []
    caption_texts: dict[str, list[str]] = {cue_id: [] for cue_id in EXPECTED_IDS}
    previous_end = -1
    for index, row in enumerate(captions):
        if not isinstance(row, dict):
            caption_issues.append(f"caption[{index}] is not an object")
            continue
        cue_id, start, end, text = row.get("id"), row.get("startFrame"), row.get("endFrame"), row.get("text")
        if cue_id not in caption_texts:
            caption_issues.append(f"caption[{index}] has an unknown cue id")
        if not (is_int(start) and is_int(end) and 0 <= start < end <= expected_frames):
            caption_issues.append(f"caption[{index}] has invalid half-open frame bounds")
        else:
            if start < previous_end:
                caption_issues.append(f"caption[{index}] overlaps or is out of order")
            previous_end = end
        if not isinstance(text, str) or not text:
            caption_issues.append(f"caption[{index}] has no text")
            continue
        lines = text.splitlines() or [text]
        if len(lines) > scene_contract.get("captionMaximumRows", 2) or any(
            len(line) > scene_contract.get("captionMaximumCharactersPerRow", 17) for line in lines
        ):
            caption_issues.append(f"caption[{index}] exceeds the planned mobile line layout")
        if cue_id in caption_texts:
            caption_texts[cue_id].append(text.replace("\n", "").replace("\r", ""))
    segment_map = {row.get("id"): row for row in segments if isinstance(row, dict)}
    for cue_id in EXPECTED_IDS:
        if "".join(caption_texts[cue_id]) != segment_map.get(cue_id, {}).get("display_subtitle"):
            caption_issues.append(cue_id + " captions do not preserve the exact displayed cue text")
    captions_ok = len(captions) > 0 and not caption_issues
    record(checks, "caption_text_and_mobile_layout", "PASS" if captions_ok else "FAIL", {
        "captionCount": len(captions), "cueCaptionCounts": {key: len(value) for key, value in caption_texts.items()},
        "maxRows": scene_contract.get("captionMaximumRows"),
        "maxCharactersPerRow": scene_contract.get("captionMaximumCharactersPerRow"),
        "issues": caption_issues,
    })

    events = timeline.get("events") if isinstance(timeline.get("events"), dict) else {}
    expected_silence = planned_anchors.get("silenceRangeHalfOpen")
    expected_confirm = planned_anchors.get("confirm")
    expected_heartbeat = planned_anchors.get("doubleHeartbeat")
    expected_cyan_eye = planned_anchors.get("cyanEyeDetailFromFrame")
    timeline_rows = timeline.get("scenes") if isinstance(timeline.get("scenes"), list) else []
    scene_windows = [(row.get("startFrame"), row.get("endFrame")) for row in timeline_rows if isinstance(row, dict)]
    contiguous = bool(scene_windows) and scene_windows[0][0] == 0 and scene_windows[-1][1] == expected_frames
    contiguous = contiguous and all(a[1] == b[0] and is_int(a[0]) and is_int(a[1]) for a, b in zip(scene_windows, scene_windows[1:]))
    anchors_ok = (
        timeline.get("fps") == expected_fps and timeline.get("durationFrames") == expected_frames
        and len(timeline_rows) == content.get("segmentCount") == 8 and contiguous
        and events.get("confirm") == story_anchors.get("confirmFrame") == expected_confirm
        and events.get("silenceRange") == story_anchors.get("silenceRangeHalfOpen") == expected_silence
        and events.get("doubleHeartbeat") == story_anchors.get("doubleHeartbeatFrame") == expected_heartbeat
        and story_anchors.get("cyanEyeDetailFromFrame") == expected_cyan_eye
        and sfx.get("silenceRangeFrames") == expected_silence
    )
    record(checks, "timeline_story_anchors", "PASS" if anchors_ok else "FAIL", {
        "confirm": events.get("confirm"), "silenceRangeHalfOpen": events.get("silenceRange"),
        "doubleHeartbeat": events.get("doubleHeartbeat"), "cyanEyeFromFrame": story_anchors.get("cyanEyeDetailFromFrame"),
        "sceneCount": len(timeline_rows), "contiguousSceneWindows": contiguous,
        "sfxSilenceRangeFrames": sfx.get("silenceRangeFrames"),
    })

    if audio_timing:
        timing_rows = {row.get("id"): row for row in audio_timing.get("segments", []) if isinstance(row, dict)}
        segment_timing_ok = len(timing_rows) == len(segments) == 8
        for row in segments:
            timing = timing_rows.get(row.get("id"))
            if not timing:
                segment_timing_ok = False
                continue
            segment_timing_ok = segment_timing_ok and timing.get("placementStartFrame") == row.get("startFrame")
            if row.get("id") == "S06":
                segment_timing_ok = segment_timing_ok and timing.get("activeEndFrameExclusive", expected_frames + 1) <= events.get("confirm", 0)
                segment_timing_ok = segment_timing_ok and row.get("originalWindow") == timing.get("originalSourceWindowFrames")
        record(checks, "measured_audio_timing_follows_current_cue_anchors", "PASS" if segment_timing_ok else "FAIL", {
            "s06CurrentStartFrame": next((row.get("startFrame") for row in segments if row.get("id") == "S06"), None),
            "s06OriginalWindowPreserved": next((row.get("originalWindow") for row in segments if row.get("id") == "S06"), None),
            "s06MeasuredActiveEndFrameExclusive": timing_rows.get("S06", {}).get("activeEndFrameExclusive"),
            "confirmFrame": events.get("confirm"),
        })
    else:
        record(checks, "measured_audio_timing_follows_current_cue_anchors", "PENDING", "audio-timing.json is not yet present")

    xhs = ((delivery.get("outputs") or {}).get("xiaohongshu") or {})
    movie_relative = xhs.get("path")
    movie_path = (DELIVERY / movie_relative).resolve() if isinstance(movie_relative, str) else None
    if movie_path is None or not movie_path.is_relative_to(DELIVERY.resolve()):
        record(checks, "actual_movie_file", "FAIL", {"path": movie_relative, "error": "invalid or escaping output path"})
        movie_status: dict[str, Any] = {"status": "INVALID_PATH", "path": movie_relative}
    elif not movie_path.is_file():
        record(checks, "actual_movie_file", "PENDING", {"path": movie_relative, "reason": "final movie does not exist yet"})
        movie_status = {"status": "PENDING_UNTIL_ACTUAL_FILE_EXISTS", "path": movie_relative}
    else:
        movie_fingerprint = stable_hash(movie_path)
        record(checks, "actual_movie_file", "PASS" if movie_fingerprint["stableDuringHash"] else "FAIL", movie_fingerprint)
        movie_status = {"status": "PRESENT_NOT_QA_ACCEPTED", "path": movie_relative, **movie_fingerprint}

    failed = [check for check in checks if check["status"] == "FAIL"]
    source_status = "FAIL" if failed else "SOURCE_CHECKS_PASS"
    report = {
        "schemaVersion": 1,
        "createdAtUtc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "work": {"id": WORK_ID, "title": title, "platform": "xiaohongshu"},
        "status": source_status,
        "movie": movie_status,
        "checks": checks,
        "inputFiles": input_hashes,
        "humanAcceptance": {
            "representativeFrames": "PENDING",
            "continuousHumanReview": "PENDING",
            "targetDevicePlayback": "PENDING",
            "accountPublication": "NOT_SUBMITTED",
        },
        "scope": "Source and manifest checks only. This report does not accept the human visuals, narration performance, continuous playback, or target-device experience.",
    }
    REVIEW.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "report": str(REPORT_PATH.relative_to(DELIVERY)), "movie": movie_status, "failedChecks": [item["name"] for item in failed]}, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
