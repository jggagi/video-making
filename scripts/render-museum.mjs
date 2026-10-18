import fs from 'node:fs';
import path from 'node:path';
import {bundle} from '@remotion/bundler';
import {openBrowser,selectComposition,renderStill,renderMedia} from '@remotion/renderer';

const mode=process.argv[2] ?? 'video';
const is4k=mode==='4k';
const output=path.resolve('out/museum');
fs.mkdirSync(output,{recursive:true});
const browserExecutable=process.env.REMOTION_BROWSER_EXECUTABLE ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const serveUrl=await bundle({entryPoint:path.resolve('src/index.ts'),outDir:path.join(output,'bundle'),onProgress:()=>{}});
const browser=await openBrowser('chrome',{browserExecutable,logLevel:'error'});
try {
  const composition=await selectComposition({serveUrl,id:is4k?'LantingMuseum4K':'LantingMuseum',browserExecutable,puppeteerInstance:browser,logLevel:'error'});
  if (mode==='stills' || mode==='frame') {
    const timeline=JSON.parse(fs.readFileSync('src/museum/timeline.json','utf8'));
    const picks=mode==='frame' ? [['frame',Number(process.argv[3])]] : [
      ['title-writing',90],['title',300],['grove',timeline.shots.find(s=>s.id==='grove').from+155],
      ['water-a',timeline.shots.find(s=>s.id==='water').from+40],['water-b',timeline.shots.find(s=>s.id==='water').from+95],
      ['cups-a',timeline.shots.find(s=>s.id==='cups').from+24],['cups-b',timeline.shots.find(s=>s.id==='cups').from+103],
      ['poems',timeline.shots.find(s=>s.id==='poems').from+159],['breeze',timeline.shots.find(s=>s.id==='breeze').from+95],
      ['traces-before',timeline.shots.find(s=>s.id==='traces').from+32],['traces-after',timeline.shots.find(s=>s.id==='traces').from+169],
      ['mortality',timeline.shots.find(s=>s.id==='mortality').from+97],['judgment',timeline.shots.find(s=>s.id==='judgment').from+99],
      ['record',timeline.shots.find(s=>s.id==='record').from+203],['future',timeline.shots.find(s=>s.id==='future').from+85],['end',timeline.shots.find(s=>s.id==='end').from+110],
    ];
    for (const [name,frame] of picks) {
      await renderStill({serveUrl,composition,output:path.join(output,`still-${name}.png`),frame,browserExecutable,puppeteerInstance:browser,imageFormat:'png',logLevel:'error'});
      console.log(`${name}: ${frame}`);
    }
  } else {
    let last=-1;
    const sample=mode==='sample';
    await renderMedia({serveUrl,composition,outputLocation:path.join(output,sample?'motion-sample.mp4':`兰亭集序-博物馆版-${is4k?'4K':'1080p'}.mp4`),
      codec:'h264',audioCodec:'aac',audioBitrate:'192k',pixelFormat:'yuv420p',crf:is4k?17:18,concurrency:is4k?1:2,
      ...(sample ? {frameRange:[785,1430]} : {}),browserExecutable,puppeteerInstance:browser,logLevel:'error',
      metadata:{title:'兰亭集序 · 博物馆版',artist:'原文：王羲之',comment:'原文全文 · 水墨意象动画 · 字形书写非历史真迹'},
      onProgress:({progress})=>{const p=Math.floor(progress*20)*5;if(p!==last){console.log(`Rendering ${p}%`);last=p;}},
    });
  }
} finally {await browser.close({silent:true});}
