#!/usr/bin/env python3
"""Build QStory EP03 narration with the explicitly selected local Bailian CLI."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TIMELINE = ROOT / "source" / "EP03_timeline.json"
LOCAL_AUDIO = ROOT / "public" / "audio"
AUDIO = ROOT / "public" / "audio-bailian"
RAW = AUDIO / "raw"
CANONICAL = AUDIO / "canonical-24k"
CUES_48K = AUDIO / "cues-48k"
CACHE = AUDIO / "cache"
LEDGER = AUDIO / "provider-calls.json"
TIMING = ROOT / "src" / "audio-timing.json"
QA = ROOT / "review" / "bailian-audio-qa.json"
BL = Path("/Users/guoq/.local/n/bin/bl")
LOCAL_AUDIO_QA = ROOT / "review" / "audio-qa.json"

PROVIDER = "Aliyun Bailian"
MODEL = "cosyvoice-v3-flash"
VOICE = "longtian_v3"
VOICE_LABEL = "longtian_v3 (龙天磁性理智男)"
DEFAULT_RATE = 0.98
FINAL_RETRY_RATE = 1.06
RAW_RATE = 24_000
SAMPLE_RATE = 48_000
FPS = 30
DURATION_SECONDS = 180
TOTAL_SAMPLES = DURATION_SECONDS * SAMPLE_RATE
MUTE_START = 129 * FPS
MUTE_END = 130 * FPS
ROOT_SAMPLE_CAPTION_ID = "caption-002"
ROOT_SAMPLE_TEXT = "一个想法，抵达另一个人，需要多久？"


class ProviderCallError(RuntimeError):
    pass


class FinalCueDoesNotFit(ProviderCallError):
    pass


def safe_run(args: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    """Run a local media command without exposing raw tool output on failure."""
    try:
        return subprocess.run(
            args,
            check=True,
            text=True,
            stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
            stderr=subprocess.PIPE if capture else subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"{Path(args[0]).name} failed (exit {exc.returncode})") from None


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(path)


def source_data() -> dict:
    data = json.loads(TIMELINE.read_text(encoding="utf-8"))
    if data.get("durationSec") != DURATION_SECONDS or data.get("fps") != FPS:
        raise ValueError("timeline must remain 180 seconds at 30 fps")
    captions = data.get("captions", [])
    expected = [f"caption-{i:03d}" for i in range(1, 26)]
    if [item["id"] for item in captions] != expected:
        raise ValueError("source caption IDs/order changed")
    sample = next((item for item in captions if item["id"] == ROOT_SAMPLE_CAPTION_ID), None)
    if sample is None or sample["text"] != ROOT_SAMPLE_TEXT:
        raise ValueError("root-provided Bailian sample no longer matches caption-002")
    return data


def cache_key(text: str, rate: float) -> str:
    material = json.dumps(
        {
            "provider": PROVIDER,
            "model": MODEL,
            "voice": VOICE,
            "rate": rate,
            "text": text,
            "format": "wav",
            "sampleRate": RAW_RATE,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(material)


def wav_header_info(path: Path) -> dict:
    payload = path.read_bytes()
    if len(payload) < 44 or payload[0:4] != b"RIFF" or payload[8:12] != b"WAVE":
        raise ValueError(f"unsupported Bailian WAV container in {path.name}")
    if payload[12:16] != b"fmt " or struct.unpack_from("<I", payload, 16)[0] != 16:
        raise ValueError(f"unsupported WAV fmt chunk in {path.name}")
    audio_format, channels, sample_rate, byte_rate, block_align, bits = struct.unpack_from("<HHIIHH", payload, 20)
    if payload[36:40] != b"data":
        raise ValueError(f"unsupported WAV chunk order in {path.name}")
    riff_size = struct.unpack_from("<I", payload, 4)[0]
    data_size = struct.unpack_from("<I", payload, 40)[0]
    pcm = payload[44:]
    if (audio_format, channels, sample_rate, byte_rate, block_align, bits) != (1, 1, RAW_RATE, RAW_RATE * 2, 2, 16):
        raise ValueError(f"unexpected Bailian PCM format in {path.name}")
    if len(pcm) == 0 or len(pcm) % block_align:
        raise ValueError(f"unaligned PCM payload in {path.name}")
    return {
        "bytes": payload,
        "pcm": pcm,
        "physicalBytes": len(payload),
        "declaredRiffSize": riff_size,
        "declaredDataBytes": data_size,
        "channels": channels,
        "sampleRate": sample_rate,
        "byteRate": byte_rate,
        "blockAlign": block_align,
        "bitsPerSample": bits,
        "sampleCount": len(pcm) // block_align,
    }


def canonicalize_wav(raw_path: Path, canonical_path: Path) -> dict:
    info = wav_header_info(raw_path)
    pcm = info["pcm"]
    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        b"RIFF"
        + struct.pack("<I", 36 + len(pcm))
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, RAW_RATE, RAW_RATE * 2, 2, 16)
        + b"data"
        + struct.pack("<I", len(pcm))
    )
    canonical_path.write_bytes(header + pcm)
    canonical_info = wav_header_info(canonical_path)
    if canonical_info["declaredRiffSize"] != canonical_info["physicalBytes"] - 8:
        raise ValueError("canonical RIFF size check failed")
    if canonical_info["declaredDataBytes"] != len(canonical_info["pcm"]):
        raise ValueError("canonical data size check failed")
    if sha256_bytes(info["pcm"]) != sha256_bytes(canonical_info["pcm"]):
        raise ValueError("PCM payload changed during header-only normalization")
    strict_decode(canonical_path)
    return {
        "rawFile": str(raw_path.relative_to(ROOT)),
        "rawFileSha256": sha256_file(raw_path),
        "rawPhysicalBytes": info["physicalBytes"],
        "rawDeclaredRiffSize": info["declaredRiffSize"],
        "rawDeclaredDataBytes": info["declaredDataBytes"],
        "canonicalFile": str(canonical_path.relative_to(ROOT)),
        "canonicalFileSha256": sha256_file(canonical_path),
        "canonicalPhysicalBytes": canonical_info["physicalBytes"],
        "pcmSha256": sha256_bytes(canonical_info["pcm"]),
        "decodedSamplesAt24k": canonical_info["sampleCount"],
        "audioSecondsAt24k": canonical_info["sampleCount"] / RAW_RATE,
        "format": "PCM16 mono 24000 Hz",
        "headerOnlyNormalization": True,
        "pcmHashUnchanged": True,
        "strictDecode": "passed",
    }


def probe_audio(path: Path) -> dict:
    result = safe_run([
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=sample_rate,channels,sample_fmt,duration,duration_ts,time_base",
        "-of", "json", str(path),
    ], capture=True)
    streams = json.loads(result.stdout).get("streams", [])
    if len(streams) != 1:
        raise ValueError(f"expected one audio stream in {path.name}")
    return streams[0]


def strict_decode(path: Path) -> None:
    safe_run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-xerror", "-i", str(path), "-f", "null", "-"])


def resample_48k(canonical_path: Path, output_path: Path) -> dict:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    safe_run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-xerror", "-y", "-i", str(canonical_path),
        "-ar", str(SAMPLE_RATE), "-ac", "1", "-c:a", "pcm_s16le", str(output_path),
    ])
    strict_decode(output_path)
    with wave.open(str(output_path), "rb") as wav:
        if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) != (SAMPLE_RATE, 1, 2):
            raise ValueError(f"resampled cue has unexpected format: {wav.getparams()}")
        sample_count = wav.getnframes()
    return {
        "file": str(output_path.relative_to(ROOT)),
        "sha256": sha256_file(output_path),
        "decodedSamplesAt48k": sample_count,
        "audioSecondsAt48k": sample_count / SAMPLE_RATE,
        "ffprobe": probe_audio(output_path),
        "strictDecode": "passed",
    }


def collect_values(obj, keys: set[str]) -> list[str]:
    values: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            normalized_key = key.casefold().replace("-", "_")
            if normalized_key in keys:
                if isinstance(value, str):
                    values.append(value)
                elif isinstance(value, dict):
                    for nested_key in ("id", "value", "name"):
                        nested = value.get(nested_key)
                        if isinstance(nested, str):
                            values.append(nested)
            values.extend(collect_values(value, keys))
    elif isinstance(obj, list):
        for item in obj:
            values.extend(collect_values(item, keys))
    return values


def effective_identity(response_text: str) -> tuple[str, str]:
    try:
        response = json.loads(response_text)
    except json.JSONDecodeError:
        raise ProviderCallError("Bailian response was not parseable JSON; raw response was discarded") from None
    models = set(collect_values(response, {"model", "model_id", "modelid", "resolved_model"}))
    voices = set(collect_values(response, {"voice", "voice_id", "voiceid", "resolved_voice"}))
    if len(models) != 1 or len(voices) != 1:
        raise ProviderCallError("Bailian response did not identify one effective model and voice; raw response was discarded")
    return next(iter(models)), next(iter(voices))


def read_ledger() -> dict:
    if LEDGER.exists():
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        if ledger.get("provider") != PROVIDER or not isinstance(ledger.get("calls"), list):
            raise ValueError("provider call ledger does not match this task")
        return ledger
    return {"provider": PROVIDER, "calls": []}


def ensure_root_sample_ledger(ledger: dict) -> None:
    existing = [item for item in ledger["calls"] if item.get("captionId") == ROOT_SAMPLE_CAPTION_ID]
    if existing:
        return
    ledger["calls"].append({
        "captionId": ROOT_SAMPLE_CAPTION_ID,
        "origin": "root-provided sample",
        "attempts": 1,
        "requestSuccess": True,
        "accepted": True,
        "model": MODEL,
        "voice": VOICE,
        "rate": DEFAULT_RATE,
        "localFile": str((RAW / "sample.wav").relative_to(ROOT)),
    })
    write_json(LEDGER, ledger)


def invoke_bailian(caption: dict, rate: float, raw_path: Path, ledger: dict) -> dict:
    caption_id = caption["id"]
    if raw_path.exists():
        raise ProviderCallError(f"raw output already exists without reusable verified cache for {caption_id}; refusing duplicate billed synthesis")
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    call = {
        "captionId": caption_id,
        "origin": "this task",
        "attempts": 1,
        "requestSuccess": False,
        "accepted": False,
        "requestedModel": "omitted to use authenticated profile default",
        "expectedModel": MODEL,
        "requestedVoice": VOICE,
        "rate": rate,
        "textSha256": sha256_bytes(caption["text"].encode("utf-8")),
        "format": "wav",
        "sampleRate": RAW_RATE,
        "localFile": str(raw_path.relative_to(ROOT)),
    }
    ledger["calls"].append(call)
    write_json(LEDGER, ledger)
    with tempfile.NamedTemporaryFile(prefix="qstory-bailian-", suffix=".txt", delete=False) as stream:
        text_path = Path(stream.name)
        stream.write(caption["text"].encode("utf-8"))
    command = [
        str(BL), "speech", "synthesize",
        "--text-file", str(text_path),
        "--voice", VOICE,
        "--rate", f"{rate:g}",
        "--format", "wav",
        "--sample-rate", str(RAW_RATE),
        "--out", str(raw_path),
        "--concurrent", "1",
        "--output", "json",
    ]
    try:
        try:
            completed = subprocess.run(command, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except OSError:
            call["failure"] = "CLI could not be started"
            write_json(LEDGER, ledger)
            raise ProviderCallError("Bailian CLI could not be started") from None
    finally:
        text_path.unlink(missing_ok=True)

    if completed.returncode != 0:
        call["failure"] = f"CLI exit {completed.returncode}; raw output was discarded"
        write_json(LEDGER, ledger)
        raise ProviderCallError(f"Bailian synthesis failed for {caption_id} (exit {completed.returncode})")

    call["requestSuccess"] = True
    if not raw_path.exists() or raw_path.stat().st_size <= 44:
        call["failure"] = "CLI returned success without a local WAV"
        write_json(LEDGER, ledger)
        raise ProviderCallError(f"Bailian synthesis returned no local WAV for {caption_id}")

    try:
        effective_model, effective_voice = effective_identity(completed.stdout)
    except ProviderCallError:
        call["failure"] = "effective provider identity unavailable; raw response discarded"
        write_json(LEDGER, ledger)
        raise
    call["model"] = effective_model
    call["voice"] = effective_voice
    if effective_model != MODEL or effective_voice != VOICE:
        call["failure"] = "effective provider identity changed"
        write_json(LEDGER, ledger)
        raise ProviderCallError(f"effective model/voice changed for {caption_id}; stopping without retry")
    call["accepted"] = True
    write_json(LEDGER, ledger)
    return {
        "model": effective_model,
        "voice": effective_voice,
        "localFile": str(raw_path.relative_to(ROOT)),
        "rawFileSha256": sha256_file(raw_path),
    }


def load_verified_cache(caption: dict, rate: float) -> tuple[dict, Path, Path, dict]:
    key = cache_key(caption["text"], rate)
    raw_path = RAW / f"{key}.wav"
    canonical_path = CANONICAL / f"{key}.wav"
    cue_path = CUES_48K / f"{key}.wav"
    meta_path = CACHE / f"{key}.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else None
    if meta is None:
        if raw_path.exists():
            raise ProviderCallError(f"unverified raw cache exists for {caption['id']}; refusing repeat synthesis")
        return {"key": key, "rawPath": raw_path, "canonicalPath": canonical_path, "cuePath": cue_path, "metaPath": meta_path}, raw_path, cue_path, {}
    if (meta.get("provider"), meta.get("model"), meta.get("voice"), meta.get("rate"), meta.get("textSha256")) != (
        PROVIDER, MODEL, VOICE, rate, sha256_bytes(caption["text"].encode("utf-8"))
    ):
        raise ProviderCallError(f"verified cache identity mismatch for {caption['id']}")
    if not raw_path.is_file() or not canonical_path.is_file() or not cue_path.is_file():
        raise ProviderCallError(f"verified cache is incomplete for {caption['id']}")
    if sha256_file(raw_path) != meta.get("rawFileSha256") or sha256_file(canonical_path) != meta.get("canonicalFileSha256") or sha256_file(cue_path) != meta.get("cue48kFileSha256"):
        raise ProviderCallError(f"verified cache hash mismatch for {caption['id']}")
    strict_decode(canonical_path)
    strict_decode(cue_path)
    return {"key": key, "rawPath": raw_path, "canonicalPath": canonical_path, "cuePath": cue_path, "metaPath": meta_path}, raw_path, cue_path, meta


def prepare_cue(caption: dict, rate: float, ledger: dict, *, root_sample: bool = False) -> dict:
    paths, raw_path, cue_path, cached_meta = load_verified_cache(caption, rate)
    if cached_meta:
        return {**cached_meta, "cacheHit": True}

    if root_sample:
        root_sample_path = RAW / "sample.wav"
        if not root_sample_path.is_file():
            raise FileNotFoundError("root-provided raw Bailian sample is missing")
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root_sample_path, raw_path)
        identity = {"model": MODEL, "voice": VOICE, "localFile": str(root_sample_path.relative_to(ROOT)),
                    "rawFileSha256": sha256_file(raw_path)}
    else:
        identity = invoke_bailian(caption, rate, raw_path, ledger)

    canonical_meta = canonicalize_wav(raw_path, paths["canonicalPath"])
    cue_meta = resample_48k(paths["canonicalPath"], cue_path)
    meta = {
        "cacheKey": paths["key"],
        "provider": PROVIDER,
        "model": identity["model"],
        "voice": identity["voice"],
        "voiceLabel": VOICE_LABEL,
        "rate": rate,
        "format": "wav",
        "rawSampleRate": RAW_RATE,
        "textSha256": sha256_bytes(caption["text"].encode("utf-8")),
        "rawFileSha256": canonical_meta["rawFileSha256"],
        "rawFile": canonical_meta["rawFile"],
        "rawPcmSha256": canonical_meta["pcmSha256"],
        "rawPhysicalBytes": canonical_meta["rawPhysicalBytes"],
        "rawDeclaredRiffSize": canonical_meta["rawDeclaredRiffSize"],
        "rawDeclaredDataBytes": canonical_meta["rawDeclaredDataBytes"],
        "canonicalFile": canonical_meta["canonicalFile"],
        "canonicalFileSha256": canonical_meta["canonicalFileSha256"],
        "canonicalPcmSha256": canonical_meta["pcmSha256"],
        "decodedSamplesAt24k": canonical_meta["decodedSamplesAt24k"],
        "audioSecondsAt24k": canonical_meta["audioSecondsAt24k"],
        "cue48kFile": cue_meta["file"],
        "cue48kFileSha256": cue_meta["sha256"],
        "decodedSamplesAt48k": cue_meta["decodedSamplesAt48k"],
        "audioSecondsAt48k": cue_meta["audioSecondsAt48k"],
        "canonicalDecode": canonical_meta["strictDecode"],
        "cue48kDecode": cue_meta["strictDecode"],
        "cacheHit": False,
    }
    write_json(paths["metaPath"], meta)
    return meta


def read_cue_pcm(path: Path) -> tuple[bytes, int]:
    with wave.open(str(path), "rb") as wav:
        if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) != (SAMPLE_RATE, 1, 2):
            raise ValueError(f"expected mono 48kHz PCM16 cue: {path.name}")
        count = wav.getnframes()
        return wav.readframes(count), count


def align_cues(data: dict, prepared: dict[str, dict]) -> list[dict]:
    shots = {shot["id"]: shot for shot in data["shots"]}
    records: list[dict] = []
    previous_end = 0
    for caption in data["captions"]:
        rate = prepared[caption["id"]]["rate"]
        pcm, sample_count = read_cue_pcm(CUES_48K / f"{prepared[caption['id']]['cacheKey']}.wav")
        duration = sample_count / SAMPLE_RATE
        display_frames = math.ceil((duration + 0.15) * FPS)
        planned_start = int(caption["fromFrame"])
        shot = shots[caption["shotId"]]
        shot_start = int(shot["fromFrame"])
        shot_end = shot_start + int(shot["durationInFrames"])
        start = max(planned_start, previous_end)
        end = start + display_frames
        if end > shot_end:
            if caption["id"] == "caption-025" and rate == DEFAULT_RATE:
                raise FinalCueDoesNotFit("caption-025 at default rate does not fit shot-24")
            raise ProviderCallError(f"{caption['id']} at rate {rate} does not fit its shot without clipping")
        overlaps_mute = start < MUTE_END and end > MUTE_START
        if start < shot_start or end > shot_end or overlaps_mute or start < previous_end:
            raise ProviderCallError(
                f"{caption['id']} cannot fit shot/silence windows: start={start}, end={end}, "
                f"shot=[{shot_start},{shot_end}), previousEnd={previous_end}, mute=[{MUTE_START},{MUTE_END})"
            )
        item = prepared[caption["id"]]
        records.append({
            "id": caption["id"],
            "shotId": caption["shotId"],
            "text": caption["text"],
            "speaker": caption["speaker"],
            "fromFrame": start,
            "toFrameExclusive": end,
            "audioSeconds": round(duration, 6),
            "voice": VOICE,
            "rate": rate,
            "pcm": pcm,
            "sampleCount": sample_count,
            "plannedFromFrame": planned_start,
            "plannedToFrameExclusive": int(caption["toFrameExclusive"]),
            "providerCacheKey": item["cacheKey"],
            "rawFile": item["rawFile"],
            "rawFileSha256": item["rawFileSha256"],
            "rawPcmSha256": item["rawPcmSha256"],
            "canonicalFile": item["canonicalFile"],
            "canonicalFileSha256": item["canonicalFileSha256"],
            "cue48kFile": item["cue48kFile"],
            "cue48kFileSha256": item["cue48kFileSha256"],
            "decodedSamplesAt24k": item["decodedSamplesAt24k"],
            "decodedSamplesAt48k": sample_count,
            "cacheHit": item.get("cacheHit", False),
        })
        previous_end = end
    return records


def copy_existing_stems() -> dict:
    local_qa = json.loads(LOCAL_AUDIO_QA.read_text(encoding="utf-8"))
    provenance = {}
    for name in ("music.wav", "sfx.wav"):
        source = LOCAL_AUDIO / name
        target = AUDIO / name
        expected_hash = local_qa["decodedFiles"][name]["sha256"]
        source_hash = sha256_file(source)
        if source_hash != expected_hash:
            raise ValueError(f"existing local {name} hash differs from its QA record")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or sha256_file(target) != expected_hash:
            shutil.copyfile(source, target)
        target_hash = sha256_file(target)
        if target_hash != source_hash:
            raise ValueError(f"Bailian {name} copy is not byte-identical to the original stem")
        strict_decode(target)
        with wave.open(str(target), "rb") as wav:
            if (wav.getframerate(), wav.getnframes()) != (SAMPLE_RATE, TOTAL_SAMPLES):
                raise ValueError(f"Bailian {name} has the wrong duration or sample rate")
        provenance[name] = {
            "source": str(source.relative_to(ROOT)),
            "sourceSha256": source_hash,
            "copy": str(target.relative_to(ROOT)),
            "copySha256": target_hash,
            "byteIdentical": True,
            "sourceQaSha256": expected_hash,
        }
    return provenance


def local_audio_module():
    path = ROOT / "scripts" / "make-audio.py"
    spec = importlib.util.spec_from_file_location("qstory_local_audio_helpers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load existing local audio helper module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.AUDIO = AUDIO
    return module


def check_file(path: Path, module) -> dict:
    module.ffmpeg_decode_check(path)
    with wave.open(str(path), "rb") as wav:
        frame_count = wav.getnframes()
        sample_rate = wav.getframerate()
        channels = wav.getnchannels()
        width = wav.getsampwidth()
        params = wav.getparams()
    if frame_count != TOTAL_SAMPLES or sample_rate != SAMPLE_RATE:
        raise ValueError(f"{path.name} is not 180 seconds at 48kHz: {params}")
    return {
        "frames": frame_count,
        "sampleRate": sample_rate,
        "channels": channels,
        "sampleWidthBytes": width,
        "sha256": sha256_file(path),
        "ffprobe": module.probe_audio(path),
        "ffmpegDecode": "passed",
    }


def ensure_sample(data: dict, ledger: dict) -> dict:
    AUDIO.mkdir(parents=True, exist_ok=True)
    for path in (RAW, CANONICAL, CUES_48K, CACHE):
        path.mkdir(parents=True, exist_ok=True)
    ensure_root_sample_ledger(ledger)
    caption = next(item for item in data["captions"] if item["id"] == ROOT_SAMPLE_CAPTION_ID)
    meta = prepare_cue(caption, DEFAULT_RATE, ledger, root_sample=True)
    if meta["model"] != MODEL or meta["voice"] != VOICE:
        raise ProviderCallError("root-provided sample metadata does not match the selected model/voice")
    return {
        "captionId": caption["id"],
        "text": caption["text"],
        "model": meta["model"],
        "voice": meta["voice"],
        "rate": meta["rate"],
        "rawFile": meta["rawFile"],
        "rawFileSha256": meta["rawFileSha256"],
        "rawPcmSha256": meta["rawPcmSha256"],
        "canonicalFile": meta["canonicalFile"],
        "canonicalFileSha256": meta["canonicalFileSha256"],
        "canonicalPcmSha256": meta["canonicalPcmSha256"],
        "cue48kFile": meta["cue48kFile"],
        "cue48kFileSha256": meta["cue48kFileSha256"],
        "decodedSamplesAt24k": meta["decodedSamplesAt24k"],
        "decodedSamplesAt48k": meta["decodedSamplesAt48k"],
        "audioSeconds": meta["audioSecondsAt48k"],
        "headerOnlyNormalization": True,
        "canonicalDecode": meta["canonicalDecode"],
        "resampledDecode": meta["cue48kDecode"],
    }


def run_full(data: dict, ledger: dict, sample_meta: dict) -> dict:
    local_audio = local_audio_module()
    stem_provenance = copy_existing_stems()
    prepared: dict[str, dict] = {}
    for caption in data["captions"]:
        if caption["id"] == ROOT_SAMPLE_CAPTION_ID:
            meta = prepare_cue(caption, DEFAULT_RATE, ledger, root_sample=True)
            prepared[caption["id"]] = meta
        else:
            rate = DEFAULT_RATE
            key = cache_key(caption["text"], rate)
            raw_path = RAW / f"{key}.wav"
            cache_meta_path = CACHE / f"{key}.json"
            cached_exists = cache_meta_path.exists()
            if raw_path.exists() and not cached_exists:
                raise ProviderCallError(f"unverified raw output exists for {caption['id']}; refusing possible duplicate call")
            if not cached_exists:
                meta = prepare_cue(caption, rate, ledger)
            else:
                meta = prepare_cue(caption, rate, ledger)
            prepared[caption["id"]] = meta

    # Every new narration cue is now canonical, decoded, and cached before timing/alignment.
    try:
        records = align_cues(data, prepared)
    except FinalCueDoesNotFit:
        final_caption = data["captions"][-1]
        meta = prepare_cue(final_caption, FINAL_RETRY_RATE, ledger)
        prepared[final_caption["id"]] = meta
        records = align_cues(data, prepared)
    voice_path = AUDIO / "voice_zh.wav"
    local_audio.write_mono_stem(records, voice_path)

    timing = {
        "cues": [{key: record[key] for key in (
            "id", "shotId", "text", "speaker", "fromFrame", "toFrameExclusive", "audioSeconds", "voice", "rate"
        )} for record in records],
        "durationSeconds": DURATION_SECONDS,
        "provider": PROVIDER,
        "voice": VOICE,
        "sampleRate": SAMPLE_RATE,
        "model": MODEL,
    }
    write_json(TIMING, timing)

    soundtrack_path = AUDIO / "soundtrack.wav"
    mix_measurement = local_audio.mix_and_loudnorm(
        soundtrack_path, voice_path, AUDIO / "music.wav", AUDIO / "sfx.wav"
    )
    # The existing local mixer targets -1 dBTP, but ffmpeg's two-pass result
    # can round a measured peak a few hundredths above that ceiling. Apply a
    # fixed, linear headroom trim to the integrated mix; this does not alter
    # cue timing or any source stem.
    headroom_path = soundtrack_path.with_name("soundtrack.headroom.wav")
    safe_run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-xerror", "-y",
        "-i", str(soundtrack_path), "-af", "volume=0.98", "-ar", str(SAMPLE_RATE),
        "-c:a", "pcm_s24le", str(headroom_path),
    ])
    strict_decode(headroom_path)
    with wave.open(str(headroom_path), "rb") as wav:
        if (wav.getframerate(), wav.getnframes(), wav.getnchannels(), wav.getsampwidth()) != (
            SAMPLE_RATE, TOTAL_SAMPLES, 2, 3
        ):
            raise ValueError(f"headroom-trimmed soundtrack has unexpected format: {wav.getparams()}")
    headroom_path.replace(soundtrack_path)
    mix_measurement["headroomAttenuation"] = {
        "linearGain": 0.98,
        "decibels": round(20 * math.log10(0.98), 4),
        "reason": "deterministic margin for -1 dBTP ceiling after two-pass loudnorm",
    }
    silence = {
        "fromSeconds": 129.0,
        "toSecondsExclusive": 130.0,
        "voiceMaxAbsPcm": local_audio.window_peak(voice_path, 129.0, 130.0),
        "musicMaxAbsPcm": local_audio.window_peak(AUDIO / "music.wav", 129.0, 130.0),
        "sfxMaxAbsPcm": local_audio.window_peak(AUDIO / "sfx.wav", 129.0, 130.0),
    }
    if any(silence[key] != 0 for key in ("voiceMaxAbsPcm", "musicMaxAbsPcm", "sfxMaxAbsPcm")):
        raise ValueError(f"129-130s source-stem silence failed: {silence}")
    local_audio.force_pcm_silence(soundtrack_path, 129.0, 130.0)
    silence["soundtrackMaxAbsPcm"] = local_audio.window_peak(soundtrack_path, 129.0, 130.0)
    if silence["soundtrackMaxAbsPcm"] != 0:
        raise ValueError(f"129-130s soundtrack silence failed: {silence}")

    decoded_files = {}
    for path in (voice_path, AUDIO / "music.wav", AUDIO / "sfx.wav", soundtrack_path):
        decoded_files[path.name] = check_file(path, local_audio)
    loudness = local_audio.ebur128_result(soundtrack_path)
    final_measurement = local_audio.loudnorm_measure(soundtrack_path)
    true_peak = float(final_measurement["input_tp"])
    if true_peak > -1.0:
        raise ValueError(f"final true peak exceeds -1 dBTP: {true_peak} dBTP")
    loudness["truePeak"] = f"{true_peak:.2f} dBTP"

    ledger["calls"] = sorted(ledger["calls"], key=lambda item: item.get("captionId", ""))
    write_json(LEDGER, ledger)
    attempts_total = sum(int(item.get("attempts", 0)) for item in ledger["calls"])
    successes_total = sum(1 for item in ledger["calls"] if item.get("requestSuccess") and item.get("accepted"))
    failures_total = sum(1 for item in ledger["calls"] if item.get("attempts") and not (item.get("requestSuccess") and item.get("accepted")))
    accepted_caption_ids = {item.get("captionId") for item in ledger["calls"] if item.get("requestSuccess") and item.get("accepted")}
    call_stats = {
        "attemptsIncludingRootSample": attempts_total,
        "acceptedSuccessesIncludingRootSample": successes_total,
        "uniqueAcceptedCaptionCountIncludingRootSample": len(accepted_caption_ids),
        "failuresOrRejectedResponses": failures_total,
        "rootSampleAttempts": 1,
        "rootSampleAcceptedSuccesses": 1,
        "newCallsThisRun": sum(1 for item in ledger["calls"] if item.get("origin") == "this task" and item.get("requestSuccess") and item.get("accepted")),
        "callLedgerFile": str(LEDGER.relative_to(ROOT)),
        "actualBill": "unknown",
    }
    accepted_by_caption: dict[str, list[dict]] = {}
    for item in ledger["calls"]:
        if item.get("requestSuccess") and item.get("accepted"):
            accepted_by_caption.setdefault(item.get("captionId"), []).append(item)
    retry_calls = [
        item for items in accepted_by_caption.values() for item in items
        if item.get("origin") == "this task"
    ]
    duplicate_ids = {caption_id for caption_id, items in accepted_by_caption.items() if len(items) > 1}
    retry_policy_ok = (
        attempts_total in (25, 26)
        and duplicate_ids <= {"caption-025"}
        and len(accepted_by_caption.get("caption-025", [])) <= 2
        and all(item.get("accepted") for item in retry_calls)
    )
    call_stats["retryCount"] = max(0, attempts_total - 25)
    if successes_total != attempts_total or failures_total != 0 or accepted_caption_ids != {item["id"] for item in data["captions"]}:
        raise ValueError(f"expected 25 total successful cues including root sample; got {call_stats}")
    if not retry_policy_ok:
        raise ValueError(f"provider call ledger exceeds the approved one-final-cue retry policy: {call_stats}")

    qa = {
        "status": "automated_pcm_checks_passed",
        "provider": PROVIDER,
        "effectiveModel": MODEL,
        "voice": VOICE,
        "voiceLabel": VOICE_LABEL,
        "requestedRate": DEFAULT_RATE,
        "finalCueRetryRate": FINAL_RETRY_RATE,
        "format": "wav",
        "providerSampleRate": RAW_RATE,
        "outputSampleRate": SAMPLE_RATE,
        "sourceTimelineSha256": sha256_file(TIMELINE),
        "sample": sample_meta,
        "cueCount": len(records),
        "cueIds": [record["id"] for record in records],
        "cueTiming": [{key: record[key] for key in (
            "id", "shotId", "fromFrame", "toFrameExclusive", "plannedFromFrame", "plannedToFrameExclusive",
            "audioSeconds", "decodedSamplesAt24k", "decodedSamplesAt48k", "rate", "providerCacheKey",
            "rawFile", "rawFileSha256", "rawPcmSha256", "canonicalFile", "canonicalFileSha256",
            "cue48kFile", "cue48kFileSha256", "cacheHit"
        )} for record in records],
        "cloudCalls": call_stats,
        "musicAndEffectsProvenance": stem_provenance,
        "decodedFiles": decoded_files,
        "silenceWindow": silence,
        "loudness": {**loudness, "targetIntegratedLUFS": -16, "targetMaximumTruePeakDbTP": -1},
        "ffmpegMixAnalysis": {**mix_measurement, "finalMeasuredInput": final_measurement},
        "rawResponsesSaved": False,
        "signedUrlsOrKeysSaved": False,
        "humanListening": "not performed",
    }
    write_json(QA, qa)
    return {
        "status": qa["status"],
        "timing": str(TIMING),
        "qa": str(QA),
        "cloudCalls": call_stats,
        "silenceWindow": silence,
        "loudness": qa["loudness"],
        "files": decoded_files,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--sample", action="store_true", help="canonicalize and fully decode the root-provided sample only")
    modes.add_argument("--full", action="store_true", help="synthesize remaining cues, assemble stems, mix, and record QA")
    args = parser.parse_args()
    if not BL.is_file():
        raise RuntimeError(f"Bailian CLI is unavailable at {BL}")
    data = source_data()
    AUDIO.mkdir(parents=True, exist_ok=True)
    for path in (RAW, CANONICAL, CUES_48K, CACHE):
        path.mkdir(parents=True, exist_ok=True)
    ledger = read_ledger()
    sample_meta = ensure_sample(data, ledger)
    if args.sample:
        print(json.dumps({"status": "sample_canonical_decode_passed", "sample": sample_meta}, ensure_ascii=False, indent=2))
        return 0
    result = run_full(data, ledger, sample_meta)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProviderCallError, RuntimeError, ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Bailian audio build stopped: {exc}", file=sys.stderr)
        raise SystemExit(1)
