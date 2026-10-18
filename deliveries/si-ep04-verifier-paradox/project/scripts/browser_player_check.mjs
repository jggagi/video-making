import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL,fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..','..');
const sdk=process.env.EP4_PLAYWRIGHT_MODULE??'/Users/guoq/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
const {chromium}=await import(sdk.startsWith('/')?pathToFileURL(sdk).href:sdk);
const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--autoplay-policy=no-user-gesture-required']});
const errors=[],results=[];
try{
 const page=await browser.newPage({viewport:{width:1280,height:1000}});
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(pathToFileURL(path.join(root,'watch.html')).href);
 await page.waitForLoadState('networkidle');
 const buttons=await page.getByRole('button').allTextContents();
 if(!buttons.includes('B站 · 横屏')||!buttons.includes('小红书 · 竖屏'))throw Error('Player controls missing');
 for(const [id,button,w,h] of [['landscape','B站 · 横屏',3840,2160],['portrait','小红书 · 竖屏',2160,3840]]){
  await page.getByRole('button',{name:button,exact:true}).click();
  const selector=`#${id} video`;
  await page.waitForFunction(sel=>{const v=document.querySelector(sel);return v&&v.readyState>=2&&v.duration>0},selector,{timeout:30000});
  const metadata=await page.locator(selector).evaluate(v=>({duration:v.duration,width:v.videoWidth,height:v.videoHeight,error:v.error?.message??null}));
  if(metadata.width!==w||metadata.height!==h||Math.abs(metadata.duration-120)>.05||metadata.error)throw Error(`Metadata failure ${id}: ${JSON.stringify(metadata)}`);
  await page.locator(selector).evaluate(async v=>{v.muted=true;v.currentTime=0;await v.play()});
  await page.waitForFunction(sel=>document.querySelector(sel).currentTime>.6,selector,{timeout:15000});
  const playing=await page.locator(selector).evaluate(v=>({currentTime:v.currentTime,paused:v.paused,quality:v.getVideoPlaybackQuality?{totalVideoFrames:v.getVideoPlaybackQuality().totalVideoFrames,droppedVideoFrames:v.getVideoPlaybackQuality().droppedVideoFrames}:null}));
  if(playing.paused||playing.quality?.totalVideoFrames<3)throw Error(`Playback did not advance/present frames ${id}`);
  const seeks=[];
  for(const target of [75.2,96.5,118.5]){
   await page.locator(selector).evaluate(async(v,t)=>{v.pause();await new Promise((resolve,reject)=>{v.addEventListener('seeked',resolve,{once:true});v.addEventListener('error',reject,{once:true});v.currentTime=t})},target);
   const state=await page.locator(selector).evaluate(v=>({time:v.currentTime,readyState:v.readyState,error:v.error?.message??null}));
   if(Math.abs(state.time-target)>.1||state.readyState<2||state.error)throw Error(`Seek failure ${id}`);
   seeks.push({target,...state});
  }
  await page.screenshot({path:path.join(root,'review',`browser-player-${id}.png`),fullPage:true});
  const other=id==='landscape'?'portrait':'landscape';
  const otherPaused=await page.locator(`#${other} video`).evaluate(v=>v.paused);
  if(!otherPaused)throw Error('Hidden video continued playing');
  results.push({layout:id,metadata,playback:playing,seeks,hidden_other_paused:otherPaused});
 }
 if(errors.length)throw Error(`Page errors: ${errors}`);
 const report={status:'PASS',method:'Real headless Google Chrome via bundled Playwright; local file player; playback and seeks',results,page_errors:errors,limitations:['Videos were muted for automation; no pronunciation or listening judgment','This is local desktop browser evidence, not phone App playback']};
 fs.writeFileSync(path.join(root,'review/browser-player-qa.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));
}finally{await browser.close();}
