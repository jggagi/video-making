"""Restore only EP17's new final Release asset into an isolated AgentDev directory."""

from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile


PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT.parent
ROOT = WORK.parents[1]
WORK_ID = "si-ep17-godel-ouroboros"
WORK_TITLE = "啃食尾巴的神"


def sha256_file(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


catalog_path = ROOT / "final" / "backup-catalog.json"
full_catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
matches = [work for work in full_catalog["works"] if work.get("id") == WORK_ID]
assert len(matches) == 1, f"Expected exactly one {WORK_ID!r} work in final backup catalog"
work = matches[0]
assert WORK_TITLE in work.get("title", ""), f"Unexpected EP17 catalog title: {work.get('title')!r}"
assert len(work["assets"]) == 1, "EP17 final probe is scoped to exactly one asset"
asset = work["assets"][0]
assert asset.get("kind") == "video" and asset.get("platform") == "小红书", (
    "The single EP17 final asset must be the Xiaohongshu video"
)
assert f"final/{WORK_ID}/小红书/" in asset.get("path", ""), (
    f"The catalog asset is outside EP17's local final path: {asset.get('path')!r}"
)

delivery = json.loads((WORK / "delivery.json").read_text(encoding="utf-8"))
assert delivery.get("title") == WORK_TITLE, "EP17 delivery title does not match the restore probe"
expected_movie_sha256 = delivery.get("final_movie_sha256")
assert isinstance(expected_movie_sha256, str) and len(expected_movie_sha256) == 64, (
    "delivery.json final_movie_sha256 is not ready"
)
assert asset["sha256"].lower() == expected_movie_sha256.lower(), (
    "EP17 final catalog asset SHA-256 does not match delivery.json final_movie_sha256"
)

tmp = Path(os.environ["TMPDIR"]).resolve()
assert str(tmp).startswith("/Volumes/AgentDev/"), f"TMPDIR must be on AgentDev, got {tmp}"
probe_root: Path | None = None
with tempfile.TemporaryDirectory(prefix="si-ep17-final-restore-", dir=tmp) as name:
    isolation = Path(name)
    probe_root = isolation
    probe_catalog = isolation / "probe-catalog.json"
    probe_catalog.write_text(
        json.dumps({**full_catalog, "works": [work]}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    downloader = ROOT / "scripts" / "fetch-archive-assets.py"
    argv = [
        "python3",
        str(downloader),
        "--root", str(isolation),
        "--catalog", str(probe_catalog),
        "--download",
    ]
    first_run_stdout = subprocess.check_output(argv, text=True)
    restored = isolation / asset["path"]
    assert restored.is_file(), "The catalogued EP17 final asset was not restored"
    assert restored.stat().st_size == asset["bytes"] and sha256_file(restored) == asset["sha256"], (
        "Restored EP17 asset failed exact byte-count or SHA-256 verification"
    )

    original_identity = restored.stat()
    second_run_stdout = subprocess.check_output(argv, text=True)
    repeated_identity = restored.stat()
    assert "1 already verified, 0 downloaded" in second_run_stdout, (
        "The repeat restore did not report one matching asset skipped"
    )
    assert sha256_file(restored) == asset["sha256"], "The repeated restore changed the verified asset"
    assert original_identity.st_ino == repeated_identity.st_ino, (
        "The repeat restore replaced the already verified file"
    )
    restored_sha256 = sha256_file(restored)
    restored_byte_count = repeated_identity.st_size

assert probe_root is not None and not probe_root.exists(), "The isolated restore directory was not cleaned up"
report = {
    "status": "PASS",
    "scope": "Only the single EP17 portrait final catalog asset was restored; no claim that historical movies were restored.",
    "work_id": WORK_ID,
    "work_title": work["title"],
    "delivery_title": delivery["title"],
    "delivery_final_movie_sha256": expected_movie_sha256,
    "catalog_sha256": sha256_file(catalog_path),
    "release_tag": work["release_tag"],
    "asset_name": asset["name"],
    "restored_relative_path": asset["path"],
    "bytes": restored_byte_count,
    "sha256": restored_sha256,
    "first_run_stdout": first_run_stdout.strip(),
    "second_run_stdout": second_run_stdout.strip(),
    "second_run_skipped_matching_file": True,
    "repeat_preserved_file_inode": True,
    "isolated_temporary_directory_cleaned_after_verification": True,
}
(WORK / "review" / "final-restore-probe.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
print(json.dumps({
    key: report[key]
    for key in ("status", "work_id", "release_tag", "bytes", "sha256", "second_run_skipped_matching_file")
}, ensure_ascii=False, indent=2))
