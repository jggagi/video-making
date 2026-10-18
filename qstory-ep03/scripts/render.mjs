import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {openBrowser,selectComposition,renderStill,renderMedia} from '@remotion/renderer';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const mode=process.argv[2]??'video';
const chrome='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
if(!fs.existsSync(chrome))throw Error('Local Chrome missing');
const out=path.join(root,'out');fs.mkdirSync(out,{recursive:true});
const serveUrl=await bundle({entryPoint:path.join(root,'src/index.ts'),publicDir:path.join(root,'public'),outDir:path.join(out,'bundle'),onProgress:()=>{}});
const browser=await openBrowser('chrome',{browserExecutable:chrome,logLevel:'error'});
try{
 const common={serveUrl,browserExecutable:chrome,puppeteerInstance:browser,logLevel:'error',inputProps:{silent:['stills','frame','frame4k','boundaries'].includes(mode)}};
 const id=['video','frame4k'].includes(mode)?'QStory-EP03-4K':'QStory-EP03-Preview';
 const composition=await selectComposition({...common,id});
 if(composition.durationInFrames!==5400||composition.fps!==30)throw Error('Timing mismatch');
 if(['stills','frame','frame4k','boundaries'].includes(mode)){
  const frames=mode==='stills'?[90,260,470,725,940,1150,1390,1640,1910,2160,2390,2660,2880,3170,3400,3650,3820,3940,4050,4200,4490,4690,4860,5030,5180,5350,5399]:mode==='boundaries'?[0,359,360,1259,1260,1799,1800,2549,2550,3299,3300,4349,4350,4949,4950,5399]:process.argv.slice(3).map(Number);
  for(const frame of frames){if(!Number.isInteger(frame)||frame<0||frame>=5400)throw Error('Frame out of range');await renderStill({...common,composition,frame,output:path.join(root,'review',`frame-${frame}-${id.endsWith('4K')?'4k':'hd'}.png`),imageFormat:'png'});console.log(`still ${frame}`)}
 }else{
  const sample=mode==='sample';const frameRange=sample?[3300,4349]:undefined;
  const outputLocation=path.join(out,sample?'climax-preview-1080p.mp4':'QStory-EP03-十万亿个分身-4K.mp4');
  let previous=-1;
  await renderMedia({...common,composition,outputLocation,frameRange,codec:'h264',audioCodec:'aac',audioBitrate:'320k',sampleRate:48000,pixelFormat:'yuv420p',colorSpace:'bt709',crf:17,x264Preset:'fast',imageFormat:'jpeg',jpegQuality:95,concurrency:2,metadata:{title:'十万亿个分身｜余问 QStory EP.03',comment:'180s 4K30 procedural vector film. Fictional SI thought experiment. Bailian CosyVoice v3 Flash, longtian_v3 Chinese narration; original procedural score.'},onProgress:({progress,renderedFrames})=>{const pc=Math.floor(progress*20)*5;if(pc!==previous){previous=pc;console.log(`${mode} ${pc}% (${renderedFrames}/${sample?1050:5400})`)}}});
  console.log(outputLocation);
 }
}finally{await browser.close({silent:true})}
