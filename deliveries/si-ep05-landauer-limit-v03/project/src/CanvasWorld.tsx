import React, {useLayoutEffect, useRef} from 'react';
import {murrayChild, planck, potential, state} from './physics';
type Ctx=CanvasRenderingContext2D;
type Box={x:number;y:number;w:number;h:number};
const C='#06b6d4',A='#f59e0b',R='#ef4444',O='#f97316',G='#facc15',V='#050811';
const cl=(v:number)=>Math.max(0,Math.min(1,v));
const sm=(v:number)=>{const t=cl(v);return t*t*(3-2*t);};
const fract=(v:number)=>v-Math.floor(v);
const seed=(i:number)=>fract(Math.sin(i*127.1+311.7)*43758.5453);
const alphaColor=(color:string,alpha:number)=>`${color}${Math.round(cl(alpha)*255).toString(16).padStart(2,'0')}`;
const tri=(v:number)=>1-Math.abs(fract(v)*2-1);
function line(c:Ctx,x:number,y:number,xx:number,yy:number,color:string,width=2){c.beginPath();c.moveTo(x,y);c.lineTo(xx,yy);c.strokeStyle=color;c.lineWidth=width;c.stroke();}
function txt(c:Ctx,t:string,x:number,y:number,size=24,color='#d5e4ed',align:CanvasTextAlign='left'){c.fillStyle=color;c.font=`500 ${size}px "PingFang SC",Arial,sans-serif`;c.textAlign=align;c.fillText(t,x,y);}
function sphere(c:Ctx,x:number,y:number,r:number,color:string,alpha=1){if(r<.01)return;c.save();c.globalAlpha=alpha;const g=c.createRadialGradient(x-r*.25,y-r*.28,r*.04,x,y,r);g.addColorStop(0,'#f9fdff');g.addColorStop(.12,color);g.addColorStop(.44,color+'8c');g.addColorStop(1,color+'00');c.fillStyle=g;c.fillRect(x-r,y-r,r*2,r*2);c.restore();}
function arrow(c:Ctx,x:number,y:number,xx:number,yy:number,color:string,width=2){line(c,x,y,xx,yy,color,width);const a=Math.atan2(yy-y,xx-x);line(c,xx,yy,xx-Math.cos(a-.5)*9,yy-Math.sin(a-.5)*9,color,width);line(c,xx,yy,xx-Math.cos(a+.5)*9,yy-Math.sin(a+.5)*9,color,width);}
function ring(c:Ctx,x:number,y:number,rx:number,ry:number,color:string,width=2){c.beginPath();c.ellipse(x,y,Math.max(.01,rx),Math.max(.01,ry),0,0,Math.PI*2);c.strokeStyle=color;c.lineWidth=width;c.stroke();}
const bounds=(p:boolean):Box=>p?{x:65,y:445,w:835,h:830}:{x:76,y:245,w:1768,h:640};
function backdrop(c:Ctx,w:number,h:number,f:number){
 c.fillStyle=V;c.fillRect(0,0,w,h);const hot=f>=2600&&f<5400;
 const glow=c.createRadialGradient(w*.48,h*.52,10,w*.48,h*.52,w*.75);glow.addColorStop(0,hot?'#321018':f>=5400?'#07202d':'#0b1c29');glow.addColorStop(1,V);c.fillStyle=glow;c.fillRect(0,0,w,h);
 c.save();c.globalAlpha=.10;const off=f*.09%60;
 for(let x=-60+off;x<w+60;x+=60)line(c,x,0,x+w*.04*Math.sin(f/230),h,hot?'#4a2731':'#153649',1.6);
 for(let y=-60+f*.13%60;y<h+60;y+=60)line(c,0,y,w,y+12*Math.sin(f/160),hot?'#4a2731':'#153649',1.6);c.restore();
 c.fillStyle='#a4c7df';c.globalAlpha=.024;for(let i=0;i<700;i++)c.fillRect(seed(i*2)*w,seed(i*2+1)*h,1,1);c.globalAlpha=1;
}
function lattice(c:Ctx,b:Box,f:number,heat:number){
 const horizon=b.y+b.h*.38,center=b.x+b.w*.5;c.save();c.globalAlpha=.5;
 for(let j=0;j<14;j++){const d=fract(j/14+f/4400),k=d*d,y=horizon+k*b.h*.65,rowFade=sm(Math.min(d,1-d)/.08);c.globalAlpha=.5*rowFade;line(c,b.x-k*80,y,b.x+b.w+k*80,y,heat>.2?'#ef44444d':'#06b6d43a',1+2*k);
  for(let i=0;i<16;i++){const x=center+(i/15-.5)*(b.w*.2+k*b.w*.95)+Math.sin(f*.035+i*3+j)*heat*1.5,yy=y+Math.sin(f*.03+i*4+j*2)*heat*1.5;sphere(c,x,yy,2+3*k,heat>.2?R:C,.75*rowFade);}}
 c.globalAlpha=.5;
 for(let i=-8;i<=8;i++)line(c,center+i*24,horizon,center+i*b.w*.09,horizon+b.h*.7,heat>.2?'#ef44444d':'#06b6d433',1);c.restore();
}
function chamber(c:Ctx,b:Box,f:number,p:boolean){
 const q=sm((f-660)/240),x=b.x+b.w*.08,y=b.y+b.h*.16,w=b.w*.82,h=b.h*.48,d=p?30:62,wall=x+w*(1-.5*q),impactAge=f-900,impact=impactAge>0&&impactAge<60?2*sm(impactAge/8)*Math.exp(-impactAge/24)*sm((60-impactAge)/15):0;
 c.save();c.translate(impact,0);lattice(c,b,f,q);c.fillStyle='#05131be6';c.fillRect(x,y,wall-x,h);
 c.beginPath();c.moveTo(x,y+h);c.lineTo(x+d,y+h+d);c.lineTo(wall+d,y+h+d);c.lineTo(wall,y+h);c.fillStyle='#102834';c.fill();
 line(c,x,y,x,y+h,'#a9c1d2',5);line(c,x,y,wall,y,'#7d9dad',3);line(c,x,y+h,wall,y+h,'#a9c1d2',5);line(c,x+d,y-d,wall+d,y-d,'#294c5a',3);line(c,x,y,x+d,y-d,'#294c5a',3);
 // Sixty fixed-seed ensemble trajectories: rapid-compression analogy, not a Langevin solution.
 for(let i=0;i<60;i++){
  const phase=seed(i*4)+f*.0018*(.7+seed(i))*(1+q),px=x+12+tri(phase)*(wall-x-28),py=y+18+seed(i*3+2)*(h-36)+Math.sin(f*.035+i*2)*6,color=q>.1?R:C,dir=fract(phase)<.5?1:-1;
  line(c,px-dir*(10+q*11),py,px,py,color+'55',3);sphere(c,px,py,p?6:7,color);arrow(c,px,py,px+dir*(12+12*q),py,color,1.6);
  const dist=Math.min(tri(phase),1-tri(phase));if(q>.1&&dist<.16&&i%3===0){const u=(.16-dist)/.16;c.save();c.globalAlpha=Math.sin(Math.PI*sm(u))*.35;ring(c,tri(phase)<.5?x:wall,py,8+u*75,8+u*60,R,2);c.restore();}}
 c.fillStyle='#8d5d18';c.fillRect(wall,y-18,18,h+36);const metal=c.createLinearGradient(wall,y,wall+36,y);metal.addColorStop(0,'#fff7b4');metal.addColorStop(.3,G);metal.addColorStop(1,'#7c4611');c.fillStyle=metal;c.fillRect(wall-8,y-18,30,h+36);c.fillStyle='#b87a23';c.fillRect(wall+22,y+h*.44,x+w-wall+55,h*.12);
 for(let j=0;j<6;j++)line(c,wall-7,y+j*h/5,wall+21,y+j*h/5,'#fff9be',1);
 const ringAge=f-900;if(ringAge>=0&&ringAge<90){const attack=sm(ringAge/5),expand=sm(ringAge/75),fadeOut=1-sm((ringAge-60)/30);c.save();c.globalAlpha=.5*attack*fadeOut;ring(c,wall,y+h*.5,30+expand*b.w*.6,20+expand*h*.8,R,1+5.5*(1-expand));c.restore();}
 txt(c,q<.01?'STATE |0⟩       STATE |1⟩':'MEMORY OVERWRITE → |0⟩',x,y-38,p?30:26,q<.01?C:G);txt(c,`Ω: ${q>.98?'V':'2V → V'}    /    60 PARTICLES`,x,y+h+d+42,p?30:23);
 const qy=b.y+b.h*.87,qx=b.x+b.w*.1,qw=b.w*.8,alpha=1-.8*Math.sin(Math.PI*q),tilt=.65*Math.sin(Math.PI*q);
 c.beginPath();for(let i=0;i<=200;i++){const xx=-1.45+i/200*2.9,yy=potential(xx,alpha,tilt),sx=qx+i/200*qw,sy=qy-yy*(p?30:25);if(i===0)c.moveTo(sx,sy);else c.lineTo(sx,sy);}c.strokeStyle=G;c.lineWidth=3;c.stroke();
 txt(c,p?'急压缩示意 · v×2':'RAPID COMPRESSION ANALOGY · v×2',b.x+b.w*.5,b.y+b.h*.78,p?30:22,A,'center');txt(c,'U/U₀ = (x/x₀)⁴ − 2α(x/x₀)² + cx',b.x+b.w*.5,b.y+b.h*.98,p?30:24,G,'center');c.restore();
}
function act1(c:Ctx,b:Box,f:number,p:boolean){
 if(f<1260)chamber(c,b,f,p);else{lattice(c,{...b,y:b.y-50,h:b.h*1.2},f,1);const k=(f-1260)/540;c.save();c.translate(b.x+b.w/2,b.y+b.h*.7);c.rotate(-.05+k*.13);c.scale(1+k*.2,.3+.08*Math.sin(f/110));for(let i=0;i<180;i++){const x=(seed(i)-.5)*b.w*1.8,y=(seed(i+300)-.5)*b.h*1.8;sphere(c,x+Math.sin(f/60+i)*12,y,4+seed(i+2)*12,i%4?R:O,.6);}c.restore();}
}
function brain(c:Ctx,x:number,y:number,r:number,f:number){
 sphere(c,x,y,r*1.6,A,.5);c.fillStyle='#f59e0b19';c.beginPath();c.arc(x,y,r,0,Math.PI*2);c.fill();for(let k=0;k<12;k++){c.beginPath();for(let j=0;j<80;j++){const a=j/79*Math.PI*2,rr=r*(.48+k*.035+.03*Math.sin(a*5+k+f/90)),xx=x+rr*Math.cos(a),yy=y+rr*.75*Math.sin(a)+Math.sin(f/50+k)*3;if(j===0)c.moveTo(xx,yy);else c.lineTo(xx,yy);}c.strokeStyle=k%3?'#f59e0b87':'#fdf0c9';c.lineWidth=1.7;c.stroke();}ring(c,x,y,r*1.12,r*.91,'#f59e0b44',1);
}
function act2(c:Ctx,b:Box,f:number,p:boolean){
 const t=f-1800,rise=sm((t-720)/560),wallY=b.y+b.h*.16,wallX=b.x+b.w*.06,wallW=b.w*.88,bx=b.x+b.w*(.27-.08*rise),by=b.y+b.h*(.55+.20*rise),br=(p?125:145)*(1-.38*rise);
 lattice(c,b,f,rise);brain(c,bx,by,br,f);txt(c,'20 W',bx,by+br+52,p?49:45,A,'center');txt(c,p?'人脑 · 温热的灯':'HUMAN BRAIN // A WARM BEDSIDE LAMP',bx,by+br+94,p?30:22,'#e6bd89','center');
 if(t<780){for(let i=0;i<25;i++){const phase=fract(t/180+seed(i)),x=bx+(seed(i+3)-.5)*br*1.8,y=by-br-phase*b.h*.4;line(c,x,y+9,x,y,A+Math.round((1-phase)*75).toString(16).padStart(2,'0'),1.5);}txt(c,p?'把思考，推向极限。':'EVER FASTER. EVER CLOSER.',b.x+b.w*.6,b.y+b.h*.32,p?36:38,C,'center');}
 if(t>=620){const q=sm((t-620)/180);c.save();c.globalAlpha=q;const glow=c.createLinearGradient(0,wallY-24,0,wallY+45);glow.addColorStop(0,'#ef444400');glow.addColorStop(.45,R);glow.addColorStop(.5,'#fff5e4');glow.addColorStop(1,'#ef444400');c.fillStyle=glow;c.fillRect(wallX,wallY-24,wallW,70);line(c,wallX,wallY,wallX+wallW,wallY,'#fff5e4',4);
  txt(c,p?'兰道尔之墙 · 300 K':'THE LANDAUER WALL @ 300 K',b.x+b.w*.5,wallY-64,p?32:31,R,'center');txt(c,'3.48 × 10²⁰ ERASED BITS / J',b.x+b.w*.5,wallY-26,p?30:25,'#fff3bc','center');
  // 256 compute paths × 8 trail segments. None crosses the ceiling.
  const basePhase=(t-620)/350+.75*cl((t-620)/1180)**3;for(let i=0;i<256;i++){const cycle=fract(basePhase*(.7+seed(i)*.6)+seed(i*3)),beamFade=sm(Math.min(cycle,1-cycle)/.1),collision=cycle>.9?Math.sin(Math.PI*sm((cycle-.9)/.1)):0,xx=b.x+b.w*(.18+seed(i+10)*.72),baseY=b.y+b.h*.91,yy=baseY-(baseY-wallY)*cycle,offset=(1-cycle)**2*b.w*.17;c.save();c.globalAlpha=q*beamFade;for(let k=0;k<8;k++)line(c,xx-offset-k*.65,yy+k*3,xx-offset-(k+1)*.65,yy+(k+1)*3,alphaColor(C,(190-k*20)/255),1.1);c.restore();if(collision>0)sphere(c,xx,wallY,7+12*collision,O,.65*collision*q);}
  const flood=cl((t-900)/900),rainIn=sm((t-900)/75);for(let i=0;i<250;i++){const phase=fract((t-900)/(100+seed(i)*150)+seed(i+800)),birthDeath=sm(Math.min(phase,1-phase)/.08),alpha=rainIn*birthDeath,x=b.x+b.w*(.10+seed(i)*.82)+Math.sin(phase*4+i)*30,y=wallY+phase**1.6*b.h*.79;if(t>900){line(c,x,y,x-4,y-10-20*phase,alphaColor(i%4?O:R,alpha),1+seed(i+1)*3);if(i%12===0)sphere(c,x,y,7,O,.4*alpha*q);}}
  const lava=c.createLinearGradient(0,b.y+b.h*.85,0,b.y+b.h);lava.addColorStop(0,'#ef444400');lava.addColorStop(1,'#ef4444a0');c.fillStyle=lava;c.fillRect(b.x,b.y+b.h*(1-.22*flood),b.w,b.h*.22*flood);c.restore();}
}
function planet(c:Ctx,b:Box,f:number,p:boolean){
 const progress=sm((f-3600)/1799),cx=b.x+b.w*.5,top=b.y+b.h*.82,crust=(x:number)=>top+((x-cx)/(b.w*.5))**2*b.h*.11,shell=(x:number)=>crust(x)-b.h*(.54-.04*progress);c.save();
 const fire=c.createLinearGradient(0,b.y,0,b.y+b.h);fire.addColorStop(0,'#ff471100');fire.addColorStop(.7,`rgba(239,68,68,${.09+.35*progress})`);fire.addColorStop(1,'#6b1114');c.fillStyle=fire;c.fillRect(b.x,b.y,b.w,b.h);
 c.beginPath();c.moveTo(b.x,b.y+b.h);for(let i=0;i<=100;i++){const x=b.x+i*b.w/100;c.lineTo(x,crust(x));}c.lineTo(b.x+b.w,b.y+b.h);c.closePath();c.fillStyle='#0d1823';c.fill();
 for(let k=0;k<4;k++){c.beginPath();for(let i=0;i<=120;i++){const x=b.x+i*b.w/120,y=shell(x)+k*5+Math.sin(x*.018+f*.045)*progress*3;if(i===0)c.moveTo(x,y);else c.lineTo(x,y);}c.strokeStyle=k===0?'#ffb187':`rgba(239,68,68,${.25-k*.04})`;c.lineWidth=k===0?4:8;c.stroke();}
 for(let i=0;i<19;i++){const x=b.x+(i+.5)*b.w/19,y=crust(x),hh=12+seed(i)*40;c.fillStyle='#182d3b';c.fillRect(x-7,y-hh,14,hh);line(c,x-5,y-hh,x+5,y-hh,progress>.4?O:C,3);sphere(c,x,y-hh,9+progress*12,O,.7);}
 // 17/20 authored rays return (85% schematic count, not atmospheric reflectivity).
 for(let i=0;i<80;i++){const x0=b.x+b.w*(.08+seed(i)*.84),y0=crust(x0)-25,x1=x0+(seed(i+1)-.5)*b.w*.2,y1=shell(x1)+10,phase=fract(f/(130+seed(i)*60)+seed(i+6)),rayFade=sm(Math.min(phase,1-phase)/.08),returns=i%20<17;let x:number,y:number,dx:number,dy:number;
  if(phase<.48){const k=phase/.48;x=x0+(x1-x0)*k;y=y0+(y1-y0)*k;dx=x1-x0;dy=y1-y0;}else if(returns){const k=(phase-.48)/.52;x=x1+(x0+b.w*.09-x1)*k;y=y1+(y0-y1)*k;dx=x0+b.w*.09-x1;dy=y0-y1;}else{const k=(phase-.48)/.52;x=x1+(x1-x0)*k;y=y1-k*b.h*.38;dx=x1-x0;dy=-b.h*.38;}const len=Math.hypot(dx,dy);arrow(c,x-dx/len*19,y-dy/len*19,x,y,alphaColor(returns?R:O,rayFade),2.2);const returnPulse=phase>.45&&phase<.53?sm((phase-.45)/.02)*(1-sm((phase-.51)/.02)):0;if(returns&&returnPulse>0)sphere(c,x1,y1,14,R,.45*returnPulse);}
 for(let k=0;k<12;k++){c.beginPath();const yy=b.y+b.h*(.3+k*.047);for(let i=0;i<=80;i++){const x=b.x+b.w*i/80,y=yy+Math.sin(i*.16+f*.055+k)*progress*6;if(i===0)c.moveTo(x,y);else c.lineTo(x,y);}c.strokeStyle=`rgba(249,115,22,${progress*.11})`;c.lineWidth=2;c.stroke();}
 txt(c,p?'热，被送回脚下。':'THE SKY SENDS THE HEAT BACK.',cx,b.y+b.h*.12,p?38:42,'#ffc3a2','center');txt(c,p?'大气吸收 / 再辐射 · 示意':'ATMOSPHERE / ABSORPTION + RE-EMISSION · SCHEMATIC',cx,b.y+b.h*.24,p?30:21,'#f4a1a2','center');c.restore();
}
function spectrum(c:Ctx,b:Box,f:number,p:boolean){
 const T=state(f).temperature;txt(c,'Bλ(λ,T)',b.x+b.w*.5,b.y+24,p?30:29,G,'center');const x=b.x+b.w*.08,y=b.y+b.h*.2,w=b.w*.84,h=b.h*.53,max=30;
 for(let k=0;k<3;k++){const temp=k===2?T:300+k*18;c.beginPath();for(let i=0;i<=180;i++){const lambda=2+i/180*48,xx=x+i/180*w,yy=y+h-planck(lambda,temp)/max*h;if(i===0)c.moveTo(xx,yy);else c.lineTo(xx,yy);}c.strokeStyle=k===2?R:'#f59e0b35';c.lineWidth=k===2?4:1.5;c.stroke();}
 line(c,x,y+h,x+w,y+h,'#a46c6e',1);txt(c,'2       λ / μm       50',x+w/2,y+h+(p?18:36),p?30:22,'#ba8b8d','center');txt(c,'P = 4πR² εσT⁴',b.x+b.w*.5,b.y+b.h*(p?.99:.88),p?34:29,G,'center');if(!p)txt(c,'HOTTER SURFACE / MORE RADIATION',b.x+b.w*.5,b.y+b.h*.98,20,'#d4a4a7','center');
}
function act3(c:Ctx,b:Box,f:number,p:boolean){
 const progress=sm((f-3600)/1799);c.save();c.translate(Math.sin(f*.025)*progress*.8,Math.sin(f*.019)*progress*.6);
 if(p){planet(c,{x:b.x,y:b.y,w:b.w,h:b.h*.59},f,p);spectrum(c,{x:b.x+40,y:b.y+b.h*.64,w:b.w-80,h:b.h*.31},f,p);}else{planet(c,{x:b.x,y:b.y,w:b.w*.64,h:b.h},f,p);spectrum(c,{x:b.x+b.w*.67,y:b.y+25,w:b.w*.32,h:b.h*.8},f,p);}c.restore();
 if(progress>.70){c.save();c.globalAlpha=cl((progress-.7)/.3);txt(c,p?'348 K · 生物圈热危机场景':'348 K SCENARIO / BIOSPHERE IN DANGER',b.x+b.w*.5,b.y+b.h*.99,p?30:24,R,'center');c.restore();}
}
function stars(c:Ctx,b:Box,f:number){for(let i=0;i<200;i++){const z=.15+seed(i+200)*.85,x=b.x+fract(seed(i)+f*.000018*z)*b.w,y=b.y+fract(seed(i+1)+Math.sin(f/1300)*.015*z)*b.h;c.fillStyle=i%13===0?C:'#dcecf4';c.globalAlpha=.15+seed(i+2)*.6;c.fillRect(x,y,i%13===0?2.5:1.3,i%13===0?2.5:1.3);}c.globalAlpha=1;}
function radiator(c:Ctx,b:Box,f:number,p:boolean){
 const t=f-5400,deploy=sm((t-25)/800),orbit=Math.sin(t/500)*.2,cx=b.x+b.w*.49,closing=sm((f-6240)/90),cy=b.y+b.h*(.55+.23*closing),sx=b.w*(p?.43:.41),sy=b.h*.46*(1-.48*closing);
 const project=(x:number,y:number,z=0)=>({x:cx+(x*Math.cos(orbit)+z*Math.sin(orbit))*sx,y:cy+y*sy+(z*Math.cos(orbit)-x*Math.sin(orbit))*sy*.18});const point=project(0,0);sphere(c,point.x,point.y,p?23:30,C,.9);
 const branch=(x:number,y:number,angle:number,len:number,r:number,level:number,side:number,branchId:number)=>{if(level>7)return;const extent=sm((deploy*9-level+1)/2),xx=x+Math.cos(angle)*len*extent,yy=y+Math.sin(angle)*len*extent,a=project(x,y,Math.sin(level)*.06),d=project(xx,yy,Math.sin(level+1)*.06);
  if(level>1){c.beginPath();c.moveTo(a.x,a.y);c.lineTo(d.x,d.y);c.lineTo(d.x+side*len*sx*.17,d.y+len*sy*.27);c.lineTo(a.x+side*len*sx*.11,a.y+len*sy*.15);c.closePath();c.fillStyle=level%2?'#06b6d40b':'#facc150a';c.fill();}line(c,a.x,a.y,d.x,d.y,level<3?G:C,Math.max(.7,r));
  if(level<7){const rr=murrayChild(r),root=branchId&0x100,path=branchId&0xff;branch(xx,yy,angle+.43*deploy,len*.70,rr,level+1,side,root|(path<<1));branch(xx,yy,angle-.43*deploy,len*.70,rr,level+1,side,root|(path<<1)|1);}else if(extent>.9&&seed(branchId+4096)>.88){const k=fract(t/140+seed(branchId+8192)),cycleFade=sm(Math.min(k,1-k)/.1),activation=sm((extent-.9)/.1),alpha=cycleFade*activation;c.save();c.globalAlpha=alpha;line(c,d.x,d.y,d.x+side*18*k,d.y-30*k,'#06b6d44d',1);c.restore();}};
 branch(0,0,-.15,.34,7,1,1,1);branch(0,0,Math.PI+.15,.34,7,1,-1,257);ring(c,cx,cy,p?26:34,p?10:14,'#06b6d4a0',2);
 if(f<6300){txt(c,p?'向寒冷，展开。':'UNFOLD INTO THE COLD.',b.x+b.w*.5,b.y+b.h*.12,p?45:49,'#c9f5fb','center');txt(c,p?'SUN–EARTH L2 / SHIELDED CONCEPT':'SUN–EARTH L2 / SHIELDED CONCEPT',b.x+b.w*.5,b.y+b.h*.21,p?30:22,'#8bb5c1','center');txt(c,'rₚ³ = r₁³ + r₂³',b.x+b.w*.5,b.y+b.h*.88,p?33:28,G,'center');txt(c,p?'7级冷却通道 · 40 K 散热翼':'7-LEVEL COOLANT CHANNELS / 40 K RADIATOR',b.x+b.w*.5,b.y+b.h*.95,p?30:23,C,'center');}
}
function cortex(c:Ctx,b:Box,f:number,p:boolean){
 const t=f-6930,cx=b.x+b.w*.5,cy=b.y+b.h*.56,wave=(xx:number,lead:number)=>{const pos=(xx-b.x)/b.w;let value=0;for(let k=0;k<4;k++){const center=fract((t+lead)/240+k*.26),d=pos-center;value+=Math.exp(-d*d/.0012)*Math.sin(d*160)*.19;}return cy+value*b.h;};
 for(const [color,lead,off] of [[C,30,-24],[A,0,26]] as const){c.beginPath();for(let i=0;i<=250;i++){const x=b.x+i*b.w/250,y=wave(x,lead)+off;if(i===0)c.moveTo(x,y);else c.lineTo(x,y);}c.strokeStyle=color;c.lineWidth=2.5;c.stroke();}
 if(f>=6990&&f<7040)sphere(c,cx,cy-24,20,C,1-cl((f-6990)/50));if(f>=7020&&f<7080)sphere(c,cx,cy+26,24,A,1-cl((f-7020)/60));const lock=sm((f-7040)/70),r=(p?130:160)*(1.6-.6*lock),angle=f*.012;
 for(let k=0;k<6;k++){const a=angle+k*Math.PI/3,aa=angle+(k+1)*Math.PI/3,x=cx+Math.cos(a)*r,y=cy+Math.sin(a)*r*.7,xx=cx+Math.cos(aa)*r,yy=cy+Math.sin(aa)*r*.7;line(c,x,y,xx,yy,G,2.5);line(c,x,y,cx,cy-r*.38,G,1.3);line(c,x,y,cx,cy+r*.38,'#facc1560',1.3);}sphere(c,cx,cy,40,A,.5);
 txt(c,p?'预测先行 500 ms':'PREDICTION LEADS BY 500 ms',cx,b.y+b.h*.91,p?31:25,C,'center');txt(c,p?'概念镜头 · 非自由意志实验证明':'SYMBOLIC SEQUENCE / NOT A LIBET EXPERIMENT',cx,b.y+b.h*.98,p?30:20,'#92a6b6','center');
}
function act4(c:Ctx,b:Box,f:number,p:boolean){stars(c,b,f);if(f<6930){const escape=cl((f-5400)/210);if(escape<1)sphere(c,b.x+b.w*.5,b.y+b.h*.66,(p?150:210)*(1-escape)**2,R,.8);radiator(c,b,f,p);}else cortex(c,b,f,p);}
export const CanvasWorld:React.FC<{frame:number;portrait:boolean;width:number;height:number}>=({frame:f,portrait:p,width,height})=>{
 const ref=useRef<HTMLCanvasElement>(null);useLayoutEffect(()=>{const canvas=ref.current;if(!canvas)return;const c=canvas.getContext('2d',{alpha:false,willReadFrequently:true});if(!c)return;const w=p?1080:1920,h=p?1920:1080;c.setTransform(width/w,0,0,height/h,0,0);backdrop(c,w,h,f);const b=bounds(p);c.save();c.beginPath();c.rect(b.x-10,b.y-15,b.w+20,b.h+35);c.clip();if(f<1800)act1(c,b,f,p);else if(f<3600)act2(c,b,f,p);else if(f<5400)act3(c,b,f,p);else act4(c,b,f,p);c.restore();},[f,p,width,height]);return <canvas ref={ref} width={width} height={height} style={{position:'absolute',width:'100%',height:'100%'}}/>;
};
