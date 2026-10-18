import fs from 'node:fs';
import path from 'node:path';
import {bundle} from '@remotion/bundler';
import {openBrowser,selectComposition,renderStill,renderMedia} from '@remotion/renderer';
const mode=process.argv[2]??'video',is4k=mode==='4k',output=path.resolve(process.env.LANTING_OUTPUT_DIR??'out/extended');
const edition=process.env.LANTING_EDITION??'展厅增强版';
const timeline=JSON.parse(fs.readFileSync('src/extended/timeline.json','utf8'));
const browserExecutable=process.env.REMOTION_BROWSER_EXECUTABLE??'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
fs.mkdirSync(output,{recursive:true});
const serveUrl=await bundle({entryPoint:path.resolve('src/index.ts'),outDir:path.join(output,'bundle'),onProgress:()=>{}});
const browser=await openBrowser('chrome',{browserExecutable,logLevel:'error'});
try{
  const composition=await selectComposition({serveUrl,id:is4k?'LantingExtended4K':'LantingExtended',browserExecutable,puppeteerInstance:browser,logLevel:'error'});
  if(mode==='stills'||mode==='frame'||mode==='time-stills'){
    const time=timeline.shots.find(s=>s.id==='time'),future=timeline.shots.find(s=>s.id==='future');
    const picks=mode==='frame'?[['frame',Number(process.argv[3])]]:mode==='time-stills'?[['ancient',time.from+24],['empty',time.from+70],['modern-emerging',time.from+96],['modern',time.from+137],['future',future.from+100]]:timeline.shots.map(s=>[s.id,s.from+Math.min(s.duration-1,Math.round(s.duration*(s.kind==='title'?.91:.72)))]);
    if(mode==='stills') for(const id of ['grove','joy','life','poems','cups']){const s=timeline.shots.find(s=>s.id===id);picks.push([id+'-early',s.from+Math.round(s.duration*.24)]);}
    if(mode==='stills'){const s=timeline.shots.find(s=>s.id==='joy');picks.push(['spring-detail',s.from+Math.round(s.duration*.44)]);}
    for(const [name,frame] of picks){await renderStill({serveUrl,composition,output:path.join(output,`still-${name}.png`),frame,browserExecutable,puppeteerInstance:browser,imageFormat:'png',logLevel:'error'});console.log(`${name}: ${frame}`);}
  }else{
    const sample=mode==='sample'||mode==='time-sample',time=timeline.shots.find(s=>s.id==='time');
    const start=mode==='time-sample'?time.from-18:timeline.shots.find(s=>s.id==='water').from,end=mode==='time-sample'?time.from+time.duration+17:timeline.shots.find(s=>s.id==='breeze').from-1;
    let last=-1;
    await renderMedia({serveUrl,composition,outputLocation:path.join(output,sample?(mode==='time-sample'?'古今回望-点睛片段.mp4':'motion-sample.mp4'):`兰亭集序-${edition}-${is4k?'4K':'1080p'}.mp4`),codec:'h264',audioCodec:'aac',audioBitrate:'192k',pixelFormat:'yuv420p',crf:is4k?17:18,concurrency:1,...(sample?{frameRange:[start,end]}:{}),browserExecutable,puppeteerInstance:browser,logLevel:'error',metadata:{title:`兰亭集序 · ${edition}`,artist:'原文：王羲之',comment:'原文全文 · 水墨意象动画 · 百炼合成男声 · 字形书写非历史真迹'},onProgress:({progress})=>{const p=Math.floor(progress*20)*5;if(p!==last){console.log(`Rendering ${p}%`);last=p;}}});
  }
}finally{await browser.close({silent:true});}
