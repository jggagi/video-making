"""Fail-closed visual QC evidence gate tests; no video decoding or rendering."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


QC = load_module(
    "visual_qc_under_test",
    REPOSITORY_ROOT / "skills" / "dual-platform-video" / "scripts" / "visual_qc.py",
)
VALIDATOR = load_module(
    "visual_qc_validator_under_test",
    REPOSITORY_ROOT / "skills" / "dual-platform-video" / "scripts" / "validate_delivery.py",
)
INITIALIZER = load_module(
    "visual_qc_initializer_under_test",
    REPOSITORY_ROOT / "skills" / "dual-platform-video" / "scripts" / "init_delivery.py",
)
ARCHIVE = load_module(
    "visual_qc_archive_under_test",
    REPOSITORY_ROOT / "scripts" / "build-archive-catalog.py",
)


REPORTS = {
    "bilibili": "review/visual-qc-bilibili/report.json",
    "xiaohongshu": "review/visual-qc-xiaohongshu/report.json",
}
EXPECTED_FRAMES = 24


def create_delivery(root, *, with_policy=True):
    (root / "source").mkdir(parents=True)
    (root / "source" / "script.md").write_text("Visual QC test.\n", encoding="utf-8")
    outputs = {}
    for key, folder in (("bilibili", "B站"), ("xiaohongshu", "小红书")):
        output = root / folder / "final.mp4"
        output.parent.mkdir(parents=True)
        output.write_bytes(f"{key} video bytes".encode())
        width, height = ((3840, 2160) if key == "bilibili" else (2160, 3840))
        outputs[key] = {"path": output.relative_to(root).as_posix(),
                        "width": width, "height": height}
    manifest = {
        "schema_version": 1,
        "title": "Visual QC test",
        "slug": root.name,
        "duration_seconds": 1,
        "fps": 24,
        "total_frames": EXPECTED_FRAMES,
        "audio": {"mode": "silent", "master": "project/public/audio/master.wav"},
        "script": {
            "path": "source/script.md",
            "sha256": hashlib.sha256((root / "source" / "script.md").read_bytes()).hexdigest(),
        },
        "outputs": outputs,
    }
    if with_policy:
        manifest["visual_qc"] = {"required": True, "reports": dict(REPORTS)}
    (root / "delivery.json").write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


def output_hashes(root, manifest):
    return {
        key: hashlib.sha256((root / config["path"]).read_bytes()).hexdigest()
        for key, config in manifest["outputs"].items()
    }


def report_for(media_sha256, *, flags=None, reviews=None, scan_overrides=None):
    scan = {
        "mode": "continuous_from_start",
        "every_frame": True,
        "no_input_seek": True,
        "decoded_frames": EXPECTED_FRAMES,
        "expected_frames": EXPECTED_FRAMES,
        "return_code": 0,
        "complete": True,
        "partial_frame_bytes": 0,
        "decode_error": None,
        "media_sha256_after": media_sha256,
        "media_sha256_matches": True,
        "analysis": ["isolated_full_frame_jump", "stable_roi", "dark_roi"],
    }
    scan.update(scan_overrides or {})
    return {
        "schema_version": 1,
        "media_sha256": media_sha256,
        "scan": scan,
        "flagged_frames": flags if flags is not None else [],
        "flag_reviews": reviews if reviews is not None else [],
        # The validator intentionally ignores any self-reported status field.
        "status": "PASS",
    }


def write_reports(root, manifest, *, flags=None, reviews=None, scan_overrides=None):
    hashes = output_hashes(root, manifest)
    reports = manifest.get("visual_qc", {}).get("reports", REPORTS)
    for key, report_path in reports.items():
        path = root / report_path
        path.parent.mkdir(parents=True, exist_ok=True)
        current_flags = (flags or {}).get(key, [])
        current_reviews = (reviews or {}).get(key, [])
        path.write_text(json.dumps(report_for(
            hashes[key], flags=current_flags, reviews=current_reviews,
            scan_overrides=(scan_overrides or {}).get(key),
        )), encoding="utf-8")
    return hashes


class VisualQCTests(unittest.TestCase):
    def test_missing_report_is_incomplete_and_stale_report_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            manifest = create_delivery(root)
            hashes = output_hashes(root, manifest)
            result = QC.validate_visual_qc(root, manifest, hashes, EXPECTED_FRAMES)
            self.assertEqual(result["status"], "INCOMPLETE")

            write_reports(root, manifest)
            (root / "B站" / "final.mp4").write_bytes(b"changed final video")
            result = QC.validate_visual_qc(
                root, manifest, output_hashes(root, manifest), EXPECTED_FRAMES
            )
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("stale", " ".join(result["failures"]))

    def test_current_complete_scan_with_no_flags_passes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            manifest = create_delivery(root)
            hashes = write_reports(root, manifest)
            result = QC.validate_visual_qc(root, manifest, hashes, EXPECTED_FRAMES)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["outputs"]["bilibili"]["decoded_frames"], EXPECTED_FRAMES)

    def test_explicit_portrait_only_manifest_validates_only_portrait_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "portrait"
            manifest = create_delivery(root)
            manifest["platforms"] = ["xiaohongshu"]
            manifest["outputs"].pop("bilibili")
            manifest["visual_qc"]["reports"].pop("bilibili")
            hashes = write_reports(root, manifest)
            result = QC.validate_visual_qc(root, manifest, hashes, EXPECTED_FRAMES)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(set(result["outputs"]), {"xiaohongshu"})

    def test_explicit_platforms_and_visual_report_keys_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "invalid"
            manifest = create_delivery(root)
            hashes = output_hashes(root, manifest)
            for platforms in ([], ["unknown"], ["xiaohongshu", "xiaohongshu"]):
                with self.subTest(platforms=platforms):
                    invalid = dict(manifest)
                    invalid["platforms"] = platforms
                    result = QC.validate_visual_qc(root, invalid, hashes, EXPECTED_FRAMES)
                    self.assertEqual(result["status"], "FAIL")

            portrait = dict(manifest)
            portrait["platforms"] = ["xiaohongshu"]
            portrait["visual_qc"] = {
                "required": True,
                "reports": dict(REPORTS),
            }
            result = QC.validate_visual_qc(root, portrait, hashes, EXPECTED_FRAMES)
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("exactly match", " ".join(result["failures"]))

            portrait.pop("visual_qc")
            result = QC.validate_visual_qc(root, portrait, hashes, EXPECTED_FRAMES)
            self.assertEqual(result["status"], "FAIL")

    def test_reviewed_authored_transition_with_matching_evidence_passes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            manifest = create_delivery(root)
            evidence = root / "review" / "transition-note.txt"
            evidence.parent.mkdir(parents=True)
            evidence.write_text("The hard cut begins the authored scene transition.\n", encoding="utf-8")
            review = {
                "frame": 7,
                "disposition": "authored_transition",
                "note": "Matches the documented scene transition.",
                "evidence": {
                    "path": evidence.relative_to(root).as_posix(),
                    "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
                },
            }
            hashes = write_reports(
                root, manifest,
                flags={"bilibili": [{"frame": 7, "reasons": ["isolated_full_frame_jump"]}]},
                reviews={"bilibili": [review]},
            )
            result = QC.validate_visual_qc(root, manifest, hashes, EXPECTED_FRAMES)
            self.assertEqual(result["status"], "PASS")

    def test_unresolved_flag_and_tampered_evidence_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "unresolved"
            manifest = create_delivery(root)
            hashes = write_reports(
                root, manifest,
                flags={"bilibili": [{"frame": 3, "reasons": ["dark_roi"]}]},
            )
            result = QC.validate_visual_qc(root, manifest, hashes, EXPECTED_FRAMES)
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("lack review", " ".join(result["failures"]))

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "tampered"
            manifest = create_delivery(root)
            evidence = root / "review" / "evidence.txt"
            evidence.parent.mkdir(parents=True)
            evidence.write_text("original evidence", encoding="utf-8")
            review = {
                "frame": 3,
                "disposition": "false_positive",
                "note": "Reviewed against the source shot.",
                "evidence": {
                    "path": "review/evidence.txt",
                    "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
                },
            }
            hashes = write_reports(
                root, manifest,
                flags={"bilibili": [{"frame": 3, "reasons": ["dark_roi"]}]},
                reviews={"bilibili": [review]},
            )
            evidence.write_text("changed evidence", encoding="utf-8")
            result = QC.validate_visual_qc(root, manifest, hashes, EXPECTED_FRAMES)
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("does not match", " ".join(result["failures"]))

    def test_partial_scan_and_malformed_policy_are_blocked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "partial"
            manifest = create_delivery(root)
            hashes = write_reports(
                root, manifest,
                scan_overrides={"bilibili": {"decoded_frames": EXPECTED_FRAMES - 1}},
            )
            result = QC.validate_visual_qc(root, manifest, hashes, EXPECTED_FRAMES)
            self.assertEqual(result["status"], "INCOMPLETE")

            manifest["visual_qc"]["required"] = False
            result = QC.validate_visual_qc(root, manifest, hashes, EXPECTED_FRAMES)
            self.assertEqual(result["status"], "FAIL")

    def test_scanner_completion_hash_and_full_frame_evidence_are_required(self):
        cases = (
            ({"complete": False}, "INCOMPLETE"),
            ({"partial_frame_bytes": 5, "complete": False}, "INCOMPLETE"),
            ({"decode_error": "decoder reported an error", "complete": False}, "INCOMPLETE"),
            ({"media_sha256_matches": False, "complete": False}, "INCOMPLETE"),
            ({"media_sha256_after": "0" * 64, "media_sha256_matches": False}, "FAIL"),
            ({"analysis": ["stable_roi"]}, "FAIL"),
            ({"analysis": ["isolated_full_frame_jump", "isolated_full_frame_jump"]}, "FAIL"),
        )
        for overrides, expected_status in cases:
            with self.subTest(overrides=overrides), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "work"
                manifest = create_delivery(root)
                hashes = write_reports(
                    root, manifest, scan_overrides={"bilibili": overrides}
                )
                result = QC.validate_visual_qc(root, manifest, hashes, EXPECTED_FRAMES)
                self.assertEqual(result["status"], expected_status)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "missing-field"
            manifest = create_delivery(root)
            hashes = write_reports(root, manifest)
            report_path = root / REPORTS["bilibili"]
            report = json.loads(report_path.read_text(encoding="utf-8"))
            del report["scan"]["complete"]
            report_path.write_text(json.dumps(report), encoding="utf-8")
            result = QC.validate_visual_qc(root, manifest, hashes, EXPECTED_FRAMES)
            self.assertEqual(result["status"], "FAIL")

    def test_malformed_and_symlinked_reports_or_evidence_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "malformed"
            manifest = create_delivery(root)
            hashes = write_reports(root, manifest)
            report_path = root / REPORTS["xiaohongshu"]
            report_path.write_text("{ malformed", encoding="utf-8")
            result = QC.validate_visual_qc(root, manifest, hashes, EXPECTED_FRAMES)
            self.assertEqual(result["status"], "FAIL")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "report-link"
            manifest = create_delivery(root)
            hashes = write_reports(root, manifest)
            linked_report = root / REPORTS["bilibili"]
            symlink_target = root / "review" / "real-report.json"
            symlink_target.write_text(json.dumps(report_for(hashes["bilibili"])), encoding="utf-8")
            linked_report.unlink()
            linked_report.symlink_to(symlink_target)
            result = QC.validate_visual_qc(root, manifest, hashes, EXPECTED_FRAMES)
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("symlink", " ".join(result["failures"]))

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "evidence-link"
            manifest = create_delivery(root)
            evidence = root / "review" / "evidence.txt"
            evidence.parent.mkdir(parents=True)
            symlink_target = root / "review" / "real-evidence.txt"
            symlink_target.write_text("review evidence", encoding="utf-8")
            evidence.symlink_to(symlink_target)
            review = {
                "frame": 2,
                "disposition": "false_positive",
                "note": "Checked against the source shot.",
                "evidence": {
                    "path": "review/evidence.txt",
                    "sha256": hashlib.sha256(symlink_target.read_bytes()).hexdigest(),
                },
            }
            hashes = write_reports(
                root, manifest,
                flags={"bilibili": [{"frame": 2, "reasons": ["dark_roi"]}]},
                reviews={"bilibili": [review]},
            )
            result = QC.validate_visual_qc(root, manifest, hashes, EXPECTED_FRAMES)
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("symlink", " ".join(result["failures"]))

    def test_initializer_adds_platform_policy_and_legacy_is_not_required(self):
        manifest = INITIALIZER.build_manifest(
            slug="new-work", title="New work", fps=60, audio_mode="silent",
            script_bytes=b"script", duration_seconds=120,
        )
        self.assertEqual(manifest["visual_qc"], {"required": True, "reports": REPORTS})
        portrait = INITIALIZER.build_manifest(
            slug="portrait-work", title="Portrait work", fps=60, audio_mode="silent",
            script_bytes=b"script", duration_seconds=90, platforms=["xiaohongshu"],
        )
        self.assertEqual(portrait["platforms"], ["xiaohongshu"])
        self.assertEqual(
            portrait["visual_qc"],
            {"required": True, "reports": {"xiaohongshu": REPORTS["xiaohongshu"]}},
        )
        self.assertEqual(
            QC.validate_visual_qc(Path("."), {"schema_version": 1}, {}, None)["status"],
            "NOT_REQUIRED",
        )

    def test_validator_keeps_required_incomplete_qc_from_passing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "validator"
            manifest = create_delivery(root)
            media_results = {}
            for key, config in manifest["outputs"].items():
                media_results[key] = {
                    "status": "PASS", "path": config["path"],
                    "sha256": hashlib.sha256((root / config["path"]).read_bytes()).hexdigest(),
                    "measurements": {}, "checks": {}, "failures": [],
                }
            with patch.object(VALIDATOR, "validate_media", side_effect=lambda key, *args: media_results[key]):
                exit_code = VALIDATOR.validate(root, skip_decode=False)
            report_path = sorted((root / "review").glob("media-validation-*.json"))[-1]
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 1)
            self.assertEqual(report["status"], "INCOMPLETE")
            self.assertEqual(report["visual_qc"]["status"], "INCOMPLETE")

    def test_archive_refuses_required_missing_visual_qc_before_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            delivery = root / "deliveries" / "archive-gate-work"
            manifest = create_delivery(delivery)
            argv = ["build-archive-catalog.py", "--root", str(root)]
            with patch.object(sys, "argv", argv):
                with self.assertRaisesRegex(ValueError, "Required visual QC is INCOMPLETE"):
                    ARCHIVE.main()
            self.assertFalse((root / "archive" / "catalog.json").exists())
            self.assertFalse((delivery / "archive.json").exists())
            self.assertFalse((delivery / "README.md").exists())

    def test_archive_derives_required_scan_frame_count_from_manifest_timing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            delivery = root / "deliveries" / "bad-frame-count"
            manifest = create_delivery(delivery)
            manifest["total_frames"] = EXPECTED_FRAMES - 1
            (delivery / "delivery.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "total_frames must equal"):
                ARCHIVE.discover(root)
            self.assertFalse((root / "archive" / "catalog.json").exists())

    def test_archive_allows_legacy_manifest_without_implied_visual_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            delivery = root / "deliveries" / "legacy-work"
            create_delivery(delivery, with_policy=False)
            works = ARCHIVE.discover(root)
            self.assertEqual(len(works), 1)
            self.assertTrue(works[0]["historical"] is False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
