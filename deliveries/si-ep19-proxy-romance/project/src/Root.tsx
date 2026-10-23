import React from 'react';
import {AbsoluteFill,Audio,Composition,staticFile,useCurrentFrame} from 'remotion';
import {World} from './World';
import timing from '../audio-timing.json';
const CHALK='#E2E8F0',GOLD='#D97706';
const hud=['SOCIAL TURING: ON // PROXY: 100.0%','SHADOW: 99.8% // EMOTIONAL BINDING','HOST: 0.05 Hz // EMPTY HULL'];
export const Film:React.FC<{silent:boolean;cover?:false|'A'|'B'}>=({silent,cover=false})=>{
 const f=useCurrentFrame();
 const caption=(timing.captions as {startFrame:number;endFrame:number;text:string}[]).find(c=>f>=c.startFrame&&f<c.endFrame);
 const titleOpacity=f<540?Math.min(1,f/40,Math.max(0,(540-f)/100)):0;
 return <AbsoluteFill style={{background:'#07090C'}}>
  <div style={{position:'absolute',inset:0,width:1080,height:1920,transform:'scale(2)',transformOrigin:'top left',fontFamily:'"PingFang SC", sans-serif',color:CHALK}}>
   <World frame={f}/>
   <svg width="1080" height="1920" style={{position:'absolute',inset:0,pointerEvents:'none'}}><defs><pattern id="linen" width="7" height="9" patternUnits="userSpaceOnUse"><path d="M0 0V9 M0 0H7" stroke="#CBD5E1" strokeWidth=".25" opacity=".035"/></pattern><radialGradient id="vignette"><stop offset="35%" stopColor="#07090C" stopOpacity="0"/><stop offset="100%" stopColor="#000" stopOpacity=".43"/></radialGradient></defs><rect width="1080" height="1920" fill="url(#linen)"/><rect width="1080" height="1920" fill="url(#vignette)"/></svg>
   <div style={{position:'absolute',top:173,left:65,right:173,fontFamily:'"SFMono-Regular", Menlo, monospace',fontSize:30,lineHeight:'30px',letterSpacing:-.35}}>
    {hud.map((line,i)=><div key={line} style={{color:[CHALK,GOLD,'#3F3F46'][i],whiteSpace:'nowrap'}}>{line}</div>)}
   </div>
   <div style={{position:'absolute',left:65,top:334,right:173,opacity:titleOpacity,transform:`translateY(${-Math.min(f,540)*.022}px)`}}>
    <div style={{fontSize:23,letterSpacing:2.7,color:GOLD}}>一 眼 万 年 · 第 四 季</div><div style={{fontSize:19,letterSpacing:1.3,color:'#A1A1AA',marginTop:9}}>SEASON 04: SHADOW SOCIETY</div>
    <div style={{fontSize:79,fontWeight:500,letterSpacing:15,marginTop:14}}>替 身 社 交</div>
    <div style={{fontFamily:'Menlo,monospace',fontSize:22,letterSpacing:1.8,marginTop:15,color:'#A1A1AA'}}>PROXY ROMANCE // EP.19</div>
   </div>
   {f>=4860&&<div style={{position:'absolute',top:430,left:85,right:185,color:CHALK,fontSize:42,fontFamily:'"Songti SC",serif',lineHeight:1.7,letterSpacing:1,transform:`translateY(${-(f-4860)*.025}px)`}}>
     <div style={{fontSize:88,color:GOLD,lineHeight:1,marginBottom:22}}>“</div>
     <div>起初，我们只是派影子</div><div>去应付敷衍的寒暄；</div><div>后来，影子在阳光下学会了相爱，</div><div>而躲在暗处的我们，</div><div style={{color:'#A1A1AA'}}>连怎么拥抱都忘了。”</div>
   </div>}
   {caption&&!cover&&f<5160&&<div style={{position:'absolute',left:65,right:173,bottom:'25%',fontSize:42,lineHeight:1.3,fontWeight:650,whiteSpace:'pre-line',textAlign:'left',color:CHALK,textShadow:'0 2px 9px #07090C'}}>{caption.text}</div>}
   {f>=5160&&!cover&&<><div style={{position:'absolute',top:1460,left:65,fontSize:27,lineHeight:'32px',letterSpacing:3,color:'#A1A1AA'}}>一 眼 万 年 · 替 身 社 交</div><div style={{position:'absolute',top:1355,left:65,fontSize:39,lineHeight:'47px',opacity:.35,color:CHALK}}>未来 SI 思想实验 ·<br/>遥测与数值均为虚构</div></>}
   {cover&&<div style={{position:'absolute',left:65,right:173,top:330,fontSize:60,fontWeight:650,lineHeight:1.45,letterSpacing:1,color:CHALK,background:'#07090CF5',padding:'14px 0'}}><span style={{color:GOLD}}>我们派 AI 替身去谈恋爱，</span><br/>最后却连怎么拥抱<br/>都忘了</div>}
  </div>
  {!silent&&<Audio src={staticFile('audio/master.wav')}/>}
 </AbsoluteFill>;
};
export const Root=()=> <Composition id="PortraitVertical" component={Film} durationInFrames={5400} fps={60} width={2160} height={3840} defaultProps={{silent:true,cover:false as false|'A'|'B'}}/>;
