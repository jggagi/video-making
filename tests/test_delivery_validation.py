import contextlib
import importlib.util
import io
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction
from unittest.mock import patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = (
    REPOSITORY_ROOT / "skills" / "xiaohongshu-video" / "scripts"
    / "validate_delivery.py"
)
SPEC = importlib.util.spec_from_file_location("validate_delivery", VALIDATOR_PATH)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


UNSET = object()


def make_atom(name, payload=b""):
    return struct.pack(">I4s", 8 + len(payload), name.encode("ascii")) + payload


def create_delivery(root, duration=UNSET, fps=30, total_frames=None,
                    xhs_dimensions=None, platforms=None):
    root.mkdir(parents=True, exist_ok=True)
    source_dir = root / "source"
    source_dir.mkdir(exist_ok=True)
    source_path = source_dir / "script.md"
    source_path.write_text("A short test script.\n", encoding="utf-8")
    outputs = {}
    selected_platforms = tuple(VALIDATOR.OUTPUTS) if platforms is None else tuple(platforms)
    for key in selected_platforms:
        width, height = VALIDATOR.OUTPUTS[key]
        if key == "xiaohongshu" and xhs_dimensions is not None:
            width, height = xhs_dimensions
        media_path = root / "outputs" / f"{key}.mp4"
        media_path.parent.mkdir(exist_ok=True)
        media_path.write_bytes(make_atom("moov") + make_atom("mdat", b"test"))
        outputs[key] = {
            "path": media_path.relative_to(root).as_posix(),
            "width": width,
            "height": height,
        }
    if total_frames is None:
        target = 120 if duration is UNSET else duration
        try:
            frame_count = Fraction(str(target)) * fps
            total_frames = int(frame_count) if frame_count.denominator == 1 else 3600
        except (ValueError, TypeError, ZeroDivisionError, OverflowError):
            total_frames = 3600
    manifest = {
        "schema_version": 1,
        "title": "Validator test",
        "slug": "validator-test",
        "fps": fps,
        "total_frames": total_frames,
        "audio": {
            "mode": "narrated",
            "master": "project/public/audio/master.wav",
        },
        "script": {
            "path": "source/script.md",
            "sha256": VALIDATOR.hashlib.sha256(source_path.read_bytes()).hexdigest(),
        },
        "outputs": outputs,
    }
    if platforms is not None:
        manifest["platforms"] = list(platforms)
        reports = {
            key: f"review/visual-qc-{key}/report.json"
            for key in selected_platforms
        }
        manifest["visual_qc"] = {"required": True, "reports": reports}
        for key, config in outputs.items():
            media_path = root / config["path"]
            digest = VALIDATOR.hashlib.sha256(media_path.read_bytes()).hexdigest()
            report_path = root / reports[key]
            report_path.parent.mkdir(parents=True, exist_ok=True)
            expected = total_frames
            scan = {
                "mode": "continuous_from_start",
                "every_frame": True,
                "no_input_seek": True,
                "decoded_frames": expected,
                "expected_frames": expected,
                "return_code": 0,
                "complete": True,
                "partial_frame_bytes": 0,
                "decode_error": None,
                "media_sha256_after": digest,
                "media_sha256_matches": True,
                "analysis": ["isolated_full_frame_jump", "stable_roi", "dark_roi"],
            }
            report_path.write_text(json.dumps({
                "schema_version": 1,
                "media_sha256": digest,
                "scan": scan,
                "flagged_frames": [],
                "flag_reviews": [],
            }), encoding="utf-8")
    if duration is not UNSET:
        manifest["duration_seconds"] = duration
    (root / "delivery.json").write_text(
        json.dumps(manifest, allow_nan=True), encoding="utf-8"
    )
    return manifest


def report_for(root):
    reports = sorted((root / "review").glob("media-validation-*.json"))
    with reports[-1].open(encoding="utf-8") as stream:
        return json.load(stream)


def run_validation(
    root,
    *,
    skip_decode=False,
    scan_source_enabled=False,
    source_only=False,
    probe_changes=None,
    decode_returncode=0,
):
    probe_changes = probe_changes or {}

    def fake_which(name):
        return f"/mock/{name}"

    def fake_run_command(args):
        if args[0].endswith("ffprobe"):
            key = Path(args[-1]).stem
            manifest = json.loads((root / "delivery.json").read_text(encoding="utf-8"))
            fps = manifest.get("fps", 30)
            target = manifest.get("duration_seconds", 120)
            if (not isinstance(target, (int, float)) or isinstance(target, bool)
                    or isinstance(target, float) and not math.isfinite(target)):
                target = 120
            target_text = str(target)
            frame_count = manifest.get("total_frames", int(Fraction(target_text) * fps))
            output_config = manifest.get("outputs", {}).get(key, {})
            width = output_config.get("width", VALIDATOR.OUTPUTS[key][0])
            height = output_config.get("height", VALIDATOR.OUTPUTS[key][1])
            video = {
                "codec_type": "video",
                "codec_name": "h264",
                "pix_fmt": "yuv420p",
                "width": width,
                "height": height,
                "r_frame_rate": f"{fps}/1",
                "avg_frame_rate": f"{fps}/1",
                "nb_read_frames": str(frame_count),
                "duration": target_text,
            }
            audio = {
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_rate": "48000",
                "channels": 2,
                "duration": target_text,
            }
            format_info = {"duration": target_text}
            key_changes = probe_changes.get(key, {})
            video.update(key_changes.get("video", {}))
            audio.update(key_changes.get("audio", {}))
            format_info.update(key_changes.get("format", {}))
            streams = [video]
            if not key_changes.get("omit_audio"):
                streams.append(audio)
            output = json.dumps({"streams": streams, "format": format_info})
            return subprocess.CompletedProcess(args, 0, output, "")
        return subprocess.CompletedProcess(args, decode_returncode, "", "mock decode error")

    stdout = io.StringIO()
    stderr = io.StringIO()
    with (
        patch.object(VALIDATOR.shutil, "which", fake_which),
        patch.object(VALIDATOR, "run_command", fake_run_command),
        contextlib.redirect_stdout(stdout),
        contextlib.redirect_stderr(stderr),
    ):
        exit_code = VALIDATOR.validate(
            root,
            skip_decode,
            scan_source_enabled=scan_source_enabled,
            source_only=source_only,
        )
    return exit_code, stdout.getvalue(), stderr.getvalue(), report_for(root)


class DeliveryDurationTests(unittest.TestCase):
    def test_default_and_declared_legacy_xhs_dimensions_match_media(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "default-delivery"
            manifest = create_delivery(root)
            self.assertEqual(
                (manifest["outputs"]["xiaohongshu"]["width"],
                 manifest["outputs"]["xiaohongshu"]["height"]),
                (2160, 3840),
            )
            exit_code, _, _, report = run_validation(root)
            self.assertEqual(exit_code, 0)
            self.assertEqual(report["outputs"]["xiaohongshu"]["checks"]["dimensions"], "PASS")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "legacy-delivery"
            create_delivery(root, xhs_dimensions=(1080, 1920))
            exit_code, _, _, report = run_validation(root)
            self.assertEqual(exit_code, 0)
            self.assertEqual(report["outputs"]["xiaohongshu"]["checks"]["manifest_dimensions"], "PASS")
            self.assertEqual(report["outputs"]["xiaohongshu"]["checks"]["dimensions"], "PASS")

    def test_declared_4k_xhs_rejects_legacy_sized_media(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "delivery"
            create_delivery(root)
            exit_code, _, _, report = run_validation(
                root,
                probe_changes={
                    "xiaohongshu": {"video": {"width": 1080, "height": 1920}}
                },
            )
            self.assertEqual(exit_code, 1)
            self.assertEqual(report["outputs"]["xiaohongshu"]["checks"]["dimensions"], "FAIL")

    def test_unsupported_or_partial_xhs_dimensions_fail_manifest_check(self):
        invalid_dimensions = ((1920, 1080), (1080, None), (2160.0, 3840))
        for dimensions in invalid_dimensions:
            with self.subTest(dimensions=dimensions), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "delivery"
                create_delivery(root)
                manifest_path = root / "delivery.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if dimensions[1] is None:
                    manifest["outputs"]["xiaohongshu"].pop("height")
                    manifest["outputs"]["xiaohongshu"]["width"] = dimensions[0]
                else:
                    manifest["outputs"]["xiaohongshu"]["width"] = dimensions[0]
                    manifest["outputs"]["xiaohongshu"]["height"] = dimensions[1]
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                exit_code, _, _, report = run_validation(root)
                self.assertEqual(exit_code, 1)
                self.assertEqual(report["checks"]["xiaohongshu_manifest_dimensions"], "FAIL")

    def test_missing_duration_defaults_to_120_seconds(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "delivery"
            manifest = create_delivery(root)
            exit_code, _, _, report = run_validation(root)
            self.assertEqual(exit_code, 0)
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["target_duration_seconds"], 120)
            self.assertEqual(report["outputs"]["bilibili"]["checks"]["counted_frames"], "PASS")
            self.assertNotIn("platforms", manifest)
            self.assertEqual(set(report["outputs"]), {"bilibili", "xiaohongshu"})

    def test_portrait_only_90_second_manifest_validates_one_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "portrait"
            create_delivery(
                root, duration=90, fps=60, total_frames=5_400,
                platforms=["xiaohongshu"],
            )
            exit_code, _, _, report = run_validation(root)
            self.assertEqual(exit_code, 0)
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(set(report["outputs"]), {"xiaohongshu"})
            self.assertEqual(report["target_duration_seconds"], 90)
            self.assertEqual(
                report["outputs"]["xiaohongshu"]["measurements"]["video"]["counted_frames"],
                "5400",
            )

    def test_invalid_explicit_platforms_and_mismatched_output_keys_fail_closed(self):
        for platforms in ([], ["unknown"], ["xiaohongshu", "xiaohongshu"]):
            with self.subTest(platforms=platforms), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "invalid"
                create_delivery(root)
                manifest_path = root / "delivery.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["platforms"] = platforms
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                exit_code, _, _, report = run_validation(root)
                self.assertEqual(exit_code, 1)
                self.assertEqual(report["checks"]["platforms"], "FAIL")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "mismatch"
            create_delivery(root)
            manifest_path = root / "delivery.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["platforms"] = ["xiaohongshu"]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            exit_code, _, _, report = run_validation(root)
            self.assertEqual(exit_code, 1)
            self.assertEqual(report["checks"]["output_platforms"], "FAIL")

    def test_180_seconds_uses_10800_frames_at_60_fps(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "delivery"
            create_delivery(root, duration=180, fps=60, total_frames=10800)
            exit_code, _, _, report = run_validation(root)
            self.assertEqual(exit_code, 0)
            self.assertEqual(report["target_duration_seconds"], 180)
            self.assertEqual(report["outputs"]["xiaohongshu"]["measurements"]["video"]["counted_frames"], "10800")

    def test_fractional_duration_is_preserved_and_validated(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "delivery"
            create_delivery(root, duration=120.5, fps=30, total_frames=3615)
            exit_code, _, _, report = run_validation(root)
            self.assertEqual(exit_code, 0)
            self.assertEqual(report["target_duration_seconds"], 120.5)
            self.assertEqual(report["outputs"]["bilibili"]["checks"]["video_duration"], "PASS")

    def test_rejects_non_number_non_finite_and_non_positive_targets(self):
        invalid_values = [True, float("nan"), float("inf"), float("-inf"), 0, -1, "120", None]
        for value in invalid_values:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "delivery"
                create_delivery(root, duration=value)
                exit_code, _, _, report = run_validation(root)
                self.assertEqual(exit_code, 1)
                self.assertEqual(report["checks"]["duration_seconds"], "FAIL")
                self.assertIsNone(report["target_duration_seconds"])

    def test_rejects_frame_and_sample_misaligned_targets(self):
        cases = [
            (120.01, "duration_frame_alignment", "FAIL"),
            (120.00001, "duration_sample_alignment", "FAIL"),
        ]
        for duration, check_name, expected_check in cases:
            with self.subTest(duration=duration), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "delivery"
                create_delivery(root, duration=duration)
                exit_code, _, _, report = run_validation(root)
                self.assertEqual(exit_code, 1)
                self.assertEqual(report["checks"][check_name], expected_check)
                if duration == 120.01:
                    self.assertEqual(report["checks"]["duration_sample_alignment"], "PASS")

    def test_wrong_size_duration_frame_count_audio_and_decode_fail(self):
        cases = [
            ({"bilibili": {"video": {"width": 1920}}}, "dimensions"),
            ({"bilibili": {"video": {"duration": "119"}}}, "video_duration"),
            ({"bilibili": {"video": {"nb_read_frames": "3599"}}}, "counted_frames"),
            ({"bilibili": {"audio": {"sample_rate": "44100"}}}, "audio_sample_rate"),
        ]
        for changes, check_name in cases:
            with self.subTest(check_name=check_name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "delivery"
                create_delivery(root)
                exit_code, _, _, report = run_validation(root, probe_changes=changes)
                self.assertEqual(exit_code, 1)
                self.assertEqual(report["outputs"]["bilibili"]["checks"][check_name], "FAIL")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "delivery"
            create_delivery(root)
            exit_code, _, _, report = run_validation(root, decode_returncode=1)
            self.assertEqual(exit_code, 1)
            self.assertEqual(report["outputs"]["bilibili"]["checks"]["strict_decode"], "FAIL")

    def test_skip_decode_stays_incomplete_and_nonzero(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "delivery"
            create_delivery(root)
            exit_code, _, _, report = run_validation(root, skip_decode=True)
            self.assertEqual(exit_code, 1)
            self.assertEqual(report["status"], "INCOMPLETE")
            self.assertEqual(report["outputs"]["bilibili"]["checks"]["strict_decode"], "SKIPPED")


class SourceScanTests(unittest.TestCase):
    def test_scanner_reports_only_narrow_typos_and_prunes_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            root.mkdir()
            source = root / "src.tsx"
            original = (
                'const a = "CASUAL DEPTH";\n'
                'const b = "casual-graph";\n'
                'const c = "MANIFLOD";\n'
                'const d = "MANFIOLD";\n'
                'const e = "MANIFOD";\n'
                'const f = "TELEMETERY";\n'
                'const good = "CASUAL tone; CAUSAL DEPTH; MANIFOLD";\n'
            )
            source.write_text(original, encoding="utf-8")
            excluded_names = [
                ".git", "node_modules", "out", "review", ".remotion", "bundle-cache",
                "dist", "build", "coverage", ".venv", "venv", ".cache", "__pycache__",
            ]
            for name in excluded_names:
                excluded = root / name
                excluded.mkdir()
                (excluded / "ignored.ts").write_text("MANIFLOD TELEMETERY\n", encoding="utf-8")

            outside = Path(temporary) / "outside"
            outside.mkdir()
            outside_file = outside / "escape.ts"
            outside_file.write_text("CASUAL DEPTH\n", encoding="utf-8")
            try:
                (root / "linked.ts").symlink_to(outside_file)
                (root / "linked-dir").symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")

            result = VALIDATOR.scan_source(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["files_scanned"], 1)
            self.assertEqual(
                [item["matched_token"] for item in result["matches"]],
                ["CASUAL DEPTH", "casual-graph", "MANIFLOD", "MANFIOLD", "MANIFOD", "TELEMETERY"],
            )
            self.assertEqual(result["matches"][0]["suggestion"], "CAUSAL DEPTH")
            self.assertEqual(result["matches"][1]["suggestion"], "CAUSAL-graph")
            self.assertTrue(all("source_line" not in item for item in result["matches"]))
            self.assertEqual(source.read_text(encoding="utf-8"), original)

    def test_empty_and_invalid_utf8_scans_are_incomplete(self):
        with tempfile.TemporaryDirectory() as temporary:
            empty = Path(temporary) / "empty"
            empty.mkdir()
            self.assertEqual(VALIDATOR.scan_source(empty)["status"], "INCOMPLETE")

            bad = Path(temporary) / "bad"
            bad.mkdir()
            (bad / "invalid.json").write_bytes(b"\xff")
            result = VALIDATOR.scan_source(bad)
            self.assertEqual(result["status"], "INCOMPLETE")
            self.assertEqual(result["files_scanned"], 1)
            self.assertEqual(result["read_errors"], [{"file": "invalid.json", "error": "invalid UTF-8"}])

    def test_normal_scan_integrates_failures_and_incomplete_status(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "delivery"
            create_delivery(root)
            (root / "project.ts").write_text("const typo = 'TELEMETERY';\n", encoding="utf-8")
            exit_code, _, _, report = run_validation(root, scan_source_enabled=True)
            self.assertEqual(exit_code, 1)
            self.assertEqual(report["source_scan"]["status"], "FAIL")
            self.assertEqual(report["status"], "FAIL")
            self.assertTrue(any("TELEMETERY" in item for item in report["failures"]))

    def test_source_only_passes_without_manifest_or_media(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source-workdir"
            root.mkdir()
            (root / "scene.ts").write_text("const tone = 'CASUAL';\n", encoding="utf-8")
            exit_code, stdout, _, report = run_validation(root, source_only=True)
            self.assertEqual(exit_code, 0)
            self.assertIn("Media validation: NOT RUN", stdout)
            self.assertEqual(report["scope"], "source-only")
            self.assertEqual(report["status"], "INCOMPLETE")
            self.assertEqual(report["media_validation"], "NOT_RUN")
            self.assertEqual(report["source_scan"]["status"], "PASS")
            self.assertFalse((root / "delivery.json").exists())

    def test_source_only_with_typo_is_nonzero_and_incomplete(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source-workdir"
            root.mkdir()
            (root / "scene.ts").write_text("const typo = 'MANIFOD';\n", encoding="utf-8")
            exit_code, stdout, _, report = run_validation(root, source_only=True)
            self.assertEqual(exit_code, 1)
            self.assertIn("Media validation: NOT RUN", stdout)
            self.assertEqual(report["status"], "INCOMPLETE")
            self.assertEqual(report["source_scan"]["status"], "FAIL")

    def test_source_only_scan_with_no_source_files_is_nonzero(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "empty-workdir"
            root.mkdir()
            exit_code, _, _, report = run_validation(root, source_only=True)
            self.assertEqual(exit_code, 1)
            self.assertEqual(report["status"], "INCOMPLETE")
            self.assertEqual(report["source_scan"]["status"], "INCOMPLETE")

    def test_source_only_and_skip_decode_are_mutually_exclusive(self):
        old_argv = sys.argv
        try:
            sys.argv = [str(VALIDATOR_PATH), ".", "--source-only", "--skip-decode"]
            with self.assertRaises(SystemExit) as raised:
                with contextlib.redirect_stderr(io.StringIO()):
                    VALIDATOR.parse_args()
            self.assertEqual(raised.exception.code, 2)
        finally:
            sys.argv = old_argv


if __name__ == "__main__":
    unittest.main()
