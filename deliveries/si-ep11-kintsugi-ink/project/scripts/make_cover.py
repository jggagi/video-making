#!/usr/bin/env python3
"""Make a type-set 3:4 cover from exact final-MP4 frame 5040 (84 seconds)."""
from pathlib import Path
import hashlib
import json
import subprocess
from PIL import Image, ImageDraw, ImageFont

PROJECT=Path(__file__).resolve().parents[1]
WORK=PROJECT.parent
OUT=WORK/'小红书'
MANIFEST=json.loads((WORK/'delivery.json').read_text())
MEDIA=WORK/MANIFEST['outputs']['xiaohongshu']['path']
BASE=OUT/'cover-frame-84s.png'
COVER=OUT/'cover.png'
FONT=Path('/System/Library/AssetsV2/com_apple_MobileAsset_Font8/86ba2c91f017a3749571a82f2c6d890ac7ffb2fb.asset/AssetData/PingFang.ttc')
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

if COVER.exists():raise SystemExit('Preserve existing cover; choose a new version for changes.')
if not MEDIA.is_file():raise SystemExit('Final MP4 is required; source render is not cover provenance.')
if BASE.exists():
    evidence=json.loads((WORK/'review'/f'encoded-qa-{sha(MEDIA)[:12]}'/'report.json').read_text())
    expected=next(v['sha256'] for v in evidence['native_inspection_frames'] if v['frame']==5040)
    if evidence['media']['sha256']!=sha(MEDIA) or sha(BASE)!=expected:raise SystemExit('Divergent base frame preserved.')
else:
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(MEDIA),'-vf',r'select=eq(n\,5040)','-frames:v','1',str(BASE)],check=True)
im=Image.open(BASE).convert('RGB')
assert im.size==(2160,3840)
poster=Image.new('RGB',(1440,1920),'#0C0C0E')
crop=(300,1080,1800,2640)
art=im.crop(crop).resize((1100,1144),Image.Resampling.LANCZOS)
poster.paste(art,(170,610))
draw=ImageDraw.Draw(poster)
def line(text,y,size,fill):
    font=ImageFont.truetype(str(FONT),size,index=11)  # verified PingFang SC Semibold
    bounds=draw.textbbox((90,y),text,font=font)
    if bounds[2]>1350:raise ValueError(f'Cover line clips: {text}')
    draw.text((90,y),text,font=font,fill=fill,stroke_width=0)
line('一眼万年 / EP.11 · 科幻思想实验',64,42,'#a89981')
line('假如 AI 让人永远年轻',168,94,'#e7e1d4')
line('「白头偕老」',302,134,'#FBBF24')
line('会成为远古词汇吗？',478,94,'#e7e1d4')
line('逆转的沙漏 / DIGITAL KINTSUGI',1798,43,'#d6bb80')
line('数字金缮 × 水墨 · 90秒 / 不是医学结论',1860,34,'#8e8270')
poster.save(COVER)
record={'status':'PREPARED','source':'exact encoded MP4 frame','media':str(MEDIA.relative_to(WORK)),'media_sha256':sha(MEDIA),'frame':5040,'seconds':84,'frame_path':str(BASE.relative_to(WORK)),'frame_sha256':sha(BASE),'cover_path':str(COVER.relative_to(WORK)),'cover_sha256':sha(COVER),'cover_dimensions':[1440,1920],'crop_source_pixels':list(crop),'art_placement':[170,610,1100,1144],'title':'假如 AI 让人永远年轻，「白头偕老」会成为远古词汇吗？','revision':'User-approved scientific edit replaces certainty of forever25 with conditional imagined eternal youth.','font':'locally installed PingFang, not redistributed'}
(OUT/'cover-provenance.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(record,ensure_ascii=False,indent=2))
