#!/usr/bin/env python3
"""Validate the native 4K UHD EP02 export and local audio reuse receipts.

This is a local-only validator. It does not contact Bailian or any other service,
and it never uploads audio. It verifies the final encoded movie, decodes the full
video/audio stream while extracting representative frames in one ffmpeg pass,
and records PCM source identity separately from lossy AAC/container timing.
"""

from __future__ import annotations

import hashlib
import json
import array
import math
from pathlib import Path
import struct
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
MOVIE = OUT / "cage-of-seven-plus-two-uhd-v3-4k.mp4"
PREVIEW = OUT / "uhd-v3-overload-preview.mp4"
BEFORE = OUT / "uhd-v3-before.json"
SOURCE_SNAPSHOT = OUT / "uhd-v3-source-before.zip"
MIX_MANIFEST = OUT / "voiced-v2-mix-manifest.json"
ASR_STATUS = ROOT / "audio-voiced-v2" / "asr-status.json"
REPORT = OUT / "uhd-v3-validation.json"

EXPECTED_MASTER_SHA256 = "f7df2b03a6f7767449dafdc8ba7ac405628fe4ea42bced50a00f597bcc7a4aef"
EXPECTED_PCM_SECONDS = 180.0
EXPECTED_VIDEO_FRAMES = 10800
EXPECTED_FPS = 60
EXPECTED_DIMENSIONS = (3840, 2160)
EXPECTED_AUDIO = ("aac", 48000, 2)
MAX_ENCODED_PADDING_SECONDS = 0.05
REPRESENTATIVE_FRAMES = [0, 1080, 1199, 1200, 1230, 2100, 3300, 4600, 6000, 7200, 9000, 10200, 10799]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def read_json(path: Path) -> dict:
    require(path.is_file(), f"Required QA input is missing: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


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


def get_media_streams(probe: dict, name: str) -> tuple[dict, dict]:
    videos = [stream for stream in probe["streams"] if stream.get("codec_type") == "video"]
    audios = [stream for stream in probe["streams"] if stream.get("codec_type") == "audio"]
    require(len(videos) == 1, f"{name}: expected exactly one video stream, got {len(videos)}")
    require(len(audios) == 1, f"{name}: expected exactly one audio stream, got {len(audios)}")
    return videos[0], audios[0]


def inspect_encoded_media(path: Path, *, frames: int, seconds: float, name: str) -> dict:
    probe = load_probe(path)
    video, audio = get_media_streams(probe, name)
    width, height = int(video["width"]), int(video["height"])
    fps = video.get("r_frame_rate")
    avg_fps = video.get("avg_frame_rate")
    frame_count = int(video.get("nb_frames", "0"))
    video_duration = float(video["duration"])
    audio_duration = float(audio["duration"])
    container_duration = float(probe["format"]["duration"])
    audio_codec = audio.get("codec_name")
    sample_rate = int(audio.get("sample_rate", "0"))
    channels = int(audio.get("channels", 0))

    require((width, height) == EXPECTED_DIMENSIONS,
            f"{name}: expected 3840x2160, got {width}x{height}")
    require(fps == "60/1" and avg_fps == "60/1",
            f"{name}: expected constant 60 fps, got r={fps}, avg={avg_fps}")
    require(frame_count == frames, f"{name}: expected {frames} frames, got {frame_count}")
    require(abs(video_duration - seconds) <= 1e-6,
            f"{name}: expected {seconds:.6f}s video, got {video_duration:.6f}s")
    require((audio_codec, sample_rate, channels) == EXPECTED_AUDIO,
            f"{name}: expected AAC 48 kHz stereo, got {audio_codec} {sample_rate} Hz/{channels} ch")
    require(abs(audio_duration - seconds) <= MAX_ENCODED_PADDING_SECONDS,
            f"{name}: audio duration differs from {seconds:.3f}s by more than 50 ms ({audio_duration:.6f}s)")
    require(abs(container_duration - seconds) <= MAX_ENCODED_PADDING_SECONDS,
            f"{name}: container duration differs from {seconds:.3f}s by more than 50 ms ({container_duration:.6f}s)")
    padding = max(0.0, container_duration - video_duration)
    require(padding <= MAX_ENCODED_PADDING_SECONDS,
            f"{name}: container padding exceeds 50 ms ({padding:.6f}s)")

    return {
        "path": relative(path),
        "width": width,
        "height": height,
        "rFrameRate": fps,
        "avgFrameRate": avg_fps,
        "videoFrames": frame_count,
        "videoDurationSeconds": video_duration,
        "audioCodec": audio_codec,
        "audioSampleRate": sample_rate,
        "audioChannels": channels,
        "audioPresentedDurationSeconds": audio_duration,
        "containerDurationSeconds": container_duration,
        "containerPaddingSeconds": padding,
        "sha256": sha256_file(path),
    }


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(24)
    require(len(header) == 24 and header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR",
            f"Not a valid PNG with an IHDR chunk: {relative(path)}")
    return struct.unpack(">II", header[16:24])


def validate_timeline(baseline_zip: Path, current_path: Path, expected_baseline_sha256: str | None) -> dict:
    require(baseline_zip.is_file(), f"Timeline baseline archive is missing: {relative(baseline_zip)}")
    with zipfile.ZipFile(baseline_zip) as archive:
        candidates = [name for name in archive.namelist() if name == "timeline.json" or name.endswith("/timeline.json")]
        require(len(candidates) == 1, f"Expected one timeline.json in baseline archive, found {len(candidates)}")
        baseline_bytes = archive.read(candidates[0])
        baseline = json.loads(baseline_bytes.decode("utf-8"))
    baseline_sha256 = sha256_bytes(baseline_bytes)
    require(expected_baseline_sha256 is None or baseline_sha256 == expected_baseline_sha256,
            "Timeline inside the safety snapshot does not match the pre-render baseline receipt")
    current = read_json(current_path)

    expected_added = {"logicalWidth", "logicalHeight", "renderScale"}
    baseline_keys, current_keys = set(baseline), set(current)
    require(current_keys - baseline_keys == expected_added,
            f"UHD timeline added unexpected fields: {sorted(current_keys - baseline_keys)}")
    require(baseline_keys - current_keys == set(),
            f"UHD timeline removed fields: {sorted(baseline_keys - current_keys)}")
    require((baseline.get("width"), baseline.get("height")) == (1920, 1080),
            f"Unexpected source timeline dimensions: {baseline.get('width')}x{baseline.get('height')}")
    require((current.get("width"), current.get("height")) == EXPECTED_DIMENSIONS,
            f"Unexpected UHD timeline dimensions: {current.get('width')}x{current.get('height')}")
    require((current.get("logicalWidth"), current.get("logicalHeight"), current.get("renderScale")) == (1920, 1080, 2),
            "UHD timeline must preserve the 1920x1080 logical canvas at a 2x render scale")

    for key, before_value in baseline.items():
        if key in {"width", "height"}:
            continue
        require(current[key] == before_value, f"Non-geometric timeline value changed: {key}")
    return {
        "status": "PASS",
        "baselineTimelineSha256": baseline_sha256,
        "currentTimelineSha256": sha256_file(current_path),
        "baselineDimensions": {"width": baseline["width"], "height": baseline["height"]},
        "currentDimensions": {"width": current["width"], "height": current["height"]},
        "logicalDimensions": {"width": current["logicalWidth"], "height": current["logicalHeight"]},
        "renderScale": current["renderScale"],
        "changedTimelineFields": ["width", "height", "logicalWidth", "logicalHeight", "renderScale"],
        "temporalAndAudioFieldsUnchanged": True,
    }


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_audio_assets(before: dict, mix: dict) -> tuple[dict, dict]:
    cached_manifest_path = ROOT / "audio-voiced-v2" / "voice-manifest.json"
    cached_plan_path = ROOT / "audio-voiced-v2" / "voice-plan.json"
    cached_manifest = read_json(cached_manifest_path)
    master_path = ROOT / "public" / "audio-voiced-v2" / "soundtrack.wav"

    before_master = before.get("public/audio-voiced-v2/soundtrack.wav")
    manifest_master = mix["outputs"]["soundtrack"]["sha256"]
    current_master = sha256_file(master_path)
    require(before_master == EXPECTED_MASTER_SHA256,
            f"The pre-UHD receipt does not match the expected PCM master hash: {before_master}")
    require(manifest_master == EXPECTED_MASTER_SHA256,
            f"The mix manifest does not match the expected PCM master hash: {manifest_master}")
    require(current_master == EXPECTED_MASTER_SHA256,
            f"The PCM soundtrack changed: {current_master}")

    checked_assets: list[dict] = []

    def verify_asset(rel: str, expected: str, category: str) -> None:
        path = ROOT / rel
        require(path.is_file(), f"Cached {category} asset is missing: {rel}")
        actual = sha256_file(path)
        require(actual == expected, f"Cached {category} hash mismatch for {rel}: {actual} != {expected}")
        checked_assets.append({"path": rel, "category": category, "sha256": actual})

    input_manifest = mix["inputs"]["voiceManifest"]
    input_plan = mix["inputs"]["voicePlan"]
    verify_asset(input_manifest["path"], input_manifest["sha256"], "voice-manifest")
    verify_asset(input_plan["path"], input_plan["sha256"], "voice-plan")

    for name, stem in mix["inputs"]["sourceStems"].items():
        verify_asset(stem["path"], stem["sha256"], f"source-stem:{name}")

    voice_by_id = {cue["id"]: cue for cue in cached_manifest["cues"]}
    require(len(mix["cues"]) == 17 and len(voice_by_id) == 17,
            f"Expected the existing 17 cached narration clips, found {len(mix['cues'])}/{len(voice_by_id)}")
    for cue in mix["cues"]:
        voice = voice_by_id.get(cue["id"])
        require(voice is not None, f"Cached voice manifest is missing cue {cue['id']}")
        require(voice.get("sha256") == cue["sourceSha256"],
                f"Source clip receipt differs for {cue['id']}")
        verify_asset(cue["file"], cue["sourceSha256"], f"voice-source:{cue['id']}")
        verify_asset(cue["alignedFile"], cue["alignedSha256"], f"voice-aligned:{cue['id']}")
        raw_sha = voice.get("rawSha256")
        if raw_sha:
            verify_asset(f"public/audio-voiced-v2/raw/{cue['id']}.wav", raw_sha, f"voice-raw:{cue['id']}")

    narration = mix["outputs"]["narration"]
    verify_asset(narration["path"], narration["sha256"], "narration-mix")
    verify_asset("public/audio-voiced-v2/soundtrack.wav", EXPECTED_MASTER_SHA256, "pcm-master")

    return (
        {
            "status": "PASS",
            "pcmMaster": {
                "path": "public/audio-voiced-v2/soundtrack.wav",
                "sha256": current_master,
                "expectedSha256": EXPECTED_MASTER_SHA256,
                "matchesPreUhdReceipt": current_master == before_master,
                "matchesMixManifest": current_master == manifest_master,
            },
            "sourceStemsVerified": len(mix["inputs"]["sourceStems"]),
            "cachedVoiceSourceClipsVerified": len(mix["cues"]),
            "alignedVoiceClipsVerified": len(mix["cues"]),
            "rawVoiceCacheFilesVerified": sum(1 for cue in cached_manifest["cues"] if cue.get("rawSha256")),
            "audioAssetsVerified": len(checked_assets),
            "assets": checked_assets,
            "note": "Exact PCM and cached-source identity checked by streamed SHA-256; loudness was not recomputed.",
        },
        {
            "baselinePcmMasterSha256": before_master,
            "mixManifestPcmMasterSha256": manifest_master,
            "currentPcmMasterSha256": current_master,
            "voicePlanSha256": sha256_file(cached_plan_path),
            "voiceManifestSha256": sha256_file(cached_manifest_path),
            "sourceStemSha256": {name: sha256_file(ROOT / stem["path"]) for name, stem in mix["inputs"]["sourceStems"].items()},
        },
    )


def validate_local_asr_choice() -> dict:
    status = read_json(ASR_STATUS)
    require(status.get("status") == "skipped_by_user", "ASR receipt does not record the user's local-only choice")
    require(status.get("userDecision") == "local_checks_only", "ASR receipt does not record local_checks_only")
    require(status.get("uploadAuthorized") is False, "ASR upload authorization must remain false")
    require(status.get("audioUploadOccurred") is False, "ASR receipt indicates an audio upload occurred")
    return {
        "status": "PASS",
        "userDecision": status["userDecision"],
        "uploadAuthorized": status["uploadAuthorized"],
        "audioUploadOccurred": status["audioUploadOccurred"],
    }


def decode_full_movie_and_extract_frames(path: Path) -> list[dict]:
    OUT.mkdir(parents=True, exist_ok=True)
    selector = "+".join(f"eq(n\\,{number})" for number in REPRESENTATIVE_FRAMES)
    pattern = OUT / "uhd-v3-final-frame-%02d.png"
    run([
        "ffmpeg", "-hide_banner", "-v", "error", "-xerror", "-i", str(path),
        "-map", "0:v:0", "-vf", f"select={selector}", "-fps_mode", "vfr",
        "-y", str(pattern),
        "-map", "0:a:0", "-f", "null", "-",
    ])
    extracted = []
    for index, source_frame in enumerate(REPRESENTATIVE_FRAMES, start=1):
        image_path = OUT / f"uhd-v3-final-frame-{index:02d}.png"
        require(image_path.is_file(), f"ffmpeg did not extract representative source frame {source_frame}")
        dimensions = png_dimensions(image_path)
        require(dimensions == EXPECTED_DIMENSIONS,
                f"Extracted frame {source_frame} is {dimensions[0]}x{dimensions[1]}, expected 3840x2160")
        extracted.append({
            "sourceFrame": source_frame,
            "path": relative(image_path),
            "width": dimensions[0],
            "height": dimensions[1],
            "sha256": sha256_file(image_path),
        })
    return extracted


def validate_source_stills() -> list[dict]:
    stills = sorted(OUT.glob("uhd-v3-frame-*.png"))
    verified = []
    for path in stills:
        dimensions = png_dimensions(path)
        require(dimensions == EXPECTED_DIMENSIONS,
                f"Source still is {dimensions[0]}x{dimensions[1]}, expected 3840x2160: {relative(path)}")
        verified.append({
            "path": relative(path),
            "width": dimensions[0],
            "height": dimensions[1],
            "sha256": sha256_file(path),
        })
    return verified


def validate_optional_preview() -> dict | None:
    if not PREVIEW.is_file():
        return None
    preview = inspect_encoded_media(PREVIEW, frames=270, seconds=4.5, name="overload preview")
    run([
        "ffmpeg", "-hide_banner", "-v", "error", "-xerror", "-i", str(PREVIEW),
        "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-",
    ])
    preview["fullStrictDecode"] = "PASS"
    return preview


def compare_encoded_audio_to_master() -> dict:
    """Check the actual AAC payload against the reused mix, allowing lossy error."""
    sample_rate = 8000

    def decode(path: Path) -> array.array:
        raw = run([
            "ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0",
            "-t", "180", "-ac", "1", "-ar", str(sample_rate),
            "-c:a", "pcm_s16le", "-f", "s16le", "-",
        ]).stdout
        samples = array.array("h", raw)
        if sys.byteorder != "little":
            samples.byteswap()
        return samples

    actual = decode(MOVIE)
    reference = decode(ROOT / "public/audio-voiced-v2/soundtrack.wav")
    require(len(actual) == len(reference) == 180 * sample_rate,
            "Decoded AAC and PCM reference must both cover the complete 180 s timeline")
    windows = [("whole-film", 0, 180), ("act-1", 0, 45), ("act-2", 45, 90),
               ("act-3", 90, 140), ("act-4", 140, 180)]
    measurements = []
    for name, start, end in windows:
        dot = ref_energy = actual_energy = error_energy = 0.0
        for index in range(start * sample_rate, end * sample_rate):
            a, b = actual[index], reference[index]
            dot += a * b
            ref_energy += b * b
            actual_energy += a * a
            error_energy += (a - b) ** 2
        correlation = dot / math.sqrt(ref_energy * actual_energy)
        gain = math.sqrt(actual_energy / ref_energy)
        normalized_error = math.sqrt(error_energy / ref_energy)
        require(correlation > 0.98 and 0.95 < gain < 1.05 and normalized_error < 0.2,
                f"Encoded audio differs materially from the cached mix in {name}: "
                f"correlation={correlation}, gain={gain}, error={normalized_error}")
        measurements.append({"window": name, "fromSeconds": start, "toSeconds": end,
                             "correlation": correlation, "rmsGainRatio": gain,
                             "normalizedRmsError": normalized_error})
    return {"status": "PASS", "comparisonSampleRate": sample_rate,
            "measurements": measurements,
            "note": "Decoded mono AAC versus PCM reference at matching times; allows lossy encoding error. This is not pronunciation or human listening acceptance."}


def main() -> None:
    before = read_json(BEFORE)
    mix = read_json(MIX_MANIFEST)
    timeline = validate_timeline(SOURCE_SNAPSHOT, ROOT / "timeline.json", before.get("timeline.json"))
    audio_reuse, audio_hashes = verify_audio_assets(before, mix)
    asr_choice = validate_local_asr_choice()

    encoded = inspect_encoded_media(MOVIE, frames=EXPECTED_VIDEO_FRAMES,
                                     seconds=EXPECTED_PCM_SECONDS, name="4K UHD feature film")
    extracted_frames = decode_full_movie_and_extract_frames(MOVIE)
    source_stills = validate_source_stills()
    preview = validate_optional_preview()
    encoded_audio = compare_encoded_audio_to_master()

    source_hashes = {
        "baselineTimelineSha256": before.get("timeline.json"),
        "currentTimelineSha256": sha256_file(ROOT / "timeline.json"),
        "sourceSnapshotZipSha256": sha256_file(SOURCE_SNAPSHOT),
        "currentRenderSources": {
            rel: sha256_file(ROOT / rel)
            for rel in sorted(before)
            if (ROOT / rel).is_file() and rel.startswith(("src/", "scripts/", "timeline.json", "package.json", "README.md", "VOICED-V2.md"))
        },
        "validatorScriptSha256": sha256_file(Path(__file__).resolve()),
        "finalMovieSha256": encoded["sha256"],
        "audio": audio_hashes,
    }
    report = {
        "status": "PASS",
        "edition": "EP02 native 4K UHD Chinese-first voiced v3",
        "results": {
            "nativeUhdProbe": "PASS",
            "timelineChangesLimitedToGeometry": timeline["status"],
            "strictFullMovieDecode": "PASS",
            "representativeFrameExtractionInSameDecodePass": "PASS",
            "sourceStills": "PASS" if source_stills else "NO_SOURCE_STILLS_PRESENT",
            "optionalOverloadPreview": "PASS" if preview else "NOT_PRESENT",
            "localOnlyAsrChoice": asr_choice["status"],
            "encodedAudioMatchesCachedMix": encoded_audio["status"],
        },
        "probe": encoded,
        "timeline": timeline,
        "representativeFrames": {
            "decodeAndAudioPass": "PASS",
            "sourceFrames": REPRESENTATIVE_FRAMES,
            "extracted": extracted_frames,
        },
        "sourceStills": source_stills,
        "optionalOverloadPreview": preview,
        "sourceHashes": source_hashes,
        "audioExactReuseStatus": audio_reuse,
        "encodedAudioComparison": encoded_audio,
        "encodedTiming": {
            "pcmMasterSeconds": EXPECTED_PCM_SECONDS,
            "videoFrames": encoded["videoFrames"],
            "videoFps": EXPECTED_FPS,
            "videoDurationSeconds": encoded["videoDurationSeconds"],
            "aacPresentedDurationSeconds": encoded["audioPresentedDurationSeconds"],
            "containerDurationSeconds": encoded["containerDurationSeconds"],
            "containerPaddingSeconds": encoded["containerPaddingSeconds"],
            "maximumAllowedPaddingSeconds": MAX_ENCODED_PADDING_SECONDS,
            "note": "AAC/container presentation timing is recorded separately from the exact 180 s PCM master.",
        },
        "asr": asr_choice,
        "humanListening": "pending",
        "manualVisualAcceptance": "pending",
        "note": "Local media/hash checks only. This report does not claim human listening or visual acceptance.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
