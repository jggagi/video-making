"""Simulated GitHub visibility responses; no network or remote mutations."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "skills/dual-platform-video/scripts/upload_releases.py"
spec = importlib.util.spec_from_file_location("release_uploader", SCRIPT)
uploader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uploader)


class ReleaseVisibilityTests(unittest.TestCase):
    def test_new_draft_can_be_temporarily_absent(self):
        draft = {"draft": True}
        with patch.object(uploader, "get_release", side_effect=[None, None, draft]) as lookup, \
                patch.object(uploader.time, "sleep") as sleep:
            self.assertEqual(uploader.wait_for_release("fixture"), draft)
            self.assertEqual(lookup.call_count, 3)
            self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])

    def test_publish_waits_for_public_state(self):
        with patch.object(uploader, "get_release", side_effect=[{"draft": True}, {"draft": False}]), \
                patch.object(uploader.time, "sleep"):
            self.assertEqual(uploader.wait_for_release("fixture", published=True), {"draft": False})

    def test_missing_release_stops_after_bounded_reads(self):
        with patch.object(uploader, "get_release", return_value=None) as lookup, \
                patch.object(uploader.time, "sleep") as sleep:
            self.assertIsNone(uploader.wait_for_release("fixture"))
            self.assertEqual(lookup.call_count, 4)
            self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2, 4])

    def test_authentication_failure_is_not_retried(self):
        with patch.object(uploader, "get_release", side_effect=uploader.UploadError("authentication failed")) as lookup, \
                patch.object(uploader.time, "sleep"):
            with self.assertRaises(uploader.UploadError):
                uploader.wait_for_release("fixture")
            self.assertEqual(lookup.call_count, 1)

    def test_by_tag_404_finds_existing_draft_without_creation(self):
        draft = {"id": 1, "tag_name": "fixture", "draft": True, "assets": [],
                 "html_url": "https://github.com/jggagi/video-making/releases/tag/untagged-fixture"}
        responses = [subprocess.CompletedProcess([], 1, "", "gh: Not Found (HTTP 404)"),
                     subprocess.CompletedProcess([], 0, json.dumps([[draft]]), "")]
        with patch.object(uploader, "run_gh", side_effect=responses) as gh:
            self.assertEqual(uploader.get_release("fixture"), draft)
            self.assertEqual(gh.call_count, 2)
            for call in gh.call_args_list:
                self.assertEqual(call.args[0][0], "api")
                self.assertNotIn("POST", call.args[0])


if __name__ == "__main__":
    unittest.main()
