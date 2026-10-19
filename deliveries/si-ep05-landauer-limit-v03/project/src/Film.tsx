import React, {useLayoutEffect} from 'react';
import {AbsoluteFill, Audio, staticFile, useCurrentFrame, useVideoConfig, useDelayRender, cancelRender} from 'remotion';
import {CanvasWorld} from './CanvasWorld';
import {landauer, state} from './physics';
import timing from '../audio-timing.json';

const cyan='#06b6d4', amber='#f59e0b', red='#ef4444', gold='#facc15';
const clamp=(x:number)=>Math.max(0,Math.min(1,x));
const fade=(f:number,a:number,b:number)=>clamp((f-a)/40)*clamp((b-f)/40);
const sci=(n:number,d=2)=>{if(n===0)return '0';const e=Math.floor(Math.log10(Math.abs(n)));return `${(n/10**e).toFixed(d)} × 10^${e}`;};
const chapters=[['01','每一次遗忘，都留下余温','THE MICROSCOPIC HAMMER'],['02','一盏灯，与烧红的天花板','THE THERMODYNAMIC WALL'],['03','天空，正在合上','THE PLANETARY PRESSURE COOKER'],['04','寒冷中的静默','THE SILENT UNIVERSE']];

export const Film:React.FC<{portrait?:boolean;silent?:boolean}>=({portrait=false,silent=false})=>{
  const f=useCurrentFrame(), {width}=useVideoConfig();
  const {delayRender,continueRender}=useDelayRender();
  // A frame is ready only after local fonts and two complete browser paint ticks.
  // This gate covers the DOM captions/HUD as well as the synchronous Canvas draw.
  useLayoutEffect(()=>{
    const handle=delayRender(`EP05 fully painted frame ${f}`);
    let released=false,first=0,second=0;
    const release=()=>{if(!released){released=true;continueRender(handle);}};
    document.fonts.ready.then(()=>{
      if(released)return;
      first=requestAnimationFrame(()=>{second=requestAnimationFrame(release);});
    }).catch((error:unknown)=>{cancelRender(error instanceof Error?error:new Error(String(error)));});
    return ()=>{cancelAnimationFrame(first);cancelAnimationFrame(second);release();};
  },[f,delayRender,continueRender]);
  const w=portrait?1080:1920,h=portrait?1920:1080,scale=width/w;
  const act=Math.min(3,Math.floor(f/1800)),s=state(f),T=s.temperature;
  const color=act===3?cyan:T>=330?red:amber;
  const caption=((timing as {captions?:{startFrame:number;endFrame:number;text:string}[]}).captions??[]).find(c=>f>=c.startFrame&&f<c.endFrame);
  const temp=`${T<10?T.toFixed(3):T.toFixed(1)} K`;
  const qualifier=act===3?'[DEEP SPACE CMB]':T>=330?'[SEVERE HEAT SCENARIO]':'';
  const drift=`perspective(1400px) rotateX(${Math.sin(f/173)*1.1}deg) rotateY(${Math.cos(f/227)*1.8}deg) translateY(${Math.sin(f/143)*7}px)`;
  return <AbsoluteFill style={{background:'#050811',fontFamily:'"PingFang SC", "Hiragino Sans GB", sans-serif',color:'#f3f8ff'}}>
    <CanvasWorld frame={f} portrait={portrait} width={width} height={portrait?3840:2160}/>
    <div style={{position:'absolute',width:w,height:h,transform:`scale(${scale})`,transformOrigin:'top left'}}>
      {portrait?<>
        <div style={{position:'absolute',left:62,top:173,width:840,height:116,fontFamily:'Arial, sans-serif',fontSize:30,lineHeight:'28.5px',color,background:'#050811ed'}}>
          <div>AMBIENT TEMP (T): {temp}</div>
          <div>HEAT PER ERASED BIT: {sci(landauer(T))} J</div>
          <div style={{color:gold}}>ACTIVE SI POWER: {sci(s.wasteHeat)} W</div>
          <div style={{color:act===3?cyan:gold,fontSize:30}}>{act===3?'NET FLUX: εσ(T_rad⁴−T_CMB⁴)':'EARTH RADIATIVE CEILING: 4πR²εσT⁴'}</div>
        </div>
        <div style={{position:'absolute',left:65,top:316,width:830,display:'flex',justifyContent:'space-between',fontFamily:'Menlo,monospace',fontSize:30,color:'#90a6bc'}}><span>余问 QSTORY / EP.05</span><span style={{color}}>{chapters[act][0]} / 04</span></div>
        <div style={{position:'absolute',left:65,top:365,fontSize:44,letterSpacing:3,color}}>{chapters[act][1]}</div>
        <div style={{position:'absolute',left:65,top:428,fontSize:30,color:'#9eb4c9',fontFamily:'Menlo,monospace'}}>{act===3?'CMB背景 2.725 K / 散热翼 40 K':act===1?'擦除下限 · 每次操作擦除1 bit时':act===2?'热危机场景示意 · 非气候预测':'未知比特 → 已知状态'}</div>
      </>:<>
        <div style={{position:'absolute',left:72,right:72,top:43,display:'flex',justifyContent:'space-between',fontFamily:'Menlo,monospace',fontSize:18,letterSpacing:2,color:'#8ea4b9'}}><span>余问 QSTORY / SUPERINTELLIGENCE</span><span>EP.05 / THE LANDAUER LIMIT</span></div>
        <div style={{position:'absolute',left:72,right:72,top:94,borderTop:'1px solid #294055',paddingTop:14,display:'grid',gridTemplateColumns:'1.4fr 1fr',gap:22,fontFamily:'Menlo,monospace',fontSize:20,lineHeight:'32px'}}>
          <div style={{color}}><div>AMBIENT TEMP (T): {temp} {qualifier}</div><div>HEAT PER ERASED BIT: k_B·T·ln(2) = {sci(landauer(T))} J</div></div>
          <div style={{color:act===3?cyan:gold,textAlign:'right'}}><div>ACTIVE SI POWER: {f<1800?'20 W (HUMAN)':`${sci(s.wasteHeat)} W`}</div><div>{act===3?'NET RADIATOR FLUX: εσ(T_rad⁴ − T_CMB⁴)':'EARTH RADIATIVE CEILING: 4πR² εσT_surface⁴'}</div></div>
        </div>
        <div style={{position:'absolute',left:74,top:211,fontSize:26,letterSpacing:3,color}}>{chapters[act][0]} / {chapters[act][1]} <span style={{fontFamily:'Menlo,monospace',fontSize:17,color:'#8fa6b8',marginLeft:18}}>{chapters[act][2]}</span></div>
        <div style={{position:'absolute',right:74,top:210,fontFamily:'Menlo,monospace',fontSize:16,color:'#a1b0bf'}}>SCHEMATIC PHYSICS / NOT A CLIMATE FORECAST</div>
      </>}
      {f<120&&<div style={{position:'absolute',left:portrait?65:74,top:portrait?465:268,fontSize:portrait?39:25,color:'#d7e9f8',opacity:clamp(f/30)}}>每一次遗忘，都有余温。</div>}
      {f>=1260&&f<1800&&<div style={{position:'absolute',left:portrait?65:170,top:portrait?650:410,width:portrait?830:1580,textAlign:'center',opacity:fade(f,1260,1800),transform:drift,textShadow:'0 0 30px #050811,0 0 50px #050811'}}>
        <div style={{fontSize:portrait?88:112,fontWeight:600,letterSpacing:portrait?10:20,lineHeight:1.5}}>兰 道 尔 极 限</div>
        <div style={{fontFamily:'Menlo,monospace',fontSize:portrait?34:28,letterSpacing:portrait?2:7,marginTop:26,color:'#9bdded'}}>{portrait?<>THE LANDAUER<br/>LIMIT</>:'T H E   L A N D A U E R   L I M I T'}</div>
        <div style={{fontFamily:'Menlo,monospace',fontSize:portrait?30:23,marginTop:34,lineHeight:1.6,color:gold}}>ΔQ ≥ k_B · T · ln(2)</div><div style={{fontSize:portrait?30:22,marginTop:20,color:'#d4ac9d'}}>Every Erased Bit Bleeds Heat</div>
      </div>}
      {f>=6300&&f<6930&&<>
        <div style={{position:'absolute',left:portrait?68:220,top:portrait?505:260,width:portrait?826:1480,textAlign:'center',opacity:fade(f,6300,6930),transform:drift,textShadow:'0 3px 15px #050811,0 0 45px #050811'}}>
          <div style={{fontSize:portrait?30:22,color:amber,marginBottom:25}}>一种未经证实的费米悖论假说</div>
          <div style={{fontSize:portrait?43:43,lineHeight:1.65,fontWeight:500,letterSpacing:1}}>{portrait?<>“这或许就是宇宙<br/>如此寂静的原因：<br/>最高等的智慧从不喧哗，<br/>它们正躲在最寒冷的<br/>黑暗里静默思考。”</>:<>“这或许就是宇宙如此寂静的原因：<br/>最高等的智慧从不喧哗，它们正躲在最寒冷的黑暗里静默思考。”</>}</div>
        </div>
        <div style={{position:'absolute',left:portrait?65:250,top:portrait?1215:820,width:portrait?830:1420,textAlign:'center',fontSize:portrait?46:42,letterSpacing:10,color:cyan,transform:drift}}>兰 道 尔 极 限</div>
      </>}
      {f>=6930&&<div style={{position:'absolute',left:portrait?65:250,top:portrait?490:250,width:portrait?830:1420,textAlign:'center',transform:drift,textShadow:'0 3px 15px #050811'}}>
        <div style={{fontFamily:'Menlo,monospace',fontSize:portrait?30:23,color:gold,lineHeight:1.6}}>{portrait?<>SOVEREIGN SOUL CRYSTAL<br/>PRIVATE KEY LOCKED</>:'[SOVEREIGN SOUL CRYSTAL // PRIVATE KEY LOCKED]'}</div>
        <div style={{marginTop:28,fontSize:portrait?49:57,letterSpacing:4}}>下一次观测：主权心印</div>
        <div style={{marginTop:23,fontSize:portrait?39:32,color:'#ffcc99'}}>[EP.06 当算法比你更懂你]</div>
      </div>}
      {caption&&<div style={{position:'absolute',left:portrait?63:190,top:portrait?1346:936,width:portrait?840:1540,height:portrait?138:130,textAlign:'center',whiteSpace:'pre-line',fontSize:portrait?43:40,fontWeight:500,lineHeight:1.45,letterSpacing:portrait?1:2,textShadow:'0 2px 8px #000,0 0 18px #000',background:'radial-gradient(ellipse,#050811eb,transparent)',padding:'6px 0',boxSizing:'border-box'}}>{caption.text}</div>}
    </div>
    {!silent&&<Audio src={staticFile('audio/master.wav')}/>}
  </AbsoluteFill>;
};
