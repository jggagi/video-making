"""Restore only EP12's new final Release asset into an isolated AgentDev directory."""
from pathlib import Path
import hashlib,json,os,subprocess,tempfile
P=Path(__file__).resolve().parents[1];W=P.parent;ROOT=W.parents[1]
sha=lambda p:hashlib.file_digest(open(p,'rb'),'sha256').hexdigest()
catalog=ROOT/'final/backup-catalog.json';full=json.loads(catalog.read_text());work=next(w for w in full['works'] if w['id']=='si-ep12-final-equation');assert len(work['assets'])==1
asset=work['assets'][0];assert asset['sha256']==json.loads((W/'delivery.json').read_text())['final_movie_sha256']
tmp=Path(os.environ['TMPDIR']).resolve();assert str(tmp).startswith('/Volumes/AgentDev/')
with tempfile.TemporaryDirectory(prefix='si-ep12-final-restore-',dir=tmp) as name:
 isolation=Path(name);probe=isolation/'probe-catalog.json';probe.write_text(json.dumps({**full,'works':[work]},ensure_ascii=False,indent=2)+'\n')
 argv=['python3',str(ROOT/'scripts/fetch-archive-assets.py'),'--root',str(isolation),'--catalog',str(probe),'--download']
 first=subprocess.check_output(argv,text=True);restored=isolation/asset['path'];assert restored.is_file();assert restored.stat().st_size==asset['bytes'] and sha(restored)==asset['sha256']
 identity=restored.stat();second=subprocess.check_output(argv,text=True);after=restored.stat();assert '1 already verified, 0 downloaded' in second and sha(restored)==asset['sha256'];assert identity.st_ino==after.st_ino
 report={'status':'PASS','scope':'Only the new EP12 portrait final was actually downloaded; no claim that all historical movies were restored.','catalog_sha256':sha(catalog),'release_tag':work['release_tag'],'asset_name':asset['name'],'restored_relative_path':asset['path'],'bytes':after.st_size,'sha256':sha(restored),'first_run_stdout':first.strip(),'second_run_stdout':second.strip(),'second_run_skipped_matching_file':True,'isolated_temporary_directory_cleaned_after_verification':True}
(W/'review/final-restore-probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['status','release_tag','bytes','sha256','second_run_skipped_matching_file']},indent=2))
