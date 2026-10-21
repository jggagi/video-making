#!/usr/bin/env python3
"""Create an editable source package with its required canyon movie, excluding other movies and private config."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import zipfile


PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT.parent
OUTPUT = WORK / f"{WORK.name}-project.zip"
REPORT = WORK / "review" / "package-integrity.json"
REQUIRED_CANYON_MEMBER = "project/public/video/canyon-v03.mp4"
REQUIRED_EDITABLE_MEMBERS = {
    "project/blender/porcelain-canyon-v03.blend",
    "project/blender/scene.py",
    "project/blender/render_saved.py",
    "project/blender/ART-DIRECTION.md",
}
EXCLUDED_DIRS = {
    "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".cache", "cache", "caches", "tmp", "temp", "temporary", "render-staging",
    "audio-staging", ".git", ".hg", ".codex", ".aws", "credentials", "secrets", "private-provider",
}
EXCLUDED_SUFFIXES = {
    ".3g2", ".3gp", ".asf", ".avi", ".f4v", ".flv", ".m2t", ".m2ts", ".m2v",
    ".m4v", ".mjpeg", ".mkv", ".mov", ".mp2", ".mp4", ".mpe", ".mpeg", ".mpg",
    ".mpv", ".mts", ".mxf", ".ogv", ".qt", ".rm", ".rmvb", ".vob", ".webm", ".wmv",
    ".zip", ".pyc", ".log", ".failed", ".partial",
    ".tmp", ".temp", ".swp", ".swo", ".bak", ".blend1", ".blend2", ".sqlite", ".sqlite3", ".db",
    ".pem", ".key", ".p12", ".pfx",
}
PRIVATE_NAMES = {
    "provider-manifest.json", "provider-config.json", "provider-config.toml",
    "audio-authorization.json", "credentials.json", "secrets.json", "tokens.json",
    "auth.json", "auth.toml",
}
SAFE_DECLARED_JSON_ASSETS = {
    "project/audio-authorization.json",
    "project/public/audio/provider-manifest.json",
}
ASSET_MANIFEST = PROJECT / "assets-manifest.json"


def excluded(path: Path, relative: Path) -> bool:
    relative_name = relative.as_posix()
    # These two JSON files are film-specific authorized provenance/settings
    # assets. Their exact paths are intentionally allowlisted; similarly named
    # files elsewhere remain excluded by the normal private-config filters.
    if relative_name in SAFE_DECLARED_JSON_ASSETS:
        return False
    if relative_name == REQUIRED_CANYON_MEMBER:
        return False
    if relative.parts[:3] == ("project", "public", "audio") and len(relative.parts) > 3 and relative.parts[3] == "history":
        return True
    name = path.name.lower()
    if any(part.lower() in EXCLUDED_DIRS for part in relative.parts):
        return True
    if name.startswith(".") or name == "ds_store" or name in PRIVATE_NAMES:
        return True
    if name == "render-staging.json" or name.startswith(".encoded-qa-"):
        return True
    if name == "package-integrity.json":
        return True
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    if name.startswith(".env") or any(secret in name for secret in ("credential", "secret", "token", "provider")):
        return True
    # Native-resolution inspection frames belong in review/ on disk; compact
    # contact sheets and their JSON remain available for project review.
    if relative.parts and relative.parts[0] == "review" and path.suffix.lower() == ".png":
        if name.startswith(("encoded-native-", "source-", "native-", "encoded-")) or path.stat().st_size > 1_000_000:
            return True
    return False


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def select_package_files() -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []
    for path in sorted(WORK.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(WORK)
        if excluded(path, relative):
            continue
        files.append((path, relative.as_posix()))
    return files


def load_declared_assets() -> list[tuple[str, str]]:
    try:
        manifest = json.loads(ASSET_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Could not read project assets manifest: {error}") from error
    assets = manifest.get("assets") if isinstance(manifest, dict) else None
    if not isinstance(assets, list):
        raise SystemExit("Project assets manifest must contain an assets list")

    declared: list[tuple[str, str]] = []
    seen: set[str] = set()
    for entry in assets:
        if not isinstance(entry, dict):
            raise SystemExit("Every project asset manifest entry must be an object")
        asset_path = entry.get("path")
        digest = entry.get("sha256")
        if not isinstance(asset_path, str) or not asset_path:
            raise SystemExit("Every project asset manifest entry must have a path")
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-fA-F]{64}", digest) is None:
            raise SystemExit(f"Asset manifest entry has an invalid SHA-256: {asset_path}")
        project_relative = Path(asset_path)
        if project_relative.is_absolute() or any(part in {"", ".", ".."} for part in project_relative.parts):
            raise SystemExit(f"Asset manifest path is not a normalized project-relative path: {asset_path}")
        member = (Path("project") / project_relative).as_posix()
        if member in seen:
            raise SystemExit(f"Duplicate project asset manifest path: {asset_path}")
        seen.add(member)
        declared.append((member, digest.lower()))
    if REQUIRED_CANYON_MEMBER not in seen:
        raise SystemExit(
            "Required Blender canyon video must be present in project/assets-manifest.json assets "
            f"with a declared SHA-256: {REQUIRED_CANYON_MEMBER.removeprefix('project/')}"
        )
    return declared


def verify_declared_assets(declared: list[tuple[str, str]], member_hashes: dict[str, str], context: str) -> None:
    for member, expected_hash in declared:
        actual_hash = member_hashes.get(member)
        if actual_hash is None:
            raise SystemExit(f"Declared project asset is missing from {context}: {member}")
        if actual_hash != expected_hash:
            raise SystemExit(f"Declared project asset SHA-256 mismatch in {context}: {member}")


def main() -> int:
    if OUTPUT.exists() or REPORT.exists():
        raise SystemExit(f"Refusing to replace an existing archive or report: {OUTPUT} / {REPORT}")
    files = select_package_files()
    if not files:
        raise SystemExit("No packageable project files found")
    selected_members = {name for _, name in files}
    missing_editable = sorted(REQUIRED_EDITABLE_MEMBERS - selected_members)
    if missing_editable:
        raise SystemExit(f"Required editable Blender source files are missing: {', '.join(missing_editable)}")

    member_hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest() for path, name in files}
    declared_assets = load_declared_assets()
    verify_declared_assets(declared_assets, member_hashes, "the selected package file set")
    with zipfile.ZipFile(OUTPUT, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path, name in files:
            archive.write(path, name)

    with zipfile.ZipFile(OUTPUT, "r") as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            OUTPUT.unlink(missing_ok=True)
            raise SystemExit(f"ZIP CRC check failed for {bad_member}")
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != set(member_hashes):
            OUTPUT.unlink(missing_ok=True)
            raise SystemExit("ZIP members do not match the selected project file set")
        verified = {name: sha256_bytes(archive.read(name)) for name in names}
        if verified != member_hashes:
            OUTPUT.unlink(missing_ok=True)
            raise SystemExit("ZIP member SHA-256 verification failed")
        try:
            verify_declared_assets(declared_assets, verified, "the created ZIP archive")
        except SystemExit:
            OUTPUT.unlink(missing_ok=True)
            raise

    report = {
        "status": "PASS",
        "archive": OUTPUT.name,
        "bytes": OUTPUT.stat().st_size,
        "sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        "file_count": len(files),
        "declared_asset_count": len(declared_assets),
        "declared_assets_sha256_verified": True,
        "member_sha256": member_hashes,
        "validation": "ZIP CRC, exact relative member list, SHA-256 of every uncompressed member, and declared assets-manifest paths and hashes",
        "exclusions": [
            "encoded movies other than the required public/video/canyon-v03.mp4 dependency, and ZIPs",
            "Blender .blend1/.blend2 backup files",
            "node_modules and caches",
            "temporary files, logs, and failed/interrupted outputs",
            "private provider, credential, token, and secret configuration (except the two exact film-specific JSON assets listed in assets-manifest.json)",
            "full-resolution review PNGs; compact QA reports and contact sheets are retained",
        ],
        "scope": "Editable source, scripts, source text, lockfiles, audio assets, and compact QA only; no platform account or GitHub upload is performed.",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("status", "archive", "bytes", "sha256", "file_count", "declared_asset_count")},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
