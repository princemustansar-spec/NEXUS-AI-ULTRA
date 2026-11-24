"""Execute the delivery PowerShell command on disposable installations.

Uses PowerShell on Linux. It verifies real scripts/SDK and file behavior, not
Windows-only networking, COM, WebView2 or an actual user's installed runtime.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tarfile
import zipfile
import uuid

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parent
ROOT = Path('/workspace/hermes-installer-acceptance') / uuid.uuid4().hex
ZIP = Path('/workspace/artifacts/NEXUS-Hermes-Integration-v3.zip')
PWSH = Path('/workspace/tooling/powershell/pwsh')
HERMES_ROOT = Path(os.environ['HERMES_TEST_ROOT'])
HERMES_HOME = Path(os.environ['HERMES_TEST_HOME'])
HERMES_PYTHON = Path(os.environ['HERMES_TEST_PYTHON'])
COMMAND = r"$z=Join-Path $env:USERPROFILE 'Downloads\NEXUS-Hermes-Integration-v3.zip'; $t=Join-Path ([IO.Path]::GetTempPath()) ('nexus-hermes-'+[Guid]::NewGuid().ToString('N')); Expand-Archive -LiteralPath $z -DestinationPath $t; & (Get-Process -Id $PID).Path -NoProfile -ExecutionPolicy Bypass -File (Join-Path $t 'Install-NexusHermes.ps1') -Destination (Join-Path $env:USERPROFILE 'NEXUS_AI_ULTRA')"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def installation(label):
    folder=ROOT/label
    folder.mkdir(parents=True)
    user=folder/'user'
    user.mkdir()
    dest=user/'NEXUS_AI_ULTRA';dest.mkdir()
    archive=subprocess.check_output(['git','archive','b630568caa735e756f96b22db07a354f041db88b:NEXUS_AI_ULTRA'],cwd=REPO)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(dest,filter='data')
    (dest/'.venv').symlink_to('/workspace/NEXUS_AI_ULTRA/.venv',target_is_directory=True)
    data=user/'.nexus_ai_ultra';data.mkdir()
    with sqlite3.connect(data/'nexus.sqlite3') as db:
        db.execute('CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)')
        db.execute('INSERT INTO settings VALUES (?,?)',('name','Existing NEXUS name'))
        db.execute('INSERT INTO settings VALUES (?,?)',('voice','Existing selected voice'))
    (data/'private-avatar.png').write_bytes(b'fixture unchanged local avatar')
    (user/'Desktop').mkdir();(user/'Desktop/NEXUS.lnk').write_bytes(b'fixture desktop shortcut')
    downloads=user/'Downloads';downloads.mkdir();shutil.copyfile(ZIP,downloads/ZIP.name)
    hermes=folder/'localappdata/hermes';hermes.mkdir(parents=True)
    (hermes/'hermes-agent').symlink_to(HERMES_ROOT,target_is_directory=True)
    (hermes/'installs').symlink_to(HERMES_HOME/'installs',target_is_directory=True)
    (hermes/'tools').symlink_to('/workspace/hermes-integration-runtime',target_is_directory=True)
    # Native installed Python discovery has this suffix; the fixture executable
    # delegates to the real 3.14.9 interpreter on this Linux host.
    python_dir=next(Path('/workspace/hermes-integration-runtime').glob('python-3.14.9*'))
    if not (python_dir/'python.exe').exists():(python_dir/'python.exe').symlink_to(HERMES_PYTHON)
    (hermes/'config.yaml').write_text('model:\n  provider: MUST_NOT_BE_USED\n')
    (hermes/'.env').write_text('OPENAI_API_KEY=private-fixture-credential-do-not-output\n')
    original={p.relative_to(dest).as_posix():digest(p) for p in dest.rglob('*') if p.is_file() and '.venv' not in p.parts}
    external={str(p):digest(p) for p in [data/'nexus.sqlite3',data/'private-avatar.png',user/'Desktop/NEXUS.lnk',hermes/'config.yaml',hermes/'.env']}
    env=dict(os.environ,USERPROFILE=str(user),LOCALAPPDATA=str(folder/'localappdata'),
             XDG_CACHE_HOME='/workspace/.cache',XDG_CONFIG_HOME='/workspace/.config',XDG_DATA_HOME='/workspace/.local/share')
    return folder,user,dest,original,external,env


def run_ps(command,env):
    result=subprocess.run([str(PWSH),'-NoProfile','-Command',command],env=env,text=True,capture_output=True,timeout=90)
    assert 'private-fixture-credential' not in result.stdout+result.stderr
    return result


def unchanged_external(external):
    assert all(digest(Path(p))==value for p,value in external.items())


def laptop_fixture(folder,user,dest,before):
    shutil.copyfile(BASE/'compatibility/laptop-7931f0/baseline_app.py',dest/'nexus/app.py')
    # Model the EXISTING dependency interface for startup. This is not installed
    # into the real product; the user's session-store code must remain untouched.
    store=dest/'nexus/store.py'
    store.write_text(store.read_text()+"\nStore.chat_sessions = lambda self: [{'id': self.get('active_chat','legacy'), 'title': 'Fixture saved chat'}]\n")
    notes=b'# Private laptop notes\nExisting chat and voice updates must stay.\n'
    (dest/'PROJECT_STATE.md').write_bytes(notes)
    for name in ['nexus/app.py','nexus/store.py','PROJECT_STATE.md']:
        before[name]=digest(dest/name)
    extracted=folder/'package'
    with zipfile.ZipFile(ZIP) as archive:archive.extractall(extracted)
    manifest=json.loads((extracted/'manifest.json').read_text())
    state=next(e for e in manifest['files'] if e['path']=='PROJECT_STATE.md')
    # Actual user notes were not uploaded. The same guarded append operation is
    # exercised with a reviewed fixture hash, never with a force/ignore option.
    state['variants'][0]['previous_sha256']=digest(dest/'PROJECT_STATE.md')
    (extracted/'manifest.json').write_text(json.dumps(manifest))
    return extracted,notes


def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    results={}
    folder,user,dest,before,external,env=installation('success')
    result=run_ps(COMMAND,env)
    if result.returncode:
        raise AssertionError(result.stdout+'\n'+result.stderr)
    assert 'configuration verified' in result.stdout and 'Integrated:' in result.stdout
    descriptor=json.loads((dest/'hermes_runtime.json').read_text(encoding='utf-8-sig'))
    assert descriptor['build'].startswith('caafe5389ae5')
    with zipfile.ZipFile(ZIP) as archive:manifest=json.loads(archive.read('manifest.json'))
    changed={e['path'] for e in manifest['files']}
    for name,value in before.items():
        if name not in changed:assert digest(dest/name)==value,name
    unchanged_external(external)
    backup=next(user.glob('NEXUS_AI_ULTRA.hermes-backup-*'))
    for name in changed & set(before):assert digest(backup/name)==before[name]
    assert (dest/'PROJECT_STATE.md').read_bytes().startswith((backup/'PROJECT_STATE.md').read_bytes())
    results['exact_delivery_command_and_default_discovery']='passed'
    results['source_backup_and_unrelated_data_preservation']='passed'

    folder,user,dest,before,external,env=installation('reviewed-laptop')
    extracted,notes=laptop_fixture(folder,user,dest,before)
    command="& '"+str(extracted/'Install-NexusHermes.ps1')+"' -Destination '"+str(dest)+"'"
    result=run_ps(command,env)
    assert result.returncode==0,result.stdout+'\n'+result.stderr
    assert digest(dest/'nexus/app.py')==digest(BASE/'compatibility/laptop-7931f0/app.py')
    assert digest(dest/'nexus/store.py')==before['nexus/store.py']
    assert (dest/'PROJECT_STATE.md').read_bytes().startswith(notes)
    backup=next(user.glob('NEXUS_AI_ULTRA.hermes-backup-*'))
    assert digest(backup/'nexus/app.py')==before['nexus/app.py']
    assert (backup/'PROJECT_STATE.md').read_bytes()==notes
    unchanged_external(external)
    results['reviewed_laptop_variant_and_note_preservation']='passed'

    folder,user,dest,before,external,env=installation('laptop-missing-dependency')
    extracted,notes=laptop_fixture(folder,user,dest,before)
    # An incomplete local update must be detected by app startup, not delivered
    # as an apparently successful install with a broken dashboard.
    original_store=subprocess.check_output(['git','show','b630568caa735e756f96b22db07a354f041db88b:NEXUS_AI_ULTRA/nexus/store.py'],cwd=REPO)
    (dest/'nexus/store.py').write_bytes(original_store)
    before['nexus/store.py']=digest(dest/'nexus/store.py')
    result=run_ps("& '"+str(extracted/'Install-NexusHermes.ps1')+"' -Destination '"+str(dest)+"'",env)
    assert result.returncode!=0 and 'post-install' in result.stderr
    for name,value in before.items():assert digest(dest/name)==value,name
    assert not (dest/'hermes_runtime.json').exists()
    unchanged_external(external)
    results['missing_session_store_dependency_restores_laptop']='passed'

    # Reproduce Windows PowerShell's native quoting mode in the same runspace as
    # the installer; a fresh pwsh child would otherwise reset to Standard mode.
    folder,user,dest,before,external,env=installation('legacy native mode with spaces')
    extracted,notes=laptop_fixture(folder,user,dest,before)
    result=run_ps("$global:PSNativeCommandArgumentPassing='Legacy'; & '"+str(extracted/'Install-NexusHermes.ps1')+"' -Destination '"+str(dest)+"'",env)
    assert result.returncode==0,result.stdout+'\n'+result.stderr
    assert 'configuration verified' in result.stdout
    assert digest(dest/'nexus/app.py')==digest(BASE/'compatibility/laptop-7931f0/app.py')
    assert (dest/'PROJECT_STATE.md').read_bytes().startswith(notes)
    unchanged_external(external)
    results['legacy_native_argument_mode_and_paths_with_spaces']='passed'

    folder,user,dest,before,external,env=installation('helper-tampering')
    extracted=folder/'package'
    with zipfile.ZipFile(ZIP) as archive:archive.extractall(extracted)
    helper=extracted/'installer_probe.py'
    helper.write_text(helper.read_text()+"\nraise RuntimeError('must not execute')\n")
    result=run_ps("& '"+str(extracted/'Install-NexusHermes.ps1')+"' -Destination '"+str(dest)+"'",env)
    assert result.returncode!=0 and 'helper hash mismatch' in result.stderr
    for name,value in before.items():assert digest(dest/name)==value,name
    assert not list(user.glob('NEXUS_AI_ULTRA.hermes-backup-*'))
    unchanged_external(external)
    results['modified_helper_refused_before_execution']='passed'

    folder,user,dest,before,external,env=installation('modified-source')
    (dest/'nexus/app.py').write_text((dest/'nexus/app.py').read_text()+'\n# private local edit\n')
    edited=digest(dest/'nexus/app.py')
    result=run_ps(COMMAND,env)
    assert result.returncode!=0 and 'tested baseline' in result.stderr
    assert digest(dest/'nexus/app.py')==edited and not (dest/'hermes_runtime.json').exists()
    assert not list(user.glob('NEXUS_AI_ULTRA.hermes-backup-*'))
    unchanged_external(external)
    results['unknown_source_refusal_before_patch']='passed'

    folder,user,dest,before,external,env=installation('postflight-failure')
    extracted=folder/'package'
    with zipfile.ZipFile(ZIP) as archive:archive.extractall(extracted)
    bad=extracted/'payload/nexus/hermes_agent.py'
    bad.write_text(bad.read_text()+"\nraise RuntimeError('synthetic postflight failure')\n")
    manifest=json.loads((extracted/'manifest.json').read_text())
    next(e for e in manifest['files'] if e['path']=='nexus/hermes_agent.py')['sha256']=digest(bad)
    (extracted/'manifest.json').write_text(json.dumps(manifest))
    command="& '"+str(extracted/'Install-NexusHermes.ps1')+"' -Destination '"+str(dest)+"'"
    result=run_ps(command,env)
    assert result.returncode!=0 and 'post-install' in result.stderr
    for name,value in before.items():assert digest(dest/name)==value,name
    for name in ('nexus/hermes_agent.py','nexus/hermes_worker.py','hermes_runtime.json'):
        assert not (dest/name).exists(),name
    unchanged_external(external)
    results['failed_application_restores_original_files']='passed'

    # A manifest path cannot escape the destination, even if its checksum is valid.
    folder,user,dest,before,external,env=installation('unsafe-path')
    extracted=folder/'package'
    with zipfile.ZipFile(ZIP) as archive:archive.extractall(extracted)
    manifest=json.loads((extracted/'manifest.json').read_text());manifest['files'][0]['path']='../outside.py'
    (extracted/'manifest.json').write_text(json.dumps(manifest))
    result=run_ps("& '"+str(extracted/'Install-NexusHermes.ps1')+"' -Destination '"+str(dest)+"'",env)
    assert result.returncode!=0 and 'Unsafe package path' in result.stderr
    assert not (user/'outside.py').exists();unchanged_external(external)
    results['unsafe_package_path_rejected']='passed'
    receipt=dict(platform='PowerShell 7.7.0 on Linux; native Windows not exercised',checks=results)
    Path('/workspace/artifacts/hermes-installer-validation-v3.json').write_text(json.dumps(receipt,indent=2))
    Path('/workspace/artifacts/NEXUS-Hermes-Install-Command-v3.ps1').write_text(COMMAND+'\n')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
