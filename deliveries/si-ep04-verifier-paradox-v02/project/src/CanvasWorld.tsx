import React,{useLayoutEffect,useRef} from 'react';
import {Draw,C} from './draw';
import {drawFormal,drawBoundary,drawFeedback} from './FormalScenes';
import {drawBoat,drawChart,drawAgents} from './RewardScenes';
import {drawPhysical,drawConclusion,drawLandauer} from './MeasurementScenes';
export const CanvasWorld:React.FC<{frame:number;portrait:boolean;width:number;height:number}>=({frame,portrait,width,height})=>{
 const ref=useRef<HTMLCanvasElement>(null);
 useLayoutEffect(()=>{const c=ref.current!.getContext('2d')!;const lw=portrait?1080:1920,lh=portrait?1920:1080,s=width/lw;c.resetTransform();c.clearRect(0,0,width,height);c.scale(s,s);c.fillStyle=C.bg;c.fillRect(0,0,lw,lh);
  // Moving observation grid is secondary; semantic packets/boats/sensors provide main motion.
  c.strokeStyle='#102031';c.lineWidth=.7;
  for(let i=-2;i<44;i++){const y=i*47+(frame/22)%47;c.beginPath();c.moveTo(0,y);c.lineTo(lw,y);c.stroke();}
  for(let i=0;i<48;i++){const x=i*49;c.beginPath();c.moveTo(x,0);c.lineTo(x,lh);c.stroke();}
  const x=portrait?65:100,y=portrait?440:300,w=portrait?850:1720,h=portrait?850:580;c.save();c.translate(x,y);c.beginPath();c.rect(0,0,w,h);c.clip();
  const d:Draw={ctx:c,f:frame,p:portrait,w,h};if(frame<1200)drawFormal(d);else if(frame<1800)drawBoundary(d);else if(frame<2700)drawFeedback(d);else if(frame<3600)drawBoat(d);else if(frame<4500)drawChart(d);else if(frame<5400)drawAgents(d);else if(frame<6300)drawPhysical(d);else if(frame<6930)drawConclusion(d);else drawLandauer(d);c.restore();
 },[frame,portrait,width,height]);
 return <canvas ref={ref} width={width} height={height} style={{position:'absolute',inset:0,width,height}}/>;
};
