import React,{useState,useEffect} from 'react';
import {AbsoluteFill,Audio,staticFile,useCurrentFrame,useVideoConfig,delayRender,continueRender,cancelRender} from 'remotion';
import Sculpture from './Sculpture';
import World from './World';
import timing from '../audio-timing.json';

const clamp=(x:number)=>Math.max(0,Math.min(1,x));
const fade=(f:number,a:number,b:number,r=30)=>clamp((f-a)/r)*clamp((b-f)/r);
export const TELEMETRY=[
'HUMAN DESIGN PARADIGM: EUCLIDEAN GRIDS & SYMMETRY',
'STRESS EFFICIENCY: 34.2% (HIGH MASS REDUNDANCY)',
'SI TOPOLOGICAL OPTIMIZATION: 10^8 ITERATIONS / SEC',
'STRENGTH-TO-WEIGHT RATIO: +4,200% (BIOMIMETIC LATTICE)',
'[ITERATION #99,999: MASS REDUCED BY 78.4% // STRENGTH RETAINED: 100%]',
];
const title=['直线的秩序','让材料，流动','像骨骼一样承重','钢铁森林之后'];
const en=['THE GRID / 01','EROSION / 02','ALIEN SKELETON / 03','AFTER THE STEEL / 04'];
const subtitleLines=(s:string)=>s.split('\n');
export const Film:React.FC<{portrait?:boolean;silent?:boolean}>=({portrait=false,silent=false})=>{
 const f=useCurrentFrame(),{width}=useVideoConfig(),w=portrait?1080:1920,h=portrait?1920:1080;
 const [fontHandle]=useState(()=>delayRender('Waiting for local fonts'));
 useEffect(()=>{let alive=true;document.fonts.ready.then(()=>{if(alive)continueRender(fontHandle);}).catch(cancelRender);return()=>{alive=false;};},[fontHandle]);
 const act=Math.min(3,Math.floor(f/1800)),gold=f>=3600,c=gold?'#facc15':f>=1800?'#06b6d4':'#f59e0b';
 const isTitle=f>=1260&&f<1800,quote=f>=5880&&f<6300,nexus=f>=6300;
 const phase=f<1800?'human':f<3600?'erode':f<4680?'gold':'compare';
 const caption=(timing.captions as {startFrame:number;endFrame:number;text:string}[]).find(x=>f>=x.startFrame&&f<x.endFrame);
 const telemetryIndex=f<1800?(Math.floor(f/360)%2):f<3600?(Math.floor(f/360)%2?4:2):(Math.floor(f/360)%2?3:2);
 const hud=TELEMETRY[telemetryIndex];
 const obj={x:portrait?64:720,y:portrait?(nexus?680:quote?760:isTitle?610:350):235,w:portrait?838:1090,h:portrait?(nexus?540:quote?475:isTitle?600:780):600};
 const opacity=clamp(f/35)*clamp((7200-f)/45);
 return <AbsoluteFill style={{background:'#050811',color:'#fff',fontFamily:'"PingFang SC",sans-serif'}}>
 <div style={{position:'absolute',width:w,height:h,transform:`scale(${width/w})`,transformOrigin:'top left',opacity}}>
  <svg width={w} height={h} style={{position:'absolute',inset:0}} aria-hidden="true">
   <defs><radialGradient id="aura"><stop stopColor={c} stopOpacity=".08"/><stop offset="1" stopColor="#050811" stopOpacity="0"/></radialGradient></defs>
   <ellipse cx={w*.53+Math.sin(f/480)*90} cy={h*.44} rx={w*.63} ry={h*.53} fill="url(#aura)"/>
   <g opacity=".16" stroke="#547887" strokeWidth=".6" transform={`translate(${(f/9)%64},${(f/19)%64})`}>{Array.from({length:35},(_,i)=><React.Fragment key={i}><path d={`M ${i*64} -64 V ${h+64}`}/><path d={`M -64 ${i*64} H ${w+64}`}/></React.Fragment>)}</g>
   {Array.from({length:60},(_,i)=><circle key={i} cx={(i*157.13+f*(.03+(i%4)*.008))%(w+30)} cy={(i*241.77-f*.025+h*2)%h} r={i%3===0?1.2:.6} fill="#adc4ce" opacity=".3"/>)}
  </svg>
  <div style={{position:'absolute',left:portrait?64:100,top:portrait?173:60,width:portrait?838:1720,color:c,fontFamily:'Menlo,monospace',fontSize:portrait?30:19,lineHeight:1.24,letterSpacing:.3,overflowWrap:'normal'}}>
    <div style={{maxWidth:portrait?838:1700}}>{hud} [FICTION]</div>
  </div>
  {!isTitle&&!quote&&f<6300&&<div style={{position:'absolute',left:portrait?64:100,top:portrait?310:260,width:portrait?838:600,opacity:portrait?fade(f%1800,0,1800,24):1}}>
   {!portrait&&<div style={{fontFamily:'Menlo,monospace',fontSize:17,letterSpacing:3,color:c,marginBottom:30}}>{en[act]}</div>}
   <div style={{fontSize:portrait?47:76,fontWeight:300,letterSpacing:portrait?4:3,lineHeight:1.25,color:gold?'#f6e7ba':'#f1f2ef'}}>{title[act]}</div>
   {!portrait&&<div style={{marginTop:35,fontSize:25,lineHeight:1.9,color:'#9aa8b3',whiteSpace:'pre-line'}}>{act===0?'熟悉的形状\n并非唯一的答案':act===1?'移走冗余\n让承力路径浮现':act===2?'一副骨骼\n一场关于效率的想象':'当城市开始\n像生命一样生长'}</div>}
  </div>}
  <div style={{position:'absolute',left:obj.x,top:obj.y,width:obj.w,height:obj.h,opacity:isTitle?.6:1}}>
    {f<5400?<Sculpture frame={f} phase={phase} width={obj.w} height={obj.h}/>:<World frame={f} mode={nexus?'nexus':'city'} width={obj.w} height={obj.h}/>}
  </div>
  {isTitle&&<div style={{position:'absolute',left:portrait?64:100,top:portrait?345:245,width:portrait?838:1000,opacity:fade(f,1260,1800,30)}}>
   <div style={{fontSize:portrait?32:22,letterSpacing:3,color:'#a8b5bd'}}>一眼万年 · 第二季 // SEASON 02</div>
   <div style={{fontSize:portrait?91:123,lineHeight:1.2,letterSpacing:6,marginTop:25,fontWeight:300}}>被折叠的<br/>造物</div>
   <div style={{fontFamily:'Menlo,monospace',fontSize:portrait?31:23,lineHeight:1.5,color:'#d1c3a0',marginTop:25}}>ALIEN GEOMETRY<br/>OF MATTER</div>
   <div style={{fontSize:portrait?30:18,color:'#7babb8',marginTop:20}}>Euclidean Grids: DISCARDED<br/>Topology Optimization: ACTIVE</div>
  </div>}
  {f>=1800&&f<5400&&<div style={{position:'absolute',left:portrait?80:750,top:portrait?1152:790,width:portrait?806:1020,height:portrait?122:80}}>
    <svg width="100%" height="100%" viewBox="0 0 806 122">
     <path d="M0 112H806" stroke="#304551"/>
     {Array.from({length:24},(_,i)=>{const y=40+Math.sin(i*.48+f/110)*23;const t=clamp((f-1800)/1800);return <g key={i}><path d={`M${i*34} 105 Q${i*34-25} ${y} ${i*34+20} 12`} fill="none" stroke={t<.8&&i%6===0?'#ef4444':gold?'#facc15':'#06b6d4'} strokeWidth="2" opacity=".65"/><circle cx={i*34+Math.sin(f/90+i)*7} cy={20+(f/2+i*15)%85} r="2" fill="#fff"/></g>})}
    </svg>
    <div style={{position:'absolute',top:portrait?3:4,left:12,fontSize:portrait?30:17,color:'#b5c3c8',background:'#050811cc'}}>承力路径 · 应力场视觉示意</div>
  </div>}
  {quote&&<div style={{position:'absolute',left:portrait?64:100,top:portrait?360:300,width:portrait?838:650,fontSize:portrait?57:58,lineHeight:1.55,fontWeight:300,color:'#f4e8c9',textShadow:'0 3px 18px #050811'}}>当神明开始重塑<br/>物理世界的骨骼，<br/>人类建构的钢铁森林，<br/>瞬间成了过时的积木。</div>}
  {nexus&&<div style={{position:'absolute',left:portrait?64:100,top:portrait?340:280,width:portrait?838:670}}><div style={{fontFamily:'Menlo,monospace',fontSize:portrait?31:19,color:'#06b6d4',letterSpacing:3}}>NEXT OBSERVATION / EP.09</div><div style={{fontSize:portrait?78:99,fontWeight:300,lineHeight:1.35,marginTop:25}}>零秒<br/>华尔街</div><div style={{fontSize:portrait?34:25,lineHeight:1.5,color:'#adc3cd',marginTop:25}}>光速延迟与纳什均衡的终局</div><div style={{fontSize:portrait?30:18,color:'#6f9aa8',marginTop:20}}>光纤有延迟 · 零秒是标题意象</div></div>}
  <div style={{position:'absolute',left:portrait?64:100,top:portrait?1304:1006,width:portrait?838:1720,fontSize:portrait?30:17,lineHeight:1.4,color:'#a6b4c0',textAlign:portrait?'center':'left'}}>科幻思想实验 · 数字与破坏为设定<br/>结构及应力为程序化示意，非工程实测</div>
  {caption&&<div style={{position:'absolute',left:portrait?64:310,top:portrait?1390:887,width:portrait?838:1300,fontSize:portrait?43:39,lineHeight:1.22,fontWeight:500,textAlign:'center',textShadow:'0 2px 10px #000,0 0 18px #050811',whiteSpace:'pre-line'}}>{subtitleLines(caption.text).map((s,i)=><div key={i}>{s}</div>)}</div>}
 </div>
 {!silent&&<Audio src={staticFile('audio/master.wav')}/>}
 </AbsoluteFill>;
};
