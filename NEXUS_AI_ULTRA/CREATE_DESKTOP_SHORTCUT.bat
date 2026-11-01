@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
 echo Run INSTALL.bat first. For a portable build, right-click NEXUS_AI_ULTRA.exe and create a shortcut.
 pause
 exit /b 1
)
.venv\Scripts\python create_shortcut.py --source
pause
