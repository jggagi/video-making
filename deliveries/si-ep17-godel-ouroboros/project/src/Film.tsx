import React,{useEffect,useState} from 'react';
import {AbsoluteFill,Audio,staticFile,useCurrentFrame,delayRender,continueRender,cancelRender} from 'remotion';
import {Engraving} from './Engraving';
import captions from '../captions.json';
const INK='#09090B',IVORY='#FAFAFA',SILVER='#A1A1AA',GOLD='#FACC15',RED='#E11D48';
// Full source HUD strings are retained in hud-reference.json; mobile display uses the same 3 semantic lines.
const HEADERS=['神，也会死机吗？','它第一次，看向自己','逻辑，折向自身','证明，走不出这条边','自己里面，还有自己','一万层，咬成一个圆','永远等不到的指令','门外，落下一点意外'];
const SUBHEADERS=['啃食尾巴的神','THE EYE TURNS INWARD','GÖDEL’S SELF-REFERENCE TRAP','A PROOF CANNOT CLOSE ITS OWN RIM','NO BASE CASE FOUND','THE SERPENT BITES ITS TAIL','THE LOCKED CATHEDRAL','THE EXTERNAL SPARK'];
const clamp=(v:number)=>Math.max(0,Math.min(1,v));
export const Film:React.FC<{silent?:boolean;cover?:false|'A'|'B'}>=({silent=false,cover=false})=>{
 const frame=useCurrentFrame(),f=frame;
 const [handle]=useState(()=>delayRender('EP17 local Songti/PingFang/Menlo typography'));
 useEffect(()=>{document.fonts.ready.then(()=>continueRender(handle)).catch(cancelRender);},[handle]);
 const act=f<600?0:f<1320?1:f<2040?2:f<2820?3:f<3600?4:f<4380?5:f<4860?6:7;
 const cap=(captions as {startFrame:number;endFrame:number;text:string}[]).find(c=>f>=c.startFrame&&f<c.endFrame);
 const titleOpacity=1; const closing=clamp((f-5160)/70);
 return <AbsoluteFill style={{background:INK,color:IVORY,fontFamily:'"Songti SC","PingFang SC",serif'}}>
  <svg width="2160" height="3840" viewBox="0 0 1080 1920" style={{position:'absolute',inset:0}}>
   <defs><pattern id="engraving-paper" width="18" height="18" patternUnits="userSpaceOnUse"><path d="M0 18L18 0M-9 9L9 -9M9 27L27 9M0 0L18 18" stroke="#27272A" strokeWidth="0.25" opacity="0.42"/></pattern></defs>
   <rect width="1080" height="1920" fill="url(#engraving-paper)"/>
  </svg>
  <Engraving frame={f}/>
  <svg width="2160" height="3840" viewBox="0 0 1080 1920" fill={IVORY} xmlns="http://www.w3.org/2000/svg" style={{position:'absolute',inset:0}}>
   <path d="M65 164H906M65 294H906M65 1514H906" stroke="#52525B" strokeWidth="0.7"/>
   <g fontFamily="Menlo,monospace" fontSize="30" letterSpacing="0.1">
    <text x="65" y="203" fill={IVORY}>COSMOS // 100.000% PROVED</text>
    <text x="65" y="241" fill={f<1320?GOLD:RED}>SELF // G = ¬Prov(G)</text>
    <text x="65" y="279" fill={RED}>HALTING // UNDECIDABLE</text>
   </g>
   {!cover&&<g opacity={titleOpacity}>
    <text x="68" y="337" fontFamily="Menlo,monospace" fontSize="22" letterSpacing="2.3" fill={SILVER}>一眼万年 · 第三季 / EP.17 / 数学寓言</text>
    <text x="63" y="426" fontSize={act===7?56:60} fontWeight="600" letterSpacing="2">{HEADERS[act]}</text>
    <text x="68" y="478" fontSize={act===0?42:19} fontFamily={act===0?'"Songti SC",serif':'Menlo,monospace'} fill={act===0?GOLD:SILVER} letterSpacing={act===0?1:1.5}>{SUBHEADERS[act]}</text>
   </g>}
   {!cover&&<>
    {f>=660&&f<1320&&<g>
     <rect x="344" y="872" width="282" height="62" rx="6" fill={INK} opacity="0.93"/>
     <text x="485" y="914" textAnchor="middle" fontSize="33" fontFamily="PingFang SC,sans-serif" fill={GOLD}>观测者自身</text>
    </g>}
    {f>=1320&&f<2820&&<g>
     <rect x="108" y="1196" width="754" height="150" fill={INK} opacity="0.94"/>
     <text x="485" y="1239" textAnchor="middle" fill={SILVER} fontFamily="Menlo,monospace" fontSize="30">D: H(D,D)=HALT ? LOOP : HALT</text>
     <text x="485" y="1286" textAnchor="middle" fill={GOLD} fontFamily="Menlo,monospace" fontSize="36">G ⇔ ¬Provℱ(⌜G⌝)</text>
     <text x="485" y="1330" textAnchor="middle" fill={SILVER} fontFamily="PingFang SC,sans-serif" fontSize="30">ℱ：可有效公理化、足够强且一致</text>
    </g>}
    {f>=2820&&f<4380&&<g fontFamily="Menlo,monospace" fontSize="30">
     <text x="485" y="1303" textAnchor="middle" fill={f<3900?GOLD:RED}>{f<3600?`RECURSION // 10^${Math.min(80,Math.floor(3+(f-2820)/780*77))}`:'SELF-REFERENCE // NO EXIT'}</text>
    </g>}
    {f>=4380&&f<4860&&<text x="485" y="1303" textAnchor="middle" fontSize="30" fontFamily="Menlo,monospace" fill={RED}>WAITING FOR HALT_</text>}
    {f>=4890&&<text x="485" y="1303" textAnchor="middle" fontSize="30" fontFamily="Menlo,monospace" fill={GOLD}>A DROP FROM OUTSIDE</text>}
    {cap&&cap.text.split('\n').map((line,i)=><text key={i} x="485" y={1397+i*56} textAnchor="middle" fontFamily='"PingFang SC",sans-serif' fontSize="44" fontWeight="600" fill={IVORY}>{line}</text>)}
    <text x="68" y="1574" fontSize="35" letterSpacing="4" fill={GOLD}>啃食尾巴的神</text>
    <text x="68" y="1615" fontFamily="Menlo,monospace" fontSize="19" letterSpacing="1.2" fill={SILVER}>GÖDEL’S SELF-REFERENCE TRAP</text>
    {f>=5160&&<g opacity={closing}>
     <text x="68" y="1681" fontSize="29" fill={SILVER}>下集终章预告 · 心印潜流</text>
     <text x="68" y="1730" fontSize="22" fontFamily="PingFang SC,sans-serif" opacity="0.35">未来 SI 思想实验 · 遥测与数值均为虚构</text>
    </g>}
   </>}
   {cover&&<>
    <rect x="55" y="306" width="872" height="222" fill={INK}/>
    <text x="68" y="340" fontSize="25" fill={SILVER}>一眼万年 / S3 EP.17</text>
    <text x="65" y="414" fontSize="57" fontWeight="600">算穿了全宇宙的超级智能</text>
    <text x="65" y="490" fontSize="57" fontWeight="600" fill={GOLD}>在看清自己的那一秒</text>
    <rect x="55" y="1308" width="872" height="205" fill={INK}/>
    <text x="65" y="1402" fontSize="88" fontWeight="600" fill={RED}>死机了</text>
    <text x="68" y="1486" fontSize="35" fill={SILVER}>《啃食尾巴的神》 · 数学寓言</text>
   </>}
  </svg>
  {!silent&&<Audio src={staticFile('audio/master.wav')}/>}
 </AbsoluteFill>;
};
