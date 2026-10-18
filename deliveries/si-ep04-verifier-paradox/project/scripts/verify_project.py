#!/usr/bin/env python3
"""Check EP04 source invariants and report delivery readiness separately.

This is a source verifier. It does not decode or approve the final MP4s; use
collect_qa.py for encoded-media evidence and keep human review separate.
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
MANIFEST_PATH = DELIVERY_DIR / "delivery.json"
EXPECTED_SEGMENTS = (
    ("S01", 120, 600),
    ("S02", 660, 1200),
    ("S03", 1260, 1740),
    ("S04", 1860, 2580),
    ("S05", 2700, 3480),
    ("S06", 3660, 4440),
    ("S07", 4500, 5340),
    ("S08", 5460, 6240),
    ("S09", 6360, 6900),
    ("S10", 6960, 7200),
)
EXPECTED_SFX_FRAMES = (120, 960, 1260, 1920, 2880, 3900, 4680, 5760, 6500, 7020)
EXPECTED_SILENCE = (5740, 5760)
EXPECTED_SAMPLE_RATE = 48_000
EXPECTED_SAMPLES = 5_760_000
EXPECTED_FRAMES = 7_200
EXPECTED_HUD_LITERALS = (
    "EXTERNAL VERIFIER: LEAN_4 & COMPILER [100.0% DETERMINISTIC]",
    "EXTERNAL VERIFIER: OFFLINE (OPEN-WORLD FOG) // PROXY REWARD ONLY",
    "GROUND-TRUTH ANCHOR: PHYSICAL EXPERIMENT LOCKED",
    "SELF-REWARD SCORE: +99.999% (MAXIMIZED)",
    "REALITY ALIGNMENT: ",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify EP04 project source invariants without claiming media acceptance."
    )
    parser.add_argument(
        "--no-write", action="store_true",
        help="Print the report without writing review/project-check.json.",
    )
    return parser.parse_args()


def load_json(path: Path, label: str, failures: list[str], incomplete: list[str]) -> Any | None:
    if not path.is_file():
        incomplete.append(f"missing {label}: {path.relative_to(DELIVERY_DIR).as_posix()}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        failures.append(f"cannot read {label}: {exc}")
        return None


def check(ok: bool, message: str, failures: list[str]) -> None:
    if not ok:
        failures.append(message)


def chinese_count(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def normalized_display(text: str) -> str:
    return re.sub(r"\s+", "", text)


def script_subtitles(failures: list[str], incomplete: list[str]) -> dict[str, str]:
    path = DELIVERY_DIR / "source/script.md"
    if not path.is_file():
        incomplete.append("source script missing; segment transcript cross-check pending")
        return {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        failures.append(f"cannot read source script for transcript cross-check: {exc}")
        return {}
    expected: dict[str, str] = {}
    for line in lines:
        match = re.match(r"^\|\s*\*\*(S\d{2})\*\*\s*\|", line)
        if match is None:
            continue
        cells = line.split("|")
        if len(cells) < 5:
            failures.append(f"source script row {match.group(1)} is malformed")
            continue
        display = re.sub(r"<br\s*/?>", "\n", cells[3], flags=re.IGNORECASE).replace("`", "").strip()
        expected[match.group(1)] = display
    expected_ids = [item[0] for item in EXPECTED_SEGMENTS]
    check(list(expected) == expected_ids, "source script must contain the ten ordered subtitle rows", failures)
    return expected


def verify_manifest(report: dict[str, Any], failures: list[str], incomplete: list[str]) -> dict[str, Any] | None:
    manifest = load_json(MANIFEST_PATH, "delivery manifest", failures, incomplete)
    if not isinstance(manifest, dict):
        if manifest is not None:
            failures.append("delivery.json must contain a JSON object")
        return None

    expected = (120, 60, EXPECTED_FRAMES)
    actual = (manifest.get("duration_seconds"), manifest.get("fps"), manifest.get("total_frames"))
    check(actual == expected, f"delivery timing must be {expected}, got {actual}", failures)

    script = manifest.get("script")
    if not isinstance(script, dict) or not isinstance(script.get("path"), str):
        failures.append("delivery.json script.path is missing")
    else:
        script_path = (DELIVERY_DIR / script["path"]).resolve()
        try:
            script_path.relative_to(DELIVERY_DIR.resolve())
        except ValueError:
            failures.append("delivery.json script.path escapes the delivery folder")
        else:
            if not script_path.is_file():
                incomplete.append("missing source script: " + script["path"])
            elif isinstance(script.get("sha256"), str):
                digest = hashlib.sha256(script_path.read_bytes()).hexdigest()
                check(digest == script["sha256"], "source script SHA-256 differs from delivery.json", failures)
            else:
                failures.append("delivery.json script.sha256 is missing")

    report["delivery_manifest"] = {
        "duration_seconds": manifest.get("duration_seconds"),
        "fps": manifest.get("fps"),
        "total_frames": manifest.get("total_frames"),
    }
    return manifest


def verify_segments(failures: list[str], incomplete: list[str]) -> None:
    path = PROJECT_DIR / "segments.json"
    data = load_json(path, "segments.json", failures, incomplete)
    if data is None:
        return
    screenplay = script_subtitles(failures, incomplete)
    if not isinstance(data, dict) or not isinstance(data.get("segments"), list):
        failures.append("segments.json must contain a segments array")
        return
    actual_ids = [item.get("id") for item in data["segments"] if isinstance(item, dict)]
    expected_ids = [segment[0] for segment in EXPECTED_SEGMENTS]
    check(actual_ids == expected_ids, "segments must contain S01-S10 in order", failures)

    for index, expected in enumerate(EXPECTED_SEGMENTS):
        if index >= len(data["segments"]):
            break
        segment = data["segments"][index]
        if not isinstance(segment, dict):
            failures.append(f"segment {expected[0]} must be an object")
            continue
        sid, start, end = expected
        check(segment.get("id") == sid, f"segment {index + 1} id must be {sid}", failures)
        check(
            (segment.get("startFrame"), segment.get("endFrame")) == (start, end),
            f"{sid} frame window must be [{start}, {end})",
            failures,
        )
        original = segment.get("original_script")
        display = segment.get("display_subtitle")
        chunks = segment.get("chunks")
        check(isinstance(original, str), f"{sid} original_script must be text", failures)
        check(isinstance(display, str), f"{sid} display_subtitle must be text", failures)
        if isinstance(original, str) and isinstance(display, str):
            check(
                normalized_display(original) == normalized_display(display),
                f"{sid} display subtitle does not preserve the original transcript",
                failures,
            )
            if sid in screenplay:
                expected_text = normalized_display(screenplay[sid])
                check(normalized_display(original) == expected_text,
                      f"{sid} transcript differs from source/script.md", failures)
                check(normalized_display(display) == expected_text,
                      f"{sid} display subtitle differs from source/script.md", failures)
        check(isinstance(chunks, list) and all(isinstance(chunk, str) for chunk in chunks),
              f"{sid} chunks must be an array of strings", failures)
        if isinstance(chunks, list) and all(isinstance(chunk, str) for chunk in chunks):
            check(
                normalized_display("".join(chunks)) == normalized_display(display or ""),
                f"{sid} chunks do not preserve the display subtitle",
                failures,
            )
            for chunk_no, chunk in enumerate(chunks, start=1):
                for line_no, line in enumerate(chunk.splitlines(), start=1):
                    check(
                        chinese_count(line) <= 14,
                        f"{sid} chunk {chunk_no} line {line_no} exceeds 14 Chinese characters",
                        failures,
                    )
        check(isinstance(segment.get("tts_phonetic_text"), str),
              f"{sid} tts_phonetic_text must be text", failures)


def verify_sfx(failures: list[str], incomplete: list[str]) -> None:
    data = load_json(PROJECT_DIR / "sfx_events.json", "sfx_events.json", failures, incomplete)
    if data is None:
        return
    events = data.get("events") if isinstance(data, dict) else None
    if not isinstance(events, list):
        failures.append("sfx_events.json must contain an events array")
        return
    frames = [event.get("frame") for event in events if isinstance(event, dict)]
    check(frames == list(EXPECTED_SFX_FRAMES), "SFX anchors must match the ten specified frames in order", failures)
    check(data.get("fps") == 60, "SFX event map fps must be 60", failures)
    check(data.get("sampleRate") == EXPECTED_SAMPLE_RATE, "SFX event map sampleRate must be 48000", failures)
    check(data.get("samplesPerFrame") == 800, "SFX event map samplesPerFrame must be 800", failures)
    for event in events:
        if not isinstance(event, dict):
            failures.append("each SFX event must be an object")
            continue
        frame = event.get("frame")
        if type(frame) is int:
            sample = event.get("sampleIndex", event.get("sample"))
            check(sample == frame * 800, f"SFX {event.get('id', '<unknown>')} sample index must equal frame × 800", failures)
    silence = data.get("absoluteSilence")
    if isinstance(silence, dict):
        check(
            (silence.get("startFrame"), silence.get("endFrame")) == EXPECTED_SILENCE,
            "SFX absolute silence must cover frames [5740, 5760)",
            failures,
        )
    else:
        failures.append("sfx_events.json absoluteSilence window is missing")


def verify_source_code(failures: list[str], incomplete: list[str]) -> None:
    src_dir = PROJECT_DIR / "src"
    source_files = sorted(
        path for path in src_dir.rglob("*")
        if path.is_file() and path.suffix in {".ts", ".tsx", ".js", ".jsx"}
    ) if src_dir.is_dir() else []
    if not source_files:
        incomplete.append("source code not present under project/src")
    for path in source_files:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            failures.append(f"cannot read source file {path.name}: {exc}")
            continue
        check(
            re.search(r"\bMath\s*\.\s*random\s*\(|\bDate\s*\.\s*now\s*\(", source) is None,
            f"nondeterministic Math.random/Date.now usage in {path.relative_to(PROJECT_DIR).as_posix()}",
            failures,
        )

    root_path = src_dir / "Root.tsx"
    film_path = src_dir / "Film.tsx"
    if not root_path.is_file():
        incomplete.append("missing project/src/Root.tsx; native composition check pending")
    else:
        root = root_path.read_text(encoding="utf-8")
        compositions: dict[str, dict[str, int]] = {}
        for tag in re.findall(r"<Composition\b[^>]*>", root, flags=re.DOTALL):
            attrs = dict(re.findall(r"\b(id|width|height)\s*=\s*\{?['\"]?([\w.-]+)['\"]?\}?", tag))
            name = attrs.get("id")
            if name:
                numeric: dict[str, int] = {}
                for key in ("width", "height"):
                    if key in attrs and attrs[key].isdigit():
                        numeric[key] = int(attrs[key])
                compositions[name] = numeric
        check(
            compositions.get("Landscape4K") == {"width": 3840, "height": 2160},
            "Root.tsx Landscape4K composition must be 3840x2160",
            failures,
        )
        check(
            compositions.get("PortraitVertical") == {"width": 2160, "height": 3840},
            "Root.tsx PortraitVertical composition must be 2160x3840",
            failures,
        )

    lexicon_path = PROJECT_DIR / "telemetry-lexicon.json"
    if film_path.is_file():
        film = film_path.read_text(encoding="utf-8")
        hud_match = re.search(r"export\s+const\s+HUD\s*=\s*\{([\s\S]*?)\};", film)
        if hud_match is None:
            failures.append("Film.tsx must define a static HUD object")
        else:
            for literal in EXPECTED_HUD_LITERALS:
                check(literal in hud_match.group(1), f"Film.tsx HUD object is missing exact literal: {literal}", failures)
        lexicon = load_json(lexicon_path, "telemetry-lexicon.json", failures, incomplete)
        if isinstance(lexicon, dict):
            for field in ("persistent", "events"):
                values = lexicon.get(field, [])
                if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
                    failures.append(f"telemetry-lexicon.json {field} must be an array of strings")
                    continue
                for text in values:
                    check(text in film, f"Film.tsx does not statically contain HUD string: {text}", failures)
            for field in ("required", "technical_terms"):
                values = lexicon.get(field, [])
                if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
                    failures.append(f"telemetry-lexicon.json {field} must be an array of strings")
                    continue
                source_folded = film.casefold()
                for term in values:
                    check(term.casefold() in source_folded,
                          f"Film.tsx does not statically contain required HUD term: {term}", failures)
    else:
        incomplete.append("missing project/src/Film.tsx; HUD lexicon source check pending")


def verify_timeline(failures: list[str], incomplete: list[str]) -> None:
    path = PROJECT_DIR / "timeline.json"
    data = load_json(path, "timeline.json", failures, incomplete)
    if data is None:
        return
    shots = data.get("shots") if isinstance(data, dict) else None
    if not isinstance(shots, list) or not shots:
        failures.append("timeline.json must contain a nonempty shots array")
        return
    check(data.get("fps") == 60 and data.get("total_frames") == EXPECTED_FRAMES,
          "timeline timing must be 60 fps and 7200 frames", failures)
    valid_shots = [shot for shot in shots if isinstance(shot, dict)]
    check(len(valid_shots) == len(shots), "every timeline shot must be an object", failures)
    if not valid_shots:
        return
    check(valid_shots[0].get("startFrame") == 0, "timeline must start at frame 0", failures)
    check(valid_shots[-1].get("endFrame") == EXPECTED_FRAMES, "timeline must end at frame 7200", failures)
    for first, second in zip(valid_shots, valid_shots[1:]):
        check(first.get("endFrame") == second.get("startFrame"), "timeline has a gap or overlap", failures)
    for shot in valid_shots:
        start, end = shot.get("startFrame"), shot.get("endFrame")
        check(type(start) is int and type(end) is int and 0 <= start < end <= EXPECTED_FRAMES,
              "timeline shot frame bounds are invalid", failures)


def verify_audio_timing(failures: list[str], incomplete: list[str]) -> str | None:
    timing_status: str | None = None
    timing_path = PROJECT_DIR / "audio-timing.json"
    if timing_path.exists():
        data = load_json(timing_path, "audio-timing.json", failures, incomplete)
        if isinstance(data, dict):
            timing_status = data.get("status") if isinstance(data.get("status"), str) else None
            if "captions" not in data:
                failures.append("audio-timing.json captions are missing")
        if isinstance(data, dict) and "captions" in data:
            captions = data["captions"]
            if not isinstance(captions, list):
                failures.append("audio-timing.json captions must be an array")
            else:
                previous_end = -1
                for index, caption in enumerate(captions, start=1):
                    if not isinstance(caption, dict):
                        failures.append(f"caption {index} must be an object")
                        continue
                    start, end, text = caption.get("startFrame"), caption.get("endFrame"), caption.get("text")
                    check(type(start) is int and type(end) is int and 0 <= start < end <= EXPECTED_FRAMES,
                          f"caption {index} frame bounds are invalid", failures)
                    if type(start) is int and type(end) is int:
                        check(start >= previous_end, f"caption {index} overlaps the preceding caption", failures)
                        previous_end = end
                    if isinstance(text, str):
                        lines = text.splitlines() or [text]
                        check(len(lines) <= 2, f"caption {index} has more than two lines", failures)
                        for line_no, line in enumerate(lines, start=1):
                            check(chinese_count(line) <= 14,
                                  f"caption {index} line {line_no} exceeds 14 Chinese characters", failures)
                    else:
                        failures.append(f"caption {index} text is missing")

    master_path = PROJECT_DIR / "public/audio/master.wav"
    if not master_path.is_file():
        incomplete.append("missing shared PCM master; sample-count check pending")
        return timing_status
    try:
        with wave.open(str(master_path), "rb") as master:
            actual = (master.getframerate(), master.getnchannels(), master.getnframes())
            check(actual == (EXPECTED_SAMPLE_RATE, 2, EXPECTED_SAMPLES),
                  f"master WAV must be 48kHz stereo with {EXPECTED_SAMPLES} samples/channel, got {actual}", failures)
            if actual == (EXPECTED_SAMPLE_RATE, 2, EXPECTED_SAMPLES):
                master.setpos(EXPECTED_SILENCE[0] * 800)
                silent_bytes = master.readframes((EXPECTED_SILENCE[1] - EXPECTED_SILENCE[0]) * 800)
                check(not any(silent_bytes), "master WAV must be exactly silent from frame 5740 through 5759", failures)
    except (OSError, wave.Error) as exc:
        failures.append(f"cannot inspect shared PCM master: {exc}")
    return timing_status


def verify_delivery_files(manifest: dict[str, Any] | None, incomplete: list[str]) -> dict[str, Any]:
    files: dict[str, Any] = {}
    output_map = {"bilibili": "landscape", "xiaohongshu": "portrait"}
    outputs = manifest.get("outputs") if isinstance(manifest, dict) else None
    for key, label in output_map.items():
        output = outputs.get(key) if isinstance(outputs, dict) else None
        relative = output.get("path") if isinstance(output, dict) else None
        if not isinstance(relative, str) or not relative:
            files[label] = {"present": False, "path": relative}
            incomplete.append(f"delivery.json outputs.{key}.path missing; final {label} media unavailable")
            continue
        path = (DELIVERY_DIR / relative).resolve()
        try:
            path.relative_to(DELIVERY_DIR.resolve())
        except ValueError:
            files[label] = {"present": False, "path": relative}
            incomplete.append(f"delivery.json outputs.{key}.path escapes the delivery folder")
            continue
        present = path.is_file()
        files[label] = {"present": present, "path": relative}
        if not present:
            incomplete.append(f"missing final {label} MP4: {relative}")
    return files


def main() -> int:
    args = parse_args()
    failures: list[str] = []
    incomplete: list[str] = []
    report: dict[str, Any] = {"schema_version": 1, "checker": "EP04 source verifier"}
    manifest = verify_manifest(report, failures, incomplete)
    verify_segments(failures, incomplete)
    verify_sfx(failures, incomplete)
    verify_source_code(failures, incomplete)
    verify_timeline(failures, incomplete)
    audio_timing_status = verify_audio_timing(failures, incomplete)
    outputs = verify_delivery_files(manifest, incomplete)

    source_incomplete = [
        message for message in incomplete
        if not message.startswith(("missing final ", "delivery.json outputs.", "missing shared PCM master"))
    ]
    source_status = "FAIL" if failures else "INCOMPLETE" if source_incomplete else "PASS"
    delivery_ready = all(item.get("present") for item in outputs.values()) and (PROJECT_DIR / "public/audio/master.wav").is_file()
    delivery_status = "MEDIA_PRESENT_UNVALIDATED" if delivery_ready else "INCOMPLETE"
    overall_status = "FAIL" if failures else "INCOMPLETE" if incomplete else "PASS"
    report.update({
        "status": overall_status,
        "source_status": source_status,
        "delivery_status": delivery_status,
        "audio_timing_status": audio_timing_status,
        "output_files": outputs,
        "failures": failures,
        "incomplete": incomplete,
        "limitations": [
            "Encoded video and audio streams are not decoded by this source verifier.",
            "MEDIA_PRESENT_UNVALIDATED is not delivery acceptance; collect encoded QA and complete human review separately.",
            "Heuristic motion evidence cannot prove meaningful continuous motion.",
        ],
    })

    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(rendered, end="")
    if not args.no_write:
        review_dir = DELIVERY_DIR / "review"
        review_dir.mkdir(parents=True, exist_ok=True)
        (review_dir / "project-check.json").write_text(rendered, encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
