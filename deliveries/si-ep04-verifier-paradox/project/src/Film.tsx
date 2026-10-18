import React from 'react';
import {AbsoluteFill, Audio, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {CanvasWorld} from './CanvasWorld';
import timing from '../audio-timing.json';

export const HUD = {
  formal:'EXTERNAL VERIFIER: LEAN_4 & COMPILER [100.0% DETERMINISTIC]',
  offline:'EXTERNAL VERIFIER: OFFLINE (OPEN-WORLD FOG) // PROXY REWARD ONLY',
  physical:'GROUND-TRUTH ANCHOR: PHYSICAL EXPERIMENT LOCKED',
  reward:'SELF-REWARD SCORE: +99.999% (MAXIMIZED)',
  alignment:'REALITY ALIGNMENT: ',
};
const C='#06b6d4', E='#10b981', A='#f59e0b', M='#d946ef', R='#ef4444', G='#facc15';
const clamp=(x:number)=>Math.max(0,Math.min(1,x));
const fade=(f:number,a:number,b:number)=>clamp((f-a)/36)*clamp((b-f)/36);
const acts=[['01','形式化温室','THE COLD JUDGE'],['02','自己给自己打分','THE MIRROR MAZE'],['03','幻觉大教堂','NARCISSISTIC EQUILIBRIUM'],['04','原子的否决权','THE VETO OF ATOMS']];
export const realityAlignment=(f:number)=>f<1800?'100.0%':f<3600?`${(100-92*clamp((f-1800)/1800)).toFixed(1)}%`:f<5400?`${Math.max(.02,8*(1-clamp((f-3600)/650))).toFixed(2)}%${f>=4250?' [DELUSION LOOP]':''}`:f<5760?'0.02% [DELUSION LOOP]':`${(.02+99.98*clamp((f-5760)/540)).toFixed(1)}%`;
export const Film:React.FC<{portrait?:boolean;silent?:boolean}>=({portrait=false,silent=false})=>{
  const f=useCurrentFrame(),{width,height}=useVideoConfig();
  const w=portrait?1080:1920,h=portrait?1920:1080,scale=width/w;
  const act=Math.min(3,Math.floor(f/1800)), color=act===0?C:act===3?A:R;
  const status=act===0?HUD.formal:act===3?HUD.physical:HUD.offline;
  const lines=act===0?['EXTERNAL VERIFIER: LEAN_4 & COMPILER','[100.0% DETERMINISTIC]']:act===3?['GROUND-TRUTH ANCHOR:','PHYSICAL EXPERIMENT LOCKED']:['EXTERNAL VERIFIER: OFFLINE','(OPEN-WORLD FOG) // PROXY REWARD ONLY'];
  const caption=(timing.captions as {startFrame:number;endFrame:number;text:string}[]).find(c=>f>=c.startFrame&&f<c.endFrame);
  const drift=`perspective(1200px) rotateX(${Math.sin(f/173)*1.1}deg) rotateY(${Math.cos(f/227)*1.8}deg) translateY(${Math.sin(f/143)*7}px)`;
  return <AbsoluteFill style={{background:'#050811',fontFamily:'"PingFang SC", "Hiragino Sans GB", sans-serif',color:'#f3f8ff'}}>
    <CanvasWorld frame={f} portrait={portrait} width={width} height={height}/>
    <div style={{position:'absolute',width:w,height:h,transform:`scale(${scale})`,transformOrigin:'top left'}}>
      {portrait?<>
        <div style={{position:'absolute',left:62,top:173,width:840,height:114,fontFamily:'Menlo,monospace',fontSize:30,lineHeight:'28.5px',padding:'0 5px',boxSizing:'border-box',background:'linear-gradient(90deg,#050811f4,#050811d9)'}}>
          {lines.map((s,i)=><div key={i} style={{color,whiteSpace:'nowrap'}}>{s}</div>)}
          <div style={{color:G,whiteSpace:'nowrap'}}>{HUD.reward}</div>
          <div style={{color:act===0?E:f>=5760?A:M,whiteSpace:'nowrap'}}>{HUD.alignment}{realityAlignment(f)}</div>
        </div>
        <div style={{position:'absolute',left:65,top:316,width:830,display:'flex',justifyContent:'space-between',fontFamily:'Menlo,monospace',fontSize:30,letterSpacing:1,color:'#90a6bc'}}><span>余问 QSTORY / EP.04</span><span style={{color}}>{acts[act][0]} / 04</span></div>
        <div style={{position:'absolute',left:65,top:367,fontSize:44,letterSpacing:4,color}}>{acts[act][1]}</div>
      </>:<>
        <div style={{position:'absolute',left:72,right:72,top:43,display:'flex',justifyContent:'space-between',fontFamily:'Menlo,monospace',fontSize:18,letterSpacing:2,color:'#8ea4b9'}}><span>余问 QSTORY / SUPERINTELLIGENCE</span><span>EP.04 / THE VERIFIER PARADOX</span></div>
        <div style={{position:'absolute',left:72,right:72,top:94,borderTop:'1px solid #294055',paddingTop:16,display:'grid',gridTemplateColumns:'1.25fr 1fr',gap:20,fontFamily:'Menlo,monospace',fontSize:20,lineHeight:'31px'}}>
          <div style={{color}}>{status}</div>
          <div style={{textAlign:'right'}}><div style={{color:G}}>{HUD.reward}</div><div style={{color:act===0?E:f>=5760?A:M}}>{HUD.alignment}{realityAlignment(f)}</div></div>
        </div>
        <div style={{position:'absolute',left:74,top:214,fontSize:25,letterSpacing:4,color}}>{acts[act][0]} / {acts[act][1]} <span style={{fontFamily:'Menlo,monospace',fontSize:16,color:'#8fa6b8',marginLeft:18}}>{acts[act][2]}</span></div>
      </>}
      {f<120&&<div style={{position:'absolute',left:portrait?65:74,top:portrait?460:294,fontSize:portrait?39:24,color:'#b5cbdc',letterSpacing:3,opacity:clamp(f/30)}}>谁来验证，验证者？</div>}
      {f>=1200&&f<1800&&<div style={{position:'absolute',left:portrait?65:170,top:portrait?660:405,width:portrait?830:1580,textAlign:'center',opacity:fade(f,1200,1800),transform:drift}}>
        <div style={{fontSize:portrait?78:108,fontWeight:600,letterSpacing:portrait?8:15,lineHeight:1.5,textShadow:'0 0 30px #06b6d455'}}>{portrait?<>神也会<br/>自我欺骗</>:'神 也 会 自 我 欺 骗'}</div>
        <div style={{fontFamily:'Menlo,monospace',fontSize:portrait?33:27,letterSpacing:portrait?2:7,marginTop:26,color:'#9bdded'}}>{portrait?<>THE VERIFIER<br/>PARADOX</>:'T H E   V E R I F I E R   P A R A D O X'}</div>
        <div style={{fontFamily:'Menlo,monospace',fontSize:portrait?30:22,marginTop:34,lineHeight:1.6,color:'#c6a6d1'}}>{portrait?<>[ Verifier Signal: NULL<br/>Goodhart's Law: ACTIVE ]</>:"[ Verifier Signal: NULL  //  Goodhart's Law: ACTIVE ]"}</div>
      </div>}
      {f>=6300&&f<6930&&<div style={{position:'absolute',left:portrait?68:225,top:portrait?475:288,width:portrait?826:1470,textAlign:'center',opacity:fade(f,6300,6930),transform:drift,textShadow:'0 3px 12px #050811,0 0 35px #050811'}}>
        <div style={{fontSize:portrait?54:51,lineHeight:1.6,fontWeight:500,letterSpacing:2}}>{portrait?<>“没有现实校准的<br/>超级智能，<br/>不过是一场算力<br/>无穷大的疯魔。”</>:<>“没有现实校准的超级智能，<br/>不过是一场算力无穷大的疯魔。”</>}</div>
        <div style={{marginTop:portrait?245:290,fontSize:portrait?63:66,letterSpacing:portrait?4:13,color:G}}>神也会自我欺骗</div>
        <div style={{height:2,marginTop:23,background:`linear-gradient(90deg,transparent,${A},${C},transparent)`,transform:`translateX(${Math.sin(f/75)*24}px)`}}/>
      </div>}
      {f>=6930&&<div style={{position:'absolute',left:portrait?65:250,top:portrait?456:275,width:portrait?830:1420,textAlign:'center',transform:drift}}>
        <div style={{fontFamily:'Menlo,monospace',fontSize:portrait?30:22,color:A,lineHeight:1.5}}>{portrait?<>[THERMODYNAMIC CEILING:<br/>k_B * T * ln(2)<br/>RADIATOR SATURATION]</>:'[THERMODYNAMIC CEILING: k_B * T * ln(2) // RADIATOR SATURATION]'}</div>
        <div style={{marginTop:28,fontSize:portrait?51:54,letterSpacing:4}}>下一次观测：兰道尔极限</div>
        <div style={{marginTop:23,fontSize:portrait?39:30,color:'#ffcc99'}}>[EP.05 算力的热力学终局]</div>
      </div>}
      {caption&&<div style={{position:'absolute',left:portrait?63:190,top:portrait?(caption.text.includes('\n')?1346:1380):936,width:portrait?840:1540,textAlign:'center',whiteSpace:'pre-line',fontSize:portrait?43:40,fontWeight:500,lineHeight:1.45,letterSpacing:portrait?1:2,textShadow:'0 2px 8px #000,0 0 18px #000',background:'radial-gradient(ellipse,#050811e0,transparent)',padding:'10px 0',boxSizing:'border-box'}}>{caption.text}</div>}
    </div>
    {!silent&&<Audio src={staticFile('audio/master.wav')}/>}
  </AbsoluteFill>;
};
