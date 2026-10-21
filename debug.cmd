@echo off
setlocal
title Quiet Capture - Continuous Debug Console
cd /d "%~dp0"
echo ============================================================
echo   STARTING QUIET CAPTURE - CONTINUOUS DEBUG MODE
echo ============================================================
echo Starts PAUSED. Ctrl+Alt+F9 turns capture/typing ON or OFF.
echo Ctrl+Alt+F12 pauses; the process keeps running.
echo Close this console when you want to stop the debug process.
echo.
if not exist ".venv\Scripts\python.exe" (
  echo Python environment missing. Run setup.ps1 first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -u -B app.py --debug
echo.
echo Process ended or could not start. Review any errors above.
pause
