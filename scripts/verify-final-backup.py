#!/usr/bin/env python3
"""Verify local final assets against published GitHub Releases, read-only.

The report is written atomically only after every local file, upload receipt,
release, and remote asset matches the current catalog. GitHub response bodies
are parsed in memory; only the established sanitized verification fields are
written to the report.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import subprocess
import sys
import tempfile
from typing import Any
from urllib.parse import quote


REPOSITORY = "jggagi/video-making"
DEFAULT_CATALOG = Path("final/backup-catalog.json")
DEFAULT_OUTPUT = Path("final/backup-verification.json")
FULL_COMMIT = re.compile(r"^[0-9a-fA-F]{40}$")
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
SAFE_TAG = re.compile(r"^[A-Za-z0-9._-]+$")
CHUNK_SIZE = 1024 * 1024
MAX_ASSET_BYTES = 2 * 1024**3
KINDS = {"video", "project"}
PLATFORMS = {"B站", "小红书", "工程", "预览"}
VERIFICATION_METHOD = (
    "Fresh published GitHub Release API inventory plus all local final file hashes; "
    "every remote size, SHA-256 digest and URL matched the current catalog."
)
RESTORE_PROBE = {
    "status": "NOT_RUN",
    "note": (
        "Fresh remote/local inventory verification only; root must run this new work "
        "restore probe and update this field separately."
    ),
}


class VerificationError(ValueError):
    """A concise error that does not reveal raw API output or credentials."""


def parse_source_commit(value: str) -> str:
    if not FULL_COMMIT.fullmatch(value):
        raise argparse.ArgumentTypeError("must be a full 40-character hexadecimal commit SHA")
    return value.lower()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only verification of local final files and published final-* Releases."
    )
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG,
                        help="Final backup catalog path, relative to --root (default: final/backup-catalog.json).")
    parser.add_argument("--root", type=Path, default=Path("."),
                        help="Repository root containing catalog assets (default: .).")
    parser.add_argument("--source-commit", required=True, type=parse_source_commit,
                        help="Full 40-character source commit recorded by the upload receipt.")
    parser.add_argument("--receipt", required=True, type=Path,
                        help="Completed upload receipt path, relative to --root unless absolute.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="Verification report path, relative to --root (default: final/backup-verification.json).")
    return parser.parse_args()


def safe_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VerificationError(f"{label} must be non-empty text.")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise VerificationError(f"{label} must not contain control characters.")
    return value


def confined_path(root: Path, requested: Path, label: str, *, must_exist: bool) -> Path:
    candidate = requested.expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve(strict=must_exist)
        resolved.relative_to(root)
    except (OSError, ValueError):
        raise VerificationError(f"{label} is missing or resolves outside --root.") from None
    if must_exist and not resolved.is_file():
        raise VerificationError(f"{label} must be a regular file.")
    return resolved


def catalog_asset_path(root: Path, relative: Any, label: str) -> tuple[str, Path]:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise VerificationError(f"{label}.path must be a relative POSIX path.")
    posix = PurePosixPath(relative)
    windows = PureWindowsPath(relative)
    parts = relative.split("/")
    if (posix.is_absolute() or windows.is_absolute() or windows.drive
            or any(part in {"", ".", ".."} for part in parts)
            or any(ord(char) < 32 or ord(char) == 127 for char in relative)):
        raise VerificationError(f"{label}.path must stay inside --root and contain no traversal components.")
    path = confined_path(root, Path(*parts), f"{label}.path", must_exist=True)
    return relative, path


def read_json(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw_bytes = path.read_bytes()
        value = json.loads(raw_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise VerificationError(f"Cannot read {label} as UTF-8 JSON.") from None
    if not isinstance(value, dict):
        raise VerificationError(f"{label} must contain a JSON object.")
    return value, raw_bytes


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_and_size(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(CHUNK_SIZE), b""):
                size += len(chunk)
                digest.update(chunk)
    except OSError:
        raise VerificationError(f"Cannot read local final asset: {path.name}") from None
    return digest.hexdigest(), size


def validate_catalog(data: dict[str, Any], root: Path) -> tuple[list[dict[str, Any]], int]:
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise VerificationError("Catalog schema_version must be 1.")
    if data.get("repository") != REPOSITORY:
        raise VerificationError(f"Catalog repository must be exactly {REPOSITORY}.")
    raw_works = data.get("works")
    if not isinstance(raw_works, list) or not raw_works:
        raise VerificationError("Catalog works must be a non-empty array.")

    seen_ids: set[str] = set()
    seen_tags: set[str] = set()
    works: list[dict[str, Any]] = []
    total_bytes = 0
    for wi, raw_work in enumerate(raw_works):
        label = f"works[{wi}]"
        if not isinstance(raw_work, dict):
            raise VerificationError(f"{label} must be an object.")
        work_id = safe_text(raw_work.get("id"), f"{label}.id")
        title = safe_text(raw_work.get("title"), f"{label}.title")
        tag = safe_text(raw_work.get("release_tag"), f"{label}.release_tag")
        if not tag.startswith("final-") or not SAFE_TAG.fullmatch(tag):
            raise VerificationError(f"{label}.release_tag must be a safe final-* release tag.")
        if work_id in seen_ids or tag in seen_tags:
            raise VerificationError(f"Catalog work id or release tag is duplicated at {label}.")
        seen_ids.add(work_id)
        seen_tags.add(tag)

        raw_assets = raw_work.get("assets")
        if not isinstance(raw_assets, list) or not raw_assets:
            raise VerificationError(f"{label}.assets must be a non-empty array.")
        assets: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        for ai, raw_asset in enumerate(raw_assets):
            asset_label = f"{label}.assets[{ai}]"
            if not isinstance(raw_asset, dict):
                raise VerificationError(f"{asset_label} must be an object.")
            relative, path = catalog_asset_path(root, raw_asset.get("path"), asset_label)
            name = safe_text(raw_asset.get("name"), f"{asset_label}.name")
            if name in {".", ".."} or "/" in name or "\\" in name:
                raise VerificationError(f"{asset_label}.name must be one release filename.")
            if name in seen_names:
                raise VerificationError(f"Release asset name is duplicated in {tag}.")
            seen_names.add(name)
            expected_bytes = raw_asset.get("bytes")
            if type(expected_bytes) is not int or not 0 < expected_bytes < MAX_ASSET_BYTES:
                raise VerificationError(f"{asset_label}.bytes must be positive and below 2 GiB.")
            expected_hash = raw_asset.get("sha256")
            if not isinstance(expected_hash, str) or not HEX_SHA256.fullmatch(expected_hash):
                raise VerificationError(f"{asset_label}.sha256 must be lowercase SHA-256 hex.")
            expected_url = safe_text(raw_asset.get("download_url"), f"{asset_label}.download_url")
            if raw_asset.get("kind") not in KINDS:
                raise VerificationError(f"{asset_label}.kind must be video or project.")
            if raw_asset.get("platform") not in PLATFORMS:
                raise VerificationError(f"{asset_label}.platform is invalid.")

            actual_hash, actual_bytes = sha256_and_size(path)
            if actual_bytes != expected_bytes:
                raise VerificationError(f"Local asset size does not match the catalog: {relative}.")
            if actual_hash != expected_hash:
                raise VerificationError(f"Local asset SHA-256 does not match the catalog: {relative}.")
            total_bytes += actual_bytes
            assets.append({
                "path": relative,
                "local_path": path,
                "name": name,
                "bytes": expected_bytes,
                "sha256": expected_hash,
                "kind": raw_asset["kind"],
                "platform": raw_asset["platform"],
                "download_url": expected_url,
            })
        works.append({"id": work_id, "title": title, "release_tag": tag, "assets": assets})
    return works, total_bytes


def validate_receipt(data: dict[str, Any], works: list[dict[str, Any]], source_commit: str) -> None:
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise VerificationError("Upload receipt schema_version must be 1.")
    if data.get("repository") != REPOSITORY:
        raise VerificationError(f"Upload receipt repository must be exactly {REPOSITORY}.")
    target = data.get("target")
    if not isinstance(target, str) or not FULL_COMMIT.fullmatch(target) or target.lower() != source_commit:
        raise VerificationError("Upload receipt target does not match --source-commit.")
    if data.get("status") != "COMPLETE":
        raise VerificationError("Upload receipt status must be COMPLETE.")
    raw_works = data.get("works")
    if not isinstance(raw_works, list) or len(raw_works) != len(works):
        raise VerificationError("Upload receipt work inventory does not match the catalog.")
    receipt_by_id: dict[str, dict[str, Any]] = {}
    for item in raw_works:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise VerificationError("Upload receipt contains an invalid work record.")
        if item["id"] in receipt_by_id:
            raise VerificationError("Upload receipt contains a duplicate work id.")
        receipt_by_id[item["id"]] = item

    for work in works:
        receipt_work = receipt_by_id.get(work["id"])
        if receipt_work is None or receipt_work.get("release_tag") != work["release_tag"]:
            raise VerificationError(f"Upload receipt work does not match the catalog: {work['id']}.")
        if receipt_work.get("title") != work["title"] or receipt_work.get("release_draft") is not False:
            raise VerificationError(f"Upload receipt release is incomplete: {work['release_tag']}.")
        expected_release_url = f"https://github.com/{REPOSITORY}/releases/tag/{quote(work['release_tag'], safe='')}"
        if receipt_work.get("release_url") != expected_release_url:
            raise VerificationError(f"Upload receipt release URL is invalid: {work['release_tag']}.")
        raw_assets = receipt_work.get("assets")
        if not isinstance(raw_assets, list) or len(raw_assets) != len(work["assets"]):
            raise VerificationError(f"Upload receipt asset inventory is incomplete: {work['release_tag']}.")
        receipt_assets: dict[str, dict[str, Any]] = {}
        for asset in raw_assets:
            if not isinstance(asset, dict) or not isinstance(asset.get("name"), str):
                raise VerificationError(f"Upload receipt contains an invalid asset in {work['release_tag']}.")
            if asset["name"] in receipt_assets:
                raise VerificationError(f"Upload receipt contains a duplicate asset in {work['release_tag']}.")
            receipt_assets[asset["name"]] = asset
        for asset in work["assets"]:
            receipt_asset = receipt_assets.get(asset["name"])
            if receipt_asset is None:
                raise VerificationError(f"Upload receipt is missing an asset in {work['release_tag']}.")
            if (type(receipt_asset.get("bytes")) is not int or receipt_asset["bytes"] != asset["bytes"]
                    or receipt_asset.get("digest") != f"sha256:{asset['sha256']}"
                    or receipt_asset.get("kind") != asset["kind"]
                    or receipt_asset.get("platform") != asset["platform"]
                    or receipt_asset.get("download_url") != asset["download_url"]
                    or receipt_asset.get("browser_download_url") != asset["download_url"]
                    or type(receipt_asset.get("id")) is not int or receipt_asset["id"] <= 0):
                raise VerificationError(f"Upload receipt asset does not match the catalog: {asset['name']}.")


def run_release_api(tag: str) -> dict[str, Any]:
    endpoint = f"repos/{REPOSITORY}/releases/tags/{tag}"
    try:
        result = subprocess.run(
            ["gh", "api", endpoint],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        raise VerificationError("Could not execute GitHub CLI (gh).") from None
    if result.returncode != 0:
        raise VerificationError(f"Fresh GitHub release lookup failed for {tag} (gh exit {result.returncode}).")
    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise VerificationError(f"Fresh GitHub release lookup returned invalid JSON for {tag}.") from None
    if not isinstance(response, dict):
        raise VerificationError(f"Fresh GitHub release lookup returned an unexpected response for {tag}.")
    return response


def verify_remote_release(work: dict[str, Any], source_commit: str) -> dict[str, Any]:
    tag = work["release_tag"]
    release = run_release_api(tag)
    if release.get("tag_name") != tag:
        raise VerificationError(f"GitHub returned a different release tag for {tag}.")
    if release.get("draft") is not False:
        raise VerificationError(f"Release {tag} is missing or still a draft.")
    if type(release.get("id")) is not int or release["id"] <= 0:
        raise VerificationError(f"GitHub release metadata is incomplete for {tag}.")
    expected_release_url = f"https://github.com/{REPOSITORY}/releases/tag/{quote(tag, safe='')}"
    if release.get("html_url") != expected_release_url:
        raise VerificationError(f"Published release URL does not match the expected URL for {tag}.")
    raw_assets = release.get("assets")
    if not isinstance(raw_assets, list):
        raise VerificationError(f"Published release asset list is missing for {tag}.")
    remote_by_name: dict[str, dict[str, Any]] = {}
    for remote in raw_assets:
        if not isinstance(remote, dict) or not isinstance(remote.get("name"), str):
            raise VerificationError(f"Published release contains an invalid asset record for {tag}.")
        name = remote["name"]
        if name in remote_by_name:
            raise VerificationError(f"Published release contains a duplicate asset name for {tag}.")
        remote_by_name[name] = remote
    expected_names = {asset["name"] for asset in work["assets"]}
    if set(remote_by_name) != expected_names:
        raise VerificationError(f"Published release asset-name set differs from the catalog for {tag}.")

    verified_assets: list[dict[str, Any]] = []
    for asset in work["assets"]:
        remote = remote_by_name[asset["name"]]
        if type(remote.get("size")) is not int or remote["size"] != asset["bytes"]:
            raise VerificationError(f"Published asset size differs from local bytes for {asset['name']}.")
        expected_digest = f"sha256:{asset['sha256']}"
        if remote.get("digest") != expected_digest:
            raise VerificationError(f"Published asset SHA-256 differs from local bytes for {asset['name']}.")
        if remote.get("browser_download_url") != asset["download_url"]:
            raise VerificationError(f"Published asset URL differs from the catalog for {asset['name']}.")
        if type(remote.get("id")) is not int or remote["id"] <= 0:
            raise VerificationError(f"Published asset ID is missing for {asset['name']}.")
        verified_assets.append({
            "path": asset["path"],
            "name": asset["name"],
            "bytes": asset["bytes"],
            "sha256": asset["sha256"],
            "github_digest": expected_digest,
            "github_asset_id": remote["id"],
            "download_url": asset["download_url"],
            "local_and_remote_match": True,
        })

    return {
        "id": work["id"],
        "title": work["title"],
        "release_tag": tag,
        "release_url": expected_release_url,
        "release_target": release.get("target_commitish"),
        "release_draft": False,
        "assets": verified_assets,
    }


def atomic_write_report(path: Path, report: dict[str, Any]) -> None:
    if path.is_symlink():
        raise VerificationError("Output path must not be a symlink.")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if path.is_symlink():
                raise VerificationError("Output path became a symlink before publication.")
            os.replace(temp_path, path)
        finally:
            temp_path.unlink(missing_ok=True)
    except VerificationError:
        raise
    except OSError:
        raise VerificationError("Could not atomically write the verification report.") from None


def main() -> int:
    args = parse_args()
    try:
        root = args.root.expanduser().resolve(strict=True)
        if not root.is_dir():
            raise VerificationError("--root must be an existing directory.")
        catalog_path = confined_path(root, args.catalog, "--catalog", must_exist=True)
        receipt_path = confined_path(root, args.receipt, "--receipt", must_exist=True)
        requested_output = args.output.expanduser()
        if not requested_output.is_absolute():
            requested_output = root / requested_output
        if requested_output.is_symlink():
            raise VerificationError("--output must not be a symlink.")
        output_path = confined_path(root, args.output, "--output", must_exist=False)
        if output_path in {catalog_path, receipt_path}:
            raise VerificationError("--output must not replace the catalog or upload receipt.")
        if output_path.is_symlink():
            raise VerificationError("--output must not be a symlink.")

        catalog, catalog_bytes = read_json(catalog_path, "catalog")
        works, total_bytes = validate_catalog(catalog, root)
        receipt, receipt_bytes = read_json(receipt_path, "upload receipt")
        validate_receipt(receipt, works, args.source_commit)
        catalog_hash = sha256_bytes(catalog_bytes)
        receipt_hash = sha256_bytes(receipt_bytes)

        verified_works = [verify_remote_release(work, args.source_commit) for work in works]

        # Guard against catalog or receipt replacement while the fresh API reads ran.
        if sha256_bytes(catalog_path.read_bytes()) != catalog_hash:
            raise VerificationError("Catalog changed during remote verification; prior report was preserved.")
        if sha256_bytes(receipt_path.read_bytes()) != receipt_hash:
            raise VerificationError("Upload receipt changed during remote verification; prior report was preserved.")

        verified_files = sum(len(work["assets"]) for work in verified_works)
        report = {
            "schema_version": 1,
            "status": "COMPLETE",
            "verified_at_utc": datetime.now(timezone.utc).isoformat(),
            "repository": REPOSITORY,
            "source_commit": args.source_commit,
            "catalog_path": catalog_path.relative_to(root).as_posix(),
            "catalog_sha256": catalog_hash,
            "upload_receipt_sha256": receipt_hash,
            "verification_method": VERIFICATION_METHOD,
            "verified_releases": len(verified_works),
            "verified_files": verified_files,
            "verified_bytes": total_bytes,
            "works": verified_works,
            "restore_probe": RESTORE_PROBE,
        }
        atomic_write_report(output_path, report)
        print(
            f"COMPLETE: verified {verified_files} local and published asset(s) across "
            f"{len(verified_works)} release(s); report written to {output_path.relative_to(root).as_posix()}."
        )
        return 0
    except VerificationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OSError:
        print("ERROR: Local I/O failed; prior verification report was preserved.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
