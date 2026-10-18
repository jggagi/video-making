"""Archive contract tests using tiny files and simulated FFprobe metadata; no real render."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'build-archive-catalog.py'
spec = importlib.util.spec_from_file_location('build_archive_catalog', SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def fake_probe(path):
    if path.parent.name == 'B站':
        width, height = 3840, 2160
    elif path.parent.name == '小红书':
        width, height = 1080, 1920
    else:
        width, height = 640, 360
    return {
        'width': width,
        'height': height,
        'fps': '60/1',
        'frames': '7200',
        'video_duration_seconds': 120.0,
        'container_duration_seconds': 120.011,
    }


def create_work(root, directory_name='森林 时间 🌲-v01', manifest_slug=None, include_xhs=True):
    delivery = root / 'deliveries' / directory_name
    (delivery / 'B站').mkdir(parents=True)
    (delivery / '小红书').mkdir()
    (delivery / 'project' / 'assets').mkdir(parents=True)
    (delivery / 'B站' / 'final.mp4').write_bytes(b'bilibili')
    if include_xhs:
        (delivery / '小红书' / 'final.mp4').write_bytes(b'xiaohongshu')
    (delivery / 'project' / 'assets' / 'reference.mp4').write_bytes(b'reference')
    (delivery / 'project' / 'editable.zip').write_bytes(b'zip-data')
    manifest = {
        'schema_version': 1,
        'duration_seconds': 120,
        'slug': manifest_slug if manifest_slug is not None else directory_name,
        'title': '森林 时间 🌲',
        'outputs': {
            'bilibili': {'path': 'B站/final.mp4'},
            'xiaohongshu': {'path': '小红书/final.mp4'},
        },
    }
    (delivery / 'delivery.json').write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
    return delivery


class ArchiveCatalogTests(unittest.TestCase):
    def run_main(self, root):
        with patch.object(mod, 'probe', side_effect=fake_probe), patch.object(sys, 'argv', ['build-archive-catalog.py', '--root', str(root)]), contextlib.redirect_stdout(io.StringIO()):
            mod.main()

    def test_chinese_spaced_slug_catalog_and_project_video_classification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            delivery = create_work(root)
            works = mod.discover(root)
            self.assertEqual(len(works), 1)
            work = works[0]
            expected_hash = mod.hashlib.sha256(work['id'].encode('utf-8')).hexdigest()[:12]
            self.assertEqual(work['release_tag'].rsplit('-', 1)[-1], expected_hash)
            self.assertRegex(work['release_tag'], r'^film-[A-Za-z0-9-]+-[0-9a-f]{12}$')
            self.assertNotEqual(work['release_tag'], mod._release_tag('树林 时间 🌲-v01'))
            self.assertEqual(work['final_output_paths'], {
                'B站': f'deliveries/{work["id"]}/B站/final.mp4',
                '小红书': f'deliveries/{work["id"]}/小红书/final.mp4',
            })
            with patch.object(mod, 'probe', side_effect=fake_probe):
                assets = [mod.make_asset(root, work, path) for path in work['files']]
            by_path = {asset['path']: asset for asset in assets}
            self.assertEqual(by_path[f'deliveries/{work["id"]}/B站/final.mp4']['platform'], 'B站')
            self.assertEqual(by_path[f'deliveries/{work["id"]}/小红书/final.mp4']['platform'], '小红书')
            self.assertEqual(by_path[f'deliveries/{work["id"]}/project/assets/reference.mp4']['platform'], '工程')
            self.run_main(root)
            catalog = json.loads((root / 'archive' / 'catalog.json').read_text(encoding='utf-8'))
            self.assertEqual(catalog['generated_by'], mod.GENERATED_BY)
            record = json.loads((delivery / 'archive.json').read_text(encoding='utf-8'))
            self.assertEqual(record['generated_by'], mod.GENERATED_BY)
            for generated_md in (
                root / 'deliveries' / 'README.md',
                delivery / 'README.md',
                delivery / 'B站' / 'README.md',
                delivery / '小红书' / 'README.md',
            ):
                self.assertEqual(generated_md.read_text(encoding='utf-8').splitlines()[0], mod.GENERATED_MARKER)
            archived_paths = {asset['path'] for asset in record['assets']}
            self.assertIn(f'deliveries/{work["id"]}/project/assets/reference.mp4', archived_paths)
            bili_index = (delivery / 'B站' / 'README.md').read_text(encoding='utf-8')
            self.assertIn('final.mp4', bili_index)
            self.assertNotIn('reference.mp4', bili_index)

    def test_bundle_prefix_in_work_slug_does_not_hide_final_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_work(root, directory_name='bundle-forest-v01')
            work = mod.discover(root)[0]
            self.assertEqual(len([path for path in work['files'] if path.suffix == '.mp4']), 3)
            self.assertEqual(set(work['final_output_paths']), {'B站', '小红书'})

    def test_explicit_xiaohongshu_output_gets_dimension_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_work(root)
            work = mod.discover(root)[0]
            xhs = next(path for path in work['files'] if path.parent.name == '小红书')
            with patch.object(mod, 'probe', return_value={
                'width': 3840, 'height': 2160, 'fps': '60/1', 'frames': '7200',
                'video_duration_seconds': 120.0, 'container_duration_seconds': 120.011,
            }):
                with self.assertRaisesRegex(ValueError, 'wrong dimensions'):
                    mod.make_asset(root, work, xhs)

    def test_mismatched_slug_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_work(root, manifest_slug='different-slug')
            with self.assertRaisesRegex(ValueError, 'exactly match its directory name'):
                mod.discover(root)

    def test_missing_xiaohongshu_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_work(root, include_xhs=False)
            with self.assertRaisesRegex(ValueError, 'existing regular nonsymlink file'):
                mod.discover(root)

    def test_duplicate_historical_and_new_work_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'out').mkdir()
            (root / 'out' / 'historic.mp4').write_bytes(b'history')
            create_work(root, directory_name='lanting')
            with self.assertRaisesRegex(ValueError, 'collides with a historical work'):
                mod.discover(root)

    def test_historical_identity_is_reserved_even_without_local_historical_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_work(root, directory_name='lanting')
            with self.assertRaisesRegex(ValueError, 'collides with a historical work'):
                mod.discover(root)

    def test_duplicate_release_tag_is_rejected(self):
        a = {'id': 'first', 'release_tag': 'same-tag'}
        b = {'id': 'second', 'release_tag': 'same-tag'}
        with self.assertRaisesRegex(ValueError, 'Duplicate Release tag'):
            mod._validate_unique_work_ids_and_tags([a, b])

    def test_unmarked_custom_readme_is_preserved_and_stops_before_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            delivery = create_work(root)
            custom_readme = delivery / '小红书' / 'README.md'
            custom_readme.write_text('# My notes\nDo not replace\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Refusing to overwrite unmarked Markdown'):
                self.run_main(root)
            self.assertEqual(custom_readme.read_text(encoding='utf-8'), '# My notes\nDo not replace\n')
            self.assertFalse((delivery / 'README.md').exists())
            self.assertFalse((root / 'archive' / 'catalog.json').exists())

    def test_non_direct_output_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            delivery = create_work(root)
            manifest_path = delivery / 'delivery.json'
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            manifest['outputs']['bilibili']['path'] = 'project/assets/final.mp4'
            manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'directly inside B站'):
                mod.discover(root)


if __name__ == '__main__':
    unittest.main(verbosity=2)
