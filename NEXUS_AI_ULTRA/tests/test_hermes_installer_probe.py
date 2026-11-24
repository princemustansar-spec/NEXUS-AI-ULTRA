"""CLI portability tests, including genuine Windows PowerShell 5.1 in CI."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

HELPER=Path(__file__).parents[1]/'scripts/hermes_installer_probe.py'


def test_installer_helper_version_uses_file_not_inline_code():
    output=subprocess.check_output([sys.executable,'-B',str(HELPER),'version'],text=True)
    assert output.strip()=='.'.join(map(str,sys.version_info[:3]))


def test_installer_schema_file_preserves_quotes_and_unicode(tmp_path):
    installation=tmp_path/'source with spaces';package=installation/'nexus';package.mkdir(parents=True)
    (package/'__init__.py').write_text('')
    (package/'tools.py').write_text("CATALOG={'probe':('A Δ label with \\\"quoted\\\" text',False,{'value':'string'})}\n",encoding='utf-8')
    output=tmp_path/'schema output.json'
    subprocess.run([sys.executable,'-B',str(HELPER),'schemas','--installation',str(installation),'--output',str(output)],check=True)
    schemas=json.loads(output.read_text(encoding='utf-8'))
    assert schemas[0]['function']['description']=='A Δ label with "quoted" text'


@pytest.mark.skipif(sys.platform!='win32',reason='Requires native Windows PowerShell 5.1')
def test_native_windows_powershell_51_installer_helpers(tmp_path):
    powershell=shutil.which('powershell.exe')
    if not powershell:pytest.skip('Native Windows PowerShell unavailable')
    script=Path(__file__).with_name('windows_hermes_probe.ps1')
    result=subprocess.run([powershell,'-NoProfile','-ExecutionPolicy','Bypass','-File',str(script),
        '-Python',sys.executable,'-Helper',str(HELPER),'-Scratch',str(tmp_path)],capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+'\n'+result.stderr
    assert 'PASS: native Windows PowerShell 5.1' in result.stdout
