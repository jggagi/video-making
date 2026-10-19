import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const work=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const sdk='/Users/guoq/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
const {chromium}=await import(pathToFileURL(sdk).href);
const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--autoplay-policy=no-user-gesture-required']});
const errors=[],results=[];
try{
 const page=await browser.newPage({viewport:{width:1280,height:1000}});
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(pathToFileURL(path.join(work,'watch.html')).href);
 const snapshot=await page.locator('body').innerText();
 if(!snapshot.includes('B站 · 4K 横屏')||!snapshot.includes('小红书 · 4K 竖屏'))throw Error('Player controls missing');
 for(const [layout,name,w,h] of [['landscape','B站 · 4K 横屏',3840,2160],['portrait','小红书 · 4K 竖屏',2160,3840]]){
  await page.getByRole('button',{name,exact:true}).click();
  await page.waitForFunction(()=>{const v=document.querySelector('#film');return v.readyState>=2&&v.duration>0;},null,{timeout:30000});
  const video=page.locator('#film');
  const meta=await video.evaluate(v=>({width:v.videoWidth,height:v.videoHeight,duration:v.duration,error:v.error?.message??null}));
  if(meta.width!==w||meta.height!==h||Math.abs(meta.duration-120)>.05||meta.error)throw Error(`Metadata mismatch ${layout}: ${JSON.stringify(meta)}`);
  await video.evaluate(async v=>{v.muted=true;v.currentTime=0;await v.play();});
  await page.waitForFunction(()=>document.querySelector('#film').currentTime>.7,null,{timeout:15000});
  const playback=await video.evaluate(v=>({time:v.currentTime,paused:v.paused,totalFrames:v.getVideoPlaybackQuality().totalVideoFrames,droppedFrames:v.getVideoPlaybackQuality().droppedVideoFrames}));
  if(playback.paused||playback.totalFrames<3)throw Error('Playback did not advance');
  const seeks=[];
  for(const target of [16,48,80,96.5,118.5]){
   await video.evaluate(async(v,t)=>{v.pause();await new Promise((resolve,reject)=>{v.addEventListener('seeked',resolve,{once:true});v.addEventListener('error',reject,{once:true});v.currentTime=t;});},target);
   const value=await video.evaluate(v=>({time:v.currentTime,readyState:v.readyState,error:v.error?.message??null}));
   if(Math.abs(value.time-target)>.1||value.readyState<2||value.error)throw Error('Seek failed');
   seeks.push({target,...value});
  }
  await page.screenshot({path:path.join(work,'review',`browser-player-${layout}.jpg`),fullPage:true,type:'jpeg',quality:90});
  results.push({layout,metadata:meta,playback,seeks});
 }
 if(errors.length)throw Error(errors.join('\n'));
 const report={status:'PASS',method:'Real local Google Chrome via the repository-style bundled Playwright check; muted playback and seeks in the supplied local player',results,page_errors:errors,limitations:['No listening or pronunciation judgment; playback muted for automation.','Desktop browser only, not phone App or account upload evidence.']};
 fs.writeFileSync(path.join(work,'review/browser-player-qa.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));
}finally{await browser.close();}
