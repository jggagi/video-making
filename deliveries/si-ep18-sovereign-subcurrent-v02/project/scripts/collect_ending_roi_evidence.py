"""Collect every flagged ending HUD ROI plus neighbor identity; never auto-clear flags."""
from pathlib import Path
import csv
import hashlib
import io
import json
import subprocess

import numpy as np
from PIL import Image, ImageDraw

WORK = Path(__file__).resolve().parents[2]
REVIEW = WORK / 'review'
REPORT = REVIEW / 'visual-qc-xiaohongshu/report.json'
doc = json.loads(REPORT.read_text())
flags = doc['flagged_frames']
assert [item['frame'] for item in flags] == list(range(4860, 5400))
assert all(set(item['reasons']) <= {'stable_roi_template_outlier', 'stable_roi_consecutive_outlier'} for item in flags)
assert doc['scan']['config']['stable_roi_normalized_xywh'] == [0.055, 0.09, 0.73, 0.066]
movie = WORK / json.loads((WORK / 'delivery.json').read_text())['outputs']['xiaohongshu']['path']
assert hashlib.sha256(movie.read_bytes()).hexdigest() == doc['media_sha256']
out = REVIEW / 'ending-roi-evidence'
out.mkdir(exist_ok=False)
command = ['ffmpeg', '-v', 'error', '-threads', '2', '-i', str(movie), '-an', '-vf', r'select=gte(n\,4859),scale=360:640:flags=bilinear', '-vsync', '0', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-']
process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
patches, full = {}, {}
frame_bytes = 360 * 640 * 3
frame = 4859
while True:
    data = bytearray()
    while len(data) < frame_bytes:
        block = process.stdout.read(frame_bytes - len(data))
        if not block:
            break
        data.extend(block)
    if not data:
        break
    assert len(data) == frame_bytes
    image = Image.frombytes('RGB', (360, 640), bytes(data))
    patches[frame] = image.crop((19, 57, 283, 100))
    if frame in (4859, 4860, 4861, 5010, 5160, 5398, 5399):
        full[frame] = image
    frame += 1
assert process.wait() == 0 and frame == 5400
patch_hashes = {f: hashlib.sha256(im.tobytes()).hexdigest() for f, im in patches.items()}
rows = []
for f in range(4860, 5400):
    pixels = np.asarray(patches[f])
    # This bounded proof establishes the exact ROI cause, not whole-frame visual quality.
    assert int(pixels.max()) <= 20, (f, int(pixels.max()))
    rows.append({'frame': f, 'roi_max_rgb': int(pixels.max()), 'roi_sha256': patch_hashes[f], 'previous_roi_sha256': patch_hashes[f-1], 'next_roi_sha256': patch_hashes.get(f+1, 'MEDIA_END'), 'sheet': f'roi-{(f-4860)//90+1:02}.png'})
for sheet in range(6):
    canvas = Image.new('RGB', (9*272, 10*65), '#222222')
    draw = ImageDraw.Draw(canvas)
    for offset in range(90):
        f = 4860 + sheet*90 + offset
        x, y = offset % 9 * 272, offset // 9 * 65
        draw.text((x+3, y+2), str(f), fill='white')
        canvas.paste(patches[f], (x+3, y+18))
    canvas.save(out/f'roi-{sheet+1:02}.png')
canvas = Image.new('RGB', (360*4, 660*2), '#181818')
draw = ImageDraw.Draw(canvas)
for index, (f, im) in enumerate(full.items()):
    x, y = index % 4 * 360, index // 4 * 660
    canvas.paste(im, (x, y)); draw.text((x+5, y+643), str(f), fill='white')
canvas.save(out/'transition-and-persistent-ending.png')
with (out/'per-frame-neighbors.csv').open('w', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=rows[0], lineterminator='\n');writer.writeheader();writer.writerows(rows)
(out/'collection.json').write_text(json.dumps({'mediaSha256': doc['media_sha256'], 'flaggedFrames': 540, 'decodedRange': [4859,5400], 'roiBoundsOn360x640': [19,57,283,100], 'maxRgbAcrossAllFlaggedRois': max(row['roi_max_rgb'] for row in rows), 'distinctEndingRoiHashes': len({row['roi_sha256'] for row in rows}), 'sourceRules': ['Film hidesHUD atframe4860', 'Scene clearsworld atframe4860 anddrawsseal only'], 'flagReviewsWritten': False, 'limitations': 'ROI evidence and neighbor pixel identity do not replace full-frame or human playback review.'}, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'evidence': str(out), 'frames': len(rows), 'distinctRoiHashes': len({row['roi_sha256'] for row in rows}), 'maxRgb': max(row['roi_max_rgb'] for row in rows)}))
