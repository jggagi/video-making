#!/usr/bin/env python3
"""Bind fresh v02 media and shared-audio QA evidence without changing delivery.json."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DELIVERY_DIR = PROJECT_DIR.parent
REVIEW_DIR = DELIVERY_DIR / "review"


class FinalizeError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FinalizeError(f"cannot read {path.relative_to(DELIVERY_DIR)}: {exc}") from None
    if not isinstance(value, dict):
        raise FinalizeError(f"{path.relative_to(DELIVERY_DIR)} must contain an object")
    return value


def latest_report(pattern: str) -> Path:
    candidates = [path for path in REVIEW_DIR.glob(pattern) if path.is_file()]
    if not candidates:
        raise FinalizeError(f"required QA report not found: review/{pattern}")
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.name))


def report_target() -> Path:
    base = REVIEW_DIR / "validation-provenance.json"
    if not base.exists():
        return base
    for revision in range(2, 10000):
        candidate = base.with_name(f"validation-provenance-r{revision:02d}.json")
        if not candidate.exists():
            return candidate
    raise FinalizeError("no unused validation-provenance report name is available")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        manifest_path = DELIVERY_DIR / "delivery.json"
        manifest = load(manifest_path)
        project_report_path = latest_report("project-validation*.json")
        media_report_path = latest_report("encoded-qa-summary*.json")
        audio_report_path = latest_report("shared-audio-correlation*.json")
        project_report = load(project_report_path)
        media_report = load(media_report_path)
        audio_report = load(audio_report_path)
        if project_report.get("status") != "PASS":
            raise FinalizeError(f"source validation is not PASS: {project_report_path.name}")
        if media_report.get("status") != "PASS" or len(media_report.get("layouts", [])) != 2:
            raise FinalizeError(f"both final layouts and full decode must pass: {media_report_path.name}")
        if audio_report.get("status") != "PASS" or len(audio_report.get("tracks", [])) != 2:
            raise FinalizeError(f"both AAC tracks must pass shared-master correlation: {audio_report_path.name}")

        outputs: list[dict[str, Any]] = []
        by_layout = {item.get("layout"): item for item in media_report["layouts"] if isinstance(item, dict)}
        for layout, key in (("landscape", "bilibili"), ("portrait", "xiaohongshu")):
            spec = manifest.get("outputs", {}).get(key, {})
            path_value = spec.get("path")
            if not isinstance(path_value, str):
                raise FinalizeError(f"delivery.json outputs.{key}.path is missing")
            media = (DELIVERY_DIR / path_value).resolve()
            try:
                media.relative_to(DELIVERY_DIR.resolve())
            except ValueError:
                raise FinalizeError(f"delivery.json outputs.{key} escapes the delivery folder") from None
            if not media.is_file():
                raise FinalizeError(f"final output is missing: {path_value}")
            measured = by_layout.get(layout)
            if measured is None or measured.get("sha256") != sha256_file(media) or measured.get("path") != media.relative_to(DELIVERY_DIR).as_posix():
                raise FinalizeError(f"media hash/path differs from fresh encoded QA: {layout}")
            if measured.get("status") != "PASS" or not measured.get("strict_full_decode", {}).get("pass"):
                raise FinalizeError(f"encoded media validation is incomplete for {layout}")
            audio_track = next((item for item in audio_report["tracks"] if item.get("layout") == layout), None)
            if audio_track is None or audio_track.get("status") != "PASS" or audio_track.get("sha256") != measured.get("sha256"):
                raise FinalizeError(f"shared audio check is missing or bound to a different {layout} output")
            outputs.append({
                "layout": layout,
                "path": media.relative_to(DELIVERY_DIR).as_posix(),
                "bytes": media.stat().st_size,
                "sha256": measured["sha256"],
                "video_and_audio_checks": measured.get("checks"),
                "shared_audio_status": audio_track.get("status"),
                "strict_full_decode": measured["strict_full_decode"],
                "mp4_faststart": measured.get("mp4_faststart"),
            })

        evidence = [project_report_path, media_report_path, audio_report_path]
        result = {
            "status": "PASS",
            "manifest_sha256": sha256_file(manifest_path),
            "outputs": outputs,
            "evidence": [
                {"path": path.relative_to(DELIVERY_DIR).as_posix(), "sha256": sha256_file(path)}
                for path in evidence
            ],
            "human_acceptance": {
                "visual_style_proof": "user_approved_12_second_proof",
                "continuous_120_second_visual_review": "pending",
                "continuous_viewing_and_listening": "pending",
                "phone_and_platform_playback": "pending",
            },
            "limitations": [
                "This report binds automated technical evidence only.",
                "It does not change delivery.json or label human acceptance complete.",
            ],
        }
        REVIEW_DIR.mkdir(parents=True, exist_ok=True)
        target = report_target()
        temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, target)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"Report: {target}")
        return 0
    except (FinalizeError, OSError, KeyError, TypeError) as exc:
        print(f"[finalize-metadata] ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
