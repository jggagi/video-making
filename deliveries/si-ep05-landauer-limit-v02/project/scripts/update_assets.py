#!/usr/bin/env python3
"""Record EP05's shared procedural assets and existing audio without generation."""
from pathlib import Path
import hashlib
import json

P = Path(__file__).resolve().parents[1]
def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()

assets = []
for path in sorted((P / 'src').glob('*')):
    if path.suffix in {'.ts', '.tsx'}:
        assets.append({'id': 'procedural-' + path.stem, 'kind': 'frame_driven_analytical_geometry', 'path': str(path.relative_to(P)), 'sha256': digest(path), 'seed': 'fixed indexed trigonometric sequences; shared frame clock', 'generation_provider': 'local source; no image generation'})
provider = json.loads((P / 'public/audio/cache-manifest.json').read_text())
for sid, record in sorted(provider['segments'].items()):
    for role in ['raw', 'canonical', 'cue']:
        path = P / record[role + '_path']
        assets.append({'id': sid + '-' + role, 'kind': 'narration', 'path': str(path.relative_to(P)), 'sha256': digest(path), 'cache_key': record['cache_key'], 'tts_phonetic_text': record['tts_phonetic_text'], 'settings': provider['settings'], 'reported_model': record.get('effective_model', record.get('effectiveModel', 'see provider manifest')), 'shared_by': ['Landscape4K', 'PortraitVertical']})
for name in ['master', 'narration', 'score', 'sfx', 'thermal']:
    path = P / f'public/audio/{name}.wav'
    assets.append({'id': 'audio-' + name, 'kind': 'shared_PCM' if name == 'master' else 'reproducible_audio_stem', 'path': str(path.relative_to(P)), 'sha256': digest(path), 'sample_rate': 48000, 'channels': 2, 'samples_per_channel': 5760000, 'shared_by': ['Landscape4K', 'PortraitVertical'], 'provenance': 'public/audio/mix-settings.json'})
out = {'schema_version': 1, 'reuse_policy': 'One source, one narration cache, one PCM master, two native layouts. No platform-specific generation.', 'assets': assets, 'fonts': [{'family': 'PingFang SC / Hiragino Sans GB', 'source': 'installed macOS system fonts, locally resolved', 'redistributed': False}, {'family': 'Menlo / Arial', 'source': 'installed macOS fonts', 'redistributed': False}], 'physics_boundaries': 'scientific-notes.md', 'audio_phrase_alignment': 'measured cue spans; estimated phrase boundaries; no ASR upload'}
(P / 'assets-manifest.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
print(f'Recorded {len(assets)} shared assets; no generation calls.')
