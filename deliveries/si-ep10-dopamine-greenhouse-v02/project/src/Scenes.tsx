import React from 'react';
import {EarlyActOne,EarlyActTwo} from './EarlyActs';
import {DeepField,NeuralIsolation} from './LateActs';
import {RawReality} from './Reality';
const C={night:'#050811',amber:'#f59e0b',cyan:'#06b6d4',magenta:'#d946ef',gold:'#facc15',red:'#ef4444',pale:'#fff4df',stone:'#e6e5e1'};
const CX=486,CY=850;
const clamp=(v:number,lo=0,hi=1)=>Math.max(lo,Math.min(hi,v));
const smooth=(v:number)=>{const t=clamp(v);return t*t*(3-2*t);};
const fmt=(v:number)=>Number(v.toFixed(2));
const polar=(r:number,a:number)=>({x:Math.cos(a)*r,y:Math.sin(a)*r});
function spiralPath(turns: number, radius: number, phase: number, frame: number): string {
  const points: string[] = [];
  const steps = 1080;
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const a = phase + t * turns * Math.PI * 2 + frame * 0.0024;
    const r = 12 + t * radius;
    points.push(`${fmt(CX + Math.cos(a) * r)},${fmt(CY + Math.sin(a) * r * 0.92)}`);
  }
  return `M${points.join(' L')}`;
}

function Pleasure({frame}: {frame: number}): React.ReactElement {
  const p = clamp((frame - 4380) / 480);
  const intensity = smooth(p);
  const turn = 6.5 + 4.2 * intensity;
  const radius = 366 + 42 * intensity;
  return (
    <>
      <ellipse cx={CX} cy={CY} rx={fmt(285 + intensity * 115)} ry={fmt(330 + intensity * 110)} fill="url(#ep10PleasureAura)" opacity={0.24 + 0.23 * intensity} />
      <g fill="none" strokeLinecap="round">
        {Array.from({length: 5}, (_, i) => (
          <path
            key={i}
            d={spiralPath(turn + (i % 2) * 1.2, radius - i * 25, i * Math.PI * 0.4, frame)}
            stroke={i % 2 === 0 ? 'url(#ep10SpiralGold)' : 'url(#ep10SpiralPink)'}
            strokeWidth={fmt(3 + intensity * 7 - i * 0.3)}
            opacity={0.58 + 0.26 * intensity}
          />
        ))}
        {Array.from({length: 18}, (_, i) => {
          const a = (Math.PI * 2 * i) / 18 + frame * 0.002;
          const inner = 156 + 22 * Math.sin(frame * 0.015 + i);
          const outer = 250 + 125 * intensity + 15 * Math.cos(frame * 0.012 + i * 2);
          const q1 = polar(inner, a);
          const q2 = polar(outer, a + 0.15 * Math.sin(frame * 0.01 + i));
          return <path key={i} d={`M${fmt(CX + q1.x)} ${fmt(CY + q1.y)} Q${CX + fmt(q2.x * 0.72)} ${CY + fmt(q2.y * 0.72)} ${fmt(CX + q2.x)} ${fmt(CY + q2.y)}`} stroke={i % 3 === 0 ? C.gold : C.magenta} strokeWidth={fmt(1.8 + intensity * 1.6)} opacity={0.48 + intensity * 0.24} />;
        })}
      </g>
      <circle cx={CX} cy={CY} r={fmt(86 + intensity * 102)} fill="url(#ep10PleasureCore)" opacity="0.82" />
      <circle cx={CX} cy={CY} r={fmt(22 + 18 * intensity)} fill="#fff3cb" opacity={0.75 + 0.16 * Math.sin(frame * 0.015)} />
    </>
  );
}



function Definitions(){return <defs>
<clipPath id="ep10ForegroundClip"><rect x="64" y="470" width="844" height="726"/></clipPath>
<pattern id="ep10Dither" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="2" cy="3" r=".62" fill="#b8c5d2" fillOpacity=".17"/><circle cx="13" cy="7" r=".48" fill="#8995a6" fillOpacity=".14"/><circle cx="21" cy="17" r=".57" fill="#d4c9b0" fillOpacity=".12"/><circle cx="7" cy="20" r=".45" fill="#6d8296" fillOpacity=".16"/></pattern>
<linearGradient id="ep10Background" x1="0" y1="0" x2="0.8" y2="1">
        <stop offset="0" stopColor="#08101b" />
        <stop offset="0.5" stopColor="#050811" />
        <stop offset="1" stopColor="#080912" />
      </linearGradient><radialGradient id="ep10Spark">
        <stop offset="0" stopColor="#fff9dd" />
        <stop offset="0.16" stopColor="#fff0a1" />
        <stop offset="0.34" stopColor="#facc15" stopOpacity="0.9" />
        <stop offset="0.64" stopColor="#f59e0b" stopOpacity="0.52" />
        <stop offset="1" stopColor="#d946ef" stopOpacity="0" />
      </radialGradient><linearGradient id="ep10SpiralGold" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#facc15" stopOpacity="0.28" />
        <stop offset="0.38" stopColor="#fff1a8" />
        <stop offset="0.62" stopColor="#f59e0b" />
        <stop offset="1" stopColor="#d946ef" stopOpacity="0.56" />
      </linearGradient><linearGradient id="ep10SpiralPink" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#d946ef" stopOpacity="0.24" />
        <stop offset="0.42" stopColor="#ffb2f5" />
        <stop offset="0.72" stopColor="#d946ef" />
        <stop offset="1" stopColor="#facc15" stopOpacity="0.6" />
      </linearGradient><radialGradient id="ep10PleasureAura">
        <stop offset="0" stopColor="#d946ef" stopOpacity="0.72" />
        <stop offset="0.48" stopColor="#facc15" stopOpacity="0.4" />
        <stop offset="1" stopColor="#d946ef" stopOpacity="0" />
      </radialGradient><radialGradient id="ep10PleasureCore">
        <stop offset="0" stopColor="#fff9de" />
        <stop offset="0.17" stopColor="#facc15" />
        <stop offset="0.58" stopColor="#d946ef" stopOpacity="0.84" />
        <stop offset="1" stopColor="#facc15" stopOpacity="0" />
      </radialGradient>
</defs>}
function NormalFrame({frame}:{frame:number}){return <>
<rect width="1080" height="1920" fill={frame>=4891?'#000':'url(#ep10Background)'}/>
{frame<4860&&<rect width="1080" height="1920" fill="url(#ep10Dither)" opacity=".42"/>}
<g clipPath="url(#ep10ForegroundClip)">
{frame<1320?<EarlyActOne frame={frame}/>:frame<2820?<EarlyActTwo frame={frame}/>:frame<3600?<DeepField frame={frame}/>:frame<4380?<NeuralIsolation frame={frame}/>:frame<4860?<Pleasure frame={frame}/>:frame>=4891?<RawReality frame={frame}/>:null}
</g></>}
export const Scenes:React.FC<{frame:number}>=({frame})=>{
const black=frame>=4861&&frame<4891;
const collapse=frame>=4854&&frame<=4860;
const sy=1-.995*smooth((frame-4854)/4);
const sx=1-.96*smooth((frame-4858)/3);
return <svg width="1080" height="1920" viewBox="0 0 1080 1920" xmlns="http://www.w3.org/2000/svg">
<Definitions/>
{black?<rect width="1080" height="1920" fill="#000"/>:collapse?<>
<rect width="1080" height="1920" fill="#000"/>
<g transform={`translate(${CX} ${CY}) scale(${sx} ${sy}) translate(${-CX} ${-CY})`}><NormalFrame frame={Math.min(frame,4859)}/></g>
<rect x={CX-390*sx} y={CY-1.5} width={780*sx} height="3" fill="#fff"/>
</>:<NormalFrame frame={frame}/>}
</svg>};
export default Scenes;
