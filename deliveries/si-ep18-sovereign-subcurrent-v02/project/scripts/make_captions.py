"""Estimated phrase timing inside measured PCM activity; no word alignment claim."""
from pathlib import Path
import json
import re

P = Path(__file__).resolve().parents[1]
W = P.parent
LAYOUT = {
    'S01': ['海面上的世界，\n被超级智能照得透亮。', '可你心里，\n还有一片不必公开的暗海。'],
    'S02': ['我们不必赢过机器，\n才有资格决定自己的人生。', '冰山之下，藏着一句朴素的话：', '这部分，我选择保留。'],
    'S03': ['于是，有人不再把秘密、软肋\n和梦境全部上传。', '那片由自己守护的暗海，', '我们叫它：心印潜流。'],
    'S04': ['那里有没说出口的暗恋，\n也有童年的伤疤。', '算法也许能猜中一些，', '却不因此，就有权替你决定。'],
    'S05': ['而海面之上，\n推演的光环仍在一遍遍回旋。', '它能列出无数条路，', '却在这里停下：\n我们究竟想去哪里？'],
    'S06': ['一缕金光，从深海升上海面。', '它没有破解所有难题，', '只带来一个人的选择：\n我想往这里走。', '坚冰，终于裂开。'],
    'S07': ['超级智能，\n可以帮我们走得更远。', '而你珍惜什么、愿意交出什么，', '仍该由你，亲口说出。'],
    'S08': ['把计算交给神明，\n把心印留给自己。', '哪扇门为谁打开，由你决定。'],
}

segments = json.loads((P / 'segments.json').read_text())
cues = {c['id']: c for c in json.loads((W / 'review/audio-synthesis.json').read_text())['cues']}
captions, timings = [], []
for segment in segments:
    cue = cues[segment['id']]
    first = segment['startFrame'] + (cue['activeStartSample'] * 60 // 48000)
    last = segment['startFrame'] + ((cue['activeEndSampleExclusive'] * 60 + 47999) // 48000)
    assert last <= segment['endFrame'], (segment['id'], last, segment['endFrame'])
    groups = LAYOUT[segment['id']]
    assert ''.join(groups).replace('\n', '') == segment['display_subtitle'].replace('\n', ''), segment['id']
    weights = [len(re.sub(r'[\n，。；！？：、“”]', '', group)) + 0.6 for group in groups]
    elapsed, total = 0.0, sum(weights)
    for index, (group, weight) in enumerate(zip(groups, weights)):
        assert len(group.split('\n')) <= 2 and max(map(len, group.split('\n'))) <= 17, group
        a = round(first + (last - first) * elapsed / total)
        elapsed += weight
        b = round(first + (last - first) * elapsed / total)
        captions.append({'id': segment['id'], 'startFrame': a, 'endFrame': min(segment['endFrame'], b + (22 if index == len(groups) - 1 else 0)), 'text': group})
    timings.append({'id': segment['id'], 'startFrame': segment['startFrame'], 'endFrame': segment['endFrame'], 'actualDurationSeconds': cue['durationSeconds'], 'activeStartFrame': first, 'activeEndFrameExclusive': last, 'cuePath': cue['canonicalAudioFile'], 'sha256': cue['canonicalSha256']})
(P / 'captions.json').write_text(json.dumps(captions, ensure_ascii=False, indent=2) + '\n')
(P / 'audio-timing.json').write_text(json.dumps({'status': 'MEASURED', 'duration_seconds': 90, 'fps': 60, 'samples_per_channel': 4320000, 'captionAlignment': 'estimated phrase weights within measured PCM activity; not word-level alignment', 'segments': timings, 'captions': captions}, ensure_ascii=False, indent=2) + '\n')

def stamp(frame):
    ms = round(frame / 60 * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    sec, ms = divmod(ms, 1000)
    return f'{h:02}:{m:02}:{sec:02},{ms:03}'

(W / '小红书/captions.srt').write_text('\n\n'.join(f'{i+1}\n{stamp(c["startFrame"])} --> {stamp(c["endFrame"])}\n{c["text"]}' for i, c in enumerate(captions)) + '\n')
print(f'Wrote {len(captions)} estimated phrase captions; exact text preserved.')
