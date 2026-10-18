import React from 'react';
import {Audio, Img, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import timelineJson from './timeline.json';
import type {Shot, Timeline} from '../types';
import {PaintedSurface, type SurfaceMode} from './PaintedSurface';
import {BrushWriting} from './BrushWriting';

const timeline = timelineJson as Timeline;
const FONT = '"Kaiti SC", "STKaiti", "Songti SC", serif';
const clamp = (x: number) => Math.max(0, Math.min(1, x));
const smooth = (x: number) => {const t=clamp(x); return t*t*(3-2*t);};
const paper = staticFile('museum/paper.png');
const cleanGathering = staticFile('museum/gathering-clean.png');
const emptyGathering = staticFile('museum/gathering-empty.png');
const stream = staticFile('museum/stream-clean.png');
const landscape = staticFile('images/landscape.png');
const study = staticFile('images/study.png');

const Painting: React.FC<{src: string; frame: number; mode?: SurfaceMode; scale: number}> = ({src,frame,mode='still',scale}) =>
  mode === 'still' || mode === 'landscape'
    ? <Img src={src} style={{position:'absolute',inset:0,width:'100%',height:'100%',objectFit:'cover'}} />
    : <PaintedSurface src={src} frame={frame} mode={mode} width={1920*scale} height={1080*scale} />;

const Bamboo: React.FC<{frame: number; amount?: number; left?: number; top?: number}> = ({frame,amount=1,left=850,top=-160}) => {
  const sway = Math.sin(frame*.036)*2.6 + Math.sin(frame*.015+1.2)*1.2;
  return <Img src={staticFile('museum/bamboo-clean.png')} style={{position:'absolute',left,top,width:1130,height:753,objectFit:'contain',opacity:.88,transformOrigin:'100% 9%',transform:`rotate(${sway*amount}deg) translateY(${Math.sin(frame*.025)*8*amount}px)`,filter:'drop-shadow(0 6px 8px rgba(19,38,25,.08))'}} />;
};

// Cup and wake share a path in normalized painting coordinates.
// The bends follow the open water between the seated figures and the banks.
const FloatingCup: React.FC<{frame: number; duration: number; close?: boolean}> = ({frame,duration,close=false}) => {
  const t=smooth(frame/Math.max(1,duration-1));
  let x: number,y: number,w: number;
  if (close) {
    x=(.66-.24*t)*1920; y=(.54+.20*t)*1080; w=210+20*t;
  } else {
    const points=[[.74,.37],[.70,.48],[.61,.61],[.50,.75],[.455,.84]];
    const segment=Math.min(3,Math.floor(t*4));
    const local=t*4-segment;
    x=(points[segment][0]+(points[segment+1][0]-points[segment][0])*local)*1920;
    y=(points[segment][1]+(points[segment+1][1]-points[segment][1])*local)*1080;
    w=70+110*t;
  }
  y+=Math.sin(frame*.10)*2;
  const angle=-6+Math.sin(frame*.035)*5;
  return <div style={{position:'absolute',left:x,top:y,width:0,height:0,transform:`rotate(${angle}deg)`}}>
    <svg width={w*1.45} height={w*.5} style={{position:'absolute',left:-w*.72,top:-w*.04,overflow:'visible'}}>
      {[0,1,2].map(i => <ellipse key={i} cx={w*.72} cy={w*.13+i*3} rx={w*(.37+i*.11)} ry={w*(.07+i*.021)} fill="none" stroke="#e5ece0" strokeWidth={1.1} opacity={.38-i*.095} />)}
      <path d={`M ${w*.73} ${w*.16} Q ${w*1.02} ${w*.31} ${w*1.4} ${w*.39}`} stroke="#e0e9df" strokeWidth={1.5} fill="none" opacity={.24} />
    </svg>
    <Img src={staticFile('museum/ear-cup.png')} style={{position:'absolute',width:w,height:w*.563,left:-w/2,top:-w*.36,objectFit:'contain',filter:'drop-shadow(1px 4px 3px rgba(28,44,34,.25))'}} />
  </div>;
};

const InkQuote: React.FC<{lines:string[];frame:number;duration:number;x?:number;y?:number;size?:number;light?:boolean}> = ({lines,frame,duration,x=180,y=290,size=92,light=false}) => {
  const alpha=smooth((frame-12)/32)*smooth((duration-frame)/22);
  return <div style={{position:'absolute',left:x,top:y,color:light?'#f4ead4':'#283a35',fontFamily:FONT,fontSize:size,letterSpacing:12,lineHeight:1.6,opacity:alpha,textShadow:light?'0 2px 20px #243d33':undefined,transform:`translateY(${(1-smooth((frame-12)/60))*16}px)`}}>
    {lines.map(line=><div key={line}>{line}</div>)}
  </div>;
};

const WrittenPaper: React.FC<{text:string;frame:number;duration:number;title?:boolean}> = ({text,frame,duration,title=false}) => <>
  <Img src={paper} style={{position:'absolute',inset:0,width:'100%',height:'100%',objectFit:'cover'}} />
  <BrushWriting text={text} frame={frame-(title?18:8)} duration={title?240:Math.min(duration-40,text==='錄其所述'?174:126)} x={title?350:405} y={title?365:395} size={title?265:240} gap={title?30:26} />
  {title ? <>
    <div style={{position:'absolute',left:374,top:232,fontFamily:FONT,color:'#667166',fontSize:28,letterSpacing:8,opacity:smooth((frame-30)/24)}}>永和九年 · 暮春之初</div>
    <div style={{position:'absolute',left:373,top:736,fontFamily:FONT,color:'#455046',fontSize:30,letterSpacing:7,opacity:smooth((frame-260)/30)}}>王羲之</div>
    <div style={{position:'absolute',right:346,top:722,border:'2px solid #996341',color:'#996341',fontFamily:FONT,fontSize:23,padding:'9px 7px',writingMode:'vertical-rl',letterSpacing:4,opacity:smooth((frame-265)/22)}}>暮春雅集</div>
  </> : null}
</>;

const ShotArt: React.FC<{shot:Shot;frame:number;scale:number}> = ({shot,frame,scale}) => {
  const f=Math.max(0,Math.min(shot.duration-1,frame));
  const camera=smooth(f/shot.duration);
  const zoom=1.015+camera*.02;
  if (shot.id==='title') return <WrittenPaper text="蘭亭集序" frame={f} duration={shot.duration} title />;
  if (shot.id==='poems' || shot.id==='record') return <WrittenPaper text={shot.id==='poems'?'一觴一詠':'錄其所述'} frame={f} duration={shot.duration} />;
  if (shot.id==='judgment') return <>
    <Painting src={paper} frame={f} scale={scale} />
    <InkQuote lines={['固知一死生為虛誕，','齊彭殤為妄作。']} frame={f} duration={shot.duration} x={365} y={342} size={73} />
  </>;
  let src=landscape;
  let mode:SurfaceMode='landscape';
  if (['grove','cups','contentment','traces'].includes(shot.id)) {src=cleanGathering;mode='gathering';}
  if (['water','change'].includes(shot.id)) {src=stream;mode='stream';}
  if (['mortality','time'].includes(shot.id)) {src=emptyGathering;mode='gathering';}
  if (['life','reading'].includes(shot.id)) {src=study;mode='still';}
  if (shot.id==='end') {src=paper;mode='still';}
  return <>
    <div style={{position:'absolute',inset:0,transform:`scale(${zoom}) translateX(${(camera-.5)*(shot.id==='water'?10:-18)}px)`,transformOrigin:'50% 45%'}}>
      <Painting src={src} frame={f} mode={mode} scale={scale} />
      {shot.id==='life' ? <div style={{position:'absolute',inset:0,opacity:smooth((f-196)/44)}}><Painting src={landscape} frame={f} scale={scale} /></div> : null}
      {shot.id==='traces' ? <div style={{position:'absolute',inset:0,opacity:smooth((f-58)/96)}}><Painting src={emptyGathering} frame={f} mode="gathering" scale={scale} /></div> : null}
      {shot.id==='water' ? <FloatingCup frame={f} duration={shot.duration} close /> : null}
      {shot.id==='cups' ? <FloatingCup frame={f} duration={shot.duration} /> : null}
    </div>
    {['grove','breeze','joy','future'].includes(shot.id) ? <Bamboo frame={f+shot.from} amount={shot.id==='breeze'?1.7:.9} top={shot.id==='grove'?-220:-170} /> : null}
    {shot.id==='date' ? <InkQuote lines={['暮春之初']} frame={f} duration={shot.duration} x={155} y={275} size={94} /> : null}
    {shot.id==='breeze' ? <InkQuote lines={['天朗氣清','惠風和暢']} frame={f} duration={shot.duration} x={148} y={290} size={90} /> : null}
    {shot.id==='joy' && f>164 ? <InkQuote lines={['信可樂也']} frame={f-164} duration={shot.duration-164} x={156} y={338} size={100} /> : null}
    {shot.id==='change' ? <InkQuote lines={['情隨事遷']} frame={f} duration={shot.duration} x={156} y={285} size={82} /> : null}
    {shot.id==='time' ? <InkQuote lines={['後之視今','亦猶今之視昔']} frame={f} duration={shot.duration} x={138} y={200} size={65} light /> : null}
    {shot.id==='future' ? <InkQuote lines={['亦將有感於斯文']} frame={f} duration={shot.duration} x={140} y={300} size={75} /> : null}
    {shot.id==='end' ? <>
      <BrushWriting text="蘭亭集序" frame={1} duration={0} x={470} y={345} size={225} gap={24} showBrush={false} />
      <div style={{position:'absolute',left:480,top:650,fontFamily:FONT,color:'#485447',fontSize:38,letterSpacing:7,opacity:1-smooth((f-180)/56)}}>后之览者，亦将有感于斯文。</div>
      <div style={{position:'absolute',inset:0,background:'#eadfc7',opacity:smooth((f-192)/46)}} />
    </> : null}
    {shot.mood!=='joy' && shot.id!=='end' ? <div style={{position:'absolute',inset:0,background:shot.mood==='reflect'?'rgba(40,53,47,.10)':'rgba(51,60,48,.04)'}} /> : null}
  </>;
};

const Caption: React.FC<{shot:Shot;frame:number}> = ({shot,frame}) => {
  const cue=shot.cues.find(c=>frame>=c.from && frame<c.from+c.duration);
  if (!cue) return null;
  const fade=smooth((frame-cue.from)/5);
  return <div style={{position:'absolute',inset:0,pointerEvents:'none',opacity:fade}}>
    <div style={{position:'absolute',left:0,right:0,bottom:0,height:260,background:'linear-gradient(0deg, rgba(15,29,26,.83),rgba(15,29,26,.36) 48%,transparent)'}} />
    <div style={{position:'absolute',bottom:102,left:140,right:140,textAlign:'center',fontFamily:'"Songti SC", "STSong", serif',fontSize:42,letterSpacing:2.5,lineHeight:1.6,fontWeight:600,color:'#fcf5e4',textShadow:'0 2px 8px rgba(0,0,0,.7)'}}>{cue.text}</div>
  </div>;
};

export const MuseumFilm: React.FC = () => {
  const frame=useCurrentFrame();
  const {width}=useVideoConfig();
  const scale=width/1920;
  const active=timeline.shots.find(s=>frame>=s.from && frame<s.from+s.duration) ?? timeline.shots.at(-1)!;
  return <div style={{position:'absolute',inset:0,background:'#eadfc7',overflow:'hidden'}}>
    <Audio src={staticFile('museum/audio/soundtrack.wav')} />
    <div style={{position:'absolute',width:1920,height:1080,transform:`scale(${scale})`,transformOrigin:'0 0',overflow:'hidden'}}>
      {timeline.shots.map((shot,index)=>{
        if (frame<shot.from-18 || frame>=shot.from+shot.duration+18) return null;
        const alpha=index===0?1:smooth((frame-shot.from+18)/36);
        return <div key={shot.id} style={{position:'absolute',inset:0,opacity:alpha}}><ShotArt shot={shot} frame={frame-shot.from} scale={scale} /></div>;
      })}
      {active.kind==='scene' ? <>
        <div style={{position:'absolute',top:65,left:102,color:'#f8edda',fontFamily:FONT,fontSize:27,letterSpacing:5,padding:'10px 20px',borderLeft:'2px solid rgba(204,173,104,.78)',background:'rgba(28,47,36,.62)'}}>{active.chapter}</div>
        <Caption shot={active} frame={frame-active.from} />
      </> : null}
    </div>
  </div>;
};
