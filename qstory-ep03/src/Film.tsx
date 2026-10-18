import React from 'react';
import {AbsoluteFill,Audio,staticFile,useCurrentFrame,useVideoConfig} from 'remotion';
import timeline from '../source/EP03_timeline.json';
import audio from './audio-timing.json';
import {HumanScene} from './HumanScenes';
import {Counterexample} from './Counterexample';
import {SIScene} from './SIScenes';
import {C,Defs,Space,ramp} from './Visuals';
const headings=['一句话的距离','群岛与文明','另一种连接','同源，不同路径','可接续的工作','反例的重量','接成下一步','回到一个声音'];
export const Film:React.FC<{silent?:boolean}>=({silent=false})=>{
 const frame=useCurrentFrame();const t=frame/30;const {width,height}=useVideoConfig();
 const scene=timeline.scenes.find(s=>frame>=s.fromFrame&&frame<s.fromFrame+s.durationInFrames)!;
 const ix=timeline.scenes.indexOf(scene);const local=t-scene.startSec;
 const opacity=ramp(local,0,.38)*(t>179?1:1-ramp(t,scene.endSec-.28,scene.endSec));
 const caption=audio.cues.find(c=>frame>=c.fromFrame&&frame<c.toFrameExclusive);
 return <AbsoluteFill style={{backgroundColor:'#040912',fontFamily:'"PingFang SC", "Hiragino Sans GB", sans-serif'}}>
  {!silent&&<Audio src={staticFile('audio-bailian/soundtrack.wav')}/>}
  <svg width={width} height={height} viewBox="0 0 1920 1080" style={{display:'block'}}>
   <Defs/>
   <Space t={t} warm={t<42||t>=165} dense={t<12?.2:t<42?.32:t>=165?.45:1}/>
   <g opacity={opacity}>{t<42||t>=165?<HumanScene t={t}/>:t>=110&&t<145?<Counterexample t={t}/>:<SIScene t={t}/>}</g>
   <rect width="1920" height="1080" fill="url(#vignette)" pointerEvents="none"/>
   <g opacity=".68"><text x="96" y="77" fill={C.white} fontSize="24" letterSpacing="4">余问 QStory</text><text x="1824" y="77" textAnchor="end" fill={C.white} fontSize="20" letterSpacing="4">感受 SI / EP.03</text></g>
   {t<176&&<g opacity={.62*ramp(local,.4,1.3)}><line x1="98" y1="122" x2="125" y2="122" stroke={t<42||t>=165?C.gold:C.blue}/><text x="144" y="129" fontSize="20" fill={C.white} letterSpacing="5">{headings[ix]}</text></g>}
   {t>=2&&t<6&&<text x="960" y="855" textAnchor="middle" fill="#b4ad9f" fontSize="23" letterSpacing="3">科幻思想实验：时间与规模为艺术设定</text>}
   {caption&&<g>
    <rect x="200" y="926" width="1520" height="104" rx="40" fill="#03070d" opacity=".64"/>
    <text x="960" y="994" textAnchor="middle" fill="#f0f2f4" fontSize="39" fontWeight="400" letterSpacing="1.8">{caption.text}</text>
   </g>}
   {t>160&&t<165&&<text x="1820" y="1045" textAnchor="end" fill="#788c9c" fontSize="17">虚构模拟 · 不代表当前 AI 能力</text>}
  </svg>
 </AbsoluteFill>
};
