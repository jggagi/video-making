#!/usr/bin/env python3
"""Check EP14 source and authored timing contracts without judging the film.

This verifier prints JSON to stdout and never edits project or review files.
Missing work in progress is reported as INCOMPLETE; an invalid authored value
is FAIL. It does not render, decode, visually review, or listen to the film.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
import wave
from pathlib import Path
from typing import Any, Callable


PROJECT = Path(__file__).resolve().parents[1]
DELIVERY = PROJECT.parent
FPS = 60
TOTAL_FRAMES = 5_400
SAMPLE_RATE = 48_000
CHANNELS = 2
SAMPLES_PER_FRAME = SAMPLE_RATE // FPS
SAMPLES_PER_CHANNEL = TOTAL_FRAMES * SAMPLES_PER_FRAME
SILENCE_FRAMES = (4_860, 4_890)
SILENCE_SAMPLES = tuple(frame * SAMPLES_PER_FRAME for frame in SILENCE_FRAMES)
SEGMENT_IDS = [f"S{i:02d}" for i in range(1, 9)]
APPROVED_S03 = "在这个思想实验里它被画成一层马尔可夫毯反应再像也不等于灵魂"
CAPTION_LINE_LIMIT = 13

checks: list[dict[str, Any]] = []


def add(status: str, check_id: str, message: str, details: Any = None) -> None:
    item: dict[str, Any] = {"id": check_id, "status": status, "message": message}
    if details is not None:
        item["details"] = details
    checks.append(item)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def run_check(check_id: str, fn: Callable[[], tuple[str, str, Any | None]]) -> None:
    try:
        status, message, details = fn()
        add(status, check_id, message, details)
    except FileNotFoundError as exc:
        add("INCOMPLETE", check_id, f"required project file is not available yet: {exc.filename}")
    except (OSError, ValueError, KeyError, TypeError, AttributeError, json.JSONDecodeError) as exc:
        add("FAIL", check_id, f"{type(exc).__name__}: {exc}")


def check_delivery_contract() -> tuple[str, str, Any]:
    delivery = load_json(DELIVERY / "delivery.json")
    errors = []
    expected_top = {"slug": "si-ep14-ghost-in-posterior", "duration_seconds": 90, "fps": FPS, "total_frames": TOTAL_FRAMES}
    for field, expected in expected_top.items():
        if delivery.get(field) != expected:
            errors.append(f"delivery.json {field} must be {expected!r}; got {delivery.get(field)!r}")
    if delivery.get("platforms") != ["xiaohongshu"]:
        errors.append("delivery.json platforms must be exactly ['xiaohongshu']")
    output = delivery.get("outputs", {}).get("xiaohongshu", {})
    if (output.get("width"), output.get("height")) != (2160, 3840):
        errors.append("delivery.json Xiaohongshu output must be 2160x3840")
    if delivery.get("visual_qc", {}).get("required") is not True:
        errors.append("delivery.json must require visual QC")
    if errors:
        raise ValueError("; ".join(errors))
    return "PASS", "Delivery manifest declares the fixed 90-second, 60 fps, portrait-only specification.", {
        "slug": delivery["slug"],
        "platforms": delivery["platforms"],
        "durationSeconds": delivery["duration_seconds"],
        "fps": FPS,
        "totalFrames": TOTAL_FRAMES,
        "output": output,
        "visualQcRequired": True,
    }


def check_source_hashes() -> tuple[str, str, Any]:
    delivery = load_json(DELIVERY / "delivery.json")
    results: dict[str, Any] = {}
    for manifest_key in ("script", "source_completion"):
        record = delivery.get(manifest_key)
        if not isinstance(record, dict):
            if manifest_key == "source_completion":
                continue
            raise ValueError("delivery.json script record is missing")
        relative = record.get("path")
        expected = record.get("sha256")
        if not isinstance(relative, str) or not relative or not isinstance(expected, str):
            raise ValueError(f"delivery.json {manifest_key} path or sha256 is missing")
        path = (DELIVERY / relative).resolve()
        try:
            path.relative_to(DELIVERY.resolve())
        except ValueError:
            raise ValueError(f"delivery.json {manifest_key} path escapes the delivery directory") from None
        if not path.is_file():
            return "INCOMPLETE", f"Source file for {manifest_key} is not present yet.", {"path": relative, "expectedSha256": expected}
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"delivery.json {manifest_key} SHA-256 mismatch: actual {actual}")
        results[manifest_key] = {"path": relative, "sha256": actual, "matchesDelivery": True}
    return "PASS", "Original script and any declared user-completion source match their delivery hashes.", results


def check_root_composition() -> tuple[str, str, Any]:
    path = PROJECT / "src" / "Root.tsx"
    if not path.is_file():
        return "INCOMPLETE", "src/Root.tsx is not available yet; composition dimensions and frame count remain unverified.", {"path": "project/src/Root.tsx"}
    entry_path = PROJECT / "src" / "index.ts"
    if not entry_path.is_file():
        return "INCOMPLETE", "src/index.ts is not available yet; the registered Remotion entry point remains unverified.", {"path": "project/src/index.ts"}
    source = path.read_text(encoding="utf-8")
    entry = entry_path.read_text(encoding="utf-8")
    if not re.search(r"\bregisterRoot\s*\(\s*Root\s*\)", entry) or not re.search(r"\bRoot\b", entry):
        raise ValueError("src/index.ts must register the project Root with Remotion")
    requirements = {
        "id": r"\bid\s*=\s*['\"]PortraitVertical['\"]",
        "width": r"\bwidth\s*=\s*\{\s*2160\s*\}",
        "height": r"\bheight\s*=\s*\{\s*3840\s*\}",
        "fps": r"\bfps\s*=\s*\{\s*60\s*\}",
        "durationInFrames": r"\bdurationInFrames\s*=\s*\{\s*5400\s*\}",
    }
    missing = [name for name, pattern in requirements.items() if not re.search(pattern, source)]
    if missing:
        raise ValueError(f"Root.tsx is missing the required composition declaration(s): {missing}")
    return "PASS", "src/index.ts registers Root, whose PortraitVertical composition declares 2160x3840 at 60 fps for 5400 frames.", {
        "entrypoint": "project/src/index.ts",
        "registersRoot": True,
        "path": "project/src/Root.tsx",
        "composition": "PortraitVertical",
        "width": 2160,
        "height": 3840,
        "fps": FPS,
        "durationInFrames": TOTAL_FRAMES,
    }


def check_segments_and_approved_s03() -> tuple[str, str, Any]:
    path = PROJECT / "segments.json"
    if not path.is_file():
        return "INCOMPLETE", "segments.json is not available yet.", {"path": "project/segments.json"}
    segments = load_json(path)
    if not isinstance(segments, list) or [item.get("id") for item in segments] != SEGMENT_IDS:
        raise ValueError("segments.json must contain exactly S01 through S08 in source order")
    prior_end = 0
    windows = []
    for item in segments:
        start, end = item.get("startFrame"), item.get("endFrame")
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= TOTAL_FRAMES:
            raise ValueError(f"{item['id']} must have bounded integer frame windows inside 0..5400")
        if start < prior_end:
            raise ValueError(f"{item['id']} overlaps or precedes the previous authored segment window")
        if not isinstance(item.get("display_subtitle"), str) or not item["display_subtitle"].strip():
            raise ValueError(f"{item['id']} is missing display_subtitle")
        if not isinstance(item.get("tts_phonetic_text"), str) or not item["tts_phonetic_text"].strip():
            raise ValueError(f"{item['id']} is missing tts_phonetic_text")
        windows.append({"id": item["id"], "frames": [start, end]})
        prior_end = end
    s03 = segments[2]
    for field in ("display_subtitle", "tts_phonetic_text"):
        actual = normalize_approved_text(s03[field])
        if actual != APPROVED_S03:
            raise ValueError(f"S03 {field} differs from the approved wording")
    return "PASS", "Eight source-order narration segments have bounded non-overlapping integer windows; S03 matches the approved correction.", {
        "segmentCount": len(segments),
        "windows": windows,
        "approvedS03": True,
        "approvedS03Fields": ["display_subtitle", "tts_phonetic_text"],
    }


def normalize_approved_text(value: str) -> str:
    return "".join(char for char in value if not char.isspace() and not unicodedata.category(char).startswith("P"))


def source_files() -> list[Path]:
    src = PROJECT / "src"
    if not src.is_dir():
        return []
    return sorted(path for path in src.rglob("*") if path.is_file() and path.suffix.lower() in {".ts", ".tsx", ".js", ".jsx", ".css"})


def check_2d_deterministic_source() -> tuple[str, str, Any]:
    paths = source_files()
    if not paths:
        return "INCOMPLETE", "No project/src source files are available to inspect yet.", {"sourceFilesScanned": []}
    forbidden = {
        "Math.random": re.compile(r"\bMath\s*\.\s*random\s*\("),
        "Date.now": re.compile(r"\bDate\s*\.\s*now\s*\("),
        "perspective": re.compile(r"\bperspective\s*(?:\(|:)" , re.I),
        "rotateX": re.compile(r"\brotateX\s*(?:\(|:)" , re.I),
        "rotateY": re.compile(r"\brotateY\s*(?:\(|:)" , re.I),
    }
    findings = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"/\*[\s\S]*?\*/", "", text)
        text = re.sub(r"(?m)^\s*//.*$", "", text)
        for api, pattern in forbidden.items():
            for match in pattern.finditer(text):
                findings.append({"file": path.relative_to(DELIVERY).as_posix(), "line": text.count("\n", 0, match.start()) + 1, "api": api})
    if findings:
        raise ValueError(f"forbidden nondeterministic or 3D APIs found: {findings}")
    return "PASS", "No Math.random, Date.now, perspective, rotateX, or rotateY source calls/properties were found.", {
        "sourceFilesScanned": [path.relative_to(DELIVERY).as_posix() for path in paths],
        "forbiddenApiFindings": 0,
    }


def check_measured_captions() -> tuple[str, str, Any]:
    path = PROJECT / "audio-timing.json"
    if not path.is_file():
        return "INCOMPLETE", "audio-timing.json is absent; measured caption timing is pending.", None
    timing = load_json(path)
    captions = timing.get("captions")
    if timing.get("status") == "PREVIEW_ONLY" or not isinstance(captions, list) or not captions:
        return "INCOMPLETE", "audio-timing.json contains preview timing; measured caption bounds remain unverified.", {
            "status": timing.get("status"),
            "captionCount": len(captions) if isinstance(captions, list) else None,
        }
    if (timing.get("fps"), timing.get("sampleRate"), timing.get("samplesPerChannel")) != (FPS, SAMPLE_RATE, SAMPLES_PER_CHANNEL):
        raise ValueError("measured audio-timing.json must declare 60 fps, 48 kHz, and 4,320,000 samples per channel")
    prior_end = 0
    for index, caption in enumerate(captions):
        start, end, text = caption.get("startFrame"), caption.get("endFrame"), caption.get("text")
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= TOTAL_FRAMES:
            raise ValueError(f"caption {index} has invalid bounded integer frame values")
        if start < prior_end:
            raise ValueError(f"caption {index} overlaps or precedes the preceding caption")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"caption {index} has no text")
        lines = text.splitlines()
        if not 1 <= len(lines) <= 2:
            raise ValueError(f"caption {index} must contain one or two lines")
        if any(len(line.strip()) > CAPTION_LINE_LIMIT for line in lines):
            raise ValueError(f"caption {index} exceeds {CAPTION_LINE_LIMIT} characters on a line")
        segment_id = caption.get("segmentId")
        if segment_id is not None and segment_id not in SEGMENT_IDS:
            raise ValueError(f"caption {index} references unknown segment {segment_id!r}")
        prior_end = end
    return "PASS", "Measured captions are bounded, ordered, non-overlapping, and fit at most two 13-character lines.", {
        "captionCount": len(captions),
        "maxLines": 2,
        "maxCharactersPerLine": CAPTION_LINE_LIMIT,
        "alignmentJudgment": "NOT_RECORDED",
    }


def check_required_assets() -> tuple[str, str, Any]:
    delivery = load_json(DELIVERY / "delivery.json")
    required = [
        "source/script.md", "source/user-completion.md", "project/adapted-script.md",
        "project/segments.json", "project/timeline.json", "project/telemetry-lexicon.json",
        "project/audio-authorization.json", "project/src/index.ts", "project/src/Root.tsx",
        "project/src/Film.tsx",
    ]
    absent = [relative for relative in required if not (DELIVERY / relative).is_file()]
    references: list[str] = []
    missing_references: list[str] = []
    extensions = ("", ".ts", ".tsx", ".js", ".jsx", ".json", ".css", ".svg", ".png", ".jpg", ".webp")
    for source in source_files():
        text = source.read_text(encoding="utf-8")
        for match in re.finditer(r"(?:\bfrom\s*|\bimport\s*)['\"](\.{1,2}/[^'\"]+)['\"]", text):
            relative = match.group(1)
            target = (source.parent / relative).resolve()
            candidates = [target] if target.suffix else [Path(str(target) + ext) for ext in extensions]
            candidates += [target / f"index{ext}" for ext in (".ts", ".tsx", ".js", ".jsx")]
            if not any(candidate.is_file() for candidate in candidates):
                missing_references.append(f"{source.relative_to(DELIVERY).as_posix()} -> {relative}")
            else:
                references.append(relative)
        for match in re.finditer(r"\bstaticFile\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", text):
            relative = match.group(1)
            if not (PROJECT / "public" / relative).is_file():
                missing_references.append(f"staticFile({relative!r}) in {source.relative_to(DELIVERY).as_posix()}")
            else:
                references.append(f"public/{relative}")

    manifest_path = PROJECT / "assets-manifest.json"
    if manifest_path.is_file():
        manifest = load_json(manifest_path)
        for item in manifest.get("resources", []):
            relative = item.get("path") if isinstance(item, dict) else None
            if isinstance(relative, str) and not (PROJECT / relative).is_file():
                missing_references.append(f"assets-manifest.json -> {relative}")

    if missing_references:
        return "INCOMPLETE", "Project assets referenced by the available source or manifest are missing.", {
            "missing": missing_references,
            "requiredFilesMissing": absent,
        }
    if absent:
        return "INCOMPLETE", "Required source/project files are still being created.", {"requiredFilesMissing": absent}
    return "PASS", "Required source/project files and all currently declared local imports/assets are present.", {
        "requiredFilesMissing": [],
        "declaredLocalReferencesChecked": len(references),
        "assetsManifestPresent": manifest_path.is_file(),
    }


def check_pcm_master() -> tuple[str, str, Any]:
    delivery = load_json(DELIVERY / "delivery.json")
    relative = delivery.get("audio", {}).get("master", "project/public/audio/master.wav")
    if not isinstance(relative, str) or not relative:
        raise ValueError("delivery.json audio.master must be a project-relative path")
    path = (DELIVERY / relative).resolve()
    try:
        path.relative_to(DELIVERY.resolve())
    except ValueError:
        raise ValueError("delivery.json audio.master escapes the delivery directory") from None
    if not path.is_file():
        return "INCOMPLETE", "Final PCM master is not present yet; format, sample count, and exact silence remain unverified.", {
            "expectedPath": relative,
            "expectedSampleRate": SAMPLE_RATE,
            "expectedChannels": CHANNELS,
            "expectedSamplesPerChannel": SAMPLES_PER_CHANNEL,
            "silenceFrameRange": list(SILENCE_FRAMES),
            "silenceSampleRange": list(SILENCE_SAMPLES),
        }
    try:
        with wave.open(str(path), "rb") as wav:
            params = wav.getparams()
            if params.comptype != "NONE":
                raise ValueError(f"master is not uncompressed PCM: {params.comptype}")
            if (params.framerate, params.nchannels, params.nframes) != (SAMPLE_RATE, CHANNELS, SAMPLES_PER_CHANNEL):
                raise ValueError(f"master must be real 48 kHz stereo PCM with {SAMPLES_PER_CHANNEL} samples per channel; got {params}")
            wav.setpos(SILENCE_SAMPLES[0])
            silence = wav.readframes(SILENCE_SAMPLES[1] - SILENCE_SAMPLES[0])
            expected_bytes = (SILENCE_SAMPLES[1] - SILENCE_SAMPLES[0]) * CHANNELS * params.sampwidth
            if len(silence) != expected_bytes:
                raise ValueError("master blackout window was truncated while reading")
            if any(silence):
                raise ValueError("master contains non-zero PCM bytes during frames [4860, 4890)")
    except (OSError, wave.Error) as exc:
        raise ValueError(f"cannot inspect PCM master WAV: {exc}") from None
    return "PASS", "PCM master has the exact stereo 48 kHz sample count and digital silence on frames [4860, 4890).", {
        "path": relative,
        "sampleRate": SAMPLE_RATE,
        "channels": CHANNELS,
        "samplesPerChannel": SAMPLES_PER_CHANNEL,
        "sampleWidthBytes": params.sampwidth,
        "silenceFrameRange": list(SILENCE_FRAMES),
        "silenceSampleRange": list(SILENCE_SAMPLES),
        "silenceBytesAreZero": True,
    }


def check_encoded_output_presence() -> tuple[str, str, Any]:
    delivery = load_json(DELIVERY / "delivery.json")
    relative = delivery.get("outputs", {}).get("xiaohongshu", {}).get("path")
    if not isinstance(relative, str) or not relative:
        raise ValueError("delivery.json outputs.xiaohongshu.path is missing")
    target = (DELIVERY / relative).resolve()
    try:
        target.relative_to(DELIVERY.resolve())
    except ValueError:
        raise ValueError("delivery output path escapes the work directory") from None
    if not target.is_file():
        return "INCOMPLETE", "Final encoded video is absent; this source verifier does not infer render or media acceptance.", {"expectedPath": relative}
    return "PASS", "Final encoded video file is present; encoding and media acceptance are not performed by this source verifier.", {
        "path": relative,
        "sizeBytes": target.stat().st_size,
        "mediaValidation": "NOT_PERFORMED",
    }


def main() -> int:
    for check_id, fn in (
        ("delivery_contract", check_delivery_contract),
        ("source_hashes", check_source_hashes),
        ("portrait_entry_root", check_root_composition),
        ("segments_and_approved_s03", check_segments_and_approved_s03),
        ("determinism_and_2d_source_apis", check_2d_deterministic_source),
        ("measured_captions", check_measured_captions),
        ("required_assets", check_required_assets),
        ("pcm_master", check_pcm_master),
        ("encoded_output_presence", check_encoded_output_presence),
    ):
        run_check(check_id, fn)

    statuses = [item["status"] for item in checks]
    overall = "FAIL" if "FAIL" in statuses else "INCOMPLETE" if "INCOMPLETE" in statuses else "PASS"
    report = {
        "schema_version": 1,
        "work": "si-ep14-ghost-in-posterior",
        "checker": "project/scripts/verify_project.py",
        "scope": "source, authored timing, local references, and PCM-master contract; not final-media or human acceptance",
        "status": overall,
        "summary": {"pass": statuses.count("PASS"), "fail": statuses.count("FAIL"), "incomplete": statuses.count("INCOMPLETE")},
        "renderAcceptance": "NOT_RECORDED",
        "visualReview": "NOT_RECORDED",
        "humanListening": "NOT_RECORDED",
        "devicePlayback": "NOT_RECORDED",
        "checks": checks,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if overall == "FAIL" else 2 if overall == "INCOMPLETE" else 0


if __name__ == "__main__":
    sys.exit(main())
