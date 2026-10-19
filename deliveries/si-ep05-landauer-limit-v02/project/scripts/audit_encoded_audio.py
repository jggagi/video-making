#!/usr/bin/env python3
"""Audit shared AAC payload and decoded gap measurements for the two final MP4s.

This check is read-only with respect to media. It decodes one movie at a time
to canonical 48 kHz stereo PCM16 in memory, hashes the decoded waveform, and
measures the authored digital-vacuum interval without treating AAC pre-echo as
a failure. It does not assess listening quality.
"""

from __future__ import annotations

from array import array
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import wave
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DELIVERY_DIR = PROJECT_DIR.parent
MANIFEST_PATH = DELIVERY_DIR / "delivery.json"
MASTER_PATH = PROJECT_DIR / "public" / "audio" / "master.wav"
REPORT_PATH = DELIVERY_DIR / "review" / "encoded-audio-details.json"
SAMPLE_RATE = 48_000
CHANNELS = 2
SAMPLES_PER_CHANNEL = 5_760_000
TOTAL_FRAMES = 7_200
VACUUM_START_SAMPLE = 4_320_000
VACUUM_END_SAMPLE = 4_340_000
SAMPLES_PER_FRAME = 800
EDGE_EXCLUSION_SAMPLES = round(0.020 * SAMPLE_RATE)
EXPECTED_OUTPUTS = {
    "bilibili": {"width": 3840, "height": 2160},
    "xiaohongshu": {"width": 2160, "height": 3840},
}


class AuditFailure(RuntimeError):
    def __init__(self, category: str, message: str):
        super().__init__(message)
        self.category = category


class AuditToolError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(DELIVERY_DIR.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def delivery_path(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise AuditFailure("missing", f"delivery.json is missing the {label} path")
    path = (DELIVERY_DIR / value).resolve()
    try:
        path.relative_to(DELIVERY_DIR.resolve())
    except ValueError:
        raise AuditToolError(f"delivery.json {label} path escapes the delivery directory") from None
    return path


def run_capture(argv: list[str], label: str) -> bytes:
    try:
        result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    except OSError as exc:
        raise AuditToolError(f"{label}: could not start {Path(argv[0]).name}: {exc}") from None
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()[-1500:]
        raise AuditToolError(f"{label}: {Path(argv[0]).name} exited {result.returncode}: {detail or 'no diagnostics'}")
    return result.stdout


def probe_media(ffprobe: str, path: Path) -> dict[str, Any]:
    raw = run_capture([
        ffprobe, "-v", "error", "-show_format", "-show_streams",
        "-show_entries",
        "format=duration:stream=index,codec_type,codec_name,width,height,sample_rate,channels,channel_layout",
        "-of", "json", str(path),
    ], f"probe {relative(path)}")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise AuditToolError(f"ffprobe returned invalid JSON for {relative(path)}") from None
    streams = value.get("streams") if isinstance(value, dict) else None
    if not isinstance(streams, list):
        raise AuditToolError(f"ffprobe returned no stream inventory for {relative(path)}")
    video = next((item for item in streams if item.get("codec_type") == "video"), None)
    audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
    if video is None:
        raise AuditFailure("missing", f"{relative(path)} has no video stream")
    if audio is None:
        raise AuditFailure("missing", f"{relative(path)} has no audio stream")
    return {"format": value.get("format", {}), "video": video, "audio": audio}


def validate_dimensions(probe: dict[str, Any], path: Path, expected: dict[str, int]) -> dict[str, Any]:
    video = probe["video"]
    actual = {"width": video.get("width"), "height": video.get("height")}
    if actual != expected:
        raise AuditFailure(
            "invalid_dimensions",
            f"{relative(path)} is {actual.get('width')}x{actual.get('height')}; expected {expected['width']}x{expected['height']}",
        )
    return {
        "codec": video.get("codec_name"),
        "width": actual["width"],
        "height": actual["height"],
        "duration": probe.get("format", {}).get("duration"),
        "expectedDimensions": expected,
        "dimensionsValid": True,
    }


def validate_aac_stream(probe: dict[str, Any], path: Path) -> dict[str, Any]:
    audio = probe["audio"]
    if audio.get("codec_name") != "aac":
        raise AuditFailure("missing", f"{relative(path)} has no AAC audio stream")
    return {
        "codec": audio.get("codec_name"),
        "sampleRateHz": int(audio["sample_rate"]) if str(audio.get("sample_rate", "")).isdigit() else None,
        "channels": audio.get("channels"),
        "channelLayout": audio.get("channel_layout"),
    }


def aac_packet_sha256(ffmpeg: str, path: Path) -> str:
    raw = run_capture([
        ffmpeg, "-hide_banner", "-nostdin", "-v", "error", "-i", str(path),
        "-map", "0:a:0", "-vn", "-c:a", "copy", "-f", "hash", "-hash", "sha256", "-",
    ], f"hash AAC packets in {relative(path)}")
    match = re.fullmatch(rb"SHA256=([0-9a-fA-F]{64})\s*", raw.strip())
    if not match:
        raise AuditToolError(f"FFmpeg hash muxer returned an unexpected digest for {relative(path)}")
    return match.group(1).decode("ascii").lower()


def decode_canonical_pcm(ffmpeg: str, path: Path) -> bytes:
    return run_capture([
        ffmpeg, "-hide_banner", "-nostdin", "-v", "error", "-i", str(path),
        "-map", "0:a:0", "-vn", "-ac", str(CHANNELS), "-ar", str(SAMPLE_RATE),
        "-acodec", "pcm_s16le", "-f", "s16le", "pipe:1",
    ], f"decode audio from {relative(path)}")


def measure_interval(samples: array, start_sample: int, end_sample: int) -> dict[str, Any]:
    start = start_sample * CHANNELS
    end = end_sample * CHANNELS
    values = samples[start:end]
    if not values:
        raise AuditToolError("AAC gap measurement window is empty")
    peak = max(abs(value) for value in values)
    squared_sum = sum(value * value for value in values)
    rms_pcm16 = math.sqrt(squared_sum / len(values))
    normalized_rms = rms_pcm16 / 32768.0
    return {
        "startSamplePerChannel": start_sample,
        "endSamplePerChannelExclusive": end_sample,
        "sampleFrames": end_sample - start_sample,
        "stereoPcmSamples": len(values),
        "peakPcm16": peak,
        "peakDbfs": 20.0 * math.log10(peak / 32768.0) if peak else None,
        "rmsPcm16": rms_pcm16,
        "rmsDbfs": 20.0 * math.log10(normalized_rms) if normalized_rms else None,
        "nonzeroPcmSampleValues": sum(value != 0 for value in values),
    }


def decode_and_measure(ffmpeg: str, path: Path) -> dict[str, Any]:
    raw = decode_canonical_pcm(ffmpeg, path)
    expected_bytes = SAMPLES_PER_CHANNEL * CHANNELS * 2
    if len(raw) != expected_bytes:
        actual_frames = len(raw) // (CHANNELS * 2)
        raise AuditFailure(
            "sample_count_mismatch",
            f"{relative(path)} decodes to {actual_frames} samples/channel; expected {SAMPLES_PER_CHANNEL}",
        )
    decoded_hash = hashlib.sha256(raw).hexdigest()
    samples = array("h")
    samples.frombytes(raw)
    if sys.byteorder != "little":
        samples.byteswap()
    if len(samples) != SAMPLES_PER_CHANNEL * CHANNELS:
        raise AuditFailure("sample_count_mismatch", f"{relative(path)} decoded PCM is not exact stereo PCM16")

    interior_start = VACUUM_START_SAMPLE + EDGE_EXCLUSION_SAMPLES
    interior_end = VACUUM_END_SAMPLE - EDGE_EXCLUSION_SAMPLES
    return {
        "decodedPcmSha256": decoded_hash,
        "decodedSampleRateHz": SAMPLE_RATE,
        "decodedChannels": CHANNELS,
        "decodedSamplesPerChannel": len(samples) // CHANNELS,
        "exactSampleCount": True,
        "digitalVacuumMeasurements": {
            "aacDigitalZeroRequired": False,
            "interpretation": "Measurement only; AAC pre-echo or ringing may produce nonzero decoded values around the PCM-master cut.",
            "full25FrameGap": measure_interval(samples, VACUUM_START_SAMPLE, VACUUM_END_SAMPLE),
            "interiorExcluding20msAtEachEdge": measure_interval(samples, interior_start, interior_end),
        },
    }


def inspect_master(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AuditFailure("missing", f"shared PCM master is missing: {relative(path)}")
    digest = sha256_file(path)
    try:
        with wave.open(str(path), "rb") as wav:
            actual = (wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getcomptype(), wav.getnframes())
            expected = (SAMPLE_RATE, CHANNELS, 2, "NONE", SAMPLES_PER_CHANNEL)
            if actual != expected:
                raise AuditFailure("sample_count_mismatch", f"PCM master format/count differs from expected: {actual}")
            wav.setpos(VACUUM_START_SAMPLE)
            raw_gap = wav.readframes(VACUUM_END_SAMPLE - VACUUM_START_SAMPLE)
    except (OSError, wave.Error) as exc:
        raise AuditToolError(f"cannot read PCM master: {exc}") from None
    expected_gap_bytes = (VACUUM_END_SAMPLE - VACUUM_START_SAMPLE) * CHANNELS * 2
    if len(raw_gap) != expected_gap_bytes:
        raise AuditFailure("sample_count_mismatch", "PCM master digital-vacuum window is incomplete")
    if any(raw_gap):
        raise AuditFailure("pcm_master_gap_nonzero", "PCM master is not exact digital zero in frames [5400, 5425)")
    return {
        "path": relative(path),
        "sha256": digest,
        "sampleRateHz": SAMPLE_RATE,
        "channels": CHANNELS,
        "samplesPerChannel": SAMPLES_PER_CHANNEL,
        "durationSeconds": SAMPLES_PER_CHANNEL / SAMPLE_RATE,
        "digitalVacuum": {
            "startFrame": VACUUM_START_SAMPLE // SAMPLES_PER_FRAME,
            "endFrameExclusive": VACUUM_END_SAMPLE // SAMPLES_PER_FRAME,
            "startSamplePerChannel": VACUUM_START_SAMPLE,
            "endSamplePerChannelExclusive": VACUUM_END_SAMPLE,
            "peakPcm16": 0,
            "exactZero": True,
        },
    }


def load_manifest() -> dict[str, Any]:
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise AuditFailure("missing", f"delivery manifest is missing: {relative(MANIFEST_PATH)}") from None
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuditToolError(f"cannot read delivery.json: {exc}") from None
    if not isinstance(manifest, dict) or manifest.get("slug") != "si-ep05-landauer-limit-v02":
        raise AuditToolError("delivery.json does not identify the expected EP05 v02 delivery")
    if (manifest.get("duration_seconds"), manifest.get("fps"), manifest.get("total_frames")) != (120, 60, TOTAL_FRAMES):
        raise AuditToolError("delivery.json timing differs from the 120-second, 60 fps, 7200-frame contract")
    return manifest


def audit() -> dict[str, Any]:
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise AuditToolError("ffmpeg and ffprobe must be available on PATH; this script does not install dependencies")

    manifest = load_manifest()
    master = inspect_master(MASTER_PATH)
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        raise AuditToolError("delivery.json outputs must be an object")

    result_outputs: dict[str, Any] = {}
    for key in ("bilibili", "xiaohongshu"):
        expected = EXPECTED_OUTPUTS[key]
        descriptor = outputs.get(key)
        if not isinstance(descriptor, dict):
            raise AuditFailure("missing", f"delivery.json outputs.{key} is missing")
        if (descriptor.get("width"), descriptor.get("height")) != (expected["width"], expected["height"]):
            raise AuditFailure("invalid_dimensions", f"delivery.json outputs.{key} declares incorrect dimensions")
        media = delivery_path(descriptor.get("path"), f"outputs.{key}")
        if not media.is_file():
            raise AuditFailure("missing", f"final movie is missing: {relative(media)}")
        probe = probe_media(ffprobe, media)
        dimensions = validate_dimensions(probe, media, expected)
        audio_stream = validate_aac_stream(probe, media)
        packet_hash = aac_packet_sha256(ffmpeg, media)
        decoded = decode_and_measure(ffmpeg, media)
        result_outputs[key] = {
            "path": relative(media),
            "fileSha256": sha256_file(media),
            "video": dimensions,
            "audio": audio_stream,
            "aacPacketPayloadSha256": packet_hash,
            "decodedAudio": decoded,
        }

    pcm_hashes = [result_outputs[key]["decodedAudio"]["decodedPcmSha256"] for key in ("bilibili", "xiaohongshu")]
    packet_hashes = [result_outputs[key]["aacPacketPayloadSha256"] for key in ("bilibili", "xiaohongshu")]
    if pcm_hashes[0] != pcm_hashes[1] or packet_hashes[0] != packet_hashes[1]:
        raise AuditFailure("streams_not_identical", "the two decoded PCM waveforms or AAC packet payload hashes differ")

    return {
        "schemaVersion": 1,
        "status": "encoded_audio_audited",
        "durationSeconds": 120,
        "sampleRateHz": SAMPLE_RATE,
        "channels": CHANNELS,
        "samplesPerChannel": SAMPLES_PER_CHANNEL,
        "bindings": {
            "deliveryManifestSha256": sha256_file(MANIFEST_PATH),
            "pcmMaster": master,
        },
        "outputs": result_outputs,
        "checks": {
            "bilibiliDimensions": True,
            "xiaohongshuDimensions": True,
            "bothDecodedSampleCountsExact": True,
            "decodedPcmStreamsIdentical": True,
            "aacPacketPayloadHashesIdentical": True,
            "pcmMasterDigitalVacuumExact": True,
        },
        "limits": [
            "AAC gap metrics are measurements only; no digital-zero threshold is asserted for decoded AAC.",
            "This report does not establish human listening quality or target-device playback acceptance.",
            "Integrated loudness and true peak are measured by collect_qa.py, not repeated here.",
        ],
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-write", action="store_true", help="print the audit report without writing review JSON")
    args = parser.parse_args()
    try:
        report = audit()
        exit_code = 0
    except AuditFailure as exc:
        report = {"schemaVersion": 1, "status": "FAIL", "failureCategory": exc.category, "reason": str(exc)}
        exit_code = 1
    except (AuditToolError, OSError, ValueError, TypeError, KeyError, wave.Error) as exc:
        report = {"schemaVersion": 1, "status": "ERROR", "reason": str(exc)}
        exit_code = 2
    if not args.no_write:
        write_json(REPORT_PATH, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
