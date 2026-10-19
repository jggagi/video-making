import React from 'react';
import {AbsoluteFill, Audio, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {CanvasWorld} from './CanvasWorld';
import timing from '../audio-timing.json';

const cyan='#06b6d4',amber='#f59e0b',gold='#facc15',magenta='#d946ef';
const chapters=[['01','影子先于念头','THE PRE-ECHO'],['02','透明的镜像','THE GLASS BOX'],['03','温柔的斜坡','THE GENTLE NUDGE'],['04','把边界交还给你','THE SOVEREIGN CRYSTAL']];
const qualifiers=[
 '平均RP示意，非单次读心；青色影子为思想实验',
 'Lorenz合成系统 · 轨迹误差≠自由意志 · 非人格重建',
 '势场与偏好推断为玩具模型，不是多巴胺实测',
 '设计愿景 · 隐私不保证不可预测，随机性不等于自由',
];
const episodes=['01 一眼万年','02 7±2的囚笼','03 百万分身','04 神也会自我欺骗','05 兰道尔极限','06 主权心印'];
const clamp=(n:number)=>Math.max(0,Math.min(1,n));
const fade=(f:number,a:number,b:number)=>clamp((f-a)/30)*clamp((b-f)/30);
export const Film:React.FC<{portrait?:boolean;silent?:boolean}>=({portrait=false,silent=false})=>{
 const f=useCurrentFrame(),{width,height}=useVideoConfig(),w=portrait?1080:1920,h=portrait?1920:1080,scale=width/w;
 const act=Math.min(3,Math.floor(f/1800)),a=chapters[act],color=act===3?gold:act===2?magenta:cyan;
 const captions=(timing as {captions?:{startFrame:number;endFrame:number;text:string}[]}).captions??[];
 const caption=captions.find(c=>f>=c.startFrame&&f<c.endFrame);
 const residual=(64*Math.pow(.001/64,clamp((f-1800)/1320))).toFixed(f>=3040?3:1);
 const telemetry=act===0?'RP −550 / W −200 / M 0 MS':act===1?`MODEL TRAJECTORY ERROR: ${residual}%`:act===2?'REWARD LANDSCAPE: SIMULATION':f<5760?'LOCAL VAULT: SEALING':'LOCAL VAULT: ACCESS DENIED';
 const drift=`perspective(1400px) rotateY(${Math.sin(f/180)*2.3}deg) rotateX(${Math.cos(f/220)*1.5}deg) translateY(${Math.sin(f/135)*9}px)`;
 return <AbsoluteFill style={{background:'#050811',fontFamily:'"PingFang SC","Hiragino Sans GB",sans-serif',color:'#f5f7fb'}}>
  <CanvasWorld frame={f} portrait={portrait} width={width} height={height}/>
  <div style={{position:'absolute',width:w,height:h,transform:`scale(${scale})`,transformOrigin:'top left'}}>
   {portrait?<>
    <div style={{position:'absolute',left:64,top:173,width:838,height:116,background:'#050811ed',fontFamily:'Menlo,monospace',fontSize:30,lineHeight:'37px',color}}>
     <div style={{color:amber}}>RP → W GAP: ≈350 MS</div>
     <div>{act===3?'SOVEREIGN AGENT / LOCAL':act===2?'INVERSE RL / TOY MODEL':'PREDICTION: THOUGHT EXPERIMENT'}</div>
     <div>{telemetry}</div>
    </div>
    <div style={{position:'absolute',left:64,top:322,width:838,display:'flex',justifyContent:'space-between',color:'#8ea5b8',fontFamily:'Menlo,monospace',fontSize:30}}><span>一眼万年 / EP.06</span><span style={{color}}>0{act+1} / 04</span></div>
    <div style={{position:'absolute',left:64,top:372,width:838,fontSize:49,letterSpacing:3,color}}>{a[1]}</div>
    <div style={{position:'absolute',left:64,top:438,width:838,fontFamily:'Menlo,monospace',fontSize:30,color:'#9fb5c9'}}>{a[2]}</div>
   </>:<>
    <div style={{position:'absolute',left:74,right:74,top:42,display:'flex',justifyContent:'space-between',fontFamily:'Menlo,monospace',fontSize:18,letterSpacing:3,color:'#96aabb'}}><span>一眼万年 / SUPERINTELLIGENCE</span><span>EP.06 / SEASON FINALE</span></div>
    <div style={{position:'absolute',left:74,right:74,top:91,borderTop:'1px solid #294052',paddingTop:18,display:'flex',justifyContent:'space-between',fontFamily:'Menlo,monospace',fontSize:20,lineHeight:'34px'}}>
     <div><div style={{color:amber}}>RP → CONSCIOUS REPORT (W): ≈350 MS / SCHEMATIC</div><div style={{color:cyan}}>SI PREDICTION LEAD: 500 MS / THOUGHT EXPERIMENT</div></div>
     <div style={{color,textAlign:'right'}}><div>{telemetry}</div><div>{act===3?'MINIMAL DISCLOSURE // PRIVACY ≠ UNPREDICTABILITY':act===1?'SYNTHETIC DYNAMICS // NOT A FREE-WILL METRIC':'SIMULATION // NO EMPIRICAL MIND-READING CLAIM'}</div></div>
    </div>
    <div style={{position:'absolute',left:74,top:210,fontSize:29,letterSpacing:3,color}}>{a[0]} / {a[1]} <span style={{marginLeft:24,fontSize:19,fontFamily:'Menlo,monospace',color:'#9fb5c9'}}>{a[2]}</span></div>
    <div style={{position:'absolute',right:74,top:215,fontSize:18,fontFamily:'Menlo,monospace',color:'#8fa8bb'}}>NEUROSCIENCE → DYNAMICS → CHOICE → BOUNDARY</div>
   </>}
   {f<120&&<div style={{position:'absolute',left:portrait?64:74,top:portrait?505:278,fontSize:portrait?43:31,color:amber,opacity:clamp(f/40)}}>如果，影子比你先做选择。</div>}
   {f>=1260&&f<1800&&<div style={{position:'absolute',left:portrait?64:170,top:portrait?660:405,width:portrait?838:1580,textAlign:'center',transform:drift,opacity:fade(f,1260,1800),textShadow:'0 2px 30px #050811,0 0 45px #050811'}}>
    <div style={{fontSize:portrait?96:116,fontWeight:600,letterSpacing:portrait?9:22,color:gold}}>主 权 心 印</div>
    <div style={{marginTop:32,fontFamily:'Menlo,monospace',fontSize:portrait?35:27,letterSpacing:portrait?3:8,lineHeight:1.6,color:'#d5eef2'}}>{portrait?<>THE SOVEREIGN<br/>SOUL CRYSTAL</>:'THE SOVEREIGN SOUL CRYSTAL'}</div>
    <div style={{marginTop:35,fontSize:portrait?38:29,color:amber}}>当算法比你更懂你</div>
   </div>}
   {f>=5400&&f<6300&&<div style={{position:'absolute',left:portrait?64:122,top:portrait?1125:796,width:portrait?838:1676,fontSize:portrait?32:23,textAlign:'center',color:gold,fontFamily:'Menlo,monospace',lineHeight:1.5}}>{f<5760?'LOCAL MEMORY → MINIMAL DISCLOSURE':portrait?<>ZERO-KNOWLEDGE / PROOF ONLY<br/>ε-DP: BOUNDED DISCLOSURE</>:'ZERO-KNOWLEDGE: PROVE A STATEMENT // ε-DP: BOUNDED DISCLOSURE'}</div>}
   {f>=6300&&f<6900&&<>
    <div style={{position:'absolute',left:portrait?64:160,top:portrait?505:280,width:portrait?838:1600,textAlign:'center',fontSize:portrait?48:43,lineHeight:1.55,letterSpacing:3,color:gold,transform:drift,textShadow:'0 3px 15px #050811,0 0 35px #050811'}}>把记忆锁进私密的圣殿</div>
    <div style={{position:'absolute',left:portrait?64:150,top:portrait?1225:815,width:portrait?838:1620,textAlign:'center',fontSize:portrait?39:32,color:'#ffdf9b'}}>“百分之一”是诗意表达，不是测量值</div>
   </>}
   {f>=6900&&<div style={{position:'absolute',left:portrait?64:220,top:portrait?505:300,width:portrait?838:1480,textAlign:'center',transform:drift,textShadow:'0 3px 18px #050811'}}>
    <div style={{fontSize:portrait?52:68,letterSpacing:5,color:gold}}>一眼万年 · 第一季终</div>
    <div style={{marginTop:20,fontSize:portrait?30:24,fontFamily:'Menlo,monospace',color:'#dddcb8'}}>THE SILICON OBSERVER</div>
    <div style={{marginTop:16,fontSize:portrait?30:24,fontFamily:'Menlo,monospace',color:gold}}>SEASON 01 COMPLETE</div>
    <div style={{marginTop:portrait?70:55,display:'grid',gridTemplateColumns:portrait?'1fr':'1fr 1fr 1fr',gap:portrait?21:26,fontSize:portrait?39:27,color:'#e8eff6'}}>{episodes.map((e,i)=><span key={e} style={{color:i===5?gold:'#c8d5df',background:'#050811b8',padding:'2px 8px'}}>{e}</span>)}</div>
   </div>}
   <div style={{position:'absolute',left:portrait?64:74,top:portrait?1288:892,width:portrait?838:1772,fontSize:portrait?39:22,lineHeight:1.2,color:'#a3b8cb',textAlign:'center',background:'#050811b8'}}>{qualifiers[act]}</div>
   {caption&&<div style={{position:'absolute',left:portrait?64:180,top:portrait?1383:947,width:portrait?838:1560,height:portrait?113:124,fontSize:portrait?43:40,fontWeight:500,lineHeight:portrait?1.22:1.45,letterSpacing:portrait?0:2,textAlign:'center',whiteSpace:'pre-line',padding:'4px 0',boxSizing:'border-box',background:'radial-gradient(ellipse,#050811f0,transparent)',textShadow:'0 2px 8px #000,0 0 18px #000'}}>{caption.text}</div>}
  </div>
  {!silent&&<Audio src={staticFile('audio/master.wav')}/>}
 </AbsoluteFill>;
};
