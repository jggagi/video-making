import React, {useState, useEffect, useRef} from 'react';
import {AbsoluteFill, Audio, staticFile, useCurrentFrame, useVideoConfig, delayRender, continueRender, cancelRender} from 'remotion';
import {Scenes} from './Scenes';
import timing from '../audio-timing.json';
import lexicon from '../telemetry-lexicon.json';

export const TELEMETRY = lexicon.persistent;
const colors = ['#06b6d4', '#d946ef', '#facc15'];
const SYNTHESIS = 'REAL-TIME SYNTHESIS: 悲伤大提琴大调 + 怀旧滤镜 + 共情文案';
const clamp = (n:number) => Math.max(0,Math.min(1,n));

export const Film:React.FC<{silent?:boolean;cover?:boolean}> = ({silent=false,cover=false}) => {
  const f=useCurrentFrame(),{width}=useVideoConfig();
  const [handle]=useState(()=>delayRender('Local fonts ready'));
  const header=useRef<HTMLDivElement>(null);
  useEffect(()=>{document.fonts.ready.then(()=>{
    for(const row of Array.from(header.current?.querySelectorAll<HTMLElement>('[data-telemetry-row]')??[])){
      if(row.scrollWidth>row.clientWidth)throw new Error('Compact telemetry exceeds safe header width');
    }
    continueRender(handle);
  }).catch(cancelRender);},[handle]);
  const black=f>=4861&&f<4891;
  const captured=clamp((f-720)/570);
  const pupil=(.01+.41*captured+.004*Math.sin(f*.016)).toFixed(2);
  const latency=(11.8-2.4*clamp(f/4800)).toFixed(1);
  const compactTelemetry=[`BIOMETRIC LOOP / PUPIL +${pupil} MM`, `REALITY GEN: ${latency} MS / 100% PERSONALIZED`,`FRICTION: 0.00% / ISLANDS: 8,000,000,000`];
  const cap=timing.captions.find((c:{startFrame:number;endFrame:number})=>f>=c.startFrame&&f<c.endFrame);
  const title=f<720?'你的停顿，成了它的指令':f<1320?'多 巴 胺 温 室':f<2040?'每一寸，都刚好合你心意':f<2820?'它替你，磨平了整个世界':f<3600?'八十亿座，一人一间的天堂':f<4380?'坐在一起，却从未抵达彼此':f<4860?'连眼泪，都能实时定制':f<5150?'痛，终于有了真实的形状':'一眼万年 · 多巴胺温室';
  const metric=f<240?'SACCADE DWELL TIME: 140 MS':f<480?'DOPAMINE BASELINE SLOPE: -4.2%/S\n(BOREDOM DETECTED)':f<720?'THUMB DECELERATION: +0.8G':f<1020?'IRL REWARD SYNTHESIS // 12 MS\n100,000 LATENT DESCENT STEPS':f<1320?SYNTHESIS.replace(': ',':\n'):f<2820?'CONFLICT: 0.0% // COMFORT: 100.0%':f<3600?'8,000,000,000 ISOLATED ISLANDS':f<4380?'COGNITIVE DISTANCE: 10,000 LIGHT-YEARS\nSEMANTIC OVERLAP: 0.000%':f<4860?'REWARD RECEPTOR\nDESENSITIZATION: 99.9%':'';
  return <AbsoluteFill style={{background:black?'#000':'#050811',color:'#f8f4ea',fontFamily:'"PingFang SC",sans-serif'}}>
    <div style={{position:'absolute',width:1080,height:1920,transform:`scale(${width/1080})`,transformOrigin:'top left'}}>
      <Scenes frame={cover?3720:f}/>
      {!black&&!(f>=4854&&f<=4860)&&<>
        {!cover&&f<4860&&<div ref={header} style={{position:'absolute',left:64,top:173,width:838,height:115,fontFamily:'Menlo,monospace',fontSize:30,lineHeight:'36px'}}>
          {compactTelemetry.map((text,i)=><div key={i} data-telemetry-row={i} style={{height:36,color:i===2&&f>=4380?'#ef4444':colors[i],whiteSpace:'nowrap',fontVariantNumeric:'tabular-nums'}}>{text}</div>)}
        </div>}
        {cover?<>
          <div style={{position:'absolute',left:64,top:175,width:838,fontSize:32,letterSpacing:4,color:'#06b6d4'}}>一眼万年 / EP.10 / 未来 SI 思想实验</div>
          <div style={{position:'absolute',left:64,top:244,width:838,fontSize:64,lineHeight:1.3,fontWeight:600}}>明明只有10厘米<br/>却活在两个宇宙</div>
          <div style={{position:'absolute',left:64,top:1320,width:838,fontSize:49,lineHeight:1.3,textAlign:'center',color:'#facc15'}}>当AI为你定制<br/>完美的“楚门世界”</div>
        </>:<>
          <div style={{position:'absolute',left:64,top:f>=4891?314:320,width:838,fontSize:f>=720&&f<1320?70:46,fontWeight:500,lineHeight:1.3,letterSpacing:1,color:f>=4891?'#f8d895':'#f6f0e9',opacity:f>=4891?clamp((f-4891)/24):1,textShadow:'0 3px 15px #050811'}}>{title}</div>
          {f>=720&&f<1320&&<div style={{position:'absolute',left:68,top:420,width:838,fontSize:29,letterSpacing:2,color:'#cfb8d3',fontFamily:'Menlo,monospace'}}>THE DOPAMINE GREENHOUSE / EP.10</div>}
          {f<720&&<div style={{position:'absolute',left:68,top:410,fontSize:33,color:'#82a6b6'}}>停下的那一秒，世界开始为你改写</div>}
          {f>=4380&&f<4800&&<div style={{position:'absolute',left:68,top:410,fontSize:32,color:'#edd2e6'}}>在这个连眼泪都能为你实时定制的时代</div>}
          {metric&&<div style={{position:'absolute',left:90,top:1204,width:794,padding:'5px 8px',fontFamily:'Menlo,monospace',fontSize:30,lineHeight:'34px',textAlign:'center',whiteSpace:'pre-line',color:f>=4380?'#ef9b92':f>=1320?'#dac98e':'#88c5cf',background:'rgba(5,8,17,.88)'}}>{metric}</div>}
          {f>=5160&&<div style={{position:'absolute',left:64,top:1278,width:838,fontSize:27,lineHeight:1.35,color:'#a8b9c2',textAlign:'center',opacity:.35}}>未来 SI 思想实验 · 遥测与数值均为虚构</div>}
          {cap&&<div style={{position:'absolute',left:64,top:1384,width:838,fontSize:49,lineHeight:'54px',fontWeight:500,textAlign:'center',textShadow:'0 3px 10px #000,0 0 16px #050811',whiteSpace:'pre-line'}}>{cap.text}</div>}
        </>}
      </>}
    </div>
    {!silent&&<Audio src={staticFile('audio/master.wav')}/>}
  </AbsoluteFill>;
};
