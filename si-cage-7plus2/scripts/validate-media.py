#!/usr/bin/env python3
"""Probe/decode actual exports and record PCM versus encoded timing separately."""
import array
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out'

def run(args):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

exports = {}
for name, duration, frames in [('overload-preview.mp4', 4.5, 270), ('manifold-preview.mp4', 10, 600), ('cage-of-seven-plus-two-1080p.mp4', 180, 10800)]:
    path = OUT / name
    probe = json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)]).stdout)
    video = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    audio = next(s for s in probe['streams'] if s['codec_type'] == 'audio')
    assert (video['width'], video['height'], video['r_frame_rate'], int(video['nb_frames'])) == (1920, 1080, '60/1', frames), name
    assert float(video['duration']) == duration, name
    assert (audio['codec_name'], audio['sample_rate'], audio['channels']) == ('aac', '48000', 2), name
    assert abs(float(probe['format']['duration']) - duration) < 0.03, name
    if frames == 10800:
        selected = [0, 1080, 1199, 1200, 1230, 2100, 3300, 4600, 6000, 7200, 9000, 10200, 10799]
        selector = '+'.join('eq(n\\,%d)' % n for n in selected)
        run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path), '-map', '0:v:0', '-vf', 'select=' + selector, '-fps_mode', 'vfr', '-y', str(OUT / 'final-frame-%02d.png'), '-map', '0:a:0', '-f', 'null', '-'])
    else:
        run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path), '-map', '0:v:0', '-map', '0:a:0', '-f', 'null', '-'])
    exports[name] = {'width': 1920, 'height': 1080, 'fps': 60, 'videoFrames': frames, 'videoDurationSeconds': float(video['duration']), 'audioPresentedDurationSeconds': float(audio['duration']), 'containerDurationSeconds': float(probe['format']['duration']), 'fullStrictDecode': 'PASS', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

decoded = run(['ffmpeg', '-v', 'error', '-i', str(OUT / 'overload-preview.mp4'), '-vn', '-ac', '2', '-ar', '48000', '-f', 's16le', '-']).stdout
pcm = array.array('h', decoded)
def rms(start, end):
    values = pcm[int(start * 48000) * 2:int(end * 48000) * 2]
    return math.sqrt(sum((v / 32768) ** 2 for v in values) / len(values))
levels = {'nineLayerRms': rms(1.75, 1.95), 'noiseRms': rms(2.03, 2.17), 'postCutRms': rms(2.3, 4.3)}
assert levels['noiseRms'] > levels['nineLayerRms'] * 4, levels
assert levels['postCutRms'] < 0.0001, levels

measurement = run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(ROOT / 'public/audio/soundtrack.wav'), '-af', 'ebur128=peak=true:framelog=verbose', '-f', 'null', '-']).stderr.decode()
summary = measurement[measurement.rfind('Summary:'):]
(OUT / 'loudness-summary.txt').write_text(summary)
integrated = float(re.search(r'I:\s*(-?[\d.]+) LUFS', summary).group(1))
true_peak = float(re.search(r'Peak:\s*(-?[\d.]+) dBFS', summary).group(1))
assert true_peak < -1, true_peak
report = {'status': 'PASS', 'exports': exports, 'encodedOverloadLevels': levels, 'masterIntegratedLufs': integrated, 'masterTruePeakDbtp': true_peak, 'pcmFrameTiming': 'PCM synthesis changes at exact sample 960000; AAC is lossy and may smear transient edges slightly.', 'humanListening': 'pending', 'finalDevicePlayback': 'pending'}
(OUT / 'media-validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report, ensure_ascii=False, indent=2))
