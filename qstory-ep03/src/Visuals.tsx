import React from 'react';
export const C={white:'#e3edf2', blue:'#87bde2', faint:'#233e58', gold:'#d8c496', amber:'#eabc77', red:'#ff625c'};
export const clamp=(x:number,a=0,b=1)=>Math.min(b,Math.max(a,x));
export const ease=(x:number)=>{x=clamp(x);return x*x*(3-2*x)};
export const mix=(a:number,b:number,x:number)=>a+(b-a)*x;
export const ramp=(t:number,a:number,b:number)=>ease((t-a)/(b-a));
export const seed=(n:number)=>{const v=Math.sin(n*127.1+311.7)*43758.5453;return v-Math.floor(v)};
export function arc(x:number,y:number,r:number,a:number,b:number,sy=1){return Array.from({length:72},(_,i)=>{const k=a+(b-a)*i/71;return `${i?'L':'M'}${(x+Math.cos(k)*r).toFixed(1)},${(y+Math.sin(k)*r*sy).toFixed(1)}`}).join(' ')}
export const Defs:React.FC=()=> <defs>
  <radialGradient id="space"><stop stopColor="#10253a"/><stop offset=".64" stopColor="#080f1b"/><stop offset="1" stopColor="#03070d"/></radialGradient>
  <radialGradient id="haze"><stop stopColor="#487ca4" stopOpacity=".12"/><stop offset="1" stopColor="#122c4e" stopOpacity="0"/></radialGradient>
  <radialGradient id="warmhaze"><stop stopColor="#aa753a" stopOpacity=".15"/><stop offset="1" stopColor="#aa753a" stopOpacity="0"/></radialGradient>
  <radialGradient id="vignette"><stop offset=".48" stopColor="#000" stopOpacity="0"/><stop offset="1" stopColor="#000" stopOpacity=".63"/></radialGradient>
  <linearGradient id="shaft" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#b9dcf6" stopOpacity="0"/><stop offset=".5" stopColor="#b9dcf6" stopOpacity=".36"/><stop offset="1" stopColor="#b9dcf6" stopOpacity="0"/></linearGradient>
  <filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3"/><feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <filter id="softGlow" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="6"/><feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>;
// Exactly 10,000 deterministic marks, batched into four SVG paths.
const starLayers=Array.from({length:4},(_,l)=>Array.from({length:2500},(_,i)=>{const k=i+l*2500;const a=seed(k*5+1)*Math.PI*2;const r=Math.pow(seed(k*5+2),.63);const spiral=a+r*2.8;const x=960+Math.cos(spiral)*r*1020;const y=450+Math.sin(spiral)*r*385+Math.sin(r*8)*45;return `M${x.toFixed(1)},${y.toFixed(1)}h.1`}).join(''));
export const Space:React.FC<{t:number;warm?:boolean;dense?:number}>=({t,warm=false,dense=1})=><g>
 <rect width="1920" height="1080" fill="url(#space)"/>
 <ellipse cx={1000+Math.sin(t*.035)*100} cy="430" rx="1000" ry="590" fill={warm?'url(#warmhaze)':'url(#haze)'}/>
 <g opacity={dense} transform={`translate(${Math.sin(t*.015)*18} ${Math.cos(t*.023)*10}) rotate(${Math.sin(t*.012)*2} 960 450)`}>
 {starLayers.map((d,i)=><path key={i} d={d} fill="none" stroke={warm?['#8c714f','#b39a78','#d5c6af','#f1e7d8'][i]:['#30465d','#4d6d85','#7697ae','#d8e4eb'][i]} strokeWidth={[.6,.8,1,1.5][i]} strokeLinecap="round" opacity={[.21,.24,.26,.33][i]}/>)}</g>
</g>;
export const Structure:React.FC<{x?:number;y?:number;r?:number;t:number;color?:string;broken?:number;opacity?:number;angle?:number}>=({x=960,y=470,r=230,t,color=C.white,broken=0,opacity=1,angle=0})=>{
 const rot=t*.045;const count=30;const p=(a:number,outer:boolean)=>{const radius=r*(outer?1:.71);return [Math.cos(a+rot)*radius,Math.sin(a+rot)*radius*.48+(outer?-7:7)]};
 const rings=[false,true].map(out=>Array.from({length:count},(_,i)=>{const a=i/count*Math.PI*2;const [px,py]=p(a,out);return `${i?'L':'M'}${px.toFixed(1)},${py.toFixed(1)}`}));
 return <g transform={`translate(${x} ${y}) rotate(${angle})`} opacity={opacity}>
 <ellipse rx={r*1.2} ry={r*.7} fill={color} opacity=".025"/>
 {[0,1].map(z=><path key={z} d={rings[z].slice(broken?3:0,broken?28:count).join(' ')+(broken?'':'Z')} stroke={color} strokeWidth={z?2:1.3} fill="none" opacity={z?.9:.42}/>) }
 {Array.from({length:count},(_,i)=>{if(broken&&i<4)return null;const a=i/count*Math.PI*2;const [ax,ay]=p(a,true);const [bx,by]=p(a,false);const [cx,cy]=p(a+Math.PI*2/count,false);const shift=broken&&i<8?broken*22:0;return <g key={i} transform={`translate(${shift} ${shift*.3})`}><path d={`M${ax},${ay}L${bx},${by}L${cx},${cy}`} fill="none" stroke={color} strokeWidth=".85" opacity={.25+.35*(Math.sin(a+rot)+1)/2}/><circle cx={ax} cy={ay} r={i%5===0?3.7:2} fill={color} opacity={i%5===0?1:.5}/></g>})}
 <path d={arc(0,0,r*1.12,.25,2.55,.37)} stroke={color} strokeWidth="1" fill="none" opacity=".2"/>
 </g>;
};
export const SmallLabel:React.FC<{x:number;y:number;children:React.ReactNode;color?:string;size?:number}>=({x,y,children,color=C.white,size=24})=><text x={x} y={y} fill={color} fontSize={size} letterSpacing="2" fontWeight="300">{children}</text>;
export const Packet:React.FC<{x:number;y:number;color?:string;scale?:number}>=({x,y,color=C.blue,scale=1})=><g transform={`translate(${x} ${y}) scale(${scale})`}><path d="M0,-26L24,0L0,26L-24,0Z M0,-15L14,0L0,15L-14,0Z" fill="#09111c" stroke={color} strokeWidth="1.7"/><circle r="3.5" fill={color}/></g>;
