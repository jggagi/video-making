#!/usr/bin/env python3
"""Create estimate-only EP05 captions until a real PCM timing pass is available."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT.parent
SEGMENTS_PATH = PROJECT / "segments.json"
TIMING_PATH = PROJECT / "audio-timing.json"
FPS = 60
SAMPLE_RATE = 48_000
SAMPLES_PER_FRAME = SAMPLE_RATE // FPS
TOTAL_FRAMES = 7_200
MAX_CHINESE_PER_LINE = 14


class CaptionError(RuntimeError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CaptionError(f"cannot read {path.name}: {exc}") from None
    if not isinstance(value, dict):
        raise CaptionError(f"{path.name} must contain a JSON object")
    return value


def chinese_count(text: str) -> int:
    return sum("\u3400" <= char <= "\u9fff" for char in text)


def timestamp(frame: int) -> str:
    milliseconds = (frame * 1_000 + FPS // 2) // FPS
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    seconds, milliseconds = divmod(milliseconds, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def cue_groups(segment: dict[str, Any]) -> list[list[int]]:
    chunks = segment.get("chunks")
    if not isinstance(chunks, list) or not chunks or not all(
        isinstance(chunk, str) and chunk.strip() for chunk in chunks
    ):
        raise CaptionError(f"{segment.get('id', 'segment')} has no spoken caption chunks")
    for chunk in chunks:
        if "\n" in chunk or chinese_count(chunk) > MAX_CHINESE_PER_LINE:
            raise CaptionError(
                f"{segment.get('id')} has a spoken chunk over {MAX_CHINESE_PER_LINE} Chinese characters"
            )
    if segment.get("display_only_prefix"):
        return [[0]] + [
            list(range(index, min(index + 2, len(chunks))))
            for index in range(1, len(chunks), 2)
        ]
    return [list(range(index, min(index + 2, len(chunks)))) for index in range(0, len(chunks), 2)]


def allocate_windows(
    start: int, end: int, groups: list[list[int]], chunks: list[str]
) -> list[tuple[int, int]]:
    if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= TOTAL_FRAMES:
        raise CaptionError("segment has an invalid declared frame window")
    if end - start < len(groups):
        raise CaptionError("segment has too few frames for its caption cues")
    weights = [
        max(1, sum(len(chunks[index].replace(" ", "")) for index in group))
        for group in groups
    ]
    total_weight = sum(weights)
    windows: list[tuple[int, int]] = []
    cursor = start
    cumulative = 0
    for index, weight in enumerate(weights):
        cumulative += weight
        if index == len(weights) - 1:
            cue_end = end
        else:
            target = start + round((end - start) * cumulative / total_weight)
            latest_valid = end - (len(weights) - index - 1)
            cue_end = min(latest_valid, max(cursor + 1, target))
        windows.append((cursor, cue_end))
        cursor = cue_end
    return windows


def make_captions(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    captions: list[dict[str, Any]] = []
    for segment in segments:
        segment_id = segment["id"]
        chunks: list[str] = segment["chunks"]
        groups = cue_groups(segment)
        windows = allocate_windows(segment["startFrame"], segment["endFrame"], groups, chunks)
        prefix = segment.get("display_only_prefix")
        suffix = segment.get("display_only_suffix")
        for cue_number, (indices, (start, end)) in enumerate(zip(groups, windows), 1):
            spoken_lines = [chunks[index] for index in indices]
            display_lines = list(spoken_lines)
            display_only_lines: list[int] = []
            display_only_text: list[str] = []
            if cue_number == 1 and prefix:
                display_lines.insert(0, prefix)
                display_only_lines.append(0)
                display_only_text.append(prefix)
            if cue_number == len(groups) and suffix:
                display_lines.append(suffix)
                display_only_lines.append(len(display_lines) - 1)
                display_only_text.append(suffix)
            if len(display_lines) > 2 or any(
                chinese_count(line) > MAX_CHINESE_PER_LINE for line in display_lines
            ):
                raise CaptionError(f"{segment_id}-C{cue_number:02d} exceeds caption layout limits")
            captions.append(
                {
                    "id": f"{segment_id}-C{cue_number:02d}",
                    "segmentId": segment_id,
                    "startFrame": start,
                    "endFrame": end,
                    "text": "\n".join(display_lines),
                    "sourceChunkIndices": indices,
                    "displayOnlyLineIndices": display_only_lines,
                    "displayOnlyText": display_only_text,
                    "alignment": "estimate from declared segment window and phrase length; not word aligned",
                }
            )
    return captions


def make_timing(segments_source: dict[str, Any]) -> dict[str, Any]:
    segments = segments_source.get("segments")
    if not isinstance(segments, list) or len(segments) != 10:
        raise CaptionError("exactly ten EP05 segments are required")
    if (
        segments_source.get("fps"),
        segments_source.get("duration_seconds"),
        segments_source.get("sample_rate"),
        segments_source.get("total_frames"),
    ) != (FPS, 120, SAMPLE_RATE, TOTAL_FRAMES):
        raise CaptionError("segments.json does not match the 120-second, 60 fps target")
    declared = [
        {
            "id": segment.get("id"),
            "declaredStartFrame": segment.get("startFrame"),
            "declaredEndFrame": segment.get("endFrame"),
            "timingStatus": "estimate_only_pending_pcm",
        }
        for segment in segments
    ]
    return {
        "durationSeconds": 120,
        "fps": FPS,
        "sampleRate": SAMPLE_RATE,
        "samplesPerFrame": SAMPLES_PER_FRAME,
        "targetSamplesPerChannel": 5_760_000,
        "status": "preview_estimate_pending_pcm",
        "pcmMeasurement": None,
        "captionTimingMethod": (
            "Estimated by distributing each declared segment window among phrase chunks "
            "by text length; not measured from PCM and not word aligned."
        ),
        "segments": declared,
        "captions": make_captions(segments),
    }


def validate_and_render(
    segments_source: dict[str, Any], timing: dict[str, Any]
) -> tuple[str, list[dict[str, Any]]]:
    if (
        timing.get("fps"),
        timing.get("sampleRate"),
        timing.get("samplesPerFrame"),
        timing.get("targetSamplesPerChannel"),
    ) != (FPS, SAMPLE_RATE, SAMPLES_PER_FRAME, 5_760_000):
        raise CaptionError("audio-timing.json does not match the EP05 target audio format")
    if timing.get("status") != "preview_estimate_pending_pcm" or timing.get("pcmMeasurement") is not None:
        raise CaptionError("caption export scaffold must remain explicitly estimate-only until PCM is measured")
    segments = segments_source.get("segments")
    measured = timing.get("segments")
    captions = timing.get("captions")
    if not isinstance(segments, list) or len(segments) != 10:
        raise CaptionError("all ten EP05 narration segments are required")
    if not isinstance(measured, list) or len(measured) != 10:
        raise CaptionError("audio-timing.json must contain all ten declared segment windows")
    if not isinstance(captions, list) or not captions:
        raise CaptionError("audio-timing.json has no estimate caption windows")
    measured_by_id = {item.get("id"): item for item in measured}
    seen_chunks: dict[str, list[int]] = {item["id"]: [] for item in segments}
    rendered: list[tuple[int, int, str]] = []
    display_text_by_segment: dict[str, list[str]] = {item["id"]: [] for item in segments}
    spoken_text_by_segment: dict[str, dict[int, str]] = {item["id"]: {} for item in segments}

    for caption in captions:
        segment_id = caption.get("segmentId")
        if segment_id not in seen_chunks:
            raise CaptionError(f"caption references unknown segment {segment_id!r}")
        text = caption.get("text")
        if not isinstance(text, str) or not text.strip():
            raise CaptionError(f"{caption.get('id', 'caption')} has empty text")
        lines = text.splitlines()
        if not 1 <= len(lines) <= 2:
            raise CaptionError(f"{caption.get('id', 'caption')} must have one or two display lines")
        if any(chinese_count(line) > MAX_CHINESE_PER_LINE for line in lines):
            raise CaptionError(f"{caption.get('id', 'caption')} exceeds 14 Chinese characters on a line")
        start, end = caption.get("startFrame"), caption.get("endFrame")
        if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= TOTAL_FRAMES:
            raise CaptionError(f"{caption.get('id', 'caption')} has an invalid frame window")
        segment = next(item for item in segments if item["id"] == segment_id)
        if not segment["startFrame"] <= start < end <= segment["endFrame"]:
            raise CaptionError(f"{caption.get('id', 'caption')} falls outside its declared segment window")
        declared = measured_by_id.get(segment_id)
        if declared != {
            "id": segment_id,
            "declaredStartFrame": segment["startFrame"],
            "declaredEndFrame": segment["endFrame"],
            "timingStatus": "estimate_only_pending_pcm",
        }:
            raise CaptionError(f"{segment_id} declared timing differs from segments.json")
        indices = caption.get("sourceChunkIndices")
        display_only_indices = caption.get("displayOnlyLineIndices")
        display_only_text = caption.get("displayOnlyText")
        if (
            not isinstance(indices, list)
            or not indices
            or any(not isinstance(index, int) for index in indices)
            or not isinstance(display_only_indices, list)
            or any(not isinstance(index, int) or not 0 <= index < len(lines) for index in display_only_indices)
            or not isinstance(display_only_text, list)
        ):
            raise CaptionError(f"{caption.get('id', 'caption')} has an invalid spoken/display-only mapping")
        if len(display_only_indices) != len(display_only_text):
            raise CaptionError(f"{caption.get('id', 'caption')} display-only lines do not match their text list")
        spoken_lines = [line for index, line in enumerate(lines) if index not in display_only_indices]
        if len(spoken_lines) != len(indices):
            raise CaptionError(f"{caption.get('id', 'caption')} lines differ from its spoken chunk mapping")
        for index, line in zip(indices, spoken_lines):
            if index in spoken_text_by_segment[segment_id]:
                raise CaptionError(f"{segment_id} repeats spoken chunk {index}")
            spoken_text_by_segment[segment_id][index] = line
        for line_index, display_text in zip(display_only_indices, display_only_text):
            if lines[line_index] != display_text:
                raise CaptionError(f"{caption.get('id', 'caption')} display-only text differs from its rendered line")
        seen_chunks[segment_id].extend(indices)
        display_text_by_segment[segment_id].append("".join(lines))
        rendered.append((start, end, text))

    for segment in segments:
        segment_id = segment["id"]
        expected = list(range(len(segment["chunks"])))
        if sorted(seen_chunks[segment_id]) != expected:
            raise CaptionError(f"{segment_id} captions do not cover every spoken chunk exactly once")
        reconstructed_spoken = "".join(
            spoken_text_by_segment[segment_id][index] for index in expected
        )
        if reconstructed_spoken != "".join(segment["chunks"]):
            raise CaptionError(f"{segment_id} caption text does not preserve its spoken chunks")
        reconstructed_display = "".join(display_text_by_segment[segment_id])
        if re.sub(r"\s+", "", reconstructed_display) != re.sub(
            r"\s+", "", segment["display_subtitle"]
        ):
            raise CaptionError(f"{segment_id} exported captions do not preserve its display subtitle")
        tts = segment.get("tts_phonetic_text", "")
        for display_only in (segment.get("display_only_prefix"), segment.get("display_only_suffix")):
            if display_only and display_only in tts:
                raise CaptionError(f"{segment_id} display-only text must not enter TTS")
        if not segment.get("original_script") or not segment.get("editorial_note"):
            raise CaptionError(f"{segment_id} must retain original text and its editing note")

    rendered.sort(key=lambda cue: (cue[0], cue[1], cue[2]))
    previous_end = -1
    blocks = []
    for index, (start, end, text) in enumerate(rendered, 1):
        if start < previous_end:
            raise CaptionError("caption estimate windows overlap")
        previous_end = end
        blocks.append(f"{index}\n{timestamp(start)} --> {timestamp(end)}\n{text}")
    return "\n\n".join(blocks) + "\n", captions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--initialize-estimates",
        action="store_true",
        help="write an estimate-only audio-timing.json and export both platform SRT files",
    )
    args = parser.parse_args()
    try:
        segments_source = read_json(SEGMENTS_PATH)
        if args.initialize_estimates:
            if TIMING_PATH.exists():
                existing_timing = read_json(TIMING_PATH)
                if (
                    existing_timing.get("status") != "preview_estimate_pending_pcm"
                    or existing_timing.get("pcmMeasurement") is not None
                ):
                    raise CaptionError(
                        "refusing to replace a timing file after PCM measurement has started"
                    )
            timing = make_timing(segments_source)
            TIMING_PATH.write_text(
                json.dumps(timing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        else:
            timing = read_json(TIMING_PATH)
        srt, captions = validate_and_render(segments_source, timing)
        destinations = [WORK / "B站" / "captions.srt", WORK / "小红书" / "captions.srt"]
        for destination in destinations:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(srt, encoding="utf-8")
        print(
            json.dumps(
                {
                    "status": "preview_estimate_pending_pcm",
                    "captionCount": len(captions),
                    "sameWindowsForBothPlatforms": True,
                    "alignment": "estimated from declared windows and phrase length; not PCM measured or word aligned",
                    "files": [str(path.relative_to(WORK)) for path in destinations],
                    "timingFile": str(TIMING_PATH.relative_to(WORK)),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except (CaptionError, OSError, ValueError) as exc:
        print(f"export_captions.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
