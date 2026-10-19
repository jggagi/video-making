#!/usr/bin/env python3
"""Validate EP04 source, timeline, subtitle, and available PCM invariants.

This checks project inputs only. Missing in-progress audio/media is reported as
INCOMPLETE; it does not imply that the final renders or human review passed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import wave
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DELIVERY_DIR = PROJECT_DIR.parent
REVIEW_DIR = DELIVERY_DIR / "review"
EXPECTED_FRAMES = 7_200
EXPECTED_FPS = 60
EXPECTED_DURATION = 120
SAMPLE_RATE = 48_000
SAMPLES_PER_FRAME = 800
EXPECTED_SAMPLES = 5_760_000
EXPECTED_IDS = [f"S{i:02d}" for i in range(1, 11)]
EXPECTED_OUTPUTS = {
    "bilibili": (3840, 2160),
    "xiaohongshu": (2160, 3840),
}
LEXICON = ("VERIFIER", "GUILLOTINE", "FALSIFIED", "DIVERGING", "AUTOPHAGY")
SILENCE_START_FRAME = 5_820
SILENCE_END_FRAME = 5_850
SILENCE_START_SAMPLE = 4_656_000
SILENCE_END_SAMPLE = 4_680_000
CHINESE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate authored EP04 source and any available shared PCM master."
    )
    parser.add_argument("--no-write", action="store_true", help="Print results without writing review/project-validation.json.")
    return parser.parse_args()


def add_check(
    checks: list[dict[str, Any]],
    failures: list[str],
    name: str,
    passed: bool,
    details: Any = None,
) -> None:
    item: dict[str, Any] = {"name": name, "status": "PASS" if passed else "FAIL"}
    if details is not None:
        item["details"] = details
    checks.append(item)
    if not passed:
        failures.append(name)


def add_incomplete(
    checks: list[dict[str, Any]],
    incomplete: list[str],
    name: str,
    details: Any = None,
) -> None:
    item: dict[str, Any] = {"name": name, "status": "INCOMPLETE"}
    if details is not None:
        item["details"] = details
    checks.append(item)
    incomplete.append(name)


def load_json(path: Path, label: str, failures: list[str]) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        failures.append(f"missing required source file: {label}")
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        failures.append(f"cannot read {label}: {exc}")
    return None


def safe_delivery_path(value: Any, label: str, failures: list[str]) -> Path | None:
    if not isinstance(value, str) or not value:
        failures.append(f"{label} path is missing")
        return None
    candidate = (DELIVERY_DIR / value).resolve()
    try:
        candidate.relative_to(DELIVERY_DIR.resolve())
    except ValueError:
        failures.append(f"{label} path escapes the delivery folder")
        return None
    return candidate


def safe_project_path(value: Any, label: str, failures: list[str]) -> Path | None:
    if not isinstance(value, str) or not value:
        failures.append(f"{label} path is missing")
        return None
    relative = value.removeprefix("project/")
    candidate = (PROJECT_DIR / relative).resolve()
    try:
        candidate.relative_to(PROJECT_DIR.resolve())
    except ValueError:
        failures.append(f"{label} path escapes the project folder")
        return None
    return candidate


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_manifest(checks: list[dict[str, Any]], failures: list[str]) -> dict[str, Any] | None:
    manifest = load_json(DELIVERY_DIR / "delivery.json", "delivery.json", failures)
    if not isinstance(manifest, dict):
        if manifest is not None:
            failures.append("delivery.json must contain an object")
        return None

    add_check(
        checks, failures, "delivery timing is 120 seconds / 60 fps / 7200 frames",
        (manifest.get("duration_seconds"), manifest.get("fps"), manifest.get("total_frames"))
        == (EXPECTED_DURATION, EXPECTED_FPS, EXPECTED_FRAMES),
    )
    add_check(checks, failures, "delivery slug matches folder", manifest.get("slug") == DELIVERY_DIR.name)

    script_info = manifest.get("script")
    if not isinstance(script_info, dict):
        failures.append("delivery.json script record is missing")
    else:
        script_path = safe_delivery_path(script_info.get("path"), "delivery.json script", failures)
        if script_path is not None:
            if not script_path.is_file():
                failures.append(f"source script is missing: {script_info.get('path')}")
            else:
                actual = sha256_file(script_path)
                add_check(checks, failures, "source script SHA-256 matches delivery.json", actual == script_info.get("sha256"), actual)

    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        failures.append("delivery.json outputs must be an object")
    else:
        for key, dimensions in EXPECTED_OUTPUTS.items():
            output = outputs.get(key)
            actual = (output.get("width"), output.get("height")) if isinstance(output, dict) else None
            add_check(
                checks, failures, f"delivery.json outputs.{key} declares {dimensions[0]}x{dimensions[1]}",
                actual == dimensions, {"actual": actual, "expected": dimensions},
            )
    return manifest


def verify_compositions(checks: list[dict[str, Any]], failures: list[str]) -> None:
    path = PROJECT_DIR / "src/Root.tsx"
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        failures.append(f"cannot read project/src/Root.tsx: {exc}")
        return

    attributes = re.compile(r"\b(id|width|height|fps|durationInFrames)\s*=\s*(?:\{\s*([^}]+?)\s*\}|\"([^\"]*)\")")
    found: dict[str, dict[str, Any]] = {}
    for tag in re.findall(r"<Composition\b([^>]*)>", source, flags=re.DOTALL):
        values: dict[str, Any] = {}
        for name, expression, quoted in attributes.findall(tag):
            value: Any = (expression or quoted).strip()
            if name != "id":
                try:
                    value = int(value)
                except ValueError:
                    pass
            values[name] = value
        if isinstance(values.get("id"), str):
            found[values["id"]] = values

    expected = {
        "Landscape4K": {"width": 3840, "height": 2160, "fps": 60, "durationInFrames": EXPECTED_FRAMES},
        "PortraitVertical": {"width": 2160, "height": 3840, "fps": 60, "durationInFrames": EXPECTED_FRAMES},
    }
    for name, wanted in expected.items():
        actual = found.get(name, {})
        passed = all(actual.get(key) == value for key, value in wanted.items())
        add_check(checks, failures, f"Root.tsx {name} composition timing and dimensions", passed,
                  {"expected": wanted, "actual": {key: actual.get(key) for key in wanted}})


def parse_script_table(script: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for line in script.splitlines():
        if not re.match(r"^\|\s*\*\*S\d{2}\*\*\s*\|", line):
            continue
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if len(cells) < 5:
            continue
        sid_match = re.search(r"S\d{2}", cells[0])
        window = re.search(r"(\d+)\s*-\s*(\d+)f", cells[1])
        if sid_match is None or window is None:
            continue

        def clean(value: str) -> str:
            return value.replace("<br>", "\n").replace("`", "").strip()

        sid = sid_match.group(0)
        rows[sid] = {
            "startFrame": int(window.group(1)),
            "endFrame": int(window.group(2)),
            "display_subtitle": clean(cells[2]),
            "tts_phonetic_text": clean(cells[3]),
        }
    return rows


def verify_segments(checks: list[dict[str, Any]], failures: list[str]) -> list[dict[str, Any]] | None:
    data = load_json(PROJECT_DIR / "segments.json", "project/segments.json", failures)
    if not isinstance(data, dict):
        if data is not None:
            failures.append("segments.json must contain an object")
        return None
    segments = data.get("segments")
    if not isinstance(segments, list):
        failures.append("segments.json must contain a segments array")
        return None

    ids = [item.get("id") for item in segments if isinstance(item, dict)]
    add_check(checks, failures, "segments.json contains S01-S10 in order", ids == EXPECTED_IDS, ids)

    sorted_windows: list[tuple[int, int, str]] = []
    bounds_valid = len(segments) == 10
    for index, item in enumerate(segments, start=1):
        if not isinstance(item, dict):
            bounds_valid = False
            continue
        start, end = item.get("startFrame"), item.get("endFrame")
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= EXPECTED_FRAMES:
            bounds_valid = False
        else:
            sorted_windows.append((start, end, str(item.get("id", index))))
    sorted_windows.sort()
    no_overlap = all(left[1] <= right[0] for left, right in zip(sorted_windows, sorted_windows[1:]))
    add_check(checks, failures, "segment frame windows are in range and do not overlap", bounds_valid and no_overlap,
              [{"id": sid, "startFrame": start, "endFrame": end} for start, end, sid in sorted_windows])

    script_path = DELIVERY_DIR / "source/script.md"
    try:
        source_rows = parse_script_table(script_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        failures.append(f"cannot read source/script.md segment table: {exc}")
        return segments
    add_check(checks, failures, "source script contains all ten segment rows", list(source_rows) == EXPECTED_IDS, list(source_rows))

    text_matches = len(segments) == len(EXPECTED_IDS) and len(source_rows) == len(EXPECTED_IDS)
    tts_file_matches = True
    mismatches: list[str] = []
    for item in segments:
        if not isinstance(item, dict):
            text_matches = False
            continue
        sid = item.get("id")
        expected = source_rows.get(sid) if isinstance(sid, str) else None
        if expected is None:
            text_matches = False
            mismatches.append(f"{sid}: no matching source row")
            continue
        if item.get("display_subtitle") != expected["display_subtitle"]:
            text_matches = False
            mismatches.append(f"{sid}: display_subtitle differs from source")
        if item.get("original_script") != expected["display_subtitle"]:
            text_matches = False
            mismatches.append(f"{sid}: original_script differs from source display text")
        if item.get("tts_phonetic_text") != expected["tts_phonetic_text"]:
            text_matches = False
            mismatches.append(f"{sid}: tts_phonetic_text differs from source")
        start, end = item.get("startFrame"), item.get("endFrame")
        if (start, end) != (expected["startFrame"], expected["endFrame"]):
            text_matches = False
            mismatches.append(f"{sid}: frame window differs from source")

        tts_path = PROJECT_DIR / "public/audio/tts-input" / f"{sid}.txt"
        try:
            actual_tts = tts_path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            tts_file_matches = False
            mismatches.append(f"{sid}: TTS input text file is missing or unreadable")
        else:
            if actual_tts != expected["tts_phonetic_text"]:
                tts_file_matches = False
                mismatches.append(f"{sid}: TTS input file differs from source text")
    add_check(checks, failures, "S01-S10 source text and frame windows are preserved", text_matches, mismatches)
    add_check(checks, failures, "S01-S10 TTS input files preserve source text", tts_file_matches)
    return segments


def verify_timeline(checks: list[dict[str, Any]], failures: list[str]) -> None:
    data = load_json(PROJECT_DIR / "timeline.json", "project/timeline.json", failures)
    if not isinstance(data, dict):
        if data is not None:
            failures.append("timeline.json must contain an object")
        return
    shots = data.get("shots")
    if not isinstance(shots, list) or not shots:
        failures.append("timeline.json must contain a non-empty shots array")
        return
    timing_ok = data.get("duration_seconds") == EXPECTED_DURATION and data.get("fps") == EXPECTED_FPS and data.get("total_frames") == EXPECTED_FRAMES
    cursor = 0
    bounds_ok = True
    normalized: list[dict[str, Any]] = []
    for index, shot in enumerate(shots, start=1):
        if not isinstance(shot, dict):
            bounds_ok = False
            continue
        start, end = shot.get("startFrame"), shot.get("endFrame")
        valid = type(start) is int and type(end) is int and start == cursor and start < end <= EXPECTED_FRAMES
        bounds_ok = bounds_ok and valid
        if valid:
            normalized.append({"startFrame": start, "endFrame": end, "title": shot.get("title")})
            cursor = end
        else:
            failures.append(f"timeline shot {index} is out of range, overlaps, or leaves a gap")
    bounds_ok = bounds_ok and cursor == EXPECTED_FRAMES
    add_check(checks, failures, "timeline declares 120 seconds / 60 fps / 7200 frames", timing_ok)
    add_check(checks, failures, "timeline shots cover 0..7200 without gaps or overlap", bounds_ok, normalized)


def verify_klein_source(checks: list[dict[str, Any]], failures: list[str]) -> None:
    path = PROJECT_DIR / "src/Cathedral.ts"
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        failures.append(f"cannot read src/Cathedral.ts: {exc}")
        return
    formula_patterns = (
        r"const\s+radius\s*=\s*2\.45\s*\+\s*cv",
        r"radius\s*\*\s*Math\.cos\(u\)",
        r"radius\s*\*\s*Math\.sin\(u\)",
        r"sv\s*\*\s*Math\.cos\(u\s*\*\s*0\.5\)",
        r"sv\s*\*\s*Math\.sin\(u\s*\*\s*0\.5\)",
    )
    formula_ok = all(re.search(pattern, source) for pattern in formula_patterns)
    lace_ok = bool(
        re.search(r"const\s+LACE_LAYERS\s*=\s*6\s*;", source)
        and re.search(r"layer\s*<\s*LACE_LAYERS", source)
        and re.search(r"const\s+count\s*=\s*8\s*\*\s*2\s*\*\*\s*layer", source)
        and re.search(r"const\s+radiusScale\s*=\s*1\s*/\s*2\s*\*\*", source)
        and re.search(r"motif\.push\((?:transformShellPoint\()?klein4\(u,\s*v\)", source)
    )
    add_check(checks, failures, "Cathedral.ts contains the four-coordinate Klein immersion", formula_ok)
    add_check(checks, failures, "Cathedral.ts grows six deterministic dyadic lace layers on Klein4", lace_ok)


def verify_source_strings(checks: list[dict[str, Any]], failures: list[str]) -> None:
    source_files = sorted(path for path in (PROJECT_DIR / "src").rglob("*") if path.suffix in {".ts", ".tsx"})
    source = "\n".join(path.read_text(encoding="utf-8") for path in source_files)
    deterministic = not re.search(r"Math\.random\s*\(|Date\.now\s*\(", source)
    add_check(checks, failures, "TypeScript sources contain no Math.random or Date.now", deterministic,
              [path.relative_to(PROJECT_DIR).as_posix() for path in source_files])
    missing = [word for word in LEXICON if re.search(re.escape(word), source, flags=re.IGNORECASE) is None]
    add_check(checks, failures, "required technical lexicon spellings occur in source", not missing, {"required": LEXICON, "missing": missing})
    lexicon = json.loads((PROJECT_DIR / "telemetry-lexicon.json").read_text(encoding="utf-8"))
    exact = lexicon["hud"] + ["END OF FORMALIZABLE REALITY", "形式化温室边界"]
    missing_exact = [text for text in exact if text not in source]
    add_check(checks, failures, "exact persistent HUD and ceiling label are present", not missing_exact, {"missing": missing_exact})


def validate_windows(
    items: Any,
    label: str,
    checks: list[dict[str, Any]],
    failures: list[str],
    incomplete: list[str],
    *,
    require_caption_text: bool,
) -> None:
    if not isinstance(items, list) or not items:
        add_incomplete(checks, incomplete, f"{label} are not yet available")
        return
    ok = True
    rows: list[tuple[int, int, int]] = []
    details: list[str] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            ok = False
            details.append(f"{label} entry {index} is not an object")
            continue
        start, end = item.get("startFrame"), item.get("endFrame")
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= EXPECTED_FRAMES:
            ok = False
            details.append(f"{label} entry {index} has invalid frame bounds")
        else:
            rows.append((start, end, index))
        if require_caption_text:
            value = item.get("text")
            if not isinstance(value, str) or not value.strip():
                ok = False
                details.append(f"caption {index} has no text")
            else:
                lines = value.splitlines() or [value]
                if len(lines) > 2:
                    ok = False
                    details.append(f"caption {index} has more than two lines")
                for line_index, line in enumerate(lines, start=1):
                    count = len(CHINESE.findall(line))
                    if count > 14:
                        ok = False
                        details.append(f"caption {index} line {line_index} has {count} Chinese characters")
    rows.sort()
    no_overlap = all(left[1] <= right[0] for left, right in zip(rows, rows[1:]))
    if not no_overlap:
        details.append(f"{label} frame windows overlap")
    add_check(checks, failures, f"{label} frame windows and text layout are valid", ok and no_overlap, details)


def verify_audio_timing(checks: list[dict[str, Any]], failures: list[str], incomplete: list[str]) -> None:
    data = load_json(PROJECT_DIR / "audio-timing.json", "project/audio-timing.json", failures)
    if not isinstance(data, dict):
        if data is not None:
            failures.append("audio-timing.json must contain an object")
        return
    metadata_ok = (
        data.get("durationSeconds"), data.get("fps"), data.get("sampleRate"), data.get("samplesPerChannel")
    ) == (EXPECTED_DURATION, EXPECTED_FPS, SAMPLE_RATE, EXPECTED_SAMPLES)
    add_check(checks, failures, "audio-timing.json declares exact 48-kHz stereo master duration", metadata_ok,
              {key: data.get(key) for key in ("durationSeconds", "fps", "sampleRate", "samplesPerChannel", "status")})
    if data.get("status") != "measured_pcm_with_estimated_phrase_timing":
        add_incomplete(checks, incomplete, "audio-timing.json has not reached measured phrase timing", data.get("status"))
    timed_segments = data.get("segments")
    if isinstance(timed_segments, list) and timed_segments:
        ids = [item.get("id") for item in timed_segments if isinstance(item, dict)]
        add_check(checks, failures, "measured audio timing contains S01-S10 in order", ids == EXPECTED_IDS, ids)
        validate_windows(timed_segments, "measured audio segment", checks, failures, incomplete, require_caption_text=False)
        sample_counts_ok = all(
            isinstance(item, dict)
            and type(item.get("samplesAt48k", item.get("sampleCount"))) is int
            and item.get("samplesAt48k", item.get("sampleCount")) > 0
            for segment in timed_segments
            for item in segment.get("cueParts", [segment])
        )
        add_check(checks, failures, "measured audio segment sample counts are positive", sample_counts_ok)
    else:
        add_incomplete(checks, incomplete, "measured audio segment spans are pending")
    validate_windows(data.get("captions"), "timed caption", checks, failures, incomplete, require_caption_text=True)

    film_path = PROJECT_DIR / "src/Film.tsx"
    try:
        film = film_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        failures.append(f"cannot read src/Film.tsx caption style: {exc}")
        return
    font = re.search(r"fontSize\s*:\s*p\s*\?\s*(\d+)\s*:\s*(\d+)", film)
    portrait_size = int(font.group(1)) if font else None
    effective = portrait_size / 3 if portrait_size is not None else None
    add_check(checks, failures, "portrait subtitle font remains above 13px at 360px preview",
              effective is not None and effective > 13,
              {"logical_font_px": portrait_size, "effective_at_360px": effective})


def verify_sfx_map(checks: list[dict[str, Any]], failures: list[str]) -> None:
    data = load_json(PROJECT_DIR / "sfx_events.json", "project/sfx_events.json", failures)
    if not isinstance(data, dict):
        if data is not None:
            failures.append("sfx_events.json must contain an object")
        return
    timing_ok = (data.get("fps"), data.get("sample_rate"), data.get("samples_per_frame")) == (EXPECTED_FPS, SAMPLE_RATE, SAMPLES_PER_FRAME)
    add_check(checks, failures, "SFX map uses 60 fps and 800 samples per frame", timing_ok)
    events = data.get("events")
    silence = next((item for item in events if isinstance(item, dict) and item.get("id") == "silence"), None) if isinstance(events, list) else None
    impact = next((item for item in events if isinstance(item, dict) and item.get("id") == "truth_drop"), None) if isinstance(events, list) else None
    silence_ok = isinstance(silence, dict) and (
        silence.get("frame"), silence.get("sample"), silence.get("durationSeconds")
    ) == (SILENCE_START_FRAME, SILENCE_START_SAMPLE, 0.5)
    impact_ok = isinstance(impact, dict) and (impact.get("frame"), impact.get("sample")) == (SILENCE_END_FRAME, SILENCE_END_SAMPLE)
    add_check(checks, failures, "SFX silence covers frames 5820-5849 / samples [4656000,4680000)", silence_ok)
    add_check(checks, failures, "truth drop starts at frame 5850 / sample 4680000", impact_ok)


def verify_pcm_master(
    manifest: dict[str, Any] | None,
    checks: list[dict[str, Any]],
    failures: list[str],
    incomplete: list[str],
) -> dict[str, Any] | None:
    if manifest is None:
        add_incomplete(checks, incomplete, "PCM master check pending because delivery manifest is unavailable")
        return None
    audio = manifest.get("audio")
    value = audio.get("master") if isinstance(audio, dict) else None
    path = safe_delivery_path(value, "delivery.json audio.master", failures)
    if path is None:
        return None
    if not path.is_file():
        add_incomplete(checks, incomplete, "shared PCM master is not available yet", value)
        return None
    try:
        with wave.open(str(path), "rb") as stream:
            actual = {
                "sample_rate": stream.getframerate(),
                "channels": stream.getnchannels(),
                "samples_per_channel": stream.getnframes(),
                "sample_width_bytes": stream.getsampwidth(),
                "compression": stream.getcomptype(),
            }
            shape_ok = (stream.getframerate(), stream.getnchannels(), stream.getnframes()) == (SAMPLE_RATE, 2, EXPECTED_SAMPLES)
            if shape_ok:
                stream.setpos(SILENCE_START_SAMPLE)
                silence = stream.readframes(SILENCE_END_SAMPLE - SILENCE_START_SAMPLE)
                silent = len(silence) == (SILENCE_END_SAMPLE - SILENCE_START_SAMPLE) * 2 * stream.getsampwidth() and not any(silence)
            else:
                silent = False
    except (OSError, wave.Error) as exc:
        failures.append(f"cannot inspect shared PCM master: {exc}")
        return None
    digest = sha256_file(path)
    add_check(checks, failures, "shared PCM is 48-kHz stereo with 5,760,000 samples/channel", shape_ok, actual)
    add_check(checks, failures, "PCM master is exactly zero during [4656000,4680000)", silent)
    return {**actual, "silent_sample_range": [SILENCE_START_SAMPLE, SILENCE_END_SAMPLE], "silence_is_zero": silent, "sha256": digest}


def main() -> int:
    args = parse_args()
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    incomplete: list[str] = []

    manifest = verify_manifest(checks, failures)
    verify_compositions(checks, failures)
    segments = verify_segments(checks, failures)
    verify_timeline(checks, failures)
    verify_klein_source(checks, failures)
    verify_source_strings(checks, failures)
    verify_audio_timing(checks, failures, incomplete)
    verify_sfx_map(checks, failures)
    pcm = verify_pcm_master(manifest, checks, failures, incomplete)

    status = "FAIL" if failures else "INCOMPLETE" if incomplete else "PASS"
    report = {
        "schema_version": 1,
        "status": status,
        "checks": checks,
        "failures": failures,
        "incomplete": incomplete,
        "segment_count": len(segments) if isinstance(segments, list) else None,
        "pcm_master": pcm,
        "acceptance_status": "NOT_EVALUATED",
        "scope": "authored source, timeline, subtitle, SFX timing and available PCM; final media decode and human acceptance are separate",
    }
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(encoded, end="")
    if not args.no_write:
        REVIEW_DIR.mkdir(parents=True, exist_ok=True)
        (REVIEW_DIR / "project-validation.json").write_text(encoded, encoding="utf-8")
    return 1 if failures else 2 if incomplete else 0


if __name__ == "__main__":
    raise SystemExit(main())
