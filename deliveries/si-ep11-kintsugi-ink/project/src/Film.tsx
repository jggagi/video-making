import React, {useEffect, useState} from 'react';
import {AbsoluteFill, Audio, staticFile, useCurrentFrame, useVideoConfig, delayRender, continueRender, cancelRender} from 'remotion';
import {Terrain} from './Terrain';
import {Eternity} from './Eternity';
import timing from '../audio-timing.json';

const clamp=(x:number)=>Math.max(0,Math.min(1,x));
const smooth=(x:number)=>{const t=clamp(x);return t*t*(3-2*t);};
const fiber=Array.from({length:150},(_,i)=>({x:((i*173.719)%1080),y:((i*317.173)%1920),a:(i*2.399963)%6.28,l:12+(i*19.73)%72}));
export const telemetry=(f:number)=>{
 const age=f<1320?20+58.5*smooth(f/1320):78.5-56.5*smooth((f-2820)/1500);
 const entropy=f<1320?89.4*smooth(f/1320):89.4*(1-smooth((f-1740)/1800));
 return [
  `BIOLOGICAL AGE INDEX: ${age.toFixed(1)} YRS${f>=4320?' [KINTSUGI SEALED]':f<1320?' -> 78.5 YRS':' -> 22.0 YRS'}`,
  `PORCELAIN FRACTURE ENTROPY: ${entropy.toFixed(f>=3540?3:1)}%`,
  'KINTSUGI CELLULAR REPROGRAMMING: [MÖBIUS EQUILIBRIUM LOCKED]',
 ];
};

export const Film:React.FC<{silent?:boolean;cover?:boolean}>=({silent=false,cover=false})=>{
 const frame=useCurrentFrame(),{width}=useVideoConfig(),f=cover?5040:frame;
 const [handle]=useState(()=>delayRender('Local typefaces ready'));
 useEffect(()=>{document.fonts.ready.then(()=>continueRender(handle)).catch(cancelRender);},[handle]);
 const cap=(timing.captions as {startFrame:number;endFrame:number;text:string}[]).find(c=>f>=c.startFrame&&f<c.endFrame);
 const quiet=f>=4860&&f<4890;
 const act4=smooth((f-4320)/90);
 const intro=smooth(f/70)*(1-smooth((f-420)/90));
 const line=telemetry(f);
 const heading=f<540?'逆 转 的 沙 漏':f<1320?'墨，顺着时间下落':f<2040?'修复与失控，仅隔一线':f<2820?'让金，找到那道窄脊':f<3600?'这一次，向上流淌':f<4380?'被改写的，不只是白发':f<4860?'没有刻度的时间':f<5160?'白头偕老':'一眼万年 · 逆转的沙漏';
 return <AbsoluteFill style={{background:'#0C0C0E',color:'#e7e1d4',fontFamily:'"PingFang SC",sans-serif'}}>
  <div style={{position:'absolute',width:1080,height:1920,transform:`scale(${width/1080})`,transformOrigin:'top left',overflow:'hidden'}}>
   <svg width="1080" height="1920" style={{position:'absolute'}}>
    <defs>
     <radialGradient id="paper-light"><stop stopColor="#27221b" stopOpacity=".4"/><stop offset="1" stopColor="#0C0C0E" stopOpacity="0"/></radialGradient>
     <linearGradient id="horizon"><stop stopColor="#FBBF24" stopOpacity="0"/><stop offset=".5" stopColor="#FBBF24" stopOpacity=".24"/><stop offset="1" stopColor="#FBBF24" stopOpacity="0"/></linearGradient>
    </defs>
    <ellipse cx={460+25*Math.sin(f/340)} cy={920+30*Math.cos(f/390)} rx="670" ry="790" fill="url(#paper-light)"/>
    <g stroke="#b5a795" strokeWidth=".7" opacity={quiet?0:.027} transform={`translate(${2*Math.sin(f/180)} ${3*Math.cos(f/270)})`}>
     {fiber.map((p,i)=><path key={i} d={`M${p.x} ${p.y}q${p.l/2} ${p.l*Math.sin(p.a)*.4} ${p.l*Math.cos(p.a)} ${p.l*Math.sin(p.a)}`}/>)}
    </g>
    <path d="M80 1321H904" stroke="url(#horizon)"/>
   </svg>
   <div style={{position:'absolute',inset:0,opacity:1-act4}}><Terrain frame={f}/></div>
   {f>=4320&&<div style={{position:'absolute',inset:0,opacity:act4}}><Eternity frame={f}/></div>}
   {quiet&&<div style={{position:'absolute',inset:0,background:'#0C0C0E',opacity:.98}}/>}
   {!quiet&&<>
    <svg width="1080" height="1920" style={{position:'absolute',inset:0,pointerEvents:'none'}}>
     {line.map((s,i)=><text key={i} x="65" y={195+i*31} fill={i===0?(f<1740?'#A1A1AA':'#F59E0B'):i===1?'#52525B':'#F59E0B'} fontFamily="Menlo,monospace" fontSize="30" textLength={Math.min(838,s.length*18)} lengthAdjust="spacingAndGlyphs">{s}</text>)}
    </svg>
    <div style={{position:'absolute',left:65,top:289,width:838,fontSize:30,letterSpacing:2,color:'#a89981'}}>一眼万年 / EP.11 <span style={{color:'#cdb689'}}>科幻推演 · 遥测为示意</span></div>
    <div style={{position:'absolute',left:65,top:353,width:838,fontSize:f<540?76:f>=4890&&f<5160?78:46,letterSpacing:f<540?9:2,fontWeight:400,lineHeight:1.3,color:f>=2040?'#eedab0':'#e7e1d4'}}>{heading}</div>
    {f<540&&<div style={{position:'absolute',left:68,top:465,width:832,fontFamily:'Menlo,monospace',fontSize:25,letterSpacing:2,color:'#a18d6a',opacity:.85}}>D I G I T A L  K I N T S U G I  O F  T I M E</div>}
    {f>=540&&f<1320&&<div style={{position:'absolute',left:68,top:424,fontSize:31,color:'#8e8b85'}}>约 37 万亿细胞 · 人体估计值因人而异</div>}
    {f>=1320&&f<2040&&<div style={{position:'absolute',left:68,top:424,fontSize:31,color:'#9c9893'}}>部分重编程研究，仍有安全与转化难题</div>}
    {f>=2040&&f<2820&&<div style={{position:'absolute',left:68,top:424,fontSize:31,color:'#a68f68'}}>十万维 / 万倍窄脊：艺术隐喻，非实测</div>}
    {f>=2820&&f<4380&&<div style={{position:'absolute',left:68,top:424,fontSize:31,color:'#b5a17a'}}>逆龄轨迹为虚构 · 尚非人体全身疗效</div>}
    {f>=4890&&f<5160&&<div style={{position:'absolute',left:68,top:470,fontSize:35,letterSpacing:4,color:'#ad9874'}}>假如这句誓言，真的成为远古词汇</div>}
    {f>=5160&&<div style={{position:'absolute',left:68,top:1248,width:832,fontSize:28,lineHeight:1.35,color:'#a69a87',opacity:.48,textAlign:'center'}}>科幻思想实验 · 非医学结论<br/>衰老机制多重，人体全身逆龄与永生尚未实现</div>}
    {cap&&<div data-subtitle style={{position:'absolute',left:65,top:1384,width:838,fontSize:49,lineHeight:'52px',fontWeight:500,textAlign:'center',whiteSpace:'pre-line',textShadow:'0 3px 12px #0C0C0E, 0 0 20px #0C0C0E'}}>{cap.text}</div>}
   </>}
   <div style={{position:'absolute',left:70,top:1580,fontSize:24,letterSpacing:4,color:'#9f8c69',opacity:.22}}>REVERSING THE HOURGLASS</div>
  </div>
  {!silent&&<Audio src={staticFile('audio/master.wav')}/>}
 </AbsoluteFill>;
};
