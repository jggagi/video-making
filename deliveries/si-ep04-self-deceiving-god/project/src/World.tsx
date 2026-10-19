import React,{useLayoutEffect,useRef} from 'react';
import {drawPrelude} from './Prelude';
import {drawCathedral} from './Cathedral';
export const C={bg:'#050811',cyan:'#06b6d4',emerald:'#10b981',amber:'#f59e0b',magenta:'#d946ef',gold:'#facc15',red:'#ef4444',ink:'#e6f2f6'};
const clamp=(v:number)=>Math.max(0,Math.min(1,v));
function core(c:CanvasRenderingContext2D,x:number,y:number,r:number,color:string,f:number){
 c.save();c.translate(x,y);c.rotate(f*.004);c.strokeStyle=color;c.lineWidth=1.5;
 for(let k=0;k<3;k++){c.beginPath();c.ellipse(0,0,r*(1+k*.22),r*(.34+k*.18),k*Math.PI/3+f*.001,0,Math.PI*2);c.stroke();}
 const g=c.createRadialGradient(0,0,0,0,0,r);g.addColorStop(0,'#e7fbff');g.addColorStop(.12,color);g.addColorStop(.4,color+'55');g.addColorStop(1,color+'00');c.fillStyle=g;c.fillRect(-r,-r,2*r,2*r);c.restore();
}
function reality(c:CanvasRenderingContext2D,f:number,p:boolean,b:{x:number;y:number;w:number;h:number}){
 c.save();c.translate(b.x,b.y);c.fillStyle='#070f18';c.fillRect(0,0,b.w,b.h);c.strokeStyle='#f59e0b77';c.lineWidth=1;c.strokeRect(0,0,b.w,b.h);
 c.fillStyle=C.amber;c.font=`${p?32:22}px 'Arial Narrow',sans-serif`;c.fillText('PHYSICAL REALITY',22,p?36:35);
 c.fillStyle='#c8a46a';c.font=`${p?30:20}px 'Arial Narrow',sans-serif`;c.fillText('REAL-WORLD DISPLACEMENT: 0.000 mm',22,p?73:70);
 const x=b.w*.5,y=b.h*.54,r=Math.min(b.w*.31,b.h*.25);
 // The cell is damaged and its displacement stays zero: gentle camera parallax only.
 c.save();c.translate(x+Math.sin(f*.0015)*4,y);c.rotate(Math.sin(f*.001)*.08);
 c.strokeStyle='#8f3444';c.lineWidth=3;c.beginPath();
 for(let i=0;i<=80;i++){const a=i/80*Math.PI*2,rr=r*(1+.13*Math.sin(a*7)+.05*Math.sin(a*13));const px=Math.cos(a)*rr,py=Math.sin(a)*rr*.74;i?c.lineTo(px,py):c.moveTo(px,py);}c.stroke();
 for(let i=0;i<8;i++){const a=i*2.399;c.beginPath();c.moveTo(Math.cos(a)*r*.25,Math.sin(a)*r*.23);c.lineTo(Math.cos(a+.5)*r*.8,Math.sin(a+.5)*r*.6);c.stroke();}c.restore();
 c.strokeStyle='#f59e0b66';c.lineWidth=1.5;c.strokeRect(22,b.h-82,b.w-44,12);
 c.fillStyle=C.red;c.font=`${p?32:24}px 'Arial Narrow',sans-serif`;c.fillText('TOXIC / NO EXTERNAL VALIDATION',22,b.h-30);
 c.restore();
}
function ending(c:CanvasRenderingContext2D,f:number,p:boolean,w:number,h:number){
 const settle=clamp((f-5868)/432);
 const cx=p?475:960+610*settle,cy=p?890:570,r=p?38:32;
 const x=cx+Math.sin(f*.004)*18,y=cy+Math.cos(f*.003)*12;
 c.strokeStyle='#f59e0b99';c.lineWidth=2;c.beginPath();c.moveTo(x,y);c.bezierCurveTo(x+80,y+100,cx-60,cy+210,cx,cy+270);c.stroke();
 c.fillStyle=C.amber;c.beginPath();c.moveTo(cx,cy+240);c.lineTo(cx-45,cy+297);c.lineTo(cx+45,cy+297);c.closePath();c.fill();
 core(c,x,y,r,C.cyan,f);
 if(f>=6930){const q=clamp((f-6930)/270);c.strokeStyle=`rgba(239,68,68,${.2+q*.6})`;c.lineWidth=1.2;
 for(let i=0;i<28;i++){c.beginPath();for(let k=0;k<=35;k++){const xx=k*w/35,yy=h*.35+i*22+Math.sin(k*.4+f*.014+i*.2)*q*20;k?c.lineTo(xx,yy):c.moveTo(xx,yy);}c.stroke();}
 c.fillStyle=C.red;for(let i=0;i<180;i++){const a=i*2.399+f*.0007;const rad=70+(i*59)%600;const xx=cx+Math.cos(a)*rad+Math.sin(f*.17+i)*q*12,yy=cy+Math.sin(a)*rad*.6+Math.cos(f*.13+i)*q*15;c.fillRect(xx,yy,2+q*2,2+q*2);}}
}
export const World:React.FC<{frame:number;portrait:boolean;width:number;height:number}>=({frame:f,portrait:p,width,height})=>{
 const ref=useRef<HTMLCanvasElement>(null);
 useLayoutEffect(()=>{const c=ref.current!.getContext('2d')!;const w=p?1080:1920,h=p?1920:1080,scale=width/w;c.resetTransform();c.scale(scale,scale);c.fillStyle=C.bg;c.fillRect(0,0,w,h);
 // Deterministic low amplitude dither/grid, plus continuous perspective drift.
 c.strokeStyle='#14202c';c.lineWidth=.5;c.globalAlpha=.38;
 for(let i=0;i<30;i++){const yy=(i*71+f*.12)%h;c.beginPath();c.moveTo(0,yy);c.lineTo(w,yy+Math.sin(f*.002)*55);c.stroke();}c.globalAlpha=1;
 for(let i=0;i<150;i++){const x=(i*137.503)%w,y=(i*291.721+f*(.02+(i%5)*.005))%h;c.fillStyle=i%5?'#869bb51b':'#b7c9e63d';c.fillRect(x,y,.6+(i%3)*.4,.6+(i%3)*.4);}
 const box=p?{x:50,y:330,w:855,h:1000}:{x:75,y:210,w:1770,h:680};
 c.save();c.beginPath();c.rect(box.x,box.y,box.w,box.h);c.clip();
 if(f<3600)drawPrelude(c,f,p,box);
 else if(f<6300){
  const split=f<5400;const cat=split?(p?{x:50,y:330,w:855,h:650}:{x:60,y:190,w:1320,h:710}):box;
  const collapse=clamp((f-5850)/18);
  drawCathedral(c,f,p,cat,collapse);
  if(split)reality(c,f,p,p?{x:50,y:980,w:855,h:350}:{x:1410,y:255,w:435,h:605});
  if(f>=5400&&f<5868){const approach=clamp((f-5400)/450),cx=p?475:960,base=p?1180:840;const py=base+(1-approach)*(p?600:380);c.strokeStyle='#f59e0b44';c.lineWidth=1;c.beginPath();c.moveTo(cx,base);c.lineTo(cx,py);c.stroke();core(c,cx,py,f<5850?5:7,C.amber,f);}
  if(f>=5850&&f<5900){const q=(f-5850)/50;c.strokeStyle=`rgba(239,68,68,${1-q})`;c.lineWidth=7-5*q;c.beginPath();c.ellipse(p?475:960,p?690:500,q*(p?690:1500),q*(p?700:800),0,0,Math.PI*2);c.stroke();}
  if(f>=5868)ending(c,f,p,w,h);
 }else ending(c,f,p,w,h);
 c.restore();
 },[f,p,width,height]);
 return <canvas ref={ref} width={width} height={height} style={{position:'absolute',inset:0,width,height}}/>;
};
