import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
const root=process.cwd();
const server=http.createServer((req,res)=>{
  let relative;
  try{relative=decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname).slice(1);}catch{res.writeHead(400).end();return;}
  const file=path.resolve(root,relative||'extended-watch.html');
  if(!file.startsWith(root+path.sep)||!['.html','.mp4','.png','.vtt'].includes(path.extname(file))||relative.split('/').some(s=>s.startsWith('.'))){res.writeHead(403).end();return;}
  let stat;try{stat=fs.statSync(file);if(!stat.isFile())throw new Error();}catch{res.writeHead(404).end();return;}
  const type={'.html':'text/html; charset=utf-8','.mp4':'video/mp4','.png':'image/png','.vtt':'text/vtt; charset=utf-8'}[path.extname(file)];
  let start=0,end=stat.size-1,status=200;
  if(req.headers.range){
    const match=/^bytes=(\d*)-(\d*)$/.exec(req.headers.range);
    if(!match){res.writeHead(416,{'Content-Range':`bytes */${stat.size}`}).end();return;}
    if(match[1]){start=Number(match[1]);if(match[2])end=Math.min(end,Number(match[2]));}
    else if(match[2])start=Math.max(0,stat.size-Number(match[2]));
    if(start>end||start>=stat.size){res.writeHead(416,{'Content-Range':`bytes */${stat.size}`}).end();return;}
    status=206;
  }
  res.writeHead(status,{'Content-Type':type,'Content-Length':end-start+1,'Accept-Ranges':'bytes','Cache-Control':'no-cache',...(status===206?{'Content-Range':`bytes ${start}-${end}/${stat.size}`}:{})});
  if(req.method==='HEAD'){res.end();return;}
  fs.createReadStream(file,{start,end}).pipe(res);
});
server.listen(8031,'127.0.0.1',()=>console.log('Preview: http://127.0.0.1:8031/extended-watch.html'));
