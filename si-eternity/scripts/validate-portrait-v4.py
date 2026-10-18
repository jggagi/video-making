"""Validate the v4 portrait render against its source snapshot and v3 assets.

This is a final-media validator. It decodes and inspects already-rendered files;
it does not invoke Remotion or create the film or preview.
"""

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
film = output / 'one-blink-ten-millennia-portrait-v4.mp4'
preview = output / 'portrait-layout-preview-v4.mp4'
master = root / 'public/audio-v3/soundtrack.wav'
EXPECTED_MASTER_SHA256 = '7d0b79b47b888a04806b4087f3b3517c1ad9989f4080f3bf10a362cb9e651571'
MASTER_FRAMES = 8_640_000
VIDEO_FRAMES = 10_800


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
        1080, 1920, '60/1', expected_frames
    ), f'{path.name}: unexpected portrait video format or frame count'
    assert audio['codec_name'] == 'aac' and audio['sample_rate'] == '48000' and int(audio['channels']) == 2, (
        f'{path.name}: expected AAC 48 kHz stereo'
    )
    duration = float(probe['format']['duration'])
    assert abs(duration - expected_seconds) <= 1 / 60, f'{path.name}: unexpected duration {duration}'
    return probe, video, audio, duration


def assert_strict_av_decode(path):
    subprocess.run([
        'ffmpeg', '-hide_banner', '-v', 'error', '-xerror', '-err_detect', 'explode',
        '-threads', '2', '-i', str(path), '-f', 'null', '-',
    ], check=True)


def decode_rgb(path):
    pixels = subprocess.check_output([
        'ffmpeg', '-hide_banner', '-v', 'error', '-xerror', '-threads', '2', '-i', str(path),
        '-map', '0:v:0', '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1',
    ])
    expected_bytes = 1920 * 1080 * 3
    assert len(pixels) == expected_bytes, f'{path.name}: expected one 1920x1080 RGB frame, got {len(pixels)} bytes'
    return np.frombuffer(pixels, dtype=np.uint8).reshape((1080, 1920, 3))


probe, video, audio, container_seconds = assert_video_audio(film, VIDEO_FRAMES, 180)
preview_probe, preview_video, preview_audio, preview_seconds = assert_video_audio(preview, 720, 12)

# Verify the exact v3 mix reused by this edition before comparing encoded AAC.
assert master.is_file() and digest(master) == EXPECTED_MASTER_SHA256, 'The v3 soundtrack master hash changed.'
with wave.open(str(master), 'rb') as reference:
    assert reference.getnframes() == MASTER_FRAMES
    assert reference.getframerate() == 48_000 and reference.getnchannels() == 2 and reference.getsampwidth() == 2

# The preview starts at 156 s, after a speech cue and before the impact.
# Verify that rendering a selected frame window also selected the correct audio window.
preview_pcm = subprocess.check_output([
    'ffmpeg', '-hide_banner', '-v', 'error', '-xerror', '-i', str(preview),
    '-map', '0:a:0', '-ac', '2', '-ar', '48000', '-f', 'f32le', 'pipe:1',
])
preview_samples = np.frombuffer(preview_pcm, dtype='<f4').reshape(-1, 2)
assert 576_000 <= len(preview_samples) <= 576_000 + 2048
assert np.isfinite(preview_samples).all()
with wave.open(str(master), 'rb') as reference:
    reference.setpos(156 * 48_000)
    preview_reference = np.frombuffer(reference.readframes(576_000), dtype='<i2').astype(np.float64) / 32768
preview_correlation = float(np.corrcoef(preview_reference, preview_samples[:576_000].reshape(-1).astype(np.float64))[0, 1])
assert preview_correlation > 0.99, f'Preview audio window mismatch: {preview_correlation}'

# Strictly decode both streams so corrupt packets or concealed decode errors fail QA.
assert_strict_av_decode(film)
assert_strict_av_decode(preview)

# Compare the complete decoded AAC timeline against the unchanged PCM master in bounded chunks.
command = [
    'ffmpeg', '-hide_banner', '-v', 'error', '-xerror', '-i', str(film),
    '-map', '0:a:0', '-ac', '2', '-ar', '48000', '-f', 'f32le', 'pipe:1',
]
process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
assert process.stdout is not None and process.stderr is not None
sx = sy = sxx = syy = sxy = 0.0
sample_count = decoded_frames = compared_frames = 0
peak = 0.0
with wave.open(str(master), 'rb') as reference:
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
assert compared_frames == MASTER_FRAMES
assert MASTER_FRAMES <= decoded_frames <= MASTER_FRAMES + 2048, f'Unexpected decoded AAC frame count: {decoded_frames}'
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

# Verify the immutable source snapshot and every prior master export.
snapshot_path = output / 'render-source-portrait-v4-sha256.json'
snapshot = json.loads(snapshot_path.read_text())
assert isinstance(snapshot, dict) and snapshot, 'The portrait-v4 source snapshot must be a non-empty path-to-hash map.'
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

old_v3_path = output / 'one-blink-ten-millennia-v3.mp4'
old_v3_report = json.loads((output / 'title-v3-validation.json').read_text())
old_v3_hash = old_v3_report['artifacts']['one-blink-ten-millennia-v3.mp4']['sha256']
old_v3_unchanged = digest(old_v3_path) == old_v3_hash
assert old_v3_unchanged, 'Full v3 film changed from its recorded artifact hash.'

# Compare decoded RGB pixels, not PNG container bytes, for unchanged landscape frames.
landscape_frames = [120, 9600, 10799]
landscape_pixel_parity = []
for frame in landscape_frames:
    portrait_path = output / f'portrait-v4-landscape-frame-{frame:05d}.png'
    source_path = output / f'v3-frame-{frame:05d}.png'
    portrait_pixels = decode_rgb(portrait_path)
    source_pixels = decode_rgb(source_path)
    exact_match = bool(np.array_equal(portrait_pixels, source_pixels))
    assert exact_match, f'Landscape output pixels changed at frame {frame}.'
    landscape_pixel_parity.append({
        'frame': frame,
        'portraitFile': portrait_path.name,
        'sourceFile': source_path.name,
        'exactRgbPixelMatch': exact_match,
        'width': 1920,
        'height': 1080,
        'rgbSha256': hashlib.sha256(portrait_pixels.tobytes()).hexdigest(),
    })

# Extract representative portrait frames for later human inspection; this script does not inspect them.
frames = [120, 1200, 3240, 4920, 6000, 7170, 7800, 9240, 9599, 9600, 10200, 10650, 10799]
selection = '+'.join(f'eq(n\\,{number})' for number in frames)
subprocess.run([
    'ffmpeg', '-y', '-hide_banner', '-v', 'error', '-xerror', '-threads', '2', '-i', str(film),
    '-map', '0:v:0', '-vf', f'select={selection}', '-fps_mode', 'vfr', '-threads', '2',
    '-start_number', '1', str(output / 'portrait-v4-encoded-%02d.png'),
], check=True)
encoded_frame_files = [
    {'frame': frame, 'file': f'portrait-v4-encoded-{index:02d}.png'}
    for index, frame in enumerate(frames, start=1)
]
assert all((output / item['file']).is_file() for item in encoded_frame_files), 'Encoded-frame extraction did not produce every requested frame.'

artifact_names = [film.name, preview.name]
artifacts = {
    name: {'bytes': (output / name).stat().st_size, 'sha256': digest(output / name)}
    for name in artifact_names
}

report = {
    'width': 1080,
    'height': 1920,
    'fps': 60,
    'videoFrames': VIDEO_FRAMES,
    'containerSeconds': container_seconds,
    'videoCodec': video['codec_name'],
    'audioCodec': audio['codec_name'],
    'audioRate': 48000,
    'audioChannels': 2,
    'strictFullAvDecodePassed': True,
    'masterSha256': EXPECTED_MASTER_SHA256,
    'masterSampleFrames': MASTER_FRAMES,
    'decodedAacFrames': decoded_frames,
    'aacPaddingFrames': decoded_frames - MASTER_FRAMES,
    'audioZeroLagCorrelationToMaster': correlation,
    'decodedSamplePeakDbfs': 20 * math.log10(peak),
    'encodedAudioIntegratedLufs': integrated_lufs,
    'encodedAudioTruePeakDbtp': true_peak_dbtp,
    'fastStart': True,
    'containerBoxes': boxes,
    'sourceSnapshotUnchanged': True,
    'oldV1Unchanged': old_v1_unchanged,
    'oldV2Unchanged': old_v2_unchanged,
    'oldV3Unchanged': old_v3_unchanged,
    'previewMetrics': {
        preview.name: {
            'width': int(preview_video['width']),
            'height': int(preview_video['height']),
            'fps': 60,
            'videoFrames': 720,
            'containerSeconds': preview_seconds,
            'videoCodec': preview_video['codec_name'],
            'audioCodec': preview_audio['codec_name'],
            'audioRate': 48000,
            'audioChannels': 2,
            'masterWindowStartSeconds': 156,
            'masterWindowEndSeconds': 168,
            'audioZeroLagCorrelationToMasterWindow': preview_correlation,
        },
    },
    'landscapePixelParity': landscape_pixel_parity,
    'extractedVideoFrames': frames,
    'extractedVideoFrameFiles': encoded_frame_files,
    'continuousHumanListeningComplete': False,
    'visualInspectionCompleted': False,
    'artifacts': artifacts,
}
(output / 'portrait-v4-validation.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
