"""Measure encoded previews and collect their actual 360px frames."""
from pathlib import Path
import hashlib
import json
import subprocess
import wave
import numpy as np
from PIL import Image, ImageDraw

P = Path(__file__).resolve().parents[1]
R = P.parent / 'review'
Q = R / 'native-preview-qa'
Q.mkdir(exist_ok=False)
index = json.loads((R / 'native-preview-index.json').read_text())
with wave.open(str(P / 'public/audio/master.wav'), 'rb') as stream:
    master = np.frombuffer(stream.readframes(stream.getnframes()), dtype='<i2').reshape(-1, 2).astype(float)
records = []
all_images = []
for entry in index['previews']:
    movie = P.parent / entry['path']
    start, end = entry['absoluteFramesInclusive']
    count = end - start + 1
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(movie)]))
    v = next(x for x in probe['streams'] if x['codec_type'] == 'video')
    assert (v['width'], v['height'], v['r_frame_rate'], int(v['nb_frames'])) == (2160, 3840, '60/1', count)
    audio = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(movie), '-map', '0:a:0', '-ar', '48000', '-ac', '2', '-f', 's16le', '-'])
    decoded = np.frombuffer(audio, dtype='<i2').reshape(-1, 2).astype(float)[:count * 800]
    reference = master[start * 800:(end + 1) * 800]
    assert len(decoded) == len(reference)
    correlation = float(np.corrcoef(reference.ravel(), decoded.ravel())[0, 1])
    assert correlation > .99, (start, correlation)
    frames = [0, count // 3, 2 * count // 3, count - 1] if start != 4800 else [59, 60, 89, 90, 97, 104, 105, 179]
    folder = Q / str(start)
    folder.mkdir()
    select = '+'.join(f'eq(n,{f})' for f in frames)
    subprocess.run(['ffmpeg', '-v', 'error', '-i', str(movie), '-vf', f'select=\'{select}\',scale=360:640',
                    '-fps_mode', 'passthrough', str(folder / '%03d.png')], check=True)
    images = sorted(folder.glob('*.png'))
    assert len(images) == len(frames)
    all_images.extend(zip(images, [start + f for f in frames]))
    records.append({'path': entry['path'], 'absoluteFramesInclusive': [start, end], 'frames': count,
                    'nativeSize': [2160, 3840], 'aacPcmCorrelationAtExactGlobalOffset': correlation,
                    'sha256': hashlib.sha256(movie.read_bytes()).hexdigest(), 'globalReviewFrames': [start + f for f in frames]})
for panel, offset in enumerate(range(0, len(all_images), 8), 1):
    page = Image.new('RGB', (1440, 1320), '#101318')
    draw = ImageDraw.Draw(page)
    for i, (path, frame) in enumerate(all_images[offset:offset+8]):
        x, y = i % 4 * 360, i // 4 * 660
        page.paste(Image.open(path).convert('RGB'), (x, y))
        draw.text((x + 8, y + 642), f'F{frame} / {frame/60:.3f}s', fill='white')
    page.save(Q / f'contact-{panel}.jpg', quality=92)
(Q / 'report.json').write_text(json.dumps({'status': 'MEASUREMENTS_PASS', 'previews': records,
    'humanListening': 'PENDING', 'modelFrameReview': 'see acceptance.md',
    'scope': 'Exact native spec and audio-clock check; representative actual encoded frames collected. No pronunciation or human experience claim.'}, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': 'MEASUREMENTS_PASS', 'previews': len(records), 'phoneFrames': len(all_images),
                  'minimumAacPcmCorrelation': min(x['aacPcmCorrelationAtExactGlobalOffset'] for x in records)}, indent=2))
