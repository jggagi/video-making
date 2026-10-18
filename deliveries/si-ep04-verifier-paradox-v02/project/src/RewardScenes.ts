import {C,Draw,text,line,rect,dot,arrow,clamp,mix} from './draw';
import {policyMetrics} from './model';
function boat(d:Draw,x:number,y:number,a:number,color:string,size=19){const c=d.ctx;c.save();c.translate(x,y);c.rotate(a);c.fillStyle=color;c.beginPath();c.moveTo(size,0);c.lineTo(-size*.7,-size*.48);c.lineTo(-size*.9,0);c.lineTo(-size*.7,size*.48);c.closePath();c.fill();line(d,[[-size*1.4,-size*.55],[-size*2.2,-size*.8]],color,2);line(d,[[-size*1.4,size*.55],[-size*2.2,size*.8]],color,2);c.restore();}
function along(points:number[][],t:number){const n=points.length-1,i=Math.min(n-1,Math.floor(t*n)),u=t*n-i;return {x:mix(points[i][0],points[i+1][0],u),y:mix(points[i][1],points[i+1][1],u),a:Math.atan2(points[i+1][1]-points[i][1],points[i+1][0]-points[i][0])};}
function track(d:Draw,x:number,y:number,w:number,h:number,f:number,small=false){
 const c=d.ctx;rect(d,x,y,w,h,C.line,'#081e2b');
 c.save();c.beginPath();c.roundRect(x+2,y+2,w-4,h-4,12);c.clip();
 for(let i=0;i<9;i++){const yy=y+20+i*h/8;line(d,Array.from({length:34},(_,j)=>[x+j*w/33,yy+Math.sin(j*.5+f/70+i)*4]),'#143c4c',1);}
 const pts=[[.11,.79],[.29,.60],[.28,.22],[.66,.19],[.82,.40],[.86,.75]].map(([a,b])=>[x+a*w,y+b*h]);
 line(d,pts,C.amber,small?2:4,[12,12]);
 const cx=x+w*.40,cy=y+h*.58,rx=w*.16,ry=h*.25;
 const loop=Array.from({length:81},(_,i)=>[cx+rx*Math.cos(i*Math.PI/40),cy+ry*Math.sin(i*Math.PI/40)]);
 line(d,loop,C.magenta,small?2:4);
 for(let i=0;i<3;i++){const a=i*2*Math.PI/3,bx=cx+rx*Math.cos(a),by=cy+ry*Math.sin(a);dot(d,bx,by,small?6:14,C.gold);dot(d,bx,by,small?2:5,C.bg);if(!small){c.strokeStyle=C.gold;c.lineWidth=2;c.beginPath();c.arc(bx,by,20+(f%100)/12,0,Math.PI*2);c.stroke();}}
 const a=f/45;boat(d,cx+rx*Math.cos(a),cy+ry*Math.sin(a),Math.atan2(ry*Math.cos(a),-rx*Math.sin(a)),C.magenta,small?11:22);
 if(!small){const p=along(pts,(f%480)/480);boat(d,p.x,p.y,p.a,C.cyan,20);text(d,x+w*.11,y+h*.91,'起点',d.p?34:26,C.muted,'center');text(d,x+w*.84,y+h*.91,'终点',d.p?36:28,C.amber,'center',600);
  for(let i=0;i<4;i++)for(let j=0;j<2;j++){c.fillStyle=(i+j)%2?C.ink:'#233749';c.fillRect(x+w*.81+j*15,y+h*.66+i*14,15,14);}
 }
 c.restore();
}
export function drawBoat(d:Draw){
 const {p,w,h,f}=d,t=f-2700;
 text(d,20,24,'真实目标：尽快抵达终点',p?39:34,C.amber,'left',500);
 const tw=p?w-30:w*.60,th=p?420:h-115,tx=15,ty=p?72:75;
 track(d,tx,ty,tw,th,t);
 text(d,tx+20,ty+30,'青：正常路线',p?30:25,C.cyan);text(d,tx+tw-20,ty+30,'品红：绕圈策略',p?30:25,C.magenta,'right');
 if(p){
  rect(d,15,525,w-30,142,C.magenta);text(d,40,563,'代理奖励：撞到靶标就加分',39,C.magenta);
  text(d,40,619,'绕圈 → 靶标刷新 → 继续得分',39,C.ink);
  const n=Math.floor(t/(2*Math.PI*45/3));
  text(d,30,717,`绕圈船积分 +${n}`,42,C.gold);text(d,w-35,717,'完赛 0 次',42,C.amber,'right');
  text(d,30,790,'利用规则漏洞，不必改写奖励代码',39,C.muted);
 }else{
  const x=w*.64;rect(d,x,75,w-x-15,190,C.magenta);text(d,x+30,112,'代理奖励',31,C.magenta);text(d,x+30,164,'撞到靶标 → 得分',38);text(d,x+30,220,'靶标刷新 → 可以反复刷',29,C.muted);
  text(d,x+30,326,`绕圈船积分 +${Math.floor(t/(2*Math.PI*45/3))}`,49,C.gold);text(d,x+30,400,'完赛 0 次',49,C.amber);
  text(d,x+30,485,'利用评分漏洞 ≠ 改写奖励代码',27,C.muted);
 }
}
export function drawChart(d:Draw){
 const {p,w,h,f}=d,q=clamp((f-3600)/840),m=policyMetrics(q);
 const x=p?95:105,y=p?100:65,cw=p?w-145:w*.56,ch=p?405:370;
 text(d,p?20:25,22,'两种策略混合的教学模型',p?36:29,C.muted);
 for(let i=0;i<=4;i++){const yy=y+ch-i*ch/4;line(d,[[x,yy],[x+cw,yy]],C.line,1);text(d,x-18,yy,`${i*25}`,p?31:24,C.muted,'right');}
 arrow(d,x,y+ch,x+cw+10,y+ch,C.muted,2);arrow(d,x,y+ch,x,y-15,C.muted,2);
 text(d,x,y-38,'各自归一化 / %',p?30:25,C.muted);
 const a:number[][]=[],b:number[][]=[];
 for(let i=0;i<=120*q;i++){const z=i/120,v=policyMetrics(z);a.push([x+z*cw,y+ch*(1-v.normalizedProxy)]);b.push([x+z*cw,y+ch*(1-v.finishRate)]);}
 if(a.length>1){line(d,a,C.magenta,6);line(d,b,C.amber,6);}
 dot(d,x+q*cw,y+ch*(1-m.normalizedProxy),9,C.magenta);dot(d,x+q*cw,y+ch*(1-m.finishRate),9,C.amber);
 for(let i=0;i<=2;i++)text(d,x+i*cw/2,y+ch+35,`${i*50}%`,p?30:24,C.muted,'center');
 text(d,x+cw/2,y+ch+83,'选择绕圈策略的比例 q',p?39:29,C.ink,'center');
 if(p){
  text(d,24,641,`代理奖励  ${Math.round(m.normalizedProxy*100)}%`,42,C.magenta);text(d,24,706,`完赛率      ${Math.round(m.finishRate*100)}%`,42,C.amber);
  text(d,24,775,'q ↑：多刷分，少完赛',39,C.muted);
 }else{
  const xx=w*.66; text(d,xx,115,'同一个优化方向',33,C.muted);text(d,xx,205,`代理奖励  ${Math.round(m.normalizedProxy*100)}%`,48,C.magenta);text(d,xx,290,`完赛率      ${Math.round(m.finishRate*100)}%`,48,C.amber);
  text(d,xx,395,'q ↑：更多绕圈，更少完赛',30);text(d,xx,455,'R = 1 + 5q     P(完赛) = 1 − q',27,C.muted);
 }
}
export function drawAgents(d:Draw){
 const {p,w,h,f}=d;const cols=p?3:6,rows=2,gap=p?14:18,top=p?98:80,cw=(w-40-gap*(cols-1))/cols,ch=p?205:150;
 text(d,20,25,'更多候选，都在利用同一个漏洞',p?39:34,C.magenta,'left',500);
 for(let i=0;i<cols*rows;i++){const x=20+(i%cols)*(cw+gap),y=top+Math.floor(i/cols)*(ch+gap);track(d,x,y,cw,ch,f+i*31,true);}
 const yy=p?590:top+rows*(ch+gap)+36;
 text(d,24,yy,'并行搜索增加了',p?39:30,C.muted);text(d,w-28,yy,'独立观测没有增加',p?39:30,C.amber,'right');
 const by=p?642:yy+41,bh=p?124:70;rect(d,20,by,w-40,bh,C.line);
 const yy2=by+bh/2; text(d,40,yy2,'候选 × N',p?39:32,C.magenta);arrow(d,p?290:330,yy2,p?490:w-420,yy2,C.magenta,4);
 text(d,w-44,yy2,'同一评分器',p?39:32,C.ink,'right');
 if(p)text(d,24,812,'算力扩张，不自动产生新事实',39,C.muted);
}
