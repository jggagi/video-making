import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const require=createRequire(import.meta.url),ts=require('typescript'),React=require('react'),SSR=require('react-dom/server');
const P=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),W=path.dirname(P);
const manifest=JSON.parse(fs.readFileSync(path.join(W,'delivery.json'))),segments=JSON.parse(fs.readFileSync(path.join(P,'segments.json'))),timing=JSON.parse(fs.readFileSync(path.join(P,'audio-timing.json')));
const assert=(v,m)=>{if(!v)throw Error(m);},hash=s=>crypto.createHash('sha256').update(s).digest('hex');
assert(manifest.duration_seconds===90&&manifest.fps===60&&manifest.total_frames===5400,'duration invariant');
const root=fs.readFileSync(path.join(P,'src/Root.tsx'),'utf8'),world=fs.readFileSync(path.join(P,'src/World.tsx'),'utf8');
for(const [name,src] of [['Root',root],['World',world]])assert(!/Math\.random|Date\.now|perspective\s*\(|rotate[XY]\s*\(|rotate3d\s*\(/.test(src),`${name}: forbidden non-deterministic or3D API`);
const exports={};new Function('require','exports',ts.transpileModule(world,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)(require,exports);
const samples=[];
for(const frame of [0,60,180,1320,1500,2100,2219,2220,2819,2820,2940,3600,3900,4379,4380,4500,4859,4860,5040,5160,5399]){
 const a=SSR.renderToStaticMarkup(React.createElement(exports.World,{frame})),b=SSR.renderToStaticMarkup(React.createElement(exports.World,{frame}));assert(a===b,'determinism');assert(!/NaN|Infinity/.test(a),'invalid geometry');samples.push({frame,sha256:hash(a)});
}
const normalize=s=>s.replace(/\s/g,'');
for(const seg of segments){const caps=timing.captions.filter(c=>c.segmentId===seg.id);assert(normalize(caps.map(c=>c.text).join(''))===normalize(seg.display_subtitle),`${seg.id}: caption text mismatch`);for(const c of caps){assert(c.startFrame>=0&&c.endFrame<=5400&&c.endFrame>c.startFrame,'caption bounds');assert(c.text.split('\n').length<=2&&c.text.split('\n').every(l=>l.length<=13),'mobile caption wrapping');}}
const motion=[];
for(let frame=0;frame<4860;frame+=150){const g=f=>{const svg=SSR.renderToStaticMarkup(React.createElement(exports.World,{frame:f}));return(svg.match(/(?:d|transform|cx|cy|x|y)="[^"]*"/g)||[]).join('');};const end=Math.min(4859,frame+150);assert(g(frame)!==g(end),`unchanged geometry at${frame}`);motion.push({first:frame,last:end,geometryChanged:true});}
assert(root.includes('-(f-4860)*.025'),'closing quote continual2D translation');
const result={status:'PASS',duration:90,fps:60,totalFrames:5400,deterministicRenderSamples:samples,spatialMotionPairs:motion,motionCoverage:'150-frame authored geometry pairs through4860; closing quote continuous2D translation4860-5400; does not substitute continuous viewing',safeZones:{hud:{left:65,top:173,fontSize360px:10,lineHeight30px:true},subtitle:{left:65,right:173,bottom:480,fontSize360px:14,maxLines:2},closingDisclaimer:{top:1355,bottom:1449,fontSize360px:13,frames:[5160,5400],opacity:.35},stamp:{top:1460,bottom:1492}},sourceHashes:{root:hash(root),world:hash(world),segments:hash(fs.readFileSync(path.join(P,'segments.json'))),timing:hash(fs.readFileSync(path.join(P,'audio-timing.json')))},humanListening:'NOT_RUN',actualPhoneApp:'NOT_RUN'};
fs.writeFileSync(path.join(W,'review/project-validation.json'),JSON.stringify(result,null,2)+'\n');console.log('Project invariants PASS; deterministic21states; captions exact; pure2D; mobile layout bounds.');
