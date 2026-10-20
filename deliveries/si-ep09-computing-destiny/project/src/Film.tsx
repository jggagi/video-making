import React,{useState,useEffect} from 'react';
import {AbsoluteFill,Audio,staticFile,useCurrentFrame,useVideoConfig,delayRender,continueRender,cancelRender} from 'remotion';
import {Scenes} from './Scenes';
import timing from '../audio-timing.json';
export const TELEMETRY=[
'SUBJECTIVE PERCEPTION: "LOVE AT FIRST SIGHT" (SERENDIPITY)',
'SI 10^5-D PHASE SPACE: [COINCIDENCE PROBABILITY = 99.9994% ENGINEERED]',
'RELATIONSHIP LIFESPAN PRE-COMPUTED: DAY 001 -> DAY 489 (ERROR < 3.0 HRS)',
];
const colors=['#f59e0b','#06b6d4','#facc15'];
const clamp=(x:number)=>Math.max(0,Math.min(1,x));
export const Film:React.FC<{silent?:boolean;cover?:boolean}>=({silent=false,cover=false})=>{
 const f=useCurrentFrame(),{width}=useVideoConfig();
 const [handle]=useState(()=>delayRender('Local Chinese fonts'));
 useEffect(()=>{document.fonts.ready.then(()=>continueRender(handle)).catch(cancelRender);},[handle]);
 const cap=timing.captions.find((c:{startFrame:number;endFrame:number})=>f>=c.startFrame&&f<c.endFrame);
 const act=f<1200?0:f<2640?1:f<4140?2:3;
 const title=f<240?'你以为的命中注定':f<480?'原来早已被算穿':f<780?'被算尽的心动':f<1200?'心动的另一面':f<1920?'“你好”之前，结局已写好':f<2640?'第 489 天 · 再见':f<3360?'是谁，安排了这场偶遇？':f<4140?'三根丝线 · 一场宿命':f<4860?'最优解：转身离开':f<5160?'明 知 故 犯':'一眼万年 · 被算尽的心动';
 if(cover)return <AbsoluteFill style={{background:'#050811',color:'#f8f4ea',fontFamily:'"PingFang SC",sans-serif'}}><div style={{position:'absolute',width:1080,height:1920,transform:`scale(${width/1080})`,transformOrigin:'top left'}}><Scenes frame={2100}/><div style={{position:'absolute',left:64,top:173,width:838,color:'#06b6d4',fontSize:32,letterSpacing:5}}>一眼万年 / EP.09 / 科幻思想实验</div><div style={{position:'absolute',left:64,top:230,width:838,fontSize:64,lineHeight:1.25,fontWeight:600}}>假如AI已经算出<br/>第489天，你们分手</div><div style={{position:'absolute',left:64,top:1298,width:838,fontSize:52,lineHeight:1.5,color:'#facc15'}}>你还会，走向那个人吗？</div><div style={{position:'absolute',left:64,top:1430,width:838,fontSize:31,color:'#a9b6bf'}}>被算尽的心动 · 日期与预测精度均为虚构设定</div></div></AbsoluteFill>;
 return <AbsoluteFill style={{background:'#050811',color:'#f8f4ea',fontFamily:'"PingFang SC",sans-serif'}}>
  <div style={{position:'absolute',width:1080,height:1920,transform:`scale(${width/1080})`,transformOrigin:'top left'}}>
   <Scenes frame={f}/>
   <div style={{position:'absolute',left:64,top:173,width:838,height:115,fontFamily:'Menlo,monospace',fontSize:30,lineHeight:'36px',letterSpacing:0}}>
   {TELEMETRY.map((text,i)=>{const travel=Math.max(0,text.length*18.07-838);const phase=((f+i*80)%1800)/1800;const p=phase<.18?0:phase<.7?(phase-.18)/.52:phase<.9?1:(1-phase)/.1;return <div key={text} style={{overflow:'hidden',height:36,color:i===1&&f>=2640?'#d946ef':colors[i],whiteSpace:'nowrap'}}><div style={{width:'max-content',transform:`translateX(${-travel*p}px)`}}>{text}</div></div>;})}
   </div>
   <div style={{position:'absolute',left:64,top:309,width:838,fontSize:f>=480&&f<780?72:48,fontWeight:f>=4860?600:400,lineHeight:1.24,letterSpacing:f>=4860?3:1,color:f>=4860?'#f8d895':'#f2eee8',textShadow:'0 2px 12px #050811'}}>{title}</div>
   {f>=480&&f<780&&<div style={{position:'absolute',left:68,top:406,fontSize:30,letterSpacing:5,color:'#9bd2da',fontFamily:'Menlo,monospace'}}>COMPUTING DESTINY / EP.09</div>}
   <div style={{position:'absolute',left:64,top:1318,width:838,fontSize:30,lineHeight:1.35,color:'#a9b6bf',textAlign:'center'}}>科幻思想实验 · 所有数值与预测均为设定</div>
   {cap&&<div style={{position:'absolute',left:64,top:1374,width:838,fontSize:49,lineHeight:'60px',fontWeight:500,textAlign:'center',textShadow:'0 3px 10px #000,0 0 16px #050811',whiteSpace:'pre-line'}}>{cap.text}</div>}
   <div style={{position:'absolute',left:64,top:1500,width:838,height:3,background:'#18313d'}}><div style={{width:`${f/5399*100}%`,height:'100%',background:colors[act===0?0:act===3?2:1]}}/></div>
  </div>
  {!silent&&<Audio src={staticFile('audio/master.wav')}/>}
 </AbsoluteFill>;
};
