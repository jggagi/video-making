#!/usr/bin/env python3
"""Assemble and verify the bounded EP11 porcelain-canyon material study.

This script writes only beneath this study's media/ and review/ directories.
It does not render Blender frames, create narration, publish, or replace v02.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import uuid
import wave
from typing import Any


STUDY_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = STUDY_ROOT.parent.parent
V02_ROOT = REPO_ROOT / "deliveries" / "si-ep11-kintsugi-ink-v02"
MEDIA_DIR = STUDY_ROOT / "media"
REVIEW_DIR = STUDY_ROOT / "review"
BRIEF_PATH = STUDY_ROOT / "project" / "brief.md"
DELIVERY_PATH = V02_ROOT / "delivery.json"
SCORE_PATH = V02_ROOT / "project" / "public" / "audio" / "score.wav"
SFX_PATH = V02_ROOT / "project" / "public" / "audio" / "sfx.wav"

FPS = 24
FRAME_COUNT = 192
WIDTH = 1080
HEIGHT = 1920
DURATION_SECONDS = 8
SAMPLE_RATE = 48_000
CHANNELS = 2
SAMPLES_PER_CHANNEL = SAMPLE_RATE * DURATION_SECONDS
SOURCE_START_SAMPLE = 46 * SAMPLE_RATE
SOURCE_END_SAMPLE = 54 * SAMPLE_RATE
TRUE_PEAK_LIMIT_DBTP = -1.0
STUDY_TARGET_LUFS = -20.0
THREADS = "2"

OUTPUTS = {
    "audio_master": MEDIA_DIR / "canyon-8s-master.wav",
    "new_video": MEDIA_DIR / "new-canyon-clean.mp4",
    "old_video": MEDIA_DIR / "old-canyon.mp4",
    "comparison": MEDIA_DIR / "canyon-side-by-side.mp4",
    "qa": REVIEW_DIR / "assembly-qa.json",
    "comparison_plate": REVIEW_DIR / "comparison-plate.png",
}


class AssemblyError(RuntimeError):
    """A concise, user-facing preflight or assembly failure."""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(argv: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a tool without a shell and retain only textual diagnostics."""
    try:
        result = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as error:
        raise AssemblyError(f"Could not execute {Path(argv[0]).name}: {error}") from error
    if check and result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise AssemblyError(
            f"{Path(argv[0]).name} exited {result.returncode}: {detail[-4000:]}"
        )
    return result


def require_regular_file(path: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_file():
        raise AssemblyError(f"{label} must be an existing regular, non-symlink file: {path}")
    if path.stat().st_size <= 0:
        raise AssemblyError(f"{label} is empty: {path}")
    return path


def require_directory(path: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_dir():
        raise AssemblyError(f"{label} must be an existing, non-symlink directory: {path}")
    return path


def probe_media(ffprobe: str, path: Path) -> dict[str, Any]:
    result = run([
        ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)
    ])
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise AssemblyError(f"ffprobe returned invalid JSON for {path.name}") from error
    if not isinstance(value, dict) or not isinstance(value.get("streams"), list):
        raise AssemblyError(f"ffprobe did not find media streams in {path}")
    return value


def first_stream(probe: dict[str, Any], codec_type: str) -> dict[str, Any]:
    for stream in probe["streams"]:
        if stream.get("codec_type") == codec_type:
            return stream
    raise AssemblyError(f"Media is missing its {codec_type} stream")


def rational(value: Any) -> Fraction | None:
    if not isinstance(value, str) or value in {"", "0/0"}:
        return None
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError):
        return None


def duration_seconds(probe: dict[str, Any]) -> float:
    try:
        return float(probe.get("format", {}).get("duration"))
    except (TypeError, ValueError):
        raise AssemblyError("ffprobe did not report a valid media duration") from None


def load_delivery_video_path() -> Path:
    try:
        delivery = json.loads(DELIVERY_PATH.read_text(encoding="utf-8"))
        relative = delivery["outputs"]["xiaohongshu"]["path"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        raise AssemblyError(f"Cannot resolve the formal v02 video from {DELIVERY_PATH}") from None
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise AssemblyError("v02 delivery video path must stay inside its delivery directory")
    return V02_ROOT / relative_path


def scan_frames(frames_dir: Path) -> list[dict[str, Any]]:
    if frames_dir.is_symlink() or not frames_dir.is_dir():
        raise AssemblyError("--frames-dir must name an existing, non-symlink directory")
    frames_dir = frames_dir.resolve(strict=True)
    expected_names = [f"{index:04d}.png" for index in range(1, FRAME_COUNT + 1)]
    actual_names = sorted(path.name for path in frames_dir.glob("*.png"))
    if actual_names != expected_names:
        missing = sorted(set(expected_names) - set(actual_names))
        unexpected = sorted(set(actual_names) - set(expected_names))
        raise AssemblyError(
            "Frame directory must contain exactly 0001.png..0192.png; "
            f"missing={missing[:8]} unexpected={unexpected[:8]}"
        )

    result: list[dict[str, Any]] = []
    signature = b"\x89PNG\r\n\x1a\n"
    for name in expected_names:
        path = frames_dir / name
        if path.is_symlink() or not path.is_file():
            raise AssemblyError(f"Frame must be a regular, non-symlink file: {path}")
        size = path.stat().st_size
        if size < 24:
            raise AssemblyError(f"Frame is empty or too short to be a PNG: {path}")
        with path.open("rb") as stream:
            header = stream.read(24)
        if header[:8] != signature or header[12:16] != b"IHDR":
            raise AssemblyError(f"Frame has an invalid PNG signature or IHDR: {path}")
        width, height = struct.unpack(">II", header[16:24])
        if (width, height) != (WIDTH, HEIGHT):
            raise AssemblyError(
                f"Frame {name} is {width}x{height}; expected native {WIDTH}x{HEIGHT}"
            )
        result.append({"name": name, "bytes": size, "sha256": file_sha256(path)})
    return result


def find_chinese_font() -> dict[str, str]:
    pingfang_candidates = (
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("/System/Library/Fonts/PingFangSC.ttc"),
        Path("/System/Library/Fonts/Supplemental/PingFang.ttc"),
        Path("/Library/Fonts/PingFang.ttc"),
        Path.home() / "Library" / "Fonts" / "PingFang.ttc",
    )
    for path in pingfang_candidates:
        if path.is_file() and not path.is_symlink():
            return {
                "path": str(path),
                "family": "PingFang",
                "provenance": "Observed PingFang TTC in a standard macOS font directory.",
            }

    fallback = Path("/System/Library/Fonts/STHeiti Medium.ttc")
    if fallback.is_file() and not fallback.is_symlink():
        return {
            "path": str(fallback),
            "family": "STHeiti Medium",
            "provenance": (
                "PingFang was not found in the checked macOS font directories; "
                "using the observed system STHeiti Medium TTC fallback."
            ),
        }
    raise AssemblyError("No supported Chinese label font was found (PingFang or STHeiti Medium)")


def ffmpeg_filter_escape(value: str) -> str:
    """Escape a value that is single-quoted in an ffmpeg filtergraph."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def build_comparison_plate(font: dict[str, str], destination: Path) -> dict[str, Any]:
    try:
        from PIL import Image, ImageDraw, ImageFont
        import PIL
    except ImportError as error:
        raise AssemblyError("Run assembly with the existing bundled Python containing Pillow") from error
    canvas = Image.new("RGB", (1440, 1440), "#0c0c0e")
    draw = ImageDraw.Draw(canvas)
    face = ImageFont.truetype(font["path"], 42)
    for text, x in (("原版", 32), ("Blender 样片", 736)):
        draw.text((x+1, 77), text, font=face, fill="#000000", anchor="lt")
        draw.text((x, 75), text, font=face, fill="#f4ede0", anchor="lt")
    with destination.open("xb") as target:
        canvas.save(target, format="PNG")
    return {"path": str(destination.relative_to(STUDY_ROOT)),
            "sha256": file_sha256(destination), "pillow": PIL.__version__,
            "method": "Pillow text plate; no FFmpeg drawtext dependency"}


def loudness_measurement(ffmpeg: str, path: Path) -> dict[str, float]:
    result = run([
        ffmpeg, "-nostdin", "-hide_banner", "-nostats", "-v", "info",
        "-threads", THREADS, "-filter_threads", THREADS,
        "-i", str(path), "-map", "0:a:0",
        "-af", "loudnorm=I=-16:TP=-1:LRA=11:print_format=json",
        "-f", "null", "-",
    ])
    blocks = re.findall(r"\{\s*\"input_i\".*?\}", result.stderr, flags=re.DOTALL)
    for block in reversed(blocks):
        try:
            measurement = json.loads(block)
            return {"integrated_lufs": float(measurement["input_i"]),
                    "true_peak_dbTP": float(measurement["input_tp"]),
                    "loudness_range_lu": float(measurement["input_lra"])}
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    raise AssemblyError(f"Could not measure loudness for {path.name}")


def wave_details(path: Path) -> dict[str, Any]:
    try:
        with wave.open(str(path), "rb") as source:
            values = {
                "sample_rate": source.getframerate(),
                "channels": source.getnchannels(),
                "sample_width_bytes": source.getsampwidth(),
                "samples_per_channel": source.getnframes(),
                "compression": source.getcomptype(),
            }
    except (wave.Error, OSError) as error:
        raise AssemblyError(f"Could not read PCM WAV {path.name}: {error}") from error
    return values


def decoded_audio_pcm(ffmpeg: str, path: Path) -> bytes:
    decoded_audio = subprocess.run(
        [ffmpeg, "-nostdin", "-hide_banner", "-v", "error", "-xerror",
         "-threads", THREADS, "-filter_threads", THREADS, "-i", str(path),
         "-map", "0:a:0", "-f", "s16le", "-acodec", "pcm_s16le",
         "-ar", str(SAMPLE_RATE), "-ac", str(CHANNELS), "pipe:1"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if decoded_audio.returncode:
        diagnostic = decoded_audio.stderr.decode("utf-8", errors="replace").strip()
        raise AssemblyError(f"Audio decode failed for {path.name}: {diagnostic[-2000:]}")
    expected_bytes = SAMPLES_PER_CHANNEL * CHANNELS * 2
    if len(decoded_audio.stdout) != expected_bytes:
        raise AssemblyError(
            f"{path.name} decodes to {len(decoded_audio.stdout)} PCM bytes; "
            f"expected {expected_bytes} ({SAMPLES_PER_CHANNEL} samples/channel)"
        )
    return decoded_audio.stdout


def pcm16_peak_dbfs(pcm: bytes) -> float:
    if not pcm or len(pcm) % 2:
        raise AssemblyError("Decoded PCM must contain complete signed 16-bit samples")
    peak = max(abs(sample[0]) for sample in struct.iter_unpack("<h", pcm))
    if peak == 0:
        return float("-inf")
    return 20.0 * math.log10(peak / 32768.0)


def json_metric(value: float) -> float | None:
    return round(value, 6) if math.isfinite(value) else None


def strict_decode(ffmpeg: str, path: Path) -> None:
    run([
        ffmpeg, "-nostdin", "-hide_banner", "-v", "error", "-xerror", "-threads", THREADS,
        "-i", str(path), "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-",
    ])


def strict_decode_audio(ffmpeg: str, path: Path) -> None:
    run([
        ffmpeg, "-nostdin", "-hide_banner", "-v", "error", "-xerror", "-threads", THREADS,
        "-filter_threads", THREADS, "-i", str(path), "-map", "0:a:0", "-f", "null", "-",
    ])


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        raise AssemblyError(f"Refusing to replace existing QA report: {path}") from None
    created_stat = os.fstat(fd)
    identity = (created_stat.st_dev, created_stat.st_ino)
    try:
        with os.fdopen(fd, "wb") as target:
            target.write(payload)
            target.flush()
            os.fsync(target.fileno())
    except Exception:
        try:
            current_stat = path.lstat()
            if (current_stat.st_dev, current_stat.st_ino) == identity:
                path.unlink()
        except OSError:
            pass
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--frames-dir", required=True, type=Path,
        help="Directory containing exactly 0001.png through 0192.png at 1080x1920.",
    )
    parser.add_argument(
        "--validate-only", action="store_true",
        help="Check inputs, tool availability, font, and output collisions without writing files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    require_directory(MEDIA_DIR, "Study media directory")
    require_directory(REVIEW_DIR, "Study review directory")
    if not BRIEF_PATH.is_file() or BRIEF_PATH.is_symlink():
        raise AssemblyError(f"Study brief must be a regular file: {BRIEF_PATH}")
    if not DELIVERY_PATH.is_file() or DELIVERY_PATH.is_symlink():
        raise AssemblyError(f"Formal v02 delivery manifest is missing: {DELIVERY_PATH}")

    collisions = [path for path in OUTPUTS.values() if path.exists() or path.is_symlink()]
    if collisions:
        raise AssemblyError(
            "Refusing to overwrite study outputs; preserve them and use a new study directory: "
            + ", ".join(str(path) for path in collisions)
        )

    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise AssemblyError("Both ffmpeg and ffprobe must already be installed and on PATH")

    frames_dir = args.frames_dir.expanduser()
    frame_records = scan_frames(frames_dir)
    font = find_chinese_font()
    old_video_path = require_regular_file(load_delivery_video_path(), "Formal v02 video")
    score_path = require_regular_file(SCORE_PATH, "v02 score stem")
    sfx_path = require_regular_file(SFX_PATH, "v02 SFX stem")

    old_probe = probe_media(ffprobe, old_video_path)
    old_stream = first_stream(old_probe, "video")
    old_fps = rational(old_stream.get("avg_frame_rate")) or rational(old_stream.get("r_frame_rate"))
    if (old_stream.get("width"), old_stream.get("height")) != (2160, 3840):
        raise AssemblyError("Formal v02 source must be the native 2160x3840 portrait movie")
    if old_fps != Fraction(60, 1) or duration_seconds(old_probe) < 54.0:
        raise AssemblyError("Formal v02 source must provide 60fps video through the 46-54s interval")

    stem_probes = {"score": probe_media(ffprobe, score_path), "sfx": probe_media(ffprobe, sfx_path)}
    for label, value in stem_probes.items():
        stream = first_stream(value, "audio")
        if int(stream.get("sample_rate", 0)) != SAMPLE_RATE or int(stream.get("channels", 0)) != CHANNELS:
            raise AssemblyError(f"v02 {label} stem must be {SAMPLE_RATE}Hz stereo")
        if duration_seconds(value) < 54.0:
            raise AssemblyError(f"v02 {label} stem does not cover source interval 46-54s")

    inputs = {
        "study_brief": BRIEF_PATH,
        "v02_delivery_manifest": DELIVERY_PATH,
        "v02_video": old_video_path,
        "v02_score": score_path,
        "v02_sfx": sfx_path,
    }
    source_records = {
        name: {"path": str(path.relative_to(REPO_ROOT)), "bytes": path.stat().st_size,
               "sha256": file_sha256(path)}
        for name, path in inputs.items()
    }
    frame_dir_hash = hashlib.sha256()
    for record in frame_records:
        frame_dir_hash.update(record["name"].encode("ascii") + b"\0")
        frame_dir_hash.update(record["sha256"].encode("ascii") + b"\n")

    if args.validate_only:
        print(json.dumps({
            "status": "INPUTS_VALIDATED_NO_OUTPUTS_CREATED",
            "frames_dir": str(frames_dir.resolve()),
            "frame_count": len(frame_records),
            "frame_manifest_sha256": frame_dir_hash.hexdigest(),
            "output_paths_available": {key: str(path.relative_to(STUDY_ROOT)) for key, path in OUTPUTS.items()},
            "font": font,
            "source_hashes": source_records,
            "writes_performed": False,
        }, ensure_ascii=False, indent=2))
        return 0

    plate = build_comparison_plate(font, OUTPUTS["comparison_plate"])

    temp_mix = MEDIA_DIR / f".assemble-mix-{uuid.uuid4().hex}.wav"
    temp_mix_identity: tuple[int, int] | None = None
    if temp_mix.exists():
        raise AssemblyError("Unexpected temporary audio path collision; retry with a fresh invocation")
    try:
        score_filter = (
            f"atrim=start_sample={SOURCE_START_SAMPLE}:end_sample={SOURCE_END_SAMPLE},"
            "asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=flt:channel_layouts=stereo"
        )
        mix_graph = (
            f"[0:a]{score_filter}[score];[1:a]{score_filter}[sfx];"
            "[score][sfx]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0,"
            "atrim=duration=8,asetpts=PTS-STARTPTS[mix]"
        )
        run([
            ffmpeg, "-nostdin", "-hide_banner", "-v", "error", "-n", "-threads", THREADS,
            "-filter_threads", THREADS, "-i", str(score_path), "-i", str(sfx_path),
            "-filter_complex_threads", THREADS, "-filter_complex", mix_graph, "-map", "[mix]", "-t", "8", "-ar", "48000",
            "-ac", "2", "-c:a", "pcm_f32le", "-f", "wav", str(temp_mix),
        ])
        temp_stat = temp_mix.stat()
        temp_mix_identity = (temp_stat.st_dev, temp_stat.st_ino)

        mix_probe = probe_media(ffprobe, temp_mix)
        mix_stream = first_stream(mix_probe, "audio")
        if (int(mix_stream.get("sample_rate", 0)) != SAMPLE_RATE
                or int(mix_stream.get("channels", 0)) != CHANNELS
                or abs(duration_seconds(mix_probe) - DURATION_SECONDS) > 0.001):
            raise AssemblyError("Mixed float audio is not exactly 8 seconds of 48kHz stereo")

        input_loudness = loudness_measurement(ffmpeg, temp_mix)
        input_true_peak = input_loudness["true_peak_dbTP"]
        if not all(math.isfinite(v) for v in input_loudness.values()):
            raise AssemblyError("Source mix has no measurable finite study audio")
        # Music/SFX stems were attenuated for narration in the full film. Apply
        # one constant gain to the shared study mix, keeping their balance and
        # dynamics intact; never run dynamic normalization or a limiter.
        gain_db = min(STUDY_TARGET_LUFS - input_loudness["integrated_lufs"],
                      TRUE_PEAK_LIMIT_DBTP - input_true_peak)
        audio_filter = "atrim=duration=8,asetpts=PTS-STARTPTS"
        if abs(gain_db) > 0.000001:
            audio_filter = f"volume={gain_db:.6f}dB,{audio_filter}"

        audio_master = OUTPUTS["audio_master"]
        run([
            ffmpeg, "-nostdin", "-hide_banner", "-v", "error", "-n", "-threads", THREADS,
            "-i", str(temp_mix), "-map", "0:a:0", "-af", audio_filter, "-t", "8",
            "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", "-f", "wav", str(audio_master),
        ])
        master_wave = wave_details(audio_master)
        if (master_wave["sample_rate"] != SAMPLE_RATE or master_wave["channels"] != CHANNELS
                or master_wave["sample_width_bytes"] != 2
                or master_wave["samples_per_channel"] != SAMPLES_PER_CHANNEL
                or master_wave["compression"] != "NONE"):
            raise AssemblyError("Generated audio master failed exact PCM format/sample-count checks")
        master_loudness = loudness_measurement(ffmpeg, audio_master)
        master_true_peak = master_loudness["true_peak_dbTP"]
        if master_true_peak > TRUE_PEAK_LIMIT_DBTP + .05:
            raise AssemblyError(f"Generated PCM master exceeds the study peak ceiling at {master_true_peak:.2f} dBTP")

        master_audio_decoded = decoded_audio_pcm(ffmpeg, audio_master)
        master_audio_hash = hashlib.sha256(master_audio_decoded).hexdigest()
        master_sample_peak = pcm16_peak_dbfs(master_audio_decoded)
        if master_sample_peak >= 0.0:
            raise AssemblyError(f"Generated PCM master reaches full scale ({master_sample_peak:.2f} dBFS)")
        audio_input = str(audio_master)
        common_video_args = [
            "-threads", THREADS, "-filter_threads", THREADS, "-frames:v", str(FRAME_COUNT),
            "-fps_mode", "cfr", "-t", "8", "-c:v", "libx264", "-preset", "slow",
            "-crf", "16", "-pix_fmt", "yuv420p", "-color_primaries", "bt709",
            "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-movflags", "+faststart",
        ]

        sequence = str(frames_dir.resolve() / "%04d.png")
        new_video = OUTPUTS["new_video"]
        # Blender's AgX PNGs are display-referred sRGB. Set the RGB-to-YUV
        # matrix explicitly, then convert the transfer curve before tagging 709.
        png_to_video = (
            "scale=in_range=full:out_color_matrix=bt709:out_range=tv,format=yuv444p,"
            "colorspace=ispace=bt709:irange=tv:iprimaries=bt709:itrc=srgb:"
            "space=bt709:range=tv:primaries=bt709:trc=bt709:format=yuv420p"
        )
        run([
            ffmpeg, "-nostdin", "-hide_banner", "-v", "error", "-n", "-threads", THREADS,
            "-filter_threads", THREADS, "-framerate", "24", "-start_number", "1", "-i", sequence,
            "-i", audio_input, "-map", "0:v:0", "-map", "1:a:0", "-vf", png_to_video,
            *common_video_args, str(new_video),
        ])

        old_video = OUTPUTS["old_video"]
        old_filter = "fps=24,scale=1080:1920:flags=lanczos,setsar=1,format=yuv420p"
        run([
            ffmpeg, "-nostdin", "-hide_banner", "-v", "error", "-n", "-threads", THREADS,
            "-filter_threads", THREADS, "-ss", "46", "-i", str(old_video_path),
            "-i", audio_input, "-map", "0:v:0", "-map", "1:a:0", "-vf", old_filter,
            *common_video_args, str(old_video),
        ])

        comparison = OUTPUTS["comparison"]
        comparison_graph = (
            "[2:v]scale=out_color_matrix=bt709:out_range=tv,format=yuv420p[bg];"
            "[1:v]scale=672:1194:flags=lanczos,setsar=1[left];"
            "[0:v]scale=672:1194:flags=lanczos,setsar=1[right];"
            "[bg][left]overlay=x=32:y=170[tmp0];"
            "[tmp0][right]overlay=x=736:y=170[v]"
        )
        run([
            ffmpeg, "-nostdin", "-hide_banner", "-v", "error", "-n", "-threads", THREADS,
            "-filter_threads", THREADS, "-i", str(new_video), "-i", str(old_video),
            "-loop", "1", "-framerate", "24", "-i", str(OUTPUTS["comparison_plate"]),
            "-i", audio_input, "-filter_complex_threads", THREADS, "-filter_complex", comparison_graph, "-map", "[v]",
            "-map", "3:a:0", *common_video_args, str(comparison),
        ])

        outputs: dict[str, Any] = {}
        expected_video = (WIDTH, HEIGHT)
        pcm_hashes: dict[str, str] = {}
        for key in ("audio_master", "new_video", "old_video", "comparison"):
            path = OUTPUTS[key]
            if not path.is_file() or path.is_symlink() or path.stat().st_size <= 0:
                raise AssemblyError(f"Output is missing, empty, or unsafe: {path}")
            probe = probe_media(ffprobe, path)
            if key == "audio_master":
                strict_decode_audio(ffmpeg, path)
            else:
                strict_decode(ffmpeg, path)
            record: dict[str, Any] = {
                "path": str(path.relative_to(STUDY_ROOT)),
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
                "ffprobe": probe,
                "full_decode": "PASS",
            }
            if key == "audio_master":
                record["pcm"] = wave_details(path)
                record["true_peak_dbTP"] = json_metric(master_true_peak)
                record["sample_peak_dbFS"] = json_metric(master_sample_peak)
            else:
                video_stream = first_stream(probe, "video")
                audio_stream = first_stream(probe, "audio")
                fps_value = rational(video_stream.get("avg_frame_rate"))
                if key == "comparison":
                    dimensions = (1440, 1440)
                else:
                    dimensions = expected_video
                if (video_stream.get("width"), video_stream.get("height")) != dimensions:
                    raise AssemblyError(f"Unexpected encoded dimensions for {path.name}")
                counted = run([
                    ffprobe, "-v", "error", "-count_frames", "-select_streams", "v:0",
                    "-show_entries", "stream=nb_read_frames,avg_frame_rate,width,height",
                    "-of", "json", str(path),
                ])
                try:
                    counted_stream = json.loads(counted.stdout)["streams"][0]
                except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                    raise AssemblyError(f"Could not verify frame count for {path.name}") from None
                decoded_frames = counted_stream.get("nb_read_frames")
                counted_fps = rational(counted_stream.get("avg_frame_rate")) or fps_value
                if counted_fps != Fraction(FPS, 1) or str(decoded_frames) != str(FRAME_COUNT):
                    raise AssemblyError(f"{path.name} is not exactly {FRAME_COUNT} frames at {FPS}fps")
                record["decoded_video_frames"] = int(decoded_frames)
                if abs(duration_seconds(probe) - DURATION_SECONDS) > (1 / FPS):
                    raise AssemblyError(f"{path.name} duration is not exactly 8 seconds")
                if (int(audio_stream.get("sample_rate", 0)) != SAMPLE_RATE
                        or int(audio_stream.get("channels", 0)) != CHANNELS):
                    raise AssemblyError(f"{path.name} AAC track is not 48kHz stereo")
                pcm = decoded_audio_pcm(ffmpeg, path)
                sample_peak = pcm16_peak_dbfs(pcm)
                if sample_peak >= 0.0:
                    raise AssemblyError(f"AAC audio in {path.name} reaches full scale")
                pcm_hash = hashlib.sha256(pcm).hexdigest()
                pcm_hashes[key] = pcm_hash
                record["audio"] = {
                    "codec": audio_stream.get("codec_name"),
                    "sample_rate": int(audio_stream.get("sample_rate", 0)),
                    "channels": int(audio_stream.get("channels", 0)),
                    "decoded_samples_per_channel": len(pcm) // (CHANNELS * 2),
                    "decoded_pcm_sha256": pcm_hash,
                    "source_pcm_master_sha256": master_audio_hash,
                    "decoded_sample_peak_dbFS": json_metric(sample_peak),
                }
            outputs[key] = record

        if len(set(pcm_hashes.values())) != 1:
            raise AssemblyError("The three study videos do not carry the same decoded audio samples")
        for key in ("new_video", "old_video", "comparison"):
            outputs[key]["audio"]["decoded_aac_tracks_identical"] = True

        report: dict[str, Any] = {
            "schema_version": 1,
            "status": "PASS",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "scope": "8-second EP11 Blender porcelain-canyon material study only",
            "study_brief_sha256": source_records["study_brief"]["sha256"],
            "formal_v02_preserved": True,
            "source_inputs": source_records,
            "rendered_frames": {
                "directory": str(frames_dir.resolve()),
                "count": len(frame_records),
                "width": WIDTH,
                "height": HEIGHT,
                "fps": FPS,
                "sha256_manifest": frame_dir_hash.hexdigest(),
                "frames": frame_records,
            },
            "audio_provenance": {
                "sources": ["v02 score.wav", "v02 sfx.wav"],
                "source_interval_seconds": [46, 54],
                "source_interval_samples": [SOURCE_START_SAMPLE, SOURCE_END_SAMPLE],
                "sample_rate": SAMPLE_RATE,
                "channels": CHANNELS,
                "samples_per_channel": SAMPLES_PER_CHANNEL,
                "mix": "amix normalize=0; narration omitted; no new TTS",
                "input_mix_true_peak_dbTP": json_metric(input_true_peak),
                "input_mix_integrated_lufs": input_loudness["integrated_lufs"],
                "study_target_lufs": STUDY_TARGET_LUFS,
                "master_integrated_lufs": master_loudness["integrated_lufs"],
                "gain_mode": "constant gain shared by all editions; stem balance/dynamics unchanged",
                "peak_limit_dbTP": TRUE_PEAK_LIMIT_DBTP,
                "applied_gain_db": round(gain_db, 6),
                "master_true_peak_dbTP": json_metric(master_true_peak),
                "master_sample_peak_dbFS": json_metric(master_sample_peak),
                "master_decoded_pcm_sha256": master_audio_hash,
                "same_audio_decoded_in_all_mp4s": True,
            },
            "video_provenance": {
                "old_source_interval_seconds": [46, 54],
                "old_source_sha256": source_records["v02_video"]["sha256"],
                "old_clip_output": "1080x1920/24fps; downscaled from the formal 2160x3840/60fps source",
            },
            "encoding": {
                "ffmpeg": run([ffmpeg, "-version"]).stdout.splitlines()[0],
                "ffprobe": run([ffprobe, "-version"]).stdout.splitlines()[0],
                "threads": int(THREADS),
                "filter_threads": int(THREADS),
                "video_codec": "H.264 / libx264",
                "preset": "slow",
                "crf": 16,
                "fps": FPS,
                "pixel_format": "yuv420p",
                "color": "BT.709 limited-range",
                "new_png_color_conversion": png_to_video,
                "audio_codec": "AAC 192 kb/s",
                "faststart": True,
                "comparison_canvas": {"width": 1440, "height": 1440, "fps": FPS},
                "comparison_panels": [
                    {"label": "原版", "x": 32, "y": 170, "width": 672, "height": 1194},
                    {"label": "Blender 样片", "x": 736, "y": 170, "width": 672, "height": 1194},
                ],
                "comparison_font": font,
                "comparison_plate": plate,
                "upscale_claim": False,
            },
            "outputs": outputs,
            "acceptance": {
                "automated_assembly": "PASS",
                "human_review": "NOT_RUN",
                "target_device_playback": "NOT_RUN",
                "creative_acceptance": "NOT_RUN",
            },
        }
        report_path = OUTPUTS["qa"]
        atomic_write_json(report_path, report)
        print(json.dumps({
            "status": report["status"],
            "outputs": {key: str(path.relative_to(STUDY_ROOT)) for key, path in OUTPUTS.items()},
            "audio_samples_per_channel": SAMPLES_PER_CHANNEL,
            "frame_count": FRAME_COUNT,
            "human_review": "NOT_RUN",
            "target_device_playback": "NOT_RUN",
        }, ensure_ascii=False, indent=2))
        return 0
    finally:
        try:
            if temp_mix_identity is not None and temp_mix.exists() and not temp_mix.is_symlink():
                current_stat = temp_mix.stat()
                if (current_stat.st_dev, current_stat.st_ino) == temp_mix_identity:
                    temp_mix.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssemblyError as error:
        print(f"assemble.py: {error}", file=sys.stderr)
        raise SystemExit(2) from None
