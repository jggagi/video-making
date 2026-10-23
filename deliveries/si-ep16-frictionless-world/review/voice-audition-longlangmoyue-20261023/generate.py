"""Generate only this explicitly authorized three-cue audition; never change profile."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess
import sys

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]
sys.path.insert(0, str(WORK / 'project/scripts'))
from synthesize import parse_provider_wav, write_canonical_wav, recursive_values


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(value):
    (HERE / 'provider-manifest.json').write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    plan = json.loads((HERE / 'plan.json').read_text())
    manifest_path = HERE / 'provider-manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {
        'version': 1, 'cli_version': '2.5.1', 'skill_version': '2.5.1',
        'authorization': plan['authorization'], 'calls': [],
        'raw_responses_or_signed_urls_saved': False,
        'auth_status_preflight': 'authenticated=true',
        'voice_list_preflight': 'Selected voice verified in official Qwen Plus base voice XLSX, row553; system --list-voices does not enumerate this base catalog',
        'environment_change': 'Reuses the already updated CLI2.5.1 and synchronized skills; no new profile changes',
    }
    env = os.environ.copy()
    env['PATH'] = '/Users/guoq/.local/n/bin:' + env.get('PATH', '')
    env.update(BAILIAN_CALLER_TYPE='agent', BAILIAN_CALLER_NAME='codex',
               BAILIAN_SKILL_NAME='bailian-gen', BAILIAN_SKILL_VERSION='2.5.1')
    for cue in plan['items']:
        settings = {k: plan[k] for k in ('model', 'voice', 'rate', 'format', 'sample_rate')}
        key = hashlib.sha256(json.dumps(
            {'text': cue['text'], 'instruction': cue['instruction'], **settings},
            sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        raw = HERE / 'qwen-raw' / f"{cue['segment_id']}-{key[:12]}.wav"
        canonical = raw.with_name(raw.stem + '-canonical.wav')
        old = next((x for x in manifest['calls'] if x.get('cache_key') == key), None)
        if old and old.get('status') == 'PASS':
            if digest(raw) != old['raw_sha256'] or digest(canonical) != old['canonical_sha256']:
                raise RuntimeError('Existing cache differs; retained without overwrite')
            print(cue['segment_id'], 'verified cache', flush=True)
            continue
        if old or raw.exists() or canonical.exists():
            raise RuntimeError('Existing attempt or unverified file retained; no automatic retry')
        if hashlib.sha256((HERE / cue['text_file']).read_bytes()).hexdigest() != cue['text_sha256']:
            raise RuntimeError('Prepared input text changed')
        record = {'segment_id': cue['segment_id'], 'cache_key': key,
                  'started_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  'requested_settings': settings, 'requested_instruction': cue['instruction'],
                  'text_sha256': cue['text_sha256'], 'status': 'STARTED'}
        manifest['calls'].append(record)
        save(manifest)
        proc = subprocess.run([
            '/Users/guoq/.local/n/bin/bl', 'speech', 'synthesize',
            '--model', plan['model'], '--voice', plan['voice'],
            '--text-file', str(HERE / cue['text_file']),
            '--instruction', cue['instruction'], '--rate', str(plan['rate']),
            '--format', plan['format'], '--sample-rate', str(plan['sample_rate']),
            '--out', str(raw), '--concurrent', '1', '--output', 'json',
        ], env=env, capture_output=True, text=True, check=False)
        record['cli_exit_code'] = proc.returncode
        if proc.returncode:
            record['status'] = 'FAILED'
            save(manifest)
            raise RuntimeError(f"{cue['segment_id']}: CLI exit {proc.returncode}; no retry or fallback")
        try:
            response = json.loads(proc.stdout)
        except ValueError:
            record['status'] = 'FAILED_NON_JSON'
            save(manifest)
            raise RuntimeError('CLI response not JSON; raw audio preserved') from None
        models = recursive_values(response, {'model', 'model_id', 'resolved_model'})
        voices = recursive_values(response, {'voice', 'voice_id', 'resolved_voice'})
        record.update(reported_models=models, reported_voices=voices,
                      identity_source='CLI response fields; not an independent acoustic identity test')
        if models != [plan['model']] or voices != [plan['voice']]:
            record['status'] = 'FAILED_IDENTITY_MISMATCH'
            save(manifest)
            raise RuntimeError('Unexpected reported model/voice; audio preserved without fallback')
        pcm, metadata = parse_provider_wav(raw.read_bytes())
        write_canonical_wav(canonical, pcm)
        record.update(status='PASS', raw_path=str(raw.relative_to(HERE)),
                      canonical_path=str(canonical.relative_to(HERE)),
                      raw_sha256=digest(raw), canonical_sha256=digest(canonical),
                      pcm=metadata,
                      completed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        save(manifest)
        print(json.dumps({'segment': cue['segment_id'], 'status': 'PASS',
                          'model': models[0], 'voice': voices[0],
                          'duration_seconds': metadata['actualDurationSeconds']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
