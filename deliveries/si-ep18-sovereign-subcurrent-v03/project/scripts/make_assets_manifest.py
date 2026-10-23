#!/usr/bin/env python3
"""Hash the current EP18 v03 source and public assets without inventing review results."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from audio_pipeline import PipelineError, pcm_wav_payload


PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT.parent
OUTPUT = PROJECT / "assets-manifest.json"
EXPECTED_WORK_ID = "si-ep18-sovereign-subcurrent-v03"
INPUT_PATHS = (
    "delivery.json",
    "source/script.md",
    "project/segments.json",
    "project/timeline.json",
    "project/sfx_events.json",
    "project/audio-plan.json",
    "project/font-sources.json",
    "project/package.json",
    "project/package-lock.json",
    "project/tsconfig.json",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    before = path.stat()
    digest = sha256_file(path)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError(f"File changed while hashing: {path.name}")
    return {"sha256": digest, "bytes": after.st_size}


def wav_info(path: Path) -> dict[str, Any]:
    """Describe only the physically present, aligned PCM payload."""
    info = pcm_wav_payload(path)
    sample_frames = info["sampleFrames"]
    sample_rate = info["sampleRate"]
    return {
        "sampleCountBasis": "physical_data_payload",
        "physicalPayloadSampleFramesPerChannel": sample_frames,
        "physicalPayloadDurationSeconds": sample_frames / sample_rate,
        "sampleRateHz": sample_rate,
        "channels": info["channels"],
        "bitsPerSample": info["bitsPerSample"],
        "sampleWidthBytes": info["sampleWidthBytes"],
        "rawHeaderMismatch": info["headerMismatch"],
        "declaredRiffBytes": info["riffDeclaredBytes"],
        "declaredDataBytes": info["dataDeclaredBytes"],
        "physicalDataBytes": info["dataPhysicalBytes"],
        "physicalFileBytes": info["physicalBytes"],
        "streamingHeaderRepairEligible": info["streamingHeaderRepairEligible"],
    }


def is_transient(path: Path, traversal_root: Path) -> bool:
    """Keep hidden files and Python bytecode out of reproducible asset indexes."""
    relative_parts = path.relative_to(traversal_root).parts
    return (
        any(part.startswith(".") or part == "__pycache__" for part in relative_parts)
        or path.suffix.lower() in {".pyc", ".pyo"}
    )


def json_or_none(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError("Refusing to overwrite assets-manifest.json")

    delivery_path = WORK / "delivery.json"
    delivery = json.loads(delivery_path.read_text(encoding="utf-8"))
    if delivery.get("slug") != EXPECTED_WORK_ID:
        raise RuntimeError("delivery.json does not identify EP18 v03")

    final_output: dict[str, Any] = {"status": "NOT_AVAILABLE"}
    outputs = delivery.get("outputs")
    xhs_output = outputs.get("xiaohongshu") if isinstance(outputs, dict) else None
    relative_movie = xhs_output.get("path") if isinstance(xhs_output, dict) else None
    if isinstance(relative_movie, str) and relative_movie.strip():
        movie_path = (WORK / relative_movie).resolve()
        if not movie_path.is_relative_to(WORK.resolve()):
            raise RuntimeError("delivery.json final movie path escapes the v03 delivery")
        if movie_path.is_file():
            movie_record = file_record(movie_path)
            declared_sha = delivery.get("final_movie_sha256")
            final_output = {
                "status": "AVAILABLE",
                "path": relative_movie,
                **movie_record,
                "deliveryManifestSha256": declared_sha if isinstance(declared_sha, str) else None,
                "matchesDeliveryManifestSha256": movie_record["sha256"].lower() == declared_sha.lower() if isinstance(declared_sha, str) else None,
            }

    inputs: dict[str, dict[str, Any]] = {}
    missing_inputs: list[str] = []
    for relative in INPUT_PATHS:
        path = WORK / relative
        if path.is_file():
            inputs[relative] = file_record(path)
        else:
            missing_inputs.append(relative)

    visual_source: dict[str, dict[str, Any]] = {}
    for base in (PROJECT / "src", PROJECT / "scripts"):
        if not base.exists():
            continue
        for path in sorted(
            candidate for candidate in base.rglob("*")
            if candidate.is_file() and not is_transient(candidate, base)
        ):
            visual_source[str(path.relative_to(WORK))] = file_record(path)

    public_assets: list[dict[str, Any]] = []
    public_dir = PROJECT / "public"
    if public_dir.exists():
        for path in sorted(
            candidate for candidate in public_dir.rglob("*")
            if candidate.is_file() and not is_transient(candidate, public_dir)
        ):
            if "mix-candidate-" in str(path):
                continue
            item: dict[str, Any] = {
                "path": str(path.relative_to(WORK)),
                **file_record(path),
            }
            if path.suffix.lower() == ".wav":
                try:
                    item["wavPayloadInspection"] = wav_info(path)
                except (OSError, PipelineError) as exc:
                    item["wavInspection"] = {"status": "FAILED", "reason": str(exc)}
            public_assets.append(item)

    audio_plan_path = PROJECT / "audio-plan.json"
    audio_plan = json_or_none(audio_plan_path) or {}
    synthesis_path = WORK / "review" / "audio-synthesis.json"
    synthesis = json_or_none(synthesis_path)
    synthesis_cues = synthesis.get("cues", []) if isinstance(synthesis, dict) else []
    segment_rows = json_or_none(PROJECT / "segments.json")
    current_cue_text = {
        row["id"]: row["tts_phonetic_text"]
        for row in segment_rows
        if isinstance(row, dict) and isinstance(row.get("id"), str) and isinstance(row.get("tts_phonetic_text"), str)
    } if isinstance(segment_rows, list) else {}
    actual_cues: list[dict[str, Any]] = []
    for cue in synthesis_cues:
        if not isinstance(cue, dict) or not isinstance(cue.get("id"), str):
            continue
        actual_model = cue.get("actualModel")
        actual_voice = cue.get("actualVoice")
        if not isinstance(actual_model, str) or not isinstance(actual_voice, str):
            continue
        canonical_name = cue.get("canonicalAudioFile")
        spoken_text = cue.get("spokenText")
        expected_text = current_cue_text.get(cue["id"])
        expected_text_sha = sha256_text(expected_text) if isinstance(expected_text, str) else None
        spoken_text_sha = sha256_text(spoken_text) if isinstance(spoken_text, str) else None
        reported_text_sha = cue.get("textSha256") if isinstance(cue.get("textSha256"), str) else None
        actual_cues.append({
            "id": cue["id"],
            "provider": cue.get("provider") if isinstance(cue.get("provider"), str) else None,
            "requestedModel": cue.get("requestedModel") if isinstance(cue.get("requestedModel"), str) else None,
            "actualModel": actual_model,
            "voice": cue.get("voice") if isinstance(cue.get("voice"), str) else None,
            "actualVoice": actual_voice,
            "providerSampleRate": cue.get("providerSampleRate") if isinstance(cue.get("providerSampleRate"), int) else None,
            "cacheReuse": cue.get("cacheReuse") if isinstance(cue.get("cacheReuse"), bool) else None,
            "cacheKey": cue.get("cacheKey") if isinstance(cue.get("cacheKey"), str) else None,
            "reportedTextSha256": reported_text_sha,
            "spokenTextSha256": spoken_text_sha,
            "currentCueTextSha256": expected_text_sha,
            "reportedTextMatchesCurrentCue": (
                isinstance(spoken_text, str) and spoken_text == expected_text
                and reported_text_sha == expected_text_sha
            ) if isinstance(expected_text, str) else None,
            "canonicalAudioFile": Path(canonical_name).name if isinstance(canonical_name, str) else None,
            "canonicalSha256": cue.get("canonicalSha256") if isinstance(cue.get("canonicalSha256"), str) else None,
        })

    fonts_dir = PROJECT / "public" / "fonts"
    font_source_manifest = json_or_none(PROJECT / "font-sources.json")
    declared_fonts: dict[str, dict[str, Any]] = {}
    if isinstance(font_source_manifest, list):
        for declared in font_source_manifest:
            if isinstance(declared, dict) and isinstance(declared.get("path"), str):
                declared_fonts["project/" + declared["path"].replace("\\", "/")] = declared
    font_records = []
    if fonts_dir.exists():
        for path in sorted(
            candidate for candidate in fonts_dir.rglob("*")
            if candidate.is_file() and not is_transient(candidate, fonts_dir)
        ):
            relative_path = str(path.relative_to(WORK))
            measured = file_record(path)
            declared = declared_fonts.get(relative_path)
            record: dict[str, Any] = {"path": relative_path, **measured}
            if declared is None:
                record["provenance"] = {"status": "NOT_SPECIFIED_IN_PROJECT"}
            else:
                declared_sha = declared.get("sha256")
                declared_bytes = declared.get("bytes")
                record["provenance"] = {
                    "status": "DECLARED",
                    "source": declared.get("source"),
                    "license": declared.get("license"),
                    "declaredSha256": declared_sha,
                    "declaredBytes": declared_bytes,
                    "matchesDeclaredSha256": measured["sha256"] == declared_sha if isinstance(declared_sha, str) else None,
                    "matchesDeclaredBytes": measured["bytes"] == declared_bytes if isinstance(declared_bytes, int) else None,
                }
            font_records.append(record)

    mix_qa_path = WORK / "review" / "audio-mix-qa.json"
    synthesis_evidence = None
    if synthesis_path.is_file():
        synthesis_evidence = {
            "path": str(synthesis_path.relative_to(WORK)),
            **file_record(synthesis_path),
        }
    mix_evidence = None
    if mix_qa_path.is_file():
        mix_evidence = {
            "path": str(mix_qa_path.relative_to(WORK)),
            **file_record(mix_qa_path),
        }

    report = {
        "schemaVersion": 1,
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "work": {"id": delivery.get("slug"), "title": delivery.get("title"), "platforms": delivery.get("platforms")},
        "inputFiles": inputs,
        "missingExpectedInputs": missing_inputs,
        "sourceFiles": visual_source,
        "publicAssets": public_assets,
        "finalOutput": final_output,
        "typography": {
            "source": "Per-file metadata from project/font-sources.json where declared; other bundled font files are marked as provenance not specified.",
            "files": font_records,
        },
        "narrationIdentity": {
            "expectedFromAudioPlan": {"model": audio_plan.get("model"), "voice": audio_plan.get("voice")},
            "actualIdentityStatus": "AVAILABLE" if actual_cues else "NOT_AVAILABLE",
            "actualReportedCues": actual_cues,
            "synthesisEvidence": synthesis_evidence,
            "mixEvidence": mix_evidence,
            "credentialsOrRawProviderOutputIncluded": False,
        },
        "acceptance": "This index records file identity and available synthesis metadata only; it does not mark visual, audio, or human review as passed.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "manifest": str(OUTPUT.relative_to(WORK)),
        "inputFiles": len(inputs),
        "sourceFiles": len(visual_source),
        "publicAssets": len(public_assets),
        "fontFiles": len(font_records),
        "actualQwenCueIdentities": len(actual_cues),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"make_assets_manifest: {exc}")
