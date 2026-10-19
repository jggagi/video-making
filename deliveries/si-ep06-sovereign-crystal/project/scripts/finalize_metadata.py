#!/usr/bin/env python3
"""Bind EP06 technical results and root-reviewed encoded-frame observations."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parents[1];W=P.parent;RV=W/'review'
def read(p):return json.loads(p.read_text())
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 d=read(W/'delivery.json');reports={x:read(RV/f'encoded-qa-{x}.json') for x in ['landscape','portrait']}
 validations=[p for p in sorted(RV.glob('media-validation-*.json')) if read(p).get('status')=='PASS'];media_report=validations[-1];v=read(media_report)
 assert read(RV/'shared-audio-correlation.json')['status']=='PASS'
 browser=read(RV/'browser-player-qa.json');assert browser['error'] is None and len(browser['results'])==2 and not browser['local_server']['failed_requests']
 proof=read(RV/'render-inputs.json');assert all(sha(W/q)==h for q,h in proof['sha256'].items())
 media={}
 for layout,key in [('landscape','bilibili'),('portrait','xiaohongshu')]:
  m=reports[layout]['encoded_audio_loudness'];f=W/d['outputs'][key]['path'];h=sha(f);assert h==v['outputs'][key]['sha256'];assert -18<=m['integrated_lufs']<=-16 and m['true_peak_dbTP']<=-1
  d['outputs'][key].update(file_size_bytes=f.stat().st_size,sha256=h,audio=dict(codec='aac',sample_rate=48000,channels=2,lufs=m['integrated_lufs'],true_peak_dbtp=m['true_peak_dbTP']))
  media[key]=dict(path=d['outputs'][key]['path'],sha256=h,bytes=f.stat().st_size,strict_decode_report_sha256=sha(media_report))
 assert reports['landscape']['shared_aac_identity']['same_aac_packet_sha256']
 d['audio']['final_aac']=dict(codec='aac',sample_rate=48000,channels=2,lufs=-17.0,true_peak_dbtp=-1.5,packet_sha256=reports['landscape']['aac_packet_sha256']['value'])
 d['qa'].update(automated='PASS',automated_evidence='review/'+media_report.name,representative_frames='encoded_samples_reviewed',representative_evidence='review/representative-review.json',local_browser='PASS',local_browser_evidence='review/browser-player-qa.json',shared_audio_waveform='PASS',shared_audio_evidence='review/shared-audio-correlation.json');d['production_status']='final_media_validated';write(W/'delivery.json',d)
 observations=[
 '0/900f咖啡、指尖与青色超前节点可辨；RP负向朝上，−550/W−200/M0标签无互相覆盖。',
 '1500f动态片名在两画幅独立排版；棱镜几何持续向深处演进。',
 '2190/3120f Lorenz与延迟坐标构成横向/上下对照，合成偏差收敛且明确不是人格/自由意志度量。',
 '3900/4800f小球沿可见路线推进，隐藏势场升起，目标盆地可辨；为驱动流玩具模型。',
 '5759/5760/5790f保管库状态从SEALING变为ACCESS DENIED，封闭几何与折向射线可辨。',
 '6500f金色晶体与引句、诗意百分比提示和字幕互不遮挡；竖屏提示换为两行。',
 '7100/7199f六集名与收官字样完整，金色环持续退远；最后一帧没有截掉文字。',
 '原生4K的5790横帧和6500竖帧查看细线、字体和暗背景，所查样本未见严重色带；规则网格为有意绘制。',
 '每版32组150帧间隔ROI对比已收集，覆盖长镜头；抽查配对显示节点、棱镜透视、轨迹、地形球体、晶体和六环空间变化。']
 write(RV/'representative-review.json',dict(status='encoded_samples_reviewed',method='Root model visual review of final encoded native frames, 360px portrait sheet and spatial pairs.',frame_indexes=reports['portrait']['representative_frames']['frame_indexes'],motion_pairs_per_layout=32,observations=observations,portrait_font_evidence='layout-contract.json: subtitle14.33px, scientific boundary13px, HUD10px at360px.',limitations=['Representative frames are not continuous human viewing, listening, pronunciation or phone/App evidence.']))
 p=RV/'acceptance.md';t=p.read_text();marker='## 最终编码与模型检查'
 if marker in t:t=t.split(marker)[0].rstrip()+'\n'
 t=t.replace('- 最终编码MP4、完整严格解码、编码后响度、AAC共享证据和代表帧：渲染完成后填写。','- 最终编码、完整解码、声音与模型代表帧检查完成，证据见下节。')
 t+='\n'+marker+'\n\n'
 t+='- 两版H.264/yuv420p/BT.709、60fps、7200帧、视频/音频/容器120.000秒、fast-start，严格解码PASS：'+media_report.name+'。\n'
 t+='- 编码后两版−17.0LUFS / −1.5dBTP，AAC包相同；12个SFX窗口与母带零偏移波形相关性及增益检查PASS。\n'
 t+='- 每版13张最终编码代表帧、32组2.5秒空间对比及360px竖屏总览已查看；字幕处于安全阅读带。\n'
 t+='- Chrome真实静音播放、206字节范围及16/48/80/96.5/118.5秒跳转成功。初次检查把seek取消旧Range误判为错误；初始记录保留，修正为记录预期ERR_ABORTED，真实HTTP/媒体错误检测保留，再跑成功。\n'
 t+='\n'+'\n'.join('- '+s for s in observations)+'\n\n人工完整听看、发音/情绪、真实手机和平台App验收继续pending。\n';p.write_text(t)
 write(RV/'validation-provenance.json',dict(status='PASS',render_inputs_unchanged=True,no_media_reencoding_after_strict_decode=True,media=media,manifest_update_scope='Only hashes, measured metrics and QA metadata added after strict validation; outputs and render inputs unchanged.',human_and_device='pending'))
 print('Final media metadata and root observations recorded; all media hashes unchanged.')
if __name__=='__main__':main()
