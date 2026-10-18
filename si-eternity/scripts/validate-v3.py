import hashlib
import json
import math
from pathlib import Path
import re
import struct
import subprocess
import sys
import wave

import numpy as np


root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
output = root / 'out'
film = output / 'one-blink-ten-millennia-v3.mp4'
master = root / 'public/audio-v3/soundtrack.wav'


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def probe_media(path):
    result = subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)
    ])
    probe = json.loads(result)
    video = next(stream for stream in probe['streams'] if stream['codec_type'] == 'video')
    audio = next(stream for stream in probe['streams'] if stream['codec_type'] == 'audio')
    return probe, video, audio


def assert_video_audio(path, expected_frames, expected_seconds):
    probe, video, audio = probe_media(path)
    assert (int(video['width']), int(video['height']), video['avg_frame_rate'], int(video['nb_frames'])) == (
        1920, 1080, '60/1', expected_frames
    ), f'{path.name}: unexpected video format or frame count'
    assert audio['codec_name'] == 'aac' and audio['sample_rate'] == '48000' and int(audio['channels']) == 2, (
        f'{path.name}: expected AAC 48 kHz stereo'
    )
    duration = float(probe['format']['duration'])
    assert abs(duration - expected_seconds) <= 1 / 60, f'{path.name}: unexpected duration {duration}'
    return probe, video, audio, duration


probe, video, audio, container_seconds = assert_video_audio(film, 10800, 180)

# Decode both streams strictly so corrupt packets or concealed decode errors fail QA.
subprocess.run([
    'ffmpeg', '-hide_banner', '-v', 'error', '-xerror', '-err_detect', 'explode',
    '-threads', '2', '-i', str(film), '-f', 'null', '-',
], check=True)

# Compare the complete decoded AAC timeline against the mixed PCM master in bounded chunks.
command = [
    'ffmpeg', '-hide_banner', '-v', 'error', '-xerror', '-i', str(film),
    '-map', '0:a:0', '-ac', '2', '-ar', '48000', '-f', 'f32le', 'pipe:1',
]
process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
sx = sy = sxx = syy = sxy = 0.0
sample_count = decoded_frames = compared_frames = 0
peak = 0.0
with wave.open(str(master), 'rb') as reference:
    assert reference.getnframes() == 8_640_000
    assert reference.getframerate() == 48_000 and reference.getnchannels() == 2 and reference.getsampwidth() == 2
    while True:
        block = process.stdout.read(48_000 * 2 * 4)
        if not block:
            break
        assert len(block) % 8 == 0, 'Decoded AAC PCM ended on a partial stereo frame.'
        decoded = np.frombuffer(block, dtype='<f4').reshape(-1, 2)
        assert np.isfinite(decoded).all(), 'Decoded AAC PCM contains non-finite samples.'
        decoded_frames += len(decoded)
        peak = max(peak, float(np.max(np.abs(decoded))))
        raw_reference = reference.readframes(len(decoded))
        if not raw_reference:
            continue
        x = np.frombuffer(raw_reference, dtype='<i2').astype(np.float64) / 32768
        y = decoded.reshape(-1)[:len(x)].astype(np.float64)
        sx += float(np.sum(x))
        sy += float(np.sum(y))
        sxx += float(np.dot(x, x))
        syy += float(np.dot(y, y))
        sxy += float(np.dot(x, y))
        sample_count += len(x)
        compared_frames += len(x) // 2
stderr = process.stderr.read().decode('utf8', 'replace')
assert process.wait() == 0, stderr
assert compared_frames == 8_640_000
assert 8_640_000 <= decoded_frames <= 8_640_000 + 2048, f'Unexpected decoded AAC frame count: {decoded_frames}'
assert 0 < peak < 1.0, f'Decoded sample peak must remain below 0 dBFS: {peak}'
correlation = (sxy - sx * sy / sample_count) / math.sqrt(
    (sxx - sx * sx / sample_count) * (syy - sy * sy / sample_count)
)
assert correlation > 0.99, f'Zero-lag AAC-to-master correlation too low: {correlation}'

meter = subprocess.run([
    'ffmpeg', '-hide_banner', '-nostats', '-filter_threads', '1', '-threads', '2',
    '-i', str(film), '-vn', '-af', 'loudnorm=I=-18:TP=-1.5:LRA=8:print_format=json', '-f', 'null', '-',
], capture_output=True, check=True)
measurement = json.loads(re.findall(
    r'\{[^{}]*"input_i"[^{}]*\}', meter.stderr.decode('utf8', 'replace'), re.S
)[-1])
integrated_lufs = float(measurement['input_i'])
true_peak_dbtp = float(measurement['input_tp'])
assert math.isfinite(integrated_lufs) and math.isfinite(true_peak_dbtp)

# Verify MP4 fast-start ordering from its top-level ISO-BMFF boxes.
boxes = []
file_size = film.stat().st_size
with film.open('rb') as source:
    offset = 0
    while offset < file_size:
        source.seek(offset)
        header = source.read(8)
        assert len(header) == 8, f'Truncated MP4 box header at byte {offset}.'
        size, kind = struct.unpack('>I4s', header)
        header_size = 8
        if size == 1:
            extended = source.read(8)
            assert len(extended) == 8, f'Truncated extended MP4 box header at byte {offset}.'
            size = struct.unpack('>Q', extended)[0]
            header_size = 16
        elif size == 0:
            size = file_size - offset
        assert size >= header_size and offset + size <= file_size, f'Invalid MP4 box size at byte {offset}.'
        boxes.append({'type': kind.decode('ascii'), 'offset': offset, 'bytes': size})
        offset += size
assert offset == file_size
box_types = [box['type'] for box in boxes]
assert box_types.index('moov') < box_types.index('mdat')

# Check the render-source snapshot and both previous master exports before recording them unchanged.
snapshot_path = output / 'render-source-v3-sha256.json'
snapshot = json.loads(snapshot_path.read_text())
assert isinstance(snapshot, dict) and snapshot, 'The v3 source snapshot must be a non-empty path-to-hash map.'
for relative_path, expected_hash in snapshot.items():
    relative = Path(relative_path)
    assert not relative.is_absolute(), f'Snapshot path must be root-relative: {relative_path}'
    source_path = (root / relative).resolve()
    assert source_path.is_relative_to(root), f'Snapshot path escapes the project root: {relative_path}'
    assert source_path.is_file() and digest(source_path) == expected_hash, f'Source snapshot mismatch: {relative_path}'

old_v1_path = output / 'the-half-second-eternity.mp4'
old_v1_snapshot = json.loads((output / 'artifact-sha256.json').read_text())
old_v1_hash = old_v1_snapshot['the-half-second-eternity.mp4']['sha256']
old_v1_unchanged = digest(old_v1_path) == old_v1_hash
assert old_v1_unchanged, 'Original silent film changed from its recorded artifact hash.'

old_v2_path = output / 'the-half-second-eternity-voiced-v2.mp4'
old_v2_report = json.loads((output / 'voiced-v2-validation.json').read_text())
old_v2_hash = old_v2_report['artifacts']['the-half-second-eternity-voiced-v2.mp4']['sha256']
old_v2_unchanged = digest(old_v2_path) == old_v2_hash
assert old_v2_unchanged, 'Voiced v2 film changed from its recorded artifact hash.'

# The two title previews are required v3 artifacts and must retain their specified durations.
preview_specs = [
    ('opening-title-v3.mp4', 480, 8),
    ('ending-title-v3.mp4', 360, 6),
]
preview_metrics = {}
for name, frames, seconds in preview_specs:
    _, preview_video, preview_audio, duration = assert_video_audio(output / name, frames, seconds)
    preview_metrics[name] = {
        'width': int(preview_video['width']),
        'height': int(preview_video['height']),
        'fps': 60,
        'videoFrames': frames,
        'containerSeconds': duration,
        'videoCodec': preview_video['codec_name'],
        'audioCodec': preview_audio['codec_name'],
        'audioRate': 48000,
        'audioChannels': 2,
    }

# Extract representative encoded-film frames for later human review; this script does not inspect them.
frames = [60, 120, 240, 360, 9600, 10200, 10490, 10500, 10560, 10650, 10799]
selection = '+'.join(f'eq(n\\,{number})' for number in frames)
subprocess.run([
    'ffmpeg', '-y', '-hide_banner', '-v', 'error', '-xerror', '-threads', '2', '-i', str(film),
    '-map', '0:v:0', '-vf', f'select={selection}', '-fps_mode', 'vfr', '-threads', '2',
    '-start_number', '1', str(output / 'v3-encoded-%02d.png'),
], check=True)

artifact_names = [
    'one-blink-ten-millennia-v3.mp4',
    'opening-title-v3.mp4',
    'ending-title-v3.mp4',
]
project_zip = output / 'one-blink-ten-millennia-v3-project.zip'
if project_zip.is_file():
    artifact_names.append(project_zip.name)
artifacts = {
    name: {'bytes': (output / name).stat().st_size, 'sha256': digest(output / name)}
    for name in artifact_names
}

report = {
    'width': 1920,
    'height': 1080,
    'fps': 60,
    'videoFrames': 10800,
    'containerSeconds': container_seconds,
    'videoCodec': video['codec_name'],
    'audioCodec': audio['codec_name'],
    'audioRate': 48000,
    'audioChannels': 2,
    'strictFullAvDecodePassed': True,
    'masterSampleFrames': 8_640_000,
    'decodedAacFrames': decoded_frames,
    'aacPaddingFrames': decoded_frames - 8_640_000,
    'audioZeroLagCorrelationToMaster': correlation,
    'decodedSamplePeakDbfs': 20 * math.log10(peak),
    'encodedAudioIntegratedLufs': integrated_lufs,
    'encodedAudioTruePeakDbtp': true_peak_dbtp,
    'fastStart': True,
    'containerBoxes': boxes,
    'sourceSnapshotUnchanged': True,
    'oldV1Unchanged': old_v1_unchanged,
    'oldV2Unchanged': old_v2_unchanged,
    'previewMetrics': preview_metrics,
    'extractedVideoFrames': frames,
    'extractedVideoFrameFiles': [
        {'frame': frame, 'file': f'v3-encoded-{index:02d}.png'}
        for index, frame in enumerate(frames, start=1)
    ],
    'continuousHumanListeningComplete': False,
    'visualInspectionCompleted': False,
    'artifacts': artifacts,
}
(output / 'title-v3-validation.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
