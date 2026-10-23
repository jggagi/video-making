#!/usr/bin/env python3
"""Restore-probe only EP18's new final Release asset into an isolated AgentDev directory."""

from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile

PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT.parent
ROOT = WORK.parents[1]
WORK_ID = "si-ep18-sovereign-subcurrent-v02"
WORK_TITLE = "心印潜流 · v02"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

catalog_path = ROOT / "final" / "backup-catalog.json"
full_catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
works = [entry for entry in full_catalog["works"] if entry.get("id") == WORK_ID]
assert len(works) == 1, "Expected exactly one EP18 work in final backup catalog"
work = works[0]
assert work.get("title") == "Final 成片备份 · " + WORK_TITLE, "Unexpected EP18 final catalog title"
assert len(work.get("assets", [])) == 1, "EP18 final restore probe is scoped to exactly one asset"
asset = work["assets"][0]
assert asset.get("kind") == "video" and asset.get("platform") == "小红书", "The EP18 asset must be its Xiaohongshu final movie"
assert "final/" + WORK_ID + "/小红书/" in asset.get("path", ""), "Catalog asset is outside EP18's local final path"

delivery = json.loads((WORK / "delivery.json").read_text(encoding="utf-8"))
assert delivery.get("title") == WORK_TITLE and delivery.get("slug") == WORK_ID, "EP18 delivery identity does not match the restore probe"
expected_movie_sha256 = delivery.get("final_movie_sha256")
assert isinstance(expected_movie_sha256, str) and len(expected_movie_sha256) == 64, "delivery.json final_movie_sha256 is not ready"
assert asset.get("sha256", "").lower() == expected_movie_sha256.lower(), "Catalog movie hash does not match delivery.json"

tmp = Path(os.environ["TMPDIR"]).resolve()
assert str(tmp).startswith("/Volumes/AgentDev/"), "TMPDIR must be on the verified AgentDev volume"
probe_root: Path | None = None
with tempfile.TemporaryDirectory(prefix="si-ep18-sovereign-subcurrent-v02-final-restore-", dir=tmp) as name:
    isolation = Path(name)
    probe_root = isolation
    probe_catalog = isolation / "probe-catalog.json"
    probe_catalog.write_text(json.dumps({**full_catalog, "works": [work]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    downloader = ROOT / "scripts" / "fetch-archive-assets.py"
    argv = ["python3", str(downloader), "--root", str(isolation), "--catalog", str(probe_catalog), "--download"]
    first_run_stdout = subprocess.check_output(argv, text=True)
    restored = isolation / asset["path"]
    assert restored.is_file(), "The catalogued EP18 movie was not restored"
    assert restored.stat().st_size == asset["bytes"] and sha256_file(restored) == asset["sha256"], "Restored EP18 movie failed byte-count or SHA-256 verification"
    original_identity = restored.stat()
    second_run_stdout = subprocess.check_output(argv, text=True)
    repeated_identity = restored.stat()
    assert "1 already verified, 0 downloaded" in second_run_stdout, "Repeat restore did not skip the matching asset"
    assert sha256_file(restored) == asset["sha256"] and original_identity.st_ino == repeated_identity.st_ino, "Repeat restore changed the verified file"
    restored_sha256 = sha256_file(restored)
    restored_byte_count = repeated_identity.st_size

assert probe_root is not None and not probe_root.exists(), "Isolated restore directory was not cleaned"
report_path = WORK / "review" / "final-restore-probe.json"
assert not report_path.exists(), "Refusing to overwrite existing final restore probe"
report = {
    "status": "PASS",
    "scope": "Only the single EP18 portrait final catalog asset was restored; no claim that historical movies were restored.",
    "workId": WORK_ID,
    "workTitle": work["title"],
    "deliveryTitle": delivery["title"],
    "deliveryFinalMovieSha256": expected_movie_sha256,
    "catalogSha256": sha256_file(catalog_path),
    "releaseTag": work["release_tag"],
    "assetName": asset["name"],
    "restoredRelativePath": asset["path"],
    "bytes": restored_byte_count,
    "sha256": restored_sha256,
    "firstRunStdout": first_run_stdout.strip(),
    "secondRunStdout": second_run_stdout.strip(),
    "secondRunSkippedMatchingFile": True,
    "repeatPreservedFileInode": True,
    "isolatedTemporaryDirectoryCleanedAfterVerification": True,
}
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: report[key] for key in ("status", "workId", "releaseTag", "bytes", "sha256", "secondRunSkippedMatchingFile")}, ensure_ascii=False, indent=2))
