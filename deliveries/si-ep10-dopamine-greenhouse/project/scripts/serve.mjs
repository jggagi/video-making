import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const types={'.html':'text/html; charset=utf-8','.mp4':'video/mp4','.png':'image/png','.jpg':'image/jpeg'};
const server=http.createServer((req,res)=>{
 let relative;try{relative=decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname).slice(1)||'watch.html';}catch{res.writeHead(400).end();return;}
 const f=path.resolve(root,relative),type=types[path.extname(f)];
 if(!f.startsWith(root+path.sep)||!type||relative.split('/').some(s=>s.startsWith('.'))){res.writeHead(403).end();return;}
 let st;try{st=fs.statSync(f);if(!st.isFile())throw Error();}catch{res.writeHead(404).end();return;}
 let start=0,end=st.size-1,status=200;
 if(req.headers.range){const m=/^bytes=(\d*)-(\d*)$/.exec(req.headers.range);if(!m){res.writeHead(416).end();return;}if(m[1]){start=Number(m[1]);if(m[2])end=Math.min(end,Number(m[2]));}else if(m[2])start=Math.max(0,st.size-Number(m[2]));if(start>end||start>=st.size){res.writeHead(416,{'Content-Range':`bytes */${st.size}`}).end();return;}status=206;}
 res.writeHead(status,{'Content-Type':type,'Content-Length':end-start+1,'Accept-Ranges':'bytes','Cache-Control':'no-cache',...(status===206?{'Content-Range':`bytes ${start}-${end}/${st.size}`}:{})});if(req.method==='HEAD'){res.end();return;}fs.createReadStream(f,{start,end}).pipe(res);
});
server.listen(0,'127.0.0.1',()=>console.log(`http://127.0.0.1:${server.address().port}/watch.html`));
