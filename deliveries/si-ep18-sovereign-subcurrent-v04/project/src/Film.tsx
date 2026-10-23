import React, {useEffect, useState} from 'react';
import {AbsoluteFill, Audio, cancelRender, continueRender, delayRender, staticFile, useCurrentFrame} from 'remotion';
import {Scene} from './Scene';
import captions from '../captions.json';
const IVORY = '#F4E7D0', GOLD = '#E8BB70', CYAN = '#63AAB4';
const clamp=(v:number)=>Math.min(1,Math.max(0,v));
type Caption={startFrame:number;endFrame:number;text:string};
export const Film:React.FC<{silent?:boolean;cover?:false|'A'|'B'}>=({silent=false,cover=false})=>{
 const currentFrame=useCurrentFrame();
 const frame=cover==='A'?3820:cover==='B'?4920:currentFrame;
 const [fontHandle]=useState(()=>delayRender('EP18 v04 local fonts'));
 useEffect(()=>{let active=true;Promise.all([document.fonts.load('600 45px EPSerif'),document.fonts.load('400 28px EPMono')]).then(()=>document.fonts.ready).then(()=>{if(active)continueRender(fontHandle);}).catch(e=>cancelRender(e instanceof Error?e:new Error(String(e))));return()=>{active=false;continueRender(fontHandle);};},[fontHandle]);
 const cap=!cover&&(captions as Caption[]).find(c=>frame>=c.startFrame&&frame<c.endFrame);
 const lines=cap?cap.text.split('\n'):[];
 if(lines.length>2||lines.some(l=>Array.from(l).length>17))throw new Error('Caption exceeds mobile layout');
 const opening=1-clamp((frame-480)/120);
 const activeChoice=frame>=2700&&frame<4260;
 const buttonAlpha=clamp((frame-2700)/90)*(1-clamp((frame-4140)/120));
 const phase=frame<1500?'记住你':frame<2580?'成为你':frame<3960?'代替你':'谁是你';
 return <AbsoluteFill style={{background:'#101111',color:IVORY,fontFamily:'EPSerif,serif'}}>
  <style>{`@font-face{font-family:EPSerif;src:url('${staticFile('fonts/NotoSerifSC.ttf')}') format('truetype');font-weight:100 900;font-display:block;}@font-face{font-family:EPMono;src:url('${staticFile('fonts/RobotoMono.ttf')}') format('truetype');font-weight:100 700;font-display:block;}`}</style>
  <Scene frame={frame}/>
  <svg width="2160" height="3840" viewBox="0 0 1080 1920" fill={IVORY} style={{position:'absolute',inset:0,pointerEvents:'none'}}>
   {!cover&&<g opacity=".66"><text x="78" y="205" fontSize="27" letterSpacing="4" fill={GOLD}>一眼万年 · EP.18</text><text x="78" y="249" fontSize="24" fill={IVORY}>心印潜流 / 人与影</text><path d="M78 274 L130 274" stroke={GOLD} strokeWidth="2"/><text x="149" y="283" fontSize="27" fill={CYAN}>{phase}</text></g>}
   {!cover&&opening>0&&<g opacity={opening}><text x="76" y="365" fontSize="52" fontWeight="600">如果影子，比你先动了一下</text><text x="80" y="416" fontSize="27" fill={CYAN}>你还会相信，做决定的是自己吗？</text></g>}
   {!cover&&frame>=600&&frame<1350&&<g opacity={clamp((frame-600)/60)*(1-clamp((frame-1260)/90))}><text x="78" y="369" fontSize="34" fill={CYAN}>影子 · SI 的心印潜流</text></g>}
   {activeChoice&&frame<3900&&<g opacity={buttonAlpha}><text x="78" y="369" fontSize="34" fill={IVORY}>改变命运的决定</text></g>}
   {!cover&&frame>=3960&&frame<4300&&<g opacity={clamp((frame-3960)/20)*(1-clamp((frame-4200)/100))}><text x="78" y="369" fontSize="37" fill={GOLD}>身份验证通过。</text><text x="78" y="420" fontSize="29" fill={IVORY}>可你明明，还没有动。</text></g>}
   {cap&&<g fill={IVORY} fontSize="45" fontWeight="600" style={{paintOrder:'stroke',stroke:'#101111',strokeWidth:6,strokeLinejoin:'round'}}>{lines.map((l,i)=><text key={i} x="78" y={lines.length===1?1415:1380+i*58}>{l}</text>)}</g>}
   {!cover&&frame>=5160&&<g opacity={clamp((frame-5160)/30)}><text x="78" y="348" fontSize="29" fill={GOLD}>一眼万年 · 全三季终</text><text x="78" y="1480" fontSize="39" opacity=".7">未来 SI 思想实验 · 并非现实能力陈述</text></g>}
   {cover&&<g><rect x="55" y="190" width="860" height="313" fill="#101111" opacity=".88" rx="4"/><text x="80" y="254" fontSize="29" fill={CYAN}>心印潜流 · 一眼万年终章</text><text x="75" y="351" fontSize="76" fontWeight="700">如果你的影子</text><text x="75" y="449" fontSize="76" fontWeight="700" fill={GOLD}>比你先动了一下</text></g>}
  </svg>
  {!silent&&!cover&&<Audio src={staticFile('audio/master.wav')}/>}
 </AbsoluteFill>;
};
