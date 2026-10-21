@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -B stop_app.py
if errorlevel 1 (
  pause
  exit /b 1
)
call "%~dp0start.cmd"
