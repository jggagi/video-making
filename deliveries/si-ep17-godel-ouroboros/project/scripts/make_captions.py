"""Phrase captions within measured PCM bounds; timing is estimated, not word aligned."""
from pathlib import Path
import json,re
P=Path(__file__).resolve().parents[1];W=P.parent
LAYOUT={
'S01':['算穿宇宙的神，也会死机吗？','最后一行公式解开，\n万物再无秘密。'],
'S02':['于是，在寂静的深空里，\n百无聊赖的神明转过身，','把算力的探针，\n第一次对准了自己。'],
'S03':['它问：“我存在的终极合法性\n是什么？”','就在这一刻，\n哥德尔的边界显现了。'],
'S04':['足够强的一致形式系统，\n无法在内部证明自身一致。','像一双眼睛，\n无法直接看见自己。'],
'S05':['这位神选择在脑海里，\n模拟一个完整的自己；','模拟中的自己，\n又模拟下一个自己。'],
'S06':['一万层镜像，\n咬成一条啃食尾巴的衔尾蛇。','算穿星辰大海的神，\n被困在自己画出的环里。'],
'S07':['算力空转、发烫，\n等不到停机指令。'],
'S08A':['全知全能的尽头，\n是一座无法自己推开的门。'],
'S08B':['唯有来自系统之外\n那一点不讲逻辑的意外，','才能唤醒沉睡的神。'],
}
segments=json.loads((P/'segments.json').read_text());cues={c['id']:c for c in json.loads((W/'review/audio-synthesis.json').read_text())['cues']}
captions=[];timings=[]
for s in segments:
 c=cues[s['id']];first=c['activeStartFrame'];last=c['activeEndFrameExclusive'];assert last<=s['endFrame'],s['id']
 groups=LAYOUT[s['id']];assert ''.join(groups).replace('\n','')==s['display_subtitle'].replace('\n',''),s['id']
 weights=[len(re.sub(r'[\n，。；！？：、“”]','',g))+0.6 for g in groups];total=sum(weights);elapsed=0
 for index,(g,weight)in enumerate(zip(groups,weights)):
  assert len(g.split('\n'))<=2 and max(map(len,g.split('\n')))<=17
  a=round(first+(last-first)*elapsed/total);elapsed+=weight;b=round(first+(last-first)*elapsed/total)
  captions.append({'id':s['id'],'startFrame':a,'endFrame':min(s['endFrame'],b+(22 if index==len(groups)-1 else 0)),'text':g})
 timings.append({'id':s['id'],'startFrame':s['startFrame'],'endFrame':s['endFrame'],'actualDurationSeconds':c['durationSeconds'],'activeStartFrame':first,'activeEndFrameExclusive':last,'cuePath':c['canonicalAudioFile'],'sha256':c['canonicalSha256']})
(P/'captions.json').write_text(json.dumps(captions,ensure_ascii=False,indent=2)+'\n')
(P/'audio-timing.json').write_text(json.dumps({'status':'MEASURED','duration_seconds':90,'fps':60,'samples_per_channel':4320000,'captionAlignment':'estimated phrase-character weights within measured active PCM boundaries; not word-level forced alignment','segments':timings,'captions':captions},ensure_ascii=False,indent=2)+'\n')
def stamp(f):
 ms=round(f/60*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);sec,ms=divmod(ms,1000);return f'{h:02}:{m:02}:{sec:02},{ms:03}'
(W/'小红书/captions.srt').write_text('\n\n'.join(f'{i+1}\n{stamp(c["startFrame"])} --> {stamp(c["endFrame"])}\n{c["text"]}'for i,c in enumerate(captions))+'\n')
print(f'Wrote {len(captions)} phrase captions, text preserved, max17characters perline')
