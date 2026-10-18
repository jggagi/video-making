#!/usr/bin/env python3
"""Validate and resumably upload archived assets to GitHub draft releases."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any
from urllib.parse import quote


REPOSITORY = "jggagi/video-making"
MAX_ASSET_BYTES = 2 * 1024**3
KINDS = {"video", "project"}
PLATFORMS = {"B站", "小红书", "工程", "预览"}
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
FULL_COMMIT = re.compile(r"^[0-9a-fA-F]{40}$")


class UploadError(ValueError):
    """A safe, concise error suitable for display and receipt storage."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate or resumably upload a release asset catalog."
    )
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--apply", action="store_true", help="Perform GitHub release changes.")
    parser.add_argument("--target", help="Full 40-character commit SHA for newly created releases.")
    parser.add_argument("--receipt", type=Path, help="Receipt path, relative to --root unless absolute.")
    args = parser.parse_args()
    if args.apply and (not args.target or not FULL_COMMIT.fullmatch(args.target)):
        parser.error("--apply requires --target with a full 40-character commit SHA")
    if not args.apply and args.target:
        parser.error("--target is only valid with --apply")
    return args


def nonempty_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise UploadError(f"{label} must be non-empty text.")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise UploadError(f"{label} must not contain control characters.")
    return value


def safe_relative_path(raw: Any, label: str) -> tuple[str, ...]:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise UploadError(f"{label} must be a non-empty relative POSIX path.")
    posix = PurePosixPath(raw)
    windows = PureWindowsPath(raw)
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        raise UploadError(f"{label} must be relative to --root.")
    parts = raw.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise UploadError(f"{label} must not contain empty, dot, or traversal components.")
    if any(any(ord(char) < 32 or ord(char) == 127 for char in part) for part in parts):
        raise UploadError(f"{label} must not contain control characters.")
    return tuple(parts)


def confined_path(root: Path, raw: Any, label: str, *, must_exist: bool) -> Path:
    parts = safe_relative_path(raw, label)
    candidate = root.joinpath(*parts)
    try:
        resolved = candidate.resolve(strict=must_exist)
        resolved.relative_to(root)
    except (OSError, ValueError):
        raise UploadError(f"{label} is missing or resolves outside --root.") from None
    return resolved


def sha256_and_size(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                size += len(chunk)
                digest.update(chunk)
    except OSError:
        raise UploadError(f"Cannot read local asset: {path.name}") from None
    return digest.hexdigest(), size


def load_and_validate_catalog(catalog_path: Path, root_arg: Path) -> tuple[Path, list[dict[str, Any]], int]:
    try:
        root = root_arg.expanduser().resolve(strict=True)
    except OSError:
        raise UploadError("--root must be an existing directory.") from None
    if not root.is_dir():
        raise UploadError("--root must be an existing directory.")

    try:
        raw = json.loads(catalog_path.expanduser().read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise UploadError("Cannot read --catalog as valid UTF-8 JSON.") from None
    if not isinstance(raw, dict) or type(raw.get("schema_version")) is not int or raw["schema_version"] != 1:
        raise UploadError("Catalog schema_version must be 1.")
    if raw.get("repository") != REPOSITORY:
        raise UploadError(f"Catalog repository must be exactly {REPOSITORY}.")
    works_raw = raw.get("works")
    if not isinstance(works_raw, list) or not works_raw:
        raise UploadError("Catalog works must be a non-empty array.")

    seen_ids: set[str] = set()
    seen_tags: set[str] = set()
    work_records: list[dict[str, Any]] = []
    total_bytes = 0
    for work_index, work_raw in enumerate(works_raw):
        label = f"works[{work_index}]"
        if not isinstance(work_raw, dict):
            raise UploadError(f"{label} must be an object.")
        work_id = nonempty_text(work_raw.get("id"), f"{label}.id")
        title = nonempty_text(work_raw.get("title"), f"{label}.title")
        tag = nonempty_text(work_raw.get("release_tag"), f"{label}.release_tag")
        if tag.startswith("-"):
            raise UploadError(f"{label}.release_tag must not begin with '-'.")
        if work_id in seen_ids:
            raise UploadError(f"Catalog work id is duplicated: {work_id}.")
        if tag in seen_tags:
            raise UploadError(f"Catalog release tag is duplicated: {tag}.")
        seen_ids.add(work_id)
        seen_tags.add(tag)

        assets_raw = work_raw.get("assets")
        if not isinstance(assets_raw, list) or not assets_raw:
            raise UploadError(f"{label}.assets must be a non-empty array.")
        seen_names: set[str] = set()
        assets: list[dict[str, Any]] = []
        for asset_index, asset_raw in enumerate(assets_raw):
            asset_label = f"{label}.assets[{asset_index}]"
            if not isinstance(asset_raw, dict):
                raise UploadError(f"{asset_label} must be an object.")
            relative = nonempty_text(asset_raw.get("path"), f"{asset_label}.path")
            path = confined_path(root, relative, f"{asset_label}.path", must_exist=True)
            if not path.is_file():
                raise UploadError(f"{asset_label}.path must resolve to a regular file.")
            name = nonempty_text(asset_raw.get("name"), f"{asset_label}.name")
            if name in {".", ".."} or "/" in name or "\\" in name:
                raise UploadError(f"{asset_label}.name must be one release filename.")
            if name in seen_names:
                raise UploadError(f"Release asset name is duplicated in {tag}: {name}.")
            seen_names.add(name)
            expected_size = asset_raw.get("bytes")
            if type(expected_size) is not int or not 0 < expected_size < MAX_ASSET_BYTES:
                raise UploadError(f"{asset_label}.bytes must be a positive integer below 2 GiB.")
            expected_hash = asset_raw.get("sha256")
            if not isinstance(expected_hash, str) or not HEX_SHA256.fullmatch(expected_hash):
                raise UploadError(f"{asset_label}.sha256 must be lowercase SHA-256 hex.")
            kind = asset_raw.get("kind")
            if not isinstance(kind, str) or kind not in KINDS:
                raise UploadError(f"{asset_label}.kind must be video or project.")
            platform = asset_raw.get("platform")
            if not isinstance(platform, str) or platform not in PLATFORMS:
                raise UploadError(f"{asset_label}.platform is invalid.")
            download_url = nonempty_text(asset_raw.get("download_url"), f"{asset_label}.download_url")

            actual_hash, actual_size = sha256_and_size(path)
            if actual_size != expected_size:
                raise UploadError(f"Local asset size does not match catalog: {relative}.")
            if actual_hash != expected_hash:
                raise UploadError(f"Local asset SHA-256 does not match catalog: {relative}.")
            if actual_size >= MAX_ASSET_BYTES:
                raise UploadError(f"Local asset must be smaller than 2 GiB: {relative}.")
            total_bytes += actual_size
            assets.append({
                "path": relative,
                "local_path": path,
                "name": name,
                "bytes": expected_size,
                "sha256": expected_hash,
                "kind": kind,
                "platform": platform,
                "download_url": download_url,
            })
        work_records.append({"id": work_id, "title": title, "release_tag": tag, "assets": assets})
    return root, work_records, total_bytes


def resolve_receipt(root: Path, requested: Path | None, target: str | None = None) -> Path:
    default_name = f"upload-receipt-{target[:12]}.json" if target else "upload-receipt.json"
    candidate = requested if requested is not None else Path("archive") / default_name
    if candidate.is_absolute():
        candidate = candidate.expanduser()
        try:
            result = candidate.resolve(strict=False)
            result.relative_to(root)
        except (OSError, ValueError):
            raise UploadError("--receipt must resolve inside --root.") from None
    else:
        parts = safe_relative_path(candidate.as_posix(), "--receipt")
        candidate = root.joinpath(*parts)
        try:
            resolved = candidate.resolve(strict=False)
            resolved.relative_to(root)
        except (OSError, ValueError):
            raise UploadError("--receipt must resolve inside --root.") from None
    if os.path.lexists(candidate) and (candidate.is_symlink() or not candidate.is_file()):
        raise UploadError("--receipt must be a regular file, not a symlink or directory.")
    return candidate


def check_existing_receipt(path: Path, target: str) -> None:
    if not path.exists():
        return
    try:
        prior = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise UploadError("Existing receipt is not readable schema-1 JSON; refusing to replace it.") from None
    if (not isinstance(prior, dict) or type(prior.get("schema_version")) is not int
            or prior.get("schema_version") != 1
            or prior.get("repository") != REPOSITORY or prior.get("target") != target):
        raise UploadError("Existing receipt belongs to a different repository or target; refusing to replace it.")


def write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if path.is_symlink():
                raise OSError("receipt became a symlink")
            os.replace(temp_path, path)
        finally:
            temp_path.unlink(missing_ok=True)
    except OSError:
        raise UploadError("Could not atomically update the upload receipt.") from None


def run_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["gh", *args], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", check=False,
        )
    except OSError:
        raise UploadError("Could not execute GitHub CLI.") from None


def endpoint(tag: str) -> str:
    return f"repos/{REPOSITORY}/releases/tags/{quote(tag, safe='')}"


def parse_json_output(result: subprocess.CompletedProcess[str], label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise UploadError(f"{label} returned invalid JSON.") from None
    if not isinstance(parsed, dict):
        raise UploadError(f"{label} returned an unexpected response.")
    return parsed


def is_not_found(result: subprocess.CompletedProcess[str]) -> bool:
    return bool(re.search(
        r"(?:HTTP\s+404\b|\b404\s+Not Found\b|\bNot Found\b.*\b404\b)",
        result.stderr + "\n" + result.stdout,
        re.IGNORECASE,
    ))


def get_release(tag: str) -> dict[str, Any] | None:
    result = run_gh(["api", endpoint(tag)])
    if result.returncode != 0:
        if not is_not_found(result):
            raise UploadError(f"Release lookup failed for tag {tag} (gh exit {result.returncode}).")
        # A newly-created draft can have tag_name but no published Git tag yet.
        # GitHub's by-tag endpoint returns404 for it; the authenticated release
        # collection includes drafts and lets a retry find the existing object.
        listed = run_gh(["api", f"repos/{REPOSITORY}/releases?per_page=100", "--paginate", "--slurp"])
        if listed.returncode != 0:
            raise UploadError(f"Draft release lookup failed for {tag} (gh exit {listed.returncode}).")
        try:
            pages = json.loads(listed.stdout)
            if not isinstance(pages, list) or any(not isinstance(page, list) for page in pages):
                raise ValueError("unexpected pagination shape")
            matches = [item for page in pages for item in page
                       if isinstance(item, dict) and item.get("tag_name") == tag]
        except (json.JSONDecodeError, ValueError):
            raise UploadError("Draft release lookup returned invalid paginated JSON.") from None
        if len(matches) > 1:
            raise UploadError(f"Multiple releases use tag {tag}; refusing to guess.")
        if not matches:
            return None
        release = matches[0]
    else:
        release = parse_json_output(result, "Release lookup")
    if type(release.get("id")) is not int or release["id"] <= 0:
        raise UploadError(f"Release lookup for tag {tag} returned no valid release id.")
    if release.get("tag_name") != tag:
        raise UploadError(f"Release lookup for tag {tag} returned a different tag.")
    if not isinstance(release.get("html_url"), str) or not release["html_url"]:
        raise UploadError(f"Release lookup for tag {tag} returned no release URL.")
    if not isinstance(release.get("draft"), bool) or not isinstance(release.get("assets"), list):
        raise UploadError(f"Release lookup for tag {tag} returned incomplete release metadata.")
    return release


def get_named_asset(release: dict[str, Any], name: str, tag: str) -> dict[str, Any] | None:
    matches = [asset for asset in release["assets"]
               if isinstance(asset, dict) and asset.get("name") == name]
    if len(matches) > 1:
        raise UploadError(f"Release {tag} contains duplicate assets named {name}.")
    return matches[0] if matches else None


def wait_for_release(tag: str, *, published: bool = False) -> dict[str, Any] | None:
    """Bounded reads for GitHub's brief create/publish visibility delay."""
    release = None
    for delay in (0, 1, 2, 4):
        if delay:
            time.sleep(delay)
        release = get_release(tag)
        if release is not None and (not published or not release["draft"]):
            return release
    return release


def verify_remote_asset(remote: dict[str, Any], asset: dict[str, Any], tag: str) -> None:
    expected_digest = f"sha256:{asset['sha256']}"
    if remote.get("size") != asset["bytes"] or remote.get("digest") != expected_digest:
        raise UploadError(
            f"Release asset conflict for {asset['name']} in {tag}; refusing to overwrite or skip it."
        )


def receipt_asset(remote: dict[str, Any], asset: dict[str, Any]) -> dict[str, Any]:
    result = {
        "name": remote.get("name"),
        "bytes": remote.get("size"),
        "digest": remote.get("digest"),
        "kind": asset["kind"],
        "platform": asset["platform"],
        "download_url": asset["download_url"],
        "browser_download_url": remote.get("browser_download_url"),
    }
    if type(remote.get("id")) is int:
        result["id"] = remote["id"]
    return result


def verify_release_inventory(release: dict[str, Any], work: dict[str, Any]) -> list[dict[str, Any]]:
    verified: list[dict[str, Any]] = []
    for asset in work["assets"]:
        remote = get_named_asset(release, asset["name"], work["release_tag"])
        if remote is None:
            raise UploadError(f"Final release inventory is missing {asset['name']} in {work['release_tag']}.")
        verify_remote_asset(remote, asset, work["release_tag"])
        verified.append(receipt_asset(remote, asset))
    return verified


def release_notes() -> str:
    return (
        "Film media and editable project archives for jggagi/video-making.\n\n"
        "See archive/catalog.json and the work directory for exact dimensions, durations, "
        "source paths and SHA-256 hashes. Historical editions retain their original "
        "specifications; uploading them does not imply new human or device acceptance.\n"
    )


def create_release(work: dict[str, Any], target: str) -> None:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".md") as notes:
        notes.write(release_notes())
        notes.flush()
        result = run_gh([
            "release", "create", work["release_tag"], "--repo", REPOSITORY,
            "--target", target, "--draft", "--title", work["title"],
            "--notes-file", notes.name, "--latest=false",
        ])
    if result.returncode != 0:
        raise UploadError(f"Could not create draft release for {work['release_tag']} (gh exit {result.returncode}).")


def upload_asset(release: dict[str, Any], work: dict[str, Any], asset: dict[str, Any]) -> dict[str, Any]:
    current_hash, current_size = sha256_and_size(asset["local_path"])
    if current_hash != asset["sha256"] or current_size != asset["bytes"]:
        raise UploadError(f"Local asset changed after preflight: {asset['path']}.")
    content_type = mimetypes.guess_type(asset["name"])[0] or "application/octet-stream"
    url = (
        "https://uploads.github.com/"
        f"repos/{REPOSITORY}/releases/{release['id']}/assets?name={quote(asset['name'], safe='')}"
    )
    result = run_gh([
        "api", "--method", "POST", url, "--input", str(asset["local_path"]),
        "-H", f"Content-Type: {content_type}",
    ])
    if result.returncode != 0:
        raise UploadError(f"Upload failed for {asset['name']} (gh exit {result.returncode}).")
    uploaded = parse_json_output(result, "Asset upload")
    if uploaded.get("name") != asset["name"]:
        raise UploadError(f"Upload response name did not match for {asset['name']}.")
    verify_remote_asset(uploaded, asset, work["release_tag"])
    return uploaded


def apply_upload(works: list[dict[str, Any]], target: str, receipt_path: Path) -> None:
    check_existing_receipt(receipt_path, target)
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "repository": REPOSITORY,
        "target": target,
        "status": "RUNNING",
        "works": [
            {"id": work["id"], "title": work["title"], "release_tag": work["release_tag"],
             "release_url": None, "assets": []}
            for work in works
        ],
    }
    write_receipt(receipt_path, receipt)
    try:
        if shutil.which("gh") is None:
            raise UploadError("GitHub CLI (gh) is not in PATH.")
        auth = run_gh(["auth", "status", "--hostname", "github.com"])
        if auth.returncode != 0:
            raise UploadError("GitHub CLI is not authenticated for github.com.")

        for index, work in enumerate(works):
            tag = work["release_tag"]
            release = get_release(tag)
            if release is None:
                create_release(work, target)
                release = wait_for_release(tag)
                if release is None:
                    raise UploadError(f"Created release {tag} could not be found afterward.")
            receipt_work = receipt["works"][index]
            receipt_work["release_url"] = release["html_url"]
            write_receipt(receipt_path, receipt)

            verified_by_name: dict[str, dict[str, Any]] = {}
            for asset in work["assets"]:
                try:
                    remote = get_named_asset(release, asset["name"], tag)
                    if remote is not None:
                        verify_remote_asset(remote, asset, tag)
                        outcome = "SKIP verified"
                    else:
                        remote = upload_asset(release, work, asset)
                        outcome = "UPLOADED and verified"
                except UploadError:
                    print(f"{tag}: FAILED {asset['name']}", flush=True)
                    raise
                verified_by_name[asset["name"]] = receipt_asset(remote, asset)
                receipt_work["assets"] = [
                    verified_by_name[item["name"]]
                    for item in work["assets"] if item["name"] in verified_by_name
                ]
                write_receipt(receipt_path, receipt)
                print(f"{tag}: {outcome} {asset['name']}", flush=True)

            # A draft is published only once every expected asset has verified.
            if release["draft"]:
                edited = run_gh([
                    "release", "edit", tag, "--repo", REPOSITORY,
                    "--draft=false", "--latest=false",
                ])
                if edited.returncode != 0:
                    raise UploadError(f"Could not publish verified draft {tag} (gh exit {edited.returncode}).")
            final_release = wait_for_release(tag, published=True)
            if final_release is None:
                raise UploadError(f"Release {tag} disappeared before final inventory verification.")
            final_assets = verify_release_inventory(final_release, work)
            if final_release["draft"]:
                raise UploadError(f"Release {tag} is still a draft after publication; archive is incomplete.")
            receipt_work["release_url"] = final_release["html_url"]
            receipt_work["assets"] = final_assets
            receipt_work["release_draft"] = final_release["draft"]
            write_receipt(receipt_path, receipt)

        receipt["status"] = "COMPLETE"
        write_receipt(receipt_path, receipt)
    except UploadError as exc:
        receipt["status"] = "FAILED"
        receipt["failure"] = str(exc)
        try:
            write_receipt(receipt_path, receipt)
        except UploadError:
            raise UploadError(f"{exc} Receipt update also failed.") from None
        raise
    except OSError:
        receipt["status"] = "FAILED"
        receipt["failure"] = "Local I/O failed during release operation."
        try:
            write_receipt(receipt_path, receipt)
        except UploadError:
            raise UploadError("Local I/O failed during release operation; receipt update also failed.") from None
        raise UploadError("Local I/O failed during release operation.") from None


def main() -> int:
    args = parse_args()
    try:
        root, works, total_bytes = load_and_validate_catalog(args.catalog, args.root)
        asset_count = sum(len(work["assets"]) for work in works)
        if not args.apply:
            print(f"DRY RUN: {len(works)} work(s), {asset_count} asset(s), {total_bytes} byte(s) validated.")
            return 0
        receipt_path = resolve_receipt(root, args.receipt, args.target)
        print(f"Validated {len(works)} work(s), {asset_count} asset(s), {total_bytes} byte(s).", flush=True)
        apply_upload(works, args.target, receipt_path)
        print(f"COMPLETE: verified {asset_count} asset(s) across {len(works)} work(s).")
        return 0
    except UploadError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
