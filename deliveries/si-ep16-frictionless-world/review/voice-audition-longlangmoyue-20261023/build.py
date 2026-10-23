"""Reuse the verified previous audition builder without changing historical files."""
from pathlib import Path
import hashlib
import importlib.util

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / 'voice-audition-qwen30plus-20261023' / 'build.py'
EXPECTED_SOURCE_SHA256 = 'aa619d425777ea6ffec05d3c6da8b3a4a2a43eaf87bf8afe64ebcdee49e17354'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == EXPECTED_SOURCE_SHA256
spec = importlib.util.spec_from_file_location('ep16_audition_builder', SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.HERE = HERE
m.PROJECT = HERE.parents[1] / 'project'
m.OUTPUT_DIR = HERE
m.NORMALIZED_DIR = HERE / 'normalized'
for name, leaf in [('QWEN_MANIFEST_PATH','provider-manifest.json'),('PLAN_PATH','plan.json'),('QA_PATH','qa.json'),('KEY_PATH','comparison-key.json'),('README_PATH','README.md')]:
    setattr(m, name, HERE / leaf)
m.COSY_MANIFEST_PATH = m.PROJECT / 'public/audio/provider-manifest.json'
if __name__ == '__main__':
    raise SystemExit(m.main())
