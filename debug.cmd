@echo off
setlocal
title Quiet Capture - Status Monitor
cd /d "%~dp0"
echo ============================================================
echo   QUIET CAPTURE - MONITOR ONLY
echo ============================================================
echo The background app runs independently of this terminal.
echo Ctrl+Alt+F9 toggles capture. Ctrl+Alt+F12 pauses and cancels.
echo If not running, use start.cmd. Closing this window only closes the monitor.
echo.
".venv\Scripts\python.exe" -u -B monitor.py
