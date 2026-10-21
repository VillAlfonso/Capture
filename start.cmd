@echo off
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" -B "%~dp0app.py"
