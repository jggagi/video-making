#!/usr/bin/env python3
"""Reproducible metadata, PCM, subtitle, and final-export checks for QStory EP03."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import wave
from fractions import Fraction
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TIMELINE_PATH = ROOT / "source" / "EP03_timeline.json"
NARRATION_PATH = ROOT / "source" / "EP03_narration_zh.txt"
AUDIO_TIMING_PATH = ROOT / "src" / "audio-timing.json"
AUDIO_DIR = ROOT / "public" / "audio-bailian"
BASELINE_AUDIO_DIR = ROOT / "public" / "audio"
VIDEO_PATH = ROOT / "out" / "QStory-EP03-十万亿个分身-4K.mp4"
SRT_PATH = ROOT / "out" / "QStory-EP03-zh.srt"
REPORT_PATH = ROOT / "review" / "validation.json"

FPS = 30
TOTAL_SECONDS = 180
TOTAL_FRAMES = FPS * TOTAL_SECONDS
SAMPLE_RATE = 48_000
TOTAL_SAMPLES = SAMPLE_RATE * TOTAL_SECONDS
SILENCE_START_SECONDS = 129
SILENCE_END_SECONDS = 130
SILENCE_START_FRAME = SILENCE_START_SECONDS * FPS
SILENCE_END_FRAME = SILENCE_END_SECONDS * FPS
SILENCE_START_SAMPLE = SILENCE_START_SECONDS * SAMPLE_RATE
SILENCE_SAMPLE_COUNT = (SILENCE_END_SECONDS - SILENCE_START_SECONDS) * SAMPLE_RATE

WAVS = {
    "voice_zh.wav": {"channels": 1, "sampleWidthBytes": 2},
    "music.wav": {"channels": 2, "sampleWidthBytes": 2},
    "sfx.wav": {"channels": 2, "sampleWidthBytes": 2},
    "soundtrack.wav": {"channels": 2, "sampleWidthBytes": 3},
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def frame_time(frame: int, fps: int = FPS) -> str:
    # Nearest millisecond, using integer arithmetic for deterministic SRT output.
    milliseconds = (int(frame) * 1000 + fps // 2) // fps
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def render_srt(cues: list[dict[str, Any]]) -> str:
    blocks = []
    for index, cue in enumerate(cues, start=1):
        start = frame_time(cue["fromFrame"])
        end = frame_time(cue["toFrameExclusive"])
        blocks.append(f"{index}\n{start} --> {end}\n{cue['text']}")
    return "\n\n".join(blocks) + "\n"


def write_srt(cues: list[dict[str, Any]]) -> None:
    SRT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SRT_PATH.write_text(render_srt(cues), encoding="utf-8")


class Validation:
    def __init__(self, mode: str):
        self.mode = mode
        self.checks: list[dict[str, Any]] = []
        self.video_observation: dict[str, Any] = {"path": str(VIDEO_PATH.relative_to(ROOT)), "status": "not_checked"}

    def record(
        self,
        check_id: str,
        passed: bool | None,
        expected: Any,
        actual: Any,
        detail: str | None = None,
    ) -> None:
        status = "passed" if passed is True else "failed" if passed is False else "pending"
        item: dict[str, Any] = {
            "id": check_id,
            "status": status,
            "expected": expected,
            "actual": actual,
        }
        if detail:
            item["detail"] = detail
        self.checks.append(item)

    def not_performed(self, check_id: str, detail: str) -> None:
        self.checks.append({"id": check_id, "status": "not_performed", "detail": detail})

    def finish(self) -> dict[str, Any]:
        counts = {status: sum(1 for check in self.checks if check["status"] == status)
                  for status in ("passed", "failed", "pending", "not_performed")}
        overall = "failed" if counts["failed"] else "passed_with_pending" if counts["pending"] else "passed"
        input_hashes: dict[str, Any] = {}
        for path in (TIMELINE_PATH, NARRATION_PATH, AUDIO_TIMING_PATH):
            key = str(path.relative_to(ROOT))
            input_hashes[key] = sha256(path) if path.is_file() else None

        deliverable_paths = [SRT_PATH, *(AUDIO_DIR / name for name in WAVS), VIDEO_PATH]
        deliverable_hashes: dict[str, Any] = {}
        for path in deliverable_paths:
            key = str(path.relative_to(ROOT))
            deliverable_hashes[key] = sha256(path) if path.is_file() else None

        script_path = Path(__file__).resolve()
        root_review = {
            "status": "not_reported_by_this_run",
            "detail": "Root-owned static-frame visual review is reported separately; this script does not infer visual acceptance from metadata or decode checks.",
        }
        human_review = {
            "humanListening": {"status": "not_performed", "detail": "No human listening evidence was supplied to this validator."},
            "audienceVisualAcceptance": {"status": "not_performed", "detail": "No audience acceptance evidence was supplied to this validator."},
            "rootStaticFrameVisualCheck": root_review,
        }
        return {
            "schemaVersion": 1,
            "mode": self.mode,
            "status": overall,
            "summary": counts,
            "specification": {
                "width": 3840,
                "height": 2160,
                "fps": FPS,
                "frames": TOTAL_FRAMES,
                "durationSeconds": TOTAL_SECONDS,
                "videoCodec": "h264",
                "pixelFormat": "yuv420p",
                "color": "BT.709",
                "audioCodec": "aac",
                "audioSampleRate": SAMPLE_RATE,
                "audioChannels": 2,
                "audioProvider": "Aliyun Bailian",
                "audioModel": "cosyvoice-v3-flash",
                "audioVoice": "longtian_v3",
                "pcmSamplesPerFullLengthAudioFile": TOTAL_SAMPLES,
            },
            "videoObservation": self.video_observation,
            "checks": self.checks,
            "review": human_review,
            "sha256": {
                "sourceInputs": input_hashes,
                "baselineAudioProvenance": {
                    name: sha256(BASELINE_AUDIO_DIR / name) if (BASELINE_AUDIO_DIR / name).is_file() else None
                    for name in ("music.wav", "sfx.wav")
                },
                "deliverables": deliverable_hashes,
                "validator": sha256(script_path) if script_path.is_file() else None,
                "validationReportSelfHash": "not_applicable",
            },
        }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def spoken_lines_from_narration(path: Path) -> str:
    active = False
    speech: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("[") and "]" in line:
            active = True
            continue
        if active and line:
            speech.append(line)
    return "".join(speech)


def validate_periods(v: Validation, name: str, items: list[dict[str, Any]], expected_count: int) -> None:
    v.record(f"timeline.{name}.count", len(items) == expected_count, expected_count, len(items))
    cursor = 0
    seen: set[str] = set()
    for item in items:
        item_id = str(item.get("id", "<missing-id>"))
        from_frame = item.get("fromFrame")
        duration = item.get("durationInFrames")
        end_frame = from_frame + duration if isinstance(from_frame, int) and isinstance(duration, int) else None
        unique = item_id not in seen
        v.record(f"timeline.{name}.{item_id}.unique_id", unique, True, unique)
        seen.add(item_id)
        v.record(f"timeline.{name}.{item_id}.continuous_start", from_frame == cursor, cursor, from_frame)
        v.record(f"timeline.{name}.{item_id}.positive_duration", isinstance(duration, int) and duration > 0, "> 0", duration)
        if end_frame is not None:
            v.record(f"timeline.{name}.{item_id}.declared_end", end_frame == round(float(item.get("endSec", -1)) * FPS),
                     end_frame, round(float(item.get("endSec", -1)) * FPS))
            v.record(f"timeline.{name}.{item_id}.declared_start", from_frame == round(float(item.get("startSec", -1)) * FPS),
                     from_frame, round(float(item.get("startSec", -1)) * FPS))
            cursor = end_frame
    v.record(f"timeline.{name}.covers_full_duration", cursor == TOTAL_FRAMES, TOTAL_FRAMES, cursor)


def validate_timeline_and_cues(v: Validation) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    try:
        timeline = load_json(TIMELINE_PATH)
    except Exception as exc:  # Keep a machine-readable failed report for malformed input.
        v.record("timeline.read", False, "valid JSON source timeline", str(exc))
        return None, []

    v.record("timeline.fps", timeline.get("fps") == FPS, FPS, timeline.get("fps"))
    v.record("timeline.duration_frames", timeline.get("durationInFrames") == TOTAL_FRAMES,
             TOTAL_FRAMES, timeline.get("durationInFrames"))
    v.record("timeline.duration_seconds", timeline.get("durationSec") == TOTAL_SECONDS,
             TOTAL_SECONDS, timeline.get("durationSec"))
    validate_periods(v, "scenes", timeline.get("scenes", []), 8)
    validate_periods(v, "shots", timeline.get("shots", []), 24)

    scenes = {scene.get("id"): scene for scene in timeline.get("scenes", [])}
    shots = {shot.get("id"): shot for shot in timeline.get("shots", [])}
    for shot in timeline.get("shots", []):
        scene = scenes.get(shot.get("sceneId"))
        inside = bool(scene) and scene["fromFrame"] <= shot["fromFrame"] and (
            shot["fromFrame"] + shot["durationInFrames"] <= scene["fromFrame"] + scene["durationInFrames"]
        )
        v.record(f"timeline.shot.{shot.get('id')}.within_scene", inside, True, inside)

    source_cues = timeline.get("captions", [])
    expected_ids = [f"caption-{index:03d}" for index in range(1, 26)]
    v.record("source_cues.count", len(source_cues) == 25, 25, len(source_cues))
    source_ids = [cue.get("id") for cue in source_cues]
    v.record("source_cues.id_order", source_ids == expected_ids, expected_ids, source_ids)

    try:
        narration = spoken_lines_from_narration(NARRATION_PATH)
        shot_text = "".join(str(shot.get("voice", "")) for shot in timeline.get("shots", []))
        v.record("source_narration.concatenation_unchanged", narration == shot_text,
                 {"characters": len(shot_text), "sha256": hashlib.sha256(shot_text.encode("utf-8")).hexdigest()},
                 {"characters": len(narration), "sha256": hashlib.sha256(narration.encode("utf-8")).hexdigest()})
    except Exception as exc:
        v.record("source_narration.concatenation_unchanged", False, "narration text matches shot voice", str(exc))

    silence_cues = timeline.get("soundCues", [])
    silence_matches = any(
        cue.get("id") == "hard-silence"
        and cue.get("fromFrame") == SILENCE_START_FRAME
        and cue.get("toFrameExclusive") == SILENCE_END_FRAME
        and set(cue.get("tracks", [])) == {"voice", "music", "sfx"}
        for cue in silence_cues
    )
    v.record("timeline.hard_silence_window", silence_matches,
             {"fromFrame": SILENCE_START_FRAME, "toFrameExclusive": SILENCE_END_FRAME,
              "tracks": ["voice", "music", "sfx"]}, silence_cues)

    try:
        timing = load_json(AUDIO_TIMING_PATH)
    except Exception as exc:
        v.record("audio_timing.read", False, "valid JSON actual cue timing", str(exc))
        return timeline, []

    v.record("audio_timing.sample_rate", timing.get("sampleRate") == SAMPLE_RATE, SAMPLE_RATE, timing.get("sampleRate"))
    v.record("audio_timing.duration", timing.get("durationSeconds") == TOTAL_SECONDS, TOTAL_SECONDS,
             timing.get("durationSeconds"))
    v.record("audio_timing.provider", timing.get("provider") == "Aliyun Bailian",
             "Aliyun Bailian", timing.get("provider"))
    v.record("audio_timing.model", timing.get("model") == "cosyvoice-v3-flash",
             "cosyvoice-v3-flash", timing.get("model"))
    v.record("audio_timing.voice", timing.get("voice") == "longtian_v3",
             "longtian_v3", timing.get("voice"))
    actual_cues = timing.get("cues", [])
    v.record("audio_timing.cue_count", len(actual_cues) == len(source_cues), len(source_cues), len(actual_cues))
    actual_ids = [cue.get("id") for cue in actual_cues]
    v.record("audio_timing.cue_id_order", actual_ids == source_ids, source_ids, actual_ids)

    previous_end = -1
    actual_spoken: list[str] = []
    for cue in actual_cues:
        cue_id = str(cue.get("id", "<missing-id>"))
        source = next((item for item in source_cues if item.get("id") == cue.get("id")), None)
        from_frame = cue.get("fromFrame")
        to_frame = cue.get("toFrameExclusive")
        valid_window = isinstance(from_frame, int) and isinstance(to_frame, int) and 0 <= from_frame < to_frame <= TOTAL_FRAMES
        v.record(f"audio_timing.{cue_id}.valid_window", valid_window, "0 <= start < end <= 5400",
                 {"fromFrame": from_frame, "toFrameExclusive": to_frame})
        cue_shot = shots.get(cue.get("shotId"))
        within_shot = bool(cue_shot) and valid_window and (
            cue_shot["fromFrame"] <= from_frame
            and to_frame <= cue_shot["fromFrame"] + cue_shot["durationInFrames"]
        )
        v.record(f"audio_timing.{cue_id}.within_corresponding_shot", within_shot, cue.get("shotId"),
                 {"fromFrame": from_frame, "toFrameExclusive": to_frame})
        no_overlap = valid_window and from_frame >= previous_end
        v.record(f"audio_timing.{cue_id}.no_overlap", no_overlap, f"start >= previous end ({previous_end})",
                 from_frame)
        if valid_window:
            previous_end = to_frame
        no_silence_overlap = valid_window and not (
            from_frame < SILENCE_END_FRAME and to_frame > SILENCE_START_FRAME
        )
        v.record(f"audio_timing.{cue_id}.avoids_129_130s", no_silence_overlap,
                 "outside [129s, 130s)", {"fromFrame": from_frame, "toFrameExclusive": to_frame})
        exact = source is not None and all(cue.get(key) == source.get(key) for key in ("id", "text", "shotId", "speaker"))
        v.record(f"audio_timing.{cue_id}.matches_source", exact,
                 {key: source.get(key) for key in ("id", "text", "shotId", "speaker")} if source else "source cue exists",
                 {key: cue.get(key) for key in ("id", "text", "shotId", "speaker")})
        actual_spoken.append(str(cue.get("text", "")))

    source_spoken = "".join(str(cue.get("text", "")) for cue in source_cues)
    spoken_matches = "".join(actual_spoken) == source_spoken == "".join(
        str(shot.get("voice", "")) for shot in timeline.get("shots", [])
    )
    v.record("audio_timing.narration_concatenation_unchanged", spoken_matches,
             {"characters": len(source_spoken), "sha256": hashlib.sha256(source_spoken.encode("utf-8")).hexdigest()},
             {"characters": len("".join(actual_spoken)), "sha256": hashlib.sha256("".join(actual_spoken).encode("utf-8")).hexdigest()})
    return timeline, actual_cues


def validate_wavs(v: Validation) -> None:
    for name, expected in WAVS.items():
        path = AUDIO_DIR / name
        if not path.is_file():
            v.record(f"audio.{name}.exists", False, True, False)
            continue
        try:
            with wave.open(str(path), "rb") as wav:
                frames = wav.getnframes()
                rate = wav.getframerate()
                channels = wav.getnchannels()
                width = wav.getsampwidth()
                params = {"frames": frames, "sampleRate": rate, "channels": channels, "sampleWidthBytes": width}
                v.record(f"audio.{name}.full_length", frames == TOTAL_SAMPLES, TOTAL_SAMPLES, frames)
                v.record(f"audio.{name}.sample_rate", rate == SAMPLE_RATE, SAMPLE_RATE, rate)
                v.record(f"audio.{name}.channels", channels == expected["channels"], expected["channels"], channels)
                v.record(f"audio.{name}.sample_width", width == expected["sampleWidthBytes"],
                         expected["sampleWidthBytes"], width,
                         "WAV sample width is measured in bytes (2=16-bit PCM, 3=24-bit PCM).")
                if rate == SAMPLE_RATE and frames >= SILENCE_START_SAMPLE + SILENCE_SAMPLE_COUNT:
                    wav.setpos(SILENCE_START_SAMPLE)
                    silence_pcm = wav.readframes(SILENCE_SAMPLE_COUNT)
                    expected_bytes = SILENCE_SAMPLE_COUNT * channels * width
                    is_silent = len(silence_pcm) == expected_bytes and not any(silence_pcm)
                    v.record(f"audio.{name}.exact_129_130s_pcm_silence", is_silent, expected_bytes,
                             {"readBytes": len(silence_pcm), "allBytesZero": not any(silence_pcm) if silence_pcm else None,
                              "frames": SILENCE_SAMPLE_COUNT})
                else:
                    v.record(f"audio.{name}.exact_129_130s_pcm_silence", False,
                             "full-rate silence window available", params)
        except (OSError, EOFError, wave.Error) as exc:
            v.record(f"audio.{name}.readable_pcm", False, "readable PCM WAV", str(exc))

    for name in ("music.wav", "sfx.wav"):
        final_path = AUDIO_DIR / name
        baseline_path = BASELINE_AUDIO_DIR / name
        if not final_path.is_file() or not baseline_path.is_file():
            v.record(f"audio.{name}.matches_local_baseline_sha256", False,
                     "final and local baseline files exist", {
                         "finalExists": final_path.is_file(),
                         "baselineExists": baseline_path.is_file(),
                     })
            continue
        final_hash = sha256(final_path)
        baseline_hash = sha256(baseline_path)
        v.record(f"audio.{name}.matches_local_baseline_sha256", final_hash == baseline_hash,
                 baseline_hash, final_hash)


def parse_duration(stream: dict[str, Any]) -> float | None:
    duration = stream.get("duration")
    if duration not in (None, "N/A"):
        try:
            return float(duration)
        except (TypeError, ValueError):
            pass
    duration_ts = stream.get("duration_ts")
    time_base = stream.get("time_base")
    if duration_ts not in (None, "N/A") and time_base not in (None, "N/A"):
        try:
            return float(Fraction(str(duration_ts)) * Fraction(str(time_base)))
        except (ValueError, ZeroDivisionError):
            return None
    return None


def frame_rate(stream: dict[str, Any], key: str) -> Fraction | None:
    raw = stream.get(key)
    if raw in (None, "N/A"):
        return None
    try:
        return Fraction(str(raw))
    except (ValueError, ZeroDivisionError):
        return None


def validate_video(v: Validation) -> None:
    exists = VIDEO_PATH.is_file()
    if not exists:
        if v.mode == "metadata-only":
            v.record("video.exists", None, True, False, "Final MP4 is absent; metadata-only mode leaves video delivery pending.")
            v.not_performed("video.metadata", "Final MP4 does not exist yet.")
            v.not_performed("video.full_decode", "Final MP4 does not exist yet.")
            v.video_observation.update({"status": "pending", "exists": False})
        else:
            v.record("video.exists", False, True, False, "--full requires the final MP4.")
            v.not_performed("video.metadata", "Final MP4 does not exist.")
            v.not_performed("video.full_decode", "Final MP4 does not exist.")
            v.video_observation.update({"status": "missing", "exists": False})
        return

    v.record("video.exists", True, True, True)
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        v.record("video.ffprobe_available", False, True, False)
        v.video_observation.update({"status": "probe_unavailable", "exists": True})
        v.not_performed("video.full_decode", "ffprobe is unavailable; metadata was not checked.")
        return

    command = [
        ffprobe, "-v", "error", "-count_frames", "-show_format", "-show_streams",
        "-show_entries",
        "format=duration:stream=index,codec_type,codec_name,width,height,pix_fmt,r_frame_rate,avg_frame_rate,nb_frames,nb_read_frames,color_primaries,color_transfer,color_space,sample_rate,channels,channel_layout,duration,duration_ts,time_base",
        "-of", "json", str(VIDEO_PATH),
    ]
    try:
        probe = subprocess.run(command, check=True, capture_output=True, text=True)
        data = json.loads(probe.stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        v.record("video.ffprobe", False, "valid ffprobe metadata", str(exc))
        v.video_observation.update({"status": "probe_failed", "exists": True, "error": str(exc)})
        v.not_performed("video.full_decode", "Video metadata probe failed.")
        return

    streams = data.get("streams", [])
    video_streams = [stream for stream in streams if stream.get("codec_type") == "video"]
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
    format_duration_raw = data.get("format", {}).get("duration")
    try:
        container_duration = float(format_duration_raw)
    except (TypeError, ValueError):
        container_duration = None
    observation: dict[str, Any] = {
        "status": "probed",
        "exists": True,
        "containerDurationSeconds": container_duration,
        "videoStreams": video_streams,
        "audioStreams": audio_streams,
    }
    v.video_observation.update(observation)

    v.record("video.video_stream_count", len(video_streams) == 1, 1, len(video_streams))
    v.record("video.audio_stream_count", len(audio_streams) == 1, 1, len(audio_streams))
    if len(video_streams) == 1:
        stream = video_streams[0]
        v.record("video.codec", stream.get("codec_name") == "h264", "h264", stream.get("codec_name"))
        v.record("video.width", stream.get("width") == 3840, 3840, stream.get("width"))
        v.record("video.height", stream.get("height") == 2160, 2160, stream.get("height"))
        v.record("video.pixel_format", stream.get("pix_fmt") == "yuv420p", "yuv420p", stream.get("pix_fmt"))
        for key in ("r_frame_rate", "avg_frame_rate"):
            parsed = frame_rate(stream, key)
            v.record(f"video.{key}", parsed == Fraction(FPS, 1), f"{FPS}/1", stream.get(key))
        raw_frames = stream.get("nb_read_frames", stream.get("nb_frames"))
        try:
            count_frames = int(raw_frames)
        except (TypeError, ValueError):
            count_frames = None
        v.record("video.frame_count", count_frames == TOTAL_FRAMES, TOTAL_FRAMES, count_frames)
        stream_duration = parse_duration(stream)
        v.record("video.stream_duration_seconds", stream_duration is not None and abs(stream_duration - TOTAL_SECONDS) <= 1e-6,
                 TOTAL_SECONDS, stream_duration)
        for key in ("color_primaries", "color_transfer", "color_space"):
            v.record(f"video.{key}", stream.get(key) == "bt709", "bt709", stream.get(key))
    else:
        stream_duration = None
        v.not_performed("video.video_stream_metadata", "Expected exactly one video stream.")

    if len(audio_streams) == 1:
        stream = audio_streams[0]
        v.record("video.audio_codec", stream.get("codec_name") == "aac", "aac", stream.get("codec_name"))
        try:
            rate = int(stream.get("sample_rate"))
        except (TypeError, ValueError):
            rate = None
        v.record("video.audio_sample_rate", rate == SAMPLE_RATE, SAMPLE_RATE, rate)
        v.record("video.audio_channels", stream.get("channels") == 2, 2, stream.get("channels"))
        audio_duration = parse_duration(stream)
        aac_packet_tolerance = 1024 / SAMPLE_RATE + 1e-6
        v.record("video.audio_stream_duration_seconds",
                 audio_duration is not None and abs(audio_duration - TOTAL_SECONDS) <= aac_packet_tolerance,
                 {"seconds": TOTAL_SECONDS, "toleranceSeconds": aac_packet_tolerance}, audio_duration,
                 "Audio stream duration is reported separately; tolerance allows one AAC packet of encoder padding.")
    else:
        audio_duration = None
        v.not_performed("video.audio_stream_metadata", "Expected exactly one audio stream.")

    container_tolerance = 1024 / SAMPLE_RATE + 1e-6
    v.record("video.container_duration_seconds",
             container_duration is not None and abs(container_duration - TOTAL_SECONDS) <= container_tolerance,
             {"seconds": TOTAL_SECONDS, "toleranceSeconds": container_tolerance}, container_duration,
             "Container duration is reported separately from each stream; tolerance allows one AAC packet of encoder padding.")
    v.video_observation.update({
        "videoStreamDurationSeconds": stream_duration,
        "audioStreamDurationSeconds": audio_duration,
        "containerDurationToleranceSeconds": container_tolerance,
    })

    if v.mode != "full":
        v.not_performed("video.full_decode", "Metadata-only mode does not decode the final MP4.")
        return
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        v.record("video.ffmpeg_available", False, True, False)
        return
    decode_command = [
        ffmpeg, "-hide_banner", "-nostats", "-loglevel", "error", "-threads", "2",
        "-i", str(VIDEO_PATH), "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-",
    ]
    try:
        decoded = subprocess.run(decode_command, capture_output=True, text=True)
        detail = decoded.stderr.strip() or None
        v.record("video.full_decode", decoded.returncode == 0,
                 "full audio/video decode succeeds with one ffmpeg process and two decoder threads",
                 {"exitCode": decoded.returncode, "command": decode_command}, detail)
    except OSError as exc:
        v.record("video.full_decode", False, "ffmpeg executable runs", str(exc))


def run_validation(mode: str) -> tuple[Validation, list[dict[str, Any]]]:
    v = Validation(mode)
    timeline, actual_cues = validate_timeline_and_cues(v)
    validate_wavs(v)
    try:
        write_srt(actual_cues)
        v.record("subtitle.srt_written", SRT_PATH.is_file(), str(SRT_PATH.relative_to(ROOT)), SRT_PATH.is_file())
        v.record("subtitle.srt_cue_count", SRT_PATH.read_text(encoding="utf-8").count(" --> ") == len(actual_cues),
                 len(actual_cues), SRT_PATH.read_text(encoding="utf-8").count(" --> "))
        actual_srt = SRT_PATH.read_text(encoding="utf-8")
        expected_srt = render_srt(actual_cues)
        v.record("subtitle.srt_matches_actual_cues", actual_srt == expected_srt,
                 hashlib.sha256(expected_srt.encode("utf-8")).hexdigest(),
                 hashlib.sha256(actual_srt.encode("utf-8")).hexdigest())
    except (KeyError, TypeError, ValueError, OSError) as exc:
        v.record("subtitle.srt_written", False, "SRT generated from actual cue frames", str(exc))
    validate_video(v)
    return v, actual_cues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--metadata-only", action="store_true", help="check source/audio and probe video metadata if present")
    modes.add_argument("--full", action="store_true", help="also require and fully decode the final MP4")
    args = parser.parse_args()
    mode = "full" if args.full else "metadata-only"

    validation, _ = run_validation(mode)
    report = validation.finish()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "mode": mode,
        "summary": report["summary"],
        "report": str(REPORT_PATH.relative_to(ROOT)),
        "srt": str(SRT_PATH.relative_to(ROOT)),
        "video": report["videoObservation"],
    }, ensure_ascii=False, indent=2))
    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, wave.Error) as exc:
        print(f"delivery validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
