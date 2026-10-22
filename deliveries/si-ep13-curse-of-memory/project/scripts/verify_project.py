#!/usr/bin/env python3
"""Verify EP13 source, timing decisions, captions, audio layout, and 2D constraints.

The report distinguishes failures from checks that cannot yet run because a
rendered timing file or final PCM master is not present.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import wave
from pathlib import Path
from typing import Any, Callable

PROJECT = Path(__file__).resolve().parents[1]
DELIVERY = PROJECT.parent
REPO = PROJECT.parents[2]
REPORT = DELIVERY / "review" / "source-check.json"
TOTAL_FRAMES = 5_400
FPS = 60
SAMPLE_RATE = 48_000
SAMPLES_PER_FRAME = 800
SAMPLES_PER_CHANNEL = 4_320_000
SILENCE_START = 3_888_000
SILENCE_END = 3_912_000
EXPECTED_IDS = [f"S{i:02d}" for i in range(1, 9)]

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
        add("FAIL", check_id, f"required project file is missing: {exc.filename}")
    except (OSError, ValueError, KeyError, TypeError, AttributeError, json.JSONDecodeError) as exc:
        add("FAIL", check_id, f"{type(exc).__name__}: {exc}")


def check_script_and_segments() -> tuple[str, str, Any]:
    source_path = DELIVERY / "source" / "script.md"
    segment_path = PROJECT / "segments.json"
    adapted_path = PROJECT / "adapted-script.md"
    delivery_path = DELIVERY / "delivery.json"
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    delivery = load_json(delivery_path)
    expected_hash = delivery.get("script", {}).get("sha256")
    if source_hash != expected_hash:
        raise ValueError(f"delivery script SHA-256 mismatch: actual {source_hash}")

    segments = load_json(segment_path)
    if not isinstance(segments, list) or [item.get("id") for item in segments] != EXPECTED_IDS:
        raise ValueError("segments.json must contain exactly S01 through S08 in source order")

    text = adapted_path.read_text(encoding="utf-8")
    rows: dict[str, dict[str, Any]] = {}
    pattern = re.compile(r"^\| (S\d{2}) \| \[(\d+), (\d+)\) \| (.*?) \| (.*?) \|")
    for line in text.splitlines():
        match = pattern.match(line)
        if match:
            segment_id, start, end, display, phonetic = match.groups()
            rows[segment_id] = {
                "startFrame": int(start),
                "endFrame": int(end),
                "display_subtitle": display.replace("<br>", "\n"),
                "tts_phonetic_text": phonetic,
            }
    if set(rows) != set(EXPECTED_IDS):
        raise ValueError(f"adapted-script.md segment rows differ: {sorted(rows)}")
    for segment in segments:
        row = rows[segment["id"]]
        for field in ("startFrame", "endFrame", "display_subtitle", "tts_phonetic_text"):
            if row[field] != segment[field]:
                raise ValueError(f"{segment['id']} {field} differs from source segments.json")
        for chunk in segment.get("chunks", []):
            if len(re.sub(r"\s+", "", chunk)) > 26:
                raise ValueError(f"{segment['id']} source caption chunk exceeds two 13-character lines")
    return "PASS", "Source hash and all eight authored segment windows, display subtitles, and TTS strings match.", {
        "scriptSha256": source_hash,
        "segmentCount": len(segments),
        "exactFields": ["startFrame", "endFrame", "display_subtitle", "tts_phonetic_text"],
    }


def check_measured_tts_placement() -> tuple[str, str, Any]:
    manifest = load_json(PROJECT / "public" / "audio" / "provider-manifest.json")
    entries = manifest["segments"]
    first, second = entries["S01"], entries["S02"]
    expected_identity = {
        "provider": "Aliyun Bailian",
        "effective_model": "cosyvoice-v3-flash",
        "voice": "longtian_v3",
        "rate": 1.0,
    }
    for segment_id, item in (("S01", first), ("S02", second)):
        settings = item["settings"]
        actual_identity = {
            "provider": settings.get("provider"),
            "effective_model": settings.get("effective_model"),
            "voice": settings.get("voice"),
            "rate": settings.get("rate"),
        }
        if actual_identity != expected_identity:
            raise ValueError(f"{segment_id} provider/model/voice/rate differs: {actual_identity}")
        if item.get("identity_status") != "reported by CLI response":
            raise ValueError(f"{segment_id} effective identity lacks CLI-reported status")

    actual = {
        "S01": {
            "cueStartSample": first["cue_start_sample"],
            "cueEndSampleExclusive": first["cue_end_sample_exclusive"],
            "activeStartSample": first["voice_start_sample"],
            "activeEndSampleExclusive": first["voice_end_sample"],
        },
        "S02": {
            "cueStartSample": second["cue_start_sample"],
            "cueEndSampleExclusive": second["cue_end_sample_exclusive"],
            "activeStartSample": second["voice_start_sample"],
            "activeEndSampleExclusive": second["voice_end_sample"],
        },
    }
    if (actual["S01"]["activeStartSample"], actual["S01"]["activeEndSampleExclusive"]) != (48_000, 472_868):
        raise ValueError(f"S01 active PCM bounds differ from the approved measured bounds: {actual['S01']}")
    if actual["S02"]["activeStartSample"] != 480_000:
        raise ValueError(f"S02 active PCM does not begin at sample 480000: {actual['S02']}")
    cue_overlap = max(
        0,
        min(actual["S01"]["cueEndSampleExclusive"], actual["S02"]["cueEndSampleExclusive"])
        - max(actual["S01"]["cueStartSample"], actual["S02"]["cueStartSample"]),
    )
    speech_overlap = max(
        0,
        min(actual["S01"]["activeEndSampleExclusive"], actual["S02"]["activeEndSampleExclusive"])
        - max(actual["S01"]["activeStartSample"], actual["S02"]["activeStartSample"]),
    )
    if cue_overlap != 13_483 or speech_overlap != 0:
        raise ValueError(f"complete-cue overlap / active-speech overlap differs: {cue_overlap} / {speech_overlap}")
    return "PASS", "Measured TTS placement preserves the complete cues and natural-rate active speech without speech overlap.", {
        "provider": "Aliyun Bailian",
        "effectiveModel": "cosyvoice-v3-flash",
        "voice": "longtian_v3",
        "rate": 1.0,
        "S01": actual["S01"],
        "S02": actual["S02"],
        "completeCueOverlapSamples": cue_overlap,
        "completeCueOverlapSeconds": cue_overlap / SAMPLE_RATE,
        "activeSpeechOverlapSamples": speech_overlap,
    }


def check_timing_override() -> tuple[str, str, Any]:
    path = PROJECT / "audio-timing-overrides.json"
    if not path.is_file():
        return "INCOMPLETE", "No root-owned audio timing override is present to verify.", None
    value = load_json(path)
    s01 = value.get("segments", {}).get("S01", {})
    actual = {
        "cueStartSample": s01.get("cueStartSample"),
        "captionEndFrame": s01.get("captionEndFrame"),
        "decisionSource": value.get("decisionSource"),
    }
    expected = {
        "cueStartSample": 37_571,
        "captionEndFrame": 592,
        "decisionSource": "Direct user reply in this EP13 chat: 使用空隙，保留全文与自然语速（推荐）",
    }
    if actual != expected:
        raise ValueError(f"approved S01 timing override differs: {actual}")
    return "PASS", "The existing root-owned override records the approved S01 cue placement and caption end.", actual


def check_audio_timing_and_captions() -> tuple[str, str, Any]:
    path = PROJECT / "audio-timing.json"
    if not path.is_file():
        return "INCOMPLETE", "Measured audio-timing.json is absent; caption timing cannot be checked yet.", None
    value = load_json(path)
    captions = value.get("captions")
    segments = value.get("segments")
    if value.get("status") == "PREVIEW_ONLY" or not isinstance(captions, list) or not captions:
        return "INCOMPLETE", "audio-timing.json still contains a preview placeholder; measured caption windows are pending.", {
            "status": value.get("status"),
            "captionCount": len(captions) if isinstance(captions, list) else None,
        }
    if value.get("fps") != FPS or value.get("sampleRate") != SAMPLE_RATE or value.get("samplesPerChannel") != SAMPLES_PER_CHANNEL:
        raise ValueError("measured audio-timing.json has incorrect fps, sample rate, or sample count")

    prior_end = -1
    by_id: dict[str, list[dict[str, Any]]] = {}
    for index, caption in enumerate(captions):
        start, end = caption.get("startFrame"), caption.get("endFrame")
        segment_id, text = caption.get("segmentId"), caption.get("text")
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= TOTAL_FRAMES:
            raise ValueError(f"caption {index} has invalid frame bounds: {start}, {end}")
        if start < prior_end:
            raise ValueError(f"caption {index} overlaps or precedes the previous caption")
        if segment_id not in EXPECTED_IDS or not isinstance(text, str) or not text:
            raise ValueError(f"caption {index} has an unknown segment or empty text")
        lines = text.splitlines()
        if not 1 <= len(lines) <= 2 or any(len(line) > 13 for line in lines):
            raise ValueError(f"caption {index} exceeds two lines or 13 characters per line: {text!r}")
        prior_end = end
        by_id.setdefault(segment_id, []).append(caption)

    if not isinstance(segments, list):
        raise ValueError("measured timing has no segment timing list")
    timing_by_id = {item.get("id"): item for item in segments if isinstance(item, dict)}
    for segment_id in EXPECTED_IDS:
        if segment_id not in by_id or segment_id not in timing_by_id:
            raise ValueError(f"measured timing is missing {segment_id} captions or segment timing")
        timing = timing_by_id[segment_id]
        ordered = by_id[segment_id]
        if ordered[0]["startFrame"] < timing["captionStartFrame"] or ordered[-1]["endFrame"] > timing["captionEndFrame"]:
            raise ValueError(f"{segment_id} captions escape its measured caption window")
        chunks = load_json(PROJECT / "segments.json")
        source_segment = next(item for item in chunks if item["id"] == segment_id)
        expected_text = "".join(re.sub(r"\s+", "", chunk) for chunk in source_segment["chunks"])
        actual_text = "".join(re.sub(r"\s+", "", item["text"]) for item in ordered)
        if actual_text != expected_text:
            raise ValueError(f"{segment_id} timed caption chunks do not preserve the source text")
    s01 = timing_by_id["S01"]
    s02 = timing_by_id["S02"]
    if s01.get("captionStartFrame") != 60 or s01.get("captionEndFrame") != 592:
        raise ValueError("measured S01 caption window must be [60, 592)")
    if s02.get("voiceStartSample") != 480_000:
        raise ValueError("measured S02 active voice must begin at sample 480000")
    return "PASS", "Measured captions are ordered, non-overlapping, in range, readable, and preserve every source chunk.", {
        "captionCount": len(captions),
        "S01CaptionWindow": [s01["captionStartFrame"], s01["captionEndFrame"]],
        "S02ActiveStartSample": s02["voiceStartSample"],
    }


def check_encoded_video_presence() -> tuple[str, str, Any]:
    delivery = load_json(DELIVERY / "delivery.json")
    relative = delivery.get("outputs", {}).get("xiaohongshu", {}).get("path")
    if not isinstance(relative, str) or not relative:
        raise ValueError("delivery.json has no Xiaohongshu output path")
    target = (DELIVERY / relative).resolve()
    try:
        target.relative_to(DELIVERY.resolve())
    except ValueError:
        raise ValueError("delivery output path escapes the work directory") from None
    if not target.is_file():
        return "INCOMPLETE", "Final encoded Xiaohongshu video is absent; encode/decode and visual checks cannot run.", {
            "expectedPath": relative,
        }
    size = target.stat().st_size
    if size <= 0:
        raise ValueError("final encoded Xiaohongshu video exists but is empty")
    return "PASS", "Final encoded video file is present; this source verifier does not decode or visually accept it.", {
        "path": relative,
        "sizeBytes": size,
        "mediaValidation": "not performed by this script",
    }


def check_pcm_master() -> tuple[str, str, Any]:
    path = PROJECT / "public" / "audio" / "master.wav"
    if not path.is_file():
        return "INCOMPLETE", "PCM master is absent; sample format, exact length, and blackout silence remain unverified.", {
            "expectedPath": "project/public/audio/master.wav",
            "expectedSamplesPerChannel": SAMPLES_PER_CHANNEL,
            "expectedSilenceSamples": [SILENCE_START, SILENCE_END],
        }
    try:
        with wave.open(str(path), "rb") as wav:
            params = wav.getparams()
            if params.comptype != "NONE":
                raise ValueError(f"master is not uncompressed PCM: {params.comptype}")
            if params.framerate != SAMPLE_RATE or params.nchannels != 2:
                raise ValueError(f"master must be stereo at 48 kHz: {params}")
            if params.nframes != SAMPLES_PER_CHANNEL:
                raise ValueError(f"master has {params.nframes} sample frames, expected {SAMPLES_PER_CHANNEL}")
            if params.sampwidth not in (2, 3, 4):
                raise ValueError(f"unsupported PCM sample width: {params.sampwidth}")
            wav.setpos(SILENCE_START)
            silence = wav.readframes(SILENCE_END - SILENCE_START)
            expected_bytes = (SILENCE_END - SILENCE_START) * 2 * params.sampwidth
            if len(silence) != expected_bytes:
                raise ValueError("master blackout window was truncated while reading")
            if any(silence):
                raise ValueError("master contains non-zero PCM bytes during [4860, 4890)")
    except (OSError, wave.Error) as exc:
        raise ValueError(f"cannot inspect PCM master WAV: {exc}") from None
    return "PASS", "PCM master is stereo 48 kHz at the exact sample count and contains exact digital silence on [4860, 4890).", {
        "sampleRate": SAMPLE_RATE,
        "channels": 2,
        "samplesPerChannel": SAMPLES_PER_CHANNEL,
        "sampleWidthBytes": params.sampwidth,
        "silenceSampleRange": [SILENCE_START, SILENCE_END],
        "silenceBytesAreZero": True,
    }


def check_hud_and_composition() -> tuple[str, str, Any]:
    root_tsx = (PROJECT / "src" / "Root.tsx").read_text(encoding="utf-8")
    film_tsx = (PROJECT / "src" / "Film.tsx").read_text(encoding="utf-8")
    lexicon = load_json(PROJECT / "telemetry-lexicon.json")
    root_requirements = {
        "width": r"width\s*=\s*\{\s*2160\s*\}",
        "height": r"height\s*=\s*\{\s*3840\s*\}",
        "fps": r"fps\s*=\s*\{\s*60\s*\}",
        "durationInFrames": r"durationInFrames\s*=\s*\{\s*5400\s*\}",
    }
    for field, pattern in root_requirements.items():
        if not re.search(pattern, root_tsx):
            raise ValueError(f"Root.tsx does not declare required {field}")
    if not re.search(r"ref=\{hud\}[\s\S]{0,320}?fontSize\s*:\s*30\b", film_tsx):
        raise ValueError("Film.tsx HUD is not declared at 30 logical pixels")
    expected = {
        "hud_biological_decay": (0, 1320, "BIO DECAY: exp(-t/S)"),
        "hud_permanent_retention": (1320, 5400, "SI RETENTION: 100.000%"),
        "hud_replay": (0, 5400, "8K REPLAY · PAIN LOSS 0.0%"),
        "hud_burn_in": (0, 5400, "BURN-IN · PRUNING DISABLED"),
    }
    entries = {item["id"]: item for item in lexicon["hud"]}
    for entry_id, (start, end, display) in expected.items():
        item = entries.get(entry_id)
        if not item or (item.get("startFrame"), item.get("endFrame"), item.get("displayText")) != (start, end, display):
            raise ValueError(f"telemetry lexicon entry differs: {entry_id}")
        if display not in film_tsx:
            raise ValueError(f"required compact HUD string is missing from Film.tsx: {entry_id}")
    if not re.search(r"fontSize\s*:\s*30\b", film_tsx) or lexicon["display_policy"].get("hud_lines") != 3:
        raise ValueError("HUD font/line-count readability contract is not present")
    return "PASS", "Portrait composition and all three compact HUD lines match the 2160×3840, 60 fps, 5400-frame, 30 px specification.", {
        "composition": "PortraitVertical",
        "resolution": [2160, 3840],
        "fps": FPS,
        "frames": TOTAL_FRAMES,
        "hudFontLogicalPx": 30,
        "hudLines": 3,
        "hudStrings": [entry[2] for entry in expected.values()],
    }


def check_source_apis() -> tuple[str, str, Any]:
    paths = sorted(
        path for path in (PROJECT / "src").rglob("*")
        if path.is_file() and path.suffix.lower() in {".ts", ".tsx", ".js", ".jsx", ".css"}
    )
    if not paths:
        raise ValueError("project/src has no TypeScript, JavaScript, or CSS sources")
    patterns = {
        "Math.random": re.compile(r"\bMath\s*\.\s*random\s*\("),
        "Date.now": re.compile(r"\bDate\s*\.\s*now\s*\("),
        "3D CSS transform": re.compile(r"\b(?:perspective|rotateX|rotateY|rotate3d|translateZ|translate3d)\s*\(", re.I),
        "Three.js import": re.compile(r"(?:from\s*|require\s*\()\s*['\"](?:three|@react-three/)[^'\"]*['\"]"),
        "Three.js runtime API": re.compile(r"\b(?:PerspectiveCamera|WebGLRenderer)\b|\bTHREE\s*\."),
        "3D scene Canvas": re.compile(r"<Canvas\b"),
    }
    findings = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"/\*[\s\S]*?\*/", "", text)
        text = re.sub(r"(?m)^\s*//.*$", "", text)
        for name, pattern in patterns.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append({"file": path.relative_to(DELIVERY).as_posix(), "line": line, "api": name})
    if findings:
        raise ValueError(f"forbidden nondeterministic or 3D APIs found: {findings}")
    return "PASS", "No actual Math.random/Date.now or 3D rendering/transform APIs were found in project/src.", {
        "sourceFilesScanned": [path.relative_to(DELIVERY).as_posix() for path in paths],
        "forbiddenApiFindings": 0,
    }


def check_event_frames() -> tuple[str, str, Any]:
    authored = load_json(PROJECT / "sfx_events.json")
    timeline = load_json(PROJECT / "timeline.json")
    expected = [
        ("rewind_calibration", 60),
        ("warm_filtered_chord", 840),
        ("tape_hiss", 1500),
        ("magnetic_relay", 1920),
        ("hv_phase_lock", 2160),
        ("nondecaying_loops", 2940),
        ("shepard_tube", 3900),
        ("harmonic_peak", 4500),
        ("crt_power_off_snap", 4860),
        ("warm_piano_chord", 4890),
    ]
    actual = [(item.get("id"), item.get("frame")) for item in authored.get("events", [])]
    if authored.get("fps") != FPS or authored.get("sampleRate") != SAMPLE_RATE or authored.get("samplesPerFrame") != SAMPLES_PER_FRAME:
        raise ValueError("sfx_events.json timing units must be 60 fps / 48 kHz / 800 samples per frame")
    if actual != expected:
        raise ValueError(f"SFX event IDs/frames differ from plan: {actual}")
    for item in authored["events"]:
        if item.get("sample") != item["frame"] * SAMPLES_PER_FRAME:
            raise ValueError(f"{item['id']} sample is not frame*800")
    silence = authored.get("absoluteSilence", {})
    if (silence.get("startFrame"), silence.get("endFrameExclusive"), silence.get("startSample"), silence.get("endSampleExclusive"), silence.get("requireExactZero")) != (4860, 4890, SILENCE_START, SILENCE_END, True):
        raise ValueError("sfx_events.json absolute-silence range is wrong")
    if authored.get("voiceMinimumOnsetFrame") != 4902:
        raise ValueError("S08 minimum voice onset must be frame 4902")
    snap = authored.get("snapBoundary", {})
    if (snap.get("anchorFrame"), snap.get("attackStartFrame"), snap.get("attackStartSample"), snap.get("endSampleExclusive")) != (4860, 4859, 3_887_200, SILENCE_START):
        raise ValueError("snap must occupy frame 4859 and end at the silence boundary")
    if timeline["canvas"].get("totalFrames") != TOTAL_FRAMES or timeline["canvas"].get("fps") != FPS:
        raise ValueError("timeline canvas frame count differs")
    timeline_events = {item.get("id"): item for item in timeline.get("events", [])}
    planned_timeline = {
        "opening_cassette_calibration": (60, 61),
        "soft_chord": (840, 841),
        "tape_hiss_fade": (1500, 1920),
        "magnetic_relay_lock": (1920, 1921),
        "crt_phase_lock": (2160, 2161),
        "feedback_stack": (2940, 2941),
        "shepard_rise": (3900, 3901),
        "harmonic_peak": (4500, 4501),
        "crt_power_off_snap": (4859, 4860),
        "absolute_silence": (4860, 4890),
        "piano_entry": (4890, 5400),
        "s08_voice_earliest_start": (4902, 5400),
    }
    for event_id, expected_bounds in planned_timeline.items():
        item = timeline_events.get(event_id)
        if not item or (item.get("startFrame"), item.get("endFrame")) != expected_bounds:
            raise ValueError(f"timeline event {event_id} does not match {expected_bounds}")
    return "PASS", "Authored SFX and timeline event frames, sample anchors, snap boundary, blackout, piano and voice onset agree.", {
        "sfxFrames": actual,
        "silenceFrames": [4860, 4890],
        "snapAttackFrames": [4859, 4860],
        "pianoFrame": 4890,
        "minimumS08VoiceFrame": 4902,
    }


def main() -> int:
    run_check("source_script_and_segments", check_script_and_segments)
    run_check("measured_tts_placement", check_measured_tts_placement)
    run_check("root_owned_timing_override", check_timing_override)
    run_check("measured_audio_timing_and_captions", check_audio_timing_and_captions)
    run_check("encoded_video_presence", check_encoded_video_presence)
    run_check("pcm_master", check_pcm_master)
    run_check("hud_and_composition", check_hud_and_composition)
    run_check("determinism_and_2d_source_apis", check_source_apis)
    run_check("event_frames", check_event_frames)

    statuses = [item["status"] for item in checks]
    overall = "FAIL" if "FAIL" in statuses else "INCOMPLETE" if "INCOMPLETE" in statuses else "PASS"
    report = {
        "schema_version": 1,
        "work": "si-ep13-curse-of-memory",
        "checker": "project/scripts/verify_project.py",
        "scope": "source, timing, and artifact presence checks; not final-media acceptance",
        "status": overall,
        "summary": {
            "pass": statuses.count("PASS"),
            "fail": statuses.count("FAIL"),
            "incomplete": statuses.count("INCOMPLETE"),
        },
        "checks": checks,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": overall, **report["summary"], "report": "review/source-check.json"}, ensure_ascii=False))
    return 1 if overall == "FAIL" else 2 if overall == "INCOMPLETE" else 0


if __name__ == "__main__":
    sys.exit(main())
