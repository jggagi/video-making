import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {bundle} from '@remotion/bundler';
import {openBrowser,selectComposition,renderStill,renderMedia} from '@remotion/renderer';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),work=path.dirname(root);
const manifest=JSON.parse(fs.readFileSync(path.join(work,'delivery.json')));
const [mode='stills',...args]=process.argv.slice(2);
const chrome='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
async function hashFile(file){const hash=createHash('sha256');for await(const chunk of fs.createReadStream(file))hash.update(chunk);return hash.digest('hex');}
if(process.platform==='darwin'&&!process.env.TMPDIR?.startsWith('/Volumes/AgentDev/'))throw Error('Use agent-dev run after volume preflight');
if(!['stills','cover'].includes(mode)&&!fs.existsSync(path.join(root,'public/audio/master.wav')))throw Error('Real narrated master required for moving preview and final');
if(mode==='video'){
 const timing=JSON.parse(fs.readFileSync(path.join(root,'audio-timing.json')));
 if(timing.segments?.length!==8||!timing.captions?.length||JSON.stringify(timing).includes('PREVIEW_ONLY'))throw Error('All 8 measured cues and captions required');
}
const tmp=fs.mkdtempSync(path.join(process.env.TMPDIR??os.tmpdir(),'si-ep10-bundle-'));
const serveUrl=await bundle({entryPoint:path.join(root,'src/index.ts'),publicDir:path.join(root,'public'),outDir:tmp,onProgress:()=>{}});
const browser=await openBrowser('chrome',{browserExecutable:chrome,logLevel:'error'});
try{
 const common={serveUrl,browserExecutable:chrome,puppeteerInstance:browser,logLevel:'error',inputProps:{silent:['stills','cover','video'].includes(mode),cover:mode==='cover'}};
 const composition=await selectComposition({...common,id:'PortraitVertical'});
 if(composition.durationInFrames!==5400||composition.fps!==60||composition.width!==2160||composition.height!==3840)throw Error('Composition mismatch');
 if(mode==='cover'){
  await renderStill({...common,composition,frame:3720,output:path.join(work,'小红书','cover.png'),imageFormat:'png'});console.log('cover 62seconds');
 }else if(mode==='stills'){
  for(const frame of(args.length?args.map(Number):[60,600,960,1500,2300,2900,3480,3720,3900,4500,4859,4860,4861,4890,4900,5100,5399])){
   await renderStill({...common,composition,frame,output:path.join(work,'review',`source-${frame}.png`),imageFormat:'png'});console.log(`still ${frame}`);
  }
 }else{
  const preview=mode==='preview',start=Number(args[0]??120),end=Number(args[1]??299);
  const stagingPointer=path.join(work,'review','render-staging.json');
  if(!preview&&fs.existsSync(stagingPointer))throw Error('Refusing to replace native staging evidence');
  const nativeStage=preview?null:fs.mkdtempSync(path.join(process.env.TMPDIR??os.tmpdir(),'si-ep10-v2-native-'));
  const outputLocation=preview?path.join(work,'review',`motion-${start}-${end}.mp4`):path.join(nativeStage,'video-only.mp4');
  if(fs.existsSync(outputLocation))throw Error('Refusing to overwrite existing render');
  let previous=-5;
  await renderMedia({...common,composition,outputLocation,frameRange:preview?[start,end]:undefined,scale:1,muted:!preview,codec:'h264',audioCodec:'aac',audioBitrate:'320k',sampleRate:48000,pixelFormat:'yuv420p',colorSpace:'bt709',crf:18,x264Preset:'fast',imageFormat:'png',concurrency:1,metadata:{title:manifest.title,comment:'Future SI thought experiment. All biometrics, dopamine percentages and timing values are fictional. Native portrait 4K; 90 seconds; 5400 frames at 60fps. Visual v2; unchanged v1 audio.'},onProgress:({progress,renderedFrames,renderEstimatedTime})=>{const p=Math.floor(progress*100);if(p>=previous+5){previous=p;console.log(`${mode} ${p}% frames=${renderedFrames} eta=${Math.round(renderEstimatedTime/1000)}s`);}}});
  console.log(outputLocation);
  if(!preview)fs.writeFileSync(stagingPointer,JSON.stringify({status:'READY',file:outputLocation,sha256:await hashFile(outputLocation),bytes:fs.statSync(outputLocation).size,scope:'Owned rebuildable native video track in verified AgentDev scratch; formal source and final movies stay in repository.'},null,2)+'\n',{flag:'wx'});
 }
}finally{await browser.close({silent:true});fs.rmSync(tmp,{recursive:true,force:true});}
