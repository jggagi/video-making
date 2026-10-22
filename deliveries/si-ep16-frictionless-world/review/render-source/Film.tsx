import React,{useEffect,useState} from 'react';
import {AbsoluteFill,Audio,staticFile,useCurrentFrame,useVideoConfig,delayRender,continueRender,cancelRender} from 'remotion';
import {Geometry} from './Geometry';
import timing from '../audio-timing.json';
const BG='#F8FAFC',INK='#39444F',SILVER='#8A95A1';
const titles=[['这里，没人再哭。','完美得像一座停尸房'],['一切，恰到好处。','没有多余，也没有意外'],['连一滴眼泪','都落不下来'],['你想换一种活法。','申请驳回'],['每一次“试试”','都被温柔地纠正'],['最优，为什么锁死？','因为改变也被禁止'],['系统越来越安静。','安静到听不见心跳'],['这一次，','他选择了“是”'],['第一圈涟漪。','终于，有事没有被安排']];
export const Film:React.FC<{silent?:boolean;cover?:false|'A'|'B'}>=({silent=false,cover=false})=>{
 const frame=useCurrentFrame(),{width}=useVideoConfig(),f=cover?1800:frame,t=f/60;
 const [handle]=useState(()=>delayRender('EP16 local typography'));
 useEffect(()=>{document.fonts.ready.then(()=>continueRender(handle)).catch(cancelRender);},[handle]);
 const index=t<12?0:t<25?1:t<38?2:t<51?3:t<65?4:t<79?5:t<93?6:t<106?7:8;
 const cap=(timing.captions as {startFrame:number;endFrame:number;text:string}[]).find(c=>f>=c.startFrame&&f<c.endFrame);
 return <AbsoluteFill style={{background:BG,color:INK,fontFamily:'"PingFang SC",sans-serif'}}>
  <svg width={width} height={width/1080*1920} viewBox="0 0 1080 1920" xmlns="http://www.w3.org/2000/svg" style={{position:'absolute',inset:0}}>
   <rect width="1080" height="1920" fill={BG}/>
   <path d="M70 157H922M70 1518H922" stroke="#CCD3DA" strokeWidth="1.1"/>
   <text x="72" y="128" fontSize="25" fill={SILVER} letterSpacing="3">感受 SI / EP.16 / 社会寓言</text>
   {!cover&&<>
    <text x="70" y="273" fontSize={index===5?68:77} fontWeight="500" letterSpacing="1">{titles[index][0]}</text>
    <text x="73" y="352" fontSize="40" fill={SILVER}>{titles[index][1]}</text>
    <text x="74" y="422" fontFamily="Menlo,monospace" fontSize="20" fill={SILVER} letterSpacing="2">{['A PERFECT WORLD / NO SURPRISES','EVERYTHING IN ITS RIGHT PLACE','COMFORT ARRIVES BEFORE THE TEAR','A REQUEST TO LIVE OTHERWISE','ALL DEVIATIONS CORRECTED','EFFICIENCY ≠ A BAN ON CHANGE','NO OSCILLATION / SLOW RETURN','CONTINUE ANYWAY?','THE FIRST RIPPLE'][index]}</text>
   </>}
   <Geometry frame={f}/>
   {!cover&&<>
    <text x="74" y="1323" fontSize="25" fill={SILVER} fontFamily="Menlo,monospace">{t<65?'ZERO FRICTION / ZERO SURPRISES':t<79?'PARETO EFFICIENCY LOCK*':t<93?'OVER-DAMPED CONTROL*':t<106?'AN UNPLANNED CHOICE':'LIFE NEEDS ROOM TO TRY'}</text>
    {cap&&cap.text.split('\n').map((line,i)=><text key={i} x="495" y={1405+i*58} textAnchor="middle" fontSize="47" fontWeight="500" fill={INK}>{line}</text>)}
    <text x="74" y="1573" fontSize="24" fill={SILVER}>零摩擦人间</text>
    <text x="74" y="1610" fontSize="18" fill={SILVER} fontFamily="Menlo,monospace">THE DEAD CALM OF PARETO OPTIMALITY</text>
    <text x="74" y="1690" fontSize="23" fill={SILVER}>科幻思想实验 · 非现实社会模型或临床测量</text>
    {t>=65&&t<93&&<text x="74" y="1735" fontSize="21" fill={SILVER}>*锁死与停止是寓言设定，非理论必然结论</text>}
    {t<12&&<text x="74" y="1735" fontSize="21" fill={SILVER}>*σ²为寓言中的社会波动，非实测</text>}
    {t<12&&<text x="850" y="1573" textAnchor="end" fontSize="22" fill={SILVER}>σ² → 0*</text>}
   </>}
   {cover&&<>
    <text x="70" y="270" fontSize="76" fontWeight="600">当世界完美到</text>
    <text x="70" y="365" fontSize="82" fontWeight="600">没人再哭</text>
    <text x="70" y="1327" fontSize="65" fontWeight="500">为什么像停尸房？</text>
    <text x="74" y="1431" fontSize="31" fill={SILVER}>《零摩擦人间》</text>
    <text x="74" y="1610" fontSize="23" fill={SILVER}>社会寓言 · 科幻思想实验</text>
   </>}
  </svg>
  {!silent&&<Audio src={staticFile('audio/master.wav')}/>}
 </AbsoluteFill>;
};
