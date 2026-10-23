#!/usr/bin/env python3
"""Mux the verified EP18 silent video track with its current measured PCM master."""

from pathlib import Path
import hashlib
import json
import os
import subprocess
import wave

PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT.parent

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def resolve_inside_work(relative: str) -> Path:
    root = WORK.resolve(strict=True)
    path = (WORK / relative).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise RuntimeError("Manifest path must resolve to a file inside this EP18 delivery")
    return path

manifest = json.loads((WORK / "delivery.json").read_text(encoding="utf-8"))
assert manifest.get("slug") == "si-ep18-sovereign-subcurrent" and manifest.get("title") == "心印潜流"
assert manifest.get("platforms") == ["xiaohongshu"] and set(manifest.get("outputs", {})) == {"xiaohongshu"}
assert manifest.get("duration_seconds") == 90 and manifest.get("fps") == 60 and manifest.get("total_frames") == 5400
output_meta = manifest["outputs"]["xiaohongshu"]
assert (output_meta.get("width"), output_meta.get("height")) == (2160, 3840)

pointer_path = WORK / "review" / "render-staging.json"
pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
video_only = Path(pointer["file"]).resolve(strict=True)
assert pointer.get("status") == "READY" and str(video_only).startswith("/Volumes/AgentDev/")
assert pointer.get("capture", {}).get("remotion") == "4.0.534" and pointer.get("capture", {}).get("concurrency") == 1
assert pointer.get("capture", {}).get("pixelFormat") == "yuv420p" and pointer.get("capture", {}).get("colorSpace") == "bt709"
assert sha256_file(video_only) == pointer.get("sha256") and video_only.stat().st_size == pointer.get("bytes")
master = resolve_inside_work(manifest["audio"]["master"])
mix_qa_path = WORK / "review" / "audio-mix-qa.json"
mix_qa = json.loads(mix_qa_path.read_text(encoding="utf-8"))
assert mix_qa.get("status") == "pass" and mix_qa.get("masterSha256") == sha256_file(master)
with wave.open(str(master), "rb") as wav:
    audio_format = (wav.getframerate(), wav.getnchannels(), wav.getnframes(), wav.getsampwidth(), wav.getcomptype())
assert audio_format == (48000, 2, 4320000, 2, "NONE"), f"Unexpected PCM master format: {audio_format}"

relative_output = manifest["outputs"]["xiaohongshu"]["path"]
assert relative_output == "小红书/si-ep18-sovereign-subcurrent-xiaohongshu-90s-portrait.mp4"
output = (WORK / relative_output).resolve()
assert output.is_relative_to(WORK.resolve()) and output.suffix.lower() == ".mp4"
output.parent.mkdir(parents=True, exist_ok=True)
partial = output.with_name(output.stem + ".mux-partial.mp4")
report_path = WORK / "review" / "mux-provenance.json"
assert not output.exists() and not partial.exists(), "Refusing to overwrite an existing final or partial movie"
assert not report_path.exists(), "Refusing to overwrite existing mux provenance"
subprocess.run([
    "ffmpeg", "-hide_banner", "-v", "error", "-n",
    "-i", str(video_only), "-i", str(master),
    "-map", "0:v:0", "-map", "1:a:0",
    "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-ac", "2",
    "-movflags", "+faststart", str(partial),
], check=True)
probe = json.loads(subprocess.check_output([
    "ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(partial)
], text=True))
video = next(row for row in probe["streams"] if row.get("codec_type") == "video")
audio = next(row for row in probe["streams"] if row.get("codec_type") == "audio")
container = probe["format"]
video_frames = int(video.get("nb_read_frames", video.get("nb_frames", 0)))
assert (video.get("codec_name"), video.get("pix_fmt"), int(video["width"]), int(video["height"]), video.get("r_frame_rate"), video_frames) == ("h264", "yuv420p", 2160, 3840, "60/1", 5400)
assert abs(float(video.get("duration", 0)) - 90.0) <= 1 / 60 + 0.001
assert (audio.get("codec_name"), audio.get("sample_rate"), int(audio.get("channels", 0))) == ("aac", "48000", 2)
assert abs(float(audio.get("duration", 0)) - 90.0) < 0.05 and abs(float(container.get("duration", 0)) - 90.0) < 0.05
os.link(partial, output)
partial.unlink()
report = {
    "status": "PASS",
    "work": manifest["slug"],
    "title": manifest["title"],
    "platform": "xiaohongshu",
    "movie": str(output.relative_to(WORK)),
    "movieSha256": sha256_file(output),
    "masterSha256": sha256_file(master),
    "videoOnlySha256": sha256_file(video_only),
    "audioMixQaSha256": sha256_file(mix_qa_path),
    "video": {"codec": video.get("codec_name"), "pixelFormat": video.get("pix_fmt"), "width": 2160, "height": 3840, "fps": "60/1", "frames": video_frames, "durationSeconds": float(video["duration"])},
    "audio": {"codec": audio.get("codec_name"), "sampleRateHz": int(audio["sample_rate"]), "channels": int(audio["channels"]), "durationSeconds": float(audio["duration"]), "pcmSamplesPerChannel": 4320000},
    "containerDurationSeconds": float(container["duration"]),
}
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(report, ensure_ascii=False))
