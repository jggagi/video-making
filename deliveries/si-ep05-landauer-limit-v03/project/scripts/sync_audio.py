#!/usr/bin/env python3
"""Map EP05 subtitle text over measured PCM spans (estimated phrase timing only)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import build_audio as audio


PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT.parent
TIMING_PATH = PROJECT / "audio-timing.json"
REPORT_PATH = WORK / "review" / "audio-caption-alignment.json"
OUTPUTS = [WORK / "B站" / "captions.srt", WORK / "小红书" / "captions.srt"]
ARCHIVE_NAMES = ("bilibili", "xiaohongshu")
MAX_CHARS_PER_LINE = 14
PHRASE_FIELDS = ("subtitle_phrases", "caption_phrases", "subtitle_units", "phrases", "chunks")
PUNCTUATION = set("，。！？；：,.!?;:")
CAPTION_STATUS = "measured_pcm_with_estimated_phrase_timing"


class SyncError(RuntimeError):
    pass


def no_linebreaks(text: str) -> str:
    return text.replace("\r", "").replace("\n", "")


def fallback_phrases(display: str) -> list[str]:
    phrases: list[str] = []
    for authored_line in display.replace("\r", "").split("\n"):
        current = ""
        for char in authored_line:
            current += char
            if char in PUNCTUATION:
                if current:
                    phrases.append(current)
                    current = ""
        if current:
            phrases.append(current)
    return phrases


def supplied_phrases(segment: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    """Return ordered subtitle units with editorial prefix/suffix marked display-only."""
    display = segment["display_subtitle"]
    phrases: list[str] | None = None
    source = "display_subtitle punctuation and line breaks"
    for field in PHRASE_FIELDS:
        if field not in segment:
            continue
        value = segment[field]
        if not isinstance(value, list) or not value or any(not isinstance(item, str) for item in value):
            raise SyncError(f"{segment['id']} {field} must be a non-empty string list")
        phrases = value
        source = field
        break
    if phrases is None:
        phrases = fallback_phrases(display)

    prefix = segment.get("display_only_prefix", "")
    suffix = segment.get("display_only_suffix", "")
    if not isinstance(prefix, str) or not isinstance(suffix, str):
        raise SyncError(f"{segment['id']} display_only_prefix/suffix must be strings")
    units = ([{"text": prefix, "displayOnly": True, "kind": "display_only_prefix"}] if prefix else [])
    units.extend({"text": phrase, "displayOnly": False, "kind": source} for phrase in phrases)
    units.extend([{"text": suffix, "displayOnly": True, "kind": "display_only_suffix"}] if suffix else [])
    reconstructed = "".join(unit["text"] for unit in units)
    if no_linebreaks(reconstructed) != no_linebreaks(display):
        raise SyncError(f"{segment['id']} subtitle units do not preserve every display_subtitle character")
    if prefix or suffix:
        source = f"{source} plus display-only prefix/suffix"
    return units, source


def chinese_count(text: str) -> int:
    return sum('\u3400' <= char <= '\u9fff' for char in text)


def split_units(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for unit in units:
        current = ""
        for char in unit["text"]:
            if '\u3400' <= char <= '\u9fff' and chinese_count(current) >= MAX_CHARS_PER_LINE:
                lines.append({"text": current, "displayOnly": unit["displayOnly"], "kind": unit["kind"]})
                current = ""
            current += char
        if current:
            lines.append({"text": current, "displayOnly": unit["displayOnly"], "kind": unit["kind"]})
    return lines


def groups_from_lines(lines: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    if not lines:
        raise SyncError("display_subtitle produced no visible phrase units")
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_kind: bool | None = None
    for line in lines:
        kind = bool(line["displayOnly"])
        if current and (kind != current_kind or len(current) == 2):
            groups.append(current)
            current = []
        current.append(line)
        current_kind = kind
    if current:
        groups.append(current)
    return groups


def boundaries(start: int, end: int, weights: list[int]) -> list[int]:
    if end <= start:
        raise SyncError("measured active PCM span is empty")
    if end - start < len(weights):
        raise SyncError("measured PCM span is too short to assign non-empty sample windows to all caption phrases")
    total = sum(weights)
    result = [start]
    cumulative = 0
    for weight in weights[:-1]:
        cumulative += weight
        candidate = start + round((end - start) * cumulative / total)
        lower = result[-1] + 1
        upper = end - (len(weights) - len(result))
        result.append(max(lower, min(upper, candidate)))
    result.append(end)
    return result


def frame_edges(sample_edges: list[int], segment: dict[str, Any]) -> list[int]:
    """Convert sample edges to shared frame boundaries, clamped to the declared window."""
    declared_start = int(segment["startFrame"])
    declared_end = int(segment["endFrame"])
    if declared_end <= declared_start:
        raise SyncError(f"{segment['id']} has an empty declared frame window")
    count = len(sample_edges) - 1
    first = max(declared_start, sample_edges[0] // audio.SAMPLES_PER_FRAME)
    final = min(declared_end, (sample_edges[-1] + audio.SAMPLES_PER_FRAME - 1) // audio.SAMPLES_PER_FRAME)
    if final - first < count:
        raise SyncError(f"{segment['id']} declared frame window is too short for non-overlapping captions")
    result = [first]
    for index, sample in enumerate(sample_edges[1:-1], start=1):
        # Round each internal sample edge once so adjacent cues share one frame boundary.
        candidate = (sample + audio.SAMPLES_PER_FRAME // 2) // audio.SAMPLES_PER_FRAME
        lower = result[-1] + 1
        upper = final - (count - index)
        result.append(max(lower, min(upper, candidate)))
    result.append(final)
    return result


def timestamp(sample: int, *, ceil: bool = False) -> str:
    if ceil:
        millis = (sample * 1000 + audio.SAMPLE_RATE - 1) // audio.SAMPLE_RATE
    else:
        millis = (sample * 1000) // audio.SAMPLE_RATE
    return timestamp_millis(millis)


def timestamp_millis(millis: int) -> str:
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def srt_time_edges(sample_edges: list[int]) -> list[str]:
    """Round each shared PCM edge once, preventing adjacent SRT cues from overlapping."""
    values = [(sample_edges[0] * 1000) // audio.SAMPLE_RATE]
    for sample in sample_edges[1:-1]:
        values.append((sample * 1000 + audio.SAMPLE_RATE // 2) // audio.SAMPLE_RATE)
    values.append((sample_edges[-1] * 1000 + audio.SAMPLE_RATE - 1) // audio.SAMPLE_RATE)
    if any(right <= left for left, right in zip(values, values[1:])):
        raise SyncError("sample-accurate caption cues collapse to a zero-duration SRT timestamp")
    return [timestamp_millis(value) for value in values]


def build_captions() -> tuple[str, dict[str, Any], dict[str, Any]]:
    segments = audio.load_segments()
    try:
        timing = json.loads(TIMING_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SyncError(f"cannot read audio-timing.json: {exc}") from None
    if not isinstance(timing, dict) or timing.get("samplesPerChannel") != audio.TOTAL_SAMPLES:
        raise SyncError("audio-timing.json does not describe the exact EP05 master length")
    source_hashes = timing.get("sourceHashes", {})
    if source_hashes.get("segmentsJson") != audio.sha256_file(audio.SEGMENTS_PATH):
        raise SyncError("segments.json changed after measured audio timing was written")
    measured = {item.get("id"): item for item in timing.get("segments", []) if isinstance(item, dict)}
    if set(measured) != {segment["id"] for segment in segments}:
        raise SyncError("audio-timing.json does not contain all ten measured segment spans")

    srt: list[str] = []
    report_captions: list[dict[str, Any]] = []
    timing_captions: list[dict[str, Any]] = []
    cue_number = 1
    for segment in segments:
        sid = segment["id"]
        span = measured[sid]
        start_sample = int(span["voiceStartSample"])
        end_sample = int(span["voiceEndSampleExclusive"])
        units, phrase_source = supplied_phrases(segment)
        lines = split_units(units)
        if any(chinese_count(line["text"]) > MAX_CHARS_PER_LINE for line in lines):
            raise SyncError(f"{sid} caption line exceeds {MAX_CHARS_PER_LINE} characters")
        groups = groups_from_lines(lines)
        for group in groups:
            if len(group) > 2 or any(chinese_count(line["text"]) > MAX_CHARS_PER_LINE for line in group):
                raise SyncError(f"{sid} caption exceeds two lines or {MAX_CHARS_PER_LINE} characters per line")
        weights = [max(1, sum(not char.isspace() for line in group for char in line["text"])) for group in groups]
        sample_edges = boundaries(start_sample, end_sample, weights)
        frames = frame_edges(sample_edges, segment)
        srt_times = srt_time_edges(sample_edges)
        for index, group in enumerate(groups):
            text = "\n".join(line["text"] for line in group)
            start, end = sample_edges[index], sample_edges[index + 1]
            start_frame, end_frame = frames[index], frames[index + 1]
            if end <= start or end_frame <= start_frame:
                raise SyncError(f"{sid} caption {index + 1} has no sample/frame duration")
            display_only = all(line["displayOnly"] for line in group)
            srt.extend((str(cue_number), f"{srt_times[index]} --> {srt_times[index + 1]}", text, ""))
            report_captions.append({
                "id": f"{sid}-C{index + 1:02d}",
                "segmentId": sid,
                "startSample": start,
                "endSampleExclusive": end,
                "startFrame": start_frame,
                "endFrame": end_frame,
                "start": srt_times[index],
                "end": srt_times[index + 1],
                "text": text,
                "displayOnly": display_only,
                "phraseSource": phrase_source,
                "alignment": "estimated phrase timing from measured active PCM samples; not word aligned",
            })
            timing_captions.append({
                "segmentId": sid,
                "startFrame": start_frame,
                "endFrame": end_frame,
                "text": text,
            })
            cue_number += 1

    content = "\n".join(srt).rstrip() + "\n"
    expected = "".join(segment["display_subtitle"] for segment in segments)
    actual = "".join(item["text"].replace("\n", "") for item in report_captions)
    if no_linebreaks(actual) != no_linebreaks(expected):
        raise SyncError("generated captions do not preserve all display subtitle text")
    report = {
        "status": CAPTION_STATUS,
        "method": "Subtitle units are divided proportionally across each segment's measured active PCM sample span. Editorial display-only prefix/suffix units are included but are not narrated. Frame boundaries are derived from sample counts and rounded once at shared cue edges. This is estimated phrase timing, not ASR or word alignment.",
        "maxChineseCharactersPerLine": MAX_CHARS_PER_LINE,
        "maxLines": 2,
        "allDisplayTextPreserved": True,
        "segments": [{
            "id": segment["id"],
            "declaredStartFrame": int(segment["startFrame"]),
            "declaredEndFrame": int(segment["endFrame"]),
            "voiceStartSample": int(measured[segment["id"]]["voiceStartSample"]),
            "voiceEndSampleExclusive": int(measured[segment["id"]]["voiceEndSampleExclusive"]),
            "displaySubtitleCharacters": len(no_linebreaks(segment["display_subtitle"])),
        } for segment in segments],
        "captions": report_captions,
        "limitation": "Text fidelity is checked against display_subtitle; pronunciation, phrase timing, and human listening are not evaluated.",
    }
    updated_timing = dict(timing)
    updated_timing["status"] = CAPTION_STATUS
    updated_timing["captionTimingMethod"] = report["method"]
    updated_timing["captions"] = timing_captions
    return content, report, updated_timing


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp.write_text(content, encoding="utf-8")
    temp.replace(path)


def archive_existing_estimate(path: Path, platform: str, new_content: str) -> Path | None:
    if not path.exists() or path.read_text(encoding="utf-8") == new_content:
        return None
    archive_dir = WORK / "review"
    archive_dir.mkdir(parents=True, exist_ok=True)
    base = archive_dir / f"estimated-captions-before-pcm-{platform}.srt"
    target = base
    suffix = 2
    while target.exists():
        if target.read_bytes() == path.read_bytes():
            return target
        target = base.with_name(f"{base.stem}-{suffix}{base.suffix}")
        suffix += 1
    atomic_write(target, path.read_text(encoding="utf-8"))
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="atomically write captions, audio-timing captions, and review report")
    mode.add_argument("--audit", action="store_true", help="print the estimated caption map without writing files")
    parser.set_defaults(audit=True)
    args = parser.parse_args()
    try:
        content, report, updated_timing = build_captions()
        if args.write:
            for path, platform in zip(OUTPUTS, ARCHIVE_NAMES):
                archive_existing_estimate(path, platform, content)
            for path in OUTPUTS:
                atomic_write(path, content)
            atomic_write(TIMING_PATH, json.dumps(updated_timing, ensure_ascii=False, indent=2) + "\n")
            atomic_write(REPORT_PATH, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            print(json.dumps({
                "status": report["status"],
                "outputs": [str(path.relative_to(WORK)) for path in OUTPUTS],
                "timing": str(TIMING_PATH.relative_to(PROJECT)),
                "report": str(REPORT_PATH.relative_to(WORK)),
                "captionCount": len(report["captions"]),
            }, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({"status": report["status"], "captionCount": len(report["captions"]), "preview": report["captions"][:5]}, ensure_ascii=False, indent=2))
        return 0
    except (SyncError, audio.AudioBuildError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"sync_audio.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
