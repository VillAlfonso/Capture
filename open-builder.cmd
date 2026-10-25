@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Project Python environment is missing. See REBUILD.md.
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" "%~dp0builder_gui.py"
