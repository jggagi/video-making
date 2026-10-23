import fs from 'node:fs';
import {spawnSync} from 'node:child_process';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {bundle} from '@remotion/bundler';
import {openBrowser,selectComposition,renderStill,renderMedia} from '@remotion/renderer';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),work=path.dirname(root);
const [mode='stills',...args]=process.argv.slice(2);
if(['covers','headlines'].includes(mode))throw Error('Use render_covers.mjs for headline variants; preserve rawcovers extracted from finalMP4');
const chrome='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const hashFile=async p=>{const h=createHash('sha256');for await(const b of fs.createReadStream(p))h.update(b);return h.digest('hex');};
if(process.platform==='darwin'&&!process.env.TMPDIR?.startsWith('/Volumes/AgentDev/'))throw Error('Run through agent-dev after volume preflight');
if(['video','preview'].includes(mode)&&!fs.existsSync(path.join(root,'public/audio/master.wav')))throw Error('A verified real master is required');
if(mode==='video'){
 const t=JSON.parse(fs.readFileSync(path.join(root,'audio-timing.json')));
 if(t.segments.length!==8||t.status==='PREVIEW_ONLY')throw Error('Measured narration required');
}
const temp=fs.mkdtempSync(path.join(process.env.TMPDIR??os.tmpdir(),'si-ep19-bundle-'));
const serveUrl=await bundle({entryPoint:path.join(root,'src/index.ts'),publicDir:path.join(root,'public'),outDir:temp,onProgress:()=>{}});
const browser=await openBrowser('chrome',{browserExecutable:chrome,logLevel:'error'});
try{
 const props={silent:mode!=='preview',cover:false};
 const common={serveUrl,browserExecutable:chrome,puppeteerInstance:browser,logLevel:'error',inputProps:props};
 const composition=await selectComposition({...common,id:'PortraitVertical'});
 if(composition.width!==2160||composition.height!==3840||composition.fps!==60||composition.durationInFrames!==5400)throw Error('Native specs mismatch');
 if(mode==='stills'||mode==='covers'||mode==='headlines'){
  const frames=mode==='headlines'?[]:mode==='covers'?[2100,5040]:(args.length?args.map(Number):[60,900,1500,2280,2940,3480,3900,2100,4500,4859,4860,5040,5160,5399]);
  for(const frame of frames){
   const name=mode==='covers'?(frame===2100?'cover-A.png':'cover-B.png'):`source-${frame}.png`;
   const folder=mode==='covers'?'小红书':'review';
   await renderStill({...common,composition,frame,output:path.join(work,folder,name),imageFormat:'png'});console.log(`still ${frame} ${name}`);
  }
  if(mode==='covers'||mode==='headlines')for(const [kind,frame] of [['A',2100],['B',5040]]){const coverProps={silent:true,cover:kind};const coverComposition=await selectComposition({...common,inputProps:coverProps,id:'PortraitVertical'});await renderStill({...common,inputProps:coverProps,composition:coverComposition,frame,output:path.join(work,'小红书',`cover-${kind}-headline.png`),imageFormat:'png'});console.log(`headline ${kind}`);}
 }else{
  const preview=mode==='preview',start=Number(args[0]??120),end=Number(args[1]??299);
  const pointer=path.join(work,'review','render-staging.json');
  if(!preview&&fs.existsSync(pointer))throw Error('Staging pointer already exists; preserve native evidence');
  const stage=preview?null:fs.mkdtempSync(path.join(process.env.TMPDIR??os.tmpdir(),'si-ep19-native-'));
  const outputLocation=preview?path.join(work,'review',`motion-${start}-${end}.mp4`):path.join(stage,'video-only.mp4');
  if(fs.existsSync(outputLocation))throw Error('Refusing overwrite');
  const renderOptions={...common,composition,scale:1,muted:!preview,codec:'h264',audioCodec:'aac',audioBitrate:'320k',sampleRate:48000,pixelFormat:'yuv420p',colorSpace:'bt709',crf:18,x264Preset:'fast',imageFormat:'png',concurrency:1,metadata:{title:'替身社交 / PROXY ROMANCE',comment:'Pure2D science-fiction thought experiment. Native portrait2160x3840/60fps/5400frames/90seconds.'}};
  if(preview){
   await renderMedia({...renderOptions,outputLocation,frameRange:[start,end],onProgress:({progress})=>{if(progress===1)console.log(`preview ${start}-${end} complete`);}});
  }else{
   const chunks=[]; const disk=[];
   for(let first=0;first<5400;first+=180){
    const last=Math.min(5399,first+179),file=path.join(stage,`chunk-${String(first).padStart(4,'0')}.mp4`);
    const st=fs.statfsSync('/Volumes/AgentDev');const before=Number(st.bavail)*Number(st.bsize);
    if(before<21*1024**3)throw Error(`AgentDev headroom below21GiB before chunk ${first}; stopped safely`);
    await renderMedia({...renderOptions,outputLocation:file,frameRange:[first,last],onProgress:()=>{}});
    const afterStat=fs.statfsSync('/Volumes/AgentDev');const after=Number(afterStat.bavail)*Number(afterStat.bsize);
    if(after<20*1024**3)throw Error('AgentDev below required20GiB; preserve owned staging for inspection');
    chunks.push({startFrame:first,endFrameExclusive:last+1,file,sha256:await hashFile(file)});disk.push({first,before,after});
    fs.writeFileSync(path.join(stage,'chunks.json'),JSON.stringify({chunks,disk},null,2));
    console.log(`video ${Math.round((last+1)/5400*100)}% frames=${last+1}/5400 headroomGiB=${(after/1024**3).toFixed(2)}`);
   }
   const list=path.join(stage,'concat.txt');fs.writeFileSync(list,chunks.map(c=>`file '${c.file}'`).join('\n')+'\n');
   const result=spawnSync('ffmpeg',['-v','error','-n','-f','concat','-safe','0','-i',list,'-map','0:v:0','-c:v','copy','-an','-movflags','+faststart',outputLocation],{encoding:'utf8'});
   if(result.status!==0)throw Error(`Chunk concatenation failed: ${result.stderr}`);
   fs.writeFileSync(path.join(work,'review','render-chunks.json'),JSON.stringify({strategy:'native180-frame ranges; absolute frame clock; same capture settings; lossless encoded-track concat',chunks,disk},null,2)+'\n');
  }
  console.log(outputLocation);
  if(!preview)fs.writeFileSync(pointer,JSON.stringify({status:'READY',file:outputLocation,sha256:await hashFile(outputLocation),bytes:fs.statSync(outputLocation).size,capture:{remotion:'4.0.534',chrome,imageFormat:'png',concurrency:1,nativeWidth:2160,nativeHeight:3840},scope:'Owned rebuildable native video track on verified AgentDev scratch; formal outputs remain in repository'},null,2)+'\n',{flag:'wx'});
 }
}finally{await browser.close({silent:true});fs.rmSync(temp,{recursive:true,force:true});}
