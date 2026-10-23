#!/usr/bin/env python3
"""Build anonymous, level-matched dry-voice audition files for EP16.

This script performs no provider calls. It validates the two manifests and
canonical source WAVs, measures full concatenated inputs with ffmpeg loudnorm,
then applies only constant gain and high-quality 24 kHz -> 48 kHz resampling.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import random
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1] / "project"
QWEN_MANIFEST_PATH = HERE / "provider-manifest.json"
COSY_MANIFEST_PATH = PROJECT / "public/audio/provider-manifest.json"
PLAN_PATH = HERE / "plan.json"
OUTPUT_DIR = HERE
NORMALIZED_DIR = HERE / "normalized"
QA_PATH = HERE / "qa.json"
KEY_PATH = HERE / "comparison-key.json"
README_PATH = HERE / "README.md"

SEGMENT_IDS = ("S01", "S08", "S09")
SAMPLE_RATE_IN = 24_000
SAMPLE_RATE_OUT = 48_000
CHANNELS = 1
SAMPLE_WIDTH = 2
GAP_SECONDS = 0.8
GAP_SAMPLES_OUT = round(GAP_SECONDS * SAMPLE_RATE_OUT)
GAP_BYTES_OUT = GAP_SAMPLES_OUT * SAMPLE_WIDTH
TARGET_LUFS_CEILING = -18.0
TRUE_PEAK_CEILING = -1.5
LOUDNORM_LRA = 7.0


def die(message: str) -> "NoReturn":
    raise RuntimeError(message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        die(f"Cannot read valid JSON from {path}: {exc}")
    if not isinstance(value, dict):
        die(f"Expected JSON object at {path}")
    return value


def parse_pcm16_mono_wav(path: Path) -> tuple[bytes, dict[str, Any]]:
    """Parse canonical PCM WAV and reject truncated or malformed RIFF data."""
    blob = path.read_bytes()
    if len(blob) < 44 or blob[:4] != b"RIFF" or blob[8:12] != b"WAVE":
        die(f"Not a RIFF/WAVE file: {path}")
    declared_riff_size = struct.unpack_from("<I", blob, 4)[0]
    if declared_riff_size + 8 != len(blob):
        die(f"RIFF size does not match file length: {path}")

    pos = 12
    fmt: tuple[int, int, int, int, int, int] | None = None
    pcm: bytes | None = None
    data_declared: int | None = None
    while pos + 8 <= len(blob):
        chunk_id = blob[pos : pos + 4]
        chunk_size = struct.unpack_from("<I", blob, pos + 4)[0]
        start = pos + 8
        end = start + chunk_size
        if end > len(blob):
            die(f"Truncated RIFF chunk in {path}")
        if chunk_id == b"fmt ":
            if chunk_size < 16:
                die(f"Short fmt chunk in {path}")
            fmt = struct.unpack_from("<HHIIHH", blob, start)
        elif chunk_id == b"data":
            data_declared = chunk_size
            pcm = blob[start:end]
        pos = end + (chunk_size & 1)

    if fmt is None or pcm is None or data_declared is None:
        die(f"Missing fmt or data chunk in {path}")
    audio_format, channels, rate, byte_rate, align, bits = fmt
    if (audio_format, channels, align, bits) != (1, CHANNELS, 2, 16) or rate not in (SAMPLE_RATE_IN, SAMPLE_RATE_OUT):
        die(
            f"Unexpected source format in {path}: format={audio_format}, "
            f"channels={channels}, rate={rate}, align={align}, bits={bits}"
        )
    if byte_rate != rate * SAMPLE_WIDTH or len(pcm) != data_declared:
        die(f"Invalid PCM byte rate or data length in {path}")
    if len(pcm) % SAMPLE_WIDTH:
        die(f"PCM payload is not sample aligned in {path}")
    return pcm, {
        "file_bytes": len(blob),
        "sha256": sha256(blob),
        "pcm_sha256": sha256(pcm),
        "pcm_samples": len(pcm) // SAMPLE_WIDTH,
        "duration_seconds": len(pcm) / SAMPLE_WIDTH / rate,
        "sample_rate_hz": rate,
        "channels": channels,
        "bits_per_sample": bits,
        "declared_pcm_bytes": data_declared,
        "actual_pcm_bytes": len(pcm),
    }


def make_wav_bytes(pcm: bytes, sample_rate: int) -> bytes:
    if len(pcm) % SAMPLE_WIDTH:
        die("Cannot write WAV with unaligned PCM payload")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(SAMPLE_WIDTH)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return buf.getvalue()


def tool_path(name: str) -> str:
    found = shutil.which(name)
    if not found:
        die(f"Required existing executable is unavailable: {name}")
    return found


def run_capture(command: list[str], *, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(
            command,
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        die(f"Could not execute {command[0]}: {exc}")
    if result.returncode != 0:
        tail = result.stderr.decode("utf-8", "replace")[-4000:]
        die(f"Command failed ({result.returncode}): {' '.join(command)}\n{tail}")
    return result


def parse_loudnorm_json(stderr: bytes) -> dict[str, float]:
    text = stderr.decode("utf-8", "replace")
    decoder = json.JSONDecoder()
    candidate: dict[str, Any] | None = None
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[i:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "input_i" in obj and "input_tp" in obj:
            candidate = obj
    if candidate is None:
        die(f"Could not parse loudnorm measurements from ffmpeg output:\n{text[-4000:]}")

    def numeric(name: str) -> float:
        try:
            value = float(candidate[name])
        except (KeyError, TypeError, ValueError):
            die(f"Missing numeric loudnorm field {name}: {candidate}")
        if not math.isfinite(value):
            die(f"Non-finite loudnorm field {name}: {candidate}")
        return value

    return {
        "integrated_lufs": numeric("input_i"),
        "true_peak_dbtp": numeric("input_tp"),
        "loudness_range_lu": numeric("input_lra"),
        "threshold_lufs": numeric("input_thresh"),
    }


def analyze_loudness(ffmpeg: str, concat_wav: bytes) -> dict[str, float]:
    command = [
        ffmpeg,
        "-hide_banner",
        "-nostats",
        "-f",
        "wav",
        "-i",
        "pipe:0",
        "-af",
        f"loudnorm=I={TARGET_LUFS_CEILING}:TP={TRUE_PEAK_CEILING}:LRA={LOUDNORM_LRA}:print_format=json",
        "-f",
        "null",
        "-",
    ]
    return parse_loudnorm_json(run_capture(command, input_bytes=concat_wav).stderr)


def validate_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    plan = load_json(PLAN_PATH)
    qwen_manifest = load_json(QWEN_MANIFEST_PATH)
    cosy_manifest = load_json(COSY_MANIFEST_PATH)
    if tuple(item.get("segment_id") for item in plan.get("items", [])) != SEGMENT_IDS:
        die(f"Unexpected plan segment order: {plan.get('items')}")
    if plan.get("comparison_design", {}).get("same_text") is not True:
        die("Plan does not require the same text")
    if abs(float(plan.get("comparison_design", {}).get("gap_seconds", -1)) - GAP_SECONDS) > 1e-9:
        die("Plan gap duration does not match the assigned 0.8 seconds")
    if qwen_manifest.get("authorization", {}).get("authorized") is not True:
        die("Qwen manifest lacks authorized state")
    if qwen_manifest.get("authorization", {}).get("text_scope") != list(SEGMENT_IDS):
        die("Qwen authorization scope does not match audition segments")
    if qwen_manifest.get("authorization", {}).get("cloud_calls_planned") != 3:
        die("Unexpected number of provider calls in Qwen authorization")

    qwen_calls = {call.get("segment_id"): call for call in qwen_manifest.get("calls", [])}
    cosy_segments = cosy_manifest.get("segments", {})
    if not set(SEGMENT_IDS).issubset(qwen_calls) or not set(SEGMENT_IDS).issubset(cosy_segments):
        die("One or more requested segments are missing from a provider manifest")

    providers: dict[str, Any] = {
        "Qwen": {"manifest": qwen_manifest, "segments": {}},
        "CosyVoice": {"manifest": cosy_manifest, "segments": {}},
    }
    expected_qwen_model = plan.get("model")
    expected_qwen_voice = plan.get("voice")
    for item in plan["items"]:
        sid = item["segment_id"]
        text_path = HERE / item["text_file"]
        text_bytes = text_path.read_bytes()
        if sha256(text_bytes) != item["text_sha256"]:
            die(f"Plan text hash mismatch for {sid}: {text_path}")
        plan_text = text_bytes.decode("utf-8").rstrip("\r\n")

        qentry = qwen_calls[sid]
        qsettings = qentry.get("requested_settings", {})
        if qentry.get("status") != "PASS" or qentry.get("cli_exit_code") != 0:
            die(f"Qwen generation did not PASS for {sid}")
        if qentry.get("reported_models") != [expected_qwen_model] or qentry.get("reported_voices") != [expected_qwen_voice]:
            die(f"Qwen identity does not match plan for {sid}")
        if qsettings != {
            "model": expected_qwen_model,
            "voice": expected_qwen_voice,
            "rate": 1.0,
            "format": "wav",
            "sample_rate": SAMPLE_RATE_IN,
        }:
            die(f"Qwen settings do not match plan for {sid}: {qsettings}")
        if qentry.get("text_sha256") != item["text_sha256"]:
            die(f"Qwen text hash does not match plan for {sid}")
        if qentry.get("requested_instruction") != item.get("instruction"):
            die(f"Qwen instruction differs from plan for {sid}")

        centry = cosy_segments[sid]
        csettings = centry.get("settings", {})
        if centry.get("effectiveModel") != "cosyvoice-v3-flash" or centry.get("effectiveVoice") != "longtian_v3":
            die(f"CosyVoice identity does not match the verified EP16 manifest for {sid}")
        if (csettings.get("effective_model"), csettings.get("voice"), csettings.get("rate"), csettings.get("sample_rate")) != (
            "cosyvoice-v3-flash",
            "longtian_v3",
            1.0,
            SAMPLE_RATE_IN,
        ):
            die(f"CosyVoice settings do not match the EP16 manifest for {sid}: {csettings}")
        if centry.get("ttsPhoneticText") != plan_text:
            die(f"CosyVoice text does not match Qwen plan text for {sid}")

        for provider_name, entry, path_key, file_sha_key, pcm_sha, samples in (
            ("Qwen", qentry, "canonical_path", "canonical_sha256", qentry["pcm"]["pcmSha256"], qentry["pcm"]["actualSamples24k"]),
            ("CosyVoice", centry, "canonicalPath", "canonicalSha256", centry["providerPcmSha256"], centry["rawSamples24k"]),
        ):
            base = HERE if provider_name == "Qwen" else PROJECT
            rel = entry.get(path_key)
            if not isinstance(rel, str):
                die(f"Missing canonical path for {provider_name} {sid}")
            source_path = (base / rel).resolve()
            expected_root = (HERE if provider_name == "Qwen" else PROJECT).resolve()
            if expected_root not in source_path.parents:
                die(f"Canonical path escapes its intended project tree: {source_path}")
            if not source_path.is_file():
                die(f"Canonical source file is missing: {source_path}")
            pcm, measured = parse_pcm16_mono_wav(source_path)
            if measured["sample_rate_hz"] != SAMPLE_RATE_IN:
                die(f"Unexpected source sample rate for {provider_name} {sid}: {measured['sample_rate_hz']}")
            if measured["sha256"] != entry.get(file_sha_key):
                die(f"Canonical full-file SHA mismatch for {provider_name} {sid}")
            if measured["pcm_sha256"] != pcm_sha:
                die(f"Canonical PCM SHA mismatch for {provider_name} {sid}")
            if measured["pcm_samples"] != samples:
                die(f"Canonical sample count mismatch for {provider_name} {sid}")
            providers[provider_name]["segments"][sid] = {
                "path": str(source_path.relative_to(HERE.parents[2])),
                "full_sha256": measured["sha256"],
                "manifest_full_sha256": entry.get(file_sha_key),
                "full_sha_matches_manifest": True,
                "pcm_sha256": measured["pcm_sha256"],
                "manifest_pcm_sha256": pcm_sha,
                "pcm_sha_matches_manifest": True,
                "file_bytes": measured["file_bytes"],
                "pcm_samples_24k": measured["pcm_samples"],
                "manifest_pcm_samples_24k": samples,
                "pcm_samples_match_manifest": True,
                "duration_seconds": measured["duration_seconds"],
                "sample_rate_hz": measured["sample_rate_hz"],
                "channels": measured["channels"],
                "bits_per_sample": measured["bits_per_sample"],
            }
            providers[provider_name]["segments"][sid]["_pcm_bytes"] = pcm

    return plan, qwen_manifest, providers


def concatenated_pcm(segments: dict[str, Any]) -> tuple[bytes, list[dict[str, Any]]]:
    parts: list[bytes] = []
    positions: list[dict[str, Any]] = []
    cursor = 0
    for index, sid in enumerate(SEGMENT_IDS):
        pcm = segments[sid]["_pcm_bytes"]
        n_samples = len(pcm) // SAMPLE_WIDTH
        start = cursor
        parts.append(pcm)
        cursor += n_samples
        positions.append(
            {
                "segment_id": sid,
                "start_sample_24k": start,
                "end_sample_24k_exclusive": cursor,
                "pcm_samples_24k": n_samples,
                "duration_seconds": n_samples / SAMPLE_RATE_IN,
            }
        )
        if index + 1 < len(SEGMENT_IDS):
            gap_samples = round(GAP_SECONDS * SAMPLE_RATE_IN)
            parts.append(bytes(gap_samples * SAMPLE_WIDTH))
            cursor += gap_samples
    return b"".join(parts), positions


def build_one_normalized_segment(
    ffmpeg: str,
    source_path: Path,
    destination: Path,
    gain_db: float,
) -> tuple[bytes, dict[str, Any]]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    gain_text = f"{gain_db:.10f}"
    filt = (
        f"volume={gain_text}dB:precision=double,"
        "aresample=48000:resampler=swr:filter_size=64:phase_shift=10:cutoff=0.97:exact_rational=1"
    )
    command = [
        ffmpeg,
        "-hide_banner",
        "-nostats",
        "-y",
        "-i",
        str(source_path),
        "-af",
        filt,
        "-ac",
        "1",
        "-ar",
        str(SAMPLE_RATE_OUT),
        "-c:a",
        "pcm_s16le",
        "-f",
        "wav",
        str(destination),
    ]
    run_capture(command)
    pcm, measured = parse_pcm16_mono_wav(destination)
    if measured["sample_rate_hz"] != SAMPLE_RATE_OUT:
        die(f"Unexpected normalized sample rate in {destination}: {measured['sample_rate_hz']}")
    return pcm, measured


def ffprobe_info(ffprobe: str, path: Path) -> dict[str, Any]:
    result = run_capture(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,codec_type,sample_rate,channels,bits_per_sample,sample_fmt",
            "-show_entries",
            "format=duration,size",
            "-of",
            "json",
            str(path),
        ]
    )
    try:
        data = json.loads(result.stdout)
        stream = data["streams"][0]
        return {
            "codec_name": stream.get("codec_name"),
            "codec_type": stream.get("codec_type"),
            "sample_rate": int(stream["sample_rate"]),
            "channels": int(stream["channels"]),
            "bits_per_sample": int(stream["bits_per_sample"]),
            "sample_fmt": stream.get("sample_fmt"),
            "format_duration_seconds": float(data["format"]["duration"]),
            "format_size_bytes": int(data["format"]["size"]),
        }
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        die(f"Unexpected ffprobe result for {path}: {exc}; output={result.stdout!r}")


def strict_decode(ffmpeg: str, path: Path) -> None:
    run_capture([ffmpeg, "-hide_banner", "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"])


def write_group(
    ffmpeg: str,
    ffprobe: str,
    label: str,
    provider_name: str,
    provider_data: dict[str, Any],
    gain_db: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    pieces: list[bytes] = []
    segment_positions: list[dict[str, Any]] = []
    cursor = 0
    normalized_records: dict[str, Any] = {}
    for index, sid in enumerate(SEGMENT_IDS):
        segment = provider_data["segments"][sid]
        source_path = Path(segment["path"])
        # QA source paths are relative to the repository's deliveries/ folder.
        if not source_path.is_absolute():
            source_path = HERE.parents[2] / source_path
        destination = NORMALIZED_DIR / label / f"{sid}.wav"
        pcm, measured = build_one_normalized_segment(ffmpeg, source_path, destination, gain_db)
        expected_samples = segment["pcm_samples_24k"] * 2
        if measured["pcm_samples"] != expected_samples:
            die(
                f"Resampler changed expected complete duration for group {label} {sid}: "
                f"expected {expected_samples}, got {measured['pcm_samples']}"
            )
        start = cursor
        pieces.append(pcm)
        cursor += measured["pcm_samples"]
        segment_positions.append(
            {
                "segment_id": sid,
                "start_sample_48k": start,
                "end_sample_48k_exclusive": cursor,
                "pcm_samples_48k": measured["pcm_samples"],
                "duration_seconds": measured["pcm_samples"] / SAMPLE_RATE_OUT,
            }
        )
        normalized_records[sid] = {
            "path": str(destination.relative_to(HERE)),
            "sha256": measured["sha256"],
            "pcm_sha256": measured["pcm_sha256"],
            "file_bytes": measured["file_bytes"],
            "pcm_samples_48k": measured["pcm_samples"],
        }
        if index + 1 < len(SEGMENT_IDS):
            pieces.append(bytes(GAP_BYTES_OUT))
            cursor += GAP_SAMPLES_OUT

    output_pcm = b"".join(pieces)
    output_path = OUTPUT_DIR / f"audition-{label}.wav"
    output_path.write_bytes(make_wav_bytes(output_pcm, SAMPLE_RATE_OUT))
    actual_pcm, measured = parse_pcm16_mono_wav(output_path)
    expected_samples = sum(provider_data["segments"][sid]["pcm_samples_24k"] * 2 for sid in SEGMENT_IDS) + 2 * GAP_SAMPLES_OUT
    if len(actual_pcm) // SAMPLE_WIDTH != expected_samples:
        die(f"Final duration/sample count mismatch for group {label}")
    if measured["pcm_samples"] != cursor:
        die(f"Final group cursor mismatch for group {label}")
    strict_decode(ffmpeg, output_path)
    probe = ffprobe_info(ffprobe, output_path)
    if (probe["codec_name"], probe["codec_type"], probe["sample_rate"], probe["channels"], probe["bits_per_sample"]) != (
        "pcm_s16le",
        "audio",
        SAMPLE_RATE_OUT,
        CHANNELS,
        16,
    ):
        die(f"Unexpected output format for group {label}: {probe}")
    final_loudness = analyze_loudness(ffmpeg, make_wav_bytes(actual_pcm, SAMPLE_RATE_OUT))
    return (
        {
            "file": output_path.name,
            "sha256": measured["sha256"],
            "file_bytes": measured["file_bytes"],
            "pcm_sha256": measured["pcm_sha256"],
            "pcm_samples_48k": measured["pcm_samples"],
            "duration_seconds": measured["duration_seconds"],
            "sample_rate_hz": SAMPLE_RATE_OUT,
            "channels": CHANNELS,
            "bits_per_sample": 16,
            "segment_positions": segment_positions,
            "gaps": [
                {"after_segment": SEGMENT_IDS[0], "start_sample_48k": segment_positions[0]["end_sample_48k_exclusive"], "samples": GAP_SAMPLES_OUT},
                {"after_segment": SEGMENT_IDS[1], "start_sample_48k": segment_positions[1]["end_sample_48k_exclusive"], "samples": GAP_SAMPLES_OUT},
            ],
            "probe": probe,
            "strict_decode": "PASS",
            "measured_integrated_lufs": final_loudness["integrated_lufs"],
            "measured_true_peak_dbtp": final_loudness["true_peak_dbtp"],
        },
        {"normalized_segments": normalized_records, "gain_db": gain_db},
    )


def write_readme(mapping: dict[str, str], qa: dict[str, Any], key: dict[str, Any]) -> None:
    a = qa["outputs"]["A"]
    b = qa["outputs"]["B"]
    target = key["normalization"]["final_common_target_lufs"]
    lines = [
        "# EP16 干声旁白 A/B 试听",
        "",
        "两份文件都按 S01 → S08 → S09 的顺序完整串接，段间各留 0.8 秒静音。没有配乐、EQ、压缩、变速或旁白裁剪。",
        "",
        "- [试听 A](audition-A.wav)",
        "- [试听 B](audition-B.wav)",
        "",
        "两份均为 48 kHz、单声道、PCM16 WAV。根据完整串接输入的 EBU R128 测量结果，使用共同目标响度和每组各自的恒定线性增益；输出阶段只做恒定音量调整与 FFmpeg SWR 高质量重采样（64-tap filter、精确有理比、0.97 cutoff），不使用动态 loudnorm 或 limiter。",
        f"共同目标响度：{target:.2f} LUFS；最终实测 A={a['measured_integrated_lufs']:.2f} LUFS / {a['measured_true_peak_dbtp']:.2f} dBTP，B={b['measured_integrated_lufs']:.2f} LUFS / {b['measured_true_peak_dbtp']:.2f} dBTP。",
        "",
        "试听限制：这是制作配置对照，不是严格的模型控制实验。两边音色不同，Qwen 生成使用了逐段表达指令，CosyVoice 使用既有系列干声；音色和指令均可能影响听感。两边旁白文本相同，原始片段完整保留。自动完整性与响度检查已运行；人工听感验收尚未执行。",
        "",
        "## 先听后揭晓",
        "",
        "下面会显示 A/B 与生成来源的对应关系。",
        "",
        "<details>",
        "<summary>展开映射</summary>",
        "",
        f"- A：{mapping['A']}",
        f"- B：{mapping['B']}",
        "",
        "增益与每组输入分析值保存在 `comparison-key.json`。分段位置、SHA、样本数与验证结果见 `qa.json`。",
        "",
        "</details>",
        "",
    ]
    README_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ffmpeg = tool_path("ffmpeg")
    ffprobe = tool_path("ffprobe")
    plan, _qwen_manifest, providers = validate_inputs()

    prior_mapping: dict[str, str] | None = None
    if KEY_PATH.exists():
        existing = load_json(KEY_PATH)
        m = existing.get("provider_by_group")
        if isinstance(m, dict) and set(m) == {"A", "B"} and set(m.values()) == {"Qwen", "CosyVoice"}:
            prior_mapping = {"A": m["A"], "B": m["B"]}
        else:
            die("Existing comparison-key.json has an invalid provider mapping")
    if prior_mapping is None:
        provider_order = ["Qwen", "CosyVoice"]
        random.SystemRandom().shuffle(provider_order)
        mapping = {"A": provider_order[0], "B": provider_order[1]}
    else:
        mapping = prior_mapping

    # Analyze complete 24 kHz concatenations, including the exact 0.8 second
    # silence gaps, before deriving one common LUFS target and constant gains.
    analyses: dict[str, dict[str, float]] = {}
    for provider_name in ("Qwen", "CosyVoice"):
        pcm, _positions = concatenated_pcm(providers[provider_name]["segments"])
        analyses[provider_name] = analyze_loudness(ffmpeg, make_wav_bytes(pcm, SAMPLE_RATE_IN))

    crest_estimates = {
        provider: data["true_peak_dbtp"] - data["integrated_lufs"]
        for provider, data in analyses.items()
    }
    common_target = min(
        TARGET_LUFS_CEILING,
        TRUE_PEAK_CEILING - max(crest_estimates.values()),
    )
    adjustment_steps = 0
    final_outputs: dict[str, Any] = {}
    final_gain_data: dict[str, Any] = {}
    for attempt in range(2):
        NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
        final_outputs = {}
        final_gain_data = {}
        for label in ("A", "B"):
            provider_name = mapping[label]
            gain_db = common_target - analyses[provider_name]["integrated_lufs"]
            output, transform = write_group(
                ffmpeg,
                ffprobe,
                label,
                provider_name,
                providers[provider_name],
                gain_db,
            )
            final_outputs[label] = output
            final_gain_data[label] = transform

        max_peak = max(v["measured_true_peak_dbtp"] for v in final_outputs.values())
        # loudnorm reports true peak to hundredths of a dB. Keep a 0.05 dB
        # buffer so a value rounded to exactly -1.50 does not sit on the limit.
        if max_peak < TRUE_PEAK_CEILING - 0.05:
            break
        if attempt == 1:
            die(
                f"Output true peak remains above ceiling after one 0.1 LU safety step: "
                f"{max_peak:.3f} dBTP"
            )
        common_target -= 0.1
        adjustment_steps += 1

    level_delta = abs(
        final_outputs["A"]["measured_integrated_lufs"]
        - final_outputs["B"]["measured_integrated_lufs"]
    )
    if level_delta > 0.2:
        die(f"Final integrated loudness difference exceeds 0.2 LU: {level_delta:.3f}")
    if max(v["measured_true_peak_dbtp"] for v in final_outputs.values()) > TRUE_PEAK_CEILING:
        die("Final true-peak ceiling was not met")

    source_validation: dict[str, Any] = {}
    for provider_name in ("Qwen", "CosyVoice"):
        source_validation[provider_name] = {
            "segments": {
                sid: {
                    k: v
                    for k, v in providers[provider_name]["segments"][sid].items()
                    if not k.startswith("_")
                }
                for sid in SEGMENT_IDS
            },
            "concatenated_input_loudness_analysis": analyses[provider_name],
        }

    qa = {
        "version": 1,
        "status": "PASS",
        "source_paths_relative_to_repository": "deliveries/",
        "design": {
            "same_text_segments": list(SEGMENT_IDS),
            "ordered_complete_cues": True,
            "gap_seconds": GAP_SECONDS,
            "sample_rate_hz": SAMPLE_RATE_OUT,
            "channels": CHANNELS,
            "bits_per_sample": 16,
            "no_music": True,
            "no_speed_change": True,
            "no_speech_trimming": True,
            "no_eq_compression_limiter": True,
            "output_processing": "constant linear volume gain followed by FFmpeg SWR resampling (filter_size=64, phase_shift=10, cutoff=0.97, exact_rational=1); output assembled with exact PCM silence gaps",
            "loudnorm_usage": "measurement only on full concatenated inputs and final outputs; no loudnorm processing saved to audition files",
        },
        "source_validation": source_validation,
        "normalized_segments_by_group": {
            label: final_gain_data[label]["normalized_segments"] for label in ("A", "B")
        },
        "normalization": {
            "formula": "min(-18.0, -1.5 - max(input_true_peak_dbtp - input_integrated_lufs))",
            "initial_formula_target_lufs": min(
                TARGET_LUFS_CEILING,
                TRUE_PEAK_CEILING - max(crest_estimates.values()),
            ),
            "final_common_target_lufs": common_target,
            "safety_adjustments_down_0_1_lu": adjustment_steps,
            "target_lufs_ceiling": TARGET_LUFS_CEILING,
            "true_peak_ceiling_dbtp": TRUE_PEAK_CEILING,
            "max_final_integrated_loudness_delta_lu": level_delta,
        },
        "outputs": final_outputs,
        "limitations": [
            "This compares production setups, not a voice-matched model benchmark: the providers use different voices.",
            "Qwen generation used per-segment expressive instructions; the existing CosyVoice cues were produced under the series voice setup, so instruction differences also affect the comparison.",
            "No human listening claim is made; human auditory acceptance remains NOT_RUN.",
        ],
    }
    key = {
        "version": 1,
        "provider_by_group": mapping,
        "normalization": {
            "formula": "min(-18.0, -1.5 - max(input_true_peak_dbtp - input_integrated_lufs))",
            "input_analysis_by_provider": analyses,
            "initial_common_target_lufs": qa["normalization"]["initial_formula_target_lufs"],
            "final_common_target_lufs": common_target,
            "safety_adjustments_down_0_1_lu": adjustment_steps,
            "constant_gain_db_by_group": {
                label: final_gain_data[label]["gain_db"] for label in ("A", "B")
            },
        },
    }
    QA_PATH.write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    KEY_PATH.write_text(json.dumps(key, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_readme(mapping, qa, key)
    print(json.dumps({"status": "PASS", "outputs": {k: {"file": v["file"], "sha256": v["sha256"], "file_bytes": v["file_bytes"], "duration_seconds": v["duration_seconds"], "lufs": v["measured_integrated_lufs"], "true_peak_dbtp": v["measured_true_peak_dbtp"]} for k, v in final_outputs.items()}, "target_lufs": common_target, "level_delta_lu": level_delta}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
