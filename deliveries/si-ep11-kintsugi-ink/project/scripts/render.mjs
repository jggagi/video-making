import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {openBrowser,selectComposition,renderStill,renderMedia} from '@remotion/renderer';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),work=path.dirname(root);
const manifest=JSON.parse(fs.readFileSync(path.join(work,'delivery.json')));
const [mode='stills',...args]=process.argv.slice(2);
const chrome='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
if(process.platform==='darwin'&&!process.env.TMPDIR?.startsWith('/Volumes/AgentDev/'))throw Error('Use agent-dev run after volume preflight');
if(!['stills','cover'].includes(mode)&&!fs.existsSync(path.join(root,'public/audio/master.wav')))throw Error('Real narrated master required for moving preview and final');
if(mode==='video'){
 const timing=JSON.parse(fs.readFileSync(path.join(root,'audio-timing.json')));
 if(timing.segments?.length!==8||!timing.captions?.length||JSON.stringify(timing).includes('PREVIEW_ONLY'))throw Error('All8 measured cues and captions required');
}
const tmp=fs.mkdtempSync(path.join(process.env.TMPDIR??os.tmpdir(),'si-ep11-bundle-'));
const serveUrl=await bundle({entryPoint:path.join(root,'src/index.ts'),publicDir:path.join(root,'public'),outDir:tmp,onProgress:()=>{}});
const browser=await openBrowser('chrome',{browserExecutable:chrome,logLevel:'error'});
try{
 const common={serveUrl,browserExecutable:chrome,puppeteerInstance:browser,logLevel:'error',inputProps:{silent:['stills','cover'].includes(mode),cover:mode==='cover'}};
 const composition=await selectComposition({...common,id:'PortraitVertical'});
 if(composition.durationInFrames!==5400||composition.fps!==60||composition.width!==2160||composition.height!==3840)throw Error('Composition mismatch');
 if(mode==='cover'){
  await renderStill({...common,composition,frame:5040,output:path.join(work,'小红书','cover.png'),imageFormat:'png'});console.log('cover 84seconds');
 }else if(mode==='stills'){
  for(const frame of(args.length?args.map(Number):[60,600,960,1560,2280,2900,3480,3900,4500,4859,4860,4889,4890,5040,5160,5399])){
   await renderStill({...common,composition,frame,output:path.join(work,'review',`source-${frame}.png`),imageFormat:'png'});console.log(`still ${frame}`);
  }
 }else{
  const preview=mode==='preview',start=Number(args[0]??120),end=Number(args[1]??299);
  const outputLocation=preview?path.join(work,'review',`motion-${start}-${end}.mp4`):path.join(work,manifest.outputs.xiaohongshu.path);
  if(fs.existsSync(outputLocation))throw Error('Refusing to overwrite existing render');
  let previous=-5;
  await renderMedia({...common,composition,outputLocation,frameRange:preview?[start,end]:undefined,scale:1,codec:'h264',audioCodec:'aac',audioBitrate:'320k',sampleRate:48000,pixelFormat:'yuv420p',colorSpace:'bt709',crf:18,x264Preset:'fast',imageFormat:'png',concurrency:1,metadata:{title:manifest.title,comment:'Science-fiction thought experiment. Biological age and fracture entropy are illustrative; whole-body rejuvenation and immortality are speculative. Native portrait 4K; 90 seconds; 5400 frames at 60fps.'},onProgress:({progress,renderedFrames,renderEstimatedTime})=>{const p=Math.floor(progress*100);if(p>=previous+5){previous=p;console.log(`${mode} ${p}% frames=${renderedFrames} eta=${Math.round(renderEstimatedTime/1000)}s`);}}});
  console.log(outputLocation);
 }
}finally{await browser.close({silent:true});fs.rmSync(tmp,{recursive:true,force:true});}
