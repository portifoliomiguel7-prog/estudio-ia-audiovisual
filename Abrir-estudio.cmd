@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" studio.py --serve --open
) else (
  python studio.py --serve --open
)
pause
