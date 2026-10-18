"""Tests for fresh dual-platform delivery scaffolding."""
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
    / "dual-platform-video"
    / "scripts"
    / "init_delivery.py"
)
spec = importlib.util.spec_from_file_location("init_delivery", SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class DeliveryInitializationTests(unittest.TestCase):
    def manifest(self, duration=mod.DEFAULT_DURATION_SECONDS, fps=60):
        return mod.build_manifest(
            slug="test-film",
            title="Test film",
            fps=fps,
            audio_mode="narrated",
            script_bytes=b"source script\n",
            duration_seconds=duration,
        )

    def args(self, output_root, script, duration=mod.DEFAULT_DURATION_SECONDS):
        return mod.argparse.Namespace(
            output_root=output_root,
            slug="test-film",
            title="Test film",
            script=script,
            fps=60,
            audio_mode="narrated",
            duration_seconds=duration,
        )

    def test_default_duration_preserves_existing_manifest_and_filenames(self):
        manifest = self.manifest()
        self.assertEqual(manifest["duration_seconds"], 120)
        self.assertEqual(manifest["total_frames"], 7_200)
        self.assertEqual(
            manifest["outputs"]["bilibili"]["path"],
            "B站/test-film-bilibili-120s-4k.mp4",
        )
        self.assertEqual(
            manifest["outputs"]["xiaohongshu"]["path"],
            "小红书/test-film-xiaohongshu-120s-portrait.mp4",
        )

    def test_180_and_fractional_durations_use_matching_frame_counts(self):
        long_manifest = self.manifest(180)
        self.assertEqual(long_manifest["duration_seconds"], 180)
        self.assertEqual(long_manifest["total_frames"], 10_800)
        self.assertIn("180s", long_manifest["outputs"]["bilibili"]["path"])

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
