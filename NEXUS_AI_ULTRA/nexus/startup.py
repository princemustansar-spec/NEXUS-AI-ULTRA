"""Current-user Windows startup shortcut; no elevation or scheduled commands."""
import os
from pathlib import Path
import subprocess
import sys

def startup_path():
    if sys.platform!='win32':raise ValueError('Start with Windows requires Windows.')
    return Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs/Startup/NEXUS AI ULTRA.lnk'

def startup_status():
    return dict(available=sys.platform=='win32',enabled=startup_path().is_file() if sys.platform=='win32' else False)

def set_startup(root,enabled):
    if type(enabled) is not bool:raise ValueError('enabled must be true or false.')
    path=startup_path()
    if not enabled:
        path.unlink(missing_ok=True);return startup_status()
    root=Path(root).resolve();python=root/'.venv/Scripts/pythonw.exe';script=root/'run.py'
    if not python.is_file() or not script.is_file():raise ValueError('Install the Windows source version before enabling startup.')
    path.parent.mkdir(parents=True,exist_ok=True)
    code="""$ErrorActionPreference='Stop'
$shell=New-Object -ComObject WScript.Shell
$link=$shell.CreateShortcut($env:NEXUS_LOGIN_LINK)
$link.TargetPath=$env:NEXUS_LOGIN_TARGET
$link.Arguments='"'+$env:NEXUS_LOGIN_SCRIPT+'"'
$link.WorkingDirectory=$env:NEXUS_LOGIN_WORKING
$link.Description='NEXUS personal assistant at Windows sign-in'
$link.Save()
"""
    subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',code],env={**os.environ,'NEXUS_LOGIN_LINK':str(path),'NEXUS_LOGIN_TARGET':str(python),'NEXUS_LOGIN_SCRIPT':str(script),'NEXUS_LOGIN_WORKING':str(root)},check=True,capture_output=True,text=True)
    return startup_status()
