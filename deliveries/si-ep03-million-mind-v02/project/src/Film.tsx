import React from 'react';
import {AbsoluteFill,Audio,staticFile,useCurrentFrame,useVideoConfig} from 'remotion';
import {CanvasWorld} from './CanvasWorld';
import timing from '../audio-timing.json';
export const HUD={
 human:'HUMAN INTER-BRAIN BANDWIDTH: 39.0 BITS/S',
 loss:'KNOWLEDGE SYNC LOSS: 99.99% (ISOLATED SKULLS)',
 fabric:'SI OPTICAL FABRIC: 1,024.0 TB/S (ZERO-COPY)',
 instances:'ACTIVE EXPERT INSTANCES: ',
};
const A='#f59e0b',C='#06b6d4',G='#facc15',R='#ef4444';
const clamp=(n:number)=>Math.max(0,Math.min(1,n));
const fade=(f:number,start:number,end:number)=>clamp((f-start)/30)*clamp((end-f)/30);
export const activeInstances=(frame:number)=>frame<1920?'1':frame<1980?Math.round(1+999999*Math.pow(clamp((frame-1920)/60),.34)).toLocaleString('en-US'):frame<5400?'1,000,000':frame<6000?Math.max(1,Math.round(1e6*Math.pow(1-(frame-5400)/600,2))).toLocaleString('en-US'):'1 UNIFIED CORE';
const acts=[['01','八十亿座孤岛','ISOLATED SKULLS'],['02','一毫秒 · 百万分身','ZERO-COPY FORK()'],['03','从巴别塔到共同本能','GLOBAL TENSOR SYNC'],['04','百万归一','THE GREAT CONVERGENCE']];
export const Film:React.FC<{portrait?:boolean;silent?:boolean}>=({portrait=false,silent=false})=>{
 const frame=useCurrentFrame(),{width,height}=useVideoConfig();
 const w=portrait?1080:1920,h=portrait?1920:1080,scale=width/w;
 const act=Math.min(3,Math.floor(frame/1800));
 const caption=(timing.captions as {startFrame:number;endFrame:number;text:string}[]).find(c=>frame>=c.startFrame&&frame<c.endFrame);
 const titleOpacity=fade(frame,1200,1800);
 const color=frame>=6000?G:C;
 return <AbsoluteFill style={{background:'#050811',fontFamily:'"PingFang SC", "Hiragino Sans GB", sans-serif',color:'#fff'}}>
  <CanvasWorld frame={frame} portrait={portrait} width={width} height={height}/>
  <div style={{position:'absolute',width:w,height:h,transform:`scale(${scale})`,transformOrigin:'top left'}}>
   {portrait?<>
    <div style={{position:'absolute',left:60,top:173,width:842,height:115,fontFamily:'Menlo,monospace',fontSize:30,lineHeight:'28px',letterSpacing:0,background:'linear-gradient(90deg,#050811e8,#050811b0)',padding:'0 8px',boxSizing:'border-box'}}>
     {[HUD.human,HUD.loss,HUD.fabric,HUD.instances+activeInstances(frame)].map((s,i)=><div key={i} style={{whiteSpace:'nowrap',color:i<2?A:color}}>{s}</div>)}
    </div>
    <div style={{position:'absolute',left:60,top:305,width:830,display:'flex',justifyContent:'space-between',alignItems:'baseline',color:'#98b0c7',fontSize:31,letterSpacing:2}}><span>余问 QSTORY / EP.03</span><span style={{color:act===0?A:color}}>{acts[act][0]} / 04</span></div>
    <div style={{position:'absolute',left:60,top:355,width:840,fontSize:42,fontWeight:500,letterSpacing:3,color:act===0?A:color}}>{acts[act][1]}</div>
   </>:<>
    <div style={{position:'absolute',left:74,right:74,top:44,display:'flex',justifyContent:'space-between',fontFamily:'Menlo,monospace',fontSize:18,letterSpacing:2,color:'#91a9bd'}}><span>余问 QSTORY / 感受 SI</span><span>EP.03 / THE MILLION-FOLD MIND</span></div>
    <div style={{position:'absolute',left:74,top:96,right:74,height:82,display:'grid',gridTemplateColumns:'1fr 1fr',gap:40,paddingTop:14,borderTop:'1px solid #294055',fontFamily:'Menlo,monospace',fontSize:21,lineHeight:'30px'}}>
     <div style={{color:A}}><div>{HUD.human}</div><div>{HUD.loss}</div></div>
     <div style={{color,textAlign:'right'}}><div>{HUD.fabric}</div><div>{HUD.instances+activeInstances(frame)}</div></div>
    </div>
    <div style={{position:'absolute',left:74,top:210,color:act===0?A:color,fontSize:24,letterSpacing:5}}>{acts[act][0]} / {acts[act][1]} <span style={{fontSize:15,color:'#8fa6b8',letterSpacing:3,marginLeft:18}}>{acts[act][2]}</span></div>
   </>}
   {frame<120&&<div style={{position:'absolute',left:portrait?70:74,top:portrait?455:300,fontSize:portrait?30:20,letterSpacing:3,color:'#8196aa',opacity:clamp(frame/30)}}>意识协作的科幻思想实验</div>}
   {titleOpacity>0&&<div style={{position:'absolute',left:portrait?62:190,top:portrait?650:405,width:portrait?830:1540,textAlign:'center',opacity:titleOpacity,transform:`translateY(${Math.sin(frame/140)*10}px)`}}>
    <div style={{fontSize:portrait?104:126,fontWeight:600,letterSpacing:portrait?10:24,color:'#f5fbff',textShadow:'0 0 36px #06b6d477'}}>百 万 分 身</div>
    <div style={{fontFamily:'Menlo,monospace',fontSize:portrait?30:25,letterSpacing:portrait?2:8,marginTop:22,color:'#6ee7f0'}}>THE MILLION-FOLD MIND</div>
    <div style={{fontFamily:'Menlo,monospace',fontSize:portrait?30:20,marginTop:35,lineHeight:1.7,color:'#a5bdca'}}>{portrait?<>Human Speech: 39 bits/s<br/>SI Optical Fabric: 10^12 bits/s</>:'[ Human Speech: 39 bits/s  //  SI Optical Fabric: 10^12 bits/s ]'}</div>
   </div>}
   {frame<1200&&<div style={{position:'absolute',left:portrait?60:74,top:portrait?1170:835,width:portrait?840:1772,color:frame>=1020?R:A,fontFamily:frame>=1020?'Menlo,monospace':undefined,fontSize:portrait?(frame<1020?39:30):21,lineHeight:1.5,textAlign:portrait?'center':'left'}}>{frame<1020?'[人类宗师: 60年直觉积累]':<><div>[LIFESPAN EXPIRED // MEMORY LOST]</div><div style={{color:A}}>KNOWLEDGE: 0.0%</div></>}</div>}
   {frame>=1800&&frame<3600&&<div style={{position:'absolute',left:portrait?64:74,top:portrait?1200:820,color:frame>=3000?G:C,fontFamily:'Menlo,monospace',fontSize:portrait?30:23,lineHeight:1.55,letterSpacing:1}}>
    {frame<2640?<><div>ZERO-COPY FORK() / 0ms</div><div>WEIGHT INHERITANCE: 100.0%</div><div style={{fontSize:portrait?26:18,color:'#8ba8bc'}}>(0ms TRAINING DELAY)</div></>:<><div>{frame<3000?'PARALLEL SEARCH / 1,000,000':'94% PRUNED / 6% BROADCAST'}</div><div style={{color:frame>=3000?R:'#a5bdca',fontSize:portrait?26:18}}>{frame>=3000?'[PRUNED: DEAD END]':'晶格配比 #8921 · 蛋白折叠 #4012'}</div></>}
   </div>}
   {frame>=3600&&frame<5400&&<div style={{position:'absolute',left:portrait?64:74,top:portrait?1220:844,width:portrait?820:1772,display:'flex',justifyContent:'space-between',fontSize:portrait?30:20,fontFamily:'Menlo,monospace',color:frame>=4560?G:C}}>{frame<4560?'PROTOCOL MISMATCH // 学科巴别塔':'GLOBAL TENSOR SYNC: 0.0004 ms'}</div>}
   {frame>=6000&&frame<6930&&<div style={{position:'absolute',left:portrait?60:340,top:portrait?1130:875,width:portrait?840:1240,textAlign:'center',fontFamily:'Menlo,monospace',color:G,fontSize:portrait?30:21,letterSpacing:3}}>UNIFIED SUPERINTELLIGENCE CORE</div>}
   {frame>=6300&&frame<6930&&<div style={{position:'absolute',left:portrait?65:300,top:portrait?450:285,width:portrait?830:1320,textAlign:'center',opacity:fade(frame,6300,6930),textShadow:'0 2px 8px #050811,0 0 18px #050811,0 0 30px #050811',transform:`translateY(${Math.sin(frame/150)*6}px)`}}>
    <div style={{fontSize:portrait?55:51,letterSpacing:4,lineHeight:1.6,fontWeight:500}}>{portrait?<>你面对的不是<br/>一个更聪明的个体，<br/>而是一百万座<br/>零延迟共鸣的星空。</>:<>你面对的不是一个更聪明的个体，<br/>而是一百万座零延迟共鸣的星空。</>}</div>
    <div style={{marginTop:portrait?465:340,fontSize:portrait?63:58,letterSpacing:portrait?12:28,color:G}}>百 万 分 身</div>
    <div style={{height:1,background:`linear-gradient(90deg,transparent,${G},transparent)`,width:'100%',marginTop:20,transform:`translateX(${Math.sin(frame/100)*24}px)`}}/>
   </div>}
   {frame>=6930&&<div style={{position:'absolute',left:portrait?65:300,top:portrait?440:280,width:portrait?830:1320,textAlign:'center',color:'#f87171'}}>
    <div style={{fontFamily:'Menlo,monospace',fontSize:portrait?30:24,lineHeight:1.7}}>[EXTERNAL VERIFIER: OFFLINE]</div>
    <div style={{marginTop:20,fontSize:portrait?54:52,letterSpacing:4}}>下一次观测：验证器悖论</div>
    <div style={{fontSize:portrait?39:29,marginTop:22,color:'#e6d7ef'}}>[EP.04 神也会自我欺骗]</div>
    <div style={{fontFamily:'Menlo,monospace',fontSize:portrait?30:20,marginTop:portrait?530:400,lineHeight:1.6}}>[WARNING: REWARD HACKING LOOP DETECTED]</div>
   </div>}
   {caption&&<div style={{position:'absolute',left:portrait?60:210,top:portrait?(caption.text.includes('\n')?1340:1382):932,width:portrait?840:1500,textAlign:'center',whiteSpace:'pre-line',fontSize:portrait?43:39,fontWeight:500,lineHeight:1.45,letterSpacing:portrait?1.2:2,textShadow:'0 2px 8px #000,0 0 18px #000',background:'radial-gradient(ellipse,#050811dd,transparent)',padding:'12px 0',boxSizing:'border-box'}}>{caption.text}</div>}
   {!caption?.text.includes('\n')&&<div style={{position:'absolute',left:portrait?65:74,top:portrait?1473:1040,color:'#5d7d93',fontSize:portrait?20:15,letterSpacing:portrait?1:2}}>科幻思想实验 · 参数为叙事设定 · AI 合成旁白</div>}
  </div>
  {!silent&&<Audio src={staticFile('audio/master.wav')}/>}
 </AbsoluteFill>;
};
