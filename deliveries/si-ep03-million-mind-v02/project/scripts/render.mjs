import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {openBrowser,selectComposition,renderStill,renderMedia} from '@remotion/renderer';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const work=path.dirname(root),manifest=JSON.parse(fs.readFileSync(path.join(work,'delivery.json')));
const [mode='stills',layout='landscape',...args]=process.argv.slice(2);
const portrait=layout==='portrait',id=portrait?'PortraitVertical':'Landscape4K';
const chrome='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
if(mode==='video'){const t=JSON.parse(fs.readFileSync(path.join(root,'audio-timing.json')));if(t.segments?.length!==10||!fs.existsSync(path.join(root,'public/audio/master.wav')))throw Error('Final render requires 10 measured PCM cues and shared master; preview timing cannot be delivered.');}
const serveUrl=await bundle({entryPoint:path.join(root,'src/index.ts'),publicDir:path.join(root,'public'),outDir:path.join(root,'out','bundle'),onProgress:()=>{}});
const browser=await openBrowser('chrome',{browserExecutable:chrome,logLevel:'error'});
try{
 const visualOnly=mode==='stills'||mode==='picture'||(mode==='preview'&&!fs.existsSync(path.join(root,'public/audio/master.wav')));
 const common={serveUrl,browserExecutable:chrome,puppeteerInstance:browser,logLevel:'error',inputProps:{portrait,silent:visualOnly}};
 const composition=await selectComposition({...common,id});
 if(composition.durationInFrames!==7200||composition.fps!==60)throw Error('Timeline mismatch');
 if(mode==='stills'){
  const frames=args.length?args.map(Number):[360,1040,1500,2190,3040,3900,4590,5790,6090,6500,7100];
  for(const frame of frames){await renderStill({...common,composition,frame,output:path.join(work,'review',`source-${layout}-${frame}.png`),imageFormat:'png'});console.log(`still ${id} ${frame}`);}
 }else{
  const preview=mode==='preview',start=Number(args[0]??5700),end=Number(args[1]??6139);
  const outputLocation=mode==='picture'?path.join(work,'review',`picture-${layout}-native4k-SILENT.mp4`):preview?path.join(work,'review',`motion-${visualOnly?'SILENT-':''}${layout}-${start}-${end}.mp4`):path.join(work,manifest.outputs[portrait?'xiaohongshu':'bilibili'].path);
  let previous=-1;
  await renderMedia({...common,composition,outputLocation,frameRange:preview?[start,end]:undefined,scale:preview?(portrait?1/3:1/3):1,codec:'h264',audioCodec:'aac',audioBitrate:'320k',sampleRate:48000,pixelFormat:'yuv420p',colorSpace:'bt709',crf:17,x264Preset:'fast',imageFormat:'jpeg',jpegQuality:95,concurrency:2,metadata:{title:'百万分身｜THE MILLION-FOLD MIND · EP.03 v02',comment:'120.00s 60fps native dual composition. Procedural science-fiction visualization; narrative parameters are fictional. Shared 48kHz PCM master. Bailian CosyVoice v3 Flash longtian_v3.'},onProgress:({progress,renderedFrames,renderEstimatedTime})=>{const p=Math.floor(progress*100);if(p!==previous){previous=p;console.log(`${id} ${p}% frames=${renderedFrames} eta=${Math.round(renderEstimatedTime/1000)}s`);}}});
  console.log(outputLocation);
 }
}finally{await browser.close({silent:true});}
