"""Tests for fresh platform-selectable delivery scaffolding."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "xiaohongshu-video"
    / "scripts"
    / "init_delivery.py"
)
spec = importlib.util.spec_from_file_location("init_delivery", SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class DeliveryInitializationTests(unittest.TestCase):
    def manifest(self, duration=mod.DEFAULT_DURATION_SECONDS, fps=60,
                 platforms=None):
        arguments = dict(
            slug="test-film",
            title="Test film",
            fps=fps,
            audio_mode="narrated",
            script_bytes=b"source script\n",
            duration_seconds=duration,
        )
        if platforms is not None:
            arguments["platforms"] = platforms
        return mod.build_manifest(**arguments)

    def args(self, output_root, script, duration=mod.DEFAULT_DURATION_SECONDS,
             platforms=None):
        arguments = dict(
            output_root=output_root,
            slug="test-film",
            title="Test film",
            script=script,
            fps=60,
            audio_mode="narrated",
            duration_seconds=duration,
        )
        if platforms is not None:
            arguments["platforms"] = list(platforms)
        return mod.argparse.Namespace(**arguments)

    def test_default_manifest_is_xiaohongshu_only_at_120_seconds(self):
        manifest = self.manifest()
        self.assertEqual(manifest["platforms"], ["xiaohongshu"])
        self.assertEqual(manifest["duration_seconds"], 120)
        self.assertEqual(manifest["total_frames"], 7_200)
        self.assertEqual(set(manifest["outputs"]), {"xiaohongshu"})
        self.assertEqual(
            (manifest["outputs"]["xiaohongshu"]["width"],
             manifest["outputs"]["xiaohongshu"]["height"]),
            (2160, 3840),
        )
        self.assertEqual(
            manifest["outputs"]["xiaohongshu"]["path"],
            "小红书/test-film-xiaohongshu-120s-portrait.mp4",
        )
        self.assertEqual(
            set(manifest["visual_qc"]["reports"]), {"xiaohongshu"}
        )

    def test_explicit_dual_platform_manifest_preserves_both_4k_outputs(self):
        manifest = self.manifest(platforms=mod.PLATFORMS)
        self.assertEqual(manifest["platforms"], ["bilibili", "xiaohongshu"])
        self.assertEqual(
            (manifest["outputs"]["bilibili"]["width"],
             manifest["outputs"]["bilibili"]["height"]),
            (3840, 2160),
        )
        self.assertEqual(
            manifest["outputs"]["bilibili"]["path"],
            "B站/test-film-bilibili-120s-4k.mp4",
        )
        self.assertEqual(
            (manifest["outputs"]["xiaohongshu"]["width"],
             manifest["outputs"]["xiaohongshu"]["height"]),
            (2160, 3840),
        )

    def test_180_and_fractional_durations_use_matching_frame_counts(self):
        long_manifest = self.manifest(180)
        self.assertEqual(long_manifest["duration_seconds"], 180)
        self.assertEqual(long_manifest["total_frames"], 10_800)
        self.assertIn("180s", long_manifest["outputs"]["xiaohongshu"]["path"])

        fractional_manifest = self.manifest(120.5)
        self.assertEqual(fractional_manifest["duration_seconds"], 120.5)
        self.assertEqual(fractional_manifest["total_frames"], 7_230)
        self.assertIn("120.5s", fractional_manifest["outputs"]["xiaohongshu"]["path"])

    def test_cli_duration_defaults_to_120_and_accepts_override(self):
        base = [
            "init_delivery.py", "--output-root", "deliveries", "--slug", "demo",
            "--title", "Demo", "--script", "script.md",
        ]
        with patch.object(sys, "argv", base):
            self.assertEqual(mod.parse_args().duration_seconds, 120)
        with patch.object(sys, "argv", base + ["--duration-seconds", "180"]):
            self.assertEqual(mod.parse_args().duration_seconds, 180)
        with patch.object(sys, "argv", base):
            self.assertEqual(mod.parse_args().platforms, ["xiaohongshu"])
        with patch.object(sys, "argv", base + ["--platforms", "xiaohongshu"]):
            self.assertEqual(mod.parse_args().platforms, ["xiaohongshu"])

    def test_cli_default_creates_only_xiaohongshu_directory_output_and_qc_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "script.md"
            script.write_text("default CLI source\n", encoding="utf-8")
            output_root = root / "deliveries"
            argv = [
                "init_delivery.py", "--output-root", str(output_root),
                "--slug", "test-film", "--title", "Test film",
                "--script", str(script),
            ]
            with patch.object(sys, "argv", argv):
                self.assertEqual(mod.main(), 0)

            target = output_root / "test-film"
            self.assertTrue((target / "小红书").is_dir())
            self.assertFalse((target / "B站").exists())
            manifest = json.loads(
                (target / "delivery.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["platforms"], ["xiaohongshu"])
            self.assertEqual(set(manifest["outputs"]), {"xiaohongshu"})
            self.assertEqual(
                set(manifest["visual_qc"]["reports"]), {"xiaohongshu"}
            )

    def test_create_delivery_without_platforms_defaults_to_xiaohongshu(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "script.md"
            script.write_text("default helper source\n", encoding="utf-8")
            target = mod.create_delivery(self.args(root / "deliveries", script))

            self.assertTrue((target / "小红书").is_dir())
            self.assertFalse((target / "B站").exists())
            manifest = json.loads(
                (target / "delivery.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["platforms"], ["xiaohongshu"])
            self.assertEqual(set(manifest["outputs"]), {"xiaohongshu"})
            self.assertEqual(
                set(manifest["visual_qc"]["reports"]), {"xiaohongshu"}
            )

    def test_explicit_dual_and_bilibili_only_delivery_initialization_still_work(self):
        cases = (
            (mod.PLATFORMS, {"B站", "小红书"}, {"bilibili", "xiaohongshu"}),
            (("bilibili",), {"B站"}, {"bilibili"}),
        )
        for platforms, expected_directories, expected_keys in cases:
            with self.subTest(platforms=platforms), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                script = root / "script.md"
                script.write_text("explicit selection source\n", encoding="utf-8")
                target = mod.create_delivery(
                    self.args(root / "deliveries", script, platforms=platforms)
                )
                created_directories = {
                    name for name in ("B站", "小红书") if (target / name).is_dir()
                }
                manifest = json.loads(
                    (target / "delivery.json").read_text(encoding="utf-8")
                )
                self.assertEqual(created_directories, expected_directories)
                self.assertEqual(set(manifest["outputs"]), expected_keys)
                self.assertEqual(
                    set(manifest["visual_qc"]["reports"]), expected_keys
                )
                self.assertEqual(set(manifest["platforms"]), expected_keys)

    def test_portrait_only_90_second_manifest_and_initializer(self):
        manifest = self.manifest(90, platforms=["xiaohongshu"])
        self.assertEqual(manifest["platforms"], ["xiaohongshu"])
        self.assertEqual(manifest["total_frames"], 5_400)
        self.assertEqual(set(manifest["outputs"]), {"xiaohongshu"})
        self.assertEqual(set(manifest["visual_qc"]["reports"]), {"xiaohongshu"})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "script.md"
            script.write_text("portrait source\n", encoding="utf-8")
            target = mod.create_delivery(
                self.args(root / "deliveries", script, duration=90,
                          platforms=["xiaohongshu"])
            )
            self.assertTrue((target / "小红书").is_dir())
            self.assertFalse((target / "B站").exists())
            created = json.loads((target / "delivery.json").read_text(encoding="utf-8"))
            self.assertEqual(created["total_frames"], 5_400)
            self.assertEqual(set(created["visual_qc"]["reports"]), {"xiaohongshu"})

    def test_platform_selection_rejects_empty_duplicate_unknown_and_nonlist(self):
        for platforms in ([], ["xiaohongshu", "xiaohongshu"], ["other"], "xiaohongshu"):
            with self.subTest(platforms=platforms), self.assertRaises(mod.InputError):
                self.manifest(platforms=platforms)

    def test_invalid_duration_values_are_rejected(self):
        invalid = (True, "120", None, float("nan"), float("inf"), 0, -1, 120.01, 0.00001)
        for duration in invalid:
            with self.subTest(duration=duration):
                with self.assertRaises(mod.InputError):
                    self.manifest(duration)

    def test_invalid_duration_does_not_create_output_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "script.md"
            script.write_bytes(b"a valid source script\n")
            output_root = root / "deliveries"
            with self.assertRaises(mod.InputError):
                mod.create_delivery(self.args(output_root, script, duration=120.01))
            self.assertFalse(output_root.exists())

    def test_source_bytes_hash_and_existing_target_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "script.md"
            source_bytes = "原文\r\nsecond line\n".encode("utf-8")
            script.write_bytes(source_bytes)
            output_root = root / "deliveries"
            target = mod.create_delivery(self.args(output_root, script, duration=180))
            self.assertEqual((target / "source" / "script.md").read_bytes(), source_bytes)
            manifest = json.loads((target / "delivery.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["script"]["sha256"], hashlib.sha256(source_bytes).hexdigest())
            self.assertEqual(manifest["total_frames"], 10_800)

            script.write_bytes(b"replacement script\n")
            with self.assertRaisesRegex(mod.InputError, "already exists"):
                mod.create_delivery(self.args(output_root, script, duration=120))
            self.assertEqual((target / "source" / "script.md").read_bytes(), source_bytes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
