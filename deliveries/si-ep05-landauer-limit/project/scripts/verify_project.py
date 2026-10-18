#!/usr/bin/env python3
"""Verify EP05 source invariants and report media readiness separately."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import wave
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DELIVERY_DIR = PROJECT_DIR.parent
MANIFEST_PATH = DELIVERY_DIR / "delivery.json"
EXPECTED_FRAMES = 7200
EXPECTED_FPS = 60
EXPECTED_DURATION = 120
EXPECTED_SAMPLE_RATE = 48_000
EXPECTED_SAMPLES_PER_CHANNEL = 5_760_000
EXPECTED_SEGMENTS = (
    ("S01", 120, 600),
    ("S02", 660, 1260),
    ("S03", 1320, 1800),
    ("S04", 1860, 2580),
    ("S05", 2700, 3480),
    ("S06", 3660, 4440),
    ("S07", 4500, 5340),
    ("S08", 5460, 6240),
    ("S09", 6360, 6900),
    ("S10", 6960, 7200),
)
EXPECTED_OUTPUTS = {
    "bilibili": (3840, 2160),
    "xiaohongshu": (2160, 3840),
}
FORMULA_EXPORTS = (
    "landauer", "planck", "wien", "radiated", "koomey", "potential", "murrayChild",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify EP05 source and numerical invariants without decoding final media."
    )
    parser.add_argument(
        "--no-write", action="store_true",
        help="Print the report without writing review/project-check.json.",
    )
    return parser.parse_args()


def add_incomplete(items: list[str], message: str) -> None:
    if message not in items:
        items.append(message)


def check(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def load_json(path: Path, label: str, failures: list[str], incomplete: list[str]) -> Any | None:
    if not path.is_file():
        add_incomplete(incomplete, f"missing {label}: {relative(path)}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        failures.append(f"cannot read {label}: {exc}")
        return None


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(DELIVERY_DIR.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_delivery_path(value: Any, label: str, failures: list[str]) -> Path | None:
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


def normalized(text: str) -> str:
    return re.sub(r"\s+", "", text)


def chinese_count(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def script_display_rows(failures: list[str], incomplete: list[str]) -> dict[str, str]:
    path = DELIVERY_DIR / "source/script.md"
    if not path.is_file():
        add_incomplete(incomplete, "source script missing; segment transcript cross-check pending")
        return {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        failures.append(f"cannot read source script: {exc}")
        return {}

    rows: dict[str, str] = {}
    for line in lines:
        match = re.match(r"^\|\s*\*\*(S\d{2})\*\*\s*\|", line)
        if match is None:
            continue
        cells = line.split("|")
        if len(cells) < 6:
            failures.append(f"source script row {match.group(1)} is malformed")
            continue
        display = re.sub(r"<br\s*/?>", "\n", cells[3], flags=re.IGNORECASE)
        display = display.replace("`", "").replace("**", "").strip()
        rows[match.group(1)] = display
    expected_ids = [item[0] for item in EXPECTED_SEGMENTS]
    check(list(rows) == expected_ids, "source script must contain ten ordered display-subtitle rows", failures)
    return rows


def verify_manifest(report: dict[str, Any], failures: list[str], incomplete: list[str]) -> dict[str, Any] | None:
    manifest = load_json(MANIFEST_PATH, "delivery manifest", failures, incomplete)
    if not isinstance(manifest, dict):
        if manifest is not None:
            failures.append("delivery.json must contain a JSON object")
        return None

    actual_timing = (manifest.get("duration_seconds"), manifest.get("fps"), manifest.get("total_frames"))
    expected_timing = (EXPECTED_DURATION, EXPECTED_FPS, EXPECTED_FRAMES)
    check(actual_timing == expected_timing,
          f"delivery timing must be {expected_timing}, got {actual_timing}", failures)

    script = manifest.get("script")
    if not isinstance(script, dict):
        failures.append("delivery.json script metadata is missing")
    else:
        script_path = resolve_delivery_path(script.get("path"), "delivery.json script", failures)
        if script_path is not None:
            if not script_path.is_file():
                add_incomplete(incomplete, f"missing source script: {script.get('path')}")
            elif not isinstance(script.get("sha256"), str):
                failures.append("delivery.json script.sha256 is missing")
            else:
                digest = hashlib.sha256(script_path.read_bytes()).hexdigest()
                check(digest == script["sha256"], "source script SHA-256 differs from delivery.json", failures)
                report["source_script"] = {"path": script["path"], "sha256": digest, "hash_matches": digest == script["sha256"]}

    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        failures.append("delivery.json outputs must be an object")
        outputs = {}
    file_state: dict[str, Any] = {}
    for key, dimensions in EXPECTED_OUTPUTS.items():
        output = outputs.get(key)
        if not isinstance(output, dict):
            add_incomplete(incomplete, f"delivery.json outputs.{key} is missing")
            file_state[key] = {"present": False}
            continue
        check((output.get("width"), output.get("height")) == dimensions,
              f"delivery.json outputs.{key} must declare {dimensions[0]}x{dimensions[1]}", failures)
        media_path = resolve_delivery_path(output.get("path"), f"delivery.json outputs.{key}", failures)
        present = media_path.is_file() if media_path is not None else False
        if media_path is not None and not present:
            add_incomplete(incomplete, f"missing final {key} media: {relative(media_path)}")
        file_state[key] = {
            "present": present,
            "path": output.get("path"),
            "expected_dimensions": {"width": dimensions[0], "height": dimensions[1]},
            "size_bytes": media_path.stat().st_size if present and media_path is not None else None,
        }
    report["output_files"] = file_state
    return manifest


def verify_segments(failures: list[str], incomplete: list[str]) -> None:
    data = load_json(PROJECT_DIR / "segments.json", "segments.json", failures, incomplete)
    if data is None:
        return
    screenplay = script_display_rows(failures, incomplete)
    segments = data.get("segments") if isinstance(data, dict) else None
    if not isinstance(segments, list):
        failures.append("segments.json must contain a segments array")
        return
    ids = [item.get("id") for item in segments if isinstance(item, dict)]
    expected_ids = [item[0] for item in EXPECTED_SEGMENTS]
    check(ids == expected_ids, "segments must be the ten ordered EP05 segment IDs", failures)
    check(data.get("fps") == EXPECTED_FPS, "segments.json fps must be 60", failures)
    check(data.get("duration_seconds") == EXPECTED_DURATION, "segments.json duration_seconds must be 120", failures)

    for index, expected in enumerate(EXPECTED_SEGMENTS):
        if index >= len(segments) or not isinstance(segments[index], dict):
            continue
        sid, start, end = expected
        segment = segments[index]
        check(segment.get("id") == sid, f"segment {index + 1} id must be {sid}", failures)
        check((segment.get("startFrame"), segment.get("endFrame")) == (start, end),
              f"{sid} frame window must be [{start}, {end})", failures)
        tracks: dict[str, str] = {}
        for field in ("original_script", "display_subtitle", "tts_phonetic_text"):
            value = segment.get(field)
            check(isinstance(value, str) and bool(value.strip()), f"{sid} {field} must be nonempty text", failures)
            if isinstance(value, str):
                tracks[field] = value
        display = tracks.get("display_subtitle")
        original = tracks.get("original_script")
        if original is not None and sid in screenplay:
            check(normalized(original) == normalized(screenplay[sid]),
                  f"{sid} original script differs from source/script.md", failures)
        chunks = segment.get("chunks")
        if chunks is not None:
            check(isinstance(chunks, list) and all(isinstance(chunk, str) for chunk in chunks),
                  f"{sid} chunks must be an array of strings", failures)
            if isinstance(chunks, list) and all(isinstance(chunk, str) for chunk in chunks) and display is not None:
                display_parts = [segment.get("display_only_prefix", ""), "".join(chunks), segment.get("display_only_suffix", "")]
                check(all(isinstance(part, str) for part in display_parts)
                      and normalized("".join(display_parts)) == normalized(display),
                      f"{sid} chunks plus display-only text do not preserve the full display subtitle", failures)
                for chunk_no, chunk in enumerate(chunks, start=1):
                    lines = chunk.splitlines() or [chunk]
                    check(len(lines) <= 2, f"{sid} chunk {chunk_no} exceeds two lines", failures)
                    for line_no, line in enumerate(lines, start=1):
                        check(chinese_count(line) <= 14,
                              f"{sid} chunk {chunk_no} line {line_no} exceeds 14 Chinese characters", failures)


def verify_timeline(failures: list[str], incomplete: list[str]) -> None:
    data = load_json(PROJECT_DIR / "timeline.json", "timeline.json", failures, incomplete)
    if data is None:
        return
    shots = data.get("shots") if isinstance(data, dict) else None
    if not isinstance(shots, list) or not shots:
        failures.append("timeline.json must contain a nonempty shots array")
        return
    check((data.get("fps"), data.get("duration_seconds"), data.get("total_frames", data.get("totalFrames"))) ==
          (EXPECTED_FPS, EXPECTED_DURATION, EXPECTED_FRAMES),
          "timeline.json must specify 120 seconds, 60 fps, and 7200 frames", failures)
    if not all(isinstance(shot, dict) for shot in shots):
        failures.append("every timeline shot must be an object")
        return
    check(shots[0].get("startFrame") == 0, "timeline must start at frame 0", failures)
    check(shots[-1].get("endFrame") == EXPECTED_FRAMES, "timeline must end at frame 7200", failures)
    previous_end: int | None = None
    for index, shot in enumerate(shots, start=1):
        start, end = shot.get("startFrame"), shot.get("endFrame")
        valid = type(start) is int and type(end) is int and 0 <= start < end <= EXPECTED_FRAMES
        check(valid, f"timeline shot {index} frame bounds are invalid", failures)
        if valid and previous_end is not None:
            check(start == previous_end, f"timeline gap or overlap before shot {index}", failures)
        if valid:
            previous_end = end


def verify_layout_contract(failures: list[str], incomplete: list[str]) -> dict[str, Any] | None:
    contract = load_json(PROJECT_DIR / "layout-contract.json", "layout-contract.json", failures, incomplete)
    if not isinstance(contract, dict):
        return None
    canvases = contract.get("logical_canvas")
    check(isinstance(canvases, dict) and canvases.get("landscape") == [1920, 1080]
          and canvases.get("portrait") == [1080, 1920],
          "layout-contract logical canvases must be 1920x1080 and 1080x1920", failures)

    portrait = contract.get("portrait")
    safe = portrait.get("safe") if isinstance(portrait, dict) else None
    check(isinstance(safe, dict), "layout-contract portrait.safe must be an object", failures)
    if isinstance(safe, dict):
        check(math.isclose(float_or_nan(safe.get("top")), 153.6, abs_tol=0.01),
              "portrait safe top must be 153.6 logical px", failures)
        check(math.isclose(float_or_nan(safe.get("right")), 928.8, abs_tol=0.01),
              "portrait safe right must be 928.8 logical px", failures)
        check(math.isclose(float_or_nan(safe.get("bottom")), 1497.6, abs_tol=0.01),
              "portrait safe bottom must be 1497.6 logical px", failures)

    portrait_dimensions = (1080, 1920)
    safe_bottom = safe.get("bottom") if isinstance(safe, dict) else None
    safe_right = safe.get("right") if isinstance(safe, dict) else None
    safe_top = safe.get("top") if isinstance(safe, dict) else None
    for section in ("hud", "plot", "subtitles"):
        box = portrait.get(section) if isinstance(portrait, dict) else None
        if not isinstance(box, dict):
            failures.append(f"layout-contract portrait.{section} box is missing")
            continue
        valid = all(type(box.get(key)) in (int, float) for key in ("x", "y", "w", "h"))
        check(valid, f"portrait.{section} must declare numeric x/y/w/h", failures)
        if not valid:
            continue
        x, y, w, h = (float(box[key]) for key in ("x", "y", "w", "h"))
        check(x >= 0 and y >= 0 and w > 0 and h > 0 and x + w <= portrait_dimensions[0]
              and y + h <= portrait_dimensions[1], f"portrait.{section} lies outside its logical canvas", failures)
        if section != "subtitles" and isinstance(safe_top, (int, float)) and isinstance(safe_right, (int, float)) and isinstance(safe_bottom, (int, float)):
            check(x >= 0 and y >= safe_top and x + w <= safe_right and y + h <= safe_bottom,
                  f"portrait.{section} box exceeds a numerical safe-zone bound", failures)
        if section == "subtitles":
            check(isinstance(safe_top, (int, float)) and isinstance(safe_right, (int, float))
                  and isinstance(safe_bottom, (int, float)) and x >= 0 and y >= safe_top
                  and x + w <= safe_right and y + h <= safe_bottom,
                  "portrait subtitles box exceeds a numerical safe-zone bound", failures)
            check(box.get("maxLines") == 2, "portrait subtitles maxLines must be 2", failures)
            check(box.get("maxChineseCharsPerLine") == 14,
                  "portrait subtitles maxChineseCharsPerLine must be 14", failures)
            effective_font = float_or_nan(box.get("fontSize")) * 360 / portrait_dimensions[0]
            check(effective_font >= 13,
                  "portrait subtitles must remain at least 13px at a 360px-wide preview", failures)
        if section == "hud":
            effective_font = float_or_nan(box.get("fontSize")) * 360 / portrait_dimensions[0]
            check(effective_font >= 10,
                  "portrait core HUD labels must remain at least 10px at a 360px-wide preview", failures)

    anchor = portrait.get("subtitle_anchor_from_bottom_fraction") if isinstance(portrait, dict) else None
    subtitles = portrait.get("subtitles") if isinstance(portrait, dict) else None
    if isinstance(subtitles, dict) and all(type(subtitles.get(key)) in (int, float) for key in ("y", "h")):
        center_from_bottom = 1 - (float(subtitles["y"]) + float(subtitles["h"]) / 2) / portrait_dimensions[1]
        check(isinstance(anchor, (int, float)) and abs(center_from_bottom - float(anchor)) <= 0.015,
              "portrait subtitle anchor does not match its box center", failures)
        check(0.24 <= center_from_bottom <= 0.28,
              "portrait subtitle anchor must remain 24%-28% from the bottom", failures)

    landscape = contract.get("landscape")
    plot = landscape.get("plot") if isinstance(landscape, dict) else None
    if not isinstance(plot, dict):
        failures.append("layout-contract landscape.plot box is missing")
    elif all(type(plot.get(key)) in (int, float) for key in ("x", "y", "w", "h")):
        x, y, w, h = (float(plot[key]) for key in ("x", "y", "w", "h"))
        check(x >= 0 and y >= 0 and w > 0 and h > 0 and x + w <= 1920 and y + h <= 1080,
              "landscape.plot lies outside its logical canvas", failures)
    else:
        failures.append("landscape.plot must declare numeric x/y/w/h")
    return contract


def float_or_nan(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def verify_deterministic_source(failures: list[str], incomplete: list[str]) -> list[Path]:
    source_dir = PROJECT_DIR / "src"
    if not source_dir.is_dir():
        add_incomplete(incomplete, "project/src is missing; deterministic source scan pending")
        return []
    files = sorted(path for path in source_dir.rglob("*") if path.is_file() and path.suffix in {".ts", ".tsx", ".js", ".jsx"})
    if not files:
        add_incomplete(incomplete, "no TypeScript/JavaScript sources under project/src")
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            failures.append(f"cannot read source file {relative(path)}: {exc}")
            continue
        if re.search(r"\bMath\s*\.\s*random\s*\(|\bDate\s*\.\s*now\s*\(", text):
            failures.append(f"banned nondeterministic call in {relative(path)}")
    lexicon = load_json(PROJECT_DIR / "telemetry-lexicon.json", "telemetry-lexicon.json", failures, incomplete)
    if isinstance(lexicon, dict):
        terms = lexicon.get("terms")
        if not isinstance(terms, list) or not all(isinstance(term, str) and term for term in terms):
            failures.append("telemetry-lexicon.json terms must be a nonempty array of exact strings")
        else:
            corpus = "\n".join(
                path.read_text(encoding="utf-8", errors="replace")
                for path in files if path.is_file()
            ).casefold()
            for term in terms:
                check(term.casefold() in corpus,
                      f"exact telemetry lexicon term is absent from project/src: {term}", failures)
    return files


def verify_physics_numerics(report: dict[str, Any], failures: list[str], incomplete: list[str]) -> None:
    physics_path = PROJECT_DIR / "src" / "physics.ts"
    if not physics_path.is_file():
        add_incomplete(incomplete, "project/src/physics.ts is missing; analytical checks pending")
        return
    try:
        source = physics_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        failures.append(f"cannot read physics.ts: {exc}")
        return
    for name in FORMULA_EXPORTS:
        found = re.search(rf"\bexport\s+(?:declare\s+)?(?:async\s+)?(?:function|const|let|var)\s+{re.escape(name)}\b", source)
        check(found is not None, f"physics.ts must export formula function {name}", failures)
    if any(f"export const {name}" not in source and f"export function {name}" not in source for name in FORMULA_EXPORTS):
        return

    node = shutil.which("node")
    if node is None:
        add_incomplete(incomplete, "Node.js is unavailable; physics.ts numerical execution pending")
        return
    harness = r'''const fs=require("node:fs");
const vm=require("node:vm");
let ts;
try { ts=require("typescript"); }
catch (e) { process.stdout.write(JSON.stringify({missingTypescript:String(e.message||e)})); process.exit(0); }
const source=fs.readFileSync(process.argv[1],"utf8");
const js=ts.transpile(source,{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS});
const mod={exports:{}};
new Function("module","exports","require",js)(mod,mod.exports,(name)=>{throw new Error("physics.ts import is not allowed in numerical harness: "+name);});
const p=mod.exports;
const names=["landauer","planck","wien","radiated","koomey","potential","murrayChild"];
const missing=names.filter(n=>typeof p[n]!=="function");
if(missing.length) throw new Error("missing exported functions: "+missing.join(", "));
const e300=p.landauer(300), eCmb=p.landauer(2.725), ratio=e300/eCmb;
let peakLambda=2, peakValue=-Infinity;
for(let i=0;i<=20000;i++){const l=2+48*i/20000;const value=p.planck(l,300);if(value>peakValue){peakValue=value;peakLambda=l;}}
const wienLambda=p.wien(300);
const h=0.001;
const potentialChecks=[-1,1].map(x=>{const y=p.potential(x,1,0), ym=p.potential(x-h,1,0), yp=p.potential(x+h,1,0);return {x,value:y,derivative:(yp-ym)/(2*h),curvature:(yp-2*y+ym)/(h*h),neighborsLower:ym<y-1e-9||yp<y-1e-9};});
const r300=p.radiated(300),r600=p.radiated(600),radiatedRatio=r600/r300;
const years=[1946,1971,2026],koomey=years.map(y=>p.koomey(y));
const parent=0.0123,child=p.murrayChild(parent),murrayRatio=2*Math.pow(child,3)/Math.pow(parent,3);
const values={e300,eCmb,ratio,peakLambda,peakValue,wienLambda,potentialChecks,r300,r600,radiatedRatio,years,koomey,parent,child,murrayRatio};
process.stdout.write(JSON.stringify(values));
'''
    try:
        result = subprocess.run(
            [node, "-e", harness, str(physics_path)], cwd=PROJECT_DIR,
            check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        add_incomplete(incomplete, f"could not execute physics.ts numerical harness: {exc}")
        return
    if result.returncode != 0:
        failures.append("physics.ts numerical harness failed: " + result.stderr.strip()[-1200:])
        return
    try:
        values = json.loads(result.stdout)
    except json.JSONDecodeError:
        failures.append("physics.ts numerical harness returned invalid JSON: " + result.stdout[-500:])
        return
    if "missingTypescript" in values:
        add_incomplete(incomplete, "TypeScript runtime package is unavailable; physics.ts numerical execution pending")
        return
    report["physics_numerics"] = values
    expected_landauer = (2.870978e-21, 2.607e-23)
    check(math.isclose(values.get("e300", math.nan), expected_landauer[0], rel_tol=3e-5),
          "landauer(300) must be approximately 2.870978e-21 J/bit", failures)
    check(math.isclose(values.get("eCmb", math.nan), expected_landauer[1], rel_tol=5e-4),
          "landauer(2.725) must be approximately 2.607e-23 J/bit", failures)
    check(math.isclose(values.get("ratio", math.nan), 300 / 2.725, rel_tol=1e-6),
          "Landauer floor ratio between 300 K and 2.725 K must match the temperature ratio", failures)
    peak, wien = values.get("peakLambda"), values.get("wienLambda")
    check(isinstance(peak, (int, float)) and isinstance(wien, (int, float))
          and abs(peak - wien) <= 0.01,
          "sampled Planck maximum must agree with Wien's law within the wavelength grid", failures)
    extrema = values.get("potentialChecks")
    check(isinstance(extrema, list) and len(extrema) == 2,
          "potential minima check must return both x=-1 and x=1", failures)
    if isinstance(extrema, list) and len(extrema) == 2:
        for item in extrema:
            check(isinstance(item, dict) and abs(float_or_nan(item.get("derivative"))) < 1e-5
                  and float_or_nan(item.get("curvature")) > 0 and not item.get("neighborsLower", True),
                  f"potential must have a local minimum at x={item.get('x') if isinstance(item, dict) else '?'} for alpha=1, tilt=0", failures)
    check(math.isclose(values.get("radiatedRatio", math.nan), 16.0, rel_tol=1e-6),
          "radiated(T) must scale with T^4 when temperature doubles", failures)
    koomey = values.get("koomey")
    check(isinstance(koomey, list) and len(koomey) == 3
          and all(isinstance(value, (int, float)) and math.isfinite(value) and value > 0 for value in koomey)
          and koomey[0] < koomey[1] < koomey[2],
          "koomey(year) must return increasing positive finite ops/J at the specified years", failures)
    check(math.isclose(values.get("murrayRatio", math.nan), 1.0, rel_tol=1e-9, abs_tol=1e-9),
          "two equal Murray children must conserve the parent cubic radius", failures)


def verify_audio(report: dict[str, Any], failures: list[str], incomplete: list[str]) -> None:
    manifest = report.get("_manifest")
    audio = manifest.get("audio") if isinstance(manifest, dict) else None
    master_value = audio.get("master") if isinstance(audio, dict) else None
    if not isinstance(master_value, str) or not master_value:
        add_incomplete(incomplete, "delivery.json audio.master missing; PCM sample-count check pending")
        return
    master = resolve_delivery_path(master_value, "delivery.json audio.master", failures)
    if master is None:
        return
    if not master.is_file():
        add_incomplete(incomplete, f"shared PCM master missing: {relative(master)}")
        return
    try:
        with wave.open(str(master), "rb") as pcm:
            actual = (pcm.getframerate(), pcm.getnchannels(), pcm.getnframes(), pcm.getsampwidth())
        digest = hashlib.sha256()
        with master.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except (OSError, wave.Error) as exc:
        failures.append(f"cannot inspect shared PCM master: {exc}")
        return
    expected = (EXPECTED_SAMPLE_RATE, 2, EXPECTED_SAMPLES_PER_CHANNEL)
    check(actual[:3] == expected,
          f"shared PCM master must be 48kHz stereo with {EXPECTED_SAMPLES_PER_CHANNEL} samples/channel; got {actual}",
          failures)
    report["pcm_master"] = {
        "path": master_value,
        "sample_rate": actual[0], "channels": actual[1], "samples_per_channel": actual[2],
        "sample_width_bytes": actual[3], "sha256": digest.hexdigest(),
    }


def verify_audio_timing(failures: list[str], incomplete: list[str]) -> None:
    data = load_json(PROJECT_DIR / "audio-timing.json", "audio-timing.json", failures, incomplete)
    if data is None:
        return
    captions = data.get("captions") if isinstance(data, dict) else None
    if isinstance(data, dict):
        samples_per_channel = data.get("samplesPerChannel", data.get("targetSamplesPerChannel"))
        check((data.get("durationSeconds"), data.get("fps"), data.get("sampleRate"), data.get("samplesPerFrame"), samples_per_channel)
              == (EXPECTED_DURATION, EXPECTED_FPS, EXPECTED_SAMPLE_RATE, 800, EXPECTED_SAMPLES_PER_CHANNEL),
              "audio-timing.json must declare the 120s/60fps/48kHz master dimensions", failures)
        status = data.get("status")
        check(isinstance(status, str) and status.startswith("measured_pcm"),
              "audio-timing.json must report measured PCM timing", failures)

        measured_segments = data.get("segments")
        if not isinstance(measured_segments, list):
            failures.append("audio-timing.json segments must be an array")
        else:
            ids = [item.get("id") for item in measured_segments if isinstance(item, dict)]
            expected_ids = [item[0] for item in EXPECTED_SEGMENTS]
            check(ids == expected_ids, "audio-timing.json must contain ten ordered measured segments", failures)
            for index, (sid, start, end) in enumerate(EXPECTED_SEGMENTS):
                if index >= len(measured_segments) or not isinstance(measured_segments[index], dict):
                    continue
                segment = measured_segments[index]
                check((segment.get("declaredStartFrame"), segment.get("declaredEndFrame")) == (start, end),
                      f"measured audio segment {sid} declared frame window is incorrect", failures)
                voice_start = segment.get("voiceStartSample")
                voice_end = segment.get("voiceEndSampleExclusive")
                check(type(voice_start) is int and start * 800 <= voice_start < end * 800,
                      f"measured audio segment {sid} voiceStartSample must stay inside its declared frame window", failures)
                check(type(voice_end) is int and type(voice_start) is int
                      and voice_start < voice_end <= end * 800,
                      f"measured audio segment {sid} voice sample range must stay inside its declared frame window", failures)
        if isinstance(samples_per_channel, int) and samples_per_channel != EXPECTED_SAMPLES_PER_CHANNEL:
            failures.append("audio-timing.json sample count does not match the required PCM master length")
    if not isinstance(captions, list):
        failures.append("audio-timing.json captions must be an array")
        return
    grouped: dict[str, list[str]] = {}
    previous_end = -1
    for index, caption in enumerate(captions, start=1):
        if not isinstance(caption, dict):
            failures.append(f"caption {index} must be an object")
            continue
        start, end, text, sid = (caption.get(key) for key in ("startFrame", "endFrame", "text", "segmentId"))
        valid = type(start) is int and type(end) is int and 0 <= start < end <= EXPECTED_FRAMES
        check(valid, f"caption {index} frame bounds must be within [0, 7200)", failures)
        if valid:
            check(start >= previous_end, f"caption {index} overlaps the preceding caption", failures)
            previous_end = end
        check(isinstance(text, str) and bool(text.strip()), f"caption {index} text is missing", failures)
        check(isinstance(sid, str) and sid in {item[0] for item in EXPECTED_SEGMENTS},
              f"caption {index} segmentId is invalid", failures)
        if not isinstance(text, str) or not isinstance(sid, str):
            continue
        grouped.setdefault(sid, []).append(text)
        lines = text.splitlines() or [text]
        check(len(lines) <= 2, f"caption {index} has more than two lines", failures)
        for line_no, line in enumerate(lines, start=1):
            check(chinese_count(line) <= 14,
                  f"caption {index} line {line_no} exceeds 14 Chinese characters", failures)

    segments_data = load_json(PROJECT_DIR / "segments.json", "segments.json for caption comparison", failures, incomplete)
    if isinstance(segments_data, dict) and isinstance(segments_data.get("segments"), list):
        by_id = {item.get("id"): item for item in segments_data["segments"] if isinstance(item, dict)}
        for sid, _, _ in EXPECTED_SEGMENTS:
            segment = by_id.get(sid)
            display = segment.get("display_subtitle") if isinstance(segment, dict) else None
            if not isinstance(display, str):
                add_incomplete(incomplete, f"{sid} display subtitle unavailable for caption comparison")
                continue
            check(sid in grouped, f"audio-timing captions are missing {sid}", failures)
            joined = "".join(grouped.get(sid, []))
            check(normalized(joined) == normalized(display),
                  f"concatenated caption text for {sid} differs from its normalized display subtitle", failures)


def main() -> int:
    args = parse_args()
    failures: list[str] = []
    incomplete: list[str] = []
    report: dict[str, Any] = {"schema_version": 1, "checker": "EP05 source and numerical verifier"}
    manifest = verify_manifest(report, failures, incomplete)
    report["_manifest"] = manifest
    verify_segments(failures, incomplete)
    verify_timeline(failures, incomplete)
    verify_layout_contract(failures, incomplete)
    verify_deterministic_source(failures, incomplete)
    verify_physics_numerics(report, failures, incomplete)
    verify_audio(report, failures, incomplete)
    verify_audio_timing(failures, incomplete)
    report.pop("_manifest", None)

    status = "FAIL" if failures else "INCOMPLETE" if incomplete else "PASS"
    report.update({
        "status": status,
        "failures": failures,
        "incomplete": incomplete,
        "limitations": [
            "This verifier checks source, numerical formulas, layout bounds, timeline and PCM metadata only.",
            "It does not decode or approve either final MP4, assess visual content, or claim human listening/device acceptance.",
            "PNG frame capture and encoded AAC evidence are collected separately by collect_qa.py.",
        ],
    })
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(rendered, end="")
    if not args.no_write:
        review = DELIVERY_DIR / "review"
        review.mkdir(parents=True, exist_ok=True)
        temp = review / "project-check.json.tmp"
        temp.write_text(rendered, encoding="utf-8")
        os.replace(temp, review / "project-check.json")
    return 1 if failures else 2 if incomplete else 0


if __name__ == "__main__":
    raise SystemExit(main())
