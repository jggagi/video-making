#!/usr/bin/env python3
"""Audit decoded audio samples without modifying the source file."""

from __future__ import annotations

import argparse
import array
from fractions import Fraction
import hashlib
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


READ_SIZE = 64 * 1024


class AuditError(Exception):
    """A local input, probe, or decode error suitable for a concise diagnostic."""


def finite_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if not math.isfinite(parsed):
        raise argparse.ArgumentTypeError("must be finite")
    return parsed


def positive_float(value: str) -> float:
    parsed = finite_float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def nonnegative_float(value: str) -> float:
    parsed = finite_float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Measure an audio file by probing and streaming its native audio stream through ffmpeg.",
        epilog="The source is never changed. Peak and RMS are sample measurements, not true-peak, LUFS, or listening checks.",
    )
    parser.add_argument("audiofile", help="audio file to inspect")
    parser.add_argument("--ffmpeg", help="ffmpeg executable (default: found on PATH)")
    parser.add_argument("--ffprobe", help="ffprobe executable (default: found on PATH)")
    parser.add_argument("--fps", type=positive_float, help="derive minimum video frames from decoded duration at this positive frame rate")
    parser.add_argument(
        "--tail-silence",
        type=nonnegative_float,
        default=0.0,
        metavar="SECONDS",
        help="require at least this many trailing seconds of exact digital zero (default: 0, disabled)",
    )
    parser.add_argument("--max-peak-dbfs", type=finite_float, metavar="DBFS", help="optional sample-peak ceiling in dBFS")
    parser.add_argument("--output", help="also write the JSON report to this path")
    return parser


def resolve_executable(requested: str | None, name: str) -> str:
    candidate = requested if requested is not None else name
    executable = shutil.which(candidate)
    if executable is None:
        label = f"'{requested}'" if requested is not None else f"'{name}' on PATH"
        raise AuditError(f"Could not find {label}.")
    return executable


def same_file_path(source: Path, output: Path) -> bool:
    if source.resolve() == output.resolve():
        return True
    try:
        return output.exists() and os.path.samefile(source, output)
    except OSError:
        return False


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def run_probe(executable: str, source: Path) -> dict[str, Any]:
    command = [
        executable,
        "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,sample_rate,channels",
        "-of", "json",
        str(source),
    ]
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AuditError(f"ffprobe could not inspect the input: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip()[-2000:]
        raise AuditError(f"ffprobe failed with exit {result.returncode}: {detail or 'no diagnostic output'}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AuditError("ffprobe returned invalid JSON.") from exc
    streams = payload.get("streams")
    if not isinstance(streams, list) or not streams:
        raise AuditError("The input has no probeable first audio stream.")
    stream = streams[0]
    try:
        sample_rate = int(stream["sample_rate"])
        channels = int(stream["channels"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AuditError("ffprobe did not report a valid sample rate and channel count.") from exc
    if sample_rate <= 0 or channels <= 0:
        raise AuditError("ffprobe reported a nonpositive sample rate or channel count.")
    codec = stream.get("codec_name")
    if not isinstance(codec, str) or not codec:
        raise AuditError("ffprobe did not report the first audio stream codec.")
    return {"codec": codec, "sample_rate_hz": sample_rate, "channels": channels}


def dbfs(value: float) -> float | None:
    if value == 0:
        return None
    return 20.0 * math.log10(value)


def decode_and_measure(executable: str, source: Path, sample_rate: int, channels: int) -> dict[str, Any]:
    command = [
        executable,
        "-nostdin", "-v", "error",
        "-i", str(source),
        "-map", "0:a:0",
        "-vn", "-sn", "-dn",
        "-c:a", "pcm_f32le",
        "-f", "f32le", "pipe:1",
    ]
    stderr_file = tempfile.TemporaryFile()
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=stderr_file, bufsize=0)
    except OSError as exc:
        stderr_file.close()
        raise AuditError(f"Could not start ffmpeg: {exc}") from exc

    assert process.stdout is not None
    sample_count = 0
    finite_count = 0
    nonfinite_count = 0
    peak = 0.0
    sum_squares = 0.0
    frame_count = 0
    frame_sample_count = 0
    frame_is_zero = True
    trailing_zero_frames = 0
    byte_remainder = b""

    try:
        while chunk := process.stdout.read(READ_SIZE):
            data = byte_remainder + chunk
            aligned_bytes = len(data) - (len(data) % 4)
            byte_remainder = data[aligned_bytes:]
            if aligned_bytes == 0:
                continue
            samples = array.array("f")
            if samples.itemsize != 4:
                process.kill()
                process.wait()
                stderr_file.close()
                raise AuditError("This Python runtime does not provide 32-bit array floats for PCM decoding.")
            samples.frombytes(data[:aligned_bytes])
            if sys.byteorder != "little":
                samples.byteswap()
            for sample in samples:
                sample_count += 1
                is_finite = math.isfinite(sample)
                if is_finite:
                    finite_count += 1
                    magnitude = abs(sample)
                    if magnitude > peak:
                        peak = magnitude
                    sum_squares += sample * sample
                else:
                    nonfinite_count += 1
                frame_is_zero = frame_is_zero and is_finite and sample == 0.0
                frame_sample_count += 1
                if frame_sample_count == channels:
                    frame_count += 1
                    if frame_is_zero:
                        trailing_zero_frames += 1
                    else:
                        trailing_zero_frames = 0
                    frame_sample_count = 0
                    frame_is_zero = True
    except OSError as exc:
        process.kill()
        process.wait()
        stderr_file.close()
        raise AuditError(f"Could not read ffmpeg's decoded audio stream: {exc}") from exc
    finally:
        process.stdout.close()

    return_code = process.wait()
    stderr_file.seek(0, os.SEEK_END)
    stderr_file.seek(max(0, stderr_file.tell() - 2000))
    stderr = stderr_file.read().decode("utf-8", errors="replace")
    stderr_file.close()
    if return_code != 0:
        detail = stderr.strip()[-2000:]
        raise AuditError(f"ffmpeg decode failed with exit {return_code}: {detail or 'no diagnostic output'}")
    if byte_remainder:
        raise AuditError("ffmpeg produced an incomplete 32-bit float sample.")
    if frame_sample_count:
        raise AuditError("Decoded sample count is not aligned to the source channel count.")
    if frame_count == 0:
        raise AuditError("ffmpeg decoded no audio sample frames.")

    duration = frame_count / sample_rate
    all_finite = nonfinite_count == 0
    rms = math.sqrt(sum_squares / finite_count) if finite_count else None
    return {
        "decoded_sample_count": sample_count,
        "decoded_frame_count_per_channel": frame_count,
        "decoded_duration_seconds": duration,
        "finite_samples": all_finite,
        "non_finite_sample_count": nonfinite_count,
        "finite_sample_count": finite_count,
        "sample_peak": peak if finite_count else None,
        "sample_peak_dbfs": dbfs(peak) if finite_count else None,
        "rms": rms,
        "rms_dbfs": dbfs(rms) if rms is not None else None,
        "trailing_exact_zero_frames_per_channel": trailing_zero_frames,
        "trailing_exact_zero_seconds": trailing_zero_frames / sample_rate,
    }


def audit(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    source = Path(args.audiofile).expanduser().resolve()
    output = Path(args.output).expanduser().resolve() if args.output else None
    if not source.is_file():
        raise AuditError(f"Audio input is missing or is not a regular file: {source}")
    if output is not None and same_file_path(source, output):
        raise AuditError("--output resolves to the audio input; refusing to overwrite the source.")

    ffmpeg = resolve_executable(args.ffmpeg, "ffmpeg")
    ffprobe = resolve_executable(args.ffprobe, "ffprobe")
    initial_stat = source.stat()
    source_hash = sha256_file(source)
    metadata = run_probe(ffprobe, source)
    measured = decode_and_measure(ffmpeg, source, metadata["sample_rate_hz"], metadata["channels"])
    final_stat = source.stat()
    unchanged = (
        initial_stat.st_dev == final_stat.st_dev
        and initial_stat.st_ino == final_stat.st_ino
        and initial_stat.st_size == final_stat.st_size
        and initial_stat.st_mtime_ns == final_stat.st_mtime_ns
    )

    violations: list[str] = []
    if not unchanged:
        violations.append("The source file changed while it was being audited.")
    if not measured["finite_samples"]:
        violations.append(f"Decoded audio contains {measured['non_finite_sample_count']} non-finite samples.")

    frame_measurement = None
    if args.fps is not None:
        frame_measurement = {
            "fps": args.fps,
            "minimum_frames": math.ceil(
                Fraction(measured["decoded_frame_count_per_channel"])
                * Fraction(str(args.fps))
                / metadata["sample_rate_hz"]
            ),
        }

    tail_constraint = {
        "enabled": args.tail_silence > 0,
        "required_seconds": args.tail_silence,
        "observed_exact_zero_frames_per_channel": measured["trailing_exact_zero_frames_per_channel"],
        "observed_exact_zero_seconds": measured["trailing_exact_zero_seconds"],
        "required_zero_frames_per_channel": None,
        "passes": None,
    }
    if args.tail_silence > 0:
        required_frames = math.ceil(Fraction(str(args.tail_silence)) * metadata["sample_rate_hz"])
        tail_constraint["required_zero_frames_per_channel"] = required_frames
        tail_passes = measured["decoded_frame_count_per_channel"] >= required_frames
        tail_passes = tail_passes and measured["trailing_exact_zero_frames_per_channel"] >= required_frames
        tail_constraint["passes"] = tail_passes
        if not tail_passes:
            violations.append(
                "Trailing exact digital zero is shorter than requested "
                f"({measured['trailing_exact_zero_seconds']:.9g}s observed, {args.tail_silence:.9g}s required)."
            )

    peak_constraint = {
        "enabled": args.max_peak_dbfs is not None,
        "maximum_sample_peak_dbfs": args.max_peak_dbfs,
        "observed_sample_peak_dbfs": measured["sample_peak_dbfs"],
        "passes": None,
    }
    if args.max_peak_dbfs is not None:
        peak_passes = measured["sample_peak"] == 0 or (
            measured["sample_peak_dbfs"] is not None
            and measured["sample_peak_dbfs"] <= args.max_peak_dbfs
        )
        peak_constraint["passes"] = peak_passes
        if not peak_passes:
            violations.append(
                "Sample peak exceeds the requested ceiling "
                f"({measured['sample_peak_dbfs']:.9g} dBFS observed, {args.max_peak_dbfs:.9g} dBFS maximum)."
            )

    report = {
        "schema_version": 1,
        "status": "fail" if violations else "pass",
        "source_unchanged_during_audit": unchanged,
        "source_metadata": {
            "path": str(source),
            "sha256": source_hash,
            **metadata,
        },
        "decoded_measurement": measured,
        "video_timing": frame_measurement,
        "constraints": {
            "tail_silence": tail_constraint,
            "max_peak": peak_constraint,
        },
        "errors": violations,
        "measurement_scope": {
            "peak": "sample peak only; not true peak, clipping diagnosis, or LUFS",
            "listening_review_performed": False,
        },
    }
    return report, 1 if violations else 0


def emit_report(report: dict[str, Any], output_name: str | None, input_name: str) -> int:
    text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    exit_code = 0 if report.get("status") == "pass" else (1 if report.get("status") == "fail" else 2)
    if output_name:
        output = Path(output_name).expanduser().resolve()
        source_name = report.get("source_metadata", {}).get("path", str(Path(input_name).expanduser().resolve()))
        if same_file_path(Path(source_name), output):
            report["status"] = "error"
            message = "--output resolves to the audio input; refusing to overwrite the source."
            if message not in report.setdefault("errors", []):
                report["errors"].append(message)
            text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
            exit_code = 2
        else:
            try:
                output.write_text(text, encoding="utf-8")
            except OSError as exc:
                report["status"] = "error"
                report.setdefault("errors", []).append(f"Could not write JSON output: {exc}")
                text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
                exit_code = 2
    sys.stdout.write(text)
    if exit_code != 0:
        for message in report.get("errors", []):
            print(f"audio audit: {message}", file=sys.stderr)
    return exit_code


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        report, exit_code = audit(args)
    except AuditError as exc:
        report = {"schema_version": 1, "status": "error", "errors": [str(exc)]}
        exit_code = 2
    except (OSError, ValueError, OverflowError, struct.error) as exc:
        report = {"schema_version": 1, "status": "error", "errors": [f"Audio audit failed: {exc}"]}
        exit_code = 2
    return emit_report(report, args.output, args.audiofile) if args.output else _emit_stdout(report, exit_code)


def _emit_stdout(report: dict[str, Any], exit_code: int) -> int:
    sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    if exit_code != 0:
        for message in report.get("errors", []):
            print(f"audio audit: {message}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
