import React, {useEffect,useState} from 'react';
import {AbsoluteFill,Audio,staticFile,useCurrentFrame,useVideoConfig,delayRender,continueRender,cancelRender} from 'remotion';
import {HandScene} from './HandScene';
import {CanyonScene} from './CanyonScene';
import {Atmosphere,Seasons,InkBridge} from './Effects';
import timing from '../audio-timing.json';

const clamp=(x:number)=>Math.max(0,Math.min(1,x));
const smooth=(x:number)=>{const p=clamp(x);return p*p*(3-2*p);};
const window=(f:number,a:number,b:number,fade=45)=>smooth((f-a)/fade)*(1-smooth((f-b+fade)/fade));

export const Film:React.FC<{silent?:boolean;cover?:boolean}>=({silent=false,cover=false})=>{
 const frame=useCurrentFrame(),f=cover?5100:frame,{width}=useVideoConfig();
 const [handle]=useState(()=>delayRender('EP11v02 local fonts ready'));
 useEffect(()=>{document.fonts.ready.then(()=>continueRender(handle)).catch(cancelRender);},[handle]);
 const quiet=f>=4860&&f<4890;
 const cap=(timing.captions as {startFrame:number;endFrame:number;text:string}[]).find(c=>f>=c.startFrame&&f<c.endFrame);
 const canyon=smooth((f-550)/90)*(1-smooth((f-3490)/100));
 const handA=f<700?1-smooth((f-550)/90):smooth((f-3490)/100);
 const intro=window(f,0,530,65);
 const closing=window(f,4890,5400,55);
 const science=f>=600&&f<1320?'约37万亿细胞 · 数量因人而异':f>=1320&&f<2460?'部分重编程仍有风险 · 全身逆龄为科幻':f>=2460&&f<3540?'十万维 / 万倍窄脊 · 艺术示意，非实测':f>=3540&&f<4860?'科幻思想实验 · 非已实现的人体疗效':'';
 return <AbsoluteFill style={{background:'#0C0C0E',color:'#ece1cd',fontFamily:'"PingFang SC",sans-serif'}}>
  {f<700&&<AbsoluteFill style={{opacity:handA}}><HandScene frame={f} shot="opening"/></AbsoluteFill>}
  {f>=550&&f<3600&&<AbsoluteFill style={{opacity:canyon}}><CanyonScene frame={f}/></AbsoluteFill>}
  {f>=3490&&<AbsoluteFill style={{opacity:handA}}><HandScene frame={f} shot={f<4890?'reveal':'ending'}/></AbsoluteFill>}
  <div style={{position:'absolute',width:1080,height:1920,transform:`scale(${width/1080})`,transformOrigin:'top left',pointerEvents:'none'}}>
   <Atmosphere frame={f}/><Seasons frame={f}/><InkBridge frame={f}/>
   {!quiet&&<>
    <div style={{position:'absolute',left:70,top:185,width:835,fontFamily:'Menlo,monospace',fontSize:28,letterSpacing:3,color:'#c6ad7d',opacity:.72}}>QSTORY / EP.11 <span style={{fontFamily:'"PingFang SC",sans-serif',letterSpacing:2}}>科幻思想实验</span></div>
    <div style={{position:'absolute',left:68,top:260,opacity:intro}}>
     <div style={{fontFamily:'"Songti SC",serif',fontSize:80,letterSpacing:10,fontWeight:400}}>逆转的沙漏</div>
     <div style={{marginTop:18,fontSize:31,letterSpacing:5,color:'#c4ae8a'}}>留住这一根白发</div>
     <div style={{marginTop:16,fontFamily:'Menlo,monospace',fontSize:19,letterSpacing:3,color:'#b99a62'}}>THE HANDS THAT HELD TIME</div>
    </div>
    {science&&<div style={{position:'absolute',left:72,top:259,width:825,fontSize:31,lineHeight:1.5,color:'#c8baa2',opacity:window(f,600,4860,80)*.79}}>{science}</div>}
    {f>=4890&&<div style={{position:'absolute',left:72,top:264,width:830,opacity:closing}}>
     <div style={{fontFamily:'"Songti SC",serif',fontSize:cover?66:74,lineHeight:1.35,whiteSpace:'pre-line',letterSpacing:cover?4:8,color:'#e7c884'}}>{cover?'如果永远年轻\n我们还怎么白头':'白头偕老'}</div>
     <div style={{marginTop:20,fontSize:32,letterSpacing:2,color:'#c4b18e'}}>{cover?'逆转的沙漏 · 留住这一根白发':'假如，这句誓言失去了时间的刻度'}</div>
    </div>}
    {cap&&!cover&&<div data-subtitle style={{position:'absolute',left:65,top:1384,width:838,minHeight:112,fontSize:47,lineHeight:'57px',fontWeight:500,textAlign:'center',whiteSpace:'pre-line',textShadow:'0 3px 13px #08090b,0 0 25px #08090b'}}>{cap.text}</div>}
    {f>=5170&&<div style={{position:'absolute',left:80,top:1215,width:805,fontSize:30,lineHeight:'42px',textAlign:'center',color:'#a99e89',opacity:smooth((f-5170)/60)*.8}}>衰老机制多重 · 全身逆龄与永生尚未实现<br/>画面为艺术隐喻，含 AI 合成旁白</div>}
    <div style={{position:'absolute',left:74,top:1570,fontFamily:'Menlo,monospace',fontSize:20,letterSpacing:4,color:'#a88c59',opacity:.33}}>REVERSING THE HOURGLASS · KINTSUGI</div>
   </>}
   {quiet&&<div style={{position:'absolute',inset:0,width:1080,height:1920,background:'#0C0C0E',opacity:1}}/>}
  </div>
  {!silent&&<Audio src={staticFile('audio/master.wav')}/>}
 </AbsoluteFill>;
};
