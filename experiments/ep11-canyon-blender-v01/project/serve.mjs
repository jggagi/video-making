import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const types={'.html':'text/html; charset=utf-8','.mp4':'video/mp4','.png':'image/png','.jpg':'image/jpeg','.md':'text/plain; charset=utf-8'};
const server=http.createServer((req,res)=>{
  let relative;try{relative=decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname).slice(1)||'watch.html';}catch{res.writeHead(400).end();return;}
  const file=path.resolve(root,relative),type=types[path.extname(file)];
  if(!file.startsWith(root+path.sep)||!type||relative.split('/').some(s=>s.startsWith('.'))){res.writeHead(403).end();return;}
  let stat;try{stat=fs.statSync(file);if(!stat.isFile())throw Error();}catch{res.writeHead(404).end();return;}
  let start=0,end=stat.size-1,status=200;
  if(req.headers.range){
    const match=/^bytes=(\d*)-(\d*)$/.exec(req.headers.range);if(!match||(!match[1]&&!match[2])){res.writeHead(416).end();return;}
    if(match[1]){start=Number(match[1]);if(match[2])end=Math.min(end,Number(match[2]));}else start=Math.max(0,stat.size-Number(match[2]));
    if(start>end||start>=stat.size){res.writeHead(416,{'Content-Range':`bytes */${stat.size}`}).end();return;}status=206;
  }
  res.writeHead(status,{'Content-Type':type,'Content-Length':end-start+1,'Accept-Ranges':'bytes','Cache-Control':'no-cache',...(status===206?{'Content-Range':`bytes ${start}-${end}/${stat.size}`}:{})});
  if(req.method==='HEAD'){res.end();return;}fs.createReadStream(file,{start,end}).pipe(res);
});
server.listen(0,'127.0.0.1',()=>console.log(`http://127.0.0.1:${server.address().port}/watch.html`));
