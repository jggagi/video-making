import React from 'react';

const clamp=(x:number)=>Math.max(0,Math.min(1,x));
const smooth=(x:number)=>{const p=clamp(x);return p*p*(3-2*p);};
const dust=Array.from({length:90},(_,i)=>({x:((i*173.719+31)%1080),y:((i*317.173+83)%1920),a:i*2.399963,r:.5+(i%5)*.3}));

/** Sparse material atmosphere; all coordinates are evaluated from absolute frame. */
export const Atmosphere:React.FC<{frame:number}>=({frame:f})=><svg width="1080" height="1920" viewBox="0 0 1080 1920" style={{position:'absolute',inset:0,pointerEvents:'none'}}>
 <defs><radialGradient id="edge-falloff"><stop offset=".25" stopColor="#08090b" stopOpacity="0"/><stop offset="1" stopColor="#08090b" stopOpacity=".78"/></radialGradient></defs>
 <rect width="1080" height="1920" fill="url(#edge-falloff)"/>
 <g opacity={f<4860?.12:.08}>{dust.map((p,i)=><circle key={i} cx={p.x+12*Math.sin(f/230+p.a)} cy={(p.y-f*(.035+(i%3)*.012)+3840)%1920} r={p.r} fill={i%4===0?'#e8c47d':'#d5cbb6'}/>)}</g>
</svg>;

/** Seasons leave a photographic time exposure around the unchanged central hands. */
export const Seasons:React.FC<{frame:number}>=({frame:f})=>{
 const a=smooth((f-4200)/100)*(1-smooth((f-4770)/80));
 if(a<=0)return null;
 const t=(f-4200)/60;
 return <svg width="1080" height="1920" style={{position:'absolute',inset:0,pointerEvents:'none',opacity:a*.6}}>
  <defs><linearGradient id="season-branch"><stop stopColor="#b3905c" stopOpacity="0"/><stop offset=".6" stopColor="#c5ad87" stopOpacity=".5"/><stop offset="1" stopColor="#c5ad87" stopOpacity="0"/></linearGradient></defs>
  {[0,1,2].map(k=><g key={k} opacity={.23-k*.05} transform={`translate(${k*12} ${-k*20}) rotate(${3*Math.sin(t*.25+k)} 540 800)`}>
   <path d="M60 1210Q165 860 82 520M1020 1220Q890 800 1030 500M93 900Q170 770 225 720M962 850Q897 740 839 680M90 640Q155 580 202 565" fill="none" stroke="url(#season-branch)" strokeWidth={3-k*.5}/>
  </g>)}
  {Array.from({length:85},(_,i)=>{
   const q=(t*(.12+(i%7)*.014)+i*.137)%1;
   const side=i%2===0?-1:1;
   const x=540+side*(260+150*Math.sin(i*2.399+q*2))+42*Math.sin(t*.75+i);
   const y=430+q*820;
   const season=t*.8+i;
   const weights=[0,1,2].map(phase=>Math.pow(Math.max(0,Math.cos((season-phase)*Math.PI*2/3)),4));
   const scale=.5+(i%6)*.16;
   return <g key={i} transform={`translate(${x} ${y}) rotate(${i*37+t*35}) scale(${scale})`} opacity={.15+.32*Math.sin(q*Math.PI)}>
    <path d="M0-7C12-16 14 2 0 10C-14 2-12-16 0-7" fill="#d6c1a5" opacity={weights[0]}/>
    <path d="M0-14Q18-4 0 15Q-12 0 0-14" fill="#b29149" opacity={weights[1]}/>
    <path d="M-6 0H6M0-6V6M-4-4L4 4M-4 4L4-4" stroke="#dfdeda" strokeWidth="1.4" opacity={weights[2]}/>
   </g>;
  })}
 </svg>;
};

export const InkBridge:React.FC<{frame:number}>=({frame:f})=>{
 const inA=smooth((f-520)/50)*(1-smooth((f-610)/60));
 const outA=smooth((f-3490)/40)*(1-smooth((f-3570)/70));
 const a=Math.max(inA,outA);
 if(a<=0)return null;
 return <div style={{position:'absolute',inset:0,background:'radial-gradient(ellipse at 46% 42%, rgba(14,12,10,.28), #08090b 68%)',opacity:a*.88,pointerEvents:'none'}}/>;
};
