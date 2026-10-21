import React,{useEffect,useRef,useState} from 'react';
import {AbsoluteFill,Audio,staticFile,useCurrentFrame,useVideoConfig,delayRender,continueRender,cancelRender} from 'remotion';
import {Geometry} from './Geometry';
import timing from '../audio-timing.json';
const INK='#18181B',SLATE='#52525B',GOLD='#D97706',PAPER='#F4F1EA';
const clamp=(x:number)=>Math.max(0,Math.min(1,x));
export const Film:React.FC<{silent?:boolean;cover?:'A'|'B'|false}>=({silent=false,cover=false})=>{
 const actual=useCurrentFrame(),{width}=useVideoConfig(),f=cover==='A'?4020:cover==='B'?5040:actual;
 const [handle]=useState(()=>delayRender('Wait for local typography'));
 const hud=useRef<HTMLDivElement>(null);
 useEffect(()=>{document.fonts.ready.then(()=>{
  for(const el of Array.from(hud.current?.querySelectorAll<HTMLElement>('[data-row]')??[]))if(el.scrollWidth>el.clientWidth)throw Error('HUD exceeds safe area');
  continueRender(handle);
 }).catch(cancelRender);},[handle]);
 const complete=f>=4380,blank=f>=4860;
 const compression=clamp((f-1320)/(4380-1320));
 const bits=10**(18-(18-Math.log10(128))*compression);
 const bitsLabel=complete?'128 BITS':bits>=1e6?`${bits.toExponential(2).replace('e+',' ×10^')} BITS`:`${Math.round(bits).toLocaleString('en-US')} BITS`;
 const rows=[f>=2820?'SCIENCE: 1 UNIFIED AXIOM':'SCIENCE: 14,820 PATCHES / FRAGMENTED',`K(U): ${bitsLabel}`,complete?'OCCAM: MINIMUM DESCRIPTION REACHED':'OCCAM: SYMBOLIC REGRESSION ACTIVE'];
 const act=f<1320?'01 / THE PATCHWORK':f<2820?'02 / OCCAM’S RAZOR':f<4380?'03 / CONVERGENCE':'04 / THE LAST PAGE';
 const cap=timing.captions.find(c=>f>=c.startFrame&&f<c.endFrame);
 return <AbsoluteFill style={{background:PAPER,color:INK,fontFamily:'"PingFang SC",sans-serif'}}>
  <div style={{position:'absolute',width:1080,height:1920,transform:`scale(${width/1080})`,transformOrigin:'top left'}}>
   <svg width="1080" height="1920" viewBox="0 0 1080 1920" style={{position:'absolute',inset:0}}>
    <defs><pattern id="micro-grid" width="36" height="36" patternUnits="userSpaceOnUse"><path d="M36 0H0V36" fill="none" stroke="#E5E0D5" strokeWidth=".7"/><circle cx="18" cy="18" r=".5" fill="#E5E0D5"/></pattern></defs>
    {!blank&&<><rect width="1080" height="1920" fill="url(#micro-grid)" opacity=".65"/>
     <path d="M64 154H920M64 300H920M64 1520H920" stroke={INK} strokeWidth="1"/>
     <path d="M40 475h12m-6-6v12M934 475h12m-6-6v12M40 1280h12m-6-6v12M934 1280h12m-6-6v12" fill="none" stroke={SLATE} strokeWidth="1"/>
    </>}
    <Geometry frame={f}/>
   </svg>
   {!blank&&!cover&&<div ref={hud} style={{position:'absolute',left:64,top:174,width:856,fontFamily:'Menlo,monospace',fontSize:30,lineHeight:'32px',fontVariantNumeric:'tabular-nums',fontWeight:400}}>{rows.map((r,i)=><div key={i} data-row={i} style={{whiteSpace:'nowrap',color:i===2?(f<2820?'#E11D48':GOLD):INK}}>{r}</div>)}</div>}
   {!blank&&!cover&&<>
    <div style={{position:'absolute',left:64,top:328,width:856,display:'flex',justifyContent:'space-between',fontFamily:'Menlo,monospace',fontSize:27,color:SLATE}}><span>一眼万年 / EP.12 FINALE</span><span>{act}</span></div>
    <div style={{position:'absolute',left:62,top:381,width:858,fontSize:62,fontWeight:500,letterSpacing:4}}>最 后 一 行 公 式</div>
    <div style={{position:'absolute',left:66,top:470,fontFamily:'Menlo,monospace',fontSize:24,letterSpacing:3,color:SLATE}}>THE FINAL EQUATION</div>
    <div style={{position:'absolute',left:64,top:1310,width:856,fontFamily:'Menlo,monospace',fontSize:30,color:f<2820?'#E11D48':GOLD,letterSpacing:.2}}>{f<1320?'14,820 PATCHES. ONE UNFINISHED SKY.':f<2820?'REMOVE A CIRCLE. REVEAL A LAW.':f<3600?'FOUR LANGUAGES. ONE GEOMETRY.':f<4380?'1 EQUATION / RESIDUAL MYSTERY: 0.000%':'THE LAST PAGE IS ALMOST EMPTY.'}</div>
   </>}
   {blank&&!cover&&<>
    <div style={{position:'absolute',left:64,top:220,width:856,fontFamily:'Menlo,monospace',fontSize:29,letterSpacing:2,color:SLATE}}>一眼万年 / THE FINAL EQUATION</div>
    <div style={{position:'absolute',left:64,top:286,width:856,fontSize:57,fontWeight:500,letterSpacing:4}}>最后一行公式</div>
    <div style={{position:'absolute',left:64,top:380,width:856,fontFamily:'Menlo,monospace',fontSize:28,color:GOLD}}>1 UNIFIED AXIOM / 128 BITS</div>
    <div style={{position:'absolute',left:84,top:958,width:808,textAlign:'center',fontFamily:'Menlo,"PingFang SC",monospace',fontSize:28,lineHeight:'37px',color:SLATE}}>[Q.E.D. // 宇宙全部定律已证明完毕]<br/>[未知剩余：0]</div>
    <div style={{position:'absolute',left:64,top:1184,width:856,textAlign:'center',fontFamily:'"Songti SC",serif',fontSize:49,lineHeight:1.35}}>“什么都还不懂的童年。”</div>
    <div style={{position:'absolute',left:64,top:1294,width:856,textAlign:'center',fontSize:34,letterSpacing:4}}>一 眼 万 年 · 全 剧 终 // THE END</div>
    {f>=5160&&<div style={{position:'absolute',left:64,top:1342,width:856,fontSize:27,textAlign:'center',opacity:.35}}>科幻思想实验｜数值与终极统一为叙事设定</div>}
   </>}
   {!cover&&cap&&<div data-caption style={{position:'absolute',left:64,top:1384,width:856,fontSize:49,lineHeight:'54px',fontWeight:600,whiteSpace:'pre-line',textAlign:'center',color:INK}}>{cap.text}</div>}
   {cover&&<>
    <div style={{position:'absolute',left:64,top:180,width:856,fontSize:31,letterSpacing:3,color:SLATE}}>一眼万年 / EP.12 / 科幻思想实验</div>
    <div style={{position:'absolute',left:64,top:270,width:856,fontSize:67,fontWeight:600,lineHeight:1.35}}>当 AI 把整个宇宙<br/>算成一行公式</div>
    <div style={{position:'absolute',left:64,top:1244,width:856,fontFamily:'"Songti SC",serif',fontSize:58,lineHeight:1.45,fontWeight:500}}>人类却突然开始<br/>怀念童年</div>
    <div style={{position:'absolute',left:64,top:1460,width:856,fontFamily:'Menlo,monospace',fontSize:28,color:GOLD}}>THE FINAL EQUATION / SERIES FINALE</div>
   </>}
  </div>
  {!silent&&<Audio src={staticFile('audio/master.wav')}/>}
 </AbsoluteFill>;
};
