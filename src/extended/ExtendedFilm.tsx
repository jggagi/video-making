import React from 'react';
import {Audio, Img, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import timelineJson from './timeline.json';
import type {Shot, Timeline} from '../types';
import {WaterSurface, type SurfaceMode} from './WaterSurface';
import {BrushWriting} from '../museum/BrushWriting';
import {LivingLayers} from './LivingLayers';

const timeline = timelineJson as Timeline;
const FONT = '"Kaiti SC", "STKaiti", "Songti SC", serif';
const clamp = (x:number) => Math.max(0,Math.min(1,x));
const smooth = (x:number) => {const t=clamp(x);return t*t*(3-2*t);};
const art = (name:string) => staticFile(`extended/${name}.png`);
const paper = staticFile('museum/paper.png');
const landscape = staticFile('images/landscape.png');
const gathering = staticFile('museum/gathering-clean.png');
const empty = staticFile('museum/gathering-empty.png');
const stream = staticFile('museum/stream-clean.png');
const study = staticFile('images/study.png');

const Painting: React.FC<{src:string;frame:number;scale:number;mode?:SurfaceMode}> = ({src,frame,scale,mode='still'}) =>
  mode==='stream'||mode==='gathering'
    ? <WaterSurface src={src} frame={frame} mode={mode} width={1920*scale} height={1080*scale}/>
    : <Img src={src} style={{position:'absolute',inset:0,width:'100%',height:'100%',objectFit:'cover'}}/>;

const Quote: React.FC<{lines:string[];frame:number;duration:number;x?:number;y?:number;size?:number;light?:boolean}> = ({lines,frame,duration,x=150,y=270,size=86,light=false}) =>
  <div style={{position:'absolute',left:x,top:y,fontFamily:FONT,fontSize:size,lineHeight:1.65,letterSpacing:10,color:light?'#f6eed8':'#293e35',opacity:smooth((frame-16)/30)*smooth((duration-frame)/24),textShadow:light?'0 2px 16px #263a32':undefined,transform:`translateY(${(1-smooth(frame/80))*14}px)`}}>{lines.map(line=><div key={line}>{line}</div>)}</div>;

const Cup: React.FC<{frame:number;duration:number;close?:boolean}> = ({frame,duration,close=false}) => {
  const t=smooth(frame/Math.max(1,duration-1));
  let x:number,y:number,w:number;
  if(close){x=(.66-.24*t)*1920;y=(.54+.20*t)*1080;w=215+30*t;}
  else {
    const p=[[.74,.37],[.70,.48],[.61,.61],[.50,.75],[.455,.84]];
    const s=Math.min(3,Math.floor(t*4)),u=t*4-s;
    x=(p[s][0]+(p[s+1][0]-p[s][0])*u)*1920;
    y=(p[s][1]+(p[s+1][1]-p[s][1])*u)*1080;w=76+115*t;
  }
  y+=Math.sin(frame*.095)*2.5;
  const angle=-6+Math.sin(frame*.032)*6;
  return <div style={{position:'absolute',left:x,top:y,width:0,height:0,transform:`rotate(${angle}deg)`}}>
    <Img src={staticFile('museum/ear-cup.png')} style={{position:'absolute',width:w,height:w*.563,left:-w/2,top:-w*.03,opacity:.14,transform:'scaleY(-.32)',transformOrigin:'50% 15%',filter:'blur(2px)'}}/>
    <svg width={w*1.9} height={w*.8} style={{position:'absolute',left:-w*.95,top:-w*.11,overflow:'visible'}}>
      {[0,1,2,3].map(i=>{const phase=(frame*.018+i*.25)%1;return <ellipse key={i} cx={w*.95} cy={w*.20} rx={w*(.3+phase*.56)} ry={w*(.065+phase*.10)} fill="none" stroke="#eaf0df" strokeWidth={1.6} opacity={.38*(1-phase)}/>;})}
      <path d={`M ${w*.95} ${w*.2} Q ${w*1.35} ${w*.43} ${w*1.8} ${w*.52}`} fill="none" stroke="#dae8d9" strokeWidth={1.5} opacity={.32}/>
    </svg>
    <Img src={staticFile('museum/ear-cup.png')} style={{position:'absolute',width:w,height:w*.563,left:-w/2,top:-w*.36,objectFit:'contain',filter:'drop-shadow(1px 4px 3px rgba(28,44,34,.25))'}}/>
  </div>;
};

const Written: React.FC<{text:string;frame:number;duration:number;title?:boolean;inset?:boolean}> = ({text,frame,duration,title=false,inset=false}) =>
  <div style={{position:'absolute',inset:0,...(inset?{clipPath:'inset(15% 12% 18% 12% round 4px)',filter:'drop-shadow(0 15px 25px rgba(22,35,26,.2))'}:{})}}>
    <Img src={paper} style={{position:'absolute',inset:0,width:'100%',height:'100%',objectFit:'cover'}}/>
    <BrushWriting text={text} frame={frame-(title?12:8)} duration={title?226:Math.min(duration-40,text==='錄其所述'?168:122)} x={title?350:405} y={title?365:395} size={title?265:240} gap={title?30:26}/>
    {title?<>
      <div style={{position:'absolute',left:374,top:232,fontFamily:FONT,color:'#667166',fontSize:28,letterSpacing:8,opacity:smooth((frame-28)/24)}}>永和九年 · 暮春之初</div>
      <div style={{position:'absolute',left:374,top:730,fontFamily:FONT,color:'#455046',fontSize:30,letterSpacing:7,opacity:smooth((frame-238)/24)}}>王羲之</div>
      <div style={{position:'absolute',right:346,top:720,border:'2px solid #996341',color:'#996341',fontFamily:FONT,fontSize:23,padding:'9px 7px',writingMode:'vertical-rl',letterSpacing:4,opacity:smooth((frame-244)/20)}}>暮春雅集</div>
    </>:null}
  </div>;

const ShotArt: React.FC<{shot:Shot;frame:number;scale:number}> = ({shot,frame,scale}) => {
  const f=clamp(frame/shot.duration)*shot.duration;
  const t=smooth(f/shot.duration);
  const second=shot.cues[1]?.from??shot.duration*.5;
  if(shot.id==='title')return <Written text="蘭亭集序" frame={f} duration={shot.duration} title/>;
  if(shot.id==='judgment')return <><Painting src={paper} frame={f} scale={scale}/><Quote lines={['固知一死生為虛誕，','齊彭殤為妄作。']} frame={f} duration={shot.duration} x={365} y={342} size={73}/></>;
  if(shot.id==='record')return <Written text="錄其所述" frame={f} duration={shot.duration}/>;
  let src=landscape,mode:SurfaceMode='still';
  if(['grove','cups','traces'].includes(shot.id)){src=gathering;mode='gathering';}
  if(['water','change'].includes(shot.id)){src=stream;mode='stream';}
  if(shot.id==='mortality'){src=empty;mode='gathering';}
  if(shot.id==='time'){src=gathering;mode='gathering';}
  if(shot.id==='future'){src=art('modern-visitors');mode='gathering';}
  if(shot.id==='poems'||shot.id==='contentment')src=art('poets-close');
  if(shot.id==='breeze')src=art('sky');
  if(shot.id==='joy')src=art('sky');
  if(shot.id==='life')src=art('conversation');
  if(shot.id==='reading')src=art('scroll-close');
  if(shot.id==='end')src=paper;
  const overlay=(next:string,start:number,nextMode:SurfaceMode='still',length=36)=> <div style={{position:'absolute',inset:0,opacity:smooth((f-start)/length)}}><Painting src={next} frame={f} scale={scale} mode={nextMode}/></div>;
  const joyDown=shot.cues[0]?shot.cues[0].from+shot.cues[0].duration*.34:80;
  return <>
    <div style={{position:'absolute',inset:0,transform:`scale(${1.025+t*.027}) translate(${(t-.5)*(shot.id==='water'?12:-28)}px, ${(t-.5)*(shot.id==='grove'?32:7)}px)`,transformOrigin:'50% 43%'}}>
      <Painting src={src} frame={f} mode={mode} scale={scale}/>
      {shot.id==='reading'?<div style={{position:'absolute',left:685,top:750,fontFamily:FONT,fontSize:43,letterSpacing:12,color:'#33382c',opacity:.65,transform:'rotate(-4deg) skewX(-12deg)',transformOrigin:'0 0'}}>死生亦大矣。</div>:null}
      {shot.id==='date'?overlay(gathering,second-10,'gathering'):null}
      {shot.id==='grove'?overlay(art('forest'),second-18):null}
      {shot.id==='joy'?<>{overlay(art('spring-detail'),joyDown)}{overlay(landscape,second)}</>:null}
      {shot.id==='life'?overlay(landscape,second+shot.cues[1].duration*.37):null}
      {shot.id==='reading'?overlay(study,second-18):null}
      {shot.id==='traces'?overlay(empty,shot.cues[0].duration*.6,'gathering',100):null}
      {shot.id==='time'?<>{overlay(empty,30,'gathering',34)}{overlay(art('modern-visitors'),78,'gathering',36)}</>:null}
      {shot.id==='water'?<Cup frame={f} duration={shot.duration} close/>:null}
      {shot.id==='cups'?<Cup frame={f} duration={shot.duration}/>:null}
    </div>
    {['grove','breeze'].includes(shot.id)?<LivingLayers frame={shot.from+f} mode="bamboo" intensity={shot.id==='grove'?.72:1}/>:null}
    {['date','joy'].includes(shot.id)?<LivingLayers frame={shot.from+f} mode="landscape" intensity={.52}/>:null}
    {shot.id==='joy'&&f>joyDown&&f<second+28?<div style={{opacity:smooth((f-joyDown)/24)*smooth((second+28-f)/28)}}><LivingLayers frame={f} mode="spring" intensity={.85}/></div>:null}
    {['life','reading'].includes(shot.id)?<LivingLayers frame={f} mode="interior" intensity={.9}/>:null}
    {shot.id==='date'?<Quote lines={['暮春之初']} frame={f} duration={second} size={88}/>:null}
    {shot.id==='breeze'?<Quote lines={['天朗氣清','惠風和暢']} frame={f} duration={shot.duration} size={88}/>:null}
    {shot.id==='joy'?<Quote lines={['信可樂也']} frame={f-second} duration={shot.duration-second} y={320} size={96}/>:null}
    {shot.id==='change'?<Quote lines={['情隨事遷']} frame={f} duration={shot.duration} size={80}/>:null}
    {shot.id==='time'?<Quote lines={['後之視今','亦猶今之視昔']} frame={f} duration={shot.duration} x={570} y={65} size={58} light/>:null}
    {shot.id==='future'?<Quote lines={['亦將有感於斯文']} frame={f} duration={shot.duration} x={555} y={155} size={63} light/>:null}
    {shot.id==='poems'?<div style={{opacity:smooth((f-shot.duration*.42)/28)}}><Written text="一觴一詠" frame={f-shot.duration*.42} duration={shot.duration*.58}/></div>:null}
    {shot.id==='end'?<>
      <BrushWriting text="蘭亭集序" frame={1} duration={0} x={470} y={345} size={225} gap={24} showBrush={false}/>
      <div style={{position:'absolute',left:480,top:650,fontFamily:FONT,color:'#485447',fontSize:38,letterSpacing:7}}>后之览者，亦将有感于斯文。</div>
      <div style={{position:'absolute',inset:0,background:'#eadfc7',opacity:smooth((f-shot.duration+50)/48)}}/>
    </>:null}
    {shot.mood==='reflect'&&shot.id!=='end'?<div style={{position:'absolute',inset:0,background:'rgba(40,53,47,.075)'}}/>:null}
  </>;
};

const Caption: React.FC<{shot:Shot;frame:number}> = ({shot,frame}) => {
  const cue=shot.cues.find(c=>frame>=c.from&&frame<c.from+c.duration);
  if(!cue)return null;
  return <div style={{position:'absolute',inset:0,opacity:smooth((frame-cue.from)/4)}}>
    <div style={{position:'absolute',left:0,right:0,bottom:0,height:240,background:'linear-gradient(0deg,rgba(15,29,26,.85),rgba(15,29,26,.34) 48%,transparent)'}}/>
    <div style={{position:'absolute',bottom:102,left:140,right:140,textAlign:'center',fontFamily:'"Songti SC", "STSong", serif',fontSize:42,letterSpacing:2.5,lineHeight:1.6,fontWeight:600,color:'#fcf5e4',textShadow:'0 2px 8px rgba(0,0,0,.7)'}}>{cue.text}</div>
  </div>;
};

export const ExtendedFilm: React.FC = () => {
  const frame=useCurrentFrame(),{width}=useVideoConfig(),scale=width/1920;
  const active=timeline.shots.find(s=>frame>=s.from&&frame<s.from+s.duration)??timeline.shots.at(-1)!;
  return <div style={{position:'absolute',inset:0,background:'#eadfc7',overflow:'hidden'}}>
    <Audio src={staticFile('extended/audio/soundtrack.wav')}/>
    <div style={{position:'absolute',width:1920,height:1080,transform:`scale(${scale})`,transformOrigin:'0 0',overflow:'hidden'}}>
      {timeline.shots.map((shot,index)=>frame<shot.from-18||frame>=shot.from+shot.duration+18?null:<div key={shot.id} style={{position:'absolute',inset:0,opacity:index===0?1:smooth((frame-shot.from+18)/36)}}><ShotArt shot={shot} frame={frame-shot.from} scale={scale}/></div>)}
      {active.kind==='scene'?<>
        <div style={{position:'absolute',top:65,left:102,color:'#f8edda',fontFamily:FONT,fontSize:27,letterSpacing:5,padding:'10px 20px',borderLeft:'2px solid rgba(204,173,104,.78)',background:'rgba(28,47,36,.62)'}}>{active.chapter}</div>
        <Caption shot={active} frame={frame-active.from}/>
      </>:null}
    </div>
  </div>;
};
