#!/usr/bin/env python3
"""Independently compare measured narration cues, authored SFX anchors, and the absolute-silence window."""

from __future__ import annotations

import argparse
import array
import json
import sys
import wave
from pathlib import Path
from typing import Any

import build_audio as audio


PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT.parent
AUDIO = PROJECT / "public" / "audio"
TIMING_PATH = PROJECT / "audio-timing.json"
MANIFEST_PATH = AUDIO / "mix-manifest.json"
REPORT_PATH = WORK / "review" / "audio-alignment.json"
STEMS = ("narration", "score", "sfx", "master")


class AuditError(RuntimeError):
    pass


def sha_matches(path: Path, expected: str | None) -> bool:
    return isinstance(expected, str) and audio.sha256_file(path) == expected


def read_mono(path: Path) -> tuple[array.array, dict[str, Any]]:
    values, info = audio.read_mono_cue(path)
    return values, info


def compare_cue_to_narration(cue_path: Path, narration_path: Path, cue_start: int, cue_samples: int) -> dict[str, Any]:
    cue, info = read_mono(cue_path)
    if len(cue) != cue_samples:
        raise AuditError(f"{cue_path.name}: measured {len(cue)} samples but timing records {cue_samples}")
    compared = 0
    cue_offset = 0
    with wave.open(str(narration_path), "rb") as narration:
        narration.setpos(cue_start)
        while cue_offset < cue_samples:
            count = min(audio.BLOCK_SAMPLES, cue_samples - cue_offset)
            raw = narration.readframes(count)
            if len(raw) != count * 4:
                raise AuditError(f"narration.wav ends during {cue_path.name}")
            stereo = array.array("h")
            stereo.frombytes(raw)
            if sys.byteorder != "little":
                stereo.byteswap()
            left = stereo[0::2]
            right = stereo[1::2]
            expected = cue[cue_offset:cue_offset + count]
            if left != expected or right != expected:
                raise AuditError(f"narration.wav does not preserve {cue_path.name} PCM exactly")
            compared += count
            cue_offset += count
    return {"cueSamplesCompared": compared, "cueSha256": info["sha256"], "exactPcmMatch": True}


def event_sample(path: Path, sample_index: int) -> tuple[int, int]:
    with wave.open(str(path), "rb") as wav:
        wav.setpos(sample_index)
        raw = wav.readframes(1)
    if len(raw) != 4:
        raise AuditError(f"sfx.wav has no sample at event sample {sample_index}")
    values = array.array("h")
    values.frombytes(raw)
    if sys.byteorder != "little":
        values.byteswap()
    return int(values[0]), int(values[1])


def run_audit() -> dict[str, Any]:
    if not TIMING_PATH.is_file() or not MANIFEST_PATH.is_file():
        missing = [str(path.relative_to(WORK)) for path in (TIMING_PATH, MANIFEST_PATH) if not path.is_file()]
        return {"status": "pending_missing_alignment_records", "missing": missing, "checks": []}
    try:
        timing = json.loads(TIMING_PATH.read_text(encoding="utf-8"))
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditError(f"audio timing or mix manifest is unreadable: {exc}") from None
    if not isinstance(timing, dict) or not isinstance(manifest, dict):
        raise AuditError("audio timing and mix manifest must be JSON objects")
    if timing.get("samplesPerChannel") != audio.TOTAL_SAMPLES or timing.get("fps") != audio.FPS or timing.get("sampleRate") != audio.SAMPLE_RATE:
        raise AuditError("audio-timing.json does not describe exact 120s / 60fps / 48kHz audio")
    timing_hashes = timing.get("sourceHashes", {})
    if timing_hashes.get("segmentsJson") != audio.sha256_file(audio.SEGMENTS_PATH):
        raise AuditError("segments.json changed after the audio timing record was written")
    if timing_hashes.get("eventsJson") != audio.sha256_file(audio.EVENTS_PATH):
        raise AuditError("sfx_events.json changed after the audio timing record was written")
    authored_events, _ = audio.load_events()
    timing_events = timing.get("sfxEvents", [])
    if not isinstance(timing_events, list) or any(not isinstance(item, dict) for item in timing_events):
        raise AuditError("audio-timing.json has an invalid SFX event list")
    if [(item.get("id"), item.get("frame"), item.get("sampleIndex"), item.get("kind"), item.get("durationSeconds"), item.get("silentMarker")) for item in timing_events] != [
        (item["id"], item["frame"], item["sampleIndex"], item["kind"], item["durationSeconds"], item["kind"] == "silence") for item in authored_events
    ]:
        raise AuditError("audio-timing.json SFX anchors differ from the authoritative sfx_events.json")
    silence = timing.get("absoluteSilence", {})
    if (silence.get("startFrame"), silence.get("endFrameExclusive"), silence.get("startSample"), silence.get("endSampleExclusive")) != (
        audio.SILENCE_START_FRAME, audio.SILENCE_END_FRAME, audio.SILENCE_START_SAMPLE, audio.SILENCE_END_SAMPLE
    ):
        raise AuditError("audio-timing.json does not record the exact authored absolute-silence window")

    measured_stems = {}
    expected_outputs = manifest.get("outputs", {})
    for name in STEMS:
        path = AUDIO / f"{name}.wav"
        if not path.is_file():
            return {"status": "pending_missing_stems", "missing": [str(path.relative_to(WORK))], "checks": []}
        info = audio.wav_info(path, stereo=True)
        if info["samples"] != audio.TOTAL_SAMPLES:
            raise AuditError(f"{name}.wav has {info['samples']} samples/ch; expected {audio.TOTAL_SAMPLES}")
        if not sha_matches(path, expected_outputs.get(name, {}).get("sha256")):
            raise AuditError(f"{name}.wav hash differs from mix-manifest.json")
        measured_stems[name] = {"samplesPerChannel": info["samples"], "sha256": info["sha256"], "exactLength": True}

    narration_path = AUDIO / "narration.wav"
    segment_results = []
    timing_segments = timing.get("segments")
    if not isinstance(timing_segments, list) or len(timing_segments) != 10:
        raise AuditError("audio-timing.json must contain ten measured narration segments")
    declared_segments = {item["id"]: item for item in audio.load_segments()}
    for segment in timing_segments:
        declared = declared_segments.get(segment.get("id"))
        if declared is None or segment.get("declaredStartFrame") != declared["startFrame"] or segment.get("declaredEndFrame") != declared["endFrame"]:
            raise AuditError(f"{segment.get('id')} declared timing differs from segments.json")
        cue_path = (WORK / segment["cueFile"]).resolve()
        if not cue_path.is_relative_to(PROJECT.resolve()) or not cue_path.is_file():
            raise AuditError(f"missing or out-of-project cue path for {segment.get('id')}")
        cue, cue_info = read_mono(cue_path)
        onset, active_end, onset_method = audio.active_bounds(cue)
        cue_start = int(segment["cueStartSample"])
        voice_start = cue_start + onset
        voice_end = cue_start + active_end
        if voice_start != int(segment["voiceStartSample"]) or voice_end != int(segment["voiceEndSampleExclusive"]):
            raise AuditError(f"{segment['id']} measured active PCM bounds changed after timing was recorded")
        if not sha_matches(cue_path, segment.get("cueSha256")):
            raise AuditError(f"{segment['id']} cue hash differs from audio-timing.json")
        exact = compare_cue_to_narration(cue_path, narration_path, cue_start, int(segment["cueSamplesAt48k"]))
        segment_results.append({
            "id": segment["id"],
            "declaredStartFrame": segment["declaredStartFrame"],
            "measuredVoiceStartSample": voice_start,
            "measuredVoiceEndSampleExclusive": voice_end,
            "measuredCueSamples": len(cue),
            "onsetMeasurement": onset_method,
            **exact,
        })

    onset_results = []
    event_list = timing_events
    sfx_path = AUDIO / "sfx.wav"
    for event in event_list:
        expected_sample = int(event["frame"]) * audio.SAMPLES_PER_FRAME
        if int(event.get("sampleIndex", -1)) != expected_sample:
            raise AuditError(f"SFX event {event.get('id')} has an incorrect sample anchor")
        if event.get("silentMarker"):
            continue
        left, right = event_sample(sfx_path, expected_sample)
        if left == 0 and right == 0:
            raise AuditError(f"SFX event {event.get('id')} has no nonzero PCM at its authored onset sample")
        onset_results.append({"id": event.get("id"), "frame": event["frame"], "sampleIndex": expected_sample, "leftPcm16AtOnset": left, "rightPcm16AtOnset": right, "sampleAnchorExact": True})

    silence_results = {}
    for name in STEMS:
        peak = audio.verify_silence_window(AUDIO / f"{name}.wav")
        if peak:
            raise AuditError(f"{name}.wav contains nonzero PCM in the authored absolute-silence window; peak={peak}")
        silence_results[name] = {"peakPcm16": peak, "exactZero": True}
    return {
        "status": "pcm_alignment_verified",
        "durationSeconds": audio.DURATION_SECONDS,
        "samplesPerChannel": audio.TOTAL_SAMPLES,
        "stems": measured_stems,
        "narrationSegments": segment_results,
        "sfxEventOnsets": onset_results,
        "absoluteSilence": {
            "startFrame": audio.SILENCE_START_FRAME,
            "endFrameExclusive": audio.SILENCE_END_FRAME,
            "startSample": audio.SILENCE_START_SAMPLE,
            "endSampleExclusive": audio.SILENCE_END_SAMPLE,
            "stems": silence_results,
        },
        "limitations": ["No ASR or pronunciation evaluation was performed.", "PCM alignment evidence does not establish human listening or mix-quality acceptance."],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-report", action="store_true", help="print the audit result without writing the review JSON")
    args = parser.parse_args()
    try:
        report = run_audit()
        if not args.no_report:
            REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
            temp = REPORT_PATH.with_name(REPORT_PATH.name + ".tmp")
            temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            temp.replace(REPORT_PATH)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "pcm_alignment_verified" else 2
    except (AuditError, audio.AudioBuildError, OSError, ValueError, TypeError, KeyError, wave.Error) as exc:
        print(f"audit_audio_alignment.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
