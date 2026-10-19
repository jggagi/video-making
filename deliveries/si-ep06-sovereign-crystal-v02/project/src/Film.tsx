import React from 'react';
import {AbsoluteFill, Audio, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {ThreeCanvas} from '@remotion/three';
import {CameraAim, StudioEnvironment} from './Stage';
import {Crystal} from './Objects';
import {CoffeeScene, ChoiceScene} from './HumanScenes';
import {MirrorScene} from './MirrorScene';
import {syntheticTrajectoryResidualPercent} from './math';
import timing from '../audio-timing.json';

const clamp=(n:number)=>Math.max(0,Math.min(1,n));
const fade=(f:number,a:number,b:number,r=35)=>clamp((f-a)/r)*clamp((b-f)/r);
const chapters=[
  {id:'01',en:'THE PRE-ECHO',title:['影子，','先于念头。'],detail:'一个尚未发生的动作，\n已经在桌面留下了回声。',qualifier:'平均RP示意 · 影子为思想实验，非单次读心'},
  {id:'02',en:'THE GLASS BOX',title:['透明的','镜像。'],detail:'行为留下碎片。\n模拟重构出它们的轨迹。',qualifier:'Lorenz合成系统 · 轨迹误差≠自由意志，非人格重建'},
  {id:'03',en:'THE GENTLE NUDGE',title:['选择还在。','地形变了。'],detail:'十条路仍然可见。\n倾斜，悄悄改变了它们的代价。',qualifier:'势场与偏好推断为玩具模型 · 非多巴胺实测'},
  {id:'04',en:'THE SOVEREIGN CRYSTAL',title:['把边界，','交还给你。'],detail:'记忆留在核心。\n向外，只披露必要的证明。',qualifier:'设计愿景 · 隐私不保证不可预测，随机性不等于自由'},
];
const episodes=['01 一眼万年','02 7±2的囚笼','03 百万分身','04 神也会自我欺骗','05 兰道尔极限','06 主权心印'];
const boundaries=[1260,1800,3600,5400,6900];

const Finale:React.FC<{frame:number;portrait:boolean}>=({frame,portrait})=><group position={[1.05,portrait?-.85:.05,0]} scale={portrait?.54:1}>
  {Array.from({length:6},(_,i)=><group key={i} rotation={[.45+Math.sin(frame/280+i)*.12,frame/600+i*.22,i*.19]}>
    <mesh><torusGeometry args={[.8+i*.32,.014,10,160]}/><meshStandardMaterial color={i===5?'#e4c685':'#9c855c'} metalness={.8} roughness={.24} emissive="#b68c45" emissiveIntensity={.08}/></mesh>
  </group>)}
  <mesh rotation={[frame/420,frame/340,0]}><icosahedronGeometry args={[.37,0]}/><meshPhysicalMaterial color="#d2ac61" metalness={.65} roughness={.18} clearcoat={1}/></mesh>
</group>;

export const Film:React.FC<{portrait?:boolean;silent?:boolean}>=({portrait=false,silent=false})=>{
  const f=useCurrentFrame(),{width,height}=useVideoConfig();
  const w=portrait?1080:1920,h=portrait?1920:1080,scale=width/w;
  const act=Math.min(3,Math.floor(f/1800)),local=f-act*1800,c=chapters[act];
  const titleCard=f>=1260&&f<1800,finale=f>=6900;
  const caption=(timing.captions as {startFrame:number;endFrame:number;text:string}[]).find(p=>f>=p.startFrame&&f<p.endFrame);
  let camera:[number,number,number],target:[number,number,number]=[0,0,0];
  if(portrait){
    camera=act===0&&!titleCard?[.12,7.4,11.2-f/7200]:act===2?[0,10.8,12.7]:[.12,3.7,16.3];
    if(act===3&&!finale)camera=[.12,3.4,16.3-Math.min(Math.max(f-5400,0),600)/600*3.2];
    if(finale)camera=[.12,4,14+(f-6900)/300*.8];
  }else{
    camera=act===0&&!titleCard?[Math.sin(f/800)*.18,4.3,6.55-f/7200]:act===1?[.1+Math.sin(local/700)*.2,2.4,8.2-local/3600]:act===2?[.1,5.2,6.7-local/6000]:[.18,1.85,8.2-Math.min(Math.max(f-5460,0),500)/500];
    if(titleCard)camera=[.2,2.2,8.7+(f-1260)/540*.5];
    if(finale)camera=[.2,1.7,8.7+(f-6900)/300*1.2];
    if(act===0&&!titleCard)target=[0,.4,0];
  }
  const actorScale=portrait?(act===0&&!titleCard?.9:act===1?1:.82):1;
  const actorY=portrait?(act===1?.7:act===2?.9:.5):0;
  const fieldOfView=portrait?38:act===0&&!titleCard?34:act===2?36:35;
  const darkDip=Math.max(Math.max(...boundaries.map(b=>clamp(1-Math.abs(f-b)/12)))*.5,clamp((f-7160)/40));
  const chapterTitleOpacity=titleCard||finale?0:act===3?fade(f,5400,6000,35):fade(local,-35,520,35);
  const titleTop=portrait?290:248;
  const poem=f>=6020&&f<6900;
  return <AbsoluteFill style={{background:'#0b1017',color:'#e9e7df',fontFamily:'"PingFang SC","Hiragino Sans GB",sans-serif'}}>
    <ThreeCanvas width={width} height={height} dpr={1} shadows camera={{position:camera,fov:fieldOfView,near:.1,far:200}} gl={{antialias:true,alpha:false,powerPreference:'high-performance'}}>
      <color attach="background" args={['#0b1017']}/><fog attach="fog" args={['#0b1017',portrait?24:13,portrait?50:35]}/>
      <CameraAim target={target} position={camera} fov={fieldOfView}/><StudioEnvironment/>
      <group position={portrait?[-.25,actorY,0]:[0,0,0]} scale={actorScale}>
        <group position={portrait?[-1.1,0,0]:[0,0,0]}>
          {finale?<Finale frame={f-6900} portrait={portrait}/>:titleCard?<Crystal frame={430+(f-1260)/5}/>:act===0?<CoffeeScene frame={f}/>:act===1?<MirrorScene frame={local}/>:act===2?<ChoiceScene frame={local}/>:<Crystal frame={f-5460}/>}
        </group>
      </group>
    </ThreeCanvas>
    <AbsoluteFill style={{background:portrait?'linear-gradient(180deg,rgba(8,13,20,.68),transparent 36%,transparent 62%,rgba(8,13,20,.85) 79%)':'linear-gradient(180deg,transparent 65%,rgba(8,13,20,.68) 87%,rgba(8,13,20,.88)),linear-gradient(90deg,rgba(8,13,20,.94),rgba(8,13,20,.8) 22%,rgba(8,13,20,.12) 47%,transparent 63%)',pointerEvents:'none'}}/>
    <div style={{position:'absolute',width:w,height:h,transform:`scale(${scale})`,transformOrigin:'top left'}}>
      <div style={{position:'absolute',left:portrait?64:132,top:portrait?178:88,right:portrait?178:132,display:'flex',justifyContent:'space-between',fontSize:portrait?30:16,letterSpacing:portrait?2:3,color:'#9ca7aa'}}>
        <span>一眼万年 / EP.06</span><span style={{color:'#b3ad9c',fontFamily:'Menlo,monospace',fontSize:portrait?30:13}}>{c.id} / 04</span>
      </div>
      <div style={{position:'absolute',left:portrait?64:132,top:titleTop,width:portrait?838:610,opacity:chapterTitleOpacity}}>
        {!portrait&&<div style={{width:42,height:2,background:'#b4945d',marginBottom:29}}/>}
        <div style={{fontFamily:'Menlo,monospace',fontSize:portrait?27:13,letterSpacing:portrait?3:4,color:'#bbaa8b',marginBottom:portrait?18:29}}>{c.en}</div>
        <div style={{fontFamily:'"Songti SC","STSong",serif',fontWeight:400,fontSize:portrait?72:82,lineHeight:1.27,letterSpacing:3,textShadow:'0 2px 24px #0a1018'}}>{c.title[0]}<br/>{c.title[1]}</div>
        {!portrait&&<><div style={{marginTop:32,width:385,height:1,background:'linear-gradient(90deg,#495057,transparent)'}}/><div style={{marginTop:28,fontSize:22,lineHeight:1.9,letterSpacing:1,color:'#a9b0b0',whiteSpace:'pre-line'}}>{c.detail}</div></>}
      </div>
      {f>=660&&f<1260&&<div style={{position:'absolute',left:portrait?64:132,top:portrait?294:325,width:portrait?838:555,opacity:fade(f,660,1260),color:'#e2d0a8'}}>
        <div style={{fontSize:portrait?34:21,letterSpacing:2,marginBottom:portrait?12:20}}>平均准备电位 / 示意</div>
        <div style={{fontFamily:'"Songti SC",serif',fontSize:portrait?64:76,lineHeight:portrait?1.1:1.4}}>−550 ms</div>
        <div style={{fontSize:portrait?34:25,lineHeight:portrait?1.45:1.7,color:'#aab5b5'}}>{portrait?'主观报告 −200 ms · 动作 0 ms':<>主观报告 −200 ms<br/>动作 0 ms</>}</div>
      </div>}
      {titleCard&&<div style={{position:'absolute',left:portrait?64:132,top:portrait?295:330,width:portrait?838:1100,opacity:fade(f,1260,1800,40)}}>
        <div style={{fontFamily:'"Songti SC",serif',fontSize:portrait?100:123,letterSpacing:portrait?6:12,color:'#e6ddc7'}}>主权心印</div>
        <div style={{fontFamily:'Menlo,monospace',fontSize:portrait?30:21,letterSpacing:portrait?3:5,color:'#b8bbae',marginTop:26}}>THE SOVEREIGN SOUL CRYSTAL</div>
        <div style={{fontSize:portrait?42:30,color:'#b7a27e',marginTop:32}}>当算法比你更懂你</div>
      </div>}
      {f>=2700&&f<3480&&<div style={{position:'absolute',left:portrait?64:132,top:portrait?292:330,width:portrait?838:580,opacity:fade(f,2700,3480),color:'#d9bd84'}}>
        <div style={{fontFamily:'"Songti SC",serif',fontSize:portrait?77:83}}>{syntheticTrajectoryResidualPercent(f).toFixed(f>=3040?3:1)}%</div>
        <div style={{fontSize:portrait?39:24,lineHeight:1.7,color:'#aab5b5'}}>合成轨迹误差<br/>不是自由意志的刻度</div>
      </div>}
      {poem&&<div style={{position:'absolute',left:portrait?64:132,top:portrait?310:330,width:portrait?838:620,opacity:fade(f,6020,6900,35)}}>
        <div style={{fontFamily:'"Songti SC",serif',fontSize:portrait?64:65,lineHeight:1.4,color:'#e6ddc7'}}>把记忆锁进<br/>私密的圣殿</div>
        <div style={{fontSize:portrait?39:23,lineHeight:1.7,marginTop:26,color:'#b6a482'}}>“百分之一”是诗意表达，<br/>不是测量值。</div>
      </div>}
      {finale&&<div style={{position:'absolute',left:portrait?64:132,top:portrait?292:275,width:portrait?838:750,opacity:fade(f,6900,7240,25)}}>
        <div style={{fontFamily:'"Songti SC",serif',fontSize:portrait?71:78,lineHeight:1.3,color:'#e5dcc5'}}>一眼万年<br/>· 第一季终</div>
        <div style={{fontFamily:'Menlo,monospace',fontSize:portrait?27:15,lineHeight:1.5,letterSpacing:3,color:'#ad9d7c',marginTop:20}}>THE SILICON OBSERVER<br/>SEASON 01 COMPLETE</div>
        <div style={{display:'grid',gridTemplateColumns:portrait?'1fr 1fr':'1fr 1fr',gap:portrait?'18px 16px':'16px 32px',fontSize:portrait?39:22,color:'#a4afae',marginTop:portrait?20:40}}>{episodes.map((e,i)=><span key={e} style={{color:i===5?'#d6b879':undefined}}>{e}</span>)}</div>
      </div>}
      <div style={{position:'absolute',left:portrait?64:132,top:portrait?(act===0?1320:1242):1008,width:portrait?838:1656,fontSize:portrait?39:15,lineHeight:portrait?1.22:1.5,letterSpacing:portrait?0:1,color:'#8e9ca1',textAlign:portrait?'center':'left',textShadow:'0 2px 8px #0b1017'}}>{c.qualifier}</div>
      {caption&&<div style={{position:'absolute',left:portrait?64:300,top:portrait?1383:907,width:portrait?838:1320,height:portrait?112:110,fontSize:portrait?43:38,lineHeight:portrait?1.22:1.45,whiteSpace:'pre-line',textAlign:'center',fontWeight:500,textShadow:'0 2px 12px #000,0 0 28px #0b1017'}}>{caption.text}</div>}
    </div>
    {darkDip>0&&<AbsoluteFill style={{background:'#0b1017',opacity:darkDip,pointerEvents:'none'}}/>}
    {!silent&&<Audio src={staticFile('audio/master.wav')}/>}
  </AbsoluteFill>;
};
