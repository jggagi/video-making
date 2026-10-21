#!/usr/bin/env python3
"""Verify EP12 source invariants without changing project or QA files.

This checks the composition source and reports evidence status to stdout. It
does not render or inspect the final video, and it does not record human or
model review.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DELIVERY_DIR = PROJECT_DIR.parent
EXPECTED_SEGMENTS = (
    ("S01", 60, 540),
    ("S02", 600, 1260),
    ("S03", 1320, 1980),
    ("S04", 2040, 2760),
    ("S05", 2820, 3540),
    ("S06", 3600, 4320),
    ("S07", 4380, 4800),
    ("S08", 4860, 5400),
)
EXPECTED_WIDTH = 2160
EXPECTED_HEIGHT = 3840
EXPECTED_FPS = 60
EXPECTED_FRAMES = 5400
LOGICAL_WIDTH = 1080
LOGICAL_HEIGHT = 1920


def normalized_whitespace(text: str) -> str:
    """Remove whitespace only; retain punctuation and quote differences."""
    return re.sub(r"\s+", "", text)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path, label: str, failures: list[str], incomplete: list[str]) -> Any | None:
    if not path.is_file():
        incomplete.append(f"missing {label}: {path.relative_to(DELIVERY_DIR).as_posix()}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        failures.append(f"cannot read {label}: {exc}")
        return None


def check(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def source_script_rows(failures: list[str], incomplete: list[str]) -> dict[str, str]:
    path = DELIVERY_DIR / "source/script.md"
    if not path.is_file():
        incomplete.append("source/script.md is missing; source text check is pending")
        return {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        failures.append(f"cannot read source/script.md: {exc}")
        return {}

    rows: dict[str, str] = {}
    for line in lines:
        match = re.match(r"^\|\s*\*\*(S\d{2})\*\*\s*\|", line)
        if not match:
            continue
        cells = line.split("|")
        if len(cells) < 5:
            failures.append(f"source subtitle row {match.group(1)} is malformed")
            continue
        text = re.sub(r"<br\s*/?>", "\n", cells[3], flags=re.IGNORECASE)
        rows[match.group(1)] = text.replace("`", "").strip()
    expected_ids = [item[0] for item in EXPECTED_SEGMENTS]
    check(list(rows) == expected_ids, "source script must contain the eight ordered subtitle rows", failures)
    return rows


def verify_delivery_manifest(failures: list[str], incomplete: list[str]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    manifest = read_json(DELIVERY_DIR / "delivery.json", "delivery.json", failures, incomplete)
    report: dict[str, Any] = {"status": "INCOMPLETE"}
    if not isinstance(manifest, dict):
        if manifest is not None:
            failures.append("delivery.json must contain a JSON object")
        return None, report

    actual_timing = (manifest.get("duration_seconds"), manifest.get("fps"), manifest.get("total_frames"))
    expected_timing = (90, EXPECTED_FPS, EXPECTED_FRAMES)
    check(actual_timing == expected_timing,
          f"delivery timing must be 90 seconds / 60 fps / 5400 frames, got {actual_timing}", failures)

    script = manifest.get("script")
    script_report: dict[str, Any] = {"path": None, "expected_sha256": None, "actual_sha256": None}
    if not isinstance(script, dict) or not isinstance(script.get("path"), str):
        failures.append("delivery.json script.path is missing")
    else:
        script_path = (DELIVERY_DIR / script["path"]).resolve()
        try:
            script_path.relative_to(DELIVERY_DIR.resolve())
        except ValueError:
            failures.append("delivery.json script.path escapes the delivery folder")
        else:
            script_report["path"] = script_path.relative_to(DELIVERY_DIR).as_posix()
            script_report["expected_sha256"] = script.get("sha256")
            if not script_path.is_file():
                incomplete.append(f"missing source script: {script_report['path']}")
            elif not isinstance(script.get("sha256"), str):
                failures.append("delivery.json script.sha256 is missing")
            else:
                actual_hash = sha256_file(script_path)
                script_report["actual_sha256"] = actual_hash
                script_report["matches_manifest"] = actual_hash == script["sha256"]
                check(actual_hash == script["sha256"], "source script SHA-256 differs from delivery.json", failures)

    outputs = manifest.get("outputs")
    portrait = outputs.get("xiaohongshu") if isinstance(outputs, dict) else None
    if not isinstance(portrait, dict):
        failures.append("delivery.json outputs.xiaohongshu is missing")
        portrait_report: dict[str, Any] = {}
    else:
        check((portrait.get("width"), portrait.get("height")) == (EXPECTED_WIDTH, EXPECTED_HEIGHT),
              f"portrait output must be native {EXPECTED_WIDTH}x{EXPECTED_HEIGHT}", failures)
        portrait_report = {
            "path": portrait.get("path"),
            "width": portrait.get("width"),
            "height": portrait.get("height"),
        }

    report.update({
        "duration_seconds": manifest.get("duration_seconds"),
        "fps": manifest.get("fps"),
        "total_frames": manifest.get("total_frames"),
        "script": script_report,
        "portrait_output": portrait_report,
    })
    return manifest, report


def verify_segments(failures: list[str], incomplete: list[str]) -> dict[str, Any]:
    data = read_json(PROJECT_DIR / "segments.json", "project/segments.json", failures, incomplete)
    expected_source_rows = source_script_rows(failures, incomplete)
    if not isinstance(data, list):
        if data is not None:
            failures.append("segments.json must be an array")
        return {"count": 0, "windows": []}

    actual_ids = [item.get("id") for item in data if isinstance(item, dict)]
    expected_ids = [entry[0] for entry in EXPECTED_SEGMENTS]
    check(actual_ids == expected_ids, "segments.json must contain S01-S08 in order", failures)
    windows: list[dict[str, Any]] = []
    for index, (segment_id, start, end) in enumerate(EXPECTED_SEGMENTS):
        if index >= len(data):
            break
        segment = data[index]
        if not isinstance(segment, dict):
            failures.append(f"segment {index + 1} must be a JSON object")
            continue
        check(segment.get("id") == segment_id, f"segment {index + 1} id must be {segment_id}", failures)
        actual_window = (segment.get("startFrame"), segment.get("endFrame"))
        check(actual_window == (start, end), f"{segment_id} must use half-open frame window [{start}, {end})", failures)
        check(type(segment.get("startFrame")) is int and type(segment.get("endFrame")) is int
              and 0 <= segment["startFrame"] < segment["endFrame"] <= EXPECTED_FRAMES,
              f"{segment_id} window falls outside source frames [0, {EXPECTED_FRAMES})", failures)

        display = segment.get("display_subtitle")
        check(isinstance(display, str), f"{segment_id} display_subtitle must be text", failures)
        if isinstance(display, str) and segment_id in expected_source_rows:
            check(normalized_whitespace(display) == normalized_whitespace(expected_source_rows[segment_id]),
                  f"{segment_id} display text differs from source/script.md beyond whitespace", failures)
        check(isinstance(segment.get("tts_phonetic_text"), str), f"{segment_id} tts_phonetic_text must be text", failures)
        windows.append({"id": segment_id, "start_frame": actual_window[0], "end_frame_exclusive": actual_window[1]})

    return {"count": len(data), "windows": windows}


def _strip_comments(source: str) -> str:
    """Remove JS/CSS comments while leaving quoted CSS/JS values available to scan."""
    output: list[str] = []
    index = 0
    quote: str | None = None
    escaped = False
    line_comment = False
    block_comment = False
    while index < len(source):
        char = source[index]
        nxt = source[index + 1] if index + 1 < len(source) else ""
        if line_comment:
            if char in "\r\n":
                line_comment = False
                output.append(char)
            else:
                output.append(" ")
            index += 1
            continue
        if block_comment:
            if char == "*" and nxt == "/":
                output.extend((" ", " "))
                block_comment = False
                index += 2
            else:
                output.append("\n" if char == "\n" else " ")
                index += 1
            continue
        if quote is not None:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in "'\"`":
            quote = char
            output.append(char)
            index += 1
            continue
        if char == "/" and nxt == "/":
            output.extend((" ", " "))
            line_comment = True
            index += 2
            continue
        if char == "/" and nxt == "*":
            output.extend((" ", " "))
            block_comment = True
            index += 2
            continue
        output.append(char)
        index += 1
    return "".join(output)


FORBIDDEN_SOURCE_PATTERNS = (
    (re.compile(r"\bMath\s*\.\s*random\s*\("), "Math.random()"),
    (re.compile(r"\bDate\s*\.\s*now\s*\("), "Date.now()"),
    (re.compile(r"\b(?:perspective|rotateX|rotateY|matrix3d)\s*\(", re.IGNORECASE), "3D/pseudo-3D transform function"),
    (re.compile(r"\bWebGL(?:2?RenderingContext|Renderer)?\b", re.IGNORECASE), "WebGL"),
    (re.compile(r"\bTHREE\b"), "Three.js identifier"),
    (re.compile(r"(?:\bfrom\s*|\brequire\s*\(\s*)['\"](?:three|@react-three/[^'\"]+)['\"]"), "Three.js import"),
    (re.compile(r"\bgetContext\s*\(\s*['\"]webgl2?['\"]", re.IGNORECASE), "WebGL context"),
    (re.compile(r"(?:^|[;{\s])@keyframes\b", re.IGNORECASE | re.MULTILINE), "CSS keyframe animation"),
    (re.compile(r"(?:^|[;{\s])animation(?:-[a-z-]+)?\s*:", re.IGNORECASE | re.MULTILINE), "CSS animation property"),
    (re.compile(r"\.\s*animate\s*\("), "Web Animations API call"),
)


def verify_source_code(failures: list[str], incomplete: list[str]) -> dict[str, Any]:
    src_dir = PROJECT_DIR / "src"
    suffixes = {".ts", ".tsx", ".js", ".jsx", ".css"}
    source_files = sorted(path for path in src_dir.rglob("*") if path.is_file() and path.suffix in suffixes) if src_dir.is_dir() else []
    if not source_files:
        incomplete.append("no TypeScript/JavaScript/CSS sources found under project/src")
    violations: list[dict[str, str]] = []
    source_hashes: dict[str, str] = {}
    for path in source_files:
        try:
            raw_source = path.read_text(encoding="utf-8")
            source_hashes[path.relative_to(PROJECT_DIR).as_posix()] = sha256_file(path)
            source = _strip_comments(raw_source)
        except (OSError, UnicodeError) as exc:
            failures.append(f"cannot read source file {path.relative_to(PROJECT_DIR).as_posix()}: {exc}")
            continue
        for pattern, label in FORBIDDEN_SOURCE_PATTERNS:
            if pattern.search(source):
                rel = path.relative_to(PROJECT_DIR).as_posix()
                violations.append({"file": rel, "rule": label})
                failures.append(f"forbidden source use of {label} in {rel}")

    root_path = src_dir / "Root.tsx"
    film_path = src_dir / "Film.tsx"
    root = ""
    film = ""
    if not root_path.is_file():
        incomplete.append("missing project/src/Root.tsx; composition checks are pending")
    else:
        root = _strip_comments(root_path.read_text(encoding="utf-8"))
        check(bool(re.search(r"\bid\s*=\s*['\"]PortraitVertical['\"]", root)),
              "Root.tsx must define the PortraitVertical composition", failures)
        check(bool(re.search(r"\bwidth\s*=\s*\{\s*2160\s*\}", root))
              and bool(re.search(r"\bheight\s*=\s*\{\s*3840\s*\}", root)),
              "PortraitVertical composition must be 2160x3840", failures)
        check(bool(re.search(r"\bfps\s*=\s*\{\s*60\s*\}", root))
              and bool(re.search(r"\bdurationInFrames\s*=\s*\{\s*5400\s*\}", root)),
              "PortraitVertical composition must be 60 fps and 5400 frames", failures)

    if not film_path.is_file():
        incomplete.append("missing project/src/Film.tsx; local typography checks are pending")
    else:
        film = _strip_comments(film_path.read_text(encoding="utf-8"))
    logical_canvas = bool(re.search(r"width\s*:\s*1080\s*,\s*height\s*:\s*1920", film))
    scaled_canvas = bool(re.search(r"scale\s*\(\s*\$\{\s*width\s*/\s*1080\s*\}\s*\)", film))
    check(logical_canvas and scaled_canvas, "Film.tsx must render a 1080x1920 logical canvas scaled to native width / 1080", failures)

    hud_expected = {
        "left": 64, "top": 174, "width": 856, "fontSize": 30, "lineHeight": "32px",
    }
    hud_match = re.search(r"\{\s*position\s*:\s*'absolute'\s*,\s*left\s*:\s*64\s*,\s*top\s*:\s*174\s*,\s*width\s*:\s*856\s*,[\s\S]*?fontSize\s*:\s*30\s*,\s*lineHeight\s*:\s*'32px'", film)
    hud_right = hud_expected["left"] + hud_expected["width"]
    right_safe = 0.86 * LOGICAL_WIDTH
    check(hud_match is not None, "Film.tsx HUD geometry must remain x64/top174/w856/font30/line32", failures)
    check(hud_right <= right_safe, f"HUD right edge {hud_right} exceeds right safe edge {right_safe:g}", failures)

    caption_match = re.search(r"data-caption[\s\S]*?\{\s*position\s*:\s*'absolute'\s*,\s*left\s*:\s*64\s*,\s*top\s*:\s*1384\s*,\s*width\s*:\s*856\s*,[\s\S]*?fontSize\s*:\s*49\s*,\s*lineHeight\s*:\s*'54px'", film)
    caption_right = 64 + 856
    caption_bottom_safe = 0.78 * LOGICAL_HEIGHT
    check(caption_match is not None, "Film.tsx subtitle geometry must remain x64/y1384/w856/font49/line54", failures)
    check(caption_right <= right_safe, f"subtitle right edge {caption_right} exceeds right safe edge {right_safe:g}", failures)
    subtitle_band = (0.72 * LOGICAL_HEIGHT, 0.76 * LOGICAL_HEIGHT)
    check(subtitle_band[0] <= 1384 <= subtitle_band[1], "subtitle anchor is outside the 24%-28% bottom reading band", failures)

    return {
        "source_files_scanned": len(source_files),
        "source_sha256": source_hashes,
        "forbidden_uses": violations,
        "composition": {
            "width": EXPECTED_WIDTH if "2160" in root else None,
            "height": EXPECTED_HEIGHT if "3840" in root else None,
            "fps": EXPECTED_FPS if "60" in root else None,
            "duration_frames": EXPECTED_FRAMES if "5400" in root else None,
            "logical_canvas": [LOGICAL_WIDTH, LOGICAL_HEIGHT],
            "native_scale": "native width / 1080 (expected 2x)",
        },
        "typography_contract": {
            "right_safe_edge_logical_px": right_safe,
            "bottom_safe_edge_logical_px": caption_bottom_safe,
            "hud": {**hud_expected, "rows": 3, "right_edge": hud_right, "fits_right_safe_edge": hud_right <= right_safe},
            "subtitle": {
                "left": 64, "top": 1384, "width": 856, "font_size": 49,
                "line_height": 54, "max_lines": 2, "maximum_box_height": 108,
                "maximum_bottom": 1384 + 2 * 54,
                "bottom_margin": caption_bottom_safe - (1384 + 2 * 54),
                "right_edge": caption_right,
            },
        },
    }


def verify_timeline(failures: list[str], incomplete: list[str]) -> dict[str, Any]:
    data = read_json(PROJECT_DIR / "timeline.json", "project/timeline.json", failures, incomplete)
    if not isinstance(data, dict):
        if data is not None:
            failures.append("timeline.json must contain a JSON object")
        return {"status": "INCOMPLETE"}
    canvas = data.get("canvas")
    check(isinstance(canvas, dict)
          and (canvas.get("nativeWidth"), canvas.get("nativeHeight"), canvas.get("fps"), canvas.get("durationInFrames"))
          == (EXPECTED_WIDTH, EXPECTED_HEIGHT, EXPECTED_FPS, EXPECTED_FRAMES),
          "timeline canvas must be native 2160x3840 at 60 fps for 5400 frames", failures)

    ranges: list[dict[str, Any]] = []
    for group_name in ("acts", "shots"):
        group = data.get(group_name)
        if not isinstance(group, list) or not group:
            failures.append(f"timeline.json must contain a nonempty {group_name} array")
            continue
        valid = [item for item in group if isinstance(item, dict)]
        check(len(valid) == len(group), f"every timeline {group_name} entry must be an object", failures)
        if not valid:
            continue
        check(valid[0].get("startFrame") == 0, f"timeline {group_name} must start at frame 0", failures)
        check(valid[-1].get("endFrame") == EXPECTED_FRAMES,
              f"timeline {group_name} must end at source frame {EXPECTED_FRAMES}", failures)
        for index, entry in enumerate(valid):
            start, end = entry.get("startFrame"), entry.get("endFrame")
            check(type(start) is int and type(end) is int and 0 <= start < end <= EXPECTED_FRAMES,
                  f"timeline {group_name} entry {index + 1} is not clamped to source frames [0, {EXPECTED_FRAMES})", failures)
            if index and type(start) is int:
                check(valid[index - 1].get("endFrame") == start,
                      f"timeline {group_name} has a gap or overlap before entry {index + 1}", failures)
        ranges.append({"group": group_name, "count": len(group), "source_frame_domain": [0, EXPECTED_FRAMES]})
    return {"fps": EXPECTED_FPS, "total_frames": EXPECTED_FRAMES, "intervals": ranges,
            "source_frame_clamped": not any("clamped to source frames" in item for item in failures)}


def parse_srt(path: Path) -> str:
    text = path.read_text(encoding="utf-8-sig")
    kept: list[str] = []
    for line in text.splitlines():
        value = line.strip()
        if not value or value.isdigit() or "-->" in value:
            continue
        kept.append(value)
    return "".join(kept)


def verify_captions(failures: list[str], incomplete: list[str], source_text: str) -> dict[str, Any]:
    path = PROJECT_DIR / "audio-timing.json"
    data = read_json(path, "project/audio-timing.json", failures, incomplete)
    if not isinstance(data, dict):
        if data is not None:
            failures.append("audio-timing.json must contain a JSON object")
        return {"status": "INCOMPLETE", "reason": "caption timing unavailable"}

    status = data.get("status")
    captions = data.get("captions")
    if status == "PREVIEW_ONLY" or not isinstance(captions, list) or not captions:
        incomplete.append("audio-timing.json is not ready; caption text comparison and actual caption-size report are pending")
        return {"status": "INCOMPLETE", "audio_timing_status": status, "caption_count": len(captions) if isinstance(captions, list) else None}

    caption_texts: list[str] = []
    caption_sizes: list[dict[str, Any]] = []
    max_lines = 0
    previous_caption_end = -1
    for index, caption in enumerate(captions, start=1):
        if not isinstance(caption, dict) or not isinstance(caption.get("text"), str):
            failures.append(f"audio-timing caption {index} is missing text")
            continue
        text = caption["text"]
        caption_texts.append(text)
        lines = text.splitlines() or [text]
        max_lines = max(max_lines, len(lines))
        start, end = caption.get("startFrame"), caption.get("endFrame")
        check(type(start) is int and type(end) is int and 0 <= start < end <= EXPECTED_FRAMES,
              f"audio-timing caption {index} frame bounds fall outside source frames [0, {EXPECTED_FRAMES})", failures)
        if type(start) is int and type(end) is int:
            check(start >= previous_caption_end, f"audio-timing caption {index} overlaps its predecessor", failures)
            previous_caption_end = end
        line_height = 54
        top = 1384
        box_height = len(lines) * line_height
        caption_sizes.append({
            "index": index,
            "segment_id": caption.get("segmentId"),
            "start_frame": start,
            "end_frame_exclusive": end,
            "line_count": len(lines),
            "line_characters": [len(line) for line in lines],
            "font_size_logical_px": 49,
            "line_height_logical_px": line_height,
            "box_logical_px": {"x": 64, "y": top, "width": 856, "height": box_height},
            "right_edge_logical_px": 920,
            "bottom_edge_logical_px": top + box_height,
        })
        check(len(lines) <= 2, f"audio-timing caption {index} exceeds the two-line limit", failures)
        check(top + box_height <= 0.78 * LOGICAL_HEIGHT,
              f"audio-timing caption {index} extends below the subtitle safe-zone bottom", failures)

    expected_joined = normalized_whitespace(source_text)
    actual_joined = normalized_whitespace("".join(caption_texts))
    check(actual_joined == expected_joined,
          "concatenated audio-timing captions differ from source display text beyond whitespace", failures)

    srt_checks: list[dict[str, Any]] = []
    srt_files = sorted(path for path in DELIVERY_DIR.rglob("*.srt") if path.is_file())
    for srt_path in srt_files:
        try:
            srt_text = parse_srt(srt_path)
        except (OSError, UnicodeError) as exc:
            failures.append(f"cannot read SRT {srt_path.relative_to(DELIVERY_DIR).as_posix()}: {exc}")
            continue
        matches = normalized_whitespace(srt_text) == expected_joined
        check(matches, f"SRT text differs from source display text beyond whitespace: {srt_path.relative_to(DELIVERY_DIR).as_posix()}", failures)
        srt_checks.append({"path": srt_path.relative_to(DELIVERY_DIR).as_posix(), "matches_source_beyond_whitespace": matches})

    return {
        "status": "CHECKED",
        "audio_timing_status": status,
        "caption_count": len(captions),
        "concatenated_text_matches_source_beyond_whitespace": actual_joined == expected_joined,
        "srt_checks": srt_checks,
        "actual_caption_sizes": caption_sizes,
        "max_caption_lines": max_lines,
        "caption_size_basis": "Film.tsx CSS box (49 logical px font, 54 logical px line height, 856 logical px width); this does not independently measure browser glyph wrapping.",
    }


def main() -> int:
    failures: list[str] = []
    incomplete: list[str] = []
    manifest, manifest_report = verify_delivery_manifest(failures, incomplete)
    segments_report = verify_segments(failures, incomplete)
    source_text = "".join(
        str(segment.get("display_subtitle", ""))
        for segment in (read_json(PROJECT_DIR / "segments.json", "project/segments.json", failures, incomplete) or [])
        if isinstance(segment, dict)
    )
    source_report = verify_source_code(failures, incomplete)
    timeline_report = verify_timeline(failures, incomplete)
    caption_report = verify_captions(failures, incomplete, source_text)

    source_status = "FAIL" if failures else "PASS"
    status = "FAIL" if failures else "INCOMPLETE" if incomplete else "PASS"
    report = {
        "schema_version": 1,
        "checker": "EP12 read-only source verifier",
        "status": status,
        "source_status": source_status,
        "delivery_status": "INCOMPLETE" if incomplete else "SOURCE_ONLY",
        "delivery": manifest_report,
        "segments": segments_report,
        "timeline": timeline_report,
        "source_audit": source_report,
        "captions": caption_report,
        "failures": failures,
        "incomplete": incomplete,
        "limitations": [
            "This verifier does not decode or approve the final MP4.",
            "Source checks do not establish perceptual motion, complete-frame integrity, human listening, or device playback.",
            "Caption geometry uses declared CSS box metrics and does not independently measure browser font shaping or glyph wrapping.",
        ],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if failures else 2 if incomplete else 0


if __name__ == "__main__":
    raise SystemExit(main())
