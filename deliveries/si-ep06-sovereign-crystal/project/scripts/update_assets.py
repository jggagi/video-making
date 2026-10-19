#!/usr/bin/env python3
"""Record EP06's shared procedural assets and local narration/audio provenance."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def relative(path: Path) -> str:
    return path.relative_to(PROJECT).as_posix()


def main() -> int:
    assets = []
    for path in sorted((PROJECT / "src").glob("*")):
        if path.suffix in {".ts", ".tsx"}:
            assets.append({
                "id": "procedural-" + path.stem,
                "kind": "frame_driven_analytical_geometry",
                "path": relative(path),
                "sha256": digest(path),
                "seed": "fixed indexed trigonometric sequences; shared frame clock",
                "generation_provider": "local source; no image generation",
            })

    provider_path = PROJECT / "public/audio/provider-manifest.json"
    provider = json.loads(provider_path.read_text(encoding="utf-8"))
    if not isinstance(provider, dict) or not isinstance(provider.get("segments"), dict):
        raise ValueError("provider-manifest.json must contain the generated segment map")
    for sid, record in sorted(provider["segments"].items()):
        for role in ("raw", "canonical", "cue"):
            key = role + "_path"
            relative_path = record.get(key)
            if not isinstance(relative_path, str):
                raise ValueError(f"{sid} is missing {key} in provider-manifest.json")
            path = (PROJECT / relative_path).resolve()
            if not path.is_relative_to(PROJECT.resolve()) or not path.is_file():
                raise ValueError(f"{sid} {role} path is missing or escapes project: {relative_path}")
            assets.append({
                "id": sid + "-" + role,
                "kind": "narration",
                "path": relative(path),
                "sha256": digest(path),
                "cache_key": record.get("cache_key"),
                "tts_phonetic_text": record.get("tts_phonetic_text"),
                "settings": provider.get("settings"),
                "reported_model": record.get("effective_model", record.get("effectiveModel", "see provider manifest")),
                "shared_by": ["Landscape4K", "PortraitVertical"],
            })

    settings_path = PROJECT / "public/audio/mix-settings.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    for name in ("master", "narration", "score", "sfx"):
        path = PROJECT / f"public/audio/{name}.wav"
        if not path.is_file():
            raise FileNotFoundError(f"required shared EP06 audio asset is missing: {relative(path)}")
        assets.append({
            "id": "audio-" + name,
            "kind": "shared_PCM" if name == "master" else "reproducible_audio_stem",
            "path": relative(path),
            "sha256": digest(path),
            "sample_rate": 48_000,
            "channels": 2,
            "samples_per_channel": 5_760_000,
            "shared_by": ["Landscape4K", "PortraitVertical"],
            "provenance": relative(settings_path),
        })

    out = {
        "schema_version": 1,
        "reuse_policy": "One source, one narration cache, one PCM master, two native layouts. No platform-specific generation.",
        "assets": assets,
        "fonts": [
            {"family": "PingFang SC / Hiragino Sans GB", "source": "installed macOS system fonts, locally resolved", "redistributed": False},
            {"family": "Menlo / Arial", "source": "installed macOS fonts", "redistributed": False},
        ],
        "scientific_boundaries": "scientific-notes.md",
        "audio_phrase_alignment": "Measured PCM cue spans; phrase boundaries are estimated proportionally and are not ASR or word alignment.",
    }
    output = PROJECT / "assets-manifest.json"
    output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Recorded {len(assets)} EP06 shared assets; no generation calls.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
