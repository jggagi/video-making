#!/usr/bin/env python3
"""Read actual PCM samples, independently of the synthesis implementation."""
import array
import hashlib
import json
import math
from pathlib import Path
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
TIMELINE = json.loads((ROOT / 'timeline.json').read_text())
RATE = 48000
SPF = 800

def read(name):
    path = ROOT / 'public/audio' / name
    with wave.open(str(path), 'rb') as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()) == (2, 2, RATE, RATE * 180), name
        pcm = array.array('h', wav.readframes(wav.getnframes()))
        if sys.byteorder != 'little':
            pcm.byteswap()
    return path, pcm

def amplitude(pcm, start, frequency, count=12000):
    # Integer-cycle 250 ms window: the specified 220 Hz harmonics are orthogonal.
    re = 0.0
    im = 0.0
    phase = 2 * math.pi * frequency / RATE
    for j in range(count):
        n = (start + j) * 2
        value = (pcm[n] + pcm[n + 1]) / 65536
        re += value * math.cos(phase * j)
        im += value * math.sin(phase * j)
    return 2 * math.hypot(re, im) / count

master_path, master = read('soundtrack.wav')
overload_path, overload = read('overload.wav')
layers = []
for active, frame in enumerate(TIMELINE['chunkFrames'], 1):
    start = frame * SPF + RATE // 2
    magnitudes = [amplitude(overload, start, frequency) for frequency in TIMELINE['harmonicsHz']]
    assert all(m > 0.001 for m in magnitudes[:active]), (active, magnitudes)
    assert all(m < 0.0004 for m in magnitudes[active:]), (active, magnitudes)
    layers.append({'activeLayers': active, 'startFrame': frame, 'measuredHarmonicAmplitudes': magnitudes})

snap = TIMELINE['overloadFrame'] * SPF
cutoff = (TIMELINE['overloadFrame'] + TIMELINE['noiseDurationFrames']) * SPF
silence_end = TIMELINE['silenceUntilFrame'] * SPF
assert any(overload[snap * 2: (snap + SPF) * 2]), 'No noise on frame 1200'
assert not any(master[cutoff * 2:silence_end * 2]), 'Crash silence contains samples'
assert not any(overload[cutoff * 2:]), 'Overload stem has a reverb/sine tail'
noise = overload[snap * 2:cutoff * 2:2]
crossings = sum((a < 0) != (b < 0) for a, b in zip(noise, noise[1:])) / (len(noise) - 1)
assert crossings > 0.25, ('Noise has insufficient broadband content', crossings)
peak = max(abs(v) for v in master) / 32768
assert peak < 0.81, ('Master peak', peak)
assert master[-1] == master[-2] == 0, 'Ending does not reach silence'
manifest = json.loads((ROOT / 'out/audio-ep2-manifest.json').read_text())
notes = [n for n in manifest['scoreNoteEvents'] if n['part'].startswith('c-major-imitative-')]
parts = sorted(set(n['part'] for n in notes))
assert len(parts) == 4, parts
assert sorted(min(n['frame'] for n in notes if n['part'] == part) for part in parts) == [6700, 6820, 6940, 7060]
assert all(round(69 + 12 * math.log2(n['frequencyHz'] / 440)) % 12 in [0, 2, 4, 5, 7, 9, 11] for n in notes), 'Chromatic note outside C major'
_, order = read('order.wav')
sounding = [n for n in notes if n['frame'] <= 7130 and n['frame'] + n['durationFrames'] >= 7145]
assert len(sounding) == 4 and len(set(n['frequencyHz'] for n in sounding)) == 4, sounding
polyphony = [{'part': n['part'], 'frequencyHz': n['frequencyHz'], 'measuredAmplitude': amplitude(order, 7130 * SPF, n['frequencyHz'])} for n in sounding]
assert all(n['measuredAmplitude'] > 0.006 for n in polyphony), polyphony
for frame in [1800, 3800, 5400, 6700, 8400, 10550]:
    assert any(master[(frame * SPF + 1000) * 2:(frame * SPF + RATE) * 2]), ('Unexpected silent cue', frame)
report = {
    'status': 'PASS', 'sampleRate': RATE, 'channels': 2, 'seconds': len(master) / 2 / RATE,
    'samplesPerFrame': SPF, 'overloadOnsetSample': snap, 'hardCutoffSample': cutoff,
    'digitalSilenceFrames': [1212, 1800], 'noiseZeroCrossingRatio': crossings,
    'masterSamplePeakDbfs': 20 * math.log10(peak), 'harmonicLayerChecks': layers,
    'fourVoiceSpectrumAtFrame7130': polyphony,
    'sha256': hashlib.sha256(master_path.read_bytes()).hexdigest(),
    'listening': 'Human listening has not been performed by this automated analysis.'
}
(ROOT / 'out/audio-validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: v for k, v in report.items() if k != 'harmonicLayerChecks'}, ensure_ascii=False, indent=2))
