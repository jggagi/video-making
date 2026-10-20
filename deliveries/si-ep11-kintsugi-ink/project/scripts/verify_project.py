#!/usr/bin/env python3
"""Check EP11 source invariants and, when present, its built audio artifacts."""

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
EXPECTED_SHOTS = [(0, 1320), (1320, 2820), (2820, 4380), (4380, 5400)]
EXPECTED_TELEMETRY = [
    "BIOLOGICAL AGE INDEX",
    "PORCELAIN FRACTURE ENTROPY",
    "KINTSUGI CELLULAR REPROGRAMMING",
    "MÖBIUS EQUILIBRIUM LOCKED",
    "KINTSUGI SEALED",
    "DIGITAL KINTSUGI OF TIME",
    "SENESCENCE BASIN",
]
SILENCE_FRAMES = (4860, 4890)
SAMPLE_RATE = 48_000
SAMPLES_PER_FRAME = SAMPLE_RATE // 60
SAMPLES_PER_CHANNEL = 90 * SAMPLE_RATE


class CheckFailure(ValueError):
    """An authored project invariant does not match its declared contract."""


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


def visible_text(value: str) -> str:
    """Keep letters, digits, and CJK so punctuation differences remain harmless."""
    return "".join(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", value))


def caption_text(chunk: str) -> str:
    clean = re.sub(r"\s+", "", chunk)
    if len(clean) <= 13:
        return clean
    if len(clean) <= 26:
        return clean[:13] + "\n" + clean[13:]
    raise CheckFailure(f"source caption chunk exceeds two 13-character lines: {chunk!r}")


def check_delivery(manifest: dict[str, Any]) -> dict[str, Any]:
    require(manifest.get("schema_version") == 1, "delivery.json schema_version must be 1")
    require(manifest.get("slug") == "si-ep11-kintsugi-ink", "delivery slug mismatch")
    require(manifest.get("platforms") == ["xiaohongshu"], "delivery must target Xiaohongshu only")
    require(
        (manifest.get("duration_seconds"), manifest.get("fps"), manifest.get("total_frames"))
        == (90, 60, 5400),
        "delivery must be 90 seconds, 60fps, and 5400 frames",
    )
    output = manifest.get("outputs", {}).get("xiaohongshu", {})
    require(
        (output.get("width"), output.get("height")) == (2160, 3840),
        "Xiaohongshu output must be native 2160x3840",
    )
    require(
        output.get("path") == "小红书/si-ep11-kintsugi-ink-xiaohongshu-90s-portrait.mp4",
        "Xiaohongshu output path mismatch",
    )
    require(
        manifest.get("script", {}).get("path") == "source/script.md",
        "delivery script path must be source/script.md",
    )
    script_path = WORK / "source" / "script.md"
    expected_hash = manifest.get("script", {}).get("sha256")
    require(isinstance(expected_hash, str) and len(expected_hash) == 64, "script SHA-256 is missing")
    require(sha256_file(script_path) == expected_hash, "source/script.md SHA-256 does not match delivery.json")
    require(
        manifest.get("audio", {}).get("master") == "project/public/audio/master.wav",
        "audio master path must be project/public/audio/master.wav",
    )
    report = manifest.get("visual_qc", {}).get("reports", {})
    require(
        report.get("xiaohongshu") == "review/visual-qc-xiaohongshu/report.json",
        "visual QC report path mismatch",
    )
    return {
        "slug": manifest["slug"],
        "platforms": manifest["platforms"],
        "duration_seconds": manifest["duration_seconds"],
        "fps": manifest["fps"],
        "total_frames": manifest["total_frames"],
        "dimensions": [output["width"], output["height"]],
        "source_script_sha256": expected_hash,
    }


def check_timeline(segments: list[dict[str, Any]], timeline: dict[str, Any], events: dict[str, Any]) -> dict[str, Any]:
    require(
        (timeline.get("durationInFrames"), timeline.get("fps"), timeline.get("durationSeconds"))
        == (5400, 60, 90),
        "timeline clock must match 5400 frames at 60fps",
    )
    require(timeline.get("platforms") == ["xiaohongshu"], "timeline platform mismatch")
    shots = timeline.get("shots")
    require(isinstance(shots, list), "timeline shots must be a list")
    ranges = [(shot.get("startFrame"), shot.get("endFrame")) for shot in shots]
    require(ranges == EXPECTED_SHOTS, f"timeline shot ranges must be {EXPECTED_SHOTS}")
    require(
        all(left[1] == right[0] for left, right in zip(ranges, ranges[1:])),
        "timeline shots must be contiguous",
    )
    require(
        timeline.get("absoluteSilence") == list(SILENCE_FRAMES),
        "timeline absolute silence must be frames [4860,4890)",
    )
    require(
        events.get("absoluteSilence") == list(SILENCE_FRAMES),
        "sfx_events absolute silence must be frames [4860,4890)",
    )
    require(events.get("fps") == 60, "sfx_events fps must be 60")
    require(events.get("sampleRate") == SAMPLE_RATE, "sfx_events sample rate must be 48000")
    require(events.get("samplesPerFrame") == SAMPLES_PER_FRAME, "sfx_events samplesPerFrame must be 800")
    for event in events.get("events", []):
        frame = event.get("frame")
        require(isinstance(frame, int) and 0 <= frame < 5400, f"invalid SFX frame for {event.get('id')}")
        require(
            event.get("sample") == frame * SAMPLES_PER_FRAME,
            f"SFX sample position mismatch for {event.get('id')}",
        )
    require(
        isinstance(segments, list) and [item.get("id") for item in segments] == [f"S{i:02}" for i in range(1, 9)],
        "segments.json must contain S01 through S08 in order",
    )
    require(
        timeline.get("segments") == segments,
        "timeline.json segments differ from segments.json",
    )
    for segment in segments:
        start, end = segment.get("startFrame"), segment.get("endFrame")
        require(
            isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= 5400,
            f"invalid segment frame interval for {segment.get('id')}",
        )
    return {
        "shot_ranges": ranges,
        "segment_ids": [item["id"] for item in segments],
        "absolute_silence_frames": list(SILENCE_FRAMES),
        "sfx_event_count": len(events.get("events", [])),
    }


def check_source_captions(segments: list[dict[str, Any]]) -> dict[str, Any]:
    chunk_count = 0
    for segment in segments:
        chunks = segment.get("chunks")
        display = segment.get("display_subtitle")
        require(isinstance(display, str) and bool(display.strip()), f"{segment['id']} display subtitle is empty")
        require(isinstance(chunks, list) and chunks, f"{segment['id']} has no caption chunks")
        require(
            visible_text(display) == visible_text("".join(chunks)),
            f"{segment['id']} caption chunks do not reproduce its display subtitle",
        )
        require(
            isinstance(segment.get("tts_phonetic_text"), str) and bool(segment["tts_phonetic_text"].strip()),
            f"{segment['id']} phonetic narration text is missing",
        )
        for chunk in chunks:
            caption_text(chunk)
            chunk_count += 1
    return {
        "segments": len(segments),
        "source_caption_chunks": chunk_count,
        "max_lines": 2,
        "max_characters_per_line": 13,
    }


def smooth(value: float) -> float:
    t = min(1.0, max(0.0, value))
    return t * t * (3 - 2 * t)


def check_source_and_telemetry() -> dict[str, Any]:
    source_files = sorted((PROJECT / "src").rglob("*"))
    typescript_files = [path for path in source_files if path.is_file() and path.suffix in {".ts", ".tsx"}]
    require(bool(typescript_files), "no TypeScript composition files found")
    source_text = "\n".join(path.read_text(encoding="utf-8") for path in typescript_files)
    require(re.search(r"\bMath\.random\s*\(", source_text) is None, "composition must not call Math.random()")
    require(re.search(r"\bDate\.now\s*\(", source_text) is None, "composition must not call Date.now()")

    lexicon = read_json(PROJECT / "telemetry-lexicon.json")
    require(lexicon.get("constants") == EXPECTED_TELEMETRY, "telemetry lexicon constants or spelling changed")
    film = (PROJECT / "src" / "Film.tsx").read_text(encoding="utf-8")
    compact = re.sub(r"\s+", "", film)
    age_formula = "constage=f<1320?20+58.5*smooth(f/1320):78.5-56.5*smooth((f-2820)/1500);"
    entropy_formula = "constentropy=f<1320?89.4*smooth(f/1320):89.4*(1-smooth((f-1740)/1800));"
    require(age_formula in compact, "source age telemetry formula does not match the approved trajectory")
    require(entropy_formula in compact, "source entropy telemetry formula does not match the approved trajectory")
    require("age.toFixed(1)" in compact, "age telemetry must display one decimal place")
    require("entropy.toFixed(f>=3540?3:1)" in compact, "entropy must display three decimals at its endpoint")
    for constant in EXPECTED_TELEMETRY[:5]:
        require(constant in film, f"source telemetry spelling is missing: {constant}")

    def age(frame: int) -> float:
        if frame < 1320:
            return 20 + 58.5 * smooth(frame / 1320)
        return 78.5 - 56.5 * smooth((frame - 2820) / 1500)

    def entropy(frame: int) -> float:
        if frame < 1320:
            return 89.4 * smooth(frame / 1320)
        return 89.4 * (1 - smooth((frame - 1740) / 1800))

    age_points = {str(frame): round(age(frame), 1) for frame in (0, 1320, 4320)}
    entropy_points = {str(frame): round(entropy(frame), 3) for frame in (0, 1320, 3540)}
    require(list(age_points.values()) == [20.0, 78.5, 22.0], f"unexpected age trajectory: {age_points}")
    require(list(entropy_points.values()) == [0.0, 89.4, 0.0], f"unexpected entropy trajectory: {entropy_points}")
    require(f"{entropy(3540):.3f}" == "0.000", "entropy endpoint must render as 0.000")

    subtitle_marker = "data-subtitlestyle={{position:'absolute',left:65,top:1384,width:838,fontSize:49,lineHeight:'52px'"
    require(subtitle_marker in compact, "subtitle geometry/style differs from the approved portrait layout")
    hud_marker = '<textkey={i}x="65"y={195+i*31}'
    require(hud_marker in compact, "telemetry HUD anchor differs from the approved top safe area")
    require('fontSize="30"' in compact, "telemetry HUD font size changed")

    canvas_width, canvas_height = 1080, 1920
    safe = {
        "left": canvas_width * 0.06,
        "right": canvas_width * 0.86,
        "top": canvas_height * 0.08,
        "bottom": canvas_height * 0.78,
    }
    subtitle_box = {"left": 65, "right": 65 + 838, "top": 1384, "bottom": 1384 + 2 * 52}
    require(
        subtitle_box["left"] >= safe["left"]
        and subtitle_box["right"] <= safe["right"]
        and subtitle_box["top"] >= safe["top"]
        and subtitle_box["bottom"] <= safe["bottom"],
        "two-line subtitle box exceeds the critical safe area",
    )
    hud_baselines = [195, 195 + 31, 195 + 62]
    require(
        all(canvas_height * 0.09 <= y <= canvas_height * 0.14 for y in hud_baselines),
        "telemetry HUD baselines exceed the approved top band",
    )
    require(65 >= safe["left"] and 65 + 838 <= safe["right"], "telemetry HUD width exceeds the critical safe area")
    return {
        "typescript_files": [str(path.relative_to(PROJECT)) for path in typescript_files],
        "determinism": "no Math.random() or Date.now() calls",
        "age_trajectory": age_points,
        "entropy_trajectory": entropy_points,
        "telemetry_constants": EXPECTED_TELEMETRY,
        "logical_subtitle_box": subtitle_box,
        "logical_safe_area": safe,
        "hud_baselines": hud_baselines,
    }


def check_timed_captions(segments: list[dict[str, Any]], timing: dict[str, Any], required: bool) -> dict[str, Any]:
    captions = timing.get("captions")
    if timing.get("status") == "PREVIEW_ONLY" or not captions:
        if required:
            raise CheckFailure("audio timing is still PREVIEW_ONLY or has no timed captions")
        return {"skipped": True, "reason": "audio build has not produced timed captions"}
    require(isinstance(captions, list), "audio-timing.json captions must be a list")
    require(timing.get("status") != "PREVIEW_ONLY", "audio timing must not be preview-only")
    expected_ids = [segment["id"] for segment in segments]
    measured_segments = timing.get("segments", [])
    require(
        [item.get("id") for item in measured_segments] == expected_ids,
        "audio-timing.json must contain measured S01 through S08 in order",
    )
    source_by_id = {segment["id"]: segment for segment in segments}
    by_id: dict[str, list[dict[str, Any]]] = {segment_id: [] for segment_id in expected_ids}
    previous_start = -1
    for caption in captions:
        require(isinstance(caption, dict), "each timed caption must be an object")
        segment_id = caption.get("segmentId")
        require(segment_id in by_id, f"caption has unknown segmentId: {segment_id}")
        start, end = caption.get("startFrame"), caption.get("endFrame")
        require(
            isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= 5400,
            f"invalid timed caption interval for {segment_id}",
        )
        require(start >= previous_start, "timed captions are not in timeline order")
        previous_start = start
        require(
            end <= source_by_id[segment_id]["endFrame"] and start >= source_by_id[segment_id]["startFrame"],
            f"timed caption falls outside authored segment {segment_id}",
        )
        require(
            not (start < SILENCE_FRAMES[1] and end > SILENCE_FRAMES[0]),
            f"caption overlaps absolute silence: {segment_id} [{start},{end})",
        )
        text = caption.get("text")
        require(isinstance(text, str) and bool(text.strip()), f"caption text is empty for {segment_id}")
        lines = text.splitlines()
        require(1 <= len(lines) <= 2 and all(len(line) <= 13 for line in lines), f"caption line limit exceeded: {text!r}")
        by_id[segment_id].append(caption)
    count = 0
    for segment in segments:
        actual = [caption["text"] for caption in by_id[segment["id"]]]
        expected = [caption_text(chunk) for chunk in segment["chunks"]]
        require(actual == expected, f"timed captions do not match {segment['id']} source chunks")
        count += len(actual)
    return {
        "skipped": False,
        "timed_caption_count": count,
        "alignment_claim": timing.get("captionTimingMethod"),
    }


def check_master(manifest: dict[str, Any], timing: dict[str, Any], required: bool) -> dict[str, Any]:
    raw_master = manifest.get("audio", {}).get("master", "")
    master = WORK / raw_master
    if not master.is_file():
        if required:
            raise CheckFailure(f"required PCM master is missing: {raw_master}")
        return {"skipped": True, "reason": "audio master has not been built"}
    with wave.open(str(master), "rb") as audio:
        channels = audio.getnchannels()
        rate = audio.getframerate()
        width = audio.getsampwidth()
        frame_count = audio.getnframes()
        require(
            (channels, rate, width, frame_count) == (2, SAMPLE_RATE, 2, SAMPLES_PER_CHANNEL),
            "PCM master must be stereo 48kHz signed 16-bit with 4,320,000 samples per channel",
        )
        audio.setpos(SILENCE_FRAMES[0] * SAMPLES_PER_FRAME)
        silence = audio.readframes((SILENCE_FRAMES[1] - SILENCE_FRAMES[0]) * SAMPLES_PER_FRAME)
        require(len(silence) == 30 * SAMPLES_PER_FRAME * channels * width, "PCM master silence window is truncated")
        require(not any(silence), "PCM master is not exactly zero throughout frames [4860,4890)")
    require(
        timing.get("absoluteSilence", {}).get("startFrame") == SILENCE_FRAMES[0]
        and timing.get("absoluteSilence", {}).get("endFrameExclusive") == SILENCE_FRAMES[1],
        "audio-timing.json silence frame interval mismatch",
    )
    require(
        timing.get("samplesPerChannel") == SAMPLES_PER_CHANNEL
        and timing.get("sampleRate") == SAMPLE_RATE,
        "audio-timing.json PCM duration or sample rate mismatch",
    )
    digest = sha256_file(master)
    declared_sha = manifest.get("audio", {}).get("master_sha256")
    if declared_sha:
        require(declared_sha == digest, "PCM master SHA-256 differs from delivery.json")
    declared_timing_sha = timing.get("master", {}).get("sha256")
    if declared_timing_sha:
        require(declared_timing_sha == digest, "PCM master SHA-256 differs from audio-timing.json")
    return {
        "skipped": False,
        "path": str(master.relative_to(WORK)),
        "sha256": digest,
        "channels": channels,
        "sample_rate": rate,
        "sample_width_bytes": width,
        "samples_per_channel": frame_count,
        "absolute_silence_frames": list(SILENCE_FRAMES),
        "exact_zero": True,
    }


def run_check(checks: list[dict[str, Any]], name: str, function: Callable[[], Any]) -> None:
    try:
        detail = function()
        if isinstance(detail, dict) and detail.get("skipped"):
            checks.append({"name": name, "result": "SKIPPED", "detail": detail})
        else:
            checks.append({"name": name, "result": "PASS", "detail": detail})
    except (CheckFailure, OSError, ValueError, TypeError, KeyError, wave.Error) as error:
        checks.append({"name": name, "result": "FAIL", "detail": str(error)})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-audio",
        action="store_true",
        help="Fail unless the PCM master, finalized timing, and measured captions exist.",
    )
    args = parser.parse_args()
    checks: list[dict[str, Any]] = []
    try:
        manifest = read_json(MANIFEST_PATH)
        timeline = read_json(PROJECT / "timeline.json")
        segments = read_json(PROJECT / "segments.json")
        events = read_json(PROJECT / "sfx_events.json")
        timing = read_json(PROJECT / "audio-timing.json")
    except CheckFailure as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, ensure_ascii=False, indent=2))
        return 1

    run_check(checks, "delivery", lambda: check_delivery(manifest))
    run_check(checks, "timeline_and_events", lambda: check_timeline(segments, timeline, events))
    run_check(checks, "source_caption_chunks", lambda: check_source_captions(segments))
    run_check(checks, "composition_and_telemetry", check_source_and_telemetry)
    run_check(checks, "timed_captions", lambda: check_timed_captions(segments, timing, args.require_audio))
    run_check(checks, "pcm_master", lambda: check_master(manifest, timing, args.require_audio))

    failed = any(check["result"] == "FAIL" for check in checks)
    skipped = any(check["result"] == "SKIPPED" for check in checks)
    result = {
        "status": "FAIL" if failed else ("INCOMPLETE" if skipped else "PASS"),
        "scope": "Authored source and PCM invariants only; this is not encoded-media, listening, or device acceptance.",
        "checks": checks,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
