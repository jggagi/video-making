#!/usr/bin/env python3
"""Build a deterministic, no-overwrite editable ZIP for the EP11 Blender study.

From the repository root, run after all required QA inputs are ready::

    python3 experiments/ep11-canyon-blender-v01/project/package_study.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import stat
import sys
import tempfile
import zipfile
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
STUDY_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]
MEDIA_DIR = STUDY_ROOT / "media"
REVIEW_DIR = STUDY_ROOT / "review"
OUTPUT_PATH = MEDIA_DIR / "ep11-canyon-blender-v01-editable.zip"
VERIFICATION_PATH = REVIEW_DIR / "package-verification.json"
LOCK_PATH = REVIEW_DIR / ".package_study.lock"
SCANNER_REPORT = REVIEW_DIR / "continuous-scan" / "report.json"
ZIP_TIMESTAMP = (2026, 10, 21, 0, 0, 0)
PACKAGE_SCHEMA = "ep11-canyon-blender-study-package/v1"
VERIFICATION_SCHEMA = "ep11-canyon-blender-study-package-verification/v1"
CHUNK_SIZE = 1024 * 1024


class PackageError(RuntimeError):
    """A concise, safe packaging or integrity failure."""


def relative_to_repo(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError as error:
        raise PackageError(f"Input path escaped repository root: {path}") from error


def assert_no_symlink_path(path: Path) -> None:
    """Reject symlinks in each component from the repository root to a file."""
    try:
        relative = path.relative_to(REPO_ROOT)
    except ValueError as error:
        raise PackageError(f"Input is outside the repository: {path}") from error
    current = REPO_ROOT
    if current.is_symlink():
        raise PackageError(f"Repository root is a symlink: {current}")
    for component in relative.parts:
        current = current / component
        if current.is_symlink():
            raise PackageError(f"Symlinks are not allowed in package inputs: {current}")


def require_regular_file(path: Path, label: str) -> Path:
    assert_no_symlink_path(path)
    if not path.is_file():
        raise PackageError(f"Required {label} is missing or is not a regular file: {relative_to_repo(path)}")
    return path


def file_digest(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        for block in iter(lambda: source.read(CHUNK_SIZE), b""):
            size += len(block)
            digest.update(block)
    return size, digest.hexdigest()


def selected_sources() -> tuple[list[tuple[str, Path]], bool]:
    """Return only the fixed study package set and whether the scan report exists."""
    required = [
        ("README.md", STUDY_ROOT / "README.md"),
        ("watch.html", STUDY_ROOT / "watch.html"),
        ("project/brief.md", STUDY_ROOT / "project" / "brief.md"),
        ("project/porcelain-canyon-look06.blend", STUDY_ROOT / "project" / "porcelain-canyon-look06.blend"),
        ("media/canyon-8s-master.wav", MEDIA_DIR / "canyon-8s-master.wav"),
        ("review/render-report.json", REVIEW_DIR / "render-report.json"),
        ("review/hero-render-report.json", REVIEW_DIR / "hero-render-report.json"),
        ("review/assembly-qa.json", REVIEW_DIR / "assembly-qa.json"),
        ("review/acceptance.json", REVIEW_DIR / "acceptance.json"),
        ("review/art-assessment.md", REVIEW_DIR / "art-assessment.md"),
        ("review/scene-reopen-pixel-check.json", REVIEW_DIR / "scene-reopen-pixel-check.json"),
        ("review/geometry-validation.json", REVIEW_DIR / "geometry-validation.json"),
        ("review/encoded-contact.jpg", REVIEW_DIR / "encoded-contact.jpg"),
        ("review/comparison-encoded-7s.jpg", REVIEW_DIR / "comparison-encoded-7s.jpg"),
        ("review/comparison-plate.png", REVIEW_DIR / "comparison-plate.png"),
        ("review/hero-4k.png", REVIEW_DIR / "hero-4k.png"),
    ]
    sources: dict[str, Path] = {}
    for member, path in required:
        require_regular_file(path, member)
        sources[member] = path

    project_dir = STUDY_ROOT / "project"
    assert_no_symlink_path(project_dir)
    project_files = sorted(
        [*project_dir.glob("*.py"), *project_dir.glob("*.mjs")],
        key=lambda path: path.name,
    )
    for path in project_files:
        require_regular_file(path, path.name)
        sources[f"project/{path.name}"] = path
    if not any(path.suffix == ".py" for path in project_files):
        raise PackageError("No project/*.py source files were found")
    if not any(path.suffix == ".mjs" for path in project_files):
        raise PackageError("No project/*.mjs source files were found")

    gitignore = STUDY_ROOT / ".gitignore"
    if os.path.lexists(gitignore):
        require_regular_file(gitignore, "study .gitignore")
        sources[".gitignore"] = gitignore

    scanner_included = os.path.lexists(SCANNER_REPORT)
    if scanner_included:
        require_regular_file(SCANNER_REPORT, "continuous visual-QC report")
        sources["review/continuous-scan/report.json"] = SCANNER_REPORT

    if len(sources) != len(set(sources)):
        raise PackageError("Selected package contains duplicate member paths")
    return sorted(sources.items()), scanner_included


def output_paths_are_available() -> None:
    for directory, label in ((MEDIA_DIR, "media directory"), (REVIEW_DIR, "review directory")):
        assert_no_symlink_path(directory)
        if not directory.is_dir():
            raise PackageError(f"Required {label} is missing: {relative_to_repo(directory)}")
    for path, label in ((OUTPUT_PATH, "study ZIP"), (VERIFICATION_PATH, "verification report")):
        if os.path.lexists(path):
            raise PackageError(f"Refusing to overwrite existing {label}: {relative_to_repo(path)}")


def acquire_lock() -> tuple[int, tuple[int, int]]:
    try:
        descriptor = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise PackageError(
            f"Packaging lock already exists: {relative_to_repo(LOCK_PATH)}; inspect before removing it"
        ) from error
    try:
        os.write(descriptor, f"pid={os.getpid()}\n".encode("ascii"))
        os.fsync(descriptor)
        info = os.fstat(descriptor)
        return descriptor, (info.st_dev, info.st_ino)
    except BaseException:
        os.close(descriptor)
        try:
            LOCK_PATH.unlink()
        except OSError:
            pass
        raise


def release_lock(lock_info: tuple[int, int]) -> None:
    try:
        info = LOCK_PATH.stat(follow_symlinks=False)
        if (info.st_dev, info.st_ino) == lock_info:
            LOCK_PATH.unlink()
    except FileNotFoundError:
        pass


def make_file_manifest(sources: list[tuple[str, Path]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for member, path in sources:
        size, digest = file_digest(path)
        if size <= 0:
            raise PackageError(f"Refusing to package an empty file: {member}")
        entries.append({"path": member, "bytes": size, "sha256": digest})
    return entries


def manifest_payload(files: list[dict[str, Any]], scanner_included: bool) -> dict[str, Any]:
    return {
        "schema": PACKAGE_SCHEMA,
        "study": "EP11 porcelain canyon / Blender material and motion study 01",
        "archive_timestamp_utc": "2026-10-21T00:00:00Z",
        "zip_member_timestamp": "2026-10-21 00:00:00",
        "compression": "ZIP_STORED",
        "files": files,
        "optional_continuous_scan_report": {
            "path": "review/continuous-scan/report.json",
            "included": scanner_included,
        },
        "self_hash_note": (
            "This manifest lists package inputs; its own byte count and SHA-256 are recorded "
            "in review/package-verification.json to avoid a self-referential hash."
        ),
    }


def zip_info(member: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(member, date_time=ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    info.extra = b""
    info.comment = b""
    return info


def add_source(archive: zipfile.ZipFile, member: str, path: Path,
               expected: dict[str, Any]) -> None:
    assert_no_symlink_path(path)
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source, archive.open(zip_info(member), "w", force_zip64=True) as target:
        for block in iter(lambda: source.read(CHUNK_SIZE), b""):
            target.write(block)
            size += len(block)
            digest.update(block)
    if size != expected["bytes"] or digest.hexdigest() != expected["sha256"]:
        raise PackageError(f"Package input changed while copying: {member}")


def build_temp_zip(temp_zip: Path, sources: list[tuple[str, Path]],
                   files: list[dict[str, Any]], scanner_included: bool) -> bytes:
    manifest = manifest_payload(files, scanner_included)
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    expected_by_path = {record["path"]: record for record in files}
    try:
        with zipfile.ZipFile(temp_zip, mode="w", compression=zipfile.ZIP_STORED,
                             allowZip64=True, strict_timestamps=True) as archive:
            with archive.open(zip_info("package-manifest.json"), "w", force_zip64=True) as target:
                target.write(manifest_bytes)
            for member, path in sources:
                add_source(archive, member, path, expected_by_path[member])
    except (OSError, zipfile.BadZipFile, RuntimeError, ValueError) as error:
        raise PackageError(f"Could not build temporary study ZIP: {error}") from error
    with temp_zip.open("rb+") as completed:
        os.fsync(completed.fileno())
    return manifest_bytes


def verify_temp_zip(temp_zip: Path, files: list[dict[str, Any]], manifest_bytes: bytes) -> list[dict[str, Any]]:
    expected = {entry["path"]: entry for entry in files}
    expected_names = ["package-manifest.json", *sorted(expected)]
    records: list[dict[str, Any]] = []
    try:
        with zipfile.ZipFile(temp_zip, mode="r") as archive:
            if archive.namelist() != expected_names:
                raise PackageError("ZIP member list differs from the deterministic selection")
            bad_member = archive.testzip()
            if bad_member is not None:
                raise PackageError(f"ZIP CRC verification failed for {bad_member}")
            for member in expected_names:
                digest = hashlib.sha256()
                size = 0
                with archive.open(member, "r") as source:
                    while True:
                        block = source.read(CHUNK_SIZE)
                        if not block:
                            break
                        size += len(block)
                        digest.update(block)
                value = {"path": member, "bytes": size, "sha256": digest.hexdigest()}
                if member == "package-manifest.json":
                    if size != len(manifest_bytes) or digest.digest() != hashlib.sha256(manifest_bytes).digest():
                        raise PackageError("Embedded package manifest did not verify")
                else:
                    input_record = expected[member]
                    if size != input_record["bytes"] or value["sha256"] != input_record["sha256"]:
                        raise PackageError(f"Embedded member failed SHA-256/size verification: {member}")
                records.append(value)
    except (OSError, zipfile.BadZipFile, RuntimeError) as error:
        raise PackageError(f"ZIP integrity verification failed: {error}") from error
    return records


def create_temp_file(directory: Path, prefix: str) -> tuple[int, Path]:
    descriptor, name = tempfile.mkstemp(prefix=prefix, suffix=".tmp", dir=directory)
    return descriptor, Path(name)


def stage_json(directory: Path, prefix: str, value: dict[str, Any]) -> Path:
    descriptor, temporary = create_temp_file(directory, prefix)
    try:
        data = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        with os.fdopen(descriptor, "wb") as target:
            target.write(data)
            target.flush()
            os.fsync(target.fileno())
        return temporary
    except BaseException:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def link_no_replace(source: Path, destination: Path, label: str) -> None:
    try:
        os.link(source, destination, follow_symlinks=False)
    except FileExistsError as error:
        raise PackageError(f"Refusing to overwrite existing {label}: {relative_to_repo(destination)}") from error
    except OSError as error:
        raise PackageError(f"Could not publish {label} without overwrite: {error}") from error


def rollback_own_publication(published: Path, staged: Path) -> None:
    """Remove only our own just-published hard link, never a replacement file."""
    try:
        if os.path.samefile(published, staged):
            published.unlink()
            fsync_directory(published.parent)
    except FileNotFoundError:
        pass


def package() -> tuple[Path, dict[str, Any]]:
    output_paths_are_available()
    lock_fd, lock_info = acquire_lock()
    os.close(lock_fd)
    temp_zip: Path | None = None
    temp_report: Path | None = None
    published_zip = False
    try:
        # Recheck after acquiring the package-specific lock.
        output_paths_are_available()
        sources, scanner_included = selected_sources()
        file_records = make_file_manifest(sources)
        zip_fd, temp_zip = create_temp_file(MEDIA_DIR, ".ep11-study-package-")
        os.close(zip_fd)
        manifest_bytes = build_temp_zip(temp_zip, sources, file_records, scanner_included)
        member_records = verify_temp_zip(temp_zip, file_records, manifest_bytes)
        package_bytes, package_sha256 = file_digest(temp_zip)
        manifest_record = next(item for item in member_records if item["path"] == "package-manifest.json")
        verification = {
            "schema": VERIFICATION_SCHEMA,
            "status": "PASS",
            "archive": relative_to_repo(OUTPUT_PATH),
            "package_bytes": package_bytes,
            "package_sha256": package_sha256,
            "member_count": len(member_records),
            "members": member_records,
            "package_manifest": manifest_record,
            "optional_continuous_scan_report_included": scanner_included,
            "integrity_checks": {
                "zip_crc_test": "PASS",
                "all_member_sha256_and_bytes": "PASS",
                "no_symlink_inputs": "PASS",
                "no_overwrite_publication": "PASS",
            },
            "runtime": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
            },
        }
        temp_report = stage_json(REVIEW_DIR, ".package-verification-", verification)
        output_paths_are_available()
        link_no_replace(temp_zip, OUTPUT_PATH, "study ZIP")
        published_zip = True
        try:
            link_no_replace(temp_report, VERIFICATION_PATH, "package verification report")
        except PackageError:
            rollback_own_publication(OUTPUT_PATH, temp_zip)
            published_zip = False
            raise
        fsync_directory(MEDIA_DIR)
        fsync_directory(REVIEW_DIR)
        return OUTPUT_PATH, verification
    finally:
        if published_zip and not os.path.lexists(VERIFICATION_PATH) and temp_zip is not None:
            rollback_own_publication(OUTPUT_PATH, temp_zip)
        if temp_zip is not None:
            try:
                temp_zip.unlink()
            except FileNotFoundError:
                pass
        if temp_report is not None:
            try:
                temp_report.unlink()
            except FileNotFoundError:
                pass
        release_lock(lock_info)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create and verify the fixed no-overwrite EP11 Blender study ZIP."
    )
    parser.parse_args(argv)
    try:
        output, report = package()
    except PackageError as error:
        print(f"package_study: {error}", file=sys.stderr)
        return 2
    print(
        f"PACKAGE COMPLETE: {output} | {report['package_bytes']} bytes | "
        f"SHA-256 {report['package_sha256']} | {report['member_count']} members"
    )
    for member in report["members"]:
        print(f"  {member['path']} | {member['bytes']} bytes | SHA-256 {member['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
