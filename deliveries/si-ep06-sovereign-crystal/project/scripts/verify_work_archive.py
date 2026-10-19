#!/usr/bin/env python3
"""Fresh read-only inventory of this film's normal and independent final Releases."""
import argparse,hashlib,json,subprocess
from pathlib import Path
P=Path(__file__).resolve().parents[1];W=P.parent;ROOT=W.parents[1]
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 a=argparse.ArgumentParser();a.add_argument('--source-commit',required=True);args=a.parse_args();slug=W.name;results={}
 remote_sha=subprocess.check_output(['gh','api',f'repos/jggagi/video-making/commits/{args.source_commit}','--jq','.sha'],text=True).strip()
 if remote_sha!=args.source_commit:raise ValueError('source commit is not accessible remotely')
 for kind,name in [('film','archive/catalog.json'),('final','final/backup-catalog.json')]:
  cp=ROOT/name;cat=json.loads(cp.read_text());work=next(w for w in cat['works'] if w['id']==slug);tag=work['release_tag'];release=json.loads(subprocess.check_output(['gh','api',f'repos/jggagi/video-making/releases/tags/{tag}'],text=True));rem={x['name']:x for x in release['assets']}
  if release['draft'] or set(rem)!=set(x['name'] for x in work['assets']):raise ValueError('unpublished or divergent release asset set')
  records=[]
  for asset in work['assets']:
   local=ROOT/asset['path'];r=rem[asset['name']]
   if local.stat().st_size!=asset['bytes'] or sha(local)!=asset['sha256']:raise ValueError('local catalog mismatch')
   if r['size']!=asset['bytes'] or r.get('digest')!='sha256:'+asset['sha256']:raise ValueError('remote size or SHA-256 mismatch')
   records.append(dict(name=asset['name'],path=asset['path'],bytes=asset['bytes'],sha256=asset['sha256'],remote_asset_id=r['id'],download_url=r['browser_download_url'],status='PASS'))
  results[kind]=dict(status='PASS',catalog=name,catalog_sha256=sha(cp),release_tag=tag,release_url=release['html_url'],assets=records)
 report=dict(status='PASS',source_commit=args.source_commit,source_commit_visible_on_github=True,film=results['film'],final=results['final'],scope='All current assets of this work in both independent Releases; global final inventory and restore probe recorded separately.')
 (W/'review/archive-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
