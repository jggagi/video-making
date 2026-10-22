import React, {useEffect, useRef, useState} from 'react';
import {AbsoluteFill, Audio, cancelRender, continueRender, delayRender, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Geometry} from './Geometry';
import timing from '../audio-timing.json';

const AMBER='#FF9E00', BONE='#FEF3C7', RUST='#DC2626';
const face='"Heiti SC", "PingFang SC", sans-serif';
const mono='Menlo, monospace';
const clamp=(v:number)=>Math.max(0,Math.min(1,v));

export const Film:React.FC<{silent?:boolean;cover?:'A'|'B'|false}>=({silent=false,cover=false})=>{
 const frame=useCurrentFrame(), {width}=useVideoConfig();
 const f=cover==='A'?1680:cover==='B'?4020:frame;
 const [handle]=useState(()=>delayRender('Wait for installed local typography'));
 const hud=useRef<HTMLDivElement>(null);
 useEffect(()=>{let live=true; document.fonts.ready.then(()=>{
  if(!live)return;
  for(const el of Array.from(hud.current?.querySelectorAll<HTMLElement>('[data-row]')??[])){
   if(el.scrollWidth>el.clientWidth)throw Error('HUD exceeds the portrait safe area');
  }
  continueRender(handle);
 }).catch(cancelRender); return()=>{live=false;};},[handle]);
 const quiet=f>=4860;
 const rows=[f<1320?'BIO DECAY: exp(-t/S)':'SI RETENTION: 100.000%', '8K REPLAY · PAIN LOSS 0.0%', 'BURN-IN · PRUNING DISABLED'];
 const cap=timing.captions.find(c=>f>=c.startFrame&&f<c.endFrame);
 const act=f<1320?'01 / MERCIFUL FADING':f<2820?'02 / PERMANENT LOCK':f<4380?'03 / ETERNAL REPLAY':quiet?'04 / PEACE RECLAIMED':'04 / MEMORY OVERLOAD';
 const lockLabels=['SHAME_EVENT_2016: BIT-LOCKED','FAREWELL_VOICE_TREMOR: +0.000 dB LOSS','REGRET_INDEX #8821: IMMUTABLE'];
 const episode=f<1320?'DAY 001 → DAY 030 → DAY 365 → YEAR 10':f<2820?lockLabels[Math.min(2,Math.floor((f-1320)/500))]:f<3900?'YEAR 01 / 03 / 07 / 15':f<4380?'SNR: COLLAPSED / PRESENT BURIED':f<4860?'BUFFER: ETERNAL YESTERDAY':'FORGETTING RESTORED';
 return <AbsoluteFill style={{background:'#120D0A',fontFamily:face,color:BONE}}>
  <div style={{position:'absolute',width:1080,height:1920,transform:`scale(${width/1080})`,transformOrigin:'top left',background:'radial-gradient(ellipse at 46% 44%, #28170B 0%, #160F0A 48%, #120D0A 76%, #0B0806 100%)'}}>
   <svg width={1080} height={1920} viewBox="0 0 1080 1920" style={{position:'absolute',inset:0}}>
    <defs>
     <pattern id="crt-lines" width="2" height="2" patternUnits="userSpaceOnUse"><path d="M0 0H2" stroke="#000" strokeWidth="1" opacity=".04"/></pattern>
     <pattern id="fine-grain" width="7" height="7" patternUnits="userSpaceOnUse"><path d="M1 1h1M4 5h1" stroke={BONE} strokeWidth=".5" opacity=".025"/></pattern>
    </defs>
    <rect width={1080} height={1920} fill="url(#fine-grain)"/>
    <path d="M64 155H920M64 294H920" stroke={AMBER} strokeWidth="1" opacity={quiet?.12:.36}/>
    <Geometry frame={f}/>
    <rect width={1080} height={1920} fill="url(#crt-lines)" pointerEvents="none"/>
    <g opacity={quiet?.06:.16} stroke={AMBER} fill="none" strokeWidth="1">
     <path d="M0 1580H1080M0 1652H1080"/>
     {Array.from({length:20},(_,i)=>{const x=(i*64-f*.065)%1280-64;return <rect key={i} x={x} y={1600} width={30} height={32} rx={5}/>;})}
    </g>
   </svg>
   {!cover&&<div ref={hud} style={{position:'absolute',left:64,top:174,width:856,fontFamily:mono,fontSize:30,lineHeight:'33px',fontVariantNumeric:'tabular-nums',opacity:quiet?.46:1}}>
    {rows.map((text,i)=><div key={i} data-row={i} style={{whiteSpace:'nowrap',color:i===0?AMBER:i===1?BONE:RUST}}>{text}</div>)}
   </div>}
   {!cover&&<>
    <div style={{position:'absolute',left:64,top:326,width:856,fontFamily:mono,fontSize:30,letterSpacing:1,color:AMBER}}>一眼万年 · 第三季 // SEASON 03</div>
    <div style={{position:'absolute',left:60,top:378,width:860,fontSize:77,fontWeight:700,letterSpacing:5}}>无法遗忘的诅咒</div>
    <div style={{position:'absolute',left:64,top:476,width:856,fontFamily:mono,fontSize:26,letterSpacing:1.1,color:AMBER,opacity:.74}}>WHEN FORGETTING BECOMES ILLEGAL</div>
    <div style={{position:'absolute',left:64,top:556,width:856,display:'flex',justifyContent:'space-between',fontFamily:mono,fontSize:27,color:AMBER,opacity:.72}}><span>{act}</span><span>EP.13</span></div>
    {!quiet&&<div style={{position:'absolute',left:64,top:1298,width:856,fontFamily:mono,fontSize:30,color:f>=3900?RUST:AMBER}}>{episode}</div>}
    {quiet&&<>
     <div style={{position:'absolute',left:74,top:1005,width:836,textAlign:'center',fontSize:43,lineHeight:'58px',fontWeight:600,opacity:.78+.22*clamp((f-4890)/120)}}>“我们才终于明白：<br/>不朽的记忆是神明的刑具；<br/>唯有会慢慢褪色的遗憾，<br/>才叫人生。”</div>
     <div style={{position:'absolute',left:64,top:1275,width:856,textAlign:'center',fontFamily:mono,fontSize:27,letterSpacing:2,color:AMBER,opacity:.65}}>一眼万年 · 无法遗忘的诅咒</div>
    </>}
    {f>=5160&&<div style={{position:'absolute',left:64,top:1325,width:856,textAlign:'center',fontSize:30,opacity:.35}}>未来 SI 思想实验 · 遥测与数值均为虚构</div>}
    {cap&&<div data-caption style={{position:'absolute',left:64,top:1384,width:856,fontSize:49,lineHeight:'54px',fontWeight:700,whiteSpace:'pre-line',textAlign:'center',textShadow:'0 2px 6px #120D0A',color:BONE}}>{cap.text}</div>}
   </>}
   {cover&&<>
    <div style={{position:'absolute',left:64,top:186,width:856,fontFamily:mono,fontSize:32,letterSpacing:1,color:AMBER}}>一眼万年 S3 · EP.13</div>
    <div style={{position:'absolute',left:62,top:286,width:856,fontSize:70,fontWeight:700,lineHeight:1.35}}>如果十年前的心碎，<br/>在今天依然像<br/>第一秒那样清晰</div>
    <div style={{position:'absolute',left:64,top:1330,width:856,fontSize:55,fontWeight:600,color:BONE}}>无法遗忘的诅咒</div>
    <div style={{position:'absolute',left:64,top:1425,width:856,fontFamily:mono,fontSize:30,color:AMBER}}>WHEN FORGETTING BECOMES ILLEGAL</div>
   </>}
  </div>
  {!silent&&<Audio src={staticFile('audio/master.wav')}/>}
 </AbsoluteFill>;
};
