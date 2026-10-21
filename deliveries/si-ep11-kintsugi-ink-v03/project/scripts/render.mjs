import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {openBrowser,selectComposition,renderStill,renderMedia,makeCancelSignal} from '@remotion/renderer';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const work=path.dirname(root);
const manifest=JSON.parse(fs.readFileSync(path.join(work,'delivery.json')));
const [mode='stills',...args]=process.argv.slice(2);
const chrome='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const canyonVideo=path.join(root,'public','video','canyon-v03.mp4');
if(!fs.existsSync(canyonVideo))throw Error('Required Blender canyon video is pending: public/video/canyon-v03.mp4');
if(process.platform==='darwin'&&!process.env.TMPDIR?.startsWith('/Volumes/AgentDev/'))throw Error('Run through agent-dev after fresh volume verification');
const silent=['stills','cover','silent-preview'].includes(mode);
if(!silent&&!fs.existsSync(path.join(root,'public/audio/master.wav')))throw Error('A real narrated PCM master is required');
if(mode==='video'){
 const timing=JSON.parse(fs.readFileSync(path.join(root,'audio-timing.json')));
 if(timing.segments?.length!==8||!timing.captions?.length||JSON.stringify(timing).includes('PREVIEW_ONLY'))throw Error('Final requires all eight measured narration cues and captions');
}
const tmp=fs.mkdtempSync(path.join(process.env.TMPDIR??os.tmpdir(),'ep11-v03-bundle-'));
const chromiumOptions={gl:'angle'};
let browser;
const {cancel,cancelSignal}=makeCancelSignal();
const stop=()=>cancel();
process.once('SIGINT',stop);process.once('SIGTERM',stop);
try{
 const serveUrl=await bundle({entryPoint:path.join(root,'src/index.ts'),publicDir:path.join(root,'public'),outDir:tmp,onProgress:()=>{}});
 browser=await openBrowser('chrome',{browserExecutable:chrome,chromiumOptions,logLevel:'warn'});
 const common={serveUrl,browserExecutable:chrome,puppeteerInstance:browser,chromiumOptions,logLevel:'warn',inputProps:{silent,cover:mode==='cover'}};
 const composition=await selectComposition({...common,id:'PortraitVertical'});
 if(composition.width!==2160||composition.height!==3840||composition.fps!==60||composition.durationInFrames!==5400)throw Error('Native 4K composition mismatch');
 if(mode==='stills'||mode==='cover'){
  const frames=mode==='cover'?[5100]:(args.length?args.map(Number):[180,480,720,1200,1680,2400,2940,3150,3540,3900,4320,4800,4890,5100,5399]);
  for(const frame of frames){
   const output=mode==='cover'?path.join(work,'小红书','cover-source.png'):path.join(work,'review',`source-${frame}.png`);
   await renderStill({...common,composition,frame,output,imageFormat:'png'});
   console.log(`STILL ${frame} ${output}`);
  }
 }else{
  const preview=['preview','silent-preview'].includes(mode),start=Number(args[0]??2940),end=Number(args[1]??3839);
  const outputLocation=preview?path.join(work,'review',`${silent?'silent-':''}motion-${start}-${end}.mp4`):path.join(work,manifest.outputs.xiaohongshu.path);
  if(fs.existsSync(outputLocation))throw Error(`Refusing to overwrite ${outputLocation}`);
  let previous=-2;
  await renderMedia({...common,composition,outputLocation,cancelSignal,frameRange:preview?[start,end]:undefined,scale:1,codec:'h264',audioCodec:'aac',audioBitrate:'320k',sampleRate:48000,pixelFormat:'yuv420p',colorSpace:'bt709',crf:16,x264Preset:'slow',imageFormat:'png',concurrency:1,timeoutInMilliseconds:120000,metadata:{title:manifest.title,comment:'EP11v03. Science-fiction thought experiment; whole-body rejuvenation and immortality remain speculative. Native 2160x3840, 60fps, 90 seconds. Blender-rendered canyon footage, frame-driven Remotion composition, and the preserved local narration master.'},onProgress:({progress,renderedFrames,renderEstimatedTime})=>{const p=Math.floor(progress*100);if(p>=previous+2){previous=p;console.log(`${mode} ${p}% frames=${renderedFrames} eta=${Math.round(renderEstimatedTime/1000)}s`);}}});
  console.log(`OUTPUT ${outputLocation}`);
 }
}finally{
 process.off('SIGINT',stop);process.off('SIGTERM',stop);
 if(browser)await browser.close({silent:true});
 fs.rmSync(tmp,{recursive:true,force:true});
}
