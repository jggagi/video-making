import fs from 'node:fs';
import {spawnSync} from 'node:child_process';
for (const [start,end] of [[120,299],[2940,3119],[4800,5099]]) {
 if(fs.existsSync(`../review/motion-${start}-${end}.mp4`)) {console.log(`existing sample ${start}-${end} preserved`);continue;}
 const r=spawnSync(process.execPath,['scripts/render.mjs','preview',String(start),String(end)],{stdio:'inherit'});
 if(r.status!==0)process.exit(r.status??1);
}
