import React from 'react';
import {C,Structure,SmallLabel,Packet,arc,clamp,ease,mix,ramp,seed} from './Visuals';
const nodes=Array.from({length:12},(_,i)=>{const a=i/12*Math.PI*2-.6;return {x:960+Math.cos(a)*(i%2?640:490),y:455+Math.sin(a)*(i%2?285:220),a}});
const roles=['构造','模拟','找反例','复核','整合','检查前提'];
function Glyph({i,x,y,t,color=C.blue}:{i:number;x:number;y:number;t:number;color?:string}){
 return <g transform={`translate(${x} ${y})`}><circle r="47" fill="#08101a" stroke={color} strokeWidth="1" opacity=".85"/>
 {i%6===0?<path d="M-24,17L0,-24L24,17ZM0,-24V17M-24,17L12,-4" fill="none" stroke={color} strokeWidth="1.5"/>:
 i%6===1?<><path d={arc(0,0,26,0,Math.PI*2,.5)} fill="none" stroke={color}/><path d={`M-26,0Q0,${Math.sin(t)*28} 26,0`} fill="none" stroke={color}/></>:
 i%6===2?<><path d="M-20,-20L20,20M-20,20L20,-20" stroke={color} strokeWidth="1.5"/><circle r="10" fill="none" stroke={color}/></>:
 i%6===3?<path d="M-26,1L-7,20L27,-18M-20,0L-7,12L20,-16" fill="none" stroke={color} strokeWidth="1.5"/>:
 i%6===4?<><path d="M-25,-18L0,0L25,-18M-25,18L0,0L25,18" fill="none" stroke={color} strokeWidth="1.5"/><circle r="7" fill={color}/></>:
 <><path d="M-25,20V-20H25V20H-25M-25,0H25" fill="none" stroke={color}/><circle cx="0" cy="0" r="8" fill="#08101a" stroke={color}/></>}
 </g>;
}
function Graph({t,spread=1,muted=false}:{t:number;spread?:number;muted?:boolean}){
 return <g>{nodes.map((n,i)=>{const next=nodes[(i+3)%nodes.length];return <g key={i}>
 <path d={`M${mix(960,n.x,spread)},${mix(450,n.y,spread)}Q960,420 ${mix(960,next.x,spread)},${mix(450,next.y,spread)}`} stroke={muted?'#37506a':'#6287a4'} strokeWidth=".7" opacity=".24" fill="none"/>
 {Array.from({length:17},(_,j)=>{const a=seed(i*31+j+1)*Math.PI*2;const rr=35+seed(i*51+j)*75;return <circle key={j} cx={mix(960,n.x+Math.cos(a)*rr,spread)} cy={mix(450,n.y+Math.sin(a)*rr*.6,spread)} r={j%5===0?2.6:1.4} fill={i%3===0?C.gold:C.blue} opacity={.2+.35*seed(j*7+i)}/>})}
 <circle cx={mix(960,n.x,spread)} cy={mix(450,n.y,spread)} r={4+Math.sin(t*.8+i)*1.2} fill={i%4===0?C.gold:C.blue}/>
 </g>})}</g>;
}
export const SIScene:React.FC<{t:number}>=({t})=>{
 if(t<60){const p=ramp(t,42,50);const q=ramp(t,50,59);return <g>
  <g opacity={1-q*.85}>
   {Array.from({length:8},(_,i)=><path key={i} d={`M160,${470+i*8}C520,${350+i*11} 1370,${570-i*7} 1760,${450+i*8}`} fill="none" stroke={i%2?C.gold:C.blue} strokeWidth={i===3?2:1} opacity={.12+i*.035}/>) }
   {Array.from({length:16},(_,i)=>{const a=(t*.09+i/16)%1;return <circle key={i} cx={160+a*1600} cy={470+Math.sin(a*Math.PI*2)*35} r="2.5" fill={i%3?C.blue:C.gold} opacity=".7"/>})}
  </g>
  <g transform={`translate(960 450) scale(${mix(.2,1,p)}) translate(-960 -450)`}>
  <Structure t={t} r={mix(150,280,q)} y={470-q*25}/>
  <ellipse cx="960" cy="470" rx={360+q*160} ry={85+q*40} stroke={C.blue} fill="none" opacity=".13"/>
  <path d="M830,440L960,365L1090,440L960,520Z" fill={C.blue} fillOpacity=".025" stroke={C.blue} strokeWidth=".8" opacity={q*.65}/>
  </g>
  <g opacity={ramp(t,51,53)}><SmallLabel x={755} y={760} size={26}>在给定扰动中保持结构</SmallLabel><SmallLabel x={817} y={803} size={18} color="#7994a9">假想任务 · 模拟可视化</SmallLabel></g>
 </g>}
 if(t<85){const split=ramp(t,60,67);const wide=ramp(t,75,82);const collapse=1-wide*.28;return <g>
  <Graph t={t} spread={split} muted/>
  <g opacity={1-wide*.4} transform={`translate(960 455) scale(${collapse}) translate(-960 -455)`}>
  {Array.from({length:6},(_,i)=>{const a=i/6*Math.PI*2-Math.PI/2;const x=960+Math.cos(a)*520*split;const y=455+Math.sin(a)*240*split;const color=i===2?C.blue:i===4?C.gold:C.white;return <g key={i} opacity={.25+.75*split}>
   <path d={`M960,455Q${960+Math.cos(a)*150},${455+Math.sin(a)*170} ${x},${y}`} stroke={C.blue} opacity=".3" fill="none" strokeDasharray="3 13"/>
   <Glyph i={i} x={x} y={y} t={t+i} color={color}/>
   <text x={x} y={y+85} textAnchor="middle" fontSize="23" letterSpacing="3" fill={color} opacity={ramp(t,68,70)}>{roles[i]}</text>
  </g>})}
  <Structure t={t} r={100-split*25} opacity={1-wide*.5}/>
  </g>
  {wide>0&&<g opacity={wide}>
   <ellipse cx="960" cy="455" rx="775" ry="325" fill="none" stroke={C.blue} strokeWidth=".7" opacity=".2"/>
   {Array.from({length:60},(_,i)=>{const a=i/60*Math.PI*2;return <path key={i} d={`M${960+Math.cos(a)*760},${455+Math.sin(a)*320}l${Math.cos(a)*14},${Math.sin(a)*7}`} stroke={C.blue} opacity=".24"/>})}
   <SmallLabel x={683} y={845} size={21} color="#8098ac">局部视图 · 10,000 节点（艺术示意）</SmallLabel>
  </g>}
 </g>}
 if(t<110){const share=ramp(t,85,93);const continueP=ramp(t,93,100);const doubtful=ramp(t,101,108);const px=mix(650,1260,share);const py=465-Math.sin(share*Math.PI)*120;return <g>
  <Graph t={t} muted/>
  <g opacity={1-doubtful*.65}>
  {[0,1,2].map(i=><g key={i} transform={`translate(${450+i*510} ${450+(i%2)*30})`}>
    <circle r="92" fill="#09131f" stroke={i===1?C.gold:C.blue} strokeWidth="1"/>
    <path d={arc(0,0,115,t*.08+i,t*.08+i+4.5,.85)} stroke={C.blue} fill="none" opacity=".24"/>
    <text textAnchor="middle" y="142" fill={C.white} fontSize="23" letterSpacing="4">{['构造','接续','独立复核'][i]}</text>
    <Structure x={0} y={0} t={t+i} r={57} color={i===1?C.gold:C.blue}/>
  </g>)}
  <path d="M540,450C700,350 780,350 870,470M1055,470C1220,360 1320,360 1380,450" fill="none" stroke={C.blue} strokeWidth="1.4" opacity=".6"/>
  <g transform={`translate(${px} ${py}) rotate(${Math.sin(t*.5)*3})`}>
   {[-18,0,18].map((y,i)=><path key={y} d={`M0,${-55+y}L90,${-y}L0,${55+y}L-90,${-y}Z`} fill="#0d1b29" fillOpacity=".8" stroke={[C.blue,C.white,C.gold][i]} strokeWidth="1.6"/>)}
   <circle r="6" fill={C.white} filter="url(#glow)"/>
  </g>
  <g opacity={continueP}><path d="M1060,425L1140,390L1178,418" fill="none" stroke={C.gold} strokeWidth="2"/><Packet x={1280} y={430} scale={.7} color={C.gold}/></g>
  </g>
  <g opacity={doubtful}>
    <g transform={`translate(960 440) scale(${mix(.8,1.25,doubtful)})`}>
     <path d="M-130,-75L120,-75L130,75L-130,75Z" fill="#0b1825" stroke={C.white} strokeWidth="1.3"/>
     <path d="M-70,10H-14L0,-13L16,10H70" fill="none" stroke={C.amber} strokeWidth="2"/>
     <path d="M0,-75V-28M0,32V75" stroke={C.amber} strokeDasharray="4 5" strokeWidth="1.5"/>
    </g>
    {[[-600,-140],[-400,230],[430,-180],[600,170]].map(([x,y],i)=><g key={i}>
     <path d={`M960,440Q${960+x*.4},${440+y*.85} ${960+x},${440+y}`} fill="none" stroke={C.amber} strokeWidth=".9" opacity=".45"/>
     <circle cx={960+x} cy={440+y} r="21" fill="#132434" stroke={C.white}/>
     <path d={`M${954+x},${440+y}l5,5l9,-10`} stroke={C.white} fill="none"/>
    </g>)}
    <SmallLabel x={816} y={743} size={24} color={C.amber}>同一个未经复核的前提</SmallLabel>
  </g>
 </g>}
 const forming=ramp(t,145,154);const stable=ramp(t,154,160);return <g>
  <Graph t={t} muted/>
  <g opacity={1-stable*.65}>
  {Array.from({length:6},(_,i)=>{const a=i/6*Math.PI*2-.8;const radius=mix(540,270,forming);const x=960+Math.cos(a)*radius;const y=450+Math.sin(a)*radius*.43;const col=[C.blue,C.gold,C.white,C.blue,C.gold,'#b5a8c8'][i];return <g key={i}>
   <path d={`M${x},${y}Q960,450 ${960+Math.cos(a+1)*180},${450+Math.sin(a+1)*70}`} stroke={col} fill="none" opacity=".35" strokeWidth="1.4"/>
   <Structure x={x} y={y} r={mix(60,80,forming)} t={t+i*3} color={col} angle={i*27} opacity={.85}/>
  </g>})}
  </g>
  <Structure t={t} r={mix(110,285,forming)} color={C.white} opacity={forming}/>
  <g opacity={forming}>
   <path d="M700,540Q590,680 340,700" stroke={C.red} opacity=".4" fill="none" strokeDasharray="3 7"/>
   <Packet x={315} y={710} color={C.red} scale={.7}/><SmallLabel x={355} y={718} color={C.red} size={19}>C-17 · 证据保留</SmallLabel>
   {Array.from({length:3},(_,i)=><g key={i}><circle cx={1370+i*95} cy={660-i*65} r="7" fill="none" stroke={C.amber}/><path d={`M${1230+i*20},550L${1370+i*95},${660-i*65}`} stroke={C.amber} opacity=".2" strokeDasharray="2 7"/></g>)}
  </g>
  <g opacity={ramp(t,153,155)}><SmallLabel x={764} y={766} size={29}>候选 v18 · 当前模拟通过</SmallLabel></g>
  <g opacity={ramp(t,158.5,160)}><SmallLabel x={825} y={817} size={24} color={C.amber}>待真实实验验证</SmallLabel></g>
 </g>
};
