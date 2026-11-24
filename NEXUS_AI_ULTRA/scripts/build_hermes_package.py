"""Build the minimal offline integration ZIP; no user data or Hermes install included."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

BASELINE = 'b630568caa735e756f96b22db07a354f041db88b'
BUILD = 'caafe5389ae585ef77387a962aee05b1bcf17029'
FILES = ('.gitignore', 'nexus/app.py', 'nexus/providers.py', 'nexus/hermes_agent.py',
         'nexus/hermes_worker.py', 'docs/HERMES_MAIN_AGENT.md', 'PROJECT_STATE.md')
LAPTOP_APP_HASH = '7931f0dbef329bcddc925547e1a30a47915fb9d9aaae26640bf1dde2f9a05e1d'
LAPTOP_STATE_HASH = '175c091d3a9165bb843957ea4d3f0986cb901cade13b91e4ce8a695461eeb384'


def build(output):
    app = Path(__file__).resolve().parents[1]
    repository = app.parent
    entries, payload = [], {}
    for name in FILES:
        data = (app / name).read_bytes() if name!='PROJECT_STATE.md' else (app/'compatibility/HERMES_STATE_APPEND.md').read_bytes()
        prior = subprocess.run(['git','show',BASELINE+':NEXUS_AI_ULTRA/'+name],
                               cwd=repository,capture_output=True)
        previous = hashlib.sha256(prior.stdout).hexdigest() if prior.returncode==0 else None
        entry=dict(path=name,sha256=hashlib.sha256(data).hexdigest(),previous_sha256=previous,
                   source_path=name,operation='append' if name=='PROJECT_STATE.md' else 'replace',variants=[])
        if name=='nexus/app.py':
            original=(app/'compatibility/laptop-7931f0/baseline_app.py').read_bytes()
            assert hashlib.sha256(original).hexdigest()==LAPTOP_APP_HASH
            variant=(app/'compatibility/laptop-7931f0/app.py').read_bytes()
            source='variants/laptop-7931f0/nexus/app.py'
            payload['payload/'+source]=variant
            entry['variants'].append(dict(previous_sha256=LAPTOP_APP_HASH,sha256=hashlib.sha256(variant).hexdigest(),source_path=source,operation='replace'))
        if name=='PROJECT_STATE.md':
            entry['variants'].append(dict(previous_sha256=LAPTOP_STATE_HASH,sha256=entry['sha256'],source_path=name,operation='append'))
        entries.append(entry)
        payload['payload/'+name] = data
    manifest = dict(format=2,baseline=BASELINE,hermes_build=BUILD,files=entries)
    payload['manifest.json'] = json.dumps(manifest,indent=2).encode()
    payload['Install-NexusHermes.ps1'] = (app/'install_hermes.ps1').read_bytes()
    patch = subprocess.check_output(['git','diff','--binary',BASELINE,'--','NEXUS_AI_ULTRA'],cwd=repository)
    if b'nexus/hermes_worker.py' not in patch:
        raise RuntimeError('Stage new source files before building the reviewable source patch.')
    payload['SOURCE-CHANGES.patch'] = patch
    payload['validation/test_hermes_main.py'] = (app/'tests/test_hermes_main.py').read_bytes()
    payload['validation/test_hermes_laptop_compat.py'] = (app/'tests/test_hermes_laptop_compat.py').read_bytes()
    payload['READ-ME-FIRST.txt'] = (
        'NEXUS + Hermes main-agent integration\n'
        'Close every NEXUS window before installing. Existing native Hermes is required.\n'
        'No API keys, private data, portrait assets or Hermes dependencies are in this ZIP.\n'
        'Run Install-NexusHermes.ps1 with your existing NEXUS destination.\n'
        'See payload/docs/HERMES_MAIN_AGENT.md for exact scope and verification limits.\n'
    ).encode()
    output = Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,data in payload.items():archive.writestr(name,data)
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist())==set(payload)
        for entry in entries:
            assert hashlib.sha256(archive.read('payload/'+entry['path'])).hexdigest()==entry['sha256']
            for variant in entry['variants']:
                assert hashlib.sha256(archive.read('payload/'+variant['source_path'])).hexdigest()==variant['sha256']
    print(json.dumps(dict(file=str(output),bytes=output.stat().st_size,
                         sha256=hashlib.sha256(output.read_bytes()).hexdigest(),files=len(payload))))
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('output',type=Path)
    build(parser.parse_args().output)
