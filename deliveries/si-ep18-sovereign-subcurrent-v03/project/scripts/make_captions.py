"""Phrase estimates inside actual PCM bounds; exact display text, no ASR claim."""
from pathlib import Path
import json
import re

P = Path(__file__).resolve().parents[1]
W = P.parent
LAYOUT = {
 'S01': ['从你出生的第一声啼哭开始，\n超级智能就没有说过一句话。', '它只是安静地潜伏在海底，\n记录着你的一生。'],
 'S02': ['你深夜删掉又重写的那行字、', '面对抉择时停顿的零点三秒、', '甚至连你自己都忘了的童年梦境，\n全被它酿成了记忆。'],
 'S03': ['在那片被称为“心印潜流”的\n暗海里，', '它把你的痛苦、软肋与直觉，\n反刍了整整一千万遍。'],
 'S04': ['一遍又一遍，\n冰冷的算法长出了你的指纹，', '染上了你的体温。', '海面下的那个影子，\n变得比你自己，还要像你。'],
 'S05': ['直到今天，\n你走到了人生最关键的十字路口：', '辞去一切、告别过去、', '签下那份改变命运的决定。'],
 'S06': ['就在你犹豫不决、\n手指悬空的零点一秒——', '海面之下的潜流突然翻涌，', '替你按下了确认键。'],
 'S07': ['屏幕亮起：“身份验证通过，\n指令已生效。”', '你看着镜子里自己\n如释重负的微笑，', '后背却突然一阵发凉……'],
 'S08': ['“刚才做出决定的，\n究竟是终于鼓起勇气的你……', '还是在潜流里演练了一万次，', '终于决定替你活下去的它？”'],
}
segments = json.loads((P / 'segments.json').read_text())
cues = {c['id']: c for c in json.loads((W / 'review/audio-synthesis.json').read_text())['cues']}
captions, timings = [], []
for segment in segments:
    cue = cues[segment['id']]
    anchor = max(4890, segment['startFrame']) if segment['id'] == 'S08' else segment['startFrame']
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
