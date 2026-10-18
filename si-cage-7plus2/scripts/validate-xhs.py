#!/usr/bin/env python3
"""Validate the EP02 Xiaohongshu portrait exports and their local audio receipt.

This validator is local-only. It probes both H.264/AAC exports, strictly decodes
each movie once, extracts the master keyframes during that decode, and keeps
automated evidence separate from human review and platform-upload acceptance.
"""

from __future__ import annotations

import array
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import wave


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
TIMELINE = ROOT / "xhs-timeline.json"
BEFORE = OUT / "xhs-v1-before.json"
AUDIO_MANIFEST = OUT / "xhs-v1-audio-manifest.json"
PCM_MASTER = ROOT / "public/audio-xhs-v1/soundtrack.wav"
NOISE_SOURCE = ROOT / "public/audio/overload.wav"
MASTER_MOVIE = OUT / "cage-of-seven-plus-two-xhs-v1-4k.mp4"
PUBLISH_MOVIE = OUT / "cage-of-seven-plus-two-xhs-v1-1080x1920.mp4"
COVER_3X4 = OUT / "cage-of-seven-plus-two-xhs-v1-cover-3x4.jpg"
COVER_4K = OUT / "xhs-v1-cover-4k.png"
CAPTIONS = OUT / "cage-of-seven-plus-two-xhs-v1-zh.srt"
REPORT = OUT / "xhs-v1-validation.json"

FPS = 60
DURATION_FRAMES = 3600
DURATION_SECONDS = 60.0
SAMPLE_RATE = 48000
CHANNELS = 2
SAMPLE_WIDTH = 2
SAMPLES_PER_FRAME = SAMPLE_RATE // FPS
PCM_SAMPLE_FRAMES = DURATION_FRAMES * SAMPLES_PER_FRAME
OVERLOAD_TONE_STOP_FRAME = 36
OVERLOAD_NOISE_END_FRAME = 48
HARMONIC_WINDOW_SAMPLES = 1309
ACTIVE_HARMONIC_MIN_AMPLITUDE = 0.003
INACTIVE_HARMONIC_MAX_AMPLITUDE = 0.001
EXPECTED_MASTER_DIMENSIONS = (2160, 3840)
EXPECTED_PUBLISH_DIMENSIONS = (1080, 1920)
MAX_ENCODED_PADDING_SECONDS = 0.05
AAC_COMPARISON_RATE = 8000
REPRESENTATIVE_FRAMES = [0, 35, 36, 60, 420, 900, 1500, 1800, 2130,
                         2400, 2850, 3200, 3500, 3599]
ALLOWED_BASELINE_CHANGES = {"src/Root.tsx", "package.json"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def resolve_project_path(value: str, *, label: str) -> Path:
    candidate = Path(value)
    require(not candidate.is_absolute(), f"{label} must be a project-relative path: {value}")
    resolved = (ROOT / candidate).resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError as exc:
        raise RuntimeError(f"{label} escapes the project root: {value}") from exc
    return resolved


def read_json(path: Path) -> dict:
    require(path.is_file(), f"Required QA input is missing: {relative(path)}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"Expected a JSON object in {relative(path)}")
    return value


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(args: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        detail = result.stderr.decode(errors="replace")[-6000:]
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(args)}\n{detail}")
    return result


def load_probe(path: Path) -> dict:
    require(path.is_file(), f"Rendered media is missing: {relative(path)}")
    result = run([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)
    ])
    return json.loads(result.stdout)


def one_stream(probe: dict, stream_type: str, name: str) -> dict:
    streams = [stream for stream in probe.get("streams", [])
               if stream.get("codec_type") == stream_type]
    require(len(streams) == 1,
            f"{name}: expected exactly one {stream_type} stream, got {len(streams)}")
    return streams[0]


def inspect_movie(path: Path, *, dimensions: tuple[int, int], name: str) -> dict:
    probe = load_probe(path)
    video = one_stream(probe, "video", name)
    audio = one_stream(probe, "audio", name)
    width, height = int(video["width"]), int(video["height"])
    fps = video.get("r_frame_rate")
    avg_fps = video.get("avg_frame_rate")
    frame_count_text = video.get("nb_frames")
    require(frame_count_text is not None,
            f"{name}: ffprobe did not report the encoded video frame count")
    frame_count = int(frame_count_text)
    video_duration = float(video["duration"])
    audio_duration = float(audio["duration"])
    container_duration = float(probe["format"]["duration"])
    audio_signature = (
        audio.get("codec_name"), int(audio.get("sample_rate", "0")), int(audio.get("channels", 0))
    )

    require((width, height) == dimensions,
            f"{name}: expected {dimensions[0]}x{dimensions[1]}, got {width}x{height}")
    require(fps == "60/1" and avg_fps == "60/1",
            f"{name}: expected constant 60 fps, got r={fps}, avg={avg_fps}")
    require(frame_count == DURATION_FRAMES,
            f"{name}: expected {DURATION_FRAMES} frames, got {frame_count}")
    require(abs(video_duration - DURATION_SECONDS) <= 1e-6,
            f"{name}: expected exactly 60 s video, got {video_duration:.6f} s")
    require(audio_signature == ("aac", SAMPLE_RATE, CHANNELS),
            f"{name}: expected AAC 48 kHz stereo, got {audio_signature}")
    require(abs(audio_duration - DURATION_SECONDS) <= MAX_ENCODED_PADDING_SECONDS,
            f"{name}: presented audio differs from 60 s by more than 50 ms ({audio_duration:.6f} s)")
    require(abs(container_duration - DURATION_SECONDS) <= MAX_ENCODED_PADDING_SECONDS,
            f"{name}: container duration differs from 60 s by more than 50 ms ({container_duration:.6f} s)")
    padding = container_duration - video_duration
    require(abs(padding) <= MAX_ENCODED_PADDING_SECONDS,
            f"{name}: container padding exceeds 50 ms ({padding:.6f} s)")

    return {
        "path": relative(path),
        "width": width,
        "height": height,
        "rFrameRate": fps,
        "avgFrameRate": avg_fps,
        "videoFrames": frame_count,
        "videoDurationSeconds": video_duration,
        "audioCodec": audio_signature[0],
        "audioSampleRate": audio_signature[1],
        "audioChannels": audio_signature[2],
        "audioPresentedDurationSeconds": audio_duration,
        "containerDurationSeconds": container_duration,
        "containerMinusVideoSeconds": padding,
        "sha256": sha256_file(path),
    }


def inspect_cover(path: Path, *, dimensions: tuple[int, int], codec: str) -> dict:
    probe = load_probe(path)
    videos = [stream for stream in probe.get("streams", [])
              if stream.get("codec_type") == "video"]
    require(len(videos) == 1, f"{relative(path)}: expected one still-image stream")
    image = videos[0]
    actual = (int(image["width"]), int(image["height"]))
    require(actual == dimensions,
            f"{relative(path)}: expected {dimensions[0]}x{dimensions[1]}, got {actual[0]}x{actual[1]}")
    require(image.get("codec_name") == codec,
            f"{relative(path)}: expected {codec} image, got {image.get('codec_name')}")
    return {"path": relative(path), "width": actual[0], "height": actual[1],
            "codec": image.get("codec_name"), "sha256": sha256_file(path)}


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(24)
    require(len(header) == 24 and header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR",
            f"Not a valid PNG with an IHDR chunk: {relative(path)}")
    return struct.unpack(">II", header[16:24])


def validate_preexisting_files(before: dict) -> dict:
    changed = []
    verified = []
    for project_path, expected in before.items():
        path = resolve_project_path(project_path, label="baseline path")
        require(path.is_file(), f"Pre-existing file was removed: {project_path}")
        actual = sha256_file(path)
        if project_path in ALLOWED_BASELINE_CHANGES:
            changed.append({"path": project_path, "baselineSha256": expected,
                            "currentSha256": actual, "allowed": True})
            continue
        require(actual == expected,
                f"Pre-existing file changed outside the two allowed paths: {project_path}")
        verified.append({"path": project_path, "sha256": actual})

    require(all(path in before for path in ALLOWED_BASELINE_CHANGES),
            "Baseline receipt must include both intentionally editable paths")
    return {"unchangedFilesVerified": len(verified), "unchangedFiles": verified,
            "allowedChanges": changed,
            "onlyAllowedPreexistingChanges": True}


def validate_audio_manifest(manifest: dict, timeline: dict, before: dict) -> dict:
    require(manifest.get("planSha256") == sha256_file(TIMELINE),
            "XHS audio manifest planSha256 does not match xhs-timeline.json")
    audio_format = manifest.get("format", {})
    expected_format = {
        "fps": FPS,
        "sampleRate": SAMPLE_RATE,
        "channels": CHANNELS,
        "bitsPerSample": SAMPLE_WIDTH * 8,
        "durationFrames": DURATION_FRAMES,
        "sampleFrames": PCM_SAMPLE_FRAMES,
        "durationSeconds": DURATION_SECONDS,
    }
    for key, value in expected_format.items():
        require(audio_format.get(key) == value,
                f"Audio manifest format.{key} must be {value}, got {audio_format.get(key)}")

    stems = manifest.get("inputs", {}).get("sourceStems", {})
    require(set(stems) == {"overload", "order", "atmosphere"},
            f"Audio manifest must describe overload, order, and atmosphere stems, got {sorted(stems)}")
    verified_stems = []
    for name, item in stems.items():
        path = resolve_project_path(item["path"], label=f"{name} stem path")
        require(path.is_file(), f"Audio source stem is missing: {item['path']}")
        actual = sha256_file(path)
        require(actual == item.get("sha256"), f"Audio source stem hash mismatch: {item['path']}")
        require(before.get(item["path"]) == actual,
                f"Pre-existing source stem hash changed: {item['path']}")
        verified_stems.append({"name": name, "path": item["path"], "sha256": actual})

    timeline_cues = timeline.get("cues", [])
    manifest_cues = manifest.get("cues", [])
    require(len(timeline_cues) == len(manifest_cues) == 11,
            f"Expected the 11 timeline voice cues, got {len(timeline_cues)}/{len(manifest_cues)}")
    timeline_by_id = {cue["id"]: cue for cue in timeline_cues}
    require(len(timeline_by_id) == len(timeline_cues), "Duplicate cue ids in xhs-timeline.json")
    manifest_ids = [cue.get("id") for cue in manifest_cues]
    require(set(manifest_ids) == set(timeline_by_id) and len(set(manifest_ids)) == 11,
            "Audio manifest cue ids do not match the 11 xhs-timeline.json cues")

    prior_end_sample = 0
    prior_end_frame = 0
    source_hashes = {}
    aligned = []
    for cue in sorted(manifest_cues, key=lambda item: (item["startFrame"], item["id"])):
        planned = timeline_by_id[cue["id"]]
        for key in ("file", "sourceFile", "sourceSha256", "startFrame", "endFrame", "sampleFrames"):
            planned_value = planned.get("sha256") if key == "alignedSha256" else planned.get(key)
            manifest_value = cue.get(key)
            if key == "alignedSha256":
                manifest_value = cue.get("alignedSha256")
            elif key == "file":
                manifest_value = cue.get("file")
            require(planned_value == manifest_value,
                    f"Cue {cue['id']} differs from the timeline plan in {key}")

        start_frame = int(cue["startFrame"])
        end_frame = int(cue["endFrame"])
        start_sample = int(cue["startSample"])
        end_sample = int(cue["endSample"])
        sample_frames = int(cue["sampleFrames"])
        require(start_frame >= 0 and end_frame > start_frame and end_frame <= DURATION_FRAMES,
                f"Cue {cue['id']} is outside the 60 s frame range")
        require(start_sample == start_frame * SAMPLES_PER_FRAME,
                f"Cue {cue['id']} does not start on its planned video frame")
        require(sample_frames > 0 and end_sample - start_sample == sample_frames,
                f"Cue {cue['id']} sampleFrames does not equal endSample-startSample")
        require(end_sample <= PCM_SAMPLE_FRAMES and end_frame == math.ceil(end_sample / SAMPLES_PER_FRAME),
                f"Cue {cue['id']} sample range does not fit its frame bounds")
        require(start_sample >= prior_end_sample and start_frame >= prior_end_frame,
                f"Cue {cue['id']} overlaps a previous voice cue")
        require(float(cue.get("atempo", 0)) == 1.0,
                f"Cue {cue['id']} was time-stretched (atempo={cue.get('atempo')})")

        source_path = resolve_project_path(cue["sourceFile"], label=f"{cue['id']} source path")
        aligned_path = resolve_project_path(cue["file"], label=f"{cue['id']} aligned path")
        require(source_path.is_file(), f"Source voice clip is missing: {cue['sourceFile']}")
        require(aligned_path.is_file(), f"Aligned voice clip is missing: {cue['file']}")
        source_sha = sha256_file(source_path)
        aligned_sha = sha256_file(aligned_path)
        require(source_sha == cue.get("sourceSha256"),
                f"Source voice hash mismatch for {cue['id']}")
        require(before.get(cue["sourceFile"]) == source_sha,
                f"Original source voice clip changed for {cue['id']}")
        require(aligned_sha == cue.get("alignedSha256"),
                f"Aligned voice hash mismatch for {cue['id']}")
        require(planned.get("sha256") == aligned_sha,
                f"Aligned voice hash differs from the XHS plan for {cue['id']}")
        source_hashes[cue["sourceFile"]] = source_sha
        aligned.append({"id": cue["id"], "sourceFile": cue["sourceFile"],
                        "sourceSha256": source_sha, "file": cue["file"],
                        "alignedSha256": aligned_sha, "startFrame": start_frame,
                        "endFrame": end_frame, "startSample": start_sample,
                        "endSample": end_sample, "sampleFrames": sample_frames,
                        "atempo": float(cue["atempo"])})
        prior_end_sample = end_sample
        prior_end_frame = end_frame

    require(len(source_hashes) == 11,
            f"Expected 11 distinct original source voice clips, got {len(source_hashes)}")

    output_audio = manifest.get("outputs", {})
    require(set(output_audio) == {"overload", "narration", "score", "soundtrack"},
            f"Audio manifest output set is incomplete: {sorted(output_audio)}")
    verified_outputs = []
    for name, item in output_audio.items():
        path = resolve_project_path(item["path"], label=f"{name} audio output path")
        require(path.is_file(), f"Audio output is missing: {item['path']}")
        actual = sha256_file(path)
        require(actual == item.get("sha256"), f"Audio output hash mismatch: {item['path']}")
        verified_outputs.append({"name": name, "path": item["path"], "sha256": actual})

    cloud = manifest.get("cloud", {})
    require(cloud.get("providerCalls") == 0 and cloud.get("asrUploads") == 0,
            "Audio manifest must attest zero provider calls and zero ASR uploads")
    validation = manifest.get("validation", {})
    require(validation.get("noiseSampleCopy") is True,
            "Audio manifest does not attest the exact opening noise sample copy")
    require(validation.get("quietFrameRange") == [48, 66],
            "Audio manifest does not attest the required digital-silence frame range")

    return {
        "planSha256": manifest["planSha256"],
        "format": audio_format,
        "sourceStemsVerified": verified_stems,
        "voiceCueCount": len(aligned),
        "sourceClipCount": len(source_hashes),
        "sourceVoiceHashes": source_hashes,
        "alignedVoiceCues": aligned,
        "outputsVerified": verified_outputs,
        "noAtTempo": True,
        "voiceCuesFitWithoutOverlap": True,
        "cloud": {"providerCalls": 0, "asrUploads": 0},
    }


def wav_metadata(path: Path, *, expected_frames: int | None = None,
                 expected_channels: int = CHANNELS) -> dict:
    require(path.is_file(), f"Required WAV is missing: {relative(path)}")
    with wave.open(str(path), "rb") as source:
        metadata = {
            "channels": source.getnchannels(),
            "sampleRate": source.getframerate(),
            "sampleWidthBytes": source.getsampwidth(),
            "sampleFrames": source.getnframes(),
            "compression": source.getcomptype(),
        }
    require((metadata["channels"], metadata["sampleRate"], metadata["sampleWidthBytes"],
             metadata["compression"]) == (expected_channels, SAMPLE_RATE, SAMPLE_WIDTH, "NONE"),
            f"{relative(path)} must be uncompressed 16-bit {expected_channels}-channel 48 kHz PCM")
    if expected_frames is not None:
        require(metadata["sampleFrames"] == expected_frames,
                f"{relative(path)} must contain {expected_frames} samples per channel, got {metadata['sampleFrames']}")
    return metadata


def verify_narration_upmix(manifest: dict) -> dict:
    narration_item = manifest["outputs"]["narration"]
    narration_path = resolve_project_path(narration_item["path"], label="narration output path")
    narration_metadata = wav_metadata(narration_path, expected_frames=PCM_SAMPLE_FRAMES,
                                      expected_channels=CHANNELS)
    cue_checks = []
    with wave.open(str(narration_path), "rb") as narration:
        for cue in manifest["cues"]:
            aligned_path = resolve_project_path(cue["file"], label=f"{cue['id']} aligned path")
            cue_frames = int(cue["sampleFrames"])
            aligned_metadata = wav_metadata(aligned_path, expected_frames=cue_frames,
                                            expected_channels=1)
            with wave.open(str(aligned_path), "rb") as aligned:
                mono_bytes = aligned.readframes(cue_frames)
            narration.setpos(int(cue["startSample"]))
            stereo_bytes = narration.readframes(cue_frames)
            require(len(mono_bytes) == cue_frames * SAMPLE_WIDTH,
                    f"Aligned cue {cue['id']} has an incomplete mono payload")
            require(len(stereo_bytes) == cue_frames * CHANNELS * SAMPLE_WIDTH,
                    f"Narration upmix has an incomplete stereo payload for {cue['id']}")

            mono = array.array("h", mono_bytes)
            stereo = array.array("h", stereo_bytes)
            if sys.byteorder != "little":
                mono.byteswap()
                stereo.byteswap()
            require(len(mono) == cue_frames and len(stereo) == cue_frames * CHANNELS,
                    f"Cue {cue['id']} sample counts do not match the manifest")
            for index, sample in enumerate(mono):
                require(stereo[index * CHANNELS] == sample
                        and stereo[index * CHANNELS + 1] == sample,
                        f"Narration is not a unity-gain dual-mono copy for {cue['id']} "
                        f"at cue sample {index}")
            cue_checks.append({
                "id": cue["id"],
                "alignedPath": cue["file"],
                "alignedChannels": aligned_metadata["channels"],
                "sampleFramesPerChannel": cue_frames,
                "narrationStartSample": int(cue["startSample"]),
                "leftAndRightEqualAlignedMono": True,
                "unityGainByteExact": True,
            })

    return {
        "path": relative(narration_path),
        "sha256": sha256_file(narration_path),
        "format": narration_metadata,
        "alignedMonoCuesVerified": cue_checks,
        "allCueSamplesCopiedToBothChannelsAtUnity": True,
        "cachedSourceClipsUnchanged": True,
    }


def verify_master_pcm_audio(manifest: dict) -> dict:
    metadata = wav_metadata(PCM_MASTER, expected_frames=PCM_SAMPLE_FRAMES)
    manifest_format = manifest["format"]
    require(metadata["sampleFrames"] == manifest_format["sampleFrames"],
            "PCM master sample count does not match the XHS audio manifest")

    with wave.open(str(PCM_MASTER), "rb") as master:
        master_intro = master.readframes(OVERLOAD_NOISE_END_FRAME * SAMPLES_PER_FRAME)
        master.setpos(36 * SAMPLES_PER_FRAME)
        copied_noise = master.readframes(12 * SAMPLES_PER_FRAME)
        master.setpos(48 * SAMPLES_PER_FRAME)
        quiet_pcm = master.readframes((66 - 48) * SAMPLES_PER_FRAME)
    with wave.open(str(NOISE_SOURCE), "rb") as original:
        wav_metadata(NOISE_SOURCE)
        original.setpos(1200 * SAMPLES_PER_FRAME)
        original_noise = original.readframes(12 * SAMPLES_PER_FRAME)
    overload_path = resolve_project_path(manifest["outputs"]["overload"]["path"],
                                         label="overload output path")
    with wave.open(str(overload_path), "rb") as overload:
        overload.setpos(0)
        overload_intro = overload.readframes(OVERLOAD_NOISE_END_FRAME * SAMPLES_PER_FRAME)
    require(master_intro == overload_intro,
            "PCM master frames 0..48 do not exactly match the overload stem while score/voice are absent")
    require(len(copied_noise) == len(original_noise) and copied_noise == original_noise,
            "PCM master frames 36..48 do not exactly copy overload source frames 1200..1212")
    require(len(quiet_pcm) == (66 - 48) * SAMPLES_PER_FRAME * CHANNELS * SAMPLE_WIDTH,
            "PCM master quiet-range sample count is incomplete")
    require(not any(quiet_pcm), "PCM master frames 48..66 are not digital zero")

    return {
        "path": relative(PCM_MASTER),
        "sha256": sha256_file(PCM_MASTER),
        "format": metadata,
        "sampleFrames": metadata["sampleFrames"],
        "exactNoiseCopy": {
            "masterFrames": [36, 48],
            "overloadStemFrames": [36, 48],
            "sourcePath": relative(NOISE_SOURCE),
            "sourceFrames": [1200, 1212],
            "sampleFramesPerChannel": 12 * SAMPLES_PER_FRAME,
            "byteExact": True,
        },
        "masterMatchesOverloadStemFrames0To48": True,
        "digitalZero": {"frames": [48, 66],
                        "sampleFramesPerChannel": 18 * SAMPLES_PER_FRAME,
                        "verified": True},
    }


def verify_overload_harmonics(manifest: dict) -> dict:
    overload_item = manifest["outputs"]["overload"]
    overload_path = resolve_project_path(overload_item["path"], label="overload output path")
    metadata = wav_metadata(overload_path, expected_frames=PCM_SAMPLE_FRAMES,
                            expected_channels=CHANNELS)
    tone_stop = OVERLOAD_TONE_STOP_FRAME * SAMPLES_PER_FRAME
    noise_end = OVERLOAD_NOISE_END_FRAME * SAMPLES_PER_FRAME
    with wave.open(str(overload_path), "rb") as overload:
        overload.setpos(noise_end)
        zero_tail = overload.readframes(PCM_SAMPLE_FRAMES - noise_end)
        overload.setpos(0)
        intro_samples = array.array("h", overload.readframes(tone_stop))
    if sys.byteorder != "little":
        intro_samples.byteswap()
    require(not any(zero_tail),
            "XHS overload stem must be digital zero after the frame-36..48 noise transient")
    require(len(intro_samples) == tone_stop * CHANNELS,
            "XHS overload stem harmonic intro has an incomplete sample range")

    mono = [(intro_samples[index * CHANNELS] + intro_samples[index * CHANNELS + 1]) / 65536.0
            for index in range(tone_stop)]
    stages = []
    for stage in range(9):
        boundary_frame = (stage + 1) * 4
        window_end = boundary_frame * SAMPLES_PER_FRAME
        window_start = window_end - HARMONIC_WINDOW_SAMPLES
        require(window_start >= 0, f"Harmonic stage {stage + 1} has no complete verification window")
        samples = mono[window_start:window_end]
        require(len(samples) == HARMONIC_WINDOW_SAMPLES,
                f"Harmonic stage {stage + 1} verification window is incomplete")
        measured = []
        for harmonic in range(1, 10):
            frequency = 220 * harmonic
            phase_step = 2.0 * math.pi * frequency / SAMPLE_RATE
            real = 0.0
            imaginary = 0.0
            for index, sample in enumerate(samples):
                phase = phase_step * index
                real += sample * math.cos(phase)
                imaginary += sample * math.sin(phase)
            amplitude = 2.0 * math.hypot(real, imaginary) / HARMONIC_WINDOW_SAMPLES
            if harmonic <= stage + 1:
                require(amplitude > ACTIVE_HARMONIC_MIN_AMPLITUDE,
                        f"Harmonic stage {stage + 1}: {frequency} Hz amplitude "
                        f"{amplitude:.6f} is below the {ACTIVE_HARMONIC_MIN_AMPLITUDE:.3f} active threshold")
            else:
                require(amplitude < INACTIVE_HARMONIC_MAX_AMPLITUDE,
                        f"Harmonic stage {stage + 1}: inactive {frequency} Hz amplitude "
                        f"{amplitude:.6f} exceeds the {INACTIVE_HARMONIC_MAX_AMPLITUDE:.3f} threshold")
            measured.append({"frequencyHz": frequency, "amplitude": amplitude,
                             "expectedActive": harmonic <= stage + 1})
        stages.append({"activeLayers": stage + 1,
                       "boundaryFrame": boundary_frame,
                       "windowStartSample": window_start,
                       "windowEndSampleExclusive": window_end,
                       "harmonics": measured})

    return {
        "path": relative(overload_path),
        "sha256": sha256_file(overload_path),
        "format": metadata,
        "toneStopFrame": OVERLOAD_TONE_STOP_FRAME,
        "allNineHarmonicsPresentByFinalStage": True,
        "inactiveHarmonicsBelowThresholdAtEveryStage": True,
        "harmonicAmplitudeThresholds": {
            "activeAbove": ACTIVE_HARMONIC_MIN_AMPLITUDE,
            "inactiveBelow": INACTIVE_HARMONIC_MAX_AMPLITUDE,
        },
        "measuredStages": stages,
        "digitalZeroFramesAfterNoise": [OVERLOAD_NOISE_END_FRAME, DURATION_FRAMES],
        "verified": True,
    }


def png_frame_selector() -> str:
    return "+".join(f"eq(n\\,{number})" for number in REPRESENTATIVE_FRAMES)


def decode_once_extract_and_copy_aac(path: Path, *, extract_frames: bool) -> tuple[array.array, dict, list[dict]]:
    """Strictly decode one movie in one ffmpeg invocation; collect its AAC packets too."""
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="xhs-v1-decode-") as temp_name:
        temp = Path(temp_name)
        aac_path = temp / "audio-packets.aac"
        pcm_path = temp / "decoded-audio-8khz-mono.s16le"
        args = ["ffmpeg", "-hide_banner", "-v", "error", "-xerror", "-y", "-i", str(path)]
        if extract_frames:
            pattern = OUT / "xhs-v1-final-frame-%02d.png"
            args += ["-map", "0:v:0", "-vf", f"select={png_frame_selector()}",
                     "-fps_mode", "vfr", "-start_number", "1", "-f", "image2", str(pattern)]
        else:
            args += ["-map", "0:v:0", "-f", "null", "-"]
        args += ["-map", "0:a:0", "-c:a", "copy", "-f", "adts", str(aac_path),
                 "-map", "0:a:0", "-ac", "1", "-ar", str(AAC_COMPARISON_RATE),
                 "-c:a", "pcm_s16le", "-f", "s16le", str(pcm_path)]
        run(args)

        pcm_bytes = pcm_path.read_bytes()
        require(len(pcm_bytes) % 2 == 0, f"Decoded audio is not aligned to 16-bit samples: {relative(path)}")
        samples = array.array("h", pcm_bytes)
        if sys.byteorder != "little":
            samples.byteswap()
        packet_hash = sha256_file(aac_path)
        packet_receipt = {"sha256": packet_hash, "bytes": aac_path.stat().st_size}

    extracted = []
    if extract_frames:
        for index, source_frame in enumerate(REPRESENTATIVE_FRAMES, start=1):
            image_path = OUT / f"xhs-v1-final-frame-{index:02d}.png"
            require(image_path.is_file(),
                    f"ffmpeg did not extract representative master frame {source_frame}")
            dimensions = png_dimensions(image_path)
            require(dimensions == EXPECTED_MASTER_DIMENSIONS,
                    f"Extracted frame {source_frame} is {dimensions[0]}x{dimensions[1]}, "
                    f"expected {EXPECTED_MASTER_DIMENSIONS[0]}x{EXPECTED_MASTER_DIMENSIONS[1]}")
            extracted.append({"sourceFrame": source_frame, "path": relative(image_path),
                              "width": dimensions[0], "height": dimensions[1],
                              "sha256": sha256_file(image_path)})
    return samples, packet_receipt, extracted


def decode_reference_audio() -> array.array:
    raw = run([
        "ffmpeg", "-hide_banner", "-v", "error", "-xerror", "-i", str(PCM_MASTER),
        "-map", "0:a:0", "-ac", "1", "-ar", str(AAC_COMPARISON_RATE),
        "-c:a", "pcm_s16le", "-f", "s16le", "-",
    ]).stdout
    reference = array.array("h", raw)
    if sys.byteorder != "little":
        reference.byteswap()
    require(len(reference) == DURATION_SECONDS * AAC_COMPARISON_RATE,
            f"Decoded PCM reference must have {int(DURATION_SECONDS * AAC_COMPARISON_RATE)} mono samples")
    return reference


def compare_encoded_audio_to_pcm(actual: array.array, reference: array.array, name: str) -> dict:
    expected_samples = len(reference)
    max_extra_samples = int(MAX_ENCODED_PADDING_SECONDS * AAC_COMPARISON_RATE)
    require(expected_samples <= len(actual) <= expected_samples + max_extra_samples,
            f"{name}: decoded AAC sample count {len(actual)} is outside the 60 s + 50 ms limit")
    actual = actual[:expected_samples]
    windows = [("whole-film", 0, 60), ("overload", 0, 10), ("linear", 10, 22),
               ("matrix", 22, 28), ("manifold", 28, 37), ("oracle", 37, 48), ("ending", 48, 60)]
    measurements = []
    for label, start_second, end_second in windows:
        start = start_second * AAC_COMPARISON_RATE
        end = end_second * AAC_COMPARISON_RATE
        dot = ref_energy = actual_energy = error_energy = 0.0
        for index in range(start, end):
            a, b = actual[index], reference[index]
            dot += a * b
            ref_energy += b * b
            actual_energy += a * a
            error_energy += (a - b) ** 2
        require(ref_energy > 0 and actual_energy > 0,
                f"{name}: audio comparison window {label} contains no signal")
        correlation = dot / math.sqrt(ref_energy * actual_energy)
        normalized_error = math.sqrt(error_energy / ref_energy)
        require(correlation > 0.98 and normalized_error < 0.2,
                f"{name}: decoded AAC differs from PCM in {label}: "
                f"correlation={correlation:.6f}, normalizedRmsError={normalized_error:.6f}")
        measurements.append({"window": label, "fromSeconds": start_second,
                             "toSeconds": end_second, "cosineCorrelation": correlation,
                             "normalizedRmsError": normalized_error})
    return {"status": "PASS", "comparisonSampleRate": AAC_COMPARISON_RATE,
            "measurements": measurements,
            "note": "Decoded mono AAC compared at matching times with the 8 kHz mono PCM source; "
                    "lossy AAC error is allowed. This does not assess voice intelligibility."}


def validate_timeline(timeline: dict) -> dict:
    expected = {
        "fps": FPS,
        "durationInFrames": DURATION_FRAMES,
        "width": EXPECTED_MASTER_DIMENSIONS[0],
        "height": EXPECTED_MASTER_DIMENSIONS[1],
        "publishWidth": EXPECTED_PUBLISH_DIMENSIONS[0],
        "publishHeight": EXPECTED_PUBLISH_DIMENSIONS[1],
        "sampleRate": SAMPLE_RATE,
    }
    for key, value in expected.items():
        require(timeline.get(key) == value,
                f"xhs-timeline.json {key} must be {value}, got {timeline.get(key)}")
    require(timeline.get("renderScale") == 2,
            "XHS timeline must use the decided 2x portrait master render scale")
    require(timeline.get("overloadFrame") == 36 and timeline.get("noiseDurationFrames") == 12,
            "XHS timeline opening-noise boundary changed")
    return {"path": relative(TIMELINE), "sha256": sha256_file(TIMELINE),
            "fps": FPS, "durationFrames": DURATION_FRAMES,
            "masterDimensions": {"width": EXPECTED_MASTER_DIMENSIONS[0],
                                 "height": EXPECTED_MASTER_DIMENSIONS[1]},
            "publishDimensions": {"width": EXPECTED_PUBLISH_DIMENSIONS[0],
                                  "height": EXPECTED_PUBLISH_DIMENSIONS[1]},
            "voiceCues": len(timeline.get("cues", []))}


def main() -> int:
    before = read_json(BEFORE)
    timeline = read_json(TIMELINE)
    manifest = read_json(AUDIO_MANIFEST)
    timeline_receipt = validate_timeline(timeline)
    baseline_receipt = validate_preexisting_files(before)
    audio_receipt = validate_audio_manifest(manifest, timeline, before)
    narration_receipt = verify_narration_upmix(manifest)
    overload_receipt = verify_overload_harmonics(manifest)
    pcm_receipt = verify_master_pcm_audio(manifest)
    require(pcm_receipt["sha256"] == manifest["outputs"]["soundtrack"]["sha256"],
            "PCM master hash does not match manifest soundtrack output")

    master_probe = inspect_movie(MASTER_MOVIE, dimensions=EXPECTED_MASTER_DIMENSIONS,
                                 name="native 4K portrait master")
    publish_probe = inspect_movie(PUBLISH_MOVIE, dimensions=EXPECTED_PUBLISH_DIMENSIONS,
                                  name="1080x1920 publish derivative")
    master_audio, master_packets, representative_frames = decode_once_extract_and_copy_aac(
        MASTER_MOVIE, extract_frames=True)
    publish_audio, publish_packets, _ = decode_once_extract_and_copy_aac(
        PUBLISH_MOVIE, extract_frames=False)
    require(master_packets["sha256"] == publish_packets["sha256"],
            "Master and publish derivative AAC packet streams are not byte-identical")
    reference_audio = decode_reference_audio()
    master_audio_comparison = compare_encoded_audio_to_pcm(master_audio, reference_audio,
                                                           "native 4K portrait master")
    publish_audio_comparison = compare_encoded_audio_to_pcm(publish_audio, reference_audio,
                                                             "1080x1920 publish derivative")

    cover_3x4 = inspect_cover(COVER_3X4, dimensions=(1080, 1440), codec="mjpeg")
    cover_4k = inspect_cover(COVER_4K, dimensions=(2160, 2880), codec="png")
    require(CAPTIONS.is_file() and CAPTIONS.stat().st_size > 0,
            f"Chinese SRT captions are missing or empty: {relative(CAPTIONS)}")
    captions = {"path": relative(CAPTIONS), "bytes": CAPTIONS.stat().st_size,
                "sha256": sha256_file(CAPTIONS)}

    report = {
        "status": "PASS",
        "edition": "EP02 Xiaohongshu portrait short v1",
        "results": {
            "sourceBaseline": "PASS",
            "audioManifestAndClipTiming": "PASS",
            "narrationUnityGainDualMono": "PASS",
            "nineStageHarmonicStackAndHardGate": "PASS",
            "overloadStemDigitalZeroAfterNoise": "PASS",
            "pcmMasterLengthAndOpeningNoise": "PASS",
            "digitalZeroFrames48To66": "PASS",
            "masterProbe": "PASS",
            "publishProbe": "PASS",
            "strictFullDecodeBothMovies": "PASS",
            "masterRepresentativeFramesInSameDecodePass": "PASS",
            "masterEncodedAudioMatchesPcm": "PASS",
            "publishEncodedAudioMatchesPcm": "PASS",
            "aacPacketsIdenticalAcrossMovies": "PASS",
            "coverDimensions": "PASS",
            "captionsPresent": "PASS",
            "humanListening": "PENDING",
            "continuousVisualReview": "PENDING",
            "actualPlatformUpload": "PENDING",
            "asr": "NOT_PERFORMED",
            "cloudServices": "NOT_USED",
        },
        "timeline": timeline_receipt,
        "sourceBaseline": baseline_receipt,
        "audio": audio_receipt,
        "narrationUpmix": narration_receipt,
        "overloadStem": overload_receipt,
        "pcmMaster": pcm_receipt,
        "movies": {"master": master_probe, "publish": publish_probe},
        "strictDecode": {
            "master": "PASS",
            "publish": "PASS",
            "atMostOneStrictDecodePassPerMovie": True,
            "aacPackets": {"master": master_packets, "publish": publish_packets,
                           "byteIdentical": True},
            "representativeFrames": {"sourceFrames": REPRESENTATIVE_FRAMES,
                                      "extracted": representative_frames},
        },
        "encodedAudioComparison": {"master": master_audio_comparison,
                                   "publish": publish_audio_comparison},
        "covers": {"3x4": cover_3x4, "4k": cover_4k},
        "captions": captions,
        "humanReview": {"listening": "pending", "continuousViewing": "pending",
                        "platformUpload": "pending"},
        "privacy": {"asrPerformed": False, "cloudServicesUsed": False,
                    "audioUploads": 0},
        "note": "Automated local media and provenance checks only. Human listening, continuous "
                "visual review, and Xiaohongshu upload acceptance remain pending.",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, KeyError, TypeError, ValueError, OSError) as error:
        print(f"XHS v1 validation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
