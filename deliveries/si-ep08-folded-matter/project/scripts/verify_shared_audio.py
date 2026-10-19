#!/usr/bin/env python3
"""Compare encoded MP4 AAC against the existing measured PCM master at zero offset."""

from __future__ import annotations

import argparse
from array import array
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import wave
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DELIVERY_DIR = PROJECT_DIR.parent
REVIEW_DIR = DELIVERY_DIR / "review"
FPS = 60
SAMPLE_RATE = 48_000
CHANNELS = 2
SAMPLES_PER_CHANNEL = 5_760_000
CORRELATION_FLOOR = 0.98
MAX_ABS_GAIN_DB = 0.5
LAYOUTS = {
    "landscape": ("bilibili", 3840, 2160),
    "portrait": ("xiaohongshu", 2160, 3840),
}


class AudioVerificationError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AudioVerificationError(f"cannot read {label}: {exc}") from None
    if not isinstance(value, dict):
        raise AudioVerificationError(f"{label} must contain an object")
    return value


def contained_path(base: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise AudioVerificationError(f"{label} path is missing")
    path = (base / value).resolve()
    try:
        path.relative_to(base.resolve())
    except ValueError:
        raise AudioVerificationError(f"{label} path escapes its owning directory") from None
    return path


def decode_pcm(ffmpeg: str, media: Path) -> array:
    command = [
        ffmpeg, "-hide_banner", "-nostdin", "-v", "error", "-i", str(media),
        "-map", "0:a:0", "-vn", "-ac", str(CHANNELS), "-ar", str(SAMPLE_RATE),
        "-acodec", "pcm_s16le", "-f", "s16le", "pipe:1",
    ]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=1800)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AudioVerificationError(f"ffmpeg audio decode failed to run: {exc}") from None
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise AudioVerificationError(f"ffmpeg decode failed for {media.name}: {detail[-1600:] or result.returncode}")
    if len(result.stdout) % 2:
        raise AudioVerificationError(f"ffmpeg returned an odd number of PCM bytes for {media.name}")
    samples = array("h")
    samples.frombytes(result.stdout)
    if sys.byteorder != "little":
        samples.byteswap()
    return samples


def load_master(path: Path, expected_hash: str) -> tuple[array, dict[str, Any]]:
    try:
        with wave.open(str(path), "rb") as wav:
            observed = {
                "sample_rate": wav.getframerate(),
                "channels": wav.getnchannels(),
                "sample_width_bytes": wav.getsampwidth(),
                "samples_per_channel": wav.getnframes(),
                "compression": wav.getcomptype(),
            }
            raw = wav.readframes(wav.getnframes())
    except (OSError, wave.Error) as exc:
        raise AudioVerificationError(f"cannot read PCM master: {exc}") from None
    if (observed["sample_rate"], observed["channels"], observed["sample_width_bytes"], observed["samples_per_channel"], observed["compression"]) != (SAMPLE_RATE, CHANNELS, 2, SAMPLES_PER_CHANNEL, "NONE"):
        raise AudioVerificationError(f"PCM master format is not exact: {observed}")
    if len(raw) != SAMPLES_PER_CHANNEL * CHANNELS * 2:
        raise AudioVerificationError("PCM master byte count does not match its declared samples")
    digest = sha256_file(path)
    observed["sha256"] = digest
    if digest != expected_hash:
        raise AudioVerificationError(f"PCM master SHA-256 differs from delivery.json: {digest}")
    pcm = array("h")
    pcm.frombytes(raw)
    if sys.byteorder != "little":
        pcm.byteswap()
    return pcm, observed


def audio_windows(timing: dict[str, Any]) -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []
    segments = timing.get("segments")
    events = timing.get("sfxEvents")
    if not isinstance(segments, list) or len(segments) != 10:
        raise AudioVerificationError("audio-timing.json must contain ten measured PCM segments")
    if not isinstance(events, list) or not events:
        raise AudioVerificationError("audio-timing.json must contain timed SFX windows")
    for segment in segments:
        if not isinstance(segment, dict):
            raise AudioVerificationError("measured audio segment is not an object")
        start, end = segment.get("voiceStartSample"), segment.get("voiceEndSampleExclusive")
        if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= SAMPLES_PER_CHANNEL:
            raise AudioVerificationError(f"invalid measured voice span for {segment.get('id')}")
        windows.append({"kind": "voice", "id": segment.get("id"), "start_sample": start, "end_sample_exclusive": end})
    for event in events:
        if not isinstance(event, dict) or event.get("silentMarker") or event.get("kind") == "silence":
            continue
        start = event.get("sampleIndex")
        duration = event.get("durationSeconds")
        if not isinstance(start, int) or not isinstance(duration, (int, float)) or duration <= 0:
            continue
        end = min(SAMPLES_PER_CHANNEL, start + round(float(duration) * SAMPLE_RATE))
        if 0 <= start < end:
            windows.append({"kind": "sfx", "id": event.get("id"), "start_sample": start, "end_sample_exclusive": end})
    if not windows:
        raise AudioVerificationError("no measured voice or SFX comparison windows were available")
    return windows


def channel_metrics(master: array, decoded: array, channel: int, start: int, end: int) -> dict[str, Any]:
    count = end - start
    sum_master = sum_decoded = sum_master_sq = sum_decoded_sq = sum_product = 0.0
    for index in range(start, end):
        offset = index * CHANNELS + channel
        x, y = master[offset], decoded[offset]
        sum_master += x
        sum_decoded += y
        sum_master_sq += x * x
        sum_decoded_sq += y * y
        sum_product += x * y
    variance_master = sum_master_sq - sum_master * sum_master / count
    variance_decoded = sum_decoded_sq - sum_decoded * sum_decoded / count
    covariance = sum_product - sum_master * sum_decoded / count
    correlation = covariance / math.sqrt(variance_master * variance_decoded) if variance_master > 0 and variance_decoded > 0 else None
    rms_master = math.sqrt(sum_master_sq / count)
    rms_decoded = math.sqrt(sum_decoded_sq / count)
    gain_db = 20 * math.log10(rms_decoded / rms_master) if rms_master > 0 and rms_decoded > 0 else None
    return {
        "channel": "left" if channel == 0 else "right",
        "pearson_zero_offset": correlation,
        "rms_gain_db": gain_db,
        "correlation_pass": correlation is not None and correlation >= CORRELATION_FLOOR,
        "gain_pass": gain_db is not None and abs(gain_db) <= MAX_ABS_GAIN_DB,
    }


def probe_audio(ffprobe: str, media: Path) -> dict[str, Any]:
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "a:0", "-show_streams", "-show_format", "-of", "json", str(media)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AudioVerificationError(f"ffprobe failed to run for {media.name}: {exc}") from None
    if result.returncode:
        raise AudioVerificationError(f"ffprobe failed for {media.name}: {result.stderr.decode('utf-8', errors='replace')[-1200:]}")
    try:
        data = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise AudioVerificationError(f"ffprobe returned invalid JSON for {media.name}") from None
    streams = data.get("streams") if isinstance(data, dict) else None
    if not isinstance(streams, list) or not streams:
        raise AudioVerificationError(f"no audio stream found in {media.name}")
    stream = streams[0]
    checks = {
        "aac": stream.get("codec_name") == "aac",
        "48khz": stream.get("sample_rate") == str(SAMPLE_RATE),
        "stereo": stream.get("channels") == CHANNELS,
    }
    return {"stream": stream, "checks": checks}


def report_path() -> Path:
    base = REVIEW_DIR / "shared-audio-correlation.json"
    if not base.exists():
        return base
    for revision in range(2, 10000):
        candidate = base.with_name(f"shared-audio-correlation-r{revision:02d}.json")
        if not candidate.exists():
            return candidate
    raise AudioVerificationError("no unused shared-audio report name is available")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", choices=("landscape", "portrait", "both"), default="both")
    parser.add_argument("--no-write", action="store_true", help="Print the report without saving it.")
    args = parser.parse_args()
    try:
        manifest = read_json(DELIVERY_DIR / "delivery.json", "delivery.json")
        timing = read_json(PROJECT_DIR / "audio-timing.json", "audio-timing.json")
        audio_spec = manifest.get("audio", {})
        master_path = contained_path(DELIVERY_DIR, audio_spec.get("master"), "shared PCM master")
        master, master_info = load_master(master_path, audio_spec.get("sha256"))
        windows = audio_windows(timing)
        ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
        if not ffmpeg or not ffprobe:
            raise AudioVerificationError("ffmpeg and ffprobe must already be available on PATH")
        layouts = ("landscape", "portrait") if args.layout == "both" else (args.layout,)
        tracks: list[dict[str, Any]] = []
        for layout in layouts:
            key, width, height = LAYOUTS[layout]
            output = manifest.get("outputs", {}).get(key, {})
            media = contained_path(DELIVERY_DIR, output.get("path"), f"{layout} MP4")
            if not media.is_file():
                raise AudioVerificationError(f"final {layout} MP4 is missing: {media}")
            if (output.get("width"), output.get("height")) != (width, height):
                raise AudioVerificationError(f"delivery.json declares the wrong {layout} dimensions")
            probe = probe_audio(ffprobe, media)
            decoded = decode_pcm(ffmpeg, media)
            sample_count = len(decoded) // CHANNELS
            record: dict[str, Any] = {
                "layout": layout,
                "path": media.relative_to(DELIVERY_DIR).as_posix(),
                "sha256": sha256_file(media),
                "decoded_samples_per_channel": sample_count,
                "codec_padding_after_master_samples": max(0, sample_count - SAMPLES_PER_CHANNEL),
                "audio_stream": {key: probe["stream"].get(key) for key in ("codec_name", "sample_rate", "channels", "channel_layout", "duration", "nb_frames")},
                "audio_stream_checks": probe["checks"],
                "windows": [],
                "status": "PASS",
            }
            if sample_count < SAMPLES_PER_CHANNEL:
                record["status"] = "FAIL"
                record["failure"] = f"decoded AAC has only {sample_count} samples per channel"
            else:
                for window in windows:
                    start, end = window["start_sample"], window["end_sample_exclusive"]
                    channels = [channel_metrics(master, decoded, channel, start, end) for channel in range(CHANNELS)]
                    passed = all(channel["correlation_pass"] and channel["gain_pass"] for channel in channels)
                    record["windows"].append({**window, "status": "PASS" if passed else "FAIL", "channels": channels})
                    if not passed:
                        record["status"] = "FAIL"
            if not all(probe["checks"].values()):
                record["status"] = "FAIL"
            tracks.append(record)

        overall = "PASS" if all(track["status"] == "PASS" for track in tracks) else "FAIL"
        report = {
            "status": overall,
            "method": "Decode AAC to 48 kHz stereo PCM16 and compare the declared measured voice spans and authored audible SFX windows at their exact sample offsets. No offset search or correlation-based alignment is performed.",
            "thresholds": {"pearson_zero_offset_minimum": CORRELATION_FLOOR, "absolute_rms_gain_db_maximum": MAX_ABS_GAIN_DB},
            "master": {"path": master_path.relative_to(DELIVERY_DIR).as_posix(), **master_info},
            "inputs": {
                "delivery_json_sha256": sha256_file(DELIVERY_DIR / "delivery.json"),
                "audio_timing_json_sha256": sha256_file(PROJECT_DIR / "audio-timing.json"),
            },
            "tracks": tracks,
            "limitations": [
                "AAC similarity is not perceptual or human listening acceptance.",
                "No time-shift search is used; a failed zero-offset window requires investigation.",
                "Codec padding is recorded and omitted only from source-length comparison; media and master are unchanged.",
            ],
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if not args.no_write:
            REVIEW_DIR.mkdir(parents=True, exist_ok=True)
            target = report_path()
            temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
            temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, target)
            print(f"Report: {target}")
        return 0 if overall == "PASS" else 1
    except (AudioVerificationError, OSError, KeyError, TypeError) as exc:
        print(f"[verify-shared-audio] ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
