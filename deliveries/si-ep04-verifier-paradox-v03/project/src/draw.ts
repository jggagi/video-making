export const C={bg:'#050811',panel:'#0d1726',line:'#294156',ink:'#edf4f7',muted:'#a5bac9',cyan:'#06b6d4',green:'#10b981',amber:'#f59e0b',magenta:'#d946ef',red:'#ef4444',gold:'#facc15'};
export type Draw={ctx:CanvasRenderingContext2D;f:number;p:boolean;w:number;h:number};
export const clamp=(x:number)=>Math.max(0,Math.min(1,x));
export const mix=(a:number,b:number,t:number)=>a+(b-a)*clamp(t);
export function text(d:Draw,x:number,y:number,s:string,size=d.p?39:29,color:string=C.ink,align:CanvasTextAlign='left',weight=400){const c=d.ctx;c.font=`${weight} ${size}px "PingFang SC", "Hiragino Sans GB", sans-serif`;c.fillStyle=color;c.textAlign=align;c.textBaseline='middle';c.fillText(s,x,y);}
export function line(d:Draw,points:number[][],color:string=C.line,width=2,dash:number[]=[]){const c=d.ctx;c.beginPath();points.forEach(([x,y],i)=>i?c.lineTo(x,y):c.moveTo(x,y));c.strokeStyle=color;c.lineWidth=width;c.setLineDash(dash);c.stroke();c.setLineDash([]);}
export function rect(d:Draw,x:number,y:number,w:number,h:number,stroke:string=C.line,fill:string=C.panel,r=14){const c=d.ctx;c.beginPath();c.roundRect(x,y,w,h,r);c.fillStyle=fill;c.fill();c.lineWidth=2;c.strokeStyle=stroke;c.stroke();}
export function dot(d:Draw,x:number,y:number,r:number,color:string=C.cyan){const c=d.ctx;c.beginPath();c.arc(x,y,r,0,Math.PI*2);c.fillStyle=color;c.fill();}
export function arrow(d:Draw,x:number,y:number,xx:number,yy:number,color:string=C.cyan,width=3){line(d,[[x,y],[xx,yy]],color,width);const a=Math.atan2(yy-y,xx-x),s=12;line(d,[[xx-s*Math.cos(a-.5),yy-s*Math.sin(a-.5)],[xx,yy],[xx-s*Math.cos(a+.5),yy-s*Math.sin(a+.5)]],color,width);}
export function pulse(d:Draw,x:number,y:number,xx:number,yy:number,color:string=C.cyan,speed=120,offset=0){arrow(d,x,y,xx,yy,color);for(let i=0;i<3;i++){const t=((d.f+offset)/speed+i/3)%1;dot(d,mix(x,xx,t),mix(y,yy,t),5,color);}}
export function badge(d:Draw,x:number,y:number,w:number,s:string,color:string=C.cyan,size=d.p?34:25){rect(d,x,y,w,d.p?64:48,color);text(d,x+w/2,y+(d.p?32:24),s,size,color,'center',500);}
