#!/usr/bin/env python3
"""Export the measured EP04 caption windows to identical platform SRT files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT.parent
SEGMENTS_PATH = PROJECT / "segments.json"
TIMING_PATH = PROJECT / "audio-timing.json"
FPS = 60
TOTAL_FRAMES = 7_200


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


def validate_and_render() -> tuple[str, list[dict[str, Any]]]:
    source = read_json(SEGMENTS_PATH)
    timing = read_json(TIMING_PATH)
    if (timing.get("fps"), timing.get("sampleRate"), timing.get("samplesPerChannel")) != (FPS, 48_000, 5_760_000):
        raise CaptionError("audio-timing.json is not the measured 120-second, 60 fps PCM schedule")
    segments = source.get("segments")
    measured = timing.get("segments")
    captions = timing.get("captions")
    if not isinstance(segments, list) or len(segments) != 10 or not isinstance(measured, list) or len(measured) != 10:
        raise CaptionError("all ten measured narration segments are required before caption export")
    if not isinstance(captions, list) or not captions:
        raise CaptionError("audio-timing.json has no measured caption windows")
    measured_by_id = {item.get("id"): item for item in measured}
    seen_chunks: dict[str, list[int]] = {item["id"]: [] for item in segments}
    rendered: list[tuple[int, int, str]] = []
    for caption in captions:
        segment_id = caption.get("segmentId")
        if segment_id not in seen_chunks:
            raise CaptionError(f"caption references unknown segment {segment_id!r}")
        if not isinstance(caption.get("text"), str) or not caption["text"].strip():
            raise CaptionError(f"{caption.get('id', 'caption')} has empty text")
        lines = caption["text"].splitlines()
        if not 1 <= len(lines) <= 2:
            raise CaptionError(f"{caption.get('id', 'caption')} must have one or two display lines")
        if any(chinese_count(line) > 14 for line in lines):
            raise CaptionError(f"{caption.get('id', 'caption')} exceeds 14 Chinese characters on a line")
        start = caption.get("startFrame")
        end = caption.get("endFrame")
        if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= TOTAL_FRAMES:
            raise CaptionError(f"{caption.get('id', 'caption')} has an invalid measured frame window")
        if segment_id not in measured_by_id:
            raise CaptionError(f"{segment_id} has no measured PCM timing")
        if caption.get("displayHoldUntilFrame") is not None:
            hold = caption["displayHoldUntilFrame"]
            if not isinstance(hold, int) or not end <= hold <= TOTAL_FRAMES:
                raise CaptionError(f"{caption.get('id', 'caption')} has an invalid display-only hold")
            end = hold
        indices = caption.get("sourceChunkIndices")
        if not isinstance(indices, list) or not indices or any(not isinstance(index, int) for index in indices):
            raise CaptionError(f"{caption.get('id', 'caption')} has no source phrase mapping")
        seen_chunks[segment_id].extend(indices)
        rendered.append((start, end, caption["text"]))

    caption_text_by_segment: dict[str, dict[int, str]] = {item["id"]: {} for item in segments}
    for caption in captions:
        lines = caption["text"].splitlines()
        indices = caption["sourceChunkIndices"]
        if len(lines) != len(indices):
            raise CaptionError(f"{caption.get('id', 'caption')} line count differs from its source phrase mapping")
        for index, line in zip(indices, lines):
            if index in caption_text_by_segment[caption["segmentId"]]:
                raise CaptionError(f"{caption['segmentId']} repeats source phrase {index}")
            caption_text_by_segment[caption["segmentId"]][index] = line

    for segment in segments:
        segment_id = segment["id"]
        expected = list(range(len(segment["chunks"])))
        if sorted(seen_chunks[segment_id]) != expected:
            raise CaptionError(f"{segment_id} captions do not cover each supplied phrase exactly once")
        reconstructed = "".join(caption_text_by_segment[segment_id][index] for index in expected)
        if "".join(reconstructed.split()) != "".join("".join(segment["chunks"]).split()):
            raise CaptionError(f"{segment_id} caption text does not preserve its supplied phrase chunks")
        if segment_id == "S10" and "[EP.05 算力的热力学终局]" not in reconstructed:
            raise CaptionError("S10 EP05 bracket text is missing from the display captions")

    rendered.sort(key=lambda cue: (cue[0], cue[1], cue[2]))
    blocks = []
    for index, (start, end, text) in enumerate(rendered, 1):
        blocks.append(f"{index}\n{timestamp(start)} --> {timestamp(end)}\n{text}")
    return "\n\n".join(blocks) + "\n", captions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        srt, captions = validate_and_render()
        destinations = [WORK / "B站" / "captions.srt", WORK / "小红书" / "captions.srt"]
        for destination in destinations:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(srt, encoding="utf-8")
        print(json.dumps({
            "status": "captions_exported",
            "captionCount": len(captions),
            "sameWindowsForBothPlatforms": True,
            "alignment": "estimated phrase timing from measured PCM; not word aligned",
            "displayOnlyText": [
                text for caption in captions for text in caption.get("displayOnlyText", [])
            ],
            "files": [str(path.relative_to(WORK)) for path in destinations],
        }, ensure_ascii=False, indent=2))
        return 0
    except (CaptionError, OSError, ValueError) as exc:
        print(f"export_captions.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
