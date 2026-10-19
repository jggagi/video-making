#!/usr/bin/env python3
"""Compare final MP4 AAC audio against the shared PCM master at zero offset."""

from __future__ import annotations

import argparse
from array import array
import hashlib
import json
import math
import shutil
import subprocess
import sys
import wave
from pathlib import Path
from typing import Any

import build_audio as audio


PROJECT_DIR = Path(__file__).resolve().parents[1]
DELIVERY_DIR = PROJECT_DIR.parent
MANIFEST_PATH = DELIVERY_DIR / "delivery.json"
REPORT_PATH = DELIVERY_DIR / "review" / "shared-audio-correlation.json"
EXPECTED_SAMPLE_RATE = 48_000
EXPECTED_CHANNELS = 2
EXPECTED_SAMPLES = 5_760_000
CORRELATION_FLOOR = 0.98
GAIN_TOLERANCE_DB = 0.5


class VerificationError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(DELIVERY_DIR.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_delivery_path(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise VerificationError(f"{label} path is missing from delivery.json")
    candidate = (DELIVERY_DIR / value).resolve()
    try:
        candidate.relative_to(DELIVERY_DIR.resolve())
    except ValueError:
        raise VerificationError(f"{label} path escapes the delivery folder") from None
    return candidate


def pcm_array(raw: bytes) -> array:
    if len(raw) % 2:
        raise VerificationError("decoded PCM byte count is not aligned to signed 16-bit samples")
    samples = array("h")
    samples.frombytes(raw)
    if sys.byteorder != "little":
        samples.byteswap()
    return samples


def load_master(path: Path, samples_per_channel: int) -> array:
    try:
        with wave.open(str(path), "rb") as wav:
            channels = wav.getnchannels()
            sample_rate = wav.getframerate()
            sample_width = wav.getsampwidth()
            frame_count = wav.getnframes()
            compression = wav.getcomptype()
            if (channels, sample_rate, sample_width, compression) != (EXPECTED_CHANNELS, EXPECTED_SAMPLE_RATE, 2, "NONE"):
                raise VerificationError(
                    f"master WAV format must be {EXPECTED_CHANNELS}-channel 48 kHz PCM16; got "
                    f"channels={channels}, rate={sample_rate}, width={sample_width}, compression={compression}"
                )
            if frame_count != samples_per_channel:
                raise VerificationError(
                    f"master WAV sample count {frame_count} differs from delivery.json {samples_per_channel}"
                )
            raw = wav.readframes(samples_per_channel)
    except (OSError, wave.Error) as exc:
        raise VerificationError(f"cannot read shared PCM master: {exc}") from None
    expected_bytes = samples_per_channel * EXPECTED_CHANNELS * 2
    if len(raw) != expected_bytes:
        raise VerificationError(f"master WAV returned {len(raw)} bytes; expected {expected_bytes}")
    return pcm_array(raw)


def verify_master_silence(path: Path) -> dict[str, Any]:
    start = audio.SILENCE_START_SAMPLE
    end = audio.SILENCE_END_SAMPLE
    with wave.open(str(path), "rb") as wav:
        wav.setpos(start)
        raw = wav.readframes(end - start)
    if len(raw) != (end - start) * EXPECTED_CHANNELS * 2:
        raise VerificationError("shared PCM master ended inside the authored absolute-silence window")
    samples = pcm_array(raw)
    peak = max((abs(value) for value in samples), default=0)
    if peak:
        raise VerificationError(f"shared PCM master is not digitally silent in [{start}, {end}); peak={peak}")
    return {
        "start_frame": audio.SILENCE_START_FRAME,
        "end_frame_exclusive": audio.SILENCE_END_FRAME,
        "start_sample": start,
        "end_sample_exclusive": end,
        "peak_pcm16": 0,
        "exact_zero": True,
    }


def decode_aac(ffmpeg: str, path: Path) -> bytes:
    command = [
        ffmpeg, "-hide_banner", "-nostdin", "-v", "error", "-i", str(path),
        "-map", "0:a:0", "-vn", "-ac", str(EXPECTED_CHANNELS), "-ar", str(EXPECTED_SAMPLE_RATE),
        "-acodec", "pcm_s16le", "-f", "s16le", "pipe:1",
    ]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    except OSError as exc:
        raise VerificationError(f"could not start ffmpeg for {relative(path)}: {exc}") from None
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise VerificationError(f"ffmpeg could not decode {relative(path)} (exit {result.returncode}): {detail[-1500:]}")
    return result.stdout


def channel_metrics(master: array, decoded: array, channel: int, start: int, end: int) -> dict[str, Any]:
    count = end - start
    sum_x = sum_y = sum_x2 = sum_y2 = sum_xy = 0.0
    for frame in range(start, end):
        x = master[frame * EXPECTED_CHANNELS + channel]
        y = decoded[frame * EXPECTED_CHANNELS + channel]
        sum_x += x
        sum_y += y
        sum_x2 += x * x
        sum_y2 += y * y
        sum_xy += x * y

    var_x = sum_x2 - (sum_x * sum_x / count)
    var_y = sum_y2 - (sum_y * sum_y / count)
    cov_xy = sum_xy - (sum_x * sum_y / count)
    pearson = cov_xy / math.sqrt(var_x * var_y) if var_x > 0 and var_y > 0 else None
    cosine = sum_xy / math.sqrt(sum_x2 * sum_y2) if sum_x2 > 0 and sum_y2 > 0 else None
    master_rms = math.sqrt(sum_x2 / count)
    decoded_rms = math.sqrt(sum_y2 / count)
    rms_ratio = decoded_rms / master_rms if master_rms > 0 else None
    rms_gain_db = 20 * math.log10(rms_ratio) if rms_ratio and rms_ratio > 0 else None
    regression_gain = cov_xy / var_x if var_x > 0 else None
    regression_gain_db = 20 * math.log10(abs(regression_gain)) if regression_gain else None
    return {
        "channel": "left" if channel == 0 else "right",
        "samples": count,
        "pearson_zero_offset": pearson,
        "cosine_zero_offset": cosine,
        "rms_gain_db": rms_gain_db,
        "regression_gain": regression_gain,
        "regression_gain_db": regression_gain_db,
        "master_rms_pcm16": master_rms,
        "decoded_rms_pcm16": decoded_rms,
        "correlation_pass": pearson is not None and pearson >= CORRELATION_FLOOR,
        "gain_pass": rms_gain_db is not None and abs(rms_gain_db) <= GAIN_TOLERANCE_DB,
    }


def comparison_windows() -> list[dict[str, Any]]:
    events, _ = audio.load_events()
    windows = []
    for event in events:
        if event["kind"] == "silence":
            continue
        start = event["frame"] / audio.FPS
        end = min(audio.DURATION_SECONDS, start + min(1.2, event["durationSeconds"]))
        if end <= start:
            raise VerificationError(f"no comparison interval for authored event {event['id']}")
        windows.append({"event_id": event["id"], "start_seconds": start, "end_seconds": end})
    if not windows:
        raise VerificationError("sfx_events.json has no audible event windows for shared-audio comparison")
    return windows


def compare_track(master: array, decoded_raw: bytes, samples_per_channel: int, label: str,
                  windows: list[dict[str, Any]]) -> dict[str, Any]:
    decoded = pcm_array(decoded_raw)
    if len(decoded) % EXPECTED_CHANNELS:
        raise VerificationError(f"decoded PCM for {label} is not aligned to stereo sample frames")
    decoded_count = len(decoded) // EXPECTED_CHANNELS
    result: dict[str, Any] = {
        "path": label,
        "decoded_sample_count_per_channel": decoded_count,
        "master_sample_count_per_channel": samples_per_channel,
        "codec_padding_samples_after_master": max(0, decoded_count - samples_per_channel),
        "trimmed_only_for_comparison_samples": max(0, decoded_count - samples_per_channel),
        "decoder_priming_handling": "ffmpeg decoded the selected AAC stream and applied available skip-sample/gapless metadata; comparison is at zero offset with no correlation-based alignment",
        "windows": [],
    }
    if decoded_count < samples_per_channel:
        result["status"] = "FAIL"
        result["reason"] = f"decoded AAC contains {decoded_count} samples/channel; at least {samples_per_channel} are required"
        return result

    all_pass = True
    for window in windows:
        window_start, window_end = window["start_seconds"], window["end_seconds"]
        start = int(round(window_start * EXPECTED_SAMPLE_RATE))
        end = int(round(window_end * EXPECTED_SAMPLE_RATE))
        channel_results = [channel_metrics(master, decoded, channel, start, end) for channel in range(EXPECTED_CHANNELS)]
        window_pass = all(item["correlation_pass"] and item["gain_pass"] for item in channel_results)
        all_pass = all_pass and window_pass
        result["windows"].append({
            "event_id": window["event_id"],
            "start_seconds": window_start,
            "end_seconds": window_end,
            "start_sample": start,
            "end_sample_exclusive": end,
            "status": "PASS" if window_pass else "FAIL",
            "criteria": {
                "pearson_minimum": CORRELATION_FLOOR,
                "absolute_rms_gain_db_maximum": GAIN_TOLERANCE_DB,
            },
            "channels": channel_results,
        })
    result["status"] = "PASS" if all_pass else "FAIL"
    return result


def build_report() -> tuple[dict[str, Any], int]:
    report: dict[str, Any] = {
        "status": "NEEDS_SOL",
        "method": "Decode only stream 0:a:0 from each final MP4 to 48 kHz stereo signed PCM16, then compare against shared master.wav at identical sample offsets. No video decode, ASR, resampling beyond ffmpeg output conversion, time shift, or correlation-based alignment is used.",
        "thresholds": {
            "zero_offset_pearson_minimum": CORRELATION_FLOOR,
            "absolute_rms_gain_db_maximum": GAIN_TOLERANCE_DB,
        },
        "event_comparison_windows": [],
        "expected_audio": {
            "sample_rate": EXPECTED_SAMPLE_RATE,
            "channels": EXPECTED_CHANNELS,
            "samples_per_channel": EXPECTED_SAMPLES,
        },
        "inputs": {},
        "tracks": [],
        "absolute_silence": None,
        "limitations": [
            "AAC is lossy; correlation and level checks measure decoded waveform similarity, not perceptual equivalence or listener acceptance.",
            "No offset search is performed. A failed zero-offset window requires review rather than automatic alignment.",
            "Decoded samples beyond the shared master are recorded as codec padding and excluded only from comparison; source media is not modified.",
        ],
    }
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise VerificationError("delivery.json must contain a JSON object")
        audio_data = manifest.get("audio")
        if not isinstance(audio_data, dict):
            raise VerificationError("delivery.json audio metadata is missing")
        sample_rate = audio_data.get("sample_rate")
        channels = audio_data.get("channels")
        samples_per_channel = audio_data.get("samples_per_channel")
        if (sample_rate, channels, samples_per_channel) != (EXPECTED_SAMPLE_RATE, EXPECTED_CHANNELS, EXPECTED_SAMPLES):
            raise VerificationError(
                "delivery.json audio format must be 48 kHz stereo with 5,760,000 samples/channel; "
                f"got rate={sample_rate}, channels={channels}, samples={samples_per_channel}"
            )
        master_path = resolve_delivery_path(audio_data.get("master"), "delivery.json audio.master")
        output_data = manifest.get("outputs")
        if not isinstance(output_data, dict):
            raise VerificationError("delivery.json outputs are missing")
        media_paths = {
            key: resolve_delivery_path(output_data.get(key, {}).get("path") if isinstance(output_data.get(key), dict) else None,
                                       f"delivery.json outputs.{key}")
            for key in ("bilibili", "xiaohongshu")
        }
        for name, path in [("master", master_path), *media_paths.items()]:
            item: dict[str, Any] = {"path": relative(path), "present": path.is_file()}
            if path.is_file():
                item["size_bytes"] = path.stat().st_size
                item["sha256"] = sha256_file(path)
            report["inputs"][name] = item
        missing = [name for name, path in [("master", master_path), *media_paths.items()] if not path.is_file()]
        if missing:
            report["status"] = "NEEDS_SOL"
            report["issues"] = [f"missing required input: {name}" for name in missing]
            return report, 2

        master_hash = report["inputs"]["master"]["sha256"]
        expected_master_hash = audio_data.get("sha256")
        report["inputs"]["master"]["manifest_sha256_matches"] = (
            expected_master_hash == master_hash if isinstance(expected_master_hash, str) else None
        )
        if isinstance(expected_master_hash, str) and expected_master_hash != master_hash:
            report["status"] = "NEEDS_SOL"
            report["issues"] = ["shared PCM master SHA-256 differs from delivery.json"]
            return report, 2
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            report["status"] = "NEEDS_SOL"
            report["issues"] = ["ffmpeg executable was not found on PATH"]
            return report, 2
        report["ffmpeg"] = ffmpeg
        windows = comparison_windows()
        report["event_comparison_windows"] = windows
        report["absolute_silence"] = verify_master_silence(master_path)
        master = load_master(master_path, samples_per_channel)
        all_pass = True
        for key, path in media_paths.items():
            track: dict[str, Any] = {
                "platform": key,
                "path": relative(path),
                "sha256": report["inputs"][key]["sha256"],
                "size_bytes": report["inputs"][key]["size_bytes"],
            }
            try:
                decoded_raw = decode_aac(ffmpeg, path)
                track.update(compare_track(master, decoded_raw, samples_per_channel, relative(path), windows))
            except VerificationError as exc:
                track["status"] = "NEEDS_SOL"
                track["reason"] = str(exc)
            report["tracks"].append(track)
            all_pass = all_pass and track.get("status") == "PASS"
            if "decoded_raw" in locals():
                del decoded_raw
        report["status"] = "PASS" if all_pass and len(report["tracks"]) == 2 else (
            "FAIL" if any(track.get("status") == "FAIL" for track in report["tracks"]) else "NEEDS_SOL"
        )
        return report, 0 if report["status"] == "PASS" else (1 if report["status"] == "FAIL" else 2)
    except (OSError, UnicodeError, json.JSONDecodeError, VerificationError, KeyError, TypeError, ValueError) as exc:
        report["status"] = "NEEDS_SOL"
        report["issues"] = [str(exc)]
        return report, 2


def atomic_write_report(report: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = REPORT_PATH.with_name(f".{REPORT_PATH.name}.tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(REPORT_PATH)


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    report, exit_code = build_report()
    try:
        atomic_write_report(report)
    except OSError as exc:
        print(f"verify_shared_audio.py: could not write report: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": report["status"], "report": str(REPORT_PATH.relative_to(DELIVERY_DIR)),
                      "tracks": len(report["tracks"]), "exitCode": exit_code}, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
