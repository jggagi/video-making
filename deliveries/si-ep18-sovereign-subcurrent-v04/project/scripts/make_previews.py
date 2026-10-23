#!/usr/bin/env python3
"""Render the planned v04 native preview ranges against the current PCM master."""

from __future__ import annotations

import hashlib
import json
import subprocess
import wave
from pathlib import Path
from typing import Any


PROJECT = Path(__file__).resolve().parents[1]
DELIVERY = PROJECT.parent
REVIEW = DELIVERY / "review"
PLAN = json.loads((PROJECT / "render-plan.json").read_text(encoding="utf-8"))
DELIVERY_MANIFEST = json.loads((DELIVERY / "delivery.json").read_text(encoding="utf-8"))
INDEX_PATH = REVIEW / "native-preview-index.json"
SAMPLE_RATE = PLAN["capture"]["audioSampleRateHz"]
FPS = PLAN["composition"]["fps"]
SAMPLES_PER_FRAME = SAMPLE_RATE // FPS


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_delivery_file(relative: Any, label: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise RuntimeError(f"delivery.json has no {label} path")
    root = DELIVERY.resolve(strict=True)
    path = (DELIVERY / relative).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise RuntimeError(f"The {label} path must resolve to a file inside this delivery")
    return path


def validate_master(path: Path) -> dict[str, Any]:
    with wave.open(str(path), "rb") as stream:
        measured = {
            "sampleRateHz": stream.getframerate(),
            "channels": stream.getnchannels(),
            "sampleWidthBytes": stream.getsampwidth(),
            "sampleFramesPerChannel": stream.getnframes(),
            "compression": stream.getcomptype(),
        }
    expected_frames = PLAN["composition"]["durationInFrames"] * SAMPLES_PER_FRAME
    if measured != {
        "sampleRateHz": SAMPLE_RATE,
        "channels": PLAN["capture"]["audioChannels"],
        "sampleWidthBytes": 2,
        "sampleFramesPerChannel": expected_frames,
        "compression": "NONE",
    }:
        raise RuntimeError(f"Current PCM master does not match the planned format: {measured}")
    return measured


def main() -> int:
    if INDEX_PATH.exists():
        raise FileExistsError("Refusing to overwrite review/native-preview-index.json")
    if DELIVERY_MANIFEST.get("slug") != PLAN["work"]["id"] or DELIVERY_MANIFEST.get("title") != PLAN["work"]["title"]:
        raise RuntimeError("delivery.json identity differs from render-plan.json")
    master = resolve_delivery_file((DELIVERY_MANIFEST.get("audio") or {}).get("master"), "PCM master")
    master_format = validate_master(master)
    master_hash = sha256_file(master)
    REVIEW.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    for entry in PLAN["previews"]["nativeRanges"]:
        start = entry["startFrame"]
        end_exclusive = entry["endFrameExclusive"]
        if not (0 <= start < end_exclusive <= PLAN["composition"]["durationInFrames"]):
            raise RuntimeError(f"Invalid planned half-open preview range: {entry}")
        movie = REVIEW / f"motion-{start}-{end_exclusive - 1}.mp4"
        if movie.exists():
            raise FileExistsError(f"Refusing to overwrite existing preview {movie.name}")
        subprocess.run(
            ["node", str(PROJECT / "scripts" / "render.mjs"), "preview", str(start), str(end_exclusive)],
            check=True,
        )
        if not movie.is_file():
            raise RuntimeError(f"Preview renderer did not create {movie.name}")
        records.append({
            "path": str(movie.relative_to(DELIVERY)),
            "label": entry["label"],
            "absoluteFramesHalfOpen": [start, end_exclusive],
            "absoluteFramesInclusive": [start, end_exclusive - 1],
            "sha256": sha256_file(movie),
            "bytes": movie.stat().st_size,
            "audioSource": str(master.relative_to(DELIVERY)),
            "audioMasterSha256": master_hash,
            "audioSourceSamplesPerChannelHalfOpen": [start * SAMPLES_PER_FRAME, end_exclusive * SAMPLES_PER_FRAME],
        })

    report = {
        "schemaVersion": 1,
        "work": {"id": PLAN["work"]["id"], "title": PLAN["work"]["title"]},
        "intervalConvention": PLAN["previews"]["intervalConvention"],
        "previews": records,
        "master": {
            "path": str(master.relative_to(DELIVERY)),
            "sha256": master_hash,
            "format": master_format,
            "sourceClock": "Preview audio uses its absolute frame range from the current PCM master.",
        },
        "acceptance": {
            "representativeVisualReview": "PENDING",
            "continuousHumanReview": "PENDING",
            "targetDevicePlayback": "PENDING",
        },
    }
    with INDEX_PATH.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"index": str(INDEX_PATH.relative_to(DELIVERY)), "previewCount": len(records), "masterSha256": master_hash}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, wave.Error, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"make_previews: {exc}")
