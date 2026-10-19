import React from 'react';
import {ThreeCanvas} from '@remotion/three';
import {AbsoluteFill,Audio,staticFile,useCurrentFrame,useVideoConfig} from 'remotion';
import {CameraAim,StudioEnvironment} from './Stage';
import {Choice,Coffee,Crystal} from './Objects';
import timing from '../audio-timing.json';

type Props={scene:'coffee'|'choice'|'crystal';still:boolean};
const copy={
  coffee:{index:'01',eyebrow:'THE PRE-ECHO',title:<>影子，<br/>先于念头。</>,detail:'一个尚未发生的动作，\n已经在桌面留下了回声。',qualifier:'影子为思想实验 · 准备电位不等于单次读心'},
  choice:{index:'03',eyebrow:'THE GENTLE NUDGE',title:<>选择还在。<br/>地形变了。</>,detail:'十条路仍然可见。\n倾斜，悄悄改变了它们的代价。',qualifier:'势场与偏好推断为玩具模型 · 高度经单调压缩以便观看'},
  crystal:{index:'04',eyebrow:'THE SOVEREIGN CRYSTAL',title:<>把边界，<br/>交还给你。</>,detail:'记忆留在核心。\n向外，只披露必要的证明。',qualifier:'设计愿景 · 隐私不保证不可预测，随机性不等于自由'},
};

export const VisualProof:React.FC<Props>=({scene,still})=>{
  const frame=useCurrentFrame(),{width,height}=useVideoConfig();
  const f=still?430:frame-180,globalFrame=5460+f,c=copy[scene],scale=width/1920;
  const captions=(timing as {captions:{startFrame:number;endFrame:number;text:string}[]}).captions;
  const caption=captions.find(p=>globalFrame>=p.startFrame&&globalFrame<p.endFrame);
  const camera: [number,number,number]=scene==='coffee'?[0,4.3,6.3]:scene==='choice'?[0,5.2,6.5]:[.18,1.85,7.5];
  // Small, motivated push toward the newly closed boundary.
  if(scene==='crystal'&&!still)camera[2]=8.2-Math.min(frame,500)/500;
  return <AbsoluteFill style={{background:'#0b1017',color:'#e9e7df',fontFamily:'"PingFang SC","Hiragino Sans GB",sans-serif'}}>
    <ThreeCanvas width={width} height={height} dpr={1} shadows camera={{position:camera,fov:scene==='coffee'?34:scene==='choice'?36:35,near:.1,far:200}} gl={{antialias:true,alpha:false,powerPreference:'high-performance'}}>
      <color attach="background" args={['#0b1017']}/><fog attach="fog" args={['#0b1017',13,35]}/>
      <CameraAim target={scene==='coffee'?[0,.4,0]:[0,0,0]}/><StudioEnvironment/>
      {scene==='coffee'?<Coffee/>:scene==='choice'?<Choice/>:<Crystal frame={f}/>}
    </ThreeCanvas>
    <AbsoluteFill style={{background:'linear-gradient(90deg,rgba(8,13,20,.94) 0%,rgba(8,13,20,.82) 22%,rgba(8,13,20,.18) 46%,transparent 62%)',pointerEvents:'none'}}/>
    <div style={{position:'absolute',width:1920,height:1080,transform:`scale(${scale})`,transformOrigin:'top left'}}>
      <div style={{position:'absolute',left:132,top:88,right:132,display:'flex',justifyContent:'space-between',color:'#9ca7aa',fontSize:16,letterSpacing:3}}>
        <span>一眼万年 / EP.06</span><span style={{color:'#b3ad9c',fontFamily:'Menlo,monospace',fontSize:13,letterSpacing:2}}>V02 · VISUAL STUDY / {c.index}</span>
      </div>
      <div style={{position:'absolute',left:132,top:248,width:610}}>
        <div style={{width:42,height:2,background:'#b4945d',marginBottom:29}}/>
        <div style={{fontFamily:'Menlo,monospace',fontSize:13,letterSpacing:4,color:'#bbaa8b',marginBottom:29}}>{c.eyebrow}</div>
        <div style={{fontFamily:'"Songti SC","STSong",serif',fontWeight:400,fontSize:82,lineHeight:1.27,letterSpacing:3,textShadow:'0 2px 24px #0a1018'}}>{c.title}</div>
        <div style={{marginTop:32,width:385,height:1,background:'linear-gradient(90deg,#495057,transparent)'}}/>
        <div style={{marginTop:28,fontSize:22,lineHeight:1.9,letterSpacing:1,color:'#a9b0b0',whiteSpace:'pre-line'}}>{c.detail}</div>
      </div>
      <div style={{position:'absolute',left:132,bottom:65,right:132,display:'flex',justifyContent:'space-between',alignItems:'center',fontSize:15,letterSpacing:1,color:'#8c999e'}}>
        <span>{c.qualifier}</span><span style={{fontFamily:'Menlo,monospace',fontSize:12,color:'#a19172'}}>{scene==='crystal'?(f>=300?'LOCAL / SEALED':'LOCAL / SEALING'):'SCHEMATIC / NOT TELEMETRY'}</span>
      </div>
      {!still&&caption&&<div style={{position:'absolute',left:360,top:907,width:1200,textAlign:'center',fontSize:32,lineHeight:1.45,whiteSpace:'pre-line',fontWeight:500,textShadow:'0 2px 12px #000'}}>{caption.text}</div>}
    </div>
    {!still&&<Audio src={staticFile('audio/master.wav')} trimBefore={5280} durationInFrames={720}/>}
  </AbsoluteFill>;
};
