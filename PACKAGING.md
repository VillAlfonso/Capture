# Executables, names, and icons

The app is `QuietCapture.exe`; the optional monitor is `QuietCaptureMonitor.exe`. Both embed the image from `icon.png`. The repository currently has no file named `ico.png`. To use a different image, replace `icon.png` before rebuilding.

## Rebuild with your own application name

Use an identifiable name for your app, for example StudyCapture. In PowerShell:

```powershell
cd C:\quiet-capture
.\stop.cmd
# Close monitor windows before rebuilding their executable.
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1 -AppName StudyCapture -MonitorName StudyCaptureMonitor
.\start.cmd
```

The build updates executable filenames, internal names, product names, file descriptions, embedded icons, package-paths.json, and startup/manual shortcuts together. Do not simply rename an executable: shortcuts and restart paths may otherwise become inconsistent. The build script needs PyInstaller and Pillow in .venv. Both were installed during packaging.

Task Manager's Details tab shows executable filenames. Its Processes tab may show the embedded file description. The monitor's console can also have a Windows-owned host process such as cmd.exe or Windows Terminal; these system components retain their own names/icons. This build does not rename Python itself, Windows processes, or unrelated programs. Explorer/Task Manager can cache icons until refreshed or reopened.

## Files and restart

Keep the project folder in place: executables load the external config.json and encrypted key.dpapi from it. Credentials are NOT embedded in the executables or copied to dist. A distributable would require separate user setup; do not share key.dpapi.

Ctrl+Alt+F12 restarts the packaged executable and reloads configuration/key settings. Source-code changes require running build.ps1 again; restarting cannot update code already compiled into an executable. Use stop.cmd to stop without restarting. The monitor remains optional and independent.

One-directory builds keep dependencies in their matching dist subfolder. Do not move just the EXE without its _internal directory. Older build artifacts are retained, but current launchers use only package-paths.json.

## Point startup to an already-built executable

From the project folder, validate first:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\enable-startup.ps1 -ExecutablePath ".\dist\StudyCapture\StudyCapture.exe" -CheckOnly
```

Then run the same command without `-CheckOnly` to save the Startup and Start menu shortcuts. Use the path to your main app, not the monitor. It must be a compatible build with the current config.json layout. No app is launched. Relative paths resolve from the script folder. For a different drive, an absolute path is accepted.

This changes startup/manual shortcuts only. The start.cmd/debug.cmd/restart.cmd launchers use package-paths.json. Building through build.ps1 updates that manifest and startup together, so it is the simplest way to keep a newly named main app and monitor consistent. Stop the app and close the monitor before rebuilding files that are in use. After rebuilding, Ctrl+Alt+F12 restarts an already-running instance of the same executable; if changing to another name or path, stop the old instance and launch the new one.
