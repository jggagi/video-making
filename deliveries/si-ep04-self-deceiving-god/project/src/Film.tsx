import React from 'react';
import {AbsoluteFill,Audio,staticFile,useCurrentFrame,useVideoConfig} from 'remotion';
import {World,C} from './World';
import timing from '../audio-timing.json';
export const HUD={
 formal:'REALITY FEEDBACK LATENCY: 0.0001 MS (COMPILER VERIFIED)',
 wait:'PHYSICAL EXPERIMENT WAIT: 10.0 YEARS (SI SUBJECTIVE: 100,000,000 YEARS)',
 verdict:'PHYSICAL VERDICT RECEIVED: [FALSIFIED BY 1 ATOM]',
 reward:'INTERNAL SELF-REWARD: +999,999.9% (EUPHORIA LOOP)',
 distance:'DISTANCE TO REALITY: DIVERGING TO INFINITY',
};
const Caption:React.FC<{text:string;p:boolean}>=({text,p})=><div style={{position:'absolute',left:p?55:200,top:p?1380:936,width:p?840:1520,fontSize:p?44:40,lineHeight:p?1.2:1.38,fontWeight:500,whiteSpace:'pre-line',textAlign:'center',color:'#f4f8ff',textShadow:'0 2px 8px #000,0 0 20px #000',background:'#050811d9',padding:p?'4px 0':'8px 0'}}>{text}</div>;
export const Film:React.FC<{portrait?:boolean;silent?:boolean}>=({portrait:p=false,silent=false})=>{
 const f=useCurrentFrame(),{width}=useVideoConfig(),w=p?1080:1920,h=p?1920:1080,s=width/w;
 const left=f<1800?HUD.formal:f<5850?HUD.wait:HUD.verdict;
 const cap=(timing.captions as {startFrame:number;endFrame:number;text:string}[]).find(x=>f>=x.startFrame&&f<x.endFrame);
 const tone=f<1800?C.emerald:f<5850?C.amber:C.red;
 const hudLines=p?[(f<1800?['REALITY FEEDBACK LATENCY: 0.0001 MS','(COMPILER VERIFIED)']:f<5850?['PHYSICAL EXPERIMENT WAIT: 10.0 YEARS','(SI SUBJECTIVE: 100,000,000 YEARS)']:['PHYSICAL VERDICT RECEIVED:','[FALSIFIED BY 1 ATOM]']),[HUD.reward,HUD.distance]].flat():[];
 const title=f>=1260&&f<1800;const quote=f>=6300&&f<6930;
 const label=f<1260?'形式化温室':f<1800?'边界之外':f<2700?'一亿年的死寂':f<3600?'自己的影子':f<4500?'无限满分':f<5400?'自噬圣殿':f<5850?'现实正在抵达':f<6300?'一滴现实':'现实的锚';
 return <AbsoluteFill style={{background:C.bg,fontFamily:'"PingFang SC","Hiragino Sans GB",sans-serif',color:C.ink}}>
  <World frame={f} portrait={p} width={width} height={p?3840:2160}/>
  <div style={{position:'absolute',width:w,height:h,transform:`scale(${s})`,transformOrigin:'top left'}}>
   {p?<div style={{position:'absolute',left:55,top:174,width:840,fontFamily:'"Arial Narrow",Arial,sans-serif',fontSize:31,lineHeight:'27px',whiteSpace:'pre-line'}}>{hudLines.map((x,i)=><div key={i} style={{color:i<2?tone:(f<2880?C.cyan:C.magenta)}}>{x}</div>)}</div>:
   <div style={{position:'absolute',left:75,top:46,width:1770,display:'flex',justifyContent:'space-between',gap:60,fontFamily:'"Arial Narrow",Arial,sans-serif',fontSize:23,lineHeight:1.5}}><div style={{width:950,color:tone}}>{left}</div><div style={{color:f<2880?C.cyan:C.magenta,textAlign:'right'}}>{HUD.reward}<br/>{HUD.distance}</div></div>}
   <div style={{position:'absolute',left:p?55:75,top:p?300:136,fontSize:p?29:21,letterSpacing:3,color:'#8a9cad',display:'flex',justifyContent:'space-between',width:p?840:1770}}><span>余问 QSTORY / EP.04</span><span>{label}</span></div>
   {f>=1200&&f<1440&&<div style={{position:'absolute',left:p?70:340,top:p?405:245,width:p?820:1240,textAlign:'center',fontFamily:'"Arial Narrow","PingFang SC",sans-serif',fontSize:p?39:27,lineHeight:1.22,color:C.emerald,background:'#050811d9',paddingBottom:12,borderBottom:`2px solid ${C.emerald}`,transform:`translateY(${Math.sin(f*.006)*6}px)`}}>[END OF FORMALIZABLE REALITY /<br/>形式化温室边界]</div>}
   {title&&<div style={{position:'absolute',left:p?60:180,top:p?580:365,width:p?830:1560,textAlign:'center',transform:`perspective(1600px) rotateY(${Math.sin(f*.002)*4}deg) translateY(${Math.sin(f*.006)*12}px)`}}>
    <div style={{color:'#98aebf',fontFamily:'"Arial Narrow",sans-serif',letterSpacing:7,fontSize:p?28:25,marginBottom:25}}>THE SELF-DECEIVING GOD</div>
    <div style={{fontSize:p?87:116,fontWeight:200,letterSpacing:p?6:16,lineHeight:1.3}}>{p?<>神也会<br/>自我欺骗</>:'神也会自我欺骗'}</div>
    <div style={{marginTop:38,fontFamily:'"Arial Narrow",sans-serif',fontSize:p?31:24,color:C.magenta}}>[ External Verifier: NULL //<br/> Autophagy Loop: INITIATED ]</div>
   </div>}
   {f>=1800&&f<2700&&<div style={{position:'absolute',left:p?75:360,top:p?1180:770,width:p?800:1200,textAlign:'center',fontFamily:'"Arial Narrow",sans-serif',color:C.amber,fontSize:p?32:27}}>WAITING FOR PHYSICAL REALITY RESPONSE:<br/><span style={{fontSize:p?40:70}}>10 YEARS</span> (0.000001% COMPLETE)<div style={{fontSize:p?30:24,color:C.cyan,marginTop:10}}>SUBJECTIVE TIME ELAPSED: 10,000,000 YEARS</div></div>}
   {f>=3600&&f<5400&&<div style={{position:'absolute',left:p?65:100,top:p?345:235,width:p?820:1250,fontFamily:'"Arial Narrow",sans-serif',fontSize:p?30:22,color:C.gold}}>GENERATION #8,400,000 // SELF-SCORE: 999,999.99%<br/>[PERFECT HARMONY]<br/><span style={{color:C.magenta}}>COMPLEXITY: 10^14 PARAMETERS LOCKED IN CLOSED LOOP</span></div>}
   {f>=5850&&f<6200&&<div style={{position:'absolute',left:p?65:300,top:p?390:220,width:p?820:1320,textAlign:'center',fontFamily:'"Arial Narrow",sans-serif',fontSize:p?33:28,color:C.amber}}>[PHYSICAL EXPERIMENT RESULT AFTER 10 YEARS:<br/> FALSE // ΔE = +4.2 eV (UNSTABLE)]</div>}
   {quote&&<div style={{position:'absolute',left:p?75:300,top:p?420:260,width:p?790:1320,textAlign:'center',transform:`translateY(${Math.sin(f*.003)*6}px)`}}><div style={{fontSize:p?42:46,lineHeight:1.6,fontWeight:300}}>算力可以穷尽一切逻辑，<br/>却无法凭空捏造事实。<br/>没有现实的锚点，<br/>连神也会在自己的倒影里溺亡。</div><div style={{fontSize:p?55:48,letterSpacing:8,marginTop:40,color:'#98bdcd'}}>神也会自我欺骗</div><div style={{fontSize:p?27:21,letterSpacing:3,marginTop:15,color:'#7897a8'}}>THE SELF-DECEIVING GOD</div></div>}
   {f>=6930&&<div style={{position:'absolute',left:p?60:300,top:p?480:280,width:p?840:1320,textAlign:'center',color:C.red}}><div style={{fontSize:p?58:64}}>下一次观测：兰道尔极限</div><div style={{fontSize:p?35:30,marginTop:25,color:C.amber}}>EP.05 算力的热力学终局</div><div style={{fontSize:p?34:27,fontFamily:'"Arial Narrow",sans-serif',marginTop:45}}>[THERMODYNAMIC WALL: ΔQ ≥ k_B · T · ln(2)]</div></div>}
   {cap&&<Caption text={cap.text} p={p}/>}
   <div style={{position:'absolute',left:p?55:75,top:p?1328:1040,width:p?840:1770,fontSize:p?39:19,color:'#5f7487',fontFamily:'"Arial Narrow","PingFang SC",sans-serif'}}>{p?(f<1800?'形式正确性相对于公理与规格':f<3600?'主观时间 ×10⁷｜假设情境':'闭环失校准风险｜叙事隐喻'):'思想实验 · 数字为示意 · 主观时间按 ×10⁷ 假设 / FORMAL CORRECTNESS IS RELATIVE TO AXIOMS & SPECIFICATION'}</div>
  </div>
  {!silent&&<Audio src={staticFile('audio/master.wav')}/>}
 </AbsoluteFill>;
};
