#!/usr/bin/env python3
"""Restore-probe only the EP18 v04 Xiaohongshu final Release asset."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any


PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT.parent
ROOT = WORK.parents[1]
WORK_ID = "si-ep18-sovereign-subcurrent-v04"
PLAN = json.loads((PROJECT / "render-plan.json").read_text(encoding="utf-8"))
WORK_TITLE = PLAN["work"]["title"]
EXPECTED_MOVIE_NAME = PurePosixPath(PLAN["output"]["path"]).name


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not read {label}: {exc}") from exc


def main() -> int:
    catalog_path = ROOT / "final" / "backup-catalog.json"
    catalog = read_json(catalog_path, "final backup catalog")
    if not isinstance(catalog, dict) or not isinstance(catalog.get("works"), list):
        raise RuntimeError("final backup catalog does not contain a works list")
    works = [entry for entry in catalog["works"] if isinstance(entry, dict) and entry.get("id") == WORK_ID]
    if len(works) != 1:
        raise RuntimeError(f"Expected exactly one {WORK_ID} entry in the current backup catalog")
    work = works[0]
    if work.get("title") != "Final 成片备份 · " + WORK_TITLE:
        raise RuntimeError("Catalogued EP18 v04 final title does not match")
    assets = work.get("assets")
    if not isinstance(assets, list) or len(assets) != 1:
        raise RuntimeError("v04 restore probe is scoped to exactly one final asset")
    asset = assets[0]
    if not isinstance(asset, dict) or asset.get("kind") != "video" or asset.get("platform") != "小红书":
        raise RuntimeError("The v04 restore asset must be its Xiaohongshu final video")

    relative_asset = asset.get("path")
    posix_asset = PurePosixPath(relative_asset) if isinstance(relative_asset, str) else None
    expected_prefix = PurePosixPath("final") / WORK_ID / "小红书"
    if (
        posix_asset is None
        or posix_asset.is_absolute()
        or ".." in posix_asset.parts
        or posix_asset.parent != expected_prefix
        or posix_asset.name != EXPECTED_MOVIE_NAME
    ):
        raise RuntimeError("Catalog asset path is outside the exact v04 Xiaohongshu final path")
    if not isinstance(asset.get("sha256"), str) or not re.fullmatch(r"[0-9a-fA-F]{64}", asset["sha256"]):
        raise RuntimeError("Catalog asset does not contain a valid SHA-256")
    if not isinstance(asset.get("bytes"), int) or asset["bytes"] <= 0:
        raise RuntimeError("Catalog asset does not contain a positive byte count")
    release_tag = work.get("release_tag")
    if not isinstance(release_tag, str) or not release_tag:
        raise RuntimeError("Catalog v04 entry has no release tag")

    delivery_path = WORK / "delivery.json"
    delivery = read_json(delivery_path, "v04 delivery manifest")
    if not isinstance(delivery, dict) or delivery.get("title") != WORK_TITLE or delivery.get("slug") != WORK_ID:
        raise RuntimeError("delivery.json identity does not match the v04 restore probe")
    if delivery.get("platforms") != ["xiaohongshu"] or delivery.get("duration_seconds") != 90 or delivery.get("fps") != 60 or delivery.get("total_frames") != 5400:
        raise RuntimeError("delivery.json is not the v04 native 90-second Xiaohongshu delivery")
    outputs = delivery.get("outputs")
    xhs = outputs.get("xiaohongshu") if isinstance(outputs, dict) else None
    movie_path = xhs.get("path") if isinstance(xhs, dict) else None
    movie_relative = PurePosixPath(movie_path) if isinstance(movie_path, str) else None
    if (
        movie_relative is None
        or movie_relative.is_absolute()
        or ".." in movie_relative.parts
        or movie_relative.parts != ("小红书", EXPECTED_MOVIE_NAME)
    ):
        raise RuntimeError("delivery.json does not point to the expected v04 final movie")
    expected_sha = delivery.get("final_movie_sha256")
    if not isinstance(expected_sha, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha):
        raise RuntimeError("delivery.json final_movie_sha256 is not ready")
    if asset["sha256"].lower() != expected_sha.lower():
        raise RuntimeError("Backup catalog movie hash does not match delivery.json")
    local_movie = WORK.joinpath(*movie_relative.parts)
    if not local_movie.is_file() or sha256_file(local_movie).lower() != expected_sha.lower():
        raise RuntimeError("The actual local v04 final movie must exist and match delivery.json before restore probing")

    temp_value = os.environ.get("TMPDIR")
    if not temp_value:
        raise RuntimeError("TMPDIR must point to the verified AgentDev temporary directory")
    temp_root = Path(temp_value).resolve(strict=True)
    agent_dev = Path("/Volumes/AgentDev").resolve(strict=True)
    if not temp_root.is_relative_to(agent_dev) or not temp_root.is_dir():
        raise RuntimeError("TMPDIR must be an available directory on the verified AgentDev volume")

    downloader = ROOT / "scripts" / "fetch-archive-assets.py"
    if not downloader.is_file():
        raise RuntimeError("Repository final-asset restore utility is unavailable")
    probe_root: Path | None = None
    first_summary = ""
    second_summary = ""
    restored_bytes = 0
    restored_sha256 = ""
    repeat_preserved_file_identity = False
    with tempfile.TemporaryDirectory(prefix=WORK_ID + "-final-restore-", dir=temp_root) as name:
        isolation = Path(name)
        probe_root = isolation
        probe_catalog = isolation / "probe-catalog.json"
        probe_catalog.write_text(
            json.dumps({**catalog, "works": [work]}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        argv = ["python3", str(downloader), "--root", str(isolation), "--catalog", str(probe_catalog), "--download"]
        first = subprocess.run(argv, check=True, capture_output=True, text=True)
        restored = isolation.joinpath(*posix_asset.parts)
        if not restored.is_file():
            raise RuntimeError("The catalogued v04 movie was not restored")
        first_stat = restored.stat()
        restored_sha256 = sha256_file(restored)
        if first_stat.st_size != asset["bytes"] or restored_sha256.lower() != asset["sha256"].lower():
            raise RuntimeError("Restored v04 movie failed byte-count or SHA-256 verification")
        first_summary = next((line.strip() for line in first.stdout.splitlines() if line.startswith("Restore complete:")), "")
        if first_summary != "Restore complete: 0 already verified, 1 downloaded":
            raise RuntimeError("First restore did not download exactly one v04 asset")

        second = subprocess.run(argv, check=True, capture_output=True, text=True)
        second_stat = restored.stat()
        second_sha = sha256_file(restored)
        second_summary = next((line.strip() for line in second.stdout.splitlines() if line.startswith("Restore complete:")), "")
        repeat_preserved_file_identity = first_stat.st_ino == second_stat.st_ino
        if second_summary != "Restore complete: 1 already verified, 0 downloaded":
            raise RuntimeError("Second restore did not skip exactly the matching v04 asset")
        if second_sha.lower() != asset["sha256"].lower() or not repeat_preserved_file_identity:
            raise RuntimeError("Repeat restore changed the verified v04 movie")
        restored_bytes = second_stat.st_size

    if probe_root is None or probe_root.exists():
        raise RuntimeError("Isolated restore directory was not cleaned after verification")
    report_path = WORK / "review" / "final-restore-probe.json"
    if report_path.exists():
        raise FileExistsError("Refusing to overwrite existing final-restore-probe.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "schemaVersion": 1,
        "status": "PASS",
        "scope": "Only the single EP18 v04 Xiaohongshu final catalog asset was restored; no claim that historical movies were restored.",
        "workId": WORK_ID,
        "workTitle": WORK_TITLE,
        "deliveryFinalMovieSha256": expected_sha,
        "catalogSha256": sha256_file(catalog_path),
        "releaseTag": release_tag,
        "assetName": asset.get("name"),
        "restoredRelativePath": relative_asset,
        "bytes": restored_bytes,
        "sha256": restored_sha256,
        "firstRunSummary": first_summary,
        "secondRunSummary": second_summary,
        "secondRunSkippedMatchingFile": True,
        "repeatPreservedFileIdentity": repeat_preserved_file_identity,
        "isolatedTemporaryDirectoryCleanedAfterVerification": True,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("status", "workId", "releaseTag", "bytes", "sha256", "secondRunSkippedMatchingFile")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"restore_probe: {exc}")
