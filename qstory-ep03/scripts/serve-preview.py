#!/usr/bin/env python3
"""Loopback-only preview server with HTTP byte ranges for native MP4 seeking."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import functools,re
ROOT=Path(__file__).resolve().parents[1]
class Handler(SimpleHTTPRequestHandler):
    def send_head(self):
        self.byte_range=None
        path=Path(self.translate_path(self.path))
        if not path.is_file(): return super().send_head()
        stream=path.open('rb'); size=path.stat().st_size
        start,end=0,size-1
        header=self.headers.get('Range')
        if header:
            match=re.fullmatch(r'bytes=(\d*)-(\d*)',header.strip())
            if not match or not any(match.groups()):
                stream.close();self.send_error(416);return None
            a,b=match.groups()
            if a: start=int(a);end=min(int(b),size-1) if b else size-1
            else: start=max(0,size-int(b))
            if start>=size or end<start:
                stream.close();self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.end_headers();return None
            self.send_response(206)
            self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        else:self.send_response(200)
        self.send_header('Content-Type',self.guess_type(str(path)))
        self.send_header('Content-Length',str(end-start+1))
        self.send_header('Accept-Ranges','bytes')
        self.send_header('Last-Modified',self.date_time_string(path.stat().st_mtime))
        self.end_headers();stream.seek(start);self.byte_range=end-start+1
        return stream
    def copyfile(self,source,outputfile):
        if self.byte_range is None:return super().copyfile(source,outputfile)
        left=self.byte_range
        try:
            while left:
                data=source.read(min(left,1024*1024))
                if not data:break
                outputfile.write(data);left-=len(data)
        except (BrokenPipeError,ConnectionResetError):pass
if __name__=='__main__':
    server=ThreadingHTTPServer(('127.0.0.1',3104),functools.partial(Handler,directory=str(ROOT)))
    print('http://127.0.0.1:3104/watch.html',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:server.server_close()
