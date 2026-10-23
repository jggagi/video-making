"""Serial native previews using the current verified real PCM master."""
from pathlib import Path
import subprocess
import hashlib
import json

P = Path(__file__).resolve().parents[1]
R = P.parent / 'review'
ranges = [(60, 239), (3600, 3959), (4800, 4979)]
records = []
for start, end in ranges:
    movie = R / f'motion-{start}-{end}.mp4'
    subprocess.run(['node', str(P / 'scripts/render.mjs'), 'preview', str(start), str(end)], check=True)
    records.append({'path': str(movie.relative_to(P.parent)), 'absoluteFramesInclusive': [start, end],
                    'sha256': hashlib.sha256(movie.read_bytes()).hexdigest(), 'bytes': movie.stat().st_size,
                    'audio': 'Current verified master; same absolute frame clock'})
(R / 'native-preview-index.json').write_text(json.dumps({'previews': records,
    'masterSha256': hashlib.sha256((P / 'public/audio/master.wav').read_bytes()).hexdigest(),
    'scope': 'Native encoded previews, not continuous human listening acceptance'}, ensure_ascii=False, indent=2) + '\n')
