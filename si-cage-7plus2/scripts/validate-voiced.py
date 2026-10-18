#!/usr/bin/env python3
"""Independent PCM, timing, identity, decode and loudness checks for voiced v2."""
from array import array
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import wave

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out'
def load(path):
    return json.loads((ROOT / path).read_text())
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def run(args):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace')[-4000:])
    return result
def pcm(path, channels=2, rate=48000):
    with wave.open(str(path), 'rb') as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (channels, 2, rate), path
        data = array('h', wav.readframes(wav.getnframes()))
    return data

source_manifest = load('audio-voiced-v2/voice-manifest.json')
mix = load('out/voiced-v2-mix-manifest.json')
assert len(source_manifest['cues']) == len(mix['cues']) == 17
assert sum(c['status'] == 'success' for c in source_manifest['attempts']) == 17
assert all(c['status'] == 'success' for c in source_manifest['attempts'])
master_path = ROOT / 'public/audio-voiced-v2/soundtrack.wav'
voice_path = ROOT / 'public/audio-voiced-v2/narration.wav'
master, voice = pcm(master_path), pcm(voice_path)
assert len(master) == len(voice) == 8640000 * 2
assert not any(master[1212 * 800 * 2:1242 * 800 * 2]), 'Post-noise quiet changed'
overload = pcm(ROOT / 'public/audio/overload.wav')
assert master[1200 * 800 * 2:1212 * 800 * 2] == overload[1200 * 800 * 2:1212 * 800 * 2], 'Overload transient changed'
assert not any(voice[10788 * 800 * 2:]), 'Narration exceeds ending boundary'
source_by_id = {c['id']: c for c in source_manifest['cues']}
for cue in mix['cues']:
    source = source_by_id[cue['id']]
    assert sha(ROOT / cue['file']) == source['sha256']
    aligned = pcm(ROOT / cue['alignedFile'], channels=1)
    assert cue['atempo'] == 1.0 and len(aligned) == source['decodedSamples'] * 2, cue['id']
    start = cue['startFrame'] * 800
    assert start + len(aligned) <= cue['deadlineFrame'] * 800
    assert voice[start * 2:(start + len(aligned)) * 2:2] == aligned
    assert voice[start * 2 + 1:(start + len(aligned)) * 2:2] == aligned
for name, source in mix['inputs']['sourceStems'].items():
    assert sha(ROOT / source['path']) == source['sha256']
assert master[-1] == master[-2] == 0
movie = OUT / 'cage-of-seven-plus-two-voiced-v2-1080p.mp4'
probe = json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(movie)]).stdout)
v = next(s for s in probe['streams'] if s['codec_type'] == 'video')
a = next(s for s in probe['streams'] if s['codec_type'] == 'audio')
assert (v['width'], v['height'], v['r_frame_rate'], int(v['nb_frames'])) == (1920, 1080, '60/1', 10800)
assert float(v['duration']) == 180
assert a['codec_name'] == 'aac' and a['sample_rate'] == '48000' and a['channels'] == 2
assert abs(float(probe['format']['duration']) - 180) < 0.03
run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(movie), '-map', '0:v:0', '-map', '0:a:0', '-f', 'null', '-'])
log = run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(master_path), '-af', 'ebur128=peak=true:framelog=verbose', '-f', 'null', '-']).stderr.decode()
summary = log[log.rfind('Summary:'):]
(OUT / 'voiced-v2-loudness-summary.txt').write_text(summary)
lufs = float(re.search(r'I:\s*(-?[\d.]+) LUFS', summary).group(1))
true_peak = float(re.search(r'Peak:\s*(-?[\d.]+) dBFS', summary).group(1))
assert true_peak < -1.0, ('True peak needs gain review', true_peak)
mux = load('out/voiced-v2-mux-manifest.json')
assert mux['videoStreamPreserved']
report = {'status': 'PASS', 'ttsClips': 17, 'ttsNewSuccessfulCalls': 17, 'ttsFailedCalls': 0, 'providerUsageAndBill': 'not reported', 'originalSamplesRetained': True, 'allCuesFitWithoutSpeedChange': True, 'sourceStemsUnchanged': True, 'overloadSamplesUnchanged': True, 'postNoiseDigitalSilenceFrames': [1212, 1242], 'narrationSourceDurationSeconds': sum(c['durationSeconds'] for c in source_manifest['cues']), 'masterSampleFrames': 8640000, 'masterSeconds': 180, 'integratedLufs': lufs, 'truePeakDbtp': true_peak, 'videoFrames': 10800, 'videoDurationSeconds': float(v['duration']), 'audioPresentedDurationSeconds': float(a['duration']), 'containerDurationSeconds': float(probe['format']['duration']), 'videoStreamPreserved': True, 'strictCompleteDecode': 'PASS', 'sha256': sha(movie), 'humanListening': 'pending', 'asr': 'See audio-voiced-v2/asr-status.json; no upload without separate authorization.'}
(OUT / 'voiced-v2-validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report, ensure_ascii=False, indent=2))
