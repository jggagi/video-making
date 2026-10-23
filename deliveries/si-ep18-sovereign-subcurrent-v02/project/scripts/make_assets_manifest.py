#!/usr/bin/env python3
"""Index the current EP18 source and public assets without inventing synthesis or review results."""

from pathlib import Path
import hashlib
import json
import wave

PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT.parent
OUTPUT = PROJECT / "assets-manifest.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def wav_info(path: Path) -> dict[str, object]:
    with wave.open(str(path), "rb") as stream:
        return {
            "sampleRateHz": stream.getframerate(),
            "channels": stream.getnchannels(),
            "sampleWidthBytes": stream.getsampwidth(),
            "declaredSampleFramesPerChannel": stream.getnframes(),
            "compressionType": stream.getcomptype(),
            "compressionName": stream.getcompname(),
        }

if OUTPUT.exists():
    raise FileExistsError("Refusing to overwrite existing assets-manifest.json")

delivery = json.loads((WORK / "delivery.json").read_text(encoding="utf-8"))
authorization_path = PROJECT / "audio-authorization.json"
authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
source_files = sorted(path for path in (PROJECT / "src").rglob("*") if path.is_file())
source_map = {
    str(path.relative_to(PROJECT)): {"sha256": sha256_file(path), "bytes": path.stat().st_size}
    for path in source_files
}
assets = []
public_dir = PROJECT / "public"
for path in sorted(public_dir.rglob("*")) if public_dir.exists() else []:
    if not path.is_file() or path.name.startswith(".") or "mix-candidate-" in str(path):
        continue
    item = {
        "id": str(path.relative_to(public_dir)),
        "path": str(path.relative_to(PROJECT)),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }
    if path.suffix.lower() == ".wav":
        try:
            item["measuredWav"] = wav_info(path)
        except (OSError, wave.Error) as exc:
            item["wavInspection"] = {"status": "FAILED", "reason": str(exc)}
    assets.append(item)

synthesis_path = WORK / "review" / "audio-synthesis.json"
synthesis = None
if synthesis_path.is_file():
    synthesis = json.loads(synthesis_path.read_text(encoding="utf-8"))
cues = synthesis.get("cues", []) if isinstance(synthesis, dict) else []
actual_models = sorted({row.get("actualModel") for row in cues if isinstance(row, dict) and isinstance(row.get("actualModel"), str)})
actual_voices = sorted({row.get("actualVoice") for row in cues if isinstance(row, dict) and isinstance(row.get("actualVoice"), str)})

report = {
    "schemaVersion": 1,
    "work": {"id": delivery.get("slug"), "title": delivery.get("title"), "platforms": delivery.get("platforms")},
    "generation": "Local deterministic 2D Canvas2D/SVG source; assets listed from the current project public directory.",
    "visualSource": source_map,
    "typography": {"source": "System fonts are provided by the rendering machine and are not copied into this project; another machine must verify its rendered layout."},
    "narrationAuthorization": {
        "path": str(authorization_path.relative_to(PROJECT)),
        "sha256": sha256_file(authorization_path),
        "provider": authorization.get("provider"),
        "voice": authorization.get("voice"),
        "expectedEffectiveModel": authorization.get("expectedEffectiveModel"),
        "actualModelsFromSynthesisEvidence": actual_models,
        "actualVoicesFromSynthesisEvidence": actual_voices,
        "synthesisEvidence": str(synthesis_path.relative_to(WORK)) if synthesis_path.is_file() else None,
        "synthesisEvidenceSha256": sha256_file(synthesis_path) if synthesis_path.is_file() else None,
        "synthesisCueCount": len(cues),
    },
    "musicAndSfx": "See current project audio pipeline and its generated mix QA; no additional source identity or acceptance is inferred here.",
    "assets": assets,
}
OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"manifest": str(OUTPUT.relative_to(WORK)), "sourceFiles": len(source_files), "publicAssets": len(assets), "actualModels": actual_models, "actualVoices": actual_voices}, ensure_ascii=False, indent=2))
