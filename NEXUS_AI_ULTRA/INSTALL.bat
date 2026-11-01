@echo off
cd /d "%~dp0"
if exist .venv\Scripts\python.exe goto dependencies
py -3.12 -m venv .venv 2>nul
if not errorlevel 1 goto dependencies
py -3.11 -m venv .venv
if errorlevel 1 goto failed
:dependencies
.venv\Scripts\python -c "import sys,struct; sys.exit(0 if sys.version_info[:2] in ((3,11),(3,12)) and struct.calcsize('P')==8 else 1)"
if errorlevel 1 (
 echo Use Python 3.11 or 3.12, 64-bit, for this Windows desktop release.
 goto failed
)
.venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 goto failed
.venv\Scripts\python create_shortcut.py --source
if errorlevel 1 echo Shortcut creation failed; START_NEXUS.bat still launches the desktop app.
echo Installation complete. Run START_NEXUS.bat or the NEXUS desktop shortcut.
echo If WebView2 is missing, install Microsoft Edge WebView2 Evergreen Runtime.
pause
exit /b 0
:failed
echo Installation failed. Install Python 3.11 or 3.12 x64, then retry. Inspect the error above.
pause
exit /b 1
