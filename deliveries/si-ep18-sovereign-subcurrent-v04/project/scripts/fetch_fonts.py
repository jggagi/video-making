"""Fetch redistributable OFL font sources from the official Google Fonts repository."""
from pathlib import Path
import hashlib
import json
import urllib.request

P = Path(__file__).resolve().parents[1]
F = P / 'public/fonts'
ASSETS = [
    ('NotoSerifSC.ttf', 'https://raw.githubusercontent.com/google/fonts/main/ofl/notoserifsc/NotoSerifSC%5Bwght%5D.ttf'),
    ('NotoSerifSC-OFL.txt', 'https://raw.githubusercontent.com/google/fonts/main/ofl/notoserifsc/OFL.txt'),
    ('RobotoMono.ttf', 'https://raw.githubusercontent.com/google/fonts/main/ofl/robotomono/RobotoMono%5Bwght%5D.ttf'),
    ('RobotoMono-OFL.txt', 'https://raw.githubusercontent.com/google/fonts/main/ofl/robotomono/OFL.txt'),
]
records = []
F.mkdir(parents=True, exist_ok=True)
for name, url in ASSETS:
    target = F / name
    if not target.exists():
        with urllib.request.urlopen(url, timeout=45) as response:
            payload = response.read()
        with target.open('xb') as output:
            output.write(payload)
    records.append({'path': str(target.relative_to(P)), 'source': url,
                    'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                    'bytes': target.stat().st_size, 'license': 'SIL Open Font License 1.1'})
    print(name, target.stat().st_size, flush=True)
(P / 'font-sources.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n')
