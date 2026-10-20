#!/usr/bin/env python3
"""Check EP11 v02's authored source, timeline, captions, and PCM invariants.

This is a source/audio check only. It does not inspect encoded media or infer
visual, listening, audience, or device acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import wave
from pathlib import Path
from typing import Any, Callable


PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT.parent
MANIFEST_PATH = WORK / "delivery.json"
ORIGINAL_SOURCE = WORK.parent / "si-ep11-kintsugi-ink" / "source" / "script.md"
DURATION_SECONDS = 90
FPS = 60
TOTAL_FRAMES = DURATION_SECONDS * FPS
SAMPLE_RATE = 48_000
SAMPLES_PER_FRAME = SAMPLE_RATE // FPS
SAMPLES_PER_CHANNEL = DURATION_SECONDS * SAMPLE_RATE
SILENCE_FRAMES = (4860, 4890)
SHOT_RANGES = [
    (0, 600),
    (600, 1320),
    (1320, 2460),
    (2460, 3540),
    (3540, 4200),
    (4200, 4860),
    (4860, 4890),
    (4890, 5400),
]
SEGMENT_RANGES = [
    ("S01", 36, 540),
    ("S02", 600, 1260),
    ("S03", 1320, 2040),
    ("S04", 2100, 2760),
    ("S05", 2820, 3480),
    ("S06", 3540, 4140),
    ("S07", 4200, 4800),
    ("S08", 4890, 5400),
]
SOURCE_COMPONENTS = (
    "Root.tsx",
    "Film.tsx",
    "index.ts",
    "Effects.tsx",
    "CanyonScene.tsx",
    "HandScene.tsx",
)


class CheckFailure(ValueError):
    """A present artifact violates the declared project contract."""


class CheckPending(RuntimeError):
    """A required-for-completion artifact has not been integrated yet."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CheckFailure(f"cannot read {path.relative_to(WORK)}: {error}") from None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def han_count(value: str) -> int:
    return len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", value))


def visible_text(value: str) -> str:
    """Ignore punctuation differences between display copy and chunk breaks."""
    return "".join(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaffA-Za-z0-9]", value))


def caption_lines(chunk: str) -> list[str]:
    compact = re.sub(r"\s+", "", chunk)
    if not compact:
        raise CheckFailure("caption chunk is empty")
    # Split by the 13-character display limit; this is conservative for mixed
    # Latin/Chinese copy and leaves each rendered line within the safe bound.
    return [compact[index:index + 13] for index in range(0, len(compact), 13)]


def check_delivery(manifest: dict[str, Any]) -> dict[str, Any]:
    require(manifest.get("schema_version") == 1, "delivery.json schema_version must be 1")
    require(manifest.get("slug") == "si-ep11-kintsugi-ink-v02", "delivery slug mismatch")
    require(manifest.get("platforms") == ["xiaohongshu"], "delivery must target Xiaohongshu only")
    require(
        (manifest.get("duration_seconds"), manifest.get("fps"), manifest.get("total_frames"))
        == (DURATION_SECONDS, FPS, TOTAL_FRAMES),
        "delivery must be 90 seconds, 60fps, and 5400 frames",
    )
    outputs = manifest.get("outputs", {})
    require(set(outputs) == {"xiaohongshu"}, "outputs must contain only the Xiaohongshu edition")
    output = outputs["xiaohongshu"]
    require((output.get("width"), output.get("height")) == (2160, 3840), "output must be native 2160x3840")
    require(
        output.get("path") == "小红书/si-ep11-kintsugi-ink-v02-xiaohongshu-90s-portrait.mp4",
        "Xiaohongshu output path mismatch",
    )
    script = manifest.get("script", {})
    require(script.get("path") == "source/script.md", "delivery script path must be source/script.md")
    expected_hash = script.get("sha256")
    require(isinstance(expected_hash, str) and re.fullmatch(r"[0-9a-f]{64}", expected_hash) is not None,
            "delivery source script SHA-256 is missing or malformed")
    source_path = WORK / "source" / "script.md"
    require(source_path.is_file(), "raw source/script.md is missing")
    source_hash = sha256_file(source_path)
    require(source_hash == expected_hash, "source/script.md SHA-256 does not match delivery.json")
    require(ORIGINAL_SOURCE.is_file(), "v01 raw script is missing; cannot verify preserved source")
    original_hash = sha256_file(ORIGINAL_SOURCE)
    require(source_hash == original_hash, "v02 raw source differs from the preserved v01 script")
    require(
        manifest.get("audio", {}).get("master") == "project/public/audio/master.wav",
        "audio master path must be project/public/audio/master.wav",
    )
    report = manifest.get("visual_qc", {})
    require(report.get("required") is True, "visual_qc.required must remain true for this new work")
    require(
        report.get("reports", {}) == {"xiaohongshu": "review/visual-qc-xiaohongshu/report.json"},
        "visual QC report path must name the Xiaohongshu report",
    )
    return {
        "slug": manifest["slug"],
        "platforms": manifest["platforms"],
        "duration_seconds": DURATION_SECONDS,
        "fps": FPS,
        "total_frames": TOTAL_FRAMES,
        "dimensions": [2160, 3840],
        "raw_source_sha256": source_hash,
        "preserved_v01_source_sha256": original_hash,
    }


def check_timeline(segments: list[dict[str, Any]], timeline: dict[str, Any]) -> dict[str, Any]:
    require(
        (timeline.get("durationInFrames"), timeline.get("fps"), timeline.get("durationSeconds"))
        == (TOTAL_FRAMES, FPS, DURATION_SECONDS),
        "timeline clock must match 5400 frames at 60fps",
    )
    require(timeline.get("platforms") == ["xiaohongshu"], "timeline platform mismatch")
    shots = timeline.get("shots")
    require(isinstance(shots, list), "timeline shots must be a list")
    ranges = [(shot.get("startFrame"), shot.get("endFrame")) for shot in shots]
    require(ranges == SHOT_RANGES, f"timeline shot ranges must be {SHOT_RANGES}")
    require(ranges[0][0] == 0 and ranges[-1][1] == TOTAL_FRAMES, "shot ranges must cover the full film")
    require(all(left[1] == right[0] for left, right in zip(ranges, ranges[1:])), "timeline shots must be contiguous")
    require(timeline.get("absoluteSilence") == list(SILENCE_FRAMES), "timeline silence must be [4860,4890)")
    require(isinstance(segments, list), "segments.json must be a list")
    actual = [(item.get("id"), item.get("startFrame"), item.get("endFrame")) for item in segments]
    require(actual == SEGMENT_RANGES, f"segments.json must match the eight locked intervals: {SEGMENT_RANGES}")
    require(timeline.get("segments") == segments, "timeline.json segments differ from segments.json")
    return {
        "shot_ranges": ranges,
        "segment_ids": [item[0] for item in SEGMENT_RANGES],
        "segment_ranges": SEGMENT_RANGES,
        "absolute_silence_frames": list(SILENCE_FRAMES),
    }


def check_source_captions(segments: list[dict[str, Any]]) -> dict[str, Any]:
    chunk_count = 0
    max_han = 0
    for segment in segments:
        display = segment.get("display_subtitle")
        chunks = segment.get("chunks")
        require(isinstance(display, str) and display.strip(), f"{segment.get('id')} display subtitle is empty")
        require(isinstance(chunks, list) and chunks, f"{segment.get('id')} has no caption chunks")
        require(
            visible_text(display) == visible_text("".join(chunks)),
            f"{segment.get('id')} caption chunks do not reproduce its display subtitle",
        )
        require(
            isinstance(segment.get("tts_phonetic_text"), str) and segment["tts_phonetic_text"].strip(),
            f"{segment.get('id')} phonetic narration text is missing",
        )
        for chunk in chunks:
            lines = caption_lines(chunk)
            require(len(lines) <= 2, f"caption chunk needs more than two lines: {chunk!r}")
            require(all(han_count(line) <= 13 for line in lines), f"caption line exceeds 13 Chinese characters: {chunk!r}")
            max_han = max(max_han, *(han_count(line) for line in lines))
            chunk_count += 1
    return {
        "segments": len(segments),
        "source_caption_chunks": chunk_count,
        "max_chinese_characters_per_line": 13,
        "observed_max_chinese_characters_per_line": max_han,
        "max_lines_per_chunk": 2,
    }


def check_composition() -> dict[str, Any]:
    source_root = PROJECT / "src"
    if not source_root.is_dir():
        raise CheckPending("project/src is not integrated yet")
    missing = [name for name in SOURCE_COMPONENTS if not (source_root / name).is_file()]
    if missing:
        raise CheckPending(f"composition files are pending integration: {', '.join(missing)}")
    files = sorted(path for path in source_root.rglob("*") if path.is_file() and path.suffix in {".ts", ".tsx"})
    source = {path.name: path.read_text(encoding="utf-8") for path in files}
    combined = "\n".join(source.values())
    require(re.search(r"\bMath\.random\s*\(", combined) is None, "frame source must not call Math.random()")
    require(re.search(r"\bDate\.now\s*\(", combined) is None, "frame source must not call Date.now()")
    require(re.search(r"\buseFrame\s*\(", combined) is None, "Three.js motion must not use useFrame()")
    require(re.search(r"\brequestAnimationFrame\s*\(", combined) is None,
            "frame source must not depend on requestAnimationFrame()")
    require("useCurrentFrame" in combined, "composition must receive its time from Remotion useCurrentFrame")
    for legacy in ("Terrain.tsx", "Eternity.tsx"):
        require(not (source_root / legacy).exists(), f"obsolete scene file remains: src/{legacy}")
    require(not (PROJECT / "telemetry-lexicon.json").exists(), "obsolete static telemetry lexicon remains")
    require(re.search(r"from\s+[\"'](?:\./|\.\./)*Terrain(?:\.tsx)?[\"']", combined) is None,
            "obsolete Terrain scene import remains")
    require(re.search(r"from\s+[\"'](?:\./|\.\./)*Eternity(?:\.tsx)?[\"']", combined) is None,
            "obsolete Eternity scene import remains")
    for component in ("CanyonScene.tsx", "HandScene.tsx"):
        text = source[component]
        require(
            re.search(r"import\s*\{[^}]*\bThreeCanvas\b[^}]*\}\s*from\s*[\"']@remotion/three[\"']", text, re.S)
            is not None,
            f"{component} must import ThreeCanvas from @remotion/three",
        )
        require(re.search(r"<ThreeCanvas\b", text) is not None,
                f"{component} must render the supported Remotion ThreeCanvas wrapper")
    consumers = source["Root.tsx"] + "\n" + source["Film.tsx"]
    require("CanyonScene" in consumers, "Root/Film must mount CanyonScene")
    require("HandScene" in consumers, "Root/Film must mount HandScene")
    require(
        re.search(r"\b(?:const|let|var)\s+(?:HUD|TELEMETRY)(?:_[A-Z0-9]+)*\s*=", combined)
        is None,
        "obsolete static HUD/telemetry constant array remains",
    )
    stale_terms = [
        "BIOLOGICAL AGE INDEX",
        "PORCELAIN FRACTURE ENTROPY",
        "KINTSUGI CELLULAR REPROGRAMMING",
        "MÖBIUS EQUILIBRIUM LOCKED",
        "KINTSUGI SEALED",
        "DIGITAL KINTSUGI OF TIME",
        "SENESCENCE BASIN",
    ]
    found = [term for term in stale_terms if term in combined]
    require(not found, f"obsolete v01 HUD copy remains in source: {found}")
    return {
        "typescript_files": [path.relative_to(PROJECT).as_posix() for path in files],
        "scene_modules": ["src/CanyonScene.tsx", "src/HandScene.tsx"],
        "three_canvas": "@remotion/three ThreeCanvas in both replacement scenes",
        "frame_source": "Remotion useCurrentFrame; no Math.random, Date.now, useFrame, or requestAnimationFrame",
        "obsolete_scenes": "Terrain/Eternity absent",
        "static_hud_constants": "legacy constants and v01 telemetry copy absent",
    }


def check_events(required: bool) -> dict[str, Any]:
    path = PROJECT / "audio-events.json"
    if not path.is_file():
        if required:
            raise CheckFailure("required project/audio-events.json is missing")
        raise CheckPending("project/audio-events.json is pending audio integration")
    events = read_json(path)
    require(events.get("fps") == FPS, "audio-events fps must be 60")
    require(events.get("absoluteSilence") == list(SILENCE_FRAMES), "audio-events silence must be [4860,4890)")
    event_list = events.get("events")
    require(isinstance(event_list, list), "audio-events.events must be a list")
    seen_ids: set[str] = set()
    release_drops = []
    for event in event_list:
        frame = event.get("frame")
        event_id = event.get("id")
        require(isinstance(event_id, str) and event_id not in seen_ids, f"missing or duplicate SFX id: {event_id}")
        seen_ids.add(event_id)
        require(type(frame) is int and 0 <= frame < TOTAL_FRAMES, f"invalid SFX frame for {event_id}")
        sample = frame * SAMPLES_PER_FRAME
        require(event.get("sample") == sample, f"SFX sample position mismatch for {event_id}")
        duration = event.get("durationSeconds")
        require(isinstance(duration, (int, float)) and duration > 0, f"invalid SFX duration for {event_id}")
        end_sample = sample + round(duration * SAMPLE_RATE)
        require(end_sample <= SAMPLES_PER_CHANNEL, f"SFX event {event_id} extends beyond the 90-second master")
        if event_id == "gold_drop":
            require(frame == SILENCE_FRAMES[1], "gold_drop must begin at frame 4890")
            require(sample == SILENCE_FRAMES[1] * SAMPLES_PER_FRAME, "gold_drop sample must begin at 3,912,000")
            release_drops.append(event_id)
        else:
            require(frame < SILENCE_FRAMES[0] and end_sample <= SILENCE_FRAMES[0] * SAMPLES_PER_FRAME,
                    f"SFX event {event_id} overlaps absolute silence")
    require(len(release_drops) == 1, "exactly one gold_drop event must begin at frame 4890")
    return {
        "event_count": len(event_list),
        "absolute_silence_frames": list(SILENCE_FRAMES),
        "release_drop_frame": SILENCE_FRAMES[1],
        "release_drop_sample": SILENCE_FRAMES[1] * SAMPLES_PER_FRAME,
    }


def check_timed_captions(segments: list[dict[str, Any]], required: bool) -> dict[str, Any]:
    path = PROJECT / "audio-timing.json"
    if not path.is_file():
        if required:
            raise CheckFailure("required project/audio-timing.json is missing")
        raise CheckPending("audio timing and measured captions are pending audio integration")
    timing = read_json(path)
    captions = timing.get("captions")
    if timing.get("status") == "PREVIEW_ONLY" or not captions:
        if required:
            raise CheckFailure("audio timing is preview-only or has no timed captions")
        raise CheckPending("audio timing is preview-only or has no timed captions")
    require(isinstance(captions, list), "audio-timing.json captions must be a list")
    require(timing.get("samplesPerChannel") == SAMPLES_PER_CHANNEL, "audio timing must describe a 90-second master")
    require(timing.get("sampleRate") == SAMPLE_RATE, "audio timing sample rate must be 48000")
    timing_master = timing.get("master", {})
    master_path = WORK / "project/public/audio/master.wav"
    if master_path.is_file() and timing_master.get("sha256"):
        require(timing_master["sha256"] == sha256_file(master_path),
                "audio-timing.json master SHA-256 differs from the current PCM master")
    source_hashes = timing.get("sourceHashes", {})
    segments_path = PROJECT / "segments.json"
    events_path = PROJECT / "audio-events.json"
    if source_hashes.get("segmentsJson"):
        require(source_hashes["segmentsJson"] == sha256_file(segments_path),
                "audio-timing.json was built from different segments.json")
    if source_hashes.get("audioEventsJson") and events_path.is_file():
        require(source_hashes["audioEventsJson"] == sha256_file(events_path),
                "audio-timing.json was built from different audio-events.json")
    silence = timing.get("absoluteSilence", {})
    require(
        (silence.get("startFrame"), silence.get("endFrameExclusive")) == SILENCE_FRAMES,
        "audio-timing.json silence frame interval mismatch",
    )
    require(
        (silence.get("startSample"), silence.get("endSampleExclusive"))
        == (SILENCE_FRAMES[0] * SAMPLES_PER_FRAME, SILENCE_FRAMES[1] * SAMPLES_PER_FRAME),
        "audio-timing.json silence sample interval mismatch",
    )
    expected_ids = [segment["id"] for segment in segments]
    measured = timing.get("segments", [])
    if measured:
        require([item.get("id") for item in measured] == expected_ids,
                "audio-timing.json must list measured S01 through S08 in order")
    by_id: dict[str, list[dict[str, Any]]] = {segment_id: [] for segment_id in expected_ids}
    previous_start = -1
    for caption in captions:
        segment_id = caption.get("segmentId")
        require(segment_id in by_id, f"caption has unknown segmentId: {segment_id}")
        start, end = caption.get("startFrame"), caption.get("endFrame")
        require(
            type(start) is int and type(end) is int and 0 <= start < end <= TOTAL_FRAMES,
            f"invalid timed caption interval for {segment_id}",
        )
        require(start >= previous_start, "timed captions are not in timeline order")
        previous_start = start
        segment = next(item for item in segments if item["id"] == segment_id)
        require(start >= segment["startFrame"] and end <= segment["endFrame"],
                f"caption falls outside authored segment {segment_id}")
        require(not (start < SILENCE_FRAMES[1] and end > SILENCE_FRAMES[0]),
                f"caption overlaps absolute silence: {segment_id}")
        text = caption.get("text")
        lines = text.splitlines() if isinstance(text, str) else []
        require(1 <= len(lines) <= 2, f"caption line count exceeds two for {segment_id}")
        require(all(han_count(line) <= 13 for line in lines), f"caption line exceeds 13 Chinese characters: {text!r}")
        by_id[segment_id].append(caption)
    for segment in segments:
        actual = [item.get("text") for item in by_id[segment["id"]]]
        expected = ["\n".join(caption_lines(chunk)) for chunk in segment["chunks"]]
        require(actual == expected, f"timed captions do not match source chunks for {segment['id']}")
    return {"timed_caption_count": len(captions), "alignment_claim": timing.get("captionTimingMethod")}


def check_master(manifest: dict[str, Any], required: bool) -> dict[str, Any]:
    path = WORK / manifest["audio"]["master"]
    if not path.is_file():
        if required:
            raise CheckFailure(f"required PCM master is missing: {manifest['audio']['master']}")
        raise CheckPending("PCM master is pending audio integration")
    try:
        with wave.open(str(path), "rb") as audio:
            channels, rate, width, count = (
                audio.getnchannels(), audio.getframerate(), audio.getsampwidth(), audio.getnframes()
            )
            require(
                (channels, rate, width, count) == (2, SAMPLE_RATE, 2, SAMPLES_PER_CHANNEL),
                "PCM master must be stereo 48kHz signed 16-bit with 4,320,000 samples per channel",
            )
            audio.setpos(SILENCE_FRAMES[0] * SAMPLES_PER_FRAME)
            silence = audio.readframes((SILENCE_FRAMES[1] - SILENCE_FRAMES[0]) * SAMPLES_PER_FRAME)
            expected_bytes = (SILENCE_FRAMES[1] - SILENCE_FRAMES[0]) * SAMPLES_PER_FRAME * channels * width
            require(len(silence) == expected_bytes, "PCM master silence window is truncated")
            require(not any(silence), "PCM master is not exactly zero throughout frames [4860,4890)")
    except (OSError, wave.Error) as error:
        raise CheckFailure(f"could not read PCM master: {error}") from None
    digest = sha256_file(path)
    declared_sha = manifest.get("audio", {}).get("master_sha256")
    if declared_sha:
        require(declared_sha == digest, "PCM master SHA-256 differs from delivery.json")
    return {
        "path": path.relative_to(WORK).as_posix(),
        "sha256": digest,
        "channels": channels,
        "sample_rate": rate,
        "sample_width_bytes": width,
        "samples_per_channel": count,
        "absolute_silence_frames": list(SILENCE_FRAMES),
        "exact_zero": True,
    }


def run_check(checks: list[dict[str, Any]], name: str, function: Callable[[], Any]) -> None:
    try:
        checks.append({"name": name, "result": "PASS", "detail": function()})
    except CheckPending as error:
        checks.append({"name": name, "result": "PENDING", "detail": str(error)})
    except (CheckFailure, OSError, UnicodeError, ValueError, TypeError, KeyError, wave.Error) as error:
        checks.append({"name": name, "result": "FAIL", "detail": str(error)})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-audio",
        action="store_true",
        help="Treat missing SFX mapping, measured captions, or PCM master as a failure.",
    )
    args = parser.parse_args()
    checks: list[dict[str, Any]] = []
    try:
        manifest = read_json(MANIFEST_PATH)
        timeline = read_json(PROJECT / "timeline.json")
        segments = read_json(PROJECT / "segments.json")
    except CheckFailure as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, ensure_ascii=False, indent=2))
        return 1

    run_check(checks, "delivery_and_preserved_source", lambda: check_delivery(manifest))
    run_check(checks, "timeline_and_locked_segments", lambda: check_timeline(segments, timeline))
    run_check(checks, "caption_source_and_mobile_lines", lambda: check_source_captions(segments))
    run_check(checks, "composition_and_frame_determinism", check_composition)
    run_check(checks, "sample_locked_audio_events", lambda: check_events(args.require_audio))
    run_check(checks, "measured_timed_captions", lambda: check_timed_captions(segments, args.require_audio))
    run_check(checks, "pcm_master_and_silence", lambda: check_master(manifest, args.require_audio))
    failed = any(item["result"] == "FAIL" for item in checks)
    pending = any(item["result"] == "PENDING" for item in checks)
    result = {
        "status": "FAIL" if failed else ("INCOMPLETE" if pending else "PASS"),
        "scope": "Source and PCM invariants only; no encoded-media, visual, listening, audience, or device acceptance is inferred.",
        "checks": checks,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if failed else (2 if pending else 0)


if __name__ == "__main__":
    raise SystemExit(main())
