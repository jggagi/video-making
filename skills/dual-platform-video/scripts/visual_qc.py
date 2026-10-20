#!/usr/bin/env python3
"""Validate current, full-frame visual QC evidence without decoding media."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
from typing import Any


PLATFORMS = ("bilibili", "xiaohongshu")
DETECTORS = {"isolated_full_frame_jump", "stable_roi", "dark_roi"}
DISPOSITIONS = {"authored_transition", "false_positive"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _failure(message: str, status: str = "FAIL") -> dict[str, Any]:
    return {"status": status, "outputs": {}, "failures": [message]}


def manifest_platforms(manifest: dict) -> tuple[str, ...] | None:
    """Return selected platforms, retaining dual-platform behavior for legacy manifests."""
    if "platforms" not in manifest:
        return PLATFORMS
    value = manifest["platforms"]
    if (not isinstance(value, list) or not value
            or any(not isinstance(platform, str) or platform not in PLATFORMS
                   for platform in value)
            or len(set(value)) != len(value)):
        return None
    return tuple(value)


def _relative_path(root: Path, raw_path: Any, label: str) -> tuple[Path | None, str | None]:
    if (not isinstance(raw_path, str) or not raw_path or "\\" in raw_path
            or "\x00" in raw_path):
        return None, f"{label} must be a non-empty relative POSIX path"
    posix = PurePosixPath(raw_path)
    windows = PureWindowsPath(raw_path)
    if (posix.is_absolute() or windows.is_absolute() or windows.drive
            or any(part in {".", ".."} for part in posix.parts)):
        return None, f"{label} must stay inside the delivery folder"

    candidate = root.joinpath(*posix.parts)
    try:
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return None, f"{label} resolves outside the delivery folder"

    current = root
    for part in posix.parts:
        current = current / part
        try:
            if current.is_symlink():
                return None, f"{label} must not pass through a symlink"
        except OSError:
            return None, f"{label} cannot be inspected safely"
    return candidate, None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scan_issue(
    scan: dict[str, Any], expected_frames: int, media_sha256: str,
    output_hash: Any,
) -> tuple[str | None, str | None]:
    required = {
        "mode", "every_frame", "no_input_seek", "decoded_frames",
        "expected_frames", "return_code", "analysis", "complete",
        "partial_frame_bytes", "decode_error", "media_sha256_matches",
        "media_sha256_after",
    }
    if not required.issubset(scan):
        return "scan is missing required fields", "FAIL"

    for name in ("decoded_frames", "expected_frames", "return_code", "partial_frame_bytes"):
        if type(scan[name]) is not int:
            return f"scan.{name} must be an integer", "FAIL"
    if scan["partial_frame_bytes"] < 0:
        return "scan.partial_frame_bytes must not be negative", "FAIL"
    if not isinstance(scan["mode"], str):
        return "scan.mode must be text", "FAIL"
    if type(scan["every_frame"]) is not bool or type(scan["no_input_seek"]) is not bool:
        return "scan frame/seek indicators must be booleans", "FAIL"
    if type(scan["complete"]) is not bool:
        return "scan.complete must be a boolean", "FAIL"
    if type(scan["media_sha256_matches"]) is not bool:
        return "scan.media_sha256_matches must be a boolean", "FAIL"
    if scan["decode_error"] is not None and not isinstance(scan["decode_error"], str):
        return "scan.decode_error must be null or text", "FAIL"

    media_sha256_after = scan["media_sha256_after"]
    if (not isinstance(media_sha256_after, str)
            or not SHA256_RE.fullmatch(media_sha256_after)):
        return "scan.media_sha256_after must be lowercase SHA-256 hex", "FAIL"
    if (media_sha256_after != media_sha256 or media_sha256_after != output_hash):
        return "scan.media_sha256_after does not match the report and current output hashes", "FAIL"

    analysis = scan["analysis"]
    if (not isinstance(analysis, list) or not analysis
            or any(not isinstance(name, str) or not name.strip() or name not in DETECTORS
                   for name in analysis)):
        return "scan.analysis must list at least one recognized nonempty detector", "FAIL"
    if len(analysis) != len(set(analysis)):
        return "scan.analysis must not repeat detector names", "FAIL"
    if "isolated_full_frame_jump" not in analysis:
        return "scan.analysis must include isolated_full_frame_jump full-frame screening", "FAIL"

    if (scan["mode"] != "continuous_from_start" or scan["every_frame"] is not True
            or scan["no_input_seek"] is not True or scan["return_code"] != 0
            or scan["expected_frames"] != expected_frames
            or scan["decoded_frames"] != expected_frames):
        return (
            "scan does not prove a successful continuous full-frame decode from frame zero",
            "INCOMPLETE",
        )
    if (scan["complete"] is not True or scan["partial_frame_bytes"] != 0
            or scan["decode_error"] is not None or scan["media_sha256_matches"] is not True):
        return "scan reports incomplete decoding or source-hash verification", "INCOMPLETE"
    return None, None


def _validate_reviews(
    root: Path, flagged_frames: Any, flag_reviews: Any, platform: str,
    expected_frames: int,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(flagged_frames, list):
        return [f"{platform}: flagged_frames must be a list"]
    if not isinstance(flag_reviews, list):
        return [f"{platform}: flag_reviews must be a list"]

    flagged_ids: list[int] = []
    for index, item in enumerate(flagged_frames):
        label = f"{platform}: flagged_frames[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object")
            continue
        frame = item.get("frame")
        reasons = item.get("reasons")
        if type(frame) is not int or frame < 0 or frame >= expected_frames:
            errors.append(f"{label}.frame must be an in-range integer frame number")
        else:
            flagged_ids.append(frame)
        if (not isinstance(reasons, list) or not reasons
                or any(not isinstance(reason, str) or not reason.strip() for reason in reasons)):
            errors.append(f"{label}.reasons must contain nonempty text")
    if len(flagged_ids) != len(set(flagged_ids)):
        errors.append(f"{platform}: flagged_frames contains duplicate frame numbers")

    reviewed: dict[int, dict[str, Any]] = {}
    for index, item in enumerate(flag_reviews):
        label = f"{platform}: flag_reviews[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object")
            continue
        frame = item.get("frame")
        if type(frame) is not int or frame < 0 or frame >= expected_frames:
            errors.append(f"{label}.frame must be an in-range integer frame number")
            continue
        if frame in reviewed:
            errors.append(f"{platform}: flag_reviews contains duplicate frame {frame}")
            continue
        reviewed[frame] = item

    flagged_set = set(flagged_ids)
    reviewed_set = set(reviewed)
    if flagged_set != reviewed_set:
        missing = sorted(flagged_set - reviewed_set)
        extra = sorted(reviewed_set - flagged_set)
        if missing:
            errors.append(f"{platform}: flagged frames lack review: {missing}")
        if extra:
            errors.append(f"{platform}: reviews refer to unflagged frames: {extra}")

    for frame, item in reviewed.items():
        label = f"{platform}: review for frame {frame}"
        disposition = item.get("disposition")
        if not isinstance(disposition, str) or disposition not in DISPOSITIONS:
            errors.append(f"{label} has an unsupported disposition")
        note = item.get("note")
        if not isinstance(note, str) or not note.strip():
            errors.append(f"{label} requires a nonempty note")
        evidence = item.get("evidence")
        if not isinstance(evidence, dict):
            errors.append(f"{label} requires evidence with path and sha256")
            continue
        digest = evidence.get("sha256")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            errors.append(f"{label} evidence.sha256 must be lowercase SHA-256 hex")
            continue
        evidence_path, path_error = _relative_path(root, evidence.get("path"),
                                                  f"{label} evidence.path")
        if path_error:
            errors.append(path_error)
            continue
        try:
            if not evidence_path.is_file():
                errors.append(f"{label} evidence must be an existing regular file")
            elif _sha256(evidence_path) != digest:
                errors.append(f"{label} evidence SHA-256 does not match the file")
        except OSError as exc:
            errors.append(f"{label} evidence cannot be read: {exc}")
    return errors


def _validate_one(
    root: Path, platform: str, report_path_value: str, output_hash: Any,
    expected_frames: int,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "PASS", "report": report_path_value,
        "media_sha256": None, "decoded_frames": None, "flagged_frames": 0,
        "failures": [],
    }

    if not isinstance(output_hash, str) or not SHA256_RE.fullmatch(output_hash):
        result["status"] = "INCOMPLETE"
        result["failures"].append(f"{platform}: actual output SHA-256 is unavailable")

    report_path, path_error = _relative_path(root, report_path_value,
                                             f"visual_qc.reports.{platform}")
    if path_error:
        result["status"] = "FAIL"
        result["failures"].append(path_error)
        return result
    try:
        if not report_path.exists():
            result["status"] = "INCOMPLETE"
            result["failures"].append(f"{platform}: visual QC report is missing")
            return result
        if not report_path.is_file():
            raise ValueError("report must be an existing regular file")
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        result["status"] = "FAIL"
        result["failures"].append(f"{platform}: cannot read valid visual QC report: {exc}")
        return result

    if not isinstance(report, dict):
        result["status"] = "FAIL"
        result["failures"].append(f"{platform}: report root must be an object")
        return result
    if type(report.get("schema_version")) is not int or report["schema_version"] != 1:
        result["status"] = "FAIL"
        result["failures"].append(f"{platform}: report schema_version must be 1")
        return result

    media_sha = report.get("media_sha256")
    result["media_sha256"] = media_sha
    if not isinstance(media_sha, str) or not SHA256_RE.fullmatch(media_sha):
        result["status"] = "FAIL"
        result["failures"].append(f"{platform}: media_sha256 must be lowercase SHA-256 hex")
    elif isinstance(output_hash, str) and media_sha != output_hash:
        result["status"] = "FAIL"
        result["failures"].append(f"{platform}: report is stale for the current output media")

    scan = report.get("scan")
    if not isinstance(scan, dict):
        result["status"] = "FAIL"
        result["failures"].append(f"{platform}: scan must be an object")
    else:
        scan_error, scan_status = _scan_issue(
            scan, expected_frames, media_sha, output_hash
        )
        if scan_error:
            result["status"] = scan_status or "FAIL"
            result["failures"].append(f"{platform}: {scan_error}")
        else:
            result["decoded_frames"] = scan["decoded_frames"]

    flagged = report.get("flagged_frames")
    result["flagged_frames"] = len(flagged) if isinstance(flagged, list) else 0
    review_errors = _validate_reviews(
        root, flagged, report.get("flag_reviews"), platform, expected_frames
    )
    if review_errors:
        result["status"] = "FAIL"
        result["failures"].extend(review_errors)
    return result


def validate_visual_qc(
    root: Path, manifest: dict, output_hashes: dict[str, str], expected_frames: int,
) -> dict[str, Any]:
    """Validate policy and reports, binding them to measured output hashes.

    Legacy manifests without a visual_qc entry remain explicitly NOT_REQUIRED.
    This helper validates evidence only; it never decodes video.
    """
    if not isinstance(manifest, dict):
        return _failure("delivery manifest must be an object when checking visual QC")
    platforms = manifest_platforms(manifest)
    if platforms is None:
        return _failure("delivery.json platforms must be a nonempty list of unique known platform keys")
    if "visual_qc" not in manifest:
        if "platforms" in manifest:
            return _failure("delivery.json with explicit platforms must include visual_qc.reports")
        return {"status": "NOT_REQUIRED", "outputs": {}, "failures": []}
    policy = manifest["visual_qc"]
    if not isinstance(policy, dict) or set(policy) != {"required", "reports"}:
        return _failure("visual_qc policy must contain exactly required and reports")
    if policy.get("required") is not True:
        return _failure("visual_qc.required must be true")
    reports = policy.get("reports")
    if not isinstance(reports, dict) or set(reports) != set(platforms):
        return _failure("visual_qc.reports keys must exactly match selected platforms")
    if type(expected_frames) is not int or expected_frames <= 0:
        return _failure("expected_frames must be a positive integer")
    if not isinstance(output_hashes, dict):
        return _failure("output_hashes must be an object")

    try:
        resolved_root = root.resolve(strict=True)
    except (OSError, RuntimeError):
        return _failure("delivery root cannot be resolved")
    if not resolved_root.is_dir():
        return _failure("delivery root must be a directory")

    output_results = {
        key: _validate_one(
            resolved_root, key, reports[key], output_hashes.get(key), expected_frames
        )
        for key in platforms
    }
    failures = [failure for result in output_results.values()
                for failure in result["failures"]]
    statuses = {result["status"] for result in output_results.values()}
    status = "FAIL" if "FAIL" in statuses else (
        "INCOMPLETE" if "INCOMPLETE" in statuses else "PASS"
    )
    return {"status": status, "outputs": output_results, "failures": failures}
