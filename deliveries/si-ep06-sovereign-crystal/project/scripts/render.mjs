import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {openBrowser,selectComposition,renderStill,renderMedia} from '@remotion/renderer';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const work=path.dirname(root),manifest=JSON.parse(fs.readFileSync(path.join(work,'delivery.json')));
const [mode='stills',layout='landscape',...args]=process.argv.slice(2);
const portrait=layout==='portrait',id=portrait?'PortraitVertical':'Landscape4K';
const chrome='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
if(mode==='video'){
 const t=JSON.parse(fs.readFileSync(path.join(root,'audio-timing.json')));
 if(t.segments?.length!==10||!t.captions?.length||!fs.existsSync(path.join(root,'public/audio/master.wav'))||JSON.stringify(t).includes('preview_estimate_pending_pcm'))throw Error('Final render requires all 10 measured PCM cues, measured-window captions and shared master.');
}
if(process.platform==='darwin'&&fs.existsSync('/Users/guoq/Developer/agent-workstation')&&!process.env.TMPDIR?.startsWith('/Volumes/AgentDev/'))throw Error('On Q’s Mac, run rendering through agent-dev run after volume preflight.');
const bundleDir=fs.mkdtempSync(path.join(process.env.TMPDIR??os.tmpdir(),'si-ep06-bundle-'));
const serveUrl=await bundle({entryPoint:path.join(root,'src/index.ts'),publicDir:path.join(root,'public'),outDir:bundleDir,onProgress:()=>{}});
const browser=await openBrowser('chrome',{browserExecutable:chrome,logLevel:'error'});
try{
 const visualOnly=mode==='stills'||!fs.existsSync(path.join(root,'public/audio/master.wav'));
 const common={serveUrl,browserExecutable:chrome,puppeteerInstance:browser,logLevel:'error',inputProps:{portrait,silent:visualOnly}};
 const composition=await selectComposition({...common,id});
 if(composition.durationInFrames!==7200||composition.fps!==60)throw Error('Timeline mismatch');
 if(mode==='stills'){
  for(const frame of (args.length?args.map(Number):[360,960,1500,2190,3120,3900,4800,5759,5760,5790,6500,7100,7199])){
   await renderStill({...common,composition,frame,output:path.join(work,'review',`source-${layout}-${frame}.png`),imageFormat:'png'});
   console.log(`still ${id} ${frame}`);
  }
 }else if(mode==='review'){
  for(const [start,end] of [[900,1079],[2160,2339],[4740,4919],[5700,5879],[6360,6539],[6960,7139]]){
   await renderMedia({...common,composition,outputLocation:path.join(work,'review',`motion-${layout}-${start}-${end}.mp4`),frameRange:[start,end],scale:1/3,codec:'h264',audioCodec:'aac',audioBitrate:'320k',sampleRate:48000,pixelFormat:'yuv420p',colorSpace:'bt709',crf:18,x264Preset:'veryfast',imageFormat:'jpeg',jpegQuality:92,concurrency:2});
   console.log(`review ${id} ${start}-${end}`);
  }
 }else{
  const preview=mode==='preview',start=Number(args[0]??900),end=Number(args[1]??1079);
  const outputLocation=preview?path.join(work,'review',`motion-${layout}-${start}-${end}.mp4`):path.join(work,manifest.outputs[portrait?'xiaohongshu':'bilibili'].path);
  let previous=-1;
  await renderMedia({...common,composition,outputLocation,frameRange:preview?[start,end]:undefined,scale:preview?1/3:1,codec:'h264',audioCodec:'aac',audioBitrate:'320k',sampleRate:48000,pixelFormat:'yuv420p',colorSpace:'bt709',crf:17,x264Preset:'fast',imageFormat:'jpeg',jpegQuality:94,concurrency:2,metadata:{title:manifest.title,comment:'Scientific thought experiment, synthetic Lorenz dynamics and local privacy boundary; no empirical mind-reading claims. Shared 120.00s / 48kHz stereo PCM. 7200 frames, 60fps.'},onProgress:({progress,renderedFrames,renderEstimatedTime})=>{const p=Math.floor(progress*100);if(p!==previous){previous=p;console.log(`${id} ${p}% frames=${renderedFrames} eta=${Math.round(renderEstimatedTime/1000)}s`);}}});
  console.log(outputLocation);
 }
}finally{await browser.close({silent:true});fs.rmSync(bundleDir,{recursive:true,force:true});}
