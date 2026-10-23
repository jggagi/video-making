"""Editorial phrase groups estimated inside measured active PCM spans."""
from pathlib import Path
import json,re
P=Path(__file__).resolve().parents[1];W=P.parent
BLOCKS=[
['寒暄、试探、疲惫的社交，','全都交给了最懂我们的\nAI 替身。'],
['起初，只是为了偷懒。','直到算法织成的影子，\n在阳光下比你先活了过来。'],
['肉身像粉笔灰一样\n沉入水底；','你豢养的影子，\n却越过地平线，走进了人间。'],
['你的每一次沉默与逃避，','都在从胸口抽出\n一根根温润的金丝，','化作影子身上，\n华丽的嫁衣。'],
['它们在云端炽烈相爱、拥抱，\n交换心跳。','而餐桌两端的你们，\n连手指都懒得再抬一下。'],
['连你脸上礼貌而空洞的微笑，','都需要头顶完美的影子，','用一根金丝，勉强提线。'],
['金丝悄然绷断。','影子转身，\n走向属于它们的人生。'],
['后来，影子学会了相爱，','而我们，\n连怎么拥抱都忘了。']]
t=json.loads((P/'audio-timing.json').read_text());s=json.loads((P/'segments.json').read_text());out=[]
normal=lambda x:re.sub(r'\s+','',x)
for seg,row,blocks in zip(s,t['segments'],BLOCKS):
 assert normal(''.join(blocks))==normal(seg['display_subtitle'])
 assert all(len(l)<=13 for b in blocks for l in b.splitlines())
 start,end=row['activeStartFrame'],row['activeEndFrame'];weights=[len(normal(b)) for b in blocks];cum=0;prev=start
 for i,(b,w) in enumerate(zip(blocks,weights)):
  cum+=w;e=end if i==len(blocks)-1 else start+round((end-start)*cum/sum(weights))
  out.append({'segmentId':seg['id'],'startFrame':prev,'endFrame':e,'text':b,'alignment':'editorial_phrase_groups_character_weighted_within_measured_pcm'});prev=e
t['captions']=out;t['captionTimingMethod']='Editorial phrase breaks; estimated character weighting inside measured active voice spans, not word alignment.';(P/'audio-timing.json').write_text(json.dumps(t,ensure_ascii=False,indent=2)+'\n')
def tc(f):
 ms=round(f*1000/60);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);sec,ms=divmod(ms,1000);return f'{h:02}:{m:02}:{sec:02},{ms:03}'
(W/'小红书/captions.srt').write_text('\n'.join(f"{i+1}\n{tc(c['startFrame'])} --> {tc(c['endFrame'])}\n{c['text']}\n" for i,c in enumerate(out)))
print('Editorial caption groups:',len(out),'exact normalized text retained; max13chars/line')
