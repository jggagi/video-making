#!/usr/bin/env python3
"""Retry visual evidence only; retain audio/probe evidence for identical movies."""
import json
from pathlib import Path
import collect_qa as qa

report = json.loads(qa.QA_PATH.read_text())
prior = qa.REVIEW_DIR / 'final-qa-attempt01.json'
if not prior.exists():
    prior.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
for layout, result in report['outputs'].items():
    movie=qa.DELIVERY_DIR/result['path']
    if qa.sha256_file(movie)!=result['sha256']:
        raise SystemExit('Movie identity changed; run the full collector instead.')
names={f'{layout} representative frames and motion samples' for layout in qa.OUTPUTS}
report['checks']=[x for x in report['checks'] if x['name'] not in names]
report['failures']=[x for x in report['failures'] if x not in names]
report['incomplete']=[x for x in report['incomplete'] if x not in names]
for layout, config in qa.OUTPUTS.items():
    movie=qa.DELIVERY_DIR/report['outputs'][layout]['path']
    visual=qa.extract_visual_evidence(movie,layout,config['dimensions'],config['roi'],qa.motion_pairs(),qa.QA_DIR,report,persist=True)
    if visual is not None:
        report['outputs'][layout]['visual_evidence']=visual
report['visual_retry']={'reason':'Use output-local video stream index 0 for passthrough on the second FFmpeg output; prevent CFR duplicate motion samples.','previous_report':'review/final-qa-attempt01.json','media_identity_unchanged':True,'audio_and_probe_reused_by_sha256':True}
report['status']='FAIL' if report['failures'] else 'INCOMPLETE' if report['incomplete'] else 'PASS'
qa.QA_PATH.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':report['status'],'failures':report['failures'],'incomplete':report['incomplete']}))
raise SystemExit(0 if report['status']=='PASS' else 1)
