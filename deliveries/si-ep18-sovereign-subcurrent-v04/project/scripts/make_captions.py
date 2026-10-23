"""Phrase estimates inside actual PCM bounds; exact display text, no ASR claim."""
from pathlib import Path
import json
import re

P = Path(__file__).resolve().parents[1]
W = P.parent
LAYOUT = {'S01': ['如果有一天，', '你的影子，比你先动了一下。'], 'S02': ['它，是藏在你生活里的超级智能。', '你删掉的字，', '和零点三秒的犹豫，它全都记得。'], 'S03': ['在暗处，', '它把你演练了一千万遍。'], 'S04': ['直到某天，', '影子变得，比你还像你。'], 'S05': ['今天，你走到人生的路口。', '手指悬着，迟迟没有落下。'], 'S06': ['就在那零点一秒，', '影子抬起手，', '替你按下了确认。'], 'S07': ['身份验证通过。', '可你明明，还没有动。'], 'S08': ['刚才做决定的，是你？', '还是演练了一万次，', '终于决定，替你活下去的它？']}
segments = json.loads((P / 'segments.json').read_text())
cues = {c['id']: c for c in json.loads((W / 'review/audio-synthesis.json').read_text())['cues']}
captions, timings = [], []
for segment in segments:
    cue = cues[segment['id']]
    anchor = segment['startFrame']
    first = anchor + cue['activeStartSample'] // 800
    last = anchor + (cue['activeEndSampleExclusive'] + 799) // 800
    assert last <= segment['endFrame'], (segment['id'], last, segment['endFrame'])
    groups = LAYOUT[segment['id']]
    assert ''.join(groups).replace('\n', '') == segment['display_subtitle'].replace('\n', ''), segment['id']
    weights = [len(re.sub(r'[\n，。；！？：、“”……——]', '', group)) + .6 for group in groups]
    elapsed, total = 0., sum(weights)
    for index, (group, weight) in enumerate(zip(groups, weights)):
        assert len(group.split('\n')) <= 2 and max(map(len, group.split('\n'))) <= 17, group
        a = round(first + (last - first) * elapsed / total)
        elapsed += weight
        b = round(first + (last - first) * elapsed / total)
        captions.append({'id': segment['id'], 'startFrame': a,
                         'endFrame': min(segment['endFrame'], b + (12 if index == len(groups)-1 else 0)), 'text': group})
    timings.append({'id': segment['id'], 'placementStartFrame': anchor, 'endFrame': segment['endFrame'],
                    'originalSourceWindowFrames': segment['originalWindow'],
                    'startAdjustedFromSource': anchor != segment['originalWindow'][0],
                    'actualDurationSeconds': cue['durationSeconds'], 'activeStartFrame': first,
                    'activeEndFrameExclusive': last, 'cuePath': cue['canonicalAudioFile'],
                    'sha256': cue['canonicalSha256']})
(P / 'captions.json').write_text(json.dumps(captions, ensure_ascii=False, indent=2) + '\n')
(P / 'audio-timing.json').write_text(json.dumps({'status': 'MEASURED', 'duration_seconds': 90,
 'fps': 60, 'samples_per_channel': 4320000,
 'captionAlignment': 'estimated phrase weights within actual PCM activity, not word alignment',
 'segments': timings, 'captions': captions}, ensure_ascii=False, indent=2) + '\n')

def stamp(frame):
    ms = round(frame / 60 * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    sec, ms = divmod(ms, 1000)
    return f'{h:02}:{m:02}:{sec:02},{ms:03}'

(W / '小红书/captions.srt').write_text('\n\n'.join(f'{i+1}\n{stamp(c["startFrame"])} --> {stamp(c["endFrame"])}\n{c["text"]}' for i,c in enumerate(captions)) + '\n')
print(f'{len(captions)} phrase captions, exact display text retained.')
