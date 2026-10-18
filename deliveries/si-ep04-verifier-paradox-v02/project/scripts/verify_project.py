#!/usr/bin/env python3
"""Check v2 source and shared-audio invariants without accepting final media.

The report keeps source checks separate from final-file presence. This script
does not decode, listen to, or visually approve either encoded movie.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import wave
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DELIVERY_DIR = PROJECT_DIR.parent
V1_DIR = DELIVERY_DIR.parent / "si-ep04-verifier-paradox"
EXPECTED_FRAMES = 7_200
EXPECTED_SEGMENT_IDS = [f"S{index:02d}" for index in range(1, 11)]
EXPECTED_SHOT_BOUNDS = [
    (0, 1200), (1200, 1800), (1800, 2700), (2700, 3600),
    (3600, 4500), (4500, 5400), (5400, 6300), (6300, 6930), (6930, 7200),
]
MODEL_KIND = "illustrative mixture of two deterministic episode policies, not paper data"
EXPECTED_AUDIO_FILES = 47


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify EP04 v2 source invariants without claiming final media acceptance."
    )
    parser.add_argument(
        "--no-write", action="store_true",
        help="Print the report without writing review/project-check.json.",
    )
    return parser.parse_args()


def check(ok: bool, message: str, failures: list[str]) -> None:
    if not ok:
        failures.append(message)


def load_json(path: Path, label: str, failures: list[str], incomplete: list[str]) -> Any | None:
    if not path.is_file():
        try:
            location = path.relative_to(DELIVERY_DIR).as_posix()
        except ValueError:
            location = path.as_posix()
        incomplete.append(f"missing {label}: {location}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        failures.append(f"cannot read {label}: {exc}")
        return None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def safe_delivery_path(relative: Any, label: str, failures: list[str]) -> Path | None:
    if not isinstance(relative, str) or not relative:
        failures.append(f"{label} path is missing")
        return None
    path = (DELIVERY_DIR / relative).resolve()
    try:
        path.relative_to(DELIVERY_DIR.resolve())
    except ValueError:
        failures.append(f"{label} path escapes the delivery folder")
        return None
    return path


def verify_manifest(report: dict[str, Any], failures: list[str], incomplete: list[str]) -> dict[str, Any] | None:
    manifest = load_json(DELIVERY_DIR / "delivery.json", "delivery.json", failures, incomplete)
    if not isinstance(manifest, dict):
        if manifest is not None:
            failures.append("delivery.json must contain an object")
        return None

    check(manifest.get("slug") == DELIVERY_DIR.name, "delivery slug must match the v2 folder", failures)
    check(
        (manifest.get("duration_seconds"), manifest.get("fps"), manifest.get("total_frames"))
        == (120, 60, EXPECTED_FRAMES),
        "delivery.json must specify 120 seconds, 60 fps, and 7200 frames",
        failures,
    )

    script_info = manifest.get("script")
    if not isinstance(script_info, dict):
        failures.append("delivery.json script record is missing")
    else:
        script_path = safe_delivery_path(script_info.get("path"), "delivery.json script", failures)
        if script_path is not None:
            if not script_path.is_file():
                incomplete.append(f"missing source script: {script_info.get('path')}")
            else:
                actual_hash = sha256_file(script_path)
                check(actual_hash == script_info.get("sha256"), "source script hash differs from delivery.json", failures)
                old_script = V1_DIR / "source/script.md"
                if old_script.is_file():
                    check(script_path.read_bytes() == old_script.read_bytes(), "v2 source script differs from v1", failures)
                else:
                    incomplete.append("v1 source script unavailable for identity comparison")
                old_manifest = load_json(V1_DIR / "delivery.json", "v1 delivery.json", failures, incomplete)
                old_script_info = old_manifest.get("script") if isinstance(old_manifest, dict) else None
                old_hash = old_script_info.get("sha256") if isinstance(old_script_info, dict) else None
                check(actual_hash == old_hash, "v2 source script SHA-256 differs from v1", failures)

    audio = manifest.get("audio")
    check(
        isinstance(audio, dict)
        and audio.get("master") == "project/public/audio/master.wav"
        and audio.get("sample_rate") == 48_000
        and audio.get("channels") == 2
        and audio.get("samples_per_channel") == 5_760_000,
        "delivery.json must identify the shared 48-kHz stereo 120-second PCM master",
        failures,
    )
    outputs = manifest.get("outputs")
    expected_outputs = {
        "bilibili": (3840, 2160),
        "xiaohongshu": (2160, 3840),
    }
    if not isinstance(outputs, dict):
        failures.append("delivery.json outputs must be an object")
    else:
        for key, dimensions in expected_outputs.items():
            output = outputs.get(key)
            check(
                isinstance(output, dict)
                and (output.get("width"), output.get("height")) == dimensions,
                f"delivery.json outputs.{key} must declare {dimensions[0]}x{dimensions[1]}",
                failures,
            )

    report["delivery_timing"] = {
        "duration_seconds": manifest.get("duration_seconds"),
        "fps": manifest.get("fps"),
        "total_frames": manifest.get("total_frames"),
    }
    return manifest


def verify_compositions(failures: list[str], incomplete: list[str]) -> None:
    root_path = PROJECT_DIR / "src/Root.tsx"
    if not root_path.is_file():
        incomplete.append("missing project/src/Root.tsx; composition check pending")
        return
    try:
        source = root_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        failures.append(f"cannot read Root.tsx: {exc}")
        return

    compositions: dict[str, dict[str, Any]] = {}
    attr_pattern = re.compile(
        r"\b(id|width|height|fps|durationInFrames)\s*=\s*(?:\{\s*([^}]+?)\s*\}|\"([^\"]*)\")"
    )
    for tag in re.findall(r"<Composition\b([^>]*)>", source, flags=re.DOTALL):
        attrs: dict[str, Any] = {}
        for name, expression, quoted in attr_pattern.findall(tag):
            raw = expression or quoted
            raw = raw.strip()
            if name == "id":
                attrs[name] = raw
            else:
                try:
                    attrs[name] = int(raw)
                except ValueError:
                    attrs[name] = raw
        if isinstance(attrs.get("id"), str):
            compositions[attrs["id"]] = attrs

    expected = {
        "Landscape4K": {"width": 3840, "height": 2160, "fps": 60, "durationInFrames": EXPECTED_FRAMES},
        "PortraitVertical": {"width": 2160, "height": 3840, "fps": 60, "durationInFrames": EXPECTED_FRAMES},
    }
    for name, values in expected.items():
        actual = compositions.get(name, {})
        check(all(actual.get(key) == value for key, value in values.items()),
              f"Root.tsx {name} composition must use native 4K, 60 fps, and 7200 frames", failures)


def verify_timeline(failures: list[str], incomplete: list[str]) -> None:
    data = load_json(PROJECT_DIR / "timeline.json", "timeline.json", failures, incomplete)
    if data is None:
        return
    shots = data.get("shots") if isinstance(data, dict) else None
    check(isinstance(shots, list), "timeline.json must contain a shots array", failures)
    if not isinstance(shots, list):
        return
    actual_bounds = []
    for index, shot in enumerate(shots, start=1):
        if not isinstance(shot, dict):
            failures.append(f"timeline shot {index} must be an object")
            continue
        actual_bounds.append((shot.get("startFrame"), shot.get("endFrame")))
    total_frames = data.get("total_frames", data.get("totalFrames"))
    check(data.get("fps") == 60 and total_frames == EXPECTED_FRAMES,
          "timeline timing must be 60 fps and 7200 frames", failures)
    check(actual_bounds == EXPECTED_SHOT_BOUNDS,
          "timeline shot bounds must match the nine approved v2 scene intervals", failures)


def verify_audio_timing(failures: list[str], incomplete: list[str]) -> dict[str, Any] | None:
    data = load_json(PROJECT_DIR / "audio-timing.json", "audio-timing.json", failures, incomplete)
    if not isinstance(data, dict):
        if data is not None:
            failures.append("audio-timing.json must contain an object")
        return None
    check(
        (data.get("durationSeconds"), data.get("fps"), data.get("sampleRate"), data.get("samplesPerChannel"))
        == (120, 60, 48_000, 5_760_000),
        "audio-timing.json must describe the exact 120-second 48-kHz timeline",
        failures,
    )
    segments, captions = data.get("segments"), data.get("captions")
    check(isinstance(segments, list) and len(segments) == 10,
          "audio-timing.json must contain exactly 10 measured PCM segments", failures)
    check(isinstance(captions, list) and len(captions) == 19,
          "audio-timing.json must contain exactly 19 captions", failures)
    if isinstance(segments, list):
        actual_ids = [item.get("id") for item in segments if isinstance(item, dict)]
        check(actual_ids == EXPECTED_SEGMENT_IDS, "audio-timing segments must be S01-S10 in order", failures)
        for index, item in enumerate(segments, start=1):
            if not isinstance(item, dict):
                failures.append(f"audio-timing segment {index} must be an object")
                continue
            check(type(item.get("samplesAt48k")) is int and item["samplesAt48k"] > 0,
                  f"audio-timing segment {index} needs a positive measured PCM sample count", failures)
            start, end = item.get("startFrame"), item.get("endFrame")
            check(type(start) is int and type(end) is int and 0 <= start < end <= EXPECTED_FRAMES,
                  f"audio-timing segment {index} has invalid frame bounds", failures)
    if isinstance(captions, list):
        for index, item in enumerate(captions, start=1):
            if not isinstance(item, dict):
                failures.append(f"caption {index} must be an object")
                continue
            start, end = item.get("startFrame"), item.get("endFrame")
            text = item.get("text")
            check(type(start) is int and type(end) is int and 0 <= start < end <= EXPECTED_FRAMES,
                  f"caption {index} has invalid frame bounds", failures)
            check(isinstance(text, str) and bool(text.strip()), f"caption {index} text is missing", failures)
    return data


def verify_sfx_and_stems(failures: list[str], incomplete: list[str]) -> dict[str, Any]:
    data = load_json(PROJECT_DIR / "sfx_events.json", "sfx_events.json", failures, incomplete)
    event_ok = False
    if isinstance(data, dict):
        events = data.get("events")
        event = next((item for item in events if isinstance(item, dict) and item.get("id") == "physical_veto"), None) if isinstance(events, list) else None
        sample = event.get("sampleIndex", event.get("sample")) if isinstance(event, dict) else None
        event_ok = isinstance(event, dict) and event.get("frame") == 5760 and sample == 4_608_000
        check(data.get("fps") == 60 and data.get("sampleRate") == 48_000 and data.get("samplesPerFrame") == 800,
              "SFX event map must use 60 fps and 48-kHz samples", failures)
        check(event_ok, "physical_veto must be anchored at frame 5760 / sample 4608000", failures)
        silence = data.get("absoluteSilence")
        check(isinstance(silence, dict) and (silence.get("startFrame"), silence.get("endFrame")) == (5740, 5760),
              "SFX absolute silence must cover [5740, 5760)", failures)

    stem_results: dict[str, Any] = {}
    for name in ("master", "narration", "score", "sfx"):
        path = PROJECT_DIR / f"public/audio/{name}.wav"
        if not path.is_file():
            incomplete.append(f"missing {name} PCM stem; shape and silence check pending")
            stem_results[name] = {"present": False}
            continue
        try:
            with wave.open(str(path), "rb") as stream:
                shape = (stream.getframerate(), stream.getnchannels(), stream.getnframes(), stream.getcomptype())
                check(shape == (48_000, 2, 5_760_000, "NONE"),
                      f"{name} WAV must be 48-kHz stereo PCM with 5760000 samples per channel", failures)
                stream.setpos(5740 * 800)
                silence_bytes = stream.readframes(20 * 800)
                silent = len(silence_bytes) == 20 * 800 * 2 * stream.getsampwidth() and not any(silence_bytes)
                check(silent, f"{name} stem must be silent throughout frames 5740-5759", failures)
                stem_results[name] = {
                    "present": True,
                    "sample_rate": shape[0],
                    "channels": shape[1],
                    "samples_per_channel": shape[2],
                    "silent_5740_5760": silent,
                    "sha256": sha256_file(path),
                }
        except (OSError, wave.Error) as exc:
            failures.append(f"cannot inspect {name} WAV: {exc}")
    return {"physical_veto_anchor_valid": event_ok, "stems": stem_results}


def verify_audio_reuse(report: dict[str, Any], failures: list[str], incomplete: list[str]) -> None:
    reuse = load_json(DELIVERY_DIR / "review/audio-reuse.json", "review/audio-reuse.json", failures, incomplete)
    if isinstance(reuse, dict):
        check(reuse.get("status") == "PASS" and reuse.get("source_work") == V1_DIR.name,
              "audio-reuse report must identify the v1 source as PASS", failures)
        check(reuse.get("files_verified") == EXPECTED_AUDIO_FILES,
              "audio-reuse report must cover all 47 copied audio files", failures)

    old_audio = V1_DIR / "project/public/audio"
    new_audio = PROJECT_DIR / "public/audio"
    if not old_audio.is_dir():
        incomplete.append("v1 audio directory unavailable for byte-identity comparison")
        return
    old_files = {path.relative_to(old_audio).as_posix(): path for path in old_audio.rglob("*") if path.is_file()}
    new_files = {path.relative_to(new_audio).as_posix(): path for path in new_audio.rglob("*") if path.is_file()}
    check(len(old_files) == EXPECTED_AUDIO_FILES and len(new_files) == EXPECTED_AUDIO_FILES,
          "v1 and v2 audio directories must each contain the expected 47 files", failures)
    check(old_files.keys() == new_files.keys(), "v2 audio file set differs from v1", failures)
    compared = 0
    for relative in sorted(old_files.keys() & new_files.keys()):
        if old_files[relative].read_bytes() != new_files[relative].read_bytes():
            failures.append(f"copied audio file differs from v1: {relative}")
        else:
            compared += 1
    check(compared == EXPECTED_AUDIO_FILES, "not all 47 copied audio files matched v1", failures)
    report["audio_reuse"] = {"files_compared_byte_for_byte": compared, "source_work": V1_DIR.name}


def verify_source_code(report: dict[str, Any], failures: list[str], incomplete: list[str]) -> None:
    source_files = sorted(
        path for path in (PROJECT_DIR / "src").rglob("*")
        if path.is_file() and path.suffix in {".ts", ".tsx", ".js", ".jsx"}
    ) if (PROJECT_DIR / "src").is_dir() else []
    if not source_files:
        incomplete.append("source code not present under project/src")
        return

    telemetry_scan = {"files_scanned": len(source_files), "nondeterministic_hits": [], "fictional_alignment_hits": []}
    number_pattern = re.compile(r"\+?99\.999\s*%|(?<![\d.])0\.02(?![\d.])", re.IGNORECASE)
    for path in source_files:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            failures.append(f"cannot read source file {path.relative_to(PROJECT_DIR).as_posix()}: {exc}")
            continue
        relative = path.relative_to(PROJECT_DIR).as_posix()
        if re.search(r"\bMath\s*\.\s*random\s*\(|\bDate\s*\.\s*now\s*\(", source):
            telemetry_scan["nondeterministic_hits"].append(relative)
            failures.append(f"nondeterministic Math.random/Date.now usage in {relative}")

        for match in number_pattern.finditer(source):
            number = match.group(0)
            if "99.999" in number:
                telemetry_scan["fictional_alignment_hits"].append({"file": relative, "literal": number})
                failures.append(f"fictional +99.999% telemetry is forbidden in {relative}")
                continue
            context = source[max(0, match.start() - 120):min(len(source), match.end() + 120)]
            if re.search(r"align|对齐", context, re.IGNORECASE):
                telemetry_scan["fictional_alignment_hits"].append({"file": relative, "literal": number})
                failures.append(f"fictional 0.02 alignment telemetry is forbidden in {relative}")
    report["source_scan"] = telemetry_scan


def numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def close(actual: Any, expected: float) -> bool:
    return numeric(actual) and math.isclose(float(actual), expected, rel_tol=0.0, abs_tol=1e-9)


def verify_model(report: dict[str, Any], failures: list[str], incomplete: list[str]) -> None:
    model_source_path = PROJECT_DIR / "src/model.ts"
    if not model_source_path.is_file():
        incomplete.append("missing project/src/model.ts; executable model formula check pending")
        return
    try:
        raw_model_source = model_source_path.read_text(encoding="utf-8")
        model_source = re.sub(r"\s+", "", raw_model_source)
    except (OSError, UnicodeError) as exc:
        failures.append(f"cannot read src/model.ts: {exc}")
        return

    check(re.search(r"export(?:const|function)policyMetrics\b", model_source) is not None,
          "src/model.ts must export policyMetrics", failures)
    check(re.search(r"proxyReward:1\+5\*q\b", model_source) is not None,
          "policyMetrics proxy reward formula must be 1 + 5q", failures)
    check(re.search(r"normalizedProxy:\(1\+5\*q\)/6\b", model_source) is not None,
          "policyMetrics normalized proxy formula must be (1 + 5q) / 6", failures)
    check(re.search(r"finishRate:1-q\b", model_source) is not None,
          "policyMetrics finish-rate formula must be 1 - q", failures)
    kind_re = re.escape(MODEL_KIND)
    check(re.search(rf"export\s+const\s+MODEL_KIND\s*=\s*['\"]{kind_re}['\"]", raw_model_source) is not None,
          "MODEL_KIND must label the policy mixture as illustrative, not paper data", failures)
    check(re.search(r"exportconstSPRING=", model_source) is not None,
          "src/model.ts must export the independent SPRING evidence", failures)
    for field, value in {
        "forceN": 10,
        "assumedStiffnessNPerM": 1000,
        "trueStiffnessNPerM": 500,
        "limitMm": 15,
        "predictedMm": 10,
        "observedMm": 20,
    }.items():
        check(re.search(rf"{field}:{value}(?:[,}}])", model_source) is not None,
              f"src/model.ts SPRING.{field} must equal {value}", failures)

    data = load_json(PROJECT_DIR / "model-data.json", "model-data.json", failures, incomplete)
    if not isinstance(data, dict):
        if data is not None:
            failures.append("model-data.json must contain an object")
        return
    check(data.get("kind") == MODEL_KIND, "model-data.json kind must retain its illustrative label", failures)

    policy = data.get("policy_model")
    if not isinstance(policy, dict):
        failures.append("model-data.json policy_model must be an object")
    else:
        normal, loop, samples = policy.get("normal"), policy.get("loop"), policy.get("samples")
        check(isinstance(normal, dict) and close(normal.get("proxy_reward"), 1) and close(normal.get("finish_rate"), 1),
              "q=0 baseline must have proxy reward 1 and finish rate 1", failures)
        check(isinstance(loop, dict) and close(loop.get("proxy_reward"), 6) and close(loop.get("finish_rate"), 0),
              "q=1 loop policy must have proxy reward 6 and finish rate 0", failures)
        if not isinstance(samples, list) or not samples:
            failures.append("model-data.json policy_model.samples must be a nonempty array")
        else:
            seen_q: set[float] = set()
            for index, sample in enumerate(samples, start=1):
                if not isinstance(sample, dict) or not numeric(sample.get("q")):
                    failures.append(f"policy model sample {index} needs a numeric q")
                    continue
                q = float(sample["q"])
                seen_q.add(q)
                check(0 <= q <= 1, f"policy model sample {index} q must be in [0, 1]", failures)
                proxy = 1 + 5 * q
                check(close(sample.get("proxyReward"), proxy), f"policy model sample {index} proxyReward must equal 1 + 5q", failures)
                check(close(sample.get("normalizedProxy"), proxy / 6), f"policy model sample {index} normalizedProxy must equal proxyReward / 6", failures)
                check(close(sample.get("finishRate"), 1 - q), f"policy model sample {index} finishRate must equal 1 - q", failures)
            check(0.0 in seen_q and 1.0 in seen_q, "policy model samples must cover q=0 and q=1", failures)

    spring = data.get("spring")
    if not isinstance(spring, dict):
        failures.append("model-data.json spring must be an object")
    else:
        force = spring.get("forceN")
        assumed = spring.get("assumedStiffnessNPerM")
        actual = spring.get("trueStiffnessNPerM")
        limit = spring.get("limitMm")
        valid_inputs = all(numeric(value) and value > 0 for value in (force, assumed, actual, limit))
        check(valid_inputs, "spring evidence needs positive numeric force, stiffnesses, and limit", failures)
        if valid_inputs:
            check(
                close(force, 10) and close(assumed, 1000) and close(actual, 500) and close(limit, 15),
                "spring evidence must use the approved 10 N, 1000/500 N/m, and 15 mm inputs",
                failures,
            )
            predicted = float(force) / float(assumed) * 1000
            observed = float(force) / float(actual) * 1000
            check(close(spring.get("predictedMm"), predicted) and close(predicted, 10),
                  "10 N / 1000 N/m must predict 10 mm", failures)
            check(close(spring.get("observedMm"), observed) and close(observed, 20),
                  "10 N / 500 N/m must yield 20 mm", failures)
            check(close(limit, 15) and predicted < float(limit) < observed,
                  "15 mm limit must lie between the 10 mm prediction and 20 mm observation", failures)

    report["numeric_model"] = {
        "kind": data.get("kind"),
        "policy_samples_checked": len(policy.get("samples", [])) if isinstance(policy, dict) and isinstance(policy.get("samples"), list) else 0,
        "spring_prediction_mm": spring.get("predictedMm") if isinstance(spring, dict) else None,
        "spring_observation_mm": spring.get("observedMm") if isinstance(spring, dict) else None,
        "spring_limit_mm": spring.get("limitMm") if isinstance(spring, dict) else None,
    }


def verify_captions_against_v1(failures: list[str], incomplete: list[str]) -> None:
    for platform in ("B站", "小红书"):
        v2_path = DELIVERY_DIR / platform / "captions.srt"
        v1_path = V1_DIR / platform / "captions.srt"
        if not v2_path.is_file() or not v1_path.is_file():
            incomplete.append(f"{platform} captions unavailable for unchanged-caption check")
            continue
        v2_text, v1_text = v2_path.read_bytes(), v1_path.read_bytes()
        check(v2_text == v1_text, f"{platform} captions differ from v1", failures)
        cue_count = len(re.findall(rb"(?m)^\d+\s*\r?$", v2_text))
        check(cue_count == 19, f"{platform} SRT must contain exactly 19 captions", failures)


def inspect_final_files(manifest: dict[str, Any] | None, incomplete: list[str]) -> dict[str, Any]:
    outputs = manifest.get("outputs") if isinstance(manifest, dict) else None
    result: dict[str, Any] = {}
    for key, label in (("bilibili", "landscape"), ("xiaohongshu", "portrait")):
        output = outputs.get(key) if isinstance(outputs, dict) else None
        relative = output.get("path") if isinstance(output, dict) else None
        path = safe_delivery_path(relative, f"delivery.json outputs.{key}", [])
        if path is None:
            result[label] = {"present": False, "path": relative}
            incomplete.append(f"final {label} media path is unavailable")
            continue
        present = path.is_file()
        result[label] = {"present": present, "path": relative}
        if not present:
            incomplete.append(f"final {label} MP4 is pending: {relative}")
    return result


def main() -> int:
    args = parse_args()
    failures: list[str] = []
    incomplete: list[str] = []
    report: dict[str, Any] = {"schema_version": 1, "checker": "EP04 v2 source verifier"}

    manifest = verify_manifest(report, failures, incomplete)
    verify_compositions(failures, incomplete)
    verify_timeline(failures, incomplete)
    verify_audio_timing(failures, incomplete)
    report["sfx_and_stems"] = verify_sfx_and_stems(failures, incomplete)
    verify_audio_reuse(report, failures, incomplete)
    verify_captions_against_v1(failures, incomplete)
    verify_source_code(report, failures, incomplete)
    verify_model(report, failures, incomplete)
    outputs = inspect_final_files(manifest, incomplete)

    source_missing = [
        message for message in incomplete
        if not message.startswith("final ")
    ]
    source_status = "FAIL" if failures else "INCOMPLETE" if source_missing else "PASS"
    final_status = "MEDIA_PRESENT_UNVALIDATED" if all(item.get("present") for item in outputs.values()) else "FINAL_FILES_PENDING"
    overall_status = "FAIL" if failures else "INCOMPLETE" if incomplete else "PASS"
    report.update({
        "status": overall_status,
        "source_status": source_status,
        "final_media_status": final_status,
        "final_files": outputs,
        "failures": failures,
        "incomplete": incomplete,
        "limitations": [
            "Source PASS confirms project invariants only; it does not validate encoded video or audio streams.",
            "FINAL_FILES_PENDING and MEDIA_PRESENT_UNVALIDATED are not media acceptance states.",
            "The motion ROI heuristic is evidence only; semantic labels remain in its crop and numeric differences do not prove meaningful motion.",
            "Human visual review, listening, and target-device playback remain separate acceptance steps.",
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
