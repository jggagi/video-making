#!/usr/bin/env python3
"""Preview or restore media listed in archive/catalog.json."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import quote, unquote, urlsplit
from urllib.request import urlopen

REPOSITORY = "jggagi/video-making"
CHUNK_SIZE = 1024 * 1024
TIMEOUT_SECONDS = 60
SHA256_RE = re.compile(r"[0-9a-fA-F]{64}\Z")


def _inside(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _destination(root: Path, relative: str, components: list[str]) -> Path:
    target = root.joinpath(*components)
    cursor = root
    for part in components:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError(f"refusing symlink in asset destination: {relative}")
    target = target.resolve(strict=False)
    if not _inside(root, target) or target == root:
        raise ValueError(f"asset destination escapes repository root: {relative!r}")
    return target


def _validate_release_url(url: object, name: str) -> str:
    if not isinstance(url, str):
        raise ValueError("asset download_url must be a string")
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.netloc != "github.com"
            or parsed.query or parsed.fragment):
        raise ValueError(f"expected a public GitHub release URL, got: {url!r}")
    parts = parsed.path.split("/")
    if len(parts) != 7 or parts[1:5] != ["jggagi", "video-making", "releases", "download"]:
        raise ValueError(f"URL is not a release download from {REPOSITORY}: {url!r}")
    tag, url_name = unquote(parts[5]), unquote(parts[6])
    if (not tag or tag in {".", ".."} or "/" in tag or "\\" in tag
            or not url_name or "/" in url_name or "\\" in url_name
            or url_name != name or quote(tag, safe="") != parts[5]
            or quote(url_name, safe="") != parts[6]):
        raise ValueError(f"release URL tag or asset name is invalid: {url!r}")
    return url


def _asset_record(root: Path, work_id: str, raw: object) -> dict:
    if not isinstance(raw, dict):
        raise ValueError(f"work {work_id!r} contains a non-object asset")
    relative = raw.get("path")
    name = raw.get("name")
    size = raw.get("bytes")
    digest = raw.get("sha256")
    if not isinstance(relative, str) or not relative or "\\" in relative or "\x00" in relative:
        raise ValueError(f"work {work_id!r} asset path must be a relative POSIX path")
    components = relative.split("/")
    if (relative.startswith("/") or any(part in {"", ".", ".."} for part in components)
            or re.match(r"^[A-Za-z]:", components[0])):
        raise ValueError(f"asset path escapes the repository root: {relative!r}")
    if (not isinstance(name, str) or not name or name in {".", ".."}
            or "/" in name or "\\" in name or "\x00" in name):
        raise ValueError(f"asset name is invalid for {relative!r}")
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise ValueError(f"asset byte count must be a positive integer for {relative!r}")
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
        raise ValueError(f"asset SHA-256 is invalid for {relative!r}")
    url = _validate_release_url(raw.get("download_url"), name)

    return {"work_id": work_id, "path": relative, "name": name,
            "bytes": size, "sha256": digest.lower(), "download_url": url,
            "root": root, "components": components,
            "target": _destination(root, relative, components)}


def _read_catalog(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid catalog JSON in {path}: {error}") from None
    if not isinstance(data, dict) or data.get("repository") != REPOSITORY:
        raise ValueError(f"catalog repository must be {REPOSITORY!r}")
    if not isinstance(data.get("works"), list):
        raise ValueError("catalog works must be a list")
    return data


def _select_assets(data: dict, root: Path, requested: list[str] | None) -> list[dict]:
    by_id = {}
    for work in data["works"]:
        if not isinstance(work, dict) or not isinstance(work.get("id"), str) or not work["id"]:
            raise ValueError("every catalog work must have a nonempty string id")
        if work["id"] in by_id:
            raise ValueError(f"duplicate work id in catalog: {work['id']!r}")
        by_id[work["id"]] = work

    selected_ids = list(dict.fromkeys(requested)) if requested else list(by_id)
    missing = [work_id for work_id in selected_ids if work_id not in by_id]
    if missing:
        raise ValueError("unknown work id(s): " + ", ".join(missing))

    assets = []
    seen_targets = set()
    for work_id in selected_ids:
        raw_assets = by_id[work_id].get("assets")
        if not isinstance(raw_assets, list):
            raise ValueError(f"work {work_id!r} assets must be a list")
        for raw in raw_assets:
            asset = _asset_record(root, work_id, raw)
            if asset["target"] in seen_targets:
                raise ValueError(f"duplicate asset destination in selected works: {asset['path']}")
            seen_targets.add(asset["target"])
            assets.append(asset)
    return assets


def _file_digest(path: Path) -> tuple[int, str]:
    before = path.stat()
    if not path.is_file():
        raise ValueError(f"asset destination is not a regular file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(block)
    after = path.stat()
    stable_before = (before.st_size, before.st_mtime_ns, before.st_ino)
    stable_after = (after.st_size, after.st_mtime_ns, after.st_ino)
    if stable_before != stable_after:
        raise ValueError(f"asset changed while checking it: {path}")
    return after.st_size, digest.hexdigest()


def _matches(asset: dict) -> bool:
    target = asset["target"]
    if target.is_symlink():
        raise ValueError(f"refusing symlink destination: {asset['path']}")
    if not target.exists():
        return False
    if not target.is_file():
        raise ValueError(f"asset destination exists and is not a regular file: {asset['path']}")
    size, digest = _file_digest(target)
    if (size, digest) == (asset["bytes"], asset["sha256"]):
        return True
    raise ValueError(f"existing file differs from catalog; preserving it: {asset['path']}")


def _download(asset: dict) -> str:
    target = asset["target"]
    target.parent.mkdir(parents=True, exist_ok=True)

    # Recheck path components after creating parents. The resolved destination is
    # rooted in the checkout, and the final hard link below is exclusive.
    target = _destination(asset["root"], asset["path"], asset["components"])
    asset["target"] = target
    if _matches(asset):
        return "skipped"

    fd, part_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".part", dir=target.parent)
    part = Path(part_name)
    try:
        digest = hashlib.sha256()
        total = 0
        with os.fdopen(fd, "wb") as output:
            with urlopen(asset["download_url"], timeout=TIMEOUT_SECONDS) as response:
                while True:
                    block = response.read(CHUNK_SIZE)
                    if not block:
                        break
                    total += len(block)
                    if total > asset["bytes"]:
                        raise ValueError(f"download exceeds catalog byte count: {asset['path']}")
                    digest.update(block)
                    output.write(block)
            output.flush()
            os.fsync(output.fileno())

        if total != asset["bytes"]:
            raise ValueError(f"download size mismatch for {asset['path']}: expected {asset['bytes']}, got {total}")
        if digest.hexdigest() != asset["sha256"]:
            raise ValueError(f"download SHA-256 mismatch for {asset['path']}")

        try:
            os.link(part, target)
        except FileExistsError:
            # A concurrent restore may have won. Accept only its verified result.
            if _matches(asset):
                return "skipped"
            raise
        return "downloaded"
    finally:
        try:
            part.unlink()
        except FileNotFoundError:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", action="append", metavar="ID", help="restore one work (repeatable; default: all)")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1],
                        help="repository root (default: this script's parent repository)")
    parser.add_argument("--catalog", type=Path, help="catalog path (default: ROOT/archive/catalog.json)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--list", action="store_true", help="show the proposed restore set (the default)")
    mode.add_argument("--download", action="store_true", help="download and verify missing assets")
    args = parser.parse_args(argv)

    root = args.root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"repository root is not a directory: {root}")
    catalog_path = args.catalog if args.catalog is not None else root / "archive" / "catalog.json"
    data = _read_catalog(catalog_path)
    assets = _select_assets(data, root, args.work)

    if not args.download:
        total = sum(asset["bytes"] for asset in assets)
        for asset in assets:
            print(f"{asset['bytes']:>12,} bytes  {asset['path']}")
        print(f"{len(assets)} assets, {total:,} bytes proposed; pass --download to restore")
        return 0

    # Detect all pre-existing conflicts before the first network request.
    pending = [asset for asset in assets if not _matches(asset)]
    already_present = len(assets) - len(pending)
    for asset in pending:
        result = _download(asset)
        action = "Restored" if result == "downloaded" else "Skipped verified"
        print(f"{action}: {asset['path']} ({asset['bytes']:,} bytes)")
    print(f"Restore complete: {already_present} already verified, {len(pending)} downloaded")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        raise SystemExit(f"Archive restore stopped: {error}") from None
