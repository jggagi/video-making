import React from 'react';
import {AbsoluteFill,Audio,staticFile,useCurrentFrame,useVideoConfig} from 'remotion';
import {CanvasWorld} from './CanvasWorld';
import timing from '../audio-timing.json';
import {C} from './draw';
const scenes=[
 {end:1200,n:'01',title:'答案，必须经得起检查',sub:'候选 → 明确规则 → 可复核的反馈',source:'Lean 官方文档｜形式化证明与有限测试的保证不同',color:C.cyan},
 {end:1800,n:'02',title:'现实，反馈没有那么便宜',sub:'能否检验，与能否即时检验，是两回事',source:'Amodei et al., 2016｜昂贵监督与分布变化',color:C.cyan},
 {end:2700,n:'03',title:'评分，成了目标的替身',sub:'易计算的代理指标，代替难取得的结果',source:'Amodei et al., 2016｜奖励投机 / 可扩展监督',color:C.magenta},
 {end:3600,n:'04',title:'它学会得分，却没学会完赛',sub:'赛艇奖励投机：绕圈刷靶标',source:'CoastRunners · OpenAI, 2016｜原理重绘，非原游戏画面',color:C.magenta},
 {end:4500,n:'05',title:'同一次优化，两条曲线',sub:'代理奖励上升，真实任务表现下降',source:'Goodhart 效应｜Gao et al., 2022 · 曲线为教学模型',color:C.magenta},
 {end:5400,n:'06',title:'更多搜索，不等于更多证据',sub:'复制评分漏洞，只会更熟练地绕圈',source:'并行策略示意｜不是“必然自我欺骗”的实验证明',color:C.magenta},
 {end:6300,n:'07',title:'让独立测量，推翻漂亮预测',sub:'胡克定律：同一载荷，伸长量暴露模型误差',source:'F = kx｜弹性范围内 · 参数与读数均为教学示意',color:C.amber},
 {end:6930,n:'08',title:'把反馈，接回现实',sub:'新证据可以纠错；校准仍需不断验证',source:'预测 → 实验 → 误差 → 修正｜不承诺万能验证器',color:C.amber},
 {end:7200,n:'09',title:'下一次观测：兰道尔极限',sub:'EP.05 算力的热力学终局',source:'Bérut et al., Nature 2012｜信息擦除与热耗散',color:C.amber},
];
export const Film:React.FC<{portrait?:boolean;silent?:boolean}>=({portrait=false,silent=false})=>{
 const f=useCurrentFrame(),{width,height}=useVideoConfig(),w=portrait?1080:1920,h=portrait?1920:1080,s=width/w;
 const scene=scenes.find(x=>f<x.end)!;
 const caption=(timing.captions as {startFrame:number;endFrame:number;displayHoldUntilFrame?:number;text:string}[]).find(x=>f>=x.startFrame&&f<(x.displayHoldUntilFrame??x.endFrame));
 return <AbsoluteFill style={{background:C.bg,color:C.ink,fontFamily:'"PingFang SC", "Hiragino Sans GB", sans-serif'}}>
  <CanvasWorld frame={f} portrait={portrait} width={width} height={height}/>
  <div style={{position:'absolute',width:w,height:h,transform:`scale(${s})`,transformOrigin:'top left'}}>
   <div style={{position:'absolute',left:portrait?65:74,top:portrait?174:43,width:portrait?840:1772,color:C.muted,fontFamily:'Menlo,monospace',fontSize:portrait?30:19,letterSpacing:1,display:'flex',justifyContent:'space-between'}}><span>余问 QSTORY / EP.04</span><span style={{color:scene.color}}>v2 · {scene.n}/09</span></div>
   <div style={{position:'absolute',left:portrait?65:74,top:portrait?228:102,width:portrait?840:1772,borderTop:`2px solid ${C.line}`,paddingTop:portrait?13:16,fontSize:portrait?35:27,letterSpacing:2}}><span style={{color:scene.color}}>神也会自我欺骗</span><span style={{fontSize:portrait?30:20,color:C.muted,marginLeft:portrait?25:35}}>机制图解版</span></div>
   <div style={{position:'absolute',left:portrait?65:100,top:portrait?332:208,width:portrait?850:1720,fontSize:portrait?48:43,fontWeight:600,letterSpacing:portrait?0:2,color:scene.color,lineHeight:1.1}}>{scene.title}</div>
   <div style={{position:'absolute',left:portrait?65:100,top:portrait?398:267,width:portrait?850:1720,fontSize:portrait?39:27,color:C.muted,lineHeight:1.1}}>{portrait&&scene.n==='07'?'同一载荷，伸长量暴露参数错误':scene.sub}</div>
   <div style={{position:'absolute',left:portrait?65:100,top:portrait?1309:901,width:portrait?850:1720,fontSize:portrait?29:21,color:'#91a9b9',lineHeight:1.1}}>{scene.source}</div>
   {f>=6300&&f<6930&&<div style={{position:'absolute',left:portrait?85:300,top:portrait?473:322,width:portrait?810:1320,fontSize:portrait?46:43,lineHeight:1.55,textAlign:'center',fontWeight:500}}>{portrait?<>“没有现实校准的超级智能，<br/>不过是一场算力无穷大的疯魔。”</>:<>“没有现实校准的超级智能，<br/>不过是一场算力无穷大的疯魔。”</>}</div>}
   {caption&&<div style={{position:'absolute',left:portrait?63:190,top:portrait?(caption.text.includes('\n')?1346:1380):936,width:portrait?840:1540,textAlign:'center',whiteSpace:'pre-line',fontSize:portrait?43:40,fontWeight:500,lineHeight:1.45,letterSpacing:portrait?1:2,textShadow:'0 2px 8px #000',background:'#050811df',padding:'10px 0',boxSizing:'border-box'}}>{caption.text}</div>}
  </div>
  {!silent&&<Audio src={staticFile('audio/master.wav')}/>}
 </AbsoluteFill>;
};
