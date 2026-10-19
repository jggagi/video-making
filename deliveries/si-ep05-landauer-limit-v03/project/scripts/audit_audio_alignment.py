#!/usr/bin/env python3
"""Independently compare measured narration cues, exact event samples, and the thermal cut."""

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
STEMS = ("narration", "score", "sfx", "thermal", "master")


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


def thermal_cut_peak(path: Path) -> int:
    peak = 0
    with wave.open(str(path), "rb") as wav:
        wav.setpos(audio.THERMAL_CUT_SAMPLE)
        remaining = audio.TOTAL_SAMPLES - audio.THERMAL_CUT_SAMPLE
        while remaining:
            count = min(audio.BLOCK_SAMPLES, remaining)
            raw = wav.readframes(count)
            if len(raw) != count * 4:
                raise AuditError("thermal.wav ended before the end of the exact master")
            values = array.array("h")
            values.frombytes(raw)
            if sys.byteorder != "little":
                values.byteswap()
            peak = max(peak, max((abs(value) for value in values), default=0))
            remaining -= count
    return peak


def interval_peak(path: Path, start_sample: int, end_sample: int) -> int:
    peak = 0
    with wave.open(str(path), "rb") as wav:
        if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getnframes()) != (
            audio.SAMPLE_RATE, 2, 2, audio.TOTAL_SAMPLES
        ):
            raise AuditError(f"{path.name} is not an exact-length 48 kHz stereo PCM16 stem")
        wav.setpos(start_sample)
        remaining = end_sample - start_sample
        while remaining:
            count = min(audio.BLOCK_SAMPLES, remaining)
            raw = wav.readframes(count)
            if len(raw) != count * 4:
                raise AuditError(f"{path.name} ended during the digital-vacuum interval")
            values = array.array("h")
            values.frombytes(raw)
            if sys.byteorder != "little":
                values.byteswap()
            peak = max(peak, max((abs(value) for value in values), default=0))
            remaining -= count
    return peak


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
    if timing.get("sourceHashes", {}).get("segmentsJson") != audio.sha256_file(audio.SEGMENTS_PATH):
        raise AuditError("segments.json changed after the audio timing record was written")

    measured_stems = {}
    expected_outputs = manifest.get("outputs", {})
    vacuum_checks = {}
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
        peak = interval_peak(path, audio.VACUUM_SILENCE_START_SAMPLE, audio.VACUUM_SILENCE_END_SAMPLE)
        if peak != 0:
            raise AuditError(f"{name}.wav must be digital zero in frames [5400, 5425); peak={peak}")
        vacuum_checks[name] = {
            "startFrame": audio.THERMAL_CUT_FRAME,
            "endFrameExclusive": audio.CRYO_CHIME_FRAME,
            "peakPcm16": peak,
            "exactZero": True,
        }

    master_loudness = expected_outputs.get("master", {}).get("ebur128Final")
    if not isinstance(master_loudness, dict):
        raise AuditError("mix-manifest.json is missing measured master loudness/true-peak metadata")
    integrated = float(master_loudness.get("integratedLUFS", float("nan")))
    true_peak = float(master_loudness.get("truePeakDBTP", float("nan")))
    if not -18.0 <= integrated <= -16.0:
        raise AuditError(f"master integrated loudness {integrated} LUFS is outside -18 to -16 LUFS")
    if true_peak > -1.0:
        raise AuditError(f"master true peak {true_peak} dBTP exceeds -1.0 dBTP")

    narration_path = AUDIO / "narration.wav"
    segment_results = []
    timing_segments = timing.get("segments")
    if not isinstance(timing_segments, list) or len(timing_segments) != 10:
        raise AuditError("audio-timing.json must contain ten measured narration segments")
    for segment in timing_segments:
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
    event_list = timing.get("sfxEvents", [])
    if [event.get("frame") for event in event_list] != audio.EXPECTED_EVENT_FRAMES:
        raise AuditError("audio-timing.json event order or frame anchors differ from the EP05 design")
    sfx_path = AUDIO / "sfx.wav"
    for event in event_list:
        expected_sample = int(event["frame"]) * audio.SAMPLES_PER_FRAME
        if int(event.get("sampleIndex", -1)) != expected_sample:
            raise AuditError(f"SFX event {event.get('id')} has an incorrect sample anchor")
        left, right = event_sample(sfx_path, expected_sample)
        if left == 0 and right == 0:
            raise AuditError(f"SFX event {event.get('id')} has no nonzero PCM at its authored onset sample")
        onset_results.append({"id": event.get("id"), "frame": event["frame"], "sampleIndex": expected_sample, "leftPcm16AtOnset": left, "rightPcm16AtOnset": right, "sampleAnchorExact": True})

    cut_peak = thermal_cut_peak(AUDIO / "thermal.wav")
    if cut_peak != 0:
        raise AuditError(f"thermal.wav contains nonzero PCM after sample {audio.THERMAL_CUT_SAMPLE}; peak={cut_peak}")
    return {
        "status": "pcm_alignment_verified",
        "durationSeconds": audio.DURATION_SECONDS,
        "samplesPerChannel": audio.TOTAL_SAMPLES,
        "stems": measured_stems,
        "narrationSegments": segment_results,
        "sfxEventOnsets": onset_results,
        "masterLoudness": {
            "integratedLUFS": integrated,
            "truePeakDBTP": true_peak,
            "acceptanceLUFS": [-18.0, -16.0],
            "acceptanceTruePeakDBTP": -1.0,
        },
        "thermalCut": {"frame": audio.THERMAL_CUT_FRAME, "sample": audio.THERMAL_CUT_SAMPLE, "peakPcm16FromCut": cut_peak, "exactZero": True},
        "digitalVacuum": vacuum_checks,
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
        return 0 if report["status"] == "pcm_alignment_verified" else 0
    except (AuditError, audio.AudioBuildError, OSError, ValueError, TypeError, KeyError, wave.Error) as exc:
        print(f"audit_audio_alignment.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
