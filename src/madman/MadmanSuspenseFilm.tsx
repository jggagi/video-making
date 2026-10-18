import React from 'react';
import {AbsoluteFill, Audio, Img, staticFile, useCurrentFrame} from 'remotion';
import rawTimeline from './suspense-v5-timeline.json';

type Cue = {id:string;text:string;from:number;duration:number;audioFrames:number};
type Shot = {id:string;section:string;from:number;duration:number;cues:Cue[]};
type Caption = {from:number;duration:number;text:string;cueId:string};
type Timeline = {durationInFrames:number;audioFile:string;shots:Shot[];captions:Caption[]};
const timeline = rawTimeline as Timeline;
const SERIF = '"Songti SC", "STSong", serif';
const SANS = '"PingFang SC", sans-serif';
const INK = '#e7e4dc';
const clamp = (n:number) => Math.min(1,Math.max(0,n));
const smooth = (n:number) => {const t=clamp(n);return t*t*(3-2*t);};
const rise = (f:number,start:number,length=24) => smooth((f-start)/length);
const at = (s:Shot,id:string) => s.cues.find(c=>c.id===id)?.from ?? 0;

// A cut changes the observer's attention; ordinary props remain ordinary.
const Photo:React.FC<{asset:string;scale?:number;origin?:string;x?:number;y?:number;dark?:number;blur?:number}> = ({asset,scale=1,origin='50% 50%',x=0,y=0,dark=0,blur=0}) => <AbsoluteFill style={{overflow:'hidden'}}>
  <Img src={staticFile(`madman/cinema-v5/${asset}.png`)} style={{width:1920,height:1080,objectFit:'cover',transform:`translate(${x}px,${y}px) scale(${scale})`,transformOrigin:origin,filter:blur?`blur(${blur}px)`:undefined}}/>
  <AbsoluteFill style={{background:`rgba(5,9,12,${dark})`}}/>
  <AbsoluteFill style={{background:'radial-gradient(ellipse at 50% 48%,transparent 32%,rgba(4,7,10,.23) 100%)'}}/>
</AbsoluteFill>;

const Scene:React.FC<{shot:Shot;f:number}> = ({shot:s,f}) => {
  const p=clamp(f/s.duration);
  if(s.id==='title') return <>
    <Photo asset="courtyard" y={72} dark={.2} scale={1.015}/>
    <div style={{position:'absolute',left:150,top:322,color:INK,opacity:rise(f,10,32)}}>
      <div style={{fontFamily:SERIF,fontSize:126,letterSpacing:18}}>狂人日记</div>
      <div style={{fontFamily:SERIF,fontSize:29,letterSpacing:12,marginTop:25}}>鲁迅</div>
      <div style={{fontFamily:SANS,fontSize:20,letterSpacing:5,marginTop:58,color:'#b6babd'}}>原文节选 · 心理悬疑改编</div>
    </div>
  </>;
  if(s.id==='moon') {
    const close=f>=at(s,'dog')+72;
    return <Photo asset="courtyard" y={close?-70:72} scale={close?1.8+rise(f,at(s,'dog')+72,170)*.025:1.015+p*.014} origin={close?'61% 67%':'50% 50%'} dark={close?.08:0}/>;
  }
  if(s.id==='street') {
    const whisper=f>=at(s,'whisper'), smile=f>=at(s,'smile');
    return <Photo asset="street" scale={smile?1.88+p*.025:whisper?1.52+p*.02:1.025+p*.02} origin={smile?'76% 40%':whisper?'74% 43%':'20% 42%'} dark={smile?.07:0}/>;
  }
  if(s.id==='door') {
    const cut=at(s,'lock')+(s.cues[0]?.audioFrames??240)*.4;
    return f<cut?<Photo asset="study" scale={1.22} origin="33% 44%" dark={.16}/>:<Photo asset="lock" scale={1.045+rise(f,cut,s.duration-cut)*.04} origin="68% 48%"/>;
  }
  if(s.id==='history') {
    const book=f>=at(s,'history-b'), reveal=rise(f,at(s,'history-c')+Math.round((s.cues[2]?.audioFrames??260)*.64),30);
    return <>
      <Photo asset="study" scale={book?1.67+p*.03:1.075} origin={book?'72% 81%':'33% 44%'} y={book?-240:0} dark={book?.10:.03}/>
      {book&&<div style={{position:'absolute',left:1290,top:640,fontFamily:SERIF,fontSize:52,letterSpacing:12,writingMode:'vertical-rl',color:'#251b14',transform:'scaleY(.48) skewX(-24deg) rotate(7deg)',transformOrigin:'0 0',filter:'blur(.3px)',mixBlendMode:'multiply',opacity:(1-reveal)*.8}}>仁义道德</div>}
      {reveal>0&&<div style={{position:'absolute',inset:0,background:'rgba(3,7,10,.30)',opacity:reveal}}/>}
      {reveal>0&&<div style={{position:'absolute',left:1268,top:662,fontFamily:SERIF,fontSize:76,letterSpacing:16,writingMode:'vertical-rl',color:'#22180f',opacity:reveal*.95,filter:`blur(${.25+(1-reveal)*3}px)`,transform:'scaleY(.48) skewX(-24deg) rotate(7deg)',transformOrigin:'0 0',mixBlendMode:'multiply'}}>吃人</div>}
    </>;
  }
  if(s.id==='meal') {
    const close=f>s.duration*.48;
    return <Photo asset="meal" scale={close?1.78+p*.025:1.018+p*.018} origin={close?'47% 56%':'50% 50%'} y={close?-40:0} dark={close?.04:0}/>;
  }
  if(s.id==='consult') {
    const t=at(s,'doctor'), d=s.cues[1]?.audioFrames??300;
    const pulse=f>=t+24&&f<t+d*.52;
    const face=f>=t+d*.52&&f<t+d*.84;
    return <Photo asset="consult" scale={pulse?1.94:face?1.68:1.018+p*.012} origin={pulse?'52% 77%':face?'77% 42%':'50% 50%'} y={pulse?-208:0} dark={pulse?.035:0}/>;
  }
  if(s.id==='aside') {
    const c=s.cues[0]; const meal=f>at(s,'aside')+(c?.audioFrames??220)*.62&&f<at(s,'aside')+(c?.audioFrames??220)*.79;
    return meal?<Photo asset="meal" scale={1.05}/>:<Photo asset="aside" scale={1.035+p*.028} origin="64% 43%" dark={.04}/>;
  }
  if(s.id==='question') return <Photo asset="study" scale={1.75} origin="34% 38%" dark={.08}/>;
  if(s.id==='named') {
    const label=f>=at(s,'label');
    return <Photo asset={label?'study':'onlookers'} scale={label?1.82+p*.025:1.025} origin={label?'34% 42%':'56% 42%'} dark={label?.15:0}/>;
  }
  if(s.id==='beams') {
    const reset=at(s,'false-weight'); const disturbed=f<reset;
    const pressure=rise(f,24,Math.max(48,reset-24));
    return <Photo asset="beams" scale={disturbed?1.035+pressure*.20:1.015} x={disturbed?Math.sin(f*.49)*pressure*5:0} y={disturbed?Math.sin(f*.31)*pressure*4:0} origin="51% 35%" dark={disturbed?pressure*.14:0} blur={disturbed?pressure*.5:0}/>;
  }
  if(s.id==='self') return <Photo asset="study" scale={1.75+p*.04} origin="34% 40%" dark={.12}/>;
  if(s.id==='children') return <Photo asset="children" scale={1.01+p*.015} dark={.02}/>;
  if(s.id==='epilogue') return <>
    <Photo asset="aside" scale={1.37} origin="73% 43%" dark={.04}/>
    <div style={{position:'absolute',left:142,top:196,fontFamily:SANS,fontSize:23,letterSpacing:5,color:INK,opacity:rise(f,8,24)*.8}}>小序 · 兄长的说法</div>
    <div style={{position:'absolute',left:146,top:358,fontFamily:SERIF,fontSize:73,letterSpacing:8,color:INK,opacity:rise(f,at(s,'cured')+60,34)}}>然已早愈，</div>
    <div style={{position:'absolute',left:150,top:476,fontFamily:SERIF,fontSize:47,letterSpacing:6,color:'#d0d3d1',opacity:rise(f,at(s,'cured')+94,32)}}>赴某地候补矣。</div>
  </>;
  if(s.id==='ending') {
    const fade=rise(f,36,30);
    return <>
      <Photo asset="lock" scale={1.12} origin="73% 47%" dark={.4}/>
      <AbsoluteFill style={{background:'#06090c',opacity:fade}}/>
      <div style={{position:'absolute',left:180,right:180,top:378,textAlign:'center',fontFamily:SERIF,fontSize:62,letterSpacing:6,lineHeight:1.8,color:INK,opacity:rise(f,66,28)}}>他真的疯了，<br/>还是周围的人让他疯了？</div>
      <div style={{position:'absolute',left:150,right:150,top:835,textAlign:'center',fontFamily:SANS,fontSize:17,letterSpacing:3,lineHeight:1.8,color:'#858d92',opacity:rise(f,103,24)}}>原著 鲁迅 · 原文节选与改编设问<br/>AI 生成画面 · 百炼合成男声 · 原创声音设计</div>
    </>;
  }
  return null;
};

export const MadmanSuspenseFilm:React.FC = () => {
  const f=useCurrentFrame();
  const shot=timeline.shots.find(s=>f>=s.from&&f<s.from+s.duration)??timeline.shots[timeline.shots.length-1];
  const local=f-shot.from;
  const caption=timeline.captions.find(c=>f>=c.from&&f<c.from+c.duration);
  const opening=1-rise(f,0,20);
  return <AbsoluteFill style={{background:'#06090c',overflow:'hidden'}}>
    <Audio src={staticFile(timeline.audioFile)}/>
    <Scene shot={shot} f={local}/>
    <AbsoluteFill style={{background:'#06090c',opacity:opening}}/>
    <div style={{position:'absolute',left:0,right:0,top:0,height:124,background:'#06090c'}}/>
    <div style={{position:'absolute',left:0,right:0,bottom:0,height:124,background:'#06090c'}}/>
    {caption&&<div style={{position:'absolute',left:100,right:100,top:984,textAlign:'center',fontFamily:SERIF,fontSize:38,letterSpacing:1.3,lineHeight:1.35,color:INK}}>{caption.text}</div>}
  </AbsoluteFill>;
};
