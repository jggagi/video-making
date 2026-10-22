import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {bundle} from '@remotion/bundler';
import {openBrowser,selectComposition,renderStill,renderMedia} from '@remotion/renderer';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),work=path.dirname(root);
const [mode='stills',...args]=process.argv.slice(2);
const chrome='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const hashFile=async p=>{const h=createHash('sha256');for await(const b of fs.createReadStream(p))h.update(b);return h.digest('hex');};
if(process.platform==='darwin'&&!process.env.TMPDIR?.startsWith('/Volumes/AgentDev/'))throw Error('Run through agent-dev after volume preflight');
if(['video','preview'].includes(mode)&&!fs.existsSync(path.join(root,'public/audio/master.wav')))throw Error('A verified real master is required');
if(mode==='video'){
 const t=JSON.parse(fs.readFileSync(path.join(root,'audio-timing.json')));
 if(t.segments.length!==8||t.status==='PREVIEW_ONLY')throw Error('Measured narration required');
}
const temp=fs.mkdtempSync(path.join(process.env.TMPDIR??os.tmpdir(),'si-ep13-bundle-'));
const serveUrl=await bundle({entryPoint:path.join(root,'src/index.ts'),publicDir:path.join(root,'public'),outDir:temp,onProgress:()=>{}});
const browser=await openBrowser('chrome',{browserExecutable:chrome,logLevel:'error'});
try{
 const props={silent:mode!=='preview',cover:false};
 const common={serveUrl,browserExecutable:chrome,puppeteerInstance:browser,logLevel:'error',inputProps:props};
 const composition=await selectComposition({...common,id:'PortraitVertical'});
 if(composition.width!==2160||composition.height!==3840||composition.fps!==60||composition.durationInFrames!==5400)throw Error('Native specs mismatch');
 if(mode==='stills'||mode==='covers'||mode==='headlines'){
  const frames=mode==='headlines'?[]:mode==='covers'?[1680,4020]:(args.length?args.map(Number):[60,900,1500,2280,2940,3480,3900,4020,4500,4859,4860,5040,5160,5399]);
  for(const frame of frames){
   const name=mode==='covers'?(frame===1680?'cover-A.png':'cover-B.png'):`source-${frame}.png`;
   const folder=mode==='covers'?'小红书':'review';
   await renderStill({...common,composition,frame,output:path.join(work,folder,name),imageFormat:'png'});console.log(`still ${frame} ${name}`);
  }
  if(mode==='covers'||mode==='headlines')for(const [kind,frame] of [['A',1680],['B',4020]]){const coverProps={silent:true,cover:kind};const coverComposition=await selectComposition({...common,inputProps:coverProps,id:'PortraitVertical'});await renderStill({...common,inputProps:coverProps,composition:coverComposition,frame,output:path.join(work,'小红书',`cover-${kind}-headline.png`),imageFormat:'png'});console.log(`headline ${kind}`);}
 }else{
  const preview=mode==='preview',start=Number(args[0]??120),end=Number(args[1]??299);
  const pointer=path.join(work,'review','render-staging.json');
  if(!preview&&fs.existsSync(pointer))throw Error('Staging pointer already exists; preserve native evidence');
  const stage=preview?null:fs.mkdtempSync(path.join(process.env.TMPDIR??os.tmpdir(),'si-ep13-native-'));
  const outputLocation=preview?path.join(work,'review',`motion-${start}-${end}.mp4`):path.join(stage,'video-only.mp4');
  if(fs.existsSync(outputLocation))throw Error('Refusing overwrite');
  let last=-5;
  await renderMedia({...common,composition,outputLocation,frameRange:preview?[start,end]:undefined,scale:1,muted:!preview,codec:'h264',audioCodec:'aac',audioBitrate:'320k',sampleRate:48000,pixelFormat:'yuv420p',colorSpace:'bt709',crf:18,x264Preset:'fast',imageFormat:'png',concurrency:2,metadata:{title:'无法遗忘的诅咒 / WHEN FORGETTING BECOMES ILLEGAL',comment:'Science-fiction thought experiment. Pure 2D amber CRT oscilloscope. Fictional telemetry and zero-loss traumatic memory. Native portrait2160x3840/60fps/5400frames/90seconds.'},onProgress:({progress,renderedFrames,renderEstimatedTime})=>{const pct=Math.floor(progress*100);if(pct>=last+2){last=pct;console.log(`${mode} ${pct}% frames=${renderedFrames} eta=${Math.round(renderEstimatedTime/1000)}s`);}}});
  console.log(outputLocation);
  if(!preview)fs.writeFileSync(pointer,JSON.stringify({status:'READY',file:outputLocation,sha256:await hashFile(outputLocation),bytes:fs.statSync(outputLocation).size,capture:{remotion:'4.0.534',chrome,imageFormat:'png',concurrency:2,nativeWidth:2160,nativeHeight:3840},scope:'Owned rebuildable native video track on verified AgentDev scratch; formal outputs remain in repository'},null,2)+'\n',{flag:'wx'});
 }
}finally{await browser.close({silent:true});fs.rmSync(temp,{recursive:true,force:true});}
