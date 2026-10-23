#!/usr/bin/env python3
"""Measure the actual v04 encoded previews and collect their phone-scale frames."""

from __future__ import annotations

import hashlib
import json
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


PROJECT = Path(__file__).resolve().parents[1]
DELIVERY = PROJECT.parent
REVIEW = DELIVERY / "review"
OUTPUT = REVIEW / "native-preview-qa"
PLAN = json.loads((PROJECT / "render-plan.json").read_text(encoding="utf-8"))
INDEX = json.loads((REVIEW / "native-preview-index.json").read_text(encoding="utf-8"))
SAMPLE_RATE = PLAN["capture"]["audioSampleRateHz"]
SAMPLES_PER_FRAME = SAMPLE_RATE // PLAN["composition"]["fps"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(args: list[str]) -> bytes:
    return subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def resolve_preview(entry: dict) -> Path:
    relative = entry.get("path")
    if not isinstance(relative, str) or not relative:
        raise RuntimeError("Preview index entry has no relative movie path")
    path = (DELIVERY / relative).resolve(strict=True)
    if not path.is_relative_to(DELIVERY.resolve()) or not path.is_file():
        raise RuntimeError("Preview path escapes the current delivery")
    return path


def inspect_master(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as stream:
        if (stream.getframerate(), stream.getnchannels(), stream.getsampwidth(), stream.getnframes(), stream.getcomptype()) != (
            SAMPLE_RATE, PLAN["capture"]["audioChannels"], 2,
            PLAN["composition"]["durationInFrames"] * SAMPLES_PER_FRAME, "NONE"
        ):
            raise RuntimeError("PCM master format or duration differs from render-plan.json")
        samples = np.frombuffer(stream.readframes(stream.getnframes()), dtype="<i2")
    return samples.reshape((-1, PLAN["capture"]["audioChannels"])).astype(np.float64)


def selected_offsets(start: int, end_exclusive: int, anchors: list[int]) -> tuple[int, ...]:
    count = end_exclusive - start
    offsets = {0, count // 3, (2 * count) // 3, count - 1}
    offsets.update(frame - start for frame in anchors if start <= frame < end_exclusive)
    return tuple(sorted(offset for offset in offsets if 0 <= offset < count))


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError("Refusing to overwrite review/native-preview-qa")
    if INDEX.get("work", {}).get("id") != PLAN["work"]["id"]:
        raise RuntimeError("Preview index belongs to a different delivery")
    expected_previews = [
        (row["startFrame"], row["endFrameExclusive"], row["label"])
        for row in PLAN["previews"]["nativeRanges"]
    ]
    indexed_previews = [
        (*row.get("absoluteFramesHalfOpen", [None, None]), row.get("label"))
        for row in INDEX.get("previews", []) if isinstance(row, dict)
    ]
    if indexed_previews != expected_previews:
        raise RuntimeError("Preview index ranges or labels differ from render-plan.json")
    expected_master_sha = INDEX.get("master", {}).get("sha256")
    master_relative = INDEX.get("master", {}).get("path")
    if not isinstance(master_relative, str):
        raise RuntimeError("Preview index has no current master path")
    master_path = (DELIVERY / master_relative).resolve(strict=True)
    if not master_path.is_relative_to(DELIVERY.resolve()) or not master_path.is_file():
        raise RuntimeError("Preview master path escapes the current delivery")
    master_sha = sha256_file(master_path)
    if master_sha != expected_master_sha:
        raise RuntimeError("PCM master changed after the previews were rendered")
    master = inspect_master(master_path)
    ffprobe = "ffprobe"
    ffmpeg = "ffmpeg"
    OUTPUT.mkdir(parents=True, exist_ok=False)
    records = []
    contact_items: list[tuple[Path, int]] = []
    anchors = [
        PLAN["frames"]["anchors"]["confirm"],
        *PLAN["frames"]["anchors"]["silenceRangeHalfOpen"],
        PLAN["frames"]["anchors"]["doubleHeartbeat"],
        PLAN["frames"]["anchors"]["cyanEyeDetailFromFrame"],
    ]

    try:
        for entry in INDEX.get("previews", []):
            movie = resolve_preview(entry)
            if sha256_file(movie) != entry.get("sha256"):
                raise RuntimeError(f"Preview hash changed since indexing: {movie.name}")
            start, end_exclusive = entry.get("absoluteFramesHalfOpen", [None, None])
            if not isinstance(start, int) or not isinstance(end_exclusive, int) or not start < end_exclusive:
                raise RuntimeError(f"Invalid half-open range for {movie.name}")
            if entry.get("audioMasterSha256") != master_sha:
                raise RuntimeError(f"Preview {movie.name} is not bound to the current master hash")
            count = end_exclusive - start
            probe = json.loads(run([ffprobe, "-v", "error", "-count_frames", "-show_streams", "-of", "json", str(movie)]))
            video = next((stream for stream in probe.get("streams", []) if stream.get("codec_type") == "video"), {})
            frame_count = int(video.get("nb_read_frames", video.get("nb_frames", -1)))
            if (video.get("codec_name"), video.get("pix_fmt"), video.get("width"), video.get("height"), video.get("r_frame_rate"), frame_count) != (
                PLAN["capture"]["codec"], PLAN["capture"]["pixelFormat"], PLAN["composition"]["width"], PLAN["composition"]["height"],
                f"{PLAN['composition']['fps']}/1", count
            ):
                raise RuntimeError(f"Preview native video spec mismatch: {movie.name}")

            decoded = run([
                ffmpeg, "-v", "error", "-threads", "2", "-i", str(movie), "-map", "0:a:0",
                "-ar", str(SAMPLE_RATE), "-ac", str(PLAN["capture"]["audioChannels"]), "-f", "s16le", "pipe:1",
            ])
            channel_count = PLAN["capture"]["audioChannels"]
            if len(decoded) % (channel_count * 2):
                raise RuntimeError(f"Decoded preview audio is not PCM16 aligned: {movie.name}")
            preview_audio = np.frombuffer(decoded, dtype="<i2").reshape((-1, channel_count)).astype(np.float64)
            wanted_samples = count * SAMPLES_PER_FRAME
            reference = master[start * SAMPLES_PER_FRAME:end_exclusive * SAMPLES_PER_FRAME]
            if preview_audio.shape[0] < wanted_samples or reference.shape[0] != wanted_samples:
                raise RuntimeError(f"Preview audio does not cover its absolute source range: {movie.name}")
            preview_audio = preview_audio[:wanted_samples]
            correlation = float(np.corrcoef(reference.ravel(), preview_audio.ravel())[0, 1])
            if not np.isfinite(correlation) or correlation <= 0.99:
                raise RuntimeError(f"Preview audio source-clock correlation is too low for {movie.name}: {correlation}")

            offsets = selected_offsets(start, end_exclusive, anchors)
            frame_dir = OUTPUT / str(start)
            frame_dir.mkdir(parents=False, exist_ok=False)
            select = "+".join(f"eq(n,{offset})" for offset in offsets)
            run([
                ffmpeg, "-hide_banner", "-loglevel", "error", "-threads", "2", "-i", str(movie),
                "-vf", f"select='{select}',scale=360:640:flags=lanczos", "-fps_mode", "passthrough",
                "-start_number", "0", str(frame_dir / "frame_%03d.png"),
            ])
            images = sorted(frame_dir.glob("frame_*.png"))
            if len(images) != len(offsets):
                raise RuntimeError(f"Expected {len(offsets)} review frames from {movie.name}; got {len(images)}")
            absolute_frames = [start + offset for offset in offsets]
            contact_items.extend(zip(images, absolute_frames))
            records.append({
                "path": str(movie.relative_to(DELIVERY)),
                "label": entry.get("label"),
                "absoluteFramesHalfOpen": [start, end_exclusive],
                "frames": count,
                "nativeSize": [PLAN["composition"]["width"], PLAN["composition"]["height"]],
                "absoluteSourceClockCorrelation": correlation,
                "sha256": sha256_file(movie),
                "globalReviewFrames": absolute_frames,
            })

        contact_sheets = []
        for panel_number, offset in enumerate(range(0, len(contact_items), 8), 1):
            page = Image.new("RGB", (1440, 1320), "#101318")
            draw = ImageDraw.Draw(page)
            for index, (path, frame) in enumerate(contact_items[offset:offset + 8]):
                x, y = index % 4 * 360, index // 4 * 660
                with Image.open(path) as image:
                    page.paste(image.convert("RGB"), (x, y))
                draw.text((x + 8, y + 642), f"F{frame} / {frame / PLAN['composition']['fps']:.3f}s", fill="white")
            name = f"contact-{panel_number}.jpg"
            page.save(OUTPUT / name, quality=92)
            contact_sheets.append(name)

        report = {
            "status": "MEASUREMENTS_PASS",
            "previews": records,
            "contactSheets": contact_sheets,
            "representativeVisualReview": "PENDING",
            "continuousHumanReview": "PENDING",
            "targetDevicePlayback": "PENDING",
            "scope": "Native encoded media and absolute PCM source-clock measurements; collected frames are evidence for review, not a human visual or listening acceptance claim.",
        }
        (OUTPUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": report["status"], "previewCount": len(records), "phoneFrames": len(contact_items), "contactSheets": contact_sheets}, ensure_ascii=False, indent=2))
        return 0
    except Exception:
        import shutil
        shutil.rmtree(OUTPUT, ignore_errors=True)
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError, wave.Error, ValueError) as exc:
        raise SystemExit(f"review_previews: {exc}")
